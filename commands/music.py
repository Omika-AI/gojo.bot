"""
Music Commands
Play music from SoundCloud in voice channels
Uses yt-dlp for audio streaming

Commands:
- /play <query or link> - Play a song immediately (or add to queue if something is playing)
- /addsong <query or link> - Add a song to the queue
- /playlist <url> - Play a SoundCloud playlist or album
- /queue - View the current queue
- /nowplaying - Show the currently playing song
- /pause - Pause the current song
- /resume - Resume playback
- /skip - Skip the current song
- /stop - Stop music and leave voice channel
- /volume <0-100> - Adjust the volume
- /shuffle - Shuffle the queue
- /clearqueue - Clear the queue (mods only)
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import asyncio
import aiohttp
import re
from typing import Optional, Dict, List
from datetime import timedelta

import config
from utils.logger import log_command, logger

# Try to import yt-dlp for audio streaming
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    logger.warning("yt-dlp not installed - Music playback disabled")


# =============================================================================
# CONFIGURATION
# =============================================================================

# yt-dlp options for audio extraction (single tracks)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'scsearch',  # SoundCloud search
    'source_address': '0.0.0.0',
    'extract_flat': False,
}

# yt-dlp options for playlists/albums
YTDL_PLAYLIST_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': False,  # Allow playlists
    'nocheckcertificate': True,
    'ignoreerrors': True,  # Skip unavailable tracks
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'extract_flat': False,  # Fully extract each track for proper metadata
}

# FFmpeg options for audio playback
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Regex patterns for SoundCloud URLs
SOUNDCLOUD_PATTERN = re.compile(r'https?://(www\.)?soundcloud\.com/.+')
SOUNDCLOUD_MOBILE_PATTERN = re.compile(r'https?://m\.soundcloud\.com/.+')

# SoundCloud playlist/album patterns (sets, albums, playlists)
SOUNDCLOUD_PLAYLIST_PATTERN = re.compile(r'https?://(www\.)?soundcloud\.com/[^/]+/sets/.+')
SOUNDCLOUD_ALBUM_PATTERN = re.compile(r'https?://(www\.)?soundcloud\.com/[^/]+/albums/.+')


# =============================================================================
# LYRICS FETCHER (Multiple sources)
# =============================================================================

def _clean_html(text: str) -> str:
    """Clean HTML tags and entities from text"""
    # Replace <br> with newlines
    text = re.sub(r'<br\s*/?>', '\n', text)
    # Remove all other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode common HTML entities
    text = text.replace('&amp;', '&')
    text = text.replace('&quot;', '"')
    text = text.replace('&#x27;', "'")
    text = text.replace('&apos;', "'")
    text = text.replace('&#39;', "'")
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


async def _fetch_genius_lyrics(artist: str, title: str, session: aiohttp.ClientSession) -> Optional[str]:
    """Fetch lyrics from Genius"""
    import urllib.parse

    try:
        search_term = f"{artist} {title}".replace(' ', '%20')
        search_url = f"https://genius.com/api/search?q={search_term}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
        }

        async with session.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                logger.debug(f"Genius search returned {response.status}")
                return None

            data = await response.json()
            hits = data.get('response', {}).get('hits', [])

            if not hits:
                logger.debug("No hits from Genius search")
                return None

            # Get the first song result
            song_url = hits[0].get('result', {}).get('url')
            if not song_url:
                return None

            logger.debug(f"Found Genius URL: {song_url}")

            # Fetch the lyrics page
            async with session.get(song_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as page_response:
                if page_response.status != 200:
                    return None

                html = await page_response.text()

                # Try multiple patterns to extract lyrics
                lyrics_parts = []

                # Pattern 1: data-lyrics-container divs (current Genius format)
                containers = re.findall(
                    r'<div[^>]*data-lyrics-container="true"[^>]*>(.*?)</div>',
                    html,
                    re.DOTALL | re.IGNORECASE
                )
                if containers:
                    lyrics_parts.extend(containers)

                # Pattern 2: Lyrics__Container class
                if not lyrics_parts:
                    containers = re.findall(
                        r'<div[^>]*class="[^"]*Lyrics__Container[^"]*"[^>]*>(.*?)</div>',
                        html,
                        re.DOTALL | re.IGNORECASE
                    )
                    if containers:
                        lyrics_parts.extend(containers)

                # Pattern 3: Look for lyrics in JSON data embedded in page
                if not lyrics_parts:
                    json_match = re.search(r'"lyrics":\s*\{"body":\s*\{"html":\s*"([^"]+)"', html)
                    if json_match:
                        lyrics_html = json_match.group(1)
                        lyrics_html = lyrics_html.encode().decode('unicode_escape')
                        lyrics_parts.append(lyrics_html)

                if lyrics_parts:
                    lyrics = '\n'.join(lyrics_parts)
                    lyrics = _clean_html(lyrics)

                    if len(lyrics) > 50:
                        logger.debug("Found lyrics on Genius")
                        return lyrics

    except Exception as e:
        logger.debug(f"Genius failed: {e}")

    return None


async def _fetch_azlyrics(artist: str, title: str, session: aiohttp.ClientSession) -> Optional[str]:
    """Fetch lyrics from AZLyrics"""
    try:
        # AZLyrics URL format: azlyrics.com/lyrics/artistname/songname.html
        clean_artist = re.sub(r'[^a-z0-9]', '', artist.lower())
        clean_title = re.sub(r'[^a-z0-9]', '', title.lower())

        url = f"https://www.azlyrics.com/lyrics/{clean_artist}/{clean_title}.html"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }

        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                return None

            html = await response.text()

            # AZLyrics has lyrics in a div after the comment "Usage of azlyrics.com content"
            match = re.search(
                r'<!-- Usage of azlyrics\.com content.*?-->\s*</div>\s*<div>(.*?)</div>',
                html,
                re.DOTALL | re.IGNORECASE
            )

            if match:
                lyrics = _clean_html(match.group(1))
                if len(lyrics) > 50:
                    logger.debug("Found lyrics on AZLyrics")
                    return lyrics

    except Exception as e:
        logger.debug(f"AZLyrics failed: {e}")

    return None


async def _fetch_lyrics_ovh(artist: str, title: str, session: aiohttp.ClientSession) -> Optional[str]:
    """Fetch lyrics from lyrics.ovh API"""
    import urllib.parse

    try:
        encoded_artist = urllib.parse.quote(artist)
        encoded_title = urllib.parse.quote(title)
        url = f"https://api.lyrics.ovh/v1/{encoded_artist}/{encoded_title}"

        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as response:
            if response.status == 200:
                data = await response.json()
                lyrics = data.get('lyrics')
                if lyrics and len(lyrics) > 50:
                    logger.debug("Found lyrics on lyrics.ovh")
                    return lyrics

    except Exception as e:
        logger.debug(f"lyrics.ovh failed: {e}")

    return None


async def _fetch_lrclib(artist: str, title: str, session: aiohttp.ClientSession) -> Optional[str]:
    """Fetch lyrics from lrclib.net"""
    import urllib.parse

    try:
        encoded_query = urllib.parse.quote(f"{artist} {title}")
        url = f"https://lrclib.net/api/search?q={encoded_query}"

        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as response:
            if response.status == 200:
                data = await response.json()
                if data and len(data) > 0:
                    for result in data:
                        plain_lyrics = result.get('plainLyrics')
                        if plain_lyrics and len(plain_lyrics) > 50:
                            logger.debug("Found lyrics on lrclib.net")
                            return plain_lyrics

    except Exception as e:
        logger.debug(f"lrclib.net failed: {e}")

    return None


async def fetch_lyrics(artist: str, title: str) -> Optional[str]:
    """Fetch lyrics from multiple sources"""
    try:
        # Clean up artist and title for search
        clean_title = re.sub(r'\(.*?\)|\[.*?\]', '', title).strip()
        clean_title = re.sub(r'(feat\.?|ft\.?|featuring).*', '', clean_title, flags=re.IGNORECASE).strip()
        clean_title = re.sub(r'\s*-\s*$', '', clean_title).strip()
        # Remove numbers at the end (like "Song (7)")
        clean_title = re.sub(r'\s*\(\d+\)\s*$', '', clean_title).strip()

        clean_artist = re.sub(r'\(.*?\)|\[.*?\]', '', artist).strip()
        clean_artist = re.sub(r'\s*(official|music|vevo|records|topic).*', '', clean_artist, flags=re.IGNORECASE).strip()

        logger.debug(f"Searching lyrics for: '{clean_artist}' - '{clean_title}'")

        # Use a single session for all requests
        async with aiohttp.ClientSession() as session:
            # Try sources in order of reliability
            # 1. Genius (best database)
            lyrics = await _fetch_genius_lyrics(clean_artist, clean_title, session)
            if lyrics:
                return lyrics

            # 2. AZLyrics (good coverage)
            lyrics = await _fetch_azlyrics(clean_artist, clean_title, session)
            if lyrics:
                return lyrics

            # 3. lrclib.net (good for synced lyrics)
            lyrics = await _fetch_lrclib(clean_artist, clean_title, session)
            if lyrics:
                return lyrics

            # 4. lyrics.ovh (API fallback)
            lyrics = await _fetch_lyrics_ovh(clean_artist, clean_title, session)
            if lyrics:
                return lyrics

            # Try with just title (artist might be wrong)
            logger.debug(f"Trying title-only search: '{clean_title}'")
            lyrics = await _fetch_genius_lyrics("", clean_title, session)
            if lyrics:
                return lyrics

    except Exception as e:
        logger.debug(f"Failed to fetch lyrics: {e}")

    logger.debug(f"No lyrics found for: '{artist}' - '{title}'")
    return None


# =============================================================================
# SONG CLASS
# =============================================================================

class Song:
    """Represents a song in the queue with full metadata"""

    def __init__(
        self,
        title: str,
        url: str,
        duration: int,
        thumbnail: str,
        requester: discord.Member,
        artist: str = "Unknown Artist",
        album: str = None,
        uploader: str = None,
        webpage_url: str = None,
        description: str = None
    ):
        self.title = title
        self.url = url
        self.duration = int(duration) if duration else 0  # in seconds (ensure int)
        self.thumbnail = thumbnail
        self.requester = requester
        self.artist = artist
        self.album = album
        self.uploader = uploader or artist
        self.webpage_url = webpage_url
        self.description = description
        self.lyrics: Optional[str] = None
        self.lyrics_fetched = False  # Track if we've tried to fetch lyrics

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

    def get_collaborators(self) -> List[str]:
        """Extract collaborating artists from title (feat., ft., with, &, x)"""
        collaborators = []
        patterns = [
            r'(?:feat\.?|ft\.?|featuring)\s+([^(\[\]]+?)(?:\s*[\(\[\]]|$)',
            r'(?:with|w/)\s+([^(\[\]]+?)(?:\s*[\(\[\]]|$)',
            r'\s+[x&]\s+([^(\[\]]+?)(?:\s*[\(\[\]]|$)',
        ]

        text = self.title.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Clean up and split multiple artists
                artists = re.split(r'[,&]', match)
                for artist in artists:
                    clean = artist.strip().title()
                    if clean and clean not in collaborators:
                        collaborators.append(clean)

        return collaborators

    async def fetch_lyrics_async(self):
        """Fetch lyrics for this song"""
        if self.lyrics_fetched:
            return

        self.lyrics_fetched = True
        self.lyrics = await fetch_lyrics(self.artist, self.title)


# =============================================================================
# NOW PLAYING VIEW WITH LYRICS BUTTON
# =============================================================================

class NowPlayingView(View):
    """View for now playing message with Lyrics button"""

    def __init__(self, song: Song):
        super().__init__(timeout=None)  # Don't timeout
        self.song = song
        # Always add the Lyrics button - it will handle missing lyrics gracefully
        self.add_item(LyricsButton(song))


class LyricsButton(Button):
    """Button to show song lyrics"""

    def __init__(self, song: Song):
        super().__init__(
            label="Lyrics",
            style=discord.ButtonStyle.secondary,
            emoji="📜"
        )
        self.song = song

    async def callback(self, interaction: discord.Interaction):
        """Send lyrics when button is clicked"""
        # Try to fetch lyrics if not already fetched
        if not self.song.lyrics_fetched:
            await interaction.response.defer(ephemeral=True, thinking=True)
            await self.song.fetch_lyrics_async()

            if not self.song.lyrics:
                await interaction.followup.send(
                    f"Could not find lyrics for **{self.song.title}** by **{self.song.artist}**.\n"
                    "This could be because:\n"
                    "- The song is an instrumental\n"
                    "- The lyrics aren't in our database\n"
                    "- The artist/title name differs from the original",
                    ephemeral=True
                )
                return
        elif not self.song.lyrics:
            await interaction.response.send_message(
                f"Could not find lyrics for **{self.song.title}** by **{self.song.artist}**.\n"
                "This could be because:\n"
                "- The song is an instrumental\n"
                "- The lyrics aren't in our database\n"
                "- The artist/title name differs from the original",
                ephemeral=True
            )
            return

        lyrics = self.song.lyrics

        # Discord has a 2000 character limit for messages
        if len(lyrics) <= 1900:
            embed = discord.Embed(
                title=f"Lyrics: {self.song.title}",
                description=lyrics,
                color=discord.Color.orange()
            )
            embed.set_footer(text=f"Artist: {self.song.artist}")
            if self.song.lyrics_fetched and interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # Split into multiple embeds for long lyrics
            chunks = [lyrics[i:i+1900] for i in range(0, len(lyrics), 1900)]

            first_embed = discord.Embed(
                title=f"Lyrics: {self.song.title}",
                description=chunks[0],
                color=discord.Color.orange()
            )

            if interaction.response.is_done():
                await interaction.followup.send(embed=first_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=first_embed, ephemeral=True)

            for chunk in chunks[1:]:
                embed = discord.Embed(
                    description=chunk,
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)


# =============================================================================
# SONG CONFIRMATION VIEW
# =============================================================================

class SongConfirmView(View):
    """View for confirming a song before adding to queue"""

    def __init__(self, song_data: dict, requester: discord.Member, player, play_next: bool = False, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.song_data = song_data
        self.requester = requester
        self.player = player
        self.play_next = play_next  # If True, play immediately or insert at front of queue
        self.confirmed = None  # None = pending, True = confirmed, False = cancelled
        self.message = None

    def _create_song_from_data(self) -> Song:
        """Create a Song object from the stored data"""
        data = self.song_data

        # Extract artist info
        artist = data.get('uploader', data.get('artist', 'Unknown Artist'))
        album = data.get('album', None)

        # Try to extract album from description
        description = data.get('description', '')
        if not album and description:
            album_match = re.search(r'(?:album|EP|LP)[:\s]+([^\n]+)', description, re.IGNORECASE)
            if album_match:
                album = album_match.group(1).strip()[:50]

        return Song(
            title=data.get('title', 'Unknown'),
            url=data.get('url') or data.get('webpage_url', ''),
            duration=data.get('duration') or 0,
            thumbnail=data.get('thumbnail', ''),
            requester=self.requester,
            artist=artist,
            album=album,
            uploader=data.get('uploader', artist),
            webpage_url=data.get('webpage_url', ''),
            description=description[:500] if description else None
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only the requester can confirm/cancel"""
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "Only the person who searched can confirm this!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        """Confirm and add the song"""
        self.confirmed = True

        # Create song and add to queue
        song = self._create_song_from_data()
        self.player.queue.append(song)

        # Check if we need to start playing
        nothing_playing = not self.player.voice_client.is_playing() and not self.player.voice_client.is_paused()

        # If play_next is True and something is playing, move song to front of queue
        if self.play_next and not nothing_playing and len(self.player.queue) > 1:
            self.player.queue.insert(0, self.player.queue.pop())

        # Update the message
        embed = discord.Embed(
            title="Song Added",
            description=f"**{song.title}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Artist", value=song.artist, inline=True)
        embed.add_field(name="Duration", value=song.duration_str, inline=True)

        if nothing_playing:
            embed.add_field(name="Status", value="Starting playback...", inline=False)
        elif self.play_next:
            embed.add_field(name="Status", value="Playing next!", inline=True)
        else:
            embed.add_field(name="Position", value=f"#{len(self.player.queue)}", inline=True)

        await interaction.response.edit_message(embed=embed, view=None)

        # Start playing if needed
        if nothing_playing:
            await self.player.play_next()

        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        """Cancel and don't add the song"""
        self.confirmed = False

        embed = discord.Embed(
            title="Search Cancelled",
            description="Song was not added to the queue.\nUse `/play` to search again.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        """Handle timeout - cancel the addition"""
        if self.confirmed is None and self.message:
            embed = discord.Embed(
                title="Search Timed Out",
                description="Song was not added to the queue.\nUse `/play` to search again.",
                color=discord.Color.grey()
            )
            try:
                await self.message.edit(embed=embed, view=None)
            except discord.NotFound:
                pass


# =============================================================================
# QUEUE VIEW WITH REMOVE BUTTONS
# =============================================================================

class QueueView(View):
    """View for queue with remove buttons"""

    def __init__(self, player, user_id: int, page: int = 0):
        super().__init__(timeout=120)
        self.player = player
        self.user_id = user_id
        self.page = page
        self.songs_per_page = 5
        self.message = None

        self._update_buttons()

    def _update_buttons(self):
        """Update button states based on queue"""
        # Clear existing items
        self.clear_items()

        # Calculate page info
        total_songs = len(self.player.queue)
        total_pages = max(1, (total_songs + self.songs_per_page - 1) // self.songs_per_page)
        start_idx = self.page * self.songs_per_page
        end_idx = min(start_idx + self.songs_per_page, total_songs)

        # Add remove buttons for songs on this page (row 0)
        for i in range(start_idx, end_idx):
            queue_position = i + 1  # 1-indexed for display
            btn = RemoveSongButton(queue_position, self.player, self)
            self.add_item(btn)

        # Add navigation buttons (row 1)
        prev_btn = Button(label="◀ Prev", style=discord.ButtonStyle.secondary, disabled=(self.page <= 0), row=1)
        prev_btn.callback = self._prev_page
        self.add_item(prev_btn)

        page_btn = Button(label=f"Page {self.page + 1}/{total_pages}", style=discord.ButtonStyle.secondary, disabled=True, row=1)
        self.add_item(page_btn)

        next_btn = Button(label="Next ▶", style=discord.ButtonStyle.secondary, disabled=(self.page >= total_pages - 1), row=1)
        next_btn.callback = self._next_page
        self.add_item(next_btn)

        # Add close button (row 1)
        close_btn = Button(label="Close", style=discord.ButtonStyle.danger, row=1)
        close_btn.callback = self._close
        self.add_item(close_btn)

    async def _prev_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your queue view!", ephemeral=True)
            return
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your queue view!", ephemeral=True)
            return
        total_pages = max(1, (len(self.player.queue) + self.songs_per_page - 1) // self.songs_per_page)
        self.page = min(total_pages - 1, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _close(self, interaction: discord.Interaction):
        """Close the queue view"""
        await interaction.response.edit_message(content="Queue closed.", embed=None, view=None)
        self.stop()

    def _build_embed(self) -> discord.Embed:
        """Build the queue embed"""
        embed = discord.Embed(
            title="Music Queue",
            color=discord.Color.purple()
        )

        # Current song
        if self.player.current:
            current_text = f"**{self.player.current.title}**\n"
            current_text += f"by {self.player.current.artist} | `{self.player.current.duration_str}`"
            embed.add_field(name="Now Playing", value=current_text, inline=False)

        # Queue
        if self.player.queue:
            start_idx = self.page * self.songs_per_page
            end_idx = min(start_idx + self.songs_per_page, len(self.player.queue))

            queue_text = ""
            for i in range(start_idx, end_idx):
                song = self.player.queue[i]
                queue_text += f"`{i+1}.` **{song.title}** by {song.artist} `{song.duration_str}`\n"

            embed.add_field(name="Up Next (click number to remove)", value=queue_text, inline=False)

            # Total duration
            total_seconds = sum(song.duration for song in self.player.queue)
            if self.player.current:
                total_seconds += self.player.current.duration
            total_duration = str(timedelta(seconds=total_seconds))
            embed.set_footer(text=f"Total: {len(self.player.queue)} songs | {total_duration}")
        else:
            if not self.player.current:
                embed.description = "The queue is empty! Use `/play` to add songs."
            else:
                embed.add_field(name="Up Next", value="No songs in queue", inline=False)

        return embed

    async def refresh(self, interaction: discord.Interaction):
        """Refresh the queue view after a removal"""
        # Adjust page if needed
        total_pages = max(1, (len(self.player.queue) + self.songs_per_page - 1) // self.songs_per_page)
        if self.page >= total_pages:
            self.page = max(0, total_pages - 1)

        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)


class RemoveSongButton(Button):
    """Button to remove a song from queue by position"""

    def __init__(self, position: int, player, queue_view: QueueView):
        super().__init__(
            label=str(position),
            style=discord.ButtonStyle.secondary,
            row=0
        )
        self.position = position  # 1-indexed
        self.player = player
        self.queue_view = queue_view

    async def callback(self, interaction: discord.Interaction):
        """Remove the song at this position"""
        if interaction.user.id != self.queue_view.user_id:
            await interaction.response.send_message("This isn't your queue view!", ephemeral=True)
            return

        # Convert to 0-indexed
        idx = self.position - 1

        if idx < 0 or idx >= len(self.player.queue):
            await interaction.response.send_message("That song is no longer in the queue!", ephemeral=True)
            return

        # Remove the song
        removed_song = self.player.queue.pop(idx)

        # Refresh the queue view first (this is the response)
        await self.queue_view.refresh(interaction)

        # Send confirmation as followup
        await interaction.followup.send(
            f"Removed **{removed_song.title}** by {removed_song.artist} from the queue.",
            ephemeral=True
        )


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
        self._ytdl_playlist = yt_dlp.YoutubeDL(YTDL_PLAYLIST_OPTIONS) if YTDLP_AVAILABLE else None
        # Track now playing message for updates
        self.now_playing_message: Optional[discord.Message] = None
        self.text_channel: Optional[discord.TextChannel] = None
        # Skip handling - if skip is called while loading, don't play
        self._skip_requested = False
        self._loading = False

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

    async def search_song(self, query: str) -> Optional[dict]:
        """Search for a song and return raw data (without adding to queue)"""
        if not self._ytdl:
            return None

        try:
            # Check if it's a direct SoundCloud URL
            is_url = query.startswith('http://') or query.startswith('https://')

            if is_url:
                search_query = query
            else:
                search_query = f"scsearch:{query}"

            # Run yt-dlp in executor to not block
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                lambda: self._ytdl.extract_info(search_query, download=False)
            )

            if not data:
                return None

            # Handle search results
            if 'entries' in data:
                data = data['entries'][0]

            return data

        except Exception as e:
            logger.error(f"Failed to search song: {e}")
            return None

    async def add_song(self, query: str, requester: discord.Member) -> Optional[Song]:
        """Add a song to the queue from a search query or SoundCloud URL"""
        if not self._ytdl:
            return None

        try:
            # Check if it's a direct SoundCloud URL
            is_url = query.startswith('http://') or query.startswith('https://')

            if is_url:
                # Use URL directly
                search_query = query
            else:
                # It's a search query - use SoundCloud search
                search_query = f"scsearch:{query}"

            # Run yt-dlp in executor to not block
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                lambda: self._ytdl.extract_info(search_query, download=False)
            )

            if not data:
                return None

            # Handle search results
            if 'entries' in data:
                data = data['entries'][0]

            # Extract artist info (SoundCloud uses 'uploader' field)
            artist = data.get('uploader', data.get('artist', 'Unknown Artist'))
            album = data.get('album', None)

            # Try to extract album from description if not available
            description = data.get('description', '')
            if not album and description:
                # Look for album mentions in description
                album_match = re.search(r'(?:album|EP|LP)[:\s]+([^\n]+)', description, re.IGNORECASE)
                if album_match:
                    album = album_match.group(1).strip()[:50]  # Limit length

            song = Song(
                title=data.get('title', 'Unknown'),
                url=data.get('url') or data.get('webpage_url', ''),
                duration=data.get('duration') or 0,
                thumbnail=data.get('thumbnail', ''),
                requester=requester,
                artist=artist,
                album=album,
                uploader=data.get('uploader', artist),
                webpage_url=data.get('webpage_url', ''),
                description=description[:500] if description else None
            )

            self.queue.append(song)
            return song

        except Exception as e:
            logger.error(f"Failed to add song: {e}")
            return None

    async def add_playlist(self, url: str, requester: discord.Member) -> List[Song]:
        """Add all songs from a SoundCloud playlist/album to the queue"""
        if not self._ytdl_playlist:
            return []

        added_songs = []
        seen_ids = set()  # Track unique song IDs to prevent duplicates

        try:
            # Extract playlist info
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                lambda: self._ytdl_playlist.extract_info(url, download=False)
            )

            if not data:
                return []

            # Get playlist title as album name
            playlist_title = data.get('title', None)

            # Get entries from playlist
            entries = data.get('entries', [])
            if not entries:
                # Maybe it's a single track, try adding it as a song
                single_song = await self.add_song(url, requester)
                return [single_song] if single_song else []

            # Add each unique track to queue
            for entry in entries:
                if not entry:
                    continue

                # Get unique identifier for this track
                track_id = entry.get('id') or entry.get('webpage_url') or entry.get('title', '')

                # Skip if we've already added this track
                if track_id in seen_ids:
                    continue
                seen_ids.add(track_id)

                # Extract artist info
                artist = entry.get('uploader', entry.get('artist', 'Unknown Artist'))
                title = entry.get('title', 'Unknown')

                # Skip if title is empty or unknown
                if not title or title == 'Unknown':
                    continue

                # Create song from entry data with metadata
                song = Song(
                    title=title,
                    url=entry.get('url') or entry.get('webpage_url', ''),
                    duration=entry.get('duration') or 0,
                    thumbnail=entry.get('thumbnail', ''),
                    requester=requester,
                    artist=artist,
                    album=playlist_title,  # Use playlist name as album
                    uploader=entry.get('uploader', artist),
                    webpage_url=entry.get('webpage_url', '')
                )

                self.queue.append(song)
                added_songs.append(song)

            return added_songs

        except Exception as e:
            logger.error(f"Failed to add playlist: {e}")
            return []

    async def _update_formerly_played(self, song: Song):
        """Update the now playing message to show it's finished"""
        if self.now_playing_message:
            try:
                # Create "formerly played" embed
                embed = discord.Embed(
                    title="Formerly Played",
                    description=f"**{song.title}** by **{song.artist}**",
                    color=discord.Color.dark_grey()
                )
                # Edit the message to remove buttons and update text
                await self.now_playing_message.edit(embed=embed, view=None)
            except discord.NotFound:
                pass  # Message was deleted
            except discord.HTTPException as e:
                logger.debug(f"Could not update formerly played message: {e}")
            finally:
                self.now_playing_message = None

    async def _send_now_playing(self, song: Song):
        """Send the now playing message with enhanced info"""
        if not self.text_channel:
            return

        # Fetch lyrics in background (non-blocking) - will be available when user clicks button
        asyncio.create_task(song.fetch_lyrics_async())

        # Build enhanced embed
        embed = discord.Embed(
            title="Now Playing",
            color=discord.Color.orange()
        )

        # Song title with link if available
        if song.webpage_url:
            embed.description = f"**[{song.title}]({song.webpage_url})**"
        else:
            embed.description = f"**{song.title}**"

        # Artist field
        embed.add_field(name="Artist", value=song.artist, inline=True)

        # Album field (if available)
        if song.album:
            embed.add_field(name="Album", value=song.album, inline=True)

        # Duration field
        embed.add_field(name="Duration", value=song.duration_str, inline=True)

        # Collaborators (if any)
        collaborators = song.get_collaborators()
        if collaborators:
            embed.add_field(
                name="Featuring",
                value=", ".join(collaborators),
                inline=True
            )

        # Requested by
        embed.add_field(name="Requested by", value=song.requester.mention, inline=True)

        # Queue info
        embed.add_field(name="Queue", value=f"{len(self.queue)} songs", inline=True)

        # Thumbnail
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)

        # Footer
        embed.set_footer(text="SoundCloud")

        # Create view with Lyrics button (always shown - button handles missing lyrics)
        view = NowPlayingView(song)

        try:
            self.now_playing_message = await self.text_channel.send(embed=embed, view=view)
        except discord.HTTPException as e:
            logger.error(f"Failed to send now playing message: {e}")

    async def play_next(self):
        """Play the next song in the queue"""
        # Reset skip flag at start
        self._skip_requested = False
        self._loading = True

        # Store the previous song to update "formerly played"
        previous_song = self.current

        if not self.queue or not self.voice_client:
            self.current = None
            self._loading = False
            # Update the last message to "formerly played" if there was a song
            if previous_song:
                await self._update_formerly_played(previous_song)
            return

        # Update the previous now playing message
        if previous_song:
            await self._update_formerly_played(previous_song)

        self.current = self.queue.pop(0)

        try:
            # Use SoundCloud search to get fresh URL (URLs can expire)
            search_query = f"scsearch:{self.current.title}"

            # Get fresh URL
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                lambda: self._ytdl.extract_info(search_query, download=False)
            )

            # Check if skip was requested while loading
            if self._skip_requested:
                logger.info(f"Skip requested during load, skipping: {self.current.title}")
                self._loading = False
                self._skip_requested = False
                await self.play_next()
                return

            if 'entries' in data:
                data = data['entries'][0]

            audio_url = data.get('url')
            if not audio_url:
                self._loading = False
                await self.play_next()
                return

            # Check again for skip after getting URL
            if self._skip_requested:
                logger.info(f"Skip requested during load, skipping: {self.current.title}")
                self._loading = False
                self._skip_requested = False
                await self.play_next()
                return

            # Update song metadata with fresh data
            self.current.artist = data.get('uploader', self.current.artist)
            self.current.thumbnail = data.get('thumbnail', self.current.thumbnail)
            self.current.webpage_url = data.get('webpage_url', self.current.webpage_url)

            # Create audio source
            source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=self.volume)

            # Mark loading complete before playing
            self._loading = False

            # Send now playing message
            await self._send_now_playing(self.current)

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
            self._loading = False
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
        """Skip current song (or skip loading song)"""
        # If still loading, set flag to skip when done loading
        if self._loading:
            self._skip_requested = True
            return True  # Indicate skip was queued

        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
            return True
        return False

    def set_volume(self, volume: float):
        """Set volume (0.0 to 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
        if self.voice_client and self.voice_client.source:
            self.voice_client.source.volume = self.volume


# =============================================================================
# MUSIC COG
# =============================================================================

class Music(commands.Cog):
    """Music commands for playing songs from SoundCloud"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: Dict[int, MusicPlayer] = {}  # guild_id -> MusicPlayer

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

    @app_commands.command(name="play", description="Play a song immediately from SoundCloud")
    @app_commands.describe(query="Song name or SoundCloud link")
    async def play(self, interaction: discord.Interaction, query: str):
        """Play a song immediately - if something is playing, it plays next"""
        log_command(str(interaction.user), interaction.user.id, f"play {query}", interaction.guild.name)

        # Check dependencies
        if not YTDLP_AVAILABLE:
            await interaction.response.send_message(
                "Music features are not available. yt-dlp is not installed.",
                ephemeral=True
            )
            return

        # Check voice channel
        voice_channel = await self._check_voice(interaction)
        if not voice_channel:
            return

        await interaction.response.defer()

        player = self.get_player(interaction.guild)

        # Set the text channel for now playing messages
        player.text_channel = interaction.channel

        # Connect to voice channel
        if not await player.connect(voice_channel):
            await interaction.followup.send("Failed to connect to voice channel!")
            return

        # Check if it's a URL (any http/https link)
        is_url = query.startswith('http://') or query.startswith('https://')

        if is_url:
            # Direct URL - add immediately without confirmation
            await interaction.followup.send("Loading song from link...")

            song = await player.add_song(query, interaction.user)

            if not song:
                await interaction.followup.send(
                    "Couldn't load the song from that URL!\n"
                    "Make sure it's a valid SoundCloud link."
                )
                return

            # If something is playing, move this song to front of queue (play next)
            if player.voice_client.is_playing() or player.voice_client.is_paused():
                # Move from end to front of queue
                if len(player.queue) > 1:
                    player.queue.insert(0, player.queue.pop())

                embed = discord.Embed(
                    title="Playing Next",
                    description=f"**{song.title}**",
                    color=discord.Color.green()
                )
                embed.add_field(name="Artist", value=song.artist, inline=True)
                embed.add_field(name="Duration", value=song.duration_str, inline=True)
                if song.thumbnail:
                    embed.set_thumbnail(url=song.thumbnail)
                await interaction.followup.send(embed=embed)
            else:
                # Nothing playing, start immediately
                await player.play_next()
        else:
            # Search query - show confirmation before adding
            await interaction.followup.send(f"Searching **SoundCloud** for: `{query}`...")

            # Search without adding to queue
            song_data = await player.search_song(query)

            if not song_data:
                await interaction.followup.send("Couldn't find any songs on SoundCloud!")
                return

            # Extract info for display
            title = song_data.get('title', 'Unknown')
            artist = song_data.get('uploader', song_data.get('artist', 'Unknown Artist'))
            duration = int(song_data.get('duration') or 0)
            thumbnail = song_data.get('thumbnail', '')

            # Format duration
            if duration < 3600:
                duration_str = f"{duration // 60}:{duration % 60:02d}"
            else:
                hours = duration // 3600
                minutes = (duration % 3600) // 60
                seconds = duration % 60
                duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"

            # Create confirmation embed
            embed = discord.Embed(
                title="Is this the right song?",
                description=f"**{title}**",
                color=discord.Color.blue()
            )
            embed.add_field(name="Artist", value=artist, inline=True)
            embed.add_field(name="Duration", value=duration_str, inline=True)
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)
            embed.set_footer(text="Click Confirm to play, or Cancel to search again")

            # Create confirmation view - pass play_next=True to play immediately
            view = SongConfirmView(song_data, interaction.user, player, play_next=True)
            msg = await interaction.followup.send(embed=embed, view=view)
            view.message = msg

    @app_commands.command(name="addsong", description="Add a song to the queue")
    @app_commands.describe(query="Song name or SoundCloud link")
    async def addsong(self, interaction: discord.Interaction, query: str):
        """Add a song to the queue (doesn't play immediately)"""
        log_command(str(interaction.user), interaction.user.id, f"addsong {query}", interaction.guild.name)

        # Check dependencies
        if not YTDLP_AVAILABLE:
            await interaction.response.send_message(
                "Music features are not available. yt-dlp is not installed.",
                ephemeral=True
            )
            return

        # Check voice channel
        voice_channel = await self._check_voice(interaction)
        if not voice_channel:
            return

        await interaction.response.defer()

        player = self.get_player(interaction.guild)

        # Set the text channel for now playing messages
        player.text_channel = interaction.channel

        # Connect to voice channel
        if not await player.connect(voice_channel):
            await interaction.followup.send("Failed to connect to voice channel!")
            return

        # Check if it's a URL (any http/https link)
        is_url = query.startswith('http://') or query.startswith('https://')

        if is_url:
            # Direct URL - add immediately without confirmation
            await interaction.followup.send("Adding song to queue...")

            song = await player.add_song(query, interaction.user)

            if not song:
                await interaction.followup.send(
                    "Couldn't load the song from that URL!\n"
                    "Make sure it's a valid SoundCloud link."
                )
                return

            embed = discord.Embed(
                title="Added to Queue",
                description=f"**{song.title}**",
                color=discord.Color.orange()
            )
            embed.add_field(name="Artist", value=song.artist, inline=True)
            embed.add_field(name="Position", value=f"#{len(player.queue)}", inline=True)
            embed.add_field(name="Duration", value=song.duration_str, inline=True)
            if song.thumbnail:
                embed.set_thumbnail(url=song.thumbnail)
            await interaction.followup.send(embed=embed)

            # Start playing if nothing is playing
            if not player.voice_client.is_playing() and not player.voice_client.is_paused():
                await player.play_next()
        else:
            # Search query - show confirmation before adding
            await interaction.followup.send(f"Searching **SoundCloud** for: `{query}`...")

            # Search without adding to queue
            song_data = await player.search_song(query)

            if not song_data:
                await interaction.followup.send("Couldn't find any songs on SoundCloud!")
                return

            # Extract info for display
            title = song_data.get('title', 'Unknown')
            artist = song_data.get('uploader', song_data.get('artist', 'Unknown Artist'))
            duration = int(song_data.get('duration') or 0)
            thumbnail = song_data.get('thumbnail', '')

            # Format duration
            if duration < 3600:
                duration_str = f"{duration // 60}:{duration % 60:02d}"
            else:
                hours = duration // 3600
                minutes = (duration % 3600) // 60
                seconds = duration % 60
                duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"

            # Create confirmation embed
            embed = discord.Embed(
                title="Is this the right song?",
                description=f"**{title}**",
                color=discord.Color.blue()
            )
            embed.add_field(name="Artist", value=artist, inline=True)
            embed.add_field(name="Duration", value=duration_str, inline=True)
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)
            embed.set_footer(text="Click Confirm to add to queue, or Cancel to search again")

            # Create confirmation view - play_next=False to just add to queue
            view = SongConfirmView(song_data, interaction.user, player, play_next=False)
            msg = await interaction.followup.send(embed=embed, view=view)
            view.message = msg

    @app_commands.command(name="playlist", description="Play a SoundCloud playlist or album")
    @app_commands.describe(url="SoundCloud playlist or album URL")
    async def playlist(self, interaction: discord.Interaction, url: str):
        """Add all songs from a SoundCloud playlist/album to the queue"""
        log_command(str(interaction.user), interaction.user.id, f"playlist {url}", interaction.guild.name)

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

        # Validate URL is a SoundCloud link
        if not (SOUNDCLOUD_PATTERN.match(url) or SOUNDCLOUD_MOBILE_PATTERN.match(url)):
            await interaction.response.send_message(
                "❌ Please provide a valid SoundCloud playlist or album URL!\n"
                "Example: `https://soundcloud.com/artist/sets/album-name`",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        player = self.get_player(interaction.guild)

        # Set the text channel for now playing messages
        player.text_channel = interaction.channel

        # Connect to voice channel
        if not await player.connect(voice_channel):
            await interaction.followup.send("❌ Failed to connect to voice channel!")
            return

        await interaction.followup.send("📂 Loading playlist/album from SoundCloud...")

        # Add all songs from playlist
        added_songs = await player.add_playlist(url, interaction.user)

        if not added_songs:
            await interaction.followup.send("❌ Couldn't load any songs from the playlist!")
            return

        # Calculate total duration
        total_duration = sum(song.duration for song in added_songs)
        duration_str = str(timedelta(seconds=total_duration))

        embed = discord.Embed(
            title="Playlist Added",
            description=f"Added **{len(added_songs)}** songs to the queue",
            color=discord.Color.orange()
        )
        embed.add_field(name="Total Duration", value=duration_str, inline=True)
        embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)

        # Show first few songs
        if added_songs:
            preview = "\n".join([f"`{i+1}.` {s.title}" for i, s in enumerate(added_songs[:5])])
            if len(added_songs) > 5:
                preview += f"\n*...and {len(added_songs) - 5} more*"
            embed.add_field(name="Songs", value=preview, inline=False)

        await interaction.followup.send(embed=embed)

        # Start playing if not already - play_next will send the enhanced now playing message
        if not player.voice_client.is_playing() and not player.voice_client.is_paused():
            await player.play_next()

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

        # Check if something is loading or playing
        if not player.voice_client:
            await interaction.response.send_message("❌ Not connected to voice!", ephemeral=True)
            return

        if not player.current and not player._loading:
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
            return

        skipped_title = player.current.title if player.current else "Loading song"

        if player._loading:
            # Song is still loading - mark for skip
            player.skip()
            await interaction.response.send_message(f"⏭️ Skipping **{skipped_title}** (was loading)")
        else:
            # Song is playing - stop it
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
        """Show the queue with remove buttons"""
        log_command(str(interaction.user), interaction.user.id, "queue", interaction.guild.name)

        player = self.get_player(interaction.guild)

        # If queue is empty and nothing playing, show simple message
        if not player.queue and not player.current:
            embed = discord.Embed(
                title="Music Queue",
                description="The queue is empty! Use `/play` to add songs.",
                color=discord.Color.purple()
            )
            await interaction.response.send_message(embed=embed)
            return

        # Create queue view with remove buttons
        view = QueueView(player, interaction.user.id)
        embed = view._build_embed()

        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        """Show current song with full details"""
        log_command(str(interaction.user), interaction.user.id, "nowplaying", interaction.guild.name)

        player = self.get_player(interaction.guild)

        if not player.current:
            await interaction.response.send_message("Nothing is playing!", ephemeral=True)
            return

        song = player.current

        # Build enhanced embed
        embed = discord.Embed(
            title="Now Playing",
            color=discord.Color.orange()
        )

        # Song title with link if available
        if song.webpage_url:
            embed.description = f"**[{song.title}]({song.webpage_url})**"
        else:
            embed.description = f"**{song.title}**"

        # Artist field
        embed.add_field(name="Artist", value=song.artist, inline=True)

        # Album field (if available)
        if song.album:
            embed.add_field(name="Album", value=song.album, inline=True)

        # Duration field
        embed.add_field(name="Duration", value=song.duration_str, inline=True)

        # Collaborators (if any)
        collaborators = song.get_collaborators()
        if collaborators:
            embed.add_field(
                name="Featuring",
                value=", ".join(collaborators),
                inline=True
            )

        # Requested by
        embed.add_field(name="Requested by", value=song.requester.mention, inline=True)

        # Volume
        embed.add_field(name="Volume", value=f"{int(player.volume * 100)}%", inline=True)

        # Queue info
        embed.add_field(name="Queue", value=f"{len(player.queue)} songs remaining", inline=True)

        # Thumbnail
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)

        # Footer
        embed.set_footer(text="SoundCloud")

        # Create view with Lyrics button (always shown - button handles missing lyrics)
        view = NowPlayingView(song)

        await interaction.response.send_message(embed=embed, view=view)

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

    @app_commands.command(name="clearqueue", description="Clear the entire queue (Mods only)")
    async def clearqueue(self, interaction: discord.Interaction):
        """Clear the queue - requires Manage Messages or Moderate Members permission"""
        log_command(str(interaction.user), interaction.user.id, "clearqueue", interaction.guild.name)

        # Check permissions - must be owner, admin, or moderator
        is_owner = interaction.user.id == interaction.guild.owner_id
        is_admin = interaction.user.guild_permissions.administrator
        is_mod = (interaction.user.guild_permissions.manage_messages or
                  interaction.user.guild_permissions.moderate_members)

        if not is_owner and not is_admin and not is_mod:
            await interaction.response.send_message(
                "You need **Manage Messages** or **Moderate Members** permission to clear the queue!",
                ephemeral=True
            )
            return

        player = self.get_player(interaction.guild)

        if not player.queue:
            await interaction.response.send_message("The queue is already empty!", ephemeral=True)
            return

        count = len(player.queue)
        player.queue.clear()
        await interaction.response.send_message(f"Cleared **{count}** songs from the queue!")


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Music cog to the bot"""
    await bot.add_cog(Music(bot))
