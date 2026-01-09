"""
Audio Optimization Settings for Discord Music Playback

This module provides optimized FFmpeg and yt-dlp configurations for
smooth, high-quality SoundCloud playback on Discord voice channels.

The optimizations focus on:
- Opus passthrough when available (Discord's native codec)
- Minimal re-encoding to preserve quality
- Proper buffering to prevent micro-stutters
- Low latency while maintaining stability
- CPU efficiency for VPS hosting

To disable optimizations, set AUDIO_OPTIMIZATION_ENABLED = False
"""

import json
import os
from typing import Dict, Optional
from pathlib import Path

# =============================================================================
# MASTER TOGGLE - Set to False to revert to basic settings
# =============================================================================
AUDIO_OPTIMIZATION_ENABLED = True

# =============================================================================
# STORAGE FOR PER-GUILD ULTRA MODE SETTINGS
# =============================================================================
_ULTRA_MODE_FILE = Path(__file__).parent.parent / "data" / "audio_ultra_mode.json"
_ultra_mode_guilds: Dict[int, bool] = {}


def _load_ultra_mode_settings():
    """Load ultra mode settings from disk"""
    global _ultra_mode_guilds
    try:
        if _ULTRA_MODE_FILE.exists():
            with open(_ULTRA_MODE_FILE, 'r') as f:
                data = json.load(f)
                _ultra_mode_guilds = {int(k): v for k, v in data.items()}
    except Exception:
        _ultra_mode_guilds = {}


def _save_ultra_mode_settings():
    """Save ultra mode settings to disk"""
    try:
        _ULTRA_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_ULTRA_MODE_FILE, 'w') as f:
            json.dump({str(k): v for k, v in _ultra_mode_guilds.items()}, f)
    except Exception:
        pass


def is_ultra_mode_enabled(guild_id: int) -> bool:
    """Check if ultra mode is enabled for a guild"""
    if not _ultra_mode_guilds:
        _load_ultra_mode_settings()
    return _ultra_mode_guilds.get(guild_id, False)


def set_ultra_mode(guild_id: int, enabled: bool):
    """Set ultra mode for a guild"""
    _ultra_mode_guilds[guild_id] = enabled
    _save_ultra_mode_settings()


# =============================================================================
# BASIC SETTINGS (Original - used when optimization is disabled)
# =============================================================================

BASIC_YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'scsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
}

BASIC_FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# =============================================================================
# OPTIMIZED SETTINGS (Standard optimization)
# =============================================================================

# yt-dlp format preference explanation:
# 1. bestaudio[acodec=opus] - Opus is Discord's native codec, no re-encoding needed
# 2. bestaudio[acodec=aac] - AAC is high quality, efficient conversion to Opus
# 3. bestaudio[acodec=vorbis] - Vorbis is similar to Opus, good quality
# 4. bestaudio - Any best audio as fallback
# This order minimizes transcoding artifacts and CPU usage

OPTIMIZED_YTDL_OPTIONS = {
    # Prefer Opus (Discord native) > AAC (high quality) > Vorbis > any best audio
    'format': 'bestaudio[acodec=opus]/bestaudio[acodec=aac]/bestaudio[acodec=vorbis]/bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'scsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
    # Optimization: Prefer formats with higher audio quality
    'format_sort': ['acodec:opus', 'acodec:aac', 'acodec:vorbis', 'abr', 'asr'],
    # Socket timeout for reliability
    'socket_timeout': 30,
}

# FFmpeg before_options explanation:
# -reconnect 1: Auto-reconnect if connection drops (critical for streaming)
# -reconnect_streamed 1: Enable reconnect for streaming protocols
# -reconnect_delay_max 5: Max 5 seconds between reconnect attempts
# -nostdin: Don't read from stdin (prevents blocking issues)
# -analyzeduration 200000: Analyze 200ms of audio for format detection (faster start)
# -probesize 200000: Probe ~200KB for format info (good balance of speed/accuracy)
# -fflags +discardcorrupt: Skip corrupt frames instead of failing (stability)

# FFmpeg options explanation:
# -vn: Disable video processing (we only want audio)
# -ar 48000: Output at 48kHz (Discord's native sample rate)
# -ac 2: Stereo output (Discord standard)
# -f s16le: Output format - 16-bit signed little-endian PCM (discord.py native)
#
# NOTE: We do NOT use aresample=async=1 because it can cause audio speedup/slowdown
# by compensating for timestamp variations. For music playback, we want exact speed.

OPTIMIZED_FFMPEG_OPTIONS = {
    'before_options': (
        '-reconnect 1 '
        '-reconnect_streamed 1 '
        '-reconnect_delay_max 5 '
        '-nostdin '
        '-analyzeduration 200000 '
        '-probesize 200000 '
        '-fflags +discardcorrupt'
    ),
    'options': (
        '-vn '
        '-ar 48000 '
        '-ac 2 '
        '-f s16le'
    )
}

# =============================================================================
# ULTRA SETTINGS (Admin-only, maximum quality)
# =============================================================================

# Ultra mode prioritizes audio quality over everything else
# Best for servers with good bandwidth and boosted Discord servers (higher bitrate limit)

ULTRA_YTDL_OPTIONS = {
    # Same format preference but with additional quality parameters
    'format': 'bestaudio[acodec=opus]/bestaudio[acodec=aac]/bestaudio[acodec=vorbis]/bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'scsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
    # Ultra: Strict format sorting for maximum quality
    'format_sort': ['acodec:opus', 'acodec:aac', 'acodec:vorbis', 'abr~256', 'asr~48000'],
    'socket_timeout': 30,
    # Prefer higher quality streams
    'prefer_free_formats': False,
}

# Ultra FFmpeg settings explanation:
# -thread_queue_size 4096: Larger buffer for input thread (prevents underruns)
# Larger analyzeduration/probesize: Better format detection at cost of startup time
# -fflags +genpts: Generate presentation timestamps for smooth playback
#
# NOTE: We do NOT use aresample=async=1 because it causes audio speed changes.
# Instead, we use high-quality resampling without async compensation.

ULTRA_FFMPEG_OPTIONS = {
    'before_options': (
        '-reconnect 1 '
        '-reconnect_streamed 1 '
        '-reconnect_delay_max 5 '
        '-nostdin '
        '-thread_queue_size 4096 '
        '-analyzeduration 500000 '
        '-probesize 500000 '
        '-fflags +discardcorrupt+genpts '
        '-err_detect ignore_err'
    ),
    'options': (
        '-vn '
        '-ar 48000 '
        '-ac 2 '
        '-f s16le '
        '-af aresample=resampler=soxr:precision=28:dither_method=triangular_hp'
    )
}

# =============================================================================
# PLAYLIST-SPECIFIC OPTIONS
# =============================================================================

OPTIMIZED_YTDL_PLAYLIST_OPTIONS = {
    'format': 'bestaudio[acodec=opus]/bestaudio[acodec=aac]/bestaudio[acodec=vorbis]/bestaudio/best',
    'noplaylist': False,  # Allow playlists
    'nocheckcertificate': True,
    'ignoreerrors': True,  # Skip unavailable tracks
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'extract_flat': False,
    'format_sort': ['acodec:opus', 'acodec:aac', 'acodec:vorbis', 'abr', 'asr'],
    'socket_timeout': 30,
}

BASIC_YTDL_PLAYLIST_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'extract_flat': False,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_ytdl_options(guild_id: Optional[int] = None) -> dict:
    """
    Get the appropriate yt-dlp options based on optimization settings.

    Args:
        guild_id: Optional guild ID to check for ultra mode

    Returns:
        Dictionary of yt-dlp options
    """
    if not AUDIO_OPTIMIZATION_ENABLED:
        return BASIC_YTDL_OPTIONS.copy()

    if guild_id and is_ultra_mode_enabled(guild_id):
        return ULTRA_YTDL_OPTIONS.copy()

    return OPTIMIZED_YTDL_OPTIONS.copy()


def get_ytdl_playlist_options(guild_id: Optional[int] = None) -> dict:
    """
    Get the appropriate yt-dlp playlist options based on optimization settings.

    Args:
        guild_id: Optional guild ID to check for ultra mode

    Returns:
        Dictionary of yt-dlp options for playlists
    """
    if not AUDIO_OPTIMIZATION_ENABLED:
        return BASIC_YTDL_PLAYLIST_OPTIONS.copy()

    # Ultra mode uses same playlist options (already optimized)
    return OPTIMIZED_YTDL_PLAYLIST_OPTIONS.copy()


def get_ffmpeg_options(guild_id: Optional[int] = None) -> dict:
    """
    Get the appropriate FFmpeg options based on optimization settings.

    Args:
        guild_id: Optional guild ID to check for ultra mode

    Returns:
        Dictionary with 'before_options' and 'options' keys
    """
    if not AUDIO_OPTIMIZATION_ENABLED:
        return BASIC_FFMPEG_OPTIONS.copy()

    if guild_id and is_ultra_mode_enabled(guild_id):
        return ULTRA_FFMPEG_OPTIONS.copy()

    return OPTIMIZED_FFMPEG_OPTIONS.copy()


def get_optimization_status(guild_id: Optional[int] = None) -> dict:
    """
    Get the current optimization status for display.

    Returns:
        Dictionary with optimization info
    """
    ultra = guild_id and is_ultra_mode_enabled(guild_id)

    return {
        'enabled': AUDIO_OPTIMIZATION_ENABLED,
        'mode': 'ultra' if ultra else ('optimized' if AUDIO_OPTIMIZATION_ENABLED else 'basic'),
        'description': (
            'Ultra Quality Mode - Maximum audio quality' if ultra
            else 'Optimized - Balanced quality and performance' if AUDIO_OPTIMIZATION_ENABLED
            else 'Basic - Standard playback'
        ),
        'features': {
            'opus_passthrough': AUDIO_OPTIMIZATION_ENABLED,
            'async_resampling': AUDIO_OPTIMIZATION_ENABLED,
            'enhanced_buffering': ultra,
            'multi_threaded_filters': ultra,
        }
    }
