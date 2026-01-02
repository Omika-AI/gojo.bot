"""
Moderation Logs Utility
Handles saving and loading moderation action logs to/from JSON file
"""

import json
import os
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

from utils.logger import logger

# Path to the moderation logs data file
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
MOD_LOGS_FILE = os.path.join(DATA_DIR, "moderation_logs.json")


class ModAction(Enum):
    """Types of moderation actions"""
    WARN = "warn"
    TIMEOUT = "timeout"
    KICK = "kick"
    BAN = "ban"
    UNBAN = "unban"
    UNMUTE = "unmute"
    CLEAR = "clear"
    SLOWMODE = "slowmode"
    LOCK = "lock"
    UNLOCK = "unlock"
    MODTALK = "modtalk"
    OTHER = "other"


def _ensure_data_dir():
    """Make sure the data directory exists"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def _load_logs() -> Dict:
    """Load moderation logs from file"""
    _ensure_data_dir()

    if not os.path.exists(MOD_LOGS_FILE):
        return {}

    try:
        with open(MOD_LOGS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load moderation logs: {e}")
        return {}


def _save_logs(data: Dict) -> bool:
    """Save moderation logs to file"""
    _ensure_data_dir()

    try:
        with open(MOD_LOGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Failed to save moderation logs: {e}")
        return False


def log_action(
    guild_id: int,
    moderator_id: int,
    moderator_name: str,
    action: ModAction,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    reason: Optional[str] = None,
    details: Optional[Dict] = None
) -> bool:
    """
    Log a moderation action

    Args:
        guild_id: The server ID
        moderator_id: The moderator's user ID
        moderator_name: The moderator's display name
        action: The type of moderation action
        target_id: The target user's ID (if applicable)
        target_name: The target user's name (if applicable)
        reason: The reason for the action (if provided)
        details: Additional details about the action

    Returns:
        True if logged successfully, False otherwise
    """
    data = _load_logs()

    guild_key = str(guild_id)

    # Initialize guild logs if needed
    if guild_key not in data:
        data[guild_key] = {"logs": [], "stats": {}}

    # Create the log entry
    log_entry = {
        "id": len(data[guild_key]["logs"]) + 1,
        "timestamp": datetime.utcnow().isoformat(),
        "action": action.value,
        "moderator": {
            "id": str(moderator_id),
            "name": moderator_name
        }
    }

    # Add target info if provided
    if target_id is not None:
        log_entry["target"] = {
            "id": str(target_id),
            "name": target_name or "Unknown"
        }

    # Add reason if provided
    if reason:
        log_entry["reason"] = reason

    # Add extra details if provided
    if details:
        log_entry["details"] = details

    # Add to logs (newest first)
    data[guild_key]["logs"].insert(0, log_entry)

    # Update stats
    if "stats" not in data[guild_key]:
        data[guild_key]["stats"] = {}

    action_key = action.value
    if action_key not in data[guild_key]["stats"]:
        data[guild_key]["stats"][action_key] = 0
    data[guild_key]["stats"][action_key] += 1

    # Update moderator stats
    if "moderator_stats" not in data[guild_key]:
        data[guild_key]["moderator_stats"] = {}

    mod_key = str(moderator_id)
    if mod_key not in data[guild_key]["moderator_stats"]:
        data[guild_key]["moderator_stats"][mod_key] = {
            "name": moderator_name,
            "total": 0,
            "actions": {}
        }

    data[guild_key]["moderator_stats"][mod_key]["total"] += 1
    data[guild_key]["moderator_stats"][mod_key]["name"] = moderator_name  # Update name

    if action_key not in data[guild_key]["moderator_stats"][mod_key]["actions"]:
        data[guild_key]["moderator_stats"][mod_key]["actions"][action_key] = 0
    data[guild_key]["moderator_stats"][mod_key]["actions"][action_key] += 1

    # Keep only last 1000 logs per guild to prevent file bloat
    if len(data[guild_key]["logs"]) > 1000:
        data[guild_key]["logs"] = data[guild_key]["logs"][:1000]

    return _save_logs(data)


def get_logs(
    guild_id: int,
    limit: int = 50,
    offset: int = 0,
    action_filter: Optional[ModAction] = None,
    moderator_filter: Optional[int] = None,
    target_filter: Optional[int] = None
) -> List[Dict]:
    """
    Get moderation logs for a guild

    Args:
        guild_id: The server ID
        limit: Maximum number of logs to return
        offset: Number of logs to skip (for pagination)
        action_filter: Filter by action type
        moderator_filter: Filter by moderator ID
        target_filter: Filter by target user ID

    Returns:
        List of log entries
    """
    data = _load_logs()
    guild_key = str(guild_id)

    if guild_key not in data or "logs" not in data[guild_key]:
        return []

    logs = data[guild_key]["logs"]

    # Apply filters
    if action_filter:
        logs = [l for l in logs if l.get("action") == action_filter.value]

    if moderator_filter:
        logs = [l for l in logs if l.get("moderator", {}).get("id") == str(moderator_filter)]

    if target_filter:
        logs = [l for l in logs if l.get("target", {}).get("id") == str(target_filter)]

    # Apply pagination
    return logs[offset:offset + limit]


def get_total_logs(
    guild_id: int,
    action_filter: Optional[ModAction] = None,
    moderator_filter: Optional[int] = None,
    target_filter: Optional[int] = None
) -> int:
    """
    Get total count of logs (for pagination)
    """
    data = _load_logs()
    guild_key = str(guild_id)

    if guild_key not in data or "logs" not in data[guild_key]:
        return 0

    logs = data[guild_key]["logs"]

    # Apply filters
    if action_filter:
        logs = [l for l in logs if l.get("action") == action_filter.value]

    if moderator_filter:
        logs = [l for l in logs if l.get("moderator", {}).get("id") == str(moderator_filter)]

    if target_filter:
        logs = [l for l in logs if l.get("target", {}).get("id") == str(target_filter)]

    return len(logs)


def get_stats(guild_id: int) -> Dict:
    """
    Get moderation statistics for a guild

    Returns:
        Dictionary with action counts and moderator stats
    """
    data = _load_logs()
    guild_key = str(guild_id)

    if guild_key not in data:
        return {"actions": {}, "moderators": {}, "total": 0}

    guild_data = data[guild_key]

    return {
        "actions": guild_data.get("stats", {}),
        "moderators": guild_data.get("moderator_stats", {}),
        "total": len(guild_data.get("logs", []))
    }


def get_user_history(guild_id: int, user_id: int, limit: int = 20) -> List[Dict]:
    """
    Get moderation history for a specific user (as target)

    Args:
        guild_id: The server ID
        user_id: The user ID to get history for
        limit: Maximum number of entries

    Returns:
        List of log entries where user was the target
    """
    return get_logs(guild_id, limit=limit, target_filter=user_id)


def get_moderator_activity(guild_id: int, moderator_id: int, limit: int = 20) -> List[Dict]:
    """
    Get activity log for a specific moderator

    Args:
        guild_id: The server ID
        moderator_id: The moderator ID to get activity for
        limit: Maximum number of entries

    Returns:
        List of log entries for the moderator
    """
    return get_logs(guild_id, limit=limit, moderator_filter=moderator_id)


def clear_logs(guild_id: int) -> bool:
    """
    Clear all moderation logs for a guild (Admin only feature)

    Args:
        guild_id: The server ID

    Returns:
        True if cleared successfully
    """
    data = _load_logs()
    guild_key = str(guild_id)

    if guild_key in data:
        data[guild_key] = {"logs": [], "stats": {}, "moderator_stats": {}}
        return _save_logs(data)

    return True


def format_action_emoji(action: str) -> str:
    """Get an emoji for the action type"""
    emojis = {
        "warn": "\u26a0\ufe0f",      # Warning sign
        "timeout": "\u23f1\ufe0f",   # Stopwatch
        "kick": "\U0001f462",        # Boot
        "ban": "\U0001f528",         # Hammer
        "unban": "\u2705",           # Check mark
        "unmute": "\U0001f508",      # Speaker
        "clear": "\U0001f9f9",       # Broom
        "slowmode": "\U0001f422",    # Turtle
        "lock": "\U0001f512",        # Lock
        "unlock": "\U0001f513",      # Unlock
        "modtalk": "\U0001f4e2",     # Loudspeaker
        "other": "\U0001f527"        # Wrench
    }
    return emojis.get(action, "\U0001f4cb")  # Default: clipboard
