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
from discord.ui import View, Select, Button, Modal, TextInput
import asyncio
import time
from typing import Optional, List, Tuple

import config
from utils.logger import log_command, logger
from utils.achievements_data import update_user_stat, check_and_complete_achievements
from utils.karaoke_data import (
    get_all_songs,
    get_song_by_id,
    load_song_lyrics,
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


class KaraokeModeView(View):
    """View for selecting karaoke mode (Solo or Duet)"""

    def __init__(self, cog: 'Karaoke', user: discord.Member, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user = user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "Only the person who started karaoke can use these buttons!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Solo Performance", style=discord.ButtonStyle.success, emoji="🌟")
    async def solo_mode(self, interaction: discord.Interaction, button: Button):
        """Select solo mode"""
        embed = discord.Embed(
            title="🌟 Solo Karaoke",
            description="Select who will be performing!",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="How it works",
            value="Click the button below and select the singer from your server.",
            inline=False
        )

        await interaction.response.edit_message(
            embed=embed,
            view=SingerSelectView(self.cog, self.user, "solo")
        )

    @discord.ui.button(label="Duet Performance", style=discord.ButtonStyle.primary, emoji="👯")
    async def duet_mode(self, interaction: discord.Interaction, button: Button):
        """Select duet mode"""
        embed = discord.Embed(
            title="👯 Duet Karaoke",
            description="Select both singers for the duet!",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="How it works",
            value="Click the button below to select both singers. They will alternate singing lines!",
            inline=False
        )

        await interaction.response.edit_message(
            embed=embed,
            view=SingerSelectView(self.cog, self.user, "duet")
        )

    @discord.ui.button(label="View Song List", style=discord.ButtonStyle.secondary, emoji="📋")
    async def view_songs(self, interaction: discord.Interaction, button: Button):
        """View available songs"""
        songs = get_all_songs()

        embed = discord.Embed(
            title="🎤 Available Karaoke Songs",
            description="Here are all the songs you can sing!",
            color=discord.Color.magenta()
        )

        emojis = {
            "happier": "😊",
            "stereo_hearts": "💕",
            "viva_la_vida": "👑",
            "something_blue": "💙"
        }

        for i, song in enumerate(songs, 1):
            emoji = emojis.get(song.id, "🎵")
            mins = song.duration // 60
            secs = song.duration % 60
            duration_str = f"{mins}:{secs:02d}"

            embed.add_field(
                name=f"{emoji} {i}. {song.title}",
                value=f"**Artist:** {song.artist}\n**Duration:** {duration_str}",
                inline=True
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class SingerSelectView(View):
    """View for selecting singer(s)"""

    def __init__(self, cog: 'Karaoke', user: discord.Member, mode: str, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user = user
        self.mode = mode
        self.singer1: Optional[discord.Member] = None
        self.singer2: Optional[discord.Member] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "Only the person who started karaoke can use these buttons!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Select Singer(s)", style=discord.ButtonStyle.primary, emoji="🎤")
    async def select_singers(self, interaction: discord.Interaction, button: Button):
        """Open modal to select singers"""
        if self.mode == "solo":
            await interaction.response.send_modal(SoloSingerModal(self.cog, self.user))
        else:
            await interaction.response.send_modal(DuetSingerModal(self.cog, self.user))

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back(self, interaction: discord.Interaction, button: Button):
        """Go back to mode selection"""
        songs = get_all_songs()

        embed = discord.Embed(
            title="🎤 Karaoke Time!",
            description="Choose your performance mode:",
            color=discord.Color.magenta()
        )
        embed.add_field(
            name="🌟 Solo",
            value="One singer takes the spotlight!",
            inline=True
        )
        embed.add_field(
            name="👯 Duet",
            value="Two singers, alternating lines!",
            inline=True
        )
        embed.add_field(
            name=f"📋 {len(songs)} Songs Available",
            value="Click 'View Song List' to see all songs",
            inline=False
        )

        await interaction.response.edit_message(
            embed=embed,
            view=KaraokeModeView(self.cog, self.user)
        )


class SoloSingerModal(Modal):
    """Modal for selecting a solo singer by mention or name"""

    def __init__(self, cog: 'Karaoke', user: discord.Member):
        super().__init__(title="Select Solo Singer")
        self.cog = cog
        self.user = user

        self.singer_input = TextInput(
            label="Singer (mention @user or type username)",
            placeholder="@username or just type their name",
            required=True,
            max_length=100
        )
        self.add_item(self.singer_input)

    async def on_submit(self, interaction: discord.Interaction):
        singer_text = self.singer_input.value.strip()

        # Try to find the user
        singer = await self._find_member(interaction, singer_text)

        if not singer:
            await interaction.response.send_message(
                f"Could not find user `{singer_text}`. Make sure they are in this server!",
                ephemeral=True
            )
            return

        # Validate singer is in voice
        if not singer.voice or not singer.voice.channel:
            await interaction.response.send_message(
                f"{singer.display_name} needs to be in a voice channel to sing! 🎤",
                ephemeral=True
            )
            return

        # Check for existing session
        if interaction.guild.id in self.cog.sessions:
            await interaction.response.send_message(
                "A karaoke session is already active! Use the Stop button to end it first.",
                ephemeral=True
            )
            return

        # Show song selection
        songs = get_all_songs()

        embed = discord.Embed(
            title="🎤 SOLO KARAOKE MODE",
            description=f"**{singer.display_name}** is about to take the stage!",
            color=discord.Color.gold()
        )
        embed.add_field(name="🌟 Tonight's Star", value=f"{singer.mention}", inline=True)

        song_list = "\n".join([f"**{i+1}.** {song.title} - *{song.artist}*" for i, song in enumerate(songs)])
        embed.add_field(name="Available Songs", value=song_list, inline=False)

        await interaction.response.edit_message(
            embed=embed,
            view=SongSelectView(self.cog, self.user, "solo", [singer])
        )

    async def _find_member(self, interaction: discord.Interaction, text: str) -> Optional[discord.Member]:
        """Find a member by mention, ID, or name"""
        import re

        # Check for mention
        mention_match = re.match(r'<@!?(\d+)>', text)
        if mention_match:
            user_id = int(mention_match.group(1))
            return interaction.guild.get_member(user_id)

        # Check if it's a user ID
        if text.isdigit():
            return interaction.guild.get_member(int(text))

        # Search by name
        text_lower = text.lower()
        for member in interaction.guild.members:
            if member.display_name.lower() == text_lower or member.name.lower() == text_lower:
                return member

        # Partial match
        for member in interaction.guild.members:
            if text_lower in member.display_name.lower() or text_lower in member.name.lower():
                return member

        return None


class DuetSingerModal(Modal):
    """Modal for selecting duet singers"""

    def __init__(self, cog: 'Karaoke', user: discord.Member):
        super().__init__(title="Select Duet Singers")
        self.cog = cog
        self.user = user

        self.singer1_input = TextInput(
            label="Singer 1 (sings odd lines)",
            placeholder="@username or just type their name",
            required=True,
            max_length=100
        )
        self.singer2_input = TextInput(
            label="Singer 2 (sings even lines)",
            placeholder="@username or just type their name",
            required=True,
            max_length=100
        )
        self.add_item(self.singer1_input)
        self.add_item(self.singer2_input)

    async def on_submit(self, interaction: discord.Interaction):
        singer1_text = self.singer1_input.value.strip()
        singer2_text = self.singer2_input.value.strip()

        # Find both singers
        singer1 = await self._find_member(interaction, singer1_text)
        singer2 = await self._find_member(interaction, singer2_text)

        if not singer1:
            await interaction.response.send_message(
                f"Could not find Singer 1: `{singer1_text}`",
                ephemeral=True
            )
            return

        if not singer2:
            await interaction.response.send_message(
                f"Could not find Singer 2: `{singer2_text}`",
                ephemeral=True
            )
            return

        if singer1.id == singer2.id:
            await interaction.response.send_message(
                "A duet needs TWO different people! Pick someone else to sing with.",
                ephemeral=True
            )
            return

        # Validate both in voice
        if not singer1.voice or not singer1.voice.channel:
            await interaction.response.send_message(
                f"{singer1.display_name} needs to be in a voice channel to sing! 🎤",
                ephemeral=True
            )
            return

        if not singer2.voice or not singer2.voice.channel:
            await interaction.response.send_message(
                f"{singer2.display_name} needs to be in a voice channel to sing! 🎤",
                ephemeral=True
            )
            return

        # Check same voice channel
        if singer1.voice.channel.id != singer2.voice.channel.id:
            await interaction.response.send_message(
                "Both singers need to be in the SAME voice channel for a duet!",
                ephemeral=True
            )
            return

        # Check for existing session
        if interaction.guild.id in self.cog.sessions:
            await interaction.response.send_message(
                "A karaoke session is already active! Use the Stop button to end it first.",
                ephemeral=True
            )
            return

        # Show song selection
        songs = get_all_songs()

        embed = discord.Embed(
            title="🎤 DUET KARAOKE MODE",
            description="Two voices, one song!",
            color=discord.Color.purple()
        )
        embed.add_field(name="🎵 Singer 1 (Odd Lines)", value=f"{singer1.mention}", inline=True)
        embed.add_field(name="🎵 Singer 2 (Even Lines)", value=f"{singer2.mention}", inline=True)

        song_list = "\n".join([f"**{i+1}.** {song.title} - *{song.artist}*" for i, song in enumerate(songs)])
        embed.add_field(name="Available Songs", value=song_list, inline=False)

        await interaction.response.edit_message(
            embed=embed,
            view=SongSelectView(self.cog, self.user, "duet", [singer1, singer2])
        )

    async def _find_member(self, interaction: discord.Interaction, text: str) -> Optional[discord.Member]:
        """Find a member by mention, ID, or name"""
        import re

        mention_match = re.match(r'<@!?(\d+)>', text)
        if mention_match:
            user_id = int(mention_match.group(1))
            return interaction.guild.get_member(user_id)

        if text.isdigit():
            return interaction.guild.get_member(int(text))

        text_lower = text.lower()
        for member in interaction.guild.members:
            if member.display_name.lower() == text_lower or member.name.lower() == text_lower:
                return member

        for member in interaction.guild.members:
            if text_lower in member.display_name.lower() or text_lower in member.name.lower():
                return member

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

        # Acknowledge the interaction first to prevent "Interaction Failed"
        await interaction.response.defer()

        # Stop the session (this will update the message)
        await self.cog.stop_karaoke_session(self.guild_id)
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
    # MAIN KARAOKE COMMAND
    # =============================================================================

    @app_commands.command(name="karaoke", description="Start a karaoke session - solo or duet!")
    async def karaoke(self, interaction: discord.Interaction):
        """Main karaoke command with mode selection"""
        log_command(str(interaction.user), interaction.user.id, "karaoke", interaction.guild.name)

        # Check if yt-dlp is available
        if not YTDLP_AVAILABLE:
            await interaction.response.send_message(
                "Karaoke is unavailable - audio system not configured.",
                ephemeral=True
            )
            return

        songs = get_all_songs()

        embed = discord.Embed(
            title="🎤 Karaoke Time!",
            description="Choose your performance mode:",
            color=discord.Color.magenta()
        )
        embed.add_field(
            name="🌟 Solo",
            value="One singer takes the spotlight!",
            inline=True
        )
        embed.add_field(
            name="👯 Duet",
            value="Two singers, alternating lines!",
            inline=True
        )
        embed.add_field(
            name=f"📋 {len(songs)} Songs Available",
            value="Click 'View Song List' to see all songs",
            inline=False
        )
        embed.set_footer(text=f"Started by {interaction.user.display_name}")

        await interaction.response.send_message(
            embed=embed,
            view=KaraokeModeView(self, interaction.user)
        )

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

    async def _perform_countdown(
        self,
        channel: discord.TextChannel,
        singers: List[discord.Member],
        mode: str,
        song: KaraokeSong,
        lyrics: list
    ) -> discord.Message:
        """
        Perform a 5-second countdown before the song starts
        Shows lyrics so singers can prepare
        Returns the countdown message for later editing
        """
        # Build singer announcement
        if mode == "solo":
            singer_text = f"🌟 **{singers[0].display_name}** 🌟"
        else:
            singer_text = f"🎵 **{singers[0].display_name}** & **{singers[1].display_name}** 🎵"

        # Format song duration
        duration_str = self._format_song_duration(song.duration)

        # Build lyrics preview (first portion to fit in embed)
        lyrics_preview = self._build_lyrics_preview(lyrics, mode, singers)

        # Initial countdown embed with lyrics
        embed = discord.Embed(
            title="🎤 GET READY!",
            description=f"**{song.title}** by *{song.artist}* • {duration_str}\n\nPerforming: {singer_text}",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Starting in...",
            value="```\n   🟡 3 🟡\n```",
            inline=False
        )

        # Add lyrics preview
        if len(lyrics_preview) > 1000:
            chunks = self._split_lyrics_into_chunks(lyrics_preview, 1000)
            for i, chunk in enumerate(chunks[:2]):
                field_name = "📜 Lyrics Preview" if i == 0 else "​"
                embed.add_field(name=field_name, value=chunk, inline=False)
        else:
            embed.add_field(name="📜 Lyrics Preview", value=lyrics_preview, inline=False)

        embed.set_footer(text="Read through the lyrics and get ready!")

        countdown_msg = await channel.send(embed=embed)

        # Countdown loop: 3, 2, 1
        countdown_emojis = {
            3: "🟡",
            2: "🟢",
            1: "💚"
        }

        for i in range(2, 0, -1):
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

    def _build_lyrics_preview(self, lyrics: list, mode: str, singers: List[discord.Member]) -> str:
        """Build a lyrics preview for the countdown screen"""
        if not lyrics:
            return "*No lyrics available*"

        lines = []
        line_number = 0
        prev_timestamp = 0

        for lyric in lyrics:
            if not lyric.text or lyric.text.startswith("--") or lyric.text.startswith("["):
                continue

            # Add spacing for verse breaks
            if lyric.timestamp - prev_timestamp > 4 and lines:
                lines.append("")

            prev_timestamp = lyric.timestamp

            if mode == "duet":
                is_singer1 = (line_number % 2 == 0)
                emoji = "🔵" if is_singer1 else "🟢"
                if is_singer1:
                    lines.append(f"{emoji} **{lyric.text}**")
                else:
                    lines.append(f"{emoji} *{lyric.text}*")
            else:
                lines.append(lyric.text)

            line_number += 1

        return "\n".join(lines) if lines else "*No lyrics*"

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
        await self._perform_countdown(interaction.channel, singers, mode, song, lyrics)

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
        """Background task to update progress bar only"""
        try:
            # Calculate update interval: 1/10 of song duration
            update_interval = session.song.duration / 10
            last_update_segment = -1

            while session.is_playing and session.guild_id in self.sessions:
                current_time = session.elapsed_time

                # Only update every 1/10 of the song
                current_segment = int(current_time / update_interval) if update_interval > 0 else 0

                if current_segment != last_update_segment:
                    last_update_segment = current_segment

                    # Build embed with static lyrics
                    if session.mode == "duet":
                        lyrics_display = self._format_all_lyrics_duet(session)
                        title = f"🎤 Duet: {session.singers[0].display_name} & {session.singers[1].display_name}"
                    else:
                        lyrics_display = self._format_all_lyrics_solo(session)
                        title = f"🎤 Now Singing: {session.singers[0].display_name}"

                    # Format song duration
                    duration_str = self._format_song_duration(session.song.duration)

                    embed = discord.Embed(
                        title=title,
                        description=f"**{session.song.title}** by *{session.song.artist}* • {duration_str}",
                        color=discord.Color.magenta()
                    )

                    # Add progress bar
                    progress_bar = self._format_progress_bar(current_time, session.song.duration)
                    embed.add_field(
                        name="Progress",
                        value=progress_bar,
                        inline=False
                    )

                    # Add lyrics - split if too long
                    if len(lyrics_display) > 1000:
                        chunks = self._split_lyrics_into_chunks(lyrics_display, 1000)
                        for i, chunk in enumerate(chunks[:3]):
                            field_name = "Lyrics" if i == 0 else "​"
                            embed.add_field(name=field_name, value=chunk, inline=False)
                    else:
                        embed.add_field(
                            name="Lyrics",
                            value=lyrics_display,
                            inline=False
                        )

                    # Add legend for duet mode
                    if session.mode == "duet":
                        embed.add_field(
                            name="Legend",
                            value=f"🔵 **{session.singers[0].display_name}** | 🟢 *{session.singers[1].display_name}*",
                            inline=False
                        )

                    embed.set_footer(text="🎵 Sing along! | Use the Stop button to end")

                    try:
                        await session.message.edit(embed=embed)
                    except discord.errors.NotFound:
                        break
                    except Exception as e:
                        logger.warning(f"Failed to update karaoke progress: {e}")

                # Check every second
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Karaoke update error: {e}")

    def _format_progress_bar(self, current_time: float, duration: float) -> str:
        """Format a progress bar with percentage"""
        progress = min(1.0, current_time / duration) if duration > 0 else 0
        percentage = int(progress * 100)

        bar_length = 20
        filled = int(bar_length * progress)
        bar = "▓" * filled + "░" * (bar_length - filled)

        return f"`[{bar}]` **{percentage}%**"

    def _format_song_duration(self, duration: float) -> str:
        """Format song duration as mm:ss"""
        mins = int(duration // 60)
        secs = int(duration % 60)
        return f"{mins}:{secs:02d}"

    def _format_all_lyrics_solo(self, session: KaraokeSession) -> str:
        """Format ALL lyrics for solo mode - static display"""
        lyrics = session.lyrics

        if not lyrics:
            return "*No lyrics loaded*"

        lines = []
        prev_timestamp = 0

        for lyric in lyrics:
            # Skip empty or placeholder lines
            if not lyric.text or lyric.text.startswith("--") or lyric.text.startswith("["):
                continue

            # Add spacing if there's a gap of 4+ seconds (verse break)
            if lyric.timestamp - prev_timestamp > 4 and lines:
                lines.append("")  # Empty line for spacing

            prev_timestamp = lyric.timestamp
            lines.append(lyric.text)

        return "\n".join(lines) if lines else "*No lyrics*"

    def _format_all_lyrics_duet(self, session: KaraokeSession) -> str:
        """Format ALL lyrics for duet mode with color-coded singers - static display"""
        lyrics = session.lyrics

        if not lyrics:
            return "*No lyrics loaded*"

        lines = []
        line_number = 0  # Track actual lyric lines for alternating
        prev_timestamp = 0

        for lyric in lyrics:
            # Skip empty or placeholder lines
            if not lyric.text or lyric.text.startswith("--") or lyric.text.startswith("["):
                continue

            # Add spacing if there's a gap of 4+ seconds (verse break)
            if lyric.timestamp - prev_timestamp > 4 and lines:
                lines.append("")  # Empty line for spacing

            prev_timestamp = lyric.timestamp

            # Determine which singer (alternating)
            is_singer1 = (line_number % 2 == 0)
            emoji = "🔵" if is_singer1 else "🟢"

            # Static display with singer colors
            if is_singer1:
                lines.append(f"{emoji} **{lyric.text}**")
            else:
                lines.append(f"{emoji} *{lyric.text}*")

            line_number += 1

        return "\n".join(lines) if lines else "*No lyrics*"

    def _split_lyrics_into_chunks(self, text: str, max_length: int) -> List[str]:
        """Split lyrics into chunks that fit in embed fields"""
        lines = text.split("\n")
        chunks = []
        current_chunk = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1  # +1 for newline
            if current_length + line_length > max_length and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

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

        # Update final message - compact end state
        try:
            if session.mode == "solo":
                thanks_to = session.singers[0].display_name
            else:
                thanks_to = f"{session.singers[0].display_name} & {session.singers[1].display_name}"

            embed = discord.Embed(
                title="🎤 Session Complete",
                description=f"**{session.song.title}** - *{session.song.artist}*\nPerformed by **{thanks_to}** 👏",
                color=discord.Color.dark_grey()
            )
            await session.message.edit(embed=embed, view=None)

            # Track achievements for participants
            try:
                for singer in session.singers:
                    # Track karaoke sessions for everyone
                    update_user_stat(singer.id, "karaoke_sessions", increment=1)

                    # Track duets specifically for duet mode
                    if session.mode == "duet":
                        update_user_stat(singer.id, "karaoke_duets", increment=1)

                    check_and_complete_achievements(singer.id)
            except Exception as e:
                logger.debug(f"Failed to track karaoke achievement: {e}")

            # Delete the message after 15 seconds to keep chat clean
            await asyncio.sleep(15)
            try:
                await session.message.delete()
            except:
                pass
        except:
            pass

        # Remove session
        del self.sessions[guild_id]
        logger.info(f"Karaoke session ended in guild {guild_id}")


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Karaoke cog to the bot"""
    await bot.add_cog(Karaoke(bot))
