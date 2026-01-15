"""
Karaoke Data Module
Handles song registry, LRC lyric parsing, and lyric synchronization

LRC Format:
[mm:ss.xx] Lyric line here
[00:15.50] First line of verse
[00:18.20] Second line of verse

The bot reads these timestamps and displays lyrics synced to playback.
"""

import re
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class LyricLine:
    """A single line of lyrics with its timestamp"""
    timestamp: float  # Time in seconds
    text: str

    def __repr__(self):
        mins = int(self.timestamp // 60)
        secs = self.timestamp % 60
        return f"[{mins:02d}:{secs:05.2f}] {self.text}"


@dataclass
class KaraokeSong:
    """A karaoke song with metadata and lyrics"""
    id: str                    # Unique identifier
    title: str                 # Song title
    artist: str                # Artist name
    soundcloud_url: str        # SoundCloud URL for audio
    duration: int              # Duration in seconds (approximate)
    lyrics_file: str           # Path to LRC file relative to data/karaoke/
    lyrics: List[LyricLine] = None  # Parsed lyrics (loaded on demand)

    @property
    def display_name(self) -> str:
        return f"{self.title} - {self.artist}"


# =============================================================================
# KARAOKE SONG REGISTRY
# =============================================================================
# Add your songs here. Each song needs:
# - A unique ID
# - Title and artist
# - SoundCloud URL (instrumental/karaoke version preferred)
# - Approximate duration in seconds
# - LRC lyrics file name

KARAOKE_SONGS: Dict[str, KaraokeSong] = {
    "happier": KaraokeSong(
        id="happier",
        title="Happier",
        artist="Marshmello ft. Bastille",
        soundcloud_url="https://soundcloud.com/search?q=happier%20marshmello%20bastille",  # Replace with actual URL
        duration=214,  # 3:34
        lyrics_file="happier.lrc"
    ),
    "stereo_hearts": KaraokeSong(
        id="stereo_hearts",
        title="Stereo Hearts",
        artist="Gym Class Heroes ft. Adam Levine",
        soundcloud_url="https://soundcloud.com/search?q=stereo%20hearts%20gym%20class%20heroes",  # Replace with actual URL
        duration=232,  # 3:52
        lyrics_file="stereo_hearts.lrc"
    ),
    "viva_la_vida": KaraokeSong(
        id="viva_la_vida",
        title="Viva La Vida",
        artist="Coldplay",
        soundcloud_url="https://soundcloud.com/search?q=viva%20la%20vida%20coldplay",  # Replace with actual URL
        duration=242,  # 4:02
        lyrics_file="viva_la_vida.lrc"
    ),
    "something_blue": KaraokeSong(
        id="something_blue",
        title="Something Blue",
        artist="VOILA",
        soundcloud_url="https://soundcloud.com/search?q=something%20blue%20voila",  # Replace with actual URL
        duration=187,  # 3:07
        lyrics_file="something_blue.lrc"
    ),
    "youre_welcome": KaraokeSong(
        id="youre_welcome",
        title="You're Welcome",
        artist="Dwayne Johnson (Maui) - Moana",
        soundcloud_url="https://soundcloud.com/fun-kids-100189584/sets/your-welcome-moana",
        duration=169,  # 2:49
        lyrics_file="youre_welcome.lrc"
    ),
}


# =============================================================================
# LRC PARSER
# =============================================================================

def parse_lrc_timestamp(timestamp_str: str) -> float:
    """
    Parse LRC timestamp format [mm:ss.xx] to seconds
    Examples: [01:23.45] -> 83.45, [00:05.00] -> 5.0
    """
    # Remove brackets
    timestamp_str = timestamp_str.strip("[]")

    # Handle different formats
    # [mm:ss.xx] or [mm:ss:xx] or [mm:ss]
    parts = re.split(r"[:.]", timestamp_str)

    if len(parts) >= 2:
        minutes = int(parts[0])
        seconds = int(parts[1])

        # Centiseconds if present
        if len(parts) >= 3:
            centiseconds = int(parts[2].ljust(2, '0')[:2])  # Ensure 2 digits
            return minutes * 60 + seconds + centiseconds / 100

        return minutes * 60 + seconds

    return 0.0


def parse_lrc_file(filepath: str) -> List[LyricLine]:
    """
    Parse an LRC file and return list of LyricLine objects
    """
    lyrics = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # Skip metadata tags like [ar:Artist], [ti:Title], etc.
                if re.match(r'\[[a-zA-Z]{2}:', line):
                    continue

                # Match timestamp and lyrics: [mm:ss.xx] lyrics text
                match = re.match(r'\[(\d{1,2}:\d{2}(?:[.:]\d{1,3})?)\](.*)', line)
                if match:
                    timestamp_str = match.group(1)
                    text = match.group(2).strip()

                    # Skip empty lines but keep instrumental markers
                    if text or "[" not in line:
                        timestamp = parse_lrc_timestamp(timestamp_str)
                        lyrics.append(LyricLine(timestamp=timestamp, text=text if text else "..."))

        # Sort by timestamp
        lyrics.sort(key=lambda x: x.timestamp)

    except FileNotFoundError:
        # Return empty list if file not found
        pass
    except Exception as e:
        print(f"Error parsing LRC file {filepath}: {e}")

    return lyrics


def load_song_lyrics(song: KaraokeSong) -> List[LyricLine]:
    """
    Load lyrics for a song from its LRC file
    """
    base_path = Path(__file__).parent.parent / "lyrics"
    lyrics_path = base_path / song.lyrics_file

    return parse_lrc_file(str(lyrics_path))


def get_current_lyric(lyrics: List[LyricLine], current_time: float, context_lines: int = 2) -> Tuple[int, str]:
    """
    Get the current lyric line based on playback time
    Returns (current_index, formatted_display_text)

    Args:
        lyrics: List of LyricLine objects
        current_time: Current playback time in seconds
        context_lines: Number of previous/next lines to show

    Returns:
        Tuple of (current line index, formatted lyrics display)
    """
    if not lyrics:
        return 0, "*No lyrics available*"

    # Find current line (last line where timestamp <= current_time)
    current_idx = 0
    for i, line in enumerate(lyrics):
        if line.timestamp <= current_time:
            current_idx = i
        else:
            break

    # Build display with context
    lines = []

    # Previous lines (dimmed)
    start_idx = max(0, current_idx - context_lines)
    for i in range(start_idx, current_idx):
        lines.append(f"*{lyrics[i].text}*")  # Italic for past lines

    # Current line (bold)
    if current_idx < len(lyrics):
        lines.append(f"**>> {lyrics[current_idx].text} <<**")

    # Upcoming lines
    end_idx = min(len(lyrics), current_idx + context_lines + 1)
    for i in range(current_idx + 1, end_idx):
        lines.append(lyrics[i].text)

    return current_idx, "\n".join(lines) if lines else "*Instrumental*"


def format_lyrics_progress(lyrics: List[LyricLine], current_time: float, duration: float) -> str:
    """
    Format lyrics display with progress bar
    """
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

    # Current lyrics
    _, lyrics_display = get_current_lyric(lyrics, current_time)

    return f"```\n[{bar}] {time_str}\n```\n\n{lyrics_display}"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_all_songs() -> List[KaraokeSong]:
    """Get all available karaoke songs"""
    return list(KARAOKE_SONGS.values())


def get_song_by_id(song_id: str) -> Optional[KaraokeSong]:
    """Get a song by its ID"""
    return KARAOKE_SONGS.get(song_id)


def initialize_all_lyrics():
    """Pre-load all lyrics on startup (optional)"""
    for song in KARAOKE_SONGS.values():
        if song.lyrics is None:
            song.lyrics = load_song_lyrics(song)
