"""
Karaoke Command
Sing along with lyrics synced to SoundCloud audio playback

Features:
- Solo mode: Spotlight on a single singer
- Duet mode: Two singers with alternating lyric lines
- Countdown before performance starts
- Real-time lyric synchronization
- Progress bar and visual display
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select, Button
import asyncio
import time
from typing import Optional, List, Tuple

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
        text_channel: discord.TextChannel,
        mode: str = "solo",
        singers: List[discord.Member] = None
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
        self.mode = mode  # "solo" or "duet"
        self.singers = singers or []  # List of singers (1 for solo, 2 for duet)

    @property
    def elapsed_time(self) -> float:
        """Get elapsed playback time in seconds"""
        if not self.is_playing or self.start_time == 0:
            return 0
        return time.time() - self.start_time

    def get_current_singer_for_line(self, line_index: int) -> Optional[discord.Member]:
        """Get which singer should sing the current line (for duet mode)"""
        if self.mode == "solo" and self.singers:
            return self.singers[0]
        elif self.mode == "duet" and len(self.singers) >= 2:
            # Alternate between singers
            return self.singers[line_index % 2]
        return None


class SongSelectView(View):
    """View for selecting a karaoke song"""

    def __init__(self, cog: 'Karaoke', user: discord.Member, mode: str, singers: List[discord.Member], timeout: float = 120):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user = user
        self.mode = mode
        self.singers = singers
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
        await self.cog.start_karaoke_session(interaction, self.selected_song, self.mode, self.singers)
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

    # =============================================================================
    # SOLO MODE
    # =============================================================================

    @app_commands.command(name="karaokesolo", description="Start a solo karaoke performance with spotlight on the singer!")
    @app_commands.describe(singer="The person who will be singing")
    async def karaokesolo(self, interaction: discord.Interaction, singer: discord.Member):
        """Start karaoke in solo mode with a spotlight singer"""
        log_command(str(interaction.user), interaction.user.id, "karaokesolo", interaction.guild.name)

        # Validation checks
        if not await self._validate_karaoke_start(interaction, singer):
            return

        # Create song selection embed with singer announcement
        songs = get_all_songs()

        embed = discord.Embed(
            title="🎤 SOLO KARAOKE MODE",
            description=f"**{singer.display_name}** is about to take the stage!",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="🌟 Tonight's Star",
            value=f"{singer.mention}",
            inline=True
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
                "2. A 5-second countdown will begin\n"
                "3. The spotlight is on you - SING YOUR HEART OUT! 🎵"
            ),
            inline=False
        )

        embed.set_footer(text=f"Karaoke started by {interaction.user.display_name}")

        # Create view with song selection
        view = SongSelectView(self, interaction.user, "solo", [singer])

        await interaction.response.send_message(embed=embed, view=view)

    # =============================================================================
    # DUET MODE
    # =============================================================================

    @app_commands.command(name="karaokeduet", description="Start a duet karaoke with two singers taking turns!")
    @app_commands.describe(
        singer1="First singer (sings odd lines)",
        singer2="Second singer (sings even lines)"
    )
    async def karaokeduet(self, interaction: discord.Interaction, singer1: discord.Member, singer2: discord.Member):
        """Start karaoke in duet mode with alternating lyrics"""
        log_command(str(interaction.user), interaction.user.id, "karaokeduet", interaction.guild.name)

        # Check if singers are the same person
        if singer1.id == singer2.id:
            await interaction.response.send_message(
                "A duet needs TWO different people! Pick someone else to sing with.",
                ephemeral=True
            )
            return

        # Validation checks for both singers
        if not await self._validate_karaoke_start(interaction, singer1, singer2):
            return

        # Create song selection embed with both singers
        songs = get_all_songs()

        embed = discord.Embed(
            title="🎤 DUET KARAOKE MODE",
            description="Two voices, one song!",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="🎵 Singer 1 (Odd Lines)",
            value=f"{singer1.mention}",
            inline=True
        )
        embed.add_field(
            name="🎵 Singer 2 (Even Lines)",
            value=f"{singer2.mention}",
            inline=True
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
                "2. A 5-second countdown will begin\n"
                "3. Lyrics will alternate between both singers!\n"
                "4. Watch for YOUR name to know when to sing! 🎵"
            ),
            inline=False
        )

        embed.set_footer(text=f"Karaoke started by {interaction.user.display_name}")

        # Create view with song selection
        view = SongSelectView(self, interaction.user, "duet", [singer1, singer2])

        await interaction.response.send_message(embed=embed, view=view)

    # =============================================================================
    # LEGACY KARAOKE COMMAND (redirects to solo)
    # =============================================================================

    @app_commands.command(name="karaoke", description="Start a karaoke session - use /karaokesolo or /karaokeduet instead!")
    async def karaoke(self, interaction: discord.Interaction):
        """Legacy karaoke command - redirects users to new commands"""
        log_command(str(interaction.user), interaction.user.id, "karaoke", interaction.guild.name)

        embed = discord.Embed(
            title="🎤 Karaoke Has Been Upgraded!",
            description="Choose your performance mode:",
            color=discord.Color.magenta()
        )

        embed.add_field(
            name="🌟 Solo Mode",
            value=(
                "`/karaokesolo @user`\n"
                "One singer takes the spotlight!\n"
                "Perfect for showing off your skills."
            ),
            inline=True
        )

        embed.add_field(
            name="👯 Duet Mode",
            value=(
                "`/karaokeduet @user1 @user2`\n"
                "Two singers, alternating lines!\n"
                "Great for singing with friends."
            ),
            inline=True
        )

        embed.add_field(
            name="📋 Song List",
            value="`/karaokelist`\nSee all available songs!",
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    # =============================================================================
    # HELPER METHODS
    # =============================================================================

    async def _validate_karaoke_start(self, interaction: discord.Interaction, *singers: discord.Member) -> bool:
        """Validate that karaoke can start"""
        # Check if yt-dlp is available
        if not YTDLP_AVAILABLE:
            await interaction.response.send_message(
                "Karaoke is unavailable - audio system not configured.",
                ephemeral=True
            )
            return False

        # Check if all singers are in a voice channel
        for singer in singers:
            if not singer.voice or not singer.voice.channel:
                await interaction.response.send_message(
                    f"{singer.display_name} needs to be in a voice channel to sing! 🎤",
                    ephemeral=True
                )
                return False

        # Check if all singers are in the SAME voice channel
        if len(singers) > 1:
            channels = set(s.voice.channel.id for s in singers)
            if len(channels) > 1:
                await interaction.response.send_message(
                    "Both singers need to be in the SAME voice channel for a duet!",
                    ephemeral=True
                )
                return False

        # Check if already in a session in this guild
        if interaction.guild.id in self.sessions:
            await interaction.response.send_message(
                "A karaoke session is already active! Use the Stop button to end it first.",
                ephemeral=True
            )
            return False

        return True

    async def _perform_countdown(self, channel: discord.TextChannel, singers: List[discord.Member], mode: str) -> discord.Message:
        """
        Perform a 5-second countdown before the song starts
        Returns the countdown message for later editing
        """
        # Build singer announcement
        if mode == "solo":
            singer_text = f"🌟 **{singers[0].display_name}** 🌟"
        else:
            singer_text = f"🎵 **{singers[0].display_name}** & **{singers[1].display_name}** 🎵"

        # Initial countdown embed
        embed = discord.Embed(
            title="🎤 GET READY!",
            description=f"Now performing: {singer_text}",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Starting in...",
            value="```\n   🔴 5 🔴\n```",
            inline=False
        )
        embed.set_footer(text="Get ready to sing!")

        countdown_msg = await channel.send(embed=embed)

        # Countdown loop: 5, 4, 3, 2, 1
        countdown_emojis = {
            5: "🔴",
            4: "🟠",
            3: "🟡",
            2: "🟢",
            1: "💚"
        }

        for i in range(4, 0, -1):
            await asyncio.sleep(1)
            emoji = countdown_emojis.get(i, "⭐")
            embed.set_field_at(
                0,
                name="Starting in...",
                value=f"```\n   {emoji} {i} {emoji}\n```",
                inline=False
            )
            await countdown_msg.edit(embed=embed)

        # Final "GO!" message
        await asyncio.sleep(1)
        embed = discord.Embed(
            title="🎤 LET'S GO!",
            description=f"🎵 **SING!** 🎵\n\n{singer_text}",
            color=discord.Color.green()
        )
        await countdown_msg.edit(embed=embed)

        # Brief pause then return
        await asyncio.sleep(0.5)
        return countdown_msg

    async def start_karaoke_session(
        self,
        interaction: discord.Interaction,
        song: KaraokeSong,
        mode: str,
        singers: List[discord.Member]
    ):
        """Start a karaoke session for the selected song"""
        guild = interaction.guild
        user = interaction.user

        # Load lyrics
        lyrics = load_song_lyrics(song)

        if not lyrics:
            await interaction.followup.send(
                f"Could not load lyrics for **{song.display_name}**.\n"
                f"Please check that `lyrics/{song.lyrics_file}` exists and is properly formatted.",
                ephemeral=True
            )
            return

        # Join voice channel (use first singer's channel)
        voice_channel = singers[0].voice.channel
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

        # Send "preparing" message
        preparing_embed = discord.Embed(
            title="🎤 Preparing Stage...",
            description="Setting up your karaoke session!",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=preparing_embed)

        # Perform the countdown!
        await self._perform_countdown(interaction.channel, singers, mode)

        # Create initial lyrics embed
        if mode == "solo":
            title = f"🎤 Now Singing: {singers[0].display_name}"
            description = f"**{song.title}** by *{song.artist}*"
        else:
            title = f"🎤 Duet: {singers[0].display_name} & {singers[1].display_name}"
            description = f"**{song.title}** by *{song.artist}*"

        embed = discord.Embed(
            title=title,
            description=description,
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
        lyrics_message = await interaction.channel.send(embed=embed, view=view)

        # Create session
        session = KaraokeSession(
            guild_id=guild.id,
            voice_client=voice_client,
            song=song,
            lyrics=lyrics,
            message=lyrics_message,
            text_channel=interaction.channel,
            mode=mode,
            singers=singers
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

            logger.info(f"Karaoke session started: {song.display_name} in {guild.name} ({mode} mode)")

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

                    # Build updated embed based on mode
                    if session.mode == "duet":
                        lyrics_display = self._format_duet_lyrics(session, current_time, current_idx)
                    else:
                        lyrics_display = format_lyrics_progress(
                            session.lyrics,
                            current_time,
                            session.song.duration
                        )

                    if session.mode == "solo":
                        title = f"🎤 Now Singing: {session.singers[0].display_name}"
                    else:
                        # Highlight current singer
                        current_singer = session.get_current_singer_for_line(current_idx)
                        if current_singer:
                            title = f"🎤 {current_singer.display_name}'s Turn!"
                        else:
                            title = f"🎤 Duet: {session.singers[0].display_name} & {session.singers[1].display_name}"

                    embed = discord.Embed(
                        title=title,
                        description=f"**{session.song.title}** by *{session.song.artist}*",
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

    def _format_duet_lyrics(self, session: KaraokeSession, current_time: float, current_idx: int) -> str:
        """Format lyrics for duet mode with singer indicators"""
        lyrics = session.lyrics
        duration = session.song.duration

        if not lyrics:
            return "*No lyrics loaded - check LRC file*"

        # Progress bar
        progress = min(1.0, current_time / duration) if duration > 0 else 0
        bar_length = 20
        filled = int(bar_length * progress)
        bar = "=" * filled + "-" * (bar_length - filled)

        # Time display
        current_mins = int(current_time // 60)
        current_secs = int(current_time % 60)
        total_mins = int(duration // 60)
        total_secs = int(duration % 60)
        time_str = f"{current_mins}:{current_secs:02d} / {total_mins}:{total_secs:02d}"

        # Build lyrics display with singer indicators
        lines = []
        context_lines = 2

        # Previous lines (dimmed)
        start_idx = max(0, current_idx - context_lines)
        for i in range(start_idx, current_idx):
            singer = session.get_current_singer_for_line(i)
            singer_tag = f"[{singer.display_name[:10]}]" if singer else ""
            lines.append(f"*{singer_tag} {lyrics[i].text}*")  # Italic for past lines

        # Current line (bold with singer highlighted)
        if current_idx < len(lyrics):
            singer = session.get_current_singer_for_line(current_idx)
            singer_tag = f"🎤 {singer.display_name}" if singer else "🎤"
            lines.append(f"**>> [{singer_tag}] {lyrics[current_idx].text} <<**")

        # Upcoming lines
        end_idx = min(len(lyrics), current_idx + context_lines + 1)
        for i in range(current_idx + 1, end_idx):
            singer = session.get_current_singer_for_line(i)
            singer_tag = f"[{singer.display_name[:10]}]" if singer else ""
            lines.append(f"{singer_tag} {lyrics[i].text}")

        lyrics_display = "\n".join(lines) if lines else "*Instrumental*"

        return f"```\n[{bar}] {time_str}\n```\n\n{lyrics_display}"

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
            if session.mode == "solo":
                thanks_to = session.singers[0].display_name
            else:
                thanks_to = f"{session.singers[0].display_name} & {session.singers[1].display_name}"

            embed = discord.Embed(
                title="🎤 Karaoke Session Ended",
                description=f"Amazing performance by **{thanks_to}**!\nThanks for singing **{session.song.title}**! 👏",
                color=discord.Color.grey()
            )
            embed.set_footer(text="Use /karaokesolo or /karaokeduet to start again!")
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
