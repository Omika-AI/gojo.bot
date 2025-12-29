"""
Music Commands
Play music from Spotify links or search queries in voice channels
Uses Spotify API for track info and YouTube for audio streaming

Commands:
- /play <query or spotify link> - Play a song or add to queue
- /pause - Pause the current song
- /resume - Resume playback
- /skip - Skip the current song
- /stop - Stop music and leave voice channel
- /queue - View the current queue
- /nowplaying - Show the currently playing song
- /volume <0-100> - Adjust the volume
- /clear - Clear the queue
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import asyncio
import re
from typing import Optional, Dict, List
from datetime import timedelta

import config
from utils.logger import log_command, logger

# Try to import optional dependencies
try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    SPOTIFY_AVAILABLE = True
except ImportError:
    SPOTIFY_AVAILABLE = False
    logger.warning("spotipy not installed - Spotify features disabled")

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    logger.warning("yt-dlp not installed - Music playback disabled")


# =============================================================================
# CONFIGURATION
# =============================================================================

# yt-dlp options for audio extraction
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
}

# FFmpeg options for audio playback
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Regex patterns for Spotify URLs
SPOTIFY_TRACK_PATTERN = re.compile(r'https?://open\.spotify\.com/track/([a-zA-Z0-9]+)')
SPOTIFY_PLAYLIST_PATTERN = re.compile(r'https?://open\.spotify\.com/playlist/([a-zA-Z0-9]+)')
SPOTIFY_ALBUM_PATTERN = re.compile(r'https?://open\.spotify\.com/album/([a-zA-Z0-9]+)')


# =============================================================================
# SONG CLASS
# =============================================================================

class Song:
    """Represents a song in the queue"""

    def __init__(self, title: str, url: str, duration: int, thumbnail: str, requester: discord.Member):
        self.title = title
        self.url = url
        self.duration = duration  # in seconds
        self.thumbnail = thumbnail
        self.requester = requester

    @property
    def duration_str(self) -> str:
        """Format duration as MM:SS or HH:MM:SS"""
        if self.duration < 3600:
            return f"{self.duration // 60}:{self.duration % 60:02d}"
        else:
            hours = self.duration // 3600
            minutes = (self.duration % 3600) // 60
            seconds = self.duration % 60
            return f"{hours}:{minutes:02d}:{seconds:02d}"


# =============================================================================
# MUSIC PLAYER CLASS (Per Guild)
# =============================================================================

class MusicPlayer:
    """Music player for a specific guild"""

    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue: List[Song] = []
        self.current: Optional[Song] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self.volume = 0.5
        self.loop = False
        self._ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) if YTDLP_AVAILABLE else None

    async def connect(self, channel: discord.VoiceChannel) -> bool:
        """Connect to a voice channel"""
        try:
            if self.voice_client and self.voice_client.is_connected():
                await self.voice_client.move_to(channel)
            else:
                self.voice_client = await channel.connect()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to voice channel: {e}")
            return False

    async def disconnect(self):
        """Disconnect from voice channel"""
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None
        self.queue.clear()
        self.current = None

    async def add_song(self, query: str, requester: discord.Member) -> Optional[Song]:
        """Add a song to the queue from a search query or URL"""
        if not self._ytdl:
            return None

        try:
            # Run yt-dlp in executor to not block
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                lambda: self._ytdl.extract_info(query, download=False)
            )

            if not data:
                return None

            # Handle search results
            if 'entries' in data:
                data = data['entries'][0]

            song = Song(
                title=data.get('title', 'Unknown'),
                url=data.get('url') or data.get('webpage_url', ''),
                duration=data.get('duration', 0),
                thumbnail=data.get('thumbnail', ''),
                requester=requester
            )

            self.queue.append(song)
            return song

        except Exception as e:
            logger.error(f"Failed to add song: {e}")
            return None

    async def play_next(self):
        """Play the next song in the queue"""
        if not self.queue or not self.voice_client:
            self.current = None
            return

        self.current = self.queue.pop(0)

        try:
            # Get fresh URL (YouTube URLs expire)
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                lambda: self._ytdl.extract_info(self.current.title, download=False)
            )

            if 'entries' in data:
                data = data['entries'][0]

            audio_url = data.get('url')
            if not audio_url:
                await self.play_next()
                return

            # Create audio source
            source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=self.volume)

            # Play the audio
            def after_playing(error):
                if error:
                    logger.error(f"Playback error: {error}")

                # Schedule next song
                if self.loop and self.current:
                    self.queue.insert(0, self.current)

                asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)

            self.voice_client.play(source, after=after_playing)

        except Exception as e:
            logger.error(f"Error playing song: {e}")
            await self.play_next()

    def pause(self):
        """Pause playback"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()

    def resume(self):
        """Resume playback"""
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()

    def skip(self):
        """Skip current song"""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()

    def set_volume(self, volume: float):
        """Set volume (0.0 to 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
        if self.voice_client and self.voice_client.source:
            self.voice_client.source.volume = self.volume


# =============================================================================
# SPOTIFY HELPER
# =============================================================================

class SpotifyHelper:
    """Helper class for Spotify API interactions"""

    def __init__(self):
        self.client = None
        if SPOTIFY_AVAILABLE and config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET:
            try:
                auth_manager = SpotifyClientCredentials(
                    client_id=config.SPOTIFY_CLIENT_ID,
                    client_secret=config.SPOTIFY_CLIENT_SECRET
                )
                self.client = spotipy.Spotify(auth_manager=auth_manager)
                logger.info("Spotify client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Spotify client: {e}")

    def is_available(self) -> bool:
        return self.client is not None

    def get_track_info(self, track_id: str) -> Optional[Dict]:
        """Get track info from Spotify"""
        if not self.client:
            return None
        try:
            track = self.client.track(track_id)
            return {
                'name': track['name'],
                'artist': ', '.join(artist['name'] for artist in track['artists']),
                'search_query': f"{track['name']} {track['artists'][0]['name']}"
            }
        except Exception as e:
            logger.error(f"Failed to get track info: {e}")
            return None

    def get_playlist_tracks(self, playlist_id: str, limit: int = 25) -> List[Dict]:
        """Get tracks from a Spotify playlist"""
        if not self.client:
            return []
        try:
            results = self.client.playlist_tracks(playlist_id, limit=limit)
            tracks = []
            for item in results['items']:
                track = item['track']
                if track:
                    tracks.append({
                        'name': track['name'],
                        'artist': ', '.join(artist['name'] for artist in track['artists']),
                        'search_query': f"{track['name']} {track['artists'][0]['name']}"
                    })
            return tracks
        except Exception as e:
            logger.error(f"Failed to get playlist tracks: {e}")
            return []

    def get_album_tracks(self, album_id: str) -> List[Dict]:
        """Get tracks from a Spotify album"""
        if not self.client:
            return []
        try:
            results = self.client.album_tracks(album_id)
            album_info = self.client.album(album_id)
            tracks = []
            for track in results['items']:
                tracks.append({
                    'name': track['name'],
                    'artist': ', '.join(artist['name'] for artist in track['artists']),
                    'search_query': f"{track['name']} {track['artists'][0]['name']}"
                })
            return tracks
        except Exception as e:
            logger.error(f"Failed to get album tracks: {e}")
            return []


# =============================================================================
# MUSIC COG
# =============================================================================

class Music(commands.Cog):
    """Music commands for playing songs in voice channels"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: Dict[int, MusicPlayer] = {}  # guild_id -> MusicPlayer
        self.spotify = SpotifyHelper()

    def get_player(self, guild: discord.Guild) -> MusicPlayer:
        """Get or create a music player for a guild"""
        if guild.id not in self.players:
            self.players[guild.id] = MusicPlayer(self.bot, guild)
        return self.players[guild.id]

    async def _check_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceChannel]:
        """Check if user is in a voice channel, return the channel or None"""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You need to be in a voice channel to use music commands!",
                ephemeral=True
            )
            return None
        return interaction.user.voice.channel

    @app_commands.command(name="play", description="Play a song from Spotify link or search query")
    @app_commands.describe(query="Song name, YouTube URL, or Spotify link")
    async def play(self, interaction: discord.Interaction, query: str):
        """Play a song or add it to the queue"""
        log_command(str(interaction.user), interaction.user.id, f"play {query}", interaction.guild.name)

        # Check dependencies
        if not YTDLP_AVAILABLE:
            await interaction.response.send_message(
                "❌ Music features are not available. yt-dlp is not installed.",
                ephemeral=True
            )
            return

        # Check voice channel
        voice_channel = await self._check_voice(interaction)
        if not voice_channel:
            return

        await interaction.response.defer()

        player = self.get_player(interaction.guild)

        # Connect to voice channel
        if not await player.connect(voice_channel):
            await interaction.followup.send("❌ Failed to connect to voice channel!")
            return

        # Check for Spotify links
        search_queries = []

        # Spotify track
        track_match = SPOTIFY_TRACK_PATTERN.match(query)
        if track_match and self.spotify.is_available():
            track_info = self.spotify.get_track_info(track_match.group(1))
            if track_info:
                search_queries.append(track_info['search_query'])
                await interaction.followup.send(
                    f"🎵 Found Spotify track: **{track_info['name']}** by **{track_info['artist']}**"
                )

        # Spotify playlist
        playlist_match = SPOTIFY_PLAYLIST_PATTERN.match(query)
        if playlist_match and self.spotify.is_available():
            tracks = self.spotify.get_playlist_tracks(playlist_match.group(1))
            if tracks:
                search_queries.extend([t['search_query'] for t in tracks])
                await interaction.followup.send(
                    f"📋 Adding **{len(tracks)}** songs from Spotify playlist..."
                )

        # Spotify album
        album_match = SPOTIFY_ALBUM_PATTERN.match(query)
        if album_match and self.spotify.is_available():
            tracks = self.spotify.get_album_tracks(album_match.group(1))
            if tracks:
                search_queries.extend([t['search_query'] for t in tracks])
                await interaction.followup.send(
                    f"💿 Adding **{len(tracks)}** songs from Spotify album..."
                )

        # Regular search query
        if not search_queries:
            search_queries.append(query)

        # Add songs to queue
        added_songs = []
        for search_query in search_queries:
            song = await player.add_song(search_query, interaction.user)
            if song:
                added_songs.append(song)

        if not added_songs:
            await interaction.followup.send("❌ Couldn't find any songs!")
            return

        # Start playing if not already
        if not player.voice_client.is_playing() and not player.voice_client.is_paused():
            await player.play_next()
            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**{player.current.title}**",
                color=discord.Color.green()
            )
            if player.current.thumbnail:
                embed.set_thumbnail(url=player.current.thumbnail)
            embed.add_field(name="Duration", value=player.current.duration_str, inline=True)
            embed.add_field(name="Requested by", value=player.current.requester.mention, inline=True)
            embed.add_field(name="Queue", value=f"{len(player.queue)} songs", inline=True)
            await interaction.followup.send(embed=embed)
        else:
            if len(added_songs) == 1:
                song = added_songs[0]
                embed = discord.Embed(
                    title="➕ Added to Queue",
                    description=f"**{song.title}**",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Position", value=f"#{len(player.queue)}", inline=True)
                embed.add_field(name="Duration", value=song.duration_str, inline=True)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"➕ Added **{len(added_songs)}** songs to the queue!"
                )

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        """Pause playback"""
        log_command(str(interaction.user), interaction.user.id, "pause", interaction.guild.name)

        player = self.get_player(interaction.guild)

        if not player.voice_client or not player.voice_client.is_playing():
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
            return

        player.pause()
        await interaction.response.send_message("⏸️ Paused the music!")

    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        """Resume playback"""
        log_command(str(interaction.user), interaction.user.id, "resume", interaction.guild.name)

        player = self.get_player(interaction.guild)

        if not player.voice_client or not player.voice_client.is_paused():
            await interaction.response.send_message("❌ Music is not paused!", ephemeral=True)
            return

        player.resume()
        await interaction.response.send_message("▶️ Resumed the music!")

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        """Skip the current song"""
        log_command(str(interaction.user), interaction.user.id, "skip", interaction.guild.name)

        player = self.get_player(interaction.guild)

        if not player.voice_client or not player.current:
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
            return

        skipped_title = player.current.title
        player.skip()
        await interaction.response.send_message(f"⏭️ Skipped **{skipped_title}**")

    @app_commands.command(name="stop", description="Stop music and leave the voice channel")
    async def stop(self, interaction: discord.Interaction):
        """Stop music and disconnect"""
        log_command(str(interaction.user), interaction.user.id, "stop", interaction.guild.name)

        player = self.get_player(interaction.guild)

        if not player.voice_client:
            await interaction.response.send_message("❌ I'm not in a voice channel!", ephemeral=True)
            return

        await player.disconnect()
        await interaction.response.send_message("⏹️ Stopped the music and left the voice channel!")

    @app_commands.command(name="queue", description="View the current song queue")
    async def queue(self, interaction: discord.Interaction):
        """Show the queue"""
        log_command(str(interaction.user), interaction.user.id, "queue", interaction.guild.name)

        player = self.get_player(interaction.guild)

        embed = discord.Embed(
            title="🎵 Music Queue",
            color=discord.Color.purple()
        )

        # Current song
        if player.current:
            embed.add_field(
                name="Now Playing",
                value=f"**{player.current.title}**\n`{player.current.duration_str}` | Requested by {player.current.requester.mention}",
                inline=False
            )

        # Queue
        if player.queue:
            queue_text = ""
            for i, song in enumerate(player.queue[:10], 1):
                queue_text += f"`{i}.` **{song.title}** `{song.duration_str}`\n"

            if len(player.queue) > 10:
                queue_text += f"\n*...and {len(player.queue) - 10} more songs*"

            embed.add_field(name="Up Next", value=queue_text, inline=False)

            # Total duration
            total_seconds = sum(song.duration for song in player.queue)
            if player.current:
                total_seconds += player.current.duration
            total_duration = str(timedelta(seconds=total_seconds))
            embed.set_footer(text=f"Total: {len(player.queue) + (1 if player.current else 0)} songs | {total_duration}")
        else:
            if not player.current:
                embed.description = "The queue is empty! Use `/play` to add songs."

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        """Show current song"""
        log_command(str(interaction.user), interaction.user.id, "nowplaying", interaction.guild.name)

        player = self.get_player(interaction.guild)

        if not player.current:
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{player.current.title}**",
            color=discord.Color.green()
        )

        if player.current.thumbnail:
            embed.set_thumbnail(url=player.current.thumbnail)

        embed.add_field(name="Duration", value=player.current.duration_str, inline=True)
        embed.add_field(name="Requested by", value=player.current.requester.mention, inline=True)
        embed.add_field(name="Volume", value=f"{int(player.volume * 100)}%", inline=True)
        embed.add_field(name="Queue", value=f"{len(player.queue)} songs remaining", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Adjust the music volume")
    @app_commands.describe(level="Volume level (0-100)")
    async def volume(self, interaction: discord.Interaction, level: int):
        """Set volume"""
        log_command(str(interaction.user), interaction.user.id, f"volume {level}", interaction.guild.name)

        if level < 0 or level > 100:
            await interaction.response.send_message(
                "❌ Volume must be between 0 and 100!",
                ephemeral=True
            )
            return

        player = self.get_player(interaction.guild)
        player.set_volume(level / 100)

        emoji = "🔇" if level == 0 else "🔈" if level < 33 else "🔉" if level < 66 else "🔊"
        await interaction.response.send_message(f"{emoji} Volume set to **{level}%**")

    @app_commands.command(name="clear", description="Clear the music queue")
    async def clear(self, interaction: discord.Interaction):
        """Clear the queue"""
        log_command(str(interaction.user), interaction.user.id, "clear", interaction.guild.name)

        player = self.get_player(interaction.guild)

        if not player.queue:
            await interaction.response.send_message("❌ The queue is already empty!", ephemeral=True)
            return

        count = len(player.queue)
        player.queue.clear()
        await interaction.response.send_message(f"🗑️ Cleared **{count}** songs from the queue!")

    @app_commands.command(name="shuffle", description="Shuffle the music queue")
    async def shuffle(self, interaction: discord.Interaction):
        """Shuffle the queue"""
        log_command(str(interaction.user), interaction.user.id, "shuffle", interaction.guild.name)

        import random

        player = self.get_player(interaction.guild)

        if len(player.queue) < 2:
            await interaction.response.send_message(
                "❌ Need at least 2 songs in queue to shuffle!",
                ephemeral=True
            )
            return

        random.shuffle(player.queue)
        await interaction.response.send_message(f"🔀 Shuffled **{len(player.queue)}** songs!")


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Music cog to the bot"""
    await bot.add_cog(Music(bot))
