"""
Karaoke Command
Sing along with lyrics synced to SoundCloud audio playback

Features:
- Fixed selection of karaoke songs
- Locally stored timestamped lyrics (LRC format)
- Real-time lyric synchronization
- Progress bar and visual display
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select, Button
import asyncio
import time
from typing import Optional

import config
from utils.logger import log_command, logger
from utils.karaoke_data import (
    get_all_songs,
    get_song_by_id,
    load_song_lyrics,
    format_lyrics_progress,
    get_current_lyric,
    KaraokeSong,
    LyricLine
)

# Check if yt-dlp is available (used by the music system)
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    logger.warning("yt-dlp not installed - Karaoke audio playback unavailable")

# yt-dlp options for SoundCloud
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
}

# FFmpeg options for smooth playback
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
    'options': '-vn -ar 48000 -ac 2 -f s16le'
}


class KaraokeSession:
    """Manages an active karaoke session"""

    def __init__(
        self,
        guild_id: int,
        voice_client: discord.VoiceClient,
        song: KaraokeSong,
        lyrics: list,
        message: discord.Message,
        text_channel: discord.TextChannel
    ):
        self.guild_id = guild_id
        self.voice_client = voice_client
        self.song = song
        self.lyrics = lyrics
        self.message = message
        self.text_channel = text_channel
        self.start_time: float = 0
        self.is_playing: bool = False
        self.update_task: Optional[asyncio.Task] = None

    @property
    def elapsed_time(self) -> float:
        """Get elapsed playback time in seconds"""
        if not self.is_playing or self.start_time == 0:
            return 0
        return time.time() - self.start_time


class SongSelectView(View):
    """View for selecting a karaoke song"""

    def __init__(self, cog: 'Karaoke', user: discord.Member, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user = user
        self.selected_song: Optional[KaraokeSong] = None

        # Create song selection dropdown
        self._add_song_select()

    def _add_song_select(self):
        """Add the song selection dropdown"""
        songs = get_all_songs()

        select = Select(
            placeholder="Choose a song to sing...",
            custom_id="song_select",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=song.title,
                    description=f"by {song.artist}",
                    value=song.id,
                    emoji=self._get_song_emoji(song.id)
                )
                for song in songs
            ]
        )
        select.callback = self.song_selected
        self.add_item(select)

    def _get_song_emoji(self, song_id: str) -> str:
        """Get an emoji for each song"""
        emojis = {
            "happier": "😊",
            "stereo_hearts": "💕",
            "viva_la_vida": "👑",
            "something_blue": "💙"
        }
        return emojis.get(song_id, "🎤")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to interact"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "Only the person who started karaoke can select a song!",
                ephemeral=True
            )
            return False
        return True

    async def song_selected(self, interaction: discord.Interaction):
        """Handle song selection"""
        song_id = interaction.data["values"][0]
        self.selected_song = get_song_by_id(song_id)

        if not self.selected_song:
            await interaction.response.send_message(
                "Song not found! Please try again.",
                ephemeral=True
            )
            return

        # Start the karaoke session
        await interaction.response.defer()
        await self.cog.start_karaoke_session(interaction, self.selected_song)
        self.stop()

    async def on_timeout(self):
        """Handle timeout"""
        for item in self.children:
            item.disabled = True


class KaraokeControlView(View):
    """Controls for an active karaoke session"""

    def __init__(self, cog: 'Karaoke', guild_id: int, timeout: float = None):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="Stop Karaoke", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_button(self, interaction: discord.Interaction, button: Button):
        """Stop the karaoke session"""
        session = self.cog.sessions.get(self.guild_id)
        if not session:
            await interaction.response.send_message(
                "No active karaoke session!",
                ephemeral=True
            )
            return

        await self.cog.stop_karaoke_session(self.guild_id)
        await interaction.response.send_message(
            "Karaoke session ended! Thanks for singing! 🎤",
            ephemeral=False
        )
        self.stop()


class Karaoke(commands.Cog):
    """Karaoke command with synced lyrics"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, KaraokeSession] = {}
        self._ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) if YTDLP_AVAILABLE else None

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        for guild_id in list(self.sessions.keys()):
            asyncio.create_task(self.stop_karaoke_session(guild_id))

    @app_commands.command(name="karaoke", description="Start a karaoke session with synced lyrics!")
    async def karaoke(self, interaction: discord.Interaction):
        """Start karaoke mode with song selection"""
        log_command(str(interaction.user), interaction.user.id, "karaoke", interaction.guild.name)

        # Check if yt-dlp is available
        if not YTDLP_AVAILABLE:
            await interaction.response.send_message(
                "Karaoke is unavailable - audio system not configured.",
                ephemeral=True
            )
            return

        # Check if user is in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "You need to be in a voice channel to use karaoke! 🎤",
                ephemeral=True
            )
            return

        # Check if already in a session in this guild
        if interaction.guild.id in self.sessions:
            await interaction.response.send_message(
                "A karaoke session is already active! Use the Stop button to end it first.",
                ephemeral=True
            )
            return

        # Create song selection embed
        songs = get_all_songs()

        embed = discord.Embed(
            title="🎤 Karaoke Mode",
            description="Select a song to sing along with synced lyrics!",
            color=discord.Color.magenta()
        )

        # List available songs
        song_list = "\n".join([
            f"**{i+1}.** {song.title} - *{song.artist}*"
            for i, song in enumerate(songs)
        ])
        embed.add_field(name="Available Songs", value=song_list, inline=False)

        embed.add_field(
            name="How it works",
            value=(
                "1. Select a song from the dropdown below\n"
                "2. The bot will join your voice channel\n"
                "3. Lyrics will appear synced to the music!\n"
                "4. Sing along and have fun! 🎵"
            ),
            inline=False
        )

        embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        # Create view with song selection
        view = SongSelectView(self, interaction.user)

        await interaction.response.send_message(embed=embed, view=view)

    async def start_karaoke_session(self, interaction: discord.Interaction, song: KaraokeSong):
        """Start a karaoke session for the selected song"""
        guild = interaction.guild
        user = interaction.user

        # Load lyrics
        lyrics = load_song_lyrics(song)

        if not lyrics:
            await interaction.followup.send(
                f"Could not load lyrics for **{song.display_name}**.\n"
                f"Please check that `data/karaoke/{song.lyrics_file}` exists and is properly formatted.",
                ephemeral=True
            )
            return

        # Join voice channel
        voice_channel = user.voice.channel
        try:
            if guild.voice_client:
                await guild.voice_client.move_to(voice_channel)
                voice_client = guild.voice_client
            else:
                voice_client = await voice_channel.connect()
        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            await interaction.followup.send(
                f"Could not join voice channel: {e}",
                ephemeral=True
            )
            return

        # Get audio URL from SoundCloud
        try:
            # Search for the song on SoundCloud
            search_query = f"scsearch:{song.title} {song.artist}"
            data = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._ytdl.extract_info(search_query, download=False)
            )

            if 'entries' in data:
                data = data['entries'][0]

            audio_url = data.get('url')
            if not audio_url:
                raise Exception("No audio URL found")

        except Exception as e:
            logger.error(f"Failed to get audio for karaoke: {e}")
            await voice_client.disconnect()
            await interaction.followup.send(
                f"Could not find audio for **{song.display_name}** on SoundCloud.\n"
                "Please check the song URL in the karaoke registry.",
                ephemeral=True
            )
            return

        # Create initial lyrics embed
        embed = discord.Embed(
            title=f"🎤 Now Playing: {song.title}",
            description=f"**{song.artist}**",
            color=discord.Color.magenta()
        )
        embed.add_field(
            name="Lyrics",
            value="*Starting...*",
            inline=False
        )
        embed.set_footer(text="🎵 Sing along! | Use the Stop button to end")

        # Send lyrics message
        view = KaraokeControlView(self, guild.id)
        lyrics_message = await interaction.followup.send(embed=embed, view=view)

        # Create session
        session = KaraokeSession(
            guild_id=guild.id,
            voice_client=voice_client,
            song=song,
            lyrics=lyrics,
            message=lyrics_message,
            text_channel=interaction.channel
        )
        self.sessions[guild.id] = session

        # Start audio playback
        try:
            source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=0.7)

            def after_playing(error):
                if error:
                    logger.error(f"Karaoke playback error: {error}")
                asyncio.run_coroutine_threadsafe(
                    self.stop_karaoke_session(guild.id),
                    self.bot.loop
                )

            voice_client.play(source, after=after_playing)
            session.start_time = time.time()
            session.is_playing = True

            # Start lyrics update task
            session.update_task = asyncio.create_task(
                self._update_lyrics_loop(session)
            )

            logger.info(f"Karaoke session started: {song.display_name} in {guild.name}")

        except Exception as e:
            logger.error(f"Failed to start karaoke playback: {e}")
            await voice_client.disconnect()
            del self.sessions[guild.id]
            await interaction.followup.send(
                f"Failed to start audio playback: {e}",
                ephemeral=True
            )

    async def _update_lyrics_loop(self, session: KaraokeSession):
        """Background task to update lyrics display"""
        try:
            last_line_idx = -1

            while session.is_playing and session.guild_id in self.sessions:
                current_time = session.elapsed_time

                # Get current lyric position
                current_idx, _ = get_current_lyric(session.lyrics, current_time)

                # Only update if we've moved to a new line
                if current_idx != last_line_idx:
                    last_line_idx = current_idx

                    # Build updated embed
                    lyrics_display = format_lyrics_progress(
                        session.lyrics,
                        current_time,
                        session.song.duration
                    )

                    embed = discord.Embed(
                        title=f"🎤 Now Playing: {session.song.title}",
                        description=f"**{session.song.artist}**",
                        color=discord.Color.magenta()
                    )
                    embed.add_field(
                        name="Lyrics",
                        value=lyrics_display,
                        inline=False
                    )
                    embed.set_footer(text="🎵 Sing along! | Use the Stop button to end")

                    try:
                        await session.message.edit(embed=embed)
                    except discord.errors.NotFound:
                        # Message was deleted
                        break
                    except Exception as e:
                        logger.warning(f"Failed to update karaoke lyrics: {e}")

                # Check every 500ms for smoother updates
                await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Karaoke lyrics update error: {e}")

    async def stop_karaoke_session(self, guild_id: int):
        """Stop a karaoke session"""
        session = self.sessions.get(guild_id)
        if not session:
            return

        session.is_playing = False

        # Cancel update task
        if session.update_task:
            session.update_task.cancel()
            try:
                await session.update_task
            except asyncio.CancelledError:
                pass

        # Stop audio and disconnect
        if session.voice_client:
            if session.voice_client.is_playing():
                session.voice_client.stop()
            await session.voice_client.disconnect()

        # Update final message
        try:
            embed = discord.Embed(
                title="🎤 Karaoke Session Ended",
                description=f"Thanks for singing **{session.song.title}**!",
                color=discord.Color.grey()
            )
            embed.set_footer(text="Use /karaoke to start again!")
            await session.message.edit(embed=embed, view=None)
        except:
            pass

        # Remove session
        del self.sessions[guild_id]
        logger.info(f"Karaoke session ended in guild {guild_id}")


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Karaoke cog to the bot"""
    await bot.add_cog(Karaoke(bot))
