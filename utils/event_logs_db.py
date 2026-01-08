"""
Event Logs Database Utility
Handles saving, loading, searching, and cleanup of event logs
Stores logs in JSON format with 30-day retention
"""

import json
import os
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum

from utils.logger import logger

# Path to the data files
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
EVENT_LOGS_FILE = os.path.join(DATA_DIR, "event_logs.json")
EVENT_CONFIG_FILE = os.path.join(DATA_DIR, "event_log_config.json")


class EventCategory(Enum):
    """Categories of events that can be logged"""
    MESSAGES = "messages"
    MEMBERS = "members"
    MODERATION = "moderation"
    VOICE = "voice"
    SERVER = "server"
    COMMANDS = "commands"
    # Future expansion:
    # CHATLOGS = "chatlogs"
    # VOICECHATLOGS = "voicechatlogs"
    # INVITES = "invites"
    # THREADS = "threads"


# Event types for each category
EVENT_TYPES = {
    "messages": [
        "message_edit",
        "message_delete",
        "bulk_delete"
    ],
    "members": [
        "member_join",
        "member_leave",
        "member_ban",
        "member_unban",
        "member_role_add",
        "member_role_remove",
        "member_nickname_change"
    ],
    "moderation": [
        "timeout_add",
        "timeout_remove",
        "kick",
        "warn"
    ],
    "voice": [
        "voice_join",
        "voice_leave",
        "voice_move",
        "voice_mute",
        "voice_deafen",
        "voice_server_mute",
        "voice_server_deafen"
    ],
    "server": [
        "channel_create",
        "channel_delete",
        "channel_update",
        "role_create",
        "role_delete",
        "role_update"
    ],
    "commands": [
        "command_use"
    ]
}


def _ensure_data_dir():
    """Make sure the data directory exists"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


# ==================== CONFIG FUNCTIONS ====================

def _load_config() -> Dict:
    """Load event log configuration from file"""
    _ensure_data_dir()

    if not os.path.exists(EVENT_CONFIG_FILE):
        return {}

    try:
        with open(EVENT_CONFIG_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load event log config: {e}")
        return {}


def _save_config(data: Dict) -> bool:
    """Save event log configuration to file"""
    _ensure_data_dir()

    try:
        with open(EVENT_CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Failed to save event log config: {e}")
        return False


def save_guild_config(
    guild_id: int,
    webhook_id: int,
    webhook_url: str,
    channel_id: int,
    configured_by: int,
    enabled_categories: Optional[List[str]] = None
) -> bool:
    """
    Save logging configuration for a guild

    Args:
        guild_id: The server ID
        webhook_id: The webhook ID for logging
        webhook_url: The webhook URL for sending logs
        channel_id: The channel ID where logs are sent
        configured_by: User ID who set up logging
        enabled_categories: List of enabled categories (defaults to all)

    Returns:
        True if saved successfully
    """
    data = _load_config()
    guild_key = str(guild_id)

    # Default to all categories enabled
    if enabled_categories is None:
        enabled_categories = [cat.value for cat in EventCategory]

    data[guild_key] = {
        "webhook_id": str(webhook_id),
        "webhook_url": webhook_url,
        "channel_id": str(channel_id),
        "enabled_categories": enabled_categories,
        "configured_by": str(configured_by),
        "configured_at": datetime.utcnow().isoformat(),
        "last_cleanup": datetime.utcnow().isoformat()
    }

    return _save_config(data)


def get_guild_config(guild_id: int) -> Optional[Dict]:
    """
    Get logging configuration for a guild

    Args:
        guild_id: The server ID

    Returns:
        Config dict or None if not configured
    """
    data = _load_config()
    guild_key = str(guild_id)

    if guild_key not in data:
        return None

    return data[guild_key]


def delete_guild_config(guild_id: int) -> bool:
    """
    Remove logging configuration for a guild

    Args:
        guild_id: The server ID

    Returns:
        True if deleted successfully
    """
    data = _load_config()
    guild_key = str(guild_id)

    if guild_key in data:
        del data[guild_key]
        return _save_config(data)

    return True


def is_logging_enabled(guild_id: int, category: Optional[str] = None) -> bool:
    """
    Check if logging is enabled for a guild (and optionally a specific category)

    Args:
        guild_id: The server ID
        category: Optional category to check

    Returns:
        True if logging is enabled
    """
    config = get_guild_config(guild_id)

    if config is None:
        return False

    if category is None:
        return True

    # Get all valid categories from the enum
    all_categories = [cat.value for cat in EventCategory]

    # If the category is a valid category, enable it by default
    # This ensures newly added categories work with existing configs
    if category in all_categories:
        enabled = config.get("enabled_categories", [])
        # If no categories are configured, or if it's a valid category, enable it
        if not enabled or category in enabled:
            return True
        # For backwards compatibility, enable all valid categories
        # (since user likely wants everything logged)
        return True

    return False


def update_last_cleanup(guild_id: int) -> bool:
    """Update the last cleanup timestamp for a guild"""
    data = _load_config()
    guild_key = str(guild_id)

    if guild_key in data:
        data[guild_key]["last_cleanup"] = datetime.utcnow().isoformat()
        return _save_config(data)

    return False


# ==================== LOG FUNCTIONS ====================

def _load_logs() -> Dict:
    """Load event logs from file"""
    _ensure_data_dir()

    if not os.path.exists(EVENT_LOGS_FILE):
        return {}

    try:
        with open(EVENT_LOGS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load event logs: {e}")
        return {}


def _save_logs(data: Dict) -> bool:
    """Save event logs to file"""
    _ensure_data_dir()

    try:
        with open(EVENT_LOGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Failed to save event logs: {e}")
        return False


def save_event_log(
    guild_id: int,
    category: str,
    event_type: str,
    user_id: int,
    user_name: str,
    user_display_name: Optional[str] = None,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    channel_id: Optional[int] = None,
    channel_name: Optional[str] = None,
    before: Optional[str] = None,
    after: Optional[str] = None,
    details: Optional[Dict] = None
) -> bool:
    """
    Save an event log entry

    Args:
        guild_id: The server ID
        category: Event category (messages, members, etc.)
        event_type: Specific event type (message_edit, member_join, etc.)
        user_id: The user who triggered the event
        user_name: The user's name (username#0000)
        user_display_name: The user's display/nick name
        target_id: Target user ID (if applicable)
        target_name: Target user name (if applicable)
        channel_id: Channel ID where event occurred
        channel_name: Channel name
        before: State before change (for edits)
        after: State after change (for edits)
        details: Additional event details

    Returns:
        True if saved successfully
    """
    data = _load_logs()
    guild_key = str(guild_id)

    # Initialize guild logs if needed
    if guild_key not in data:
        data[guild_key] = {
            "logs": [],
            "stats": {},
            "total_logged": 0
        }

    # Create the log entry
    log_entry = {
        "id": data[guild_key]["total_logged"] + 1,
        "timestamp": datetime.utcnow().isoformat(),
        "category": category,
        "event_type": event_type,
        "user": {
            "id": str(user_id),
            "name": user_name,
            "display_name": user_display_name or user_name
        }
    }

    # Add target info if provided
    if target_id is not None:
        log_entry["target"] = {
            "id": str(target_id),
            "name": target_name or "Unknown"
        }

    # Add channel info if provided
    if channel_id is not None:
        log_entry["channel"] = {
            "id": str(channel_id),
            "name": channel_name or "Unknown"
        }

    # Add before/after for edits
    if before is not None:
        log_entry["before"] = before
    if after is not None:
        log_entry["after"] = after

    # Add extra details if provided
    if details:
        log_entry["details"] = details

    # Add to logs (newest first)
    data[guild_key]["logs"].insert(0, log_entry)
    data[guild_key]["total_logged"] += 1

    # Update category stats
    if category not in data[guild_key]["stats"]:
        data[guild_key]["stats"][category] = 0
    data[guild_key]["stats"][category] += 1

    # Keep logs under a reasonable size (10000 entries max)
    if len(data[guild_key]["logs"]) > 10000:
        data[guild_key]["logs"] = data[guild_key]["logs"][:10000]

    return _save_logs(data)


def search_logs(
    guild_id: int,
    query: Optional[str] = None,
    user_filter: Optional[int] = None,
    category_filter: Optional[str] = None,
    event_type_filter: Optional[str] = None,
    channel_filter: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[Dict], int]:
    """
    Search logs with multiple filters

    Args:
        guild_id: The server ID
        query: Text to search in log content
        user_filter: Filter by user ID (matches user OR target)
        category_filter: Filter by category
        event_type_filter: Filter by event type
        channel_filter: Filter by channel ID
        date_from: Start date filter
        date_to: End date filter
        limit: Maximum results to return
        offset: Number of results to skip (for pagination)

    Returns:
        Tuple of (matching_logs, total_count)
    """
    data = _load_logs()
    guild_key = str(guild_id)

    if guild_key not in data or "logs" not in data[guild_key]:
        return [], 0

    logs = data[guild_key]["logs"]

    # Apply filters
    filtered = logs

    # User filter (matches user.id OR target.id)
    if user_filter:
        user_str = str(user_filter)
        filtered = [
            l for l in filtered
            if l.get("user", {}).get("id") == user_str or
               l.get("target", {}).get("id") == user_str
        ]

    # Category filter
    if category_filter:
        filtered = [l for l in filtered if l.get("category") == category_filter]

    # Event type filter
    if event_type_filter:
        filtered = [l for l in filtered if l.get("event_type") == event_type_filter]

    # Channel filter
    if channel_filter:
        channel_str = str(channel_filter)
        filtered = [l for l in filtered if l.get("channel", {}).get("id") == channel_str]

    # Date range filter
    if date_from:
        filtered = [
            l for l in filtered
            if datetime.fromisoformat(l["timestamp"]) >= date_from
        ]
    if date_to:
        filtered = [
            l for l in filtered
            if datetime.fromisoformat(l["timestamp"]) <= date_to
        ]

    # Text search in before/after/details/names
    if query:
        query_lower = query.lower()

        def matches_query(log):
            searchable = [
                log.get("before", ""),
                log.get("after", ""),
                log.get("user", {}).get("name", ""),
                log.get("user", {}).get("display_name", ""),
                log.get("target", {}).get("name", ""),
                log.get("channel", {}).get("name", ""),
                str(log.get("details", {}))
            ]
            return any(query_lower in str(s).lower() for s in searchable)

        filtered = [l for l in filtered if matches_query(l)]

    total_count = len(filtered)

    # Apply pagination
    paginated = filtered[offset:offset + limit]

    return paginated, total_count


def get_logs(
    guild_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[Dict]:
    """
    Get event logs for a guild (simple retrieval without search)

    Args:
        guild_id: The server ID
        limit: Maximum number of logs to return
        offset: Number of logs to skip

    Returns:
        List of log entries
    """
    logs, _ = search_logs(guild_id, limit=limit, offset=offset)
    return logs


def get_stats(guild_id: int) -> Dict:
    """
    Get event logging statistics for a guild

    Returns:
        Dictionary with category counts and total
    """
    data = _load_logs()
    guild_key = str(guild_id)

    if guild_key not in data:
        return {"categories": {}, "total": 0}

    guild_data = data[guild_key]

    return {
        "categories": guild_data.get("stats", {}),
        "total": len(guild_data.get("logs", []))
    }


def cleanup_old_logs(guild_id: int, days: int = 30) -> int:
    """
    Remove logs older than specified days

    Args:
        guild_id: The server ID
        days: Number of days to keep logs (default 30)

    Returns:
        Number of logs removed
    """
    data = _load_logs()
    guild_key = str(guild_id)

    if guild_key not in data or "logs" not in data[guild_key]:
        return 0

    cutoff = datetime.utcnow() - timedelta(days=days)
    original_count = len(data[guild_key]["logs"])

    # Filter out old logs
    data[guild_key]["logs"] = [
        log for log in data[guild_key]["logs"]
        if datetime.fromisoformat(log["timestamp"]) > cutoff
    ]

    removed = original_count - len(data[guild_key]["logs"])

    if removed > 0:
        _save_logs(data)
        update_last_cleanup(guild_id)
        logger.info(f"Cleaned up {removed} old event logs for guild {guild_id}")

    return removed


def clear_logs(guild_id: int) -> bool:
    """
    Clear all event logs for a guild

    Args:
        guild_id: The server ID

    Returns:
        True if cleared successfully
    """
    data = _load_logs()
    guild_key = str(guild_id)

    if guild_key in data:
        data[guild_key] = {"logs": [], "stats": {}, "total_logged": 0}
        return _save_logs(data)

    return True


def format_event_emoji(event_type: str) -> str:
    """Get an emoji for the event type"""
    emojis = {
        # Messages
        "message_edit": "\u270f\ufe0f",       # Pencil
        "message_delete": "\U0001f5d1\ufe0f", # Wastebasket
        "bulk_delete": "\U0001f5d1\ufe0f",    # Wastebasket

        # Members
        "member_join": "\U0001f44b",          # Waving hand
        "member_leave": "\U0001f6aa",         # Door
        "member_ban": "\U0001f528",           # Hammer
        "member_unban": "\u2705",             # Check mark
        "member_role_add": "\U0001f3f7\ufe0f",# Label
        "member_role_remove": "\U0001f3f7\ufe0f",
        "member_nickname_change": "\U0001f4dd", # Memo

        # Voice
        "voice_join": "\U0001f50a",           # Speaker high volume
        "voice_leave": "\U0001f507",          # Muted speaker
        "voice_move": "\u27a1\ufe0f",         # Right arrow
        "voice_mute": "\U0001f507",           # Muted speaker
        "voice_deafen": "\U0001f3a7",         # Headphones
        "voice_server_mute": "\U0001f507",
        "voice_server_deafen": "\U0001f3a7",

        # Server
        "channel_create": "\u2795",           # Plus
        "channel_delete": "\u2796",           # Minus
        "channel_update": "\U0001f527",       # Wrench
        "role_create": "\u2795",
        "role_delete": "\u2796",
        "role_update": "\U0001f527",

        # Moderation
        "timeout_add": "\u23f1\ufe0f",        # Stopwatch
        "timeout_remove": "\u23f1\ufe0f",
        "kick": "\U0001f462",                 # Boot
        "warn": "\u26a0\ufe0f",               # Warning

        # Commands
        "command_use": "\u2699\ufe0f"         # Gear
    }
    return emojis.get(event_type, "\U0001f4cb")  # Default: clipboard


def format_category_color(category: str) -> int:
    """Get a color for the category (as integer for Discord embed)"""
    colors = {
        "messages": 0xFFA500,    # Orange
        "members": 0x3498DB,     # Blue
        "moderation": 0xE74C3C,  # Red
        "voice": 0x9B59B6,       # Purple
        "server": 0x2ECC71,      # Green
        "commands": 0x00CED1    # Dark Cyan/Turquoise
    }
    return colors.get(category, 0x95A5A6)  # Default: Gray
