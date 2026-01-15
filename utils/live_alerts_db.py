"""
Live Alerts Database - Manages streamer tracking and notifications

This module handles:
- Tracking Twitch/YouTube/TikTok streamers
- Storing which channels to post alerts in
- Preventing duplicate notifications
- RSS/Reddit feed tracking for auto-news
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

# File path for storing live alerts data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
LIVE_ALERTS_FILE = os.path.join(DATA_DIR, 'live_alerts.json')


# ============================================
# DATA PERSISTENCE FUNCTIONS
# ============================================

def _load_alerts_data() -> dict:
    """Load live alerts data from JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(LIVE_ALERTS_FILE):
        try:
            with open(LIVE_ALERTS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Default structure
    return {
        "guilds": {}
    }


def _save_alerts_data(data: dict):
    """Save live alerts data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LIVE_ALERTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _get_guild_data(guild_id: int) -> dict:
    """Get guild's alerts config, creating default if doesn't exist"""
    data = _load_alerts_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {
            "alert_channel_id": None,
            "news_channel_id": None,
            "streamers": [],  # List of {platform, username, last_notified, last_status}
            "feeds": [],      # List of {type, url, last_post_id}
            "mention_role_id": None
        }
        _save_alerts_data(data)

    return data["guilds"][guild_str]


# ============================================
# CHANNEL CONFIGURATION
# ============================================

def set_alert_channel(guild_id: int, channel_id: int) -> bool:
    """Set the channel for live stream alerts"""
    data = _load_alerts_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {
            "alert_channel_id": None,
            "news_channel_id": None,
            "streamers": [],
            "feeds": [],
            "mention_role_id": None
        }

    data["guilds"][guild_str]["alert_channel_id"] = channel_id
    _save_alerts_data(data)
    return True


def set_news_channel(guild_id: int, channel_id: int) -> bool:
    """Set the channel for auto news/feed posts"""
    data = _load_alerts_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {
            "alert_channel_id": None,
            "news_channel_id": None,
            "streamers": [],
            "feeds": [],
            "mention_role_id": None
        }

    data["guilds"][guild_str]["news_channel_id"] = channel_id
    _save_alerts_data(data)
    return True


def set_mention_role(guild_id: int, role_id: Optional[int]) -> bool:
    """Set the role to mention when someone goes live"""
    data = _load_alerts_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False

    data["guilds"][guild_str]["mention_role_id"] = role_id
    _save_alerts_data(data)
    return True


def get_alert_channel(guild_id: int) -> Optional[int]:
    """Get the alert channel ID for a guild"""
    guild_data = _get_guild_data(guild_id)
    return guild_data.get("alert_channel_id")


def get_news_channel(guild_id: int) -> Optional[int]:
    """Get the news channel ID for a guild"""
    guild_data = _get_guild_data(guild_id)
    return guild_data.get("news_channel_id")


def get_mention_role(guild_id: int) -> Optional[int]:
    """Get the mention role ID for a guild"""
    guild_data = _get_guild_data(guild_id)
    return guild_data.get("mention_role_id")


# ============================================
# STREAMER MANAGEMENT
# ============================================

def add_streamer(guild_id: int, platform: str, username: str) -> Tuple[bool, str]:
    """
    Add a streamer to track

    Args:
        guild_id: The guild ID
        platform: "twitch", "youtube", or "tiktok"
        username: The streamer's username/channel ID

    Returns:
        (success, message)
    """
    data = _load_alerts_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {
            "alert_channel_id": None,
            "news_channel_id": None,
            "streamers": [],
            "feeds": [],
            "mention_role_id": None
        }

    # Check if already tracking
    for streamer in data["guilds"][guild_str]["streamers"]:
        if streamer["platform"] == platform and streamer["username"].lower() == username.lower():
            return False, f"Already tracking {username} on {platform}"

    # Add the streamer
    data["guilds"][guild_str]["streamers"].append({
        "platform": platform.lower(),
        "username": username,
        "last_notified": None,
        "last_status": "offline",
        "custom_message": None
    })

    _save_alerts_data(data)
    return True, f"Now tracking {username} on {platform}"


def remove_streamer(guild_id: int, platform: str, username: str) -> Tuple[bool, str]:
    """Remove a streamer from tracking"""
    data = _load_alerts_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "No streamers being tracked"

    streamers = data["guilds"][guild_str]["streamers"]
    for i, streamer in enumerate(streamers):
        if streamer["platform"] == platform.lower() and streamer["username"].lower() == username.lower():
            streamers.pop(i)
            _save_alerts_data(data)
            return True, f"Stopped tracking {username} on {platform}"

    return False, f"Not tracking {username} on {platform}"


def get_streamers(guild_id: int) -> List[Dict]:
    """Get all tracked streamers for a guild"""
    guild_data = _get_guild_data(guild_id)
    return guild_data.get("streamers", [])


def update_streamer_status(guild_id: int, platform: str, username: str, status: str, notified: bool = False):
    """Update a streamer's status after checking"""
    data = _load_alerts_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return

    for streamer in data["guilds"][guild_str]["streamers"]:
        if streamer["platform"] == platform.lower() and streamer["username"].lower() == username.lower():
            streamer["last_status"] = status
            if notified:
                streamer["last_notified"] = datetime.now().isoformat()
            break

    _save_alerts_data(data)


def get_all_guilds_with_streamers() -> List[Tuple[int, List[Dict]]]:
    """Get all guilds that have streamers configured"""
    data = _load_alerts_data()
    result = []

    for guild_str, guild_data in data.get("guilds", {}).items():
        streamers = guild_data.get("streamers", [])
        if streamers and guild_data.get("alert_channel_id"):
            result.append((int(guild_str), streamers))

    return result


# ============================================
# FEED MANAGEMENT (Reddit/RSS)
# ============================================

def add_feed(guild_id: int, feed_type: str, url: str, name: str = None) -> Tuple[bool, str]:
    """
    Add a feed to track

    Args:
        guild_id: The guild ID
        feed_type: "reddit" or "rss"
        url: The subreddit name (for reddit) or RSS URL
        name: Optional display name

    Returns:
        (success, message)
    """
    data = _load_alerts_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {
            "alert_channel_id": None,
            "news_channel_id": None,
            "streamers": [],
            "feeds": [],
            "mention_role_id": None
        }

    # Check if already tracking
    for feed in data["guilds"][guild_str]["feeds"]:
        if feed["type"] == feed_type and feed["url"].lower() == url.lower():
            return False, f"Already tracking this {feed_type} feed"

    # Add the feed
    data["guilds"][guild_str]["feeds"].append({
        "type": feed_type.lower(),
        "url": url,
        "name": name or url,
        "last_post_id": None,
        "last_checked": None
    })

    _save_alerts_data(data)
    return True, f"Now tracking {feed_type} feed: {name or url}"


def remove_feed(guild_id: int, feed_type: str, url: str) -> Tuple[bool, str]:
    """Remove a feed from tracking"""
    data = _load_alerts_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "No feeds being tracked"

    feeds = data["guilds"][guild_str]["feeds"]
    for i, feed in enumerate(feeds):
        if feed["type"] == feed_type.lower() and feed["url"].lower() == url.lower():
            feeds.pop(i)
            _save_alerts_data(data)
            return True, f"Stopped tracking {feed_type} feed: {url}"

    return False, f"Not tracking this {feed_type} feed"


def get_feeds(guild_id: int) -> List[Dict]:
    """Get all tracked feeds for a guild"""
    guild_data = _get_guild_data(guild_id)
    return guild_data.get("feeds", [])


def update_feed_last_post(guild_id: int, feed_type: str, url: str, post_id: str):
    """Update a feed's last post ID after posting"""
    data = _load_alerts_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return

    for feed in data["guilds"][guild_str]["feeds"]:
        if feed["type"] == feed_type.lower() and feed["url"].lower() == url.lower():
            feed["last_post_id"] = post_id
            feed["last_checked"] = datetime.now().isoformat()
            break

    _save_alerts_data(data)


def get_all_guilds_with_feeds() -> List[Tuple[int, List[Dict]]]:
    """Get all guilds that have feeds configured"""
    data = _load_alerts_data()
    result = []

    for guild_str, guild_data in data.get("guilds", {}).items():
        feeds = guild_data.get("feeds", [])
        if feeds and guild_data.get("news_channel_id"):
            result.append((int(guild_str), feeds))

    return result
