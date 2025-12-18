"""
Warnings Database
Stores and manages user warnings using a JSON file
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from utils.logger import logger


# Path to the warnings database file
DATA_DIR = Path(__file__).parent.parent / "data"
WARNINGS_FILE = DATA_DIR / "warnings.json"


def _ensure_data_dir():
    """Make sure the data directory exists"""
    DATA_DIR.mkdir(exist_ok=True)


def _load_warnings() -> Dict:
    """Load warnings from the JSON file"""
    _ensure_data_dir()

    if not WARNINGS_FILE.exists():
        return {}

    try:
        with open(WARNINGS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load warnings: {e}")
        return {}


def _save_warnings(data: Dict):
    """Save warnings to the JSON file"""
    _ensure_data_dir()

    try:
        with open(WARNINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save warnings: {e}")


def add_warning(
    guild_id: int,
    user_id: int,
    user_name: str,
    warning_type: str,
    reason: str,
    warned_by: str
) -> int:
    """
    Add a warning to a user and return the warning count in last 7 days.

    Args:
        guild_id: The Discord server ID
        user_id: The user's Discord ID
        user_name: The user's display name
        warning_type: Type of warning (Verbal, Serious, Shut up)
        reason: The reason for the warning
        warned_by: Who issued the warning

    Returns:
        The number of warnings this user has received in the last 7 days
    """
    data = _load_warnings()

    # Create guild entry if it doesn't exist
    guild_key = str(guild_id)
    if guild_key not in data:
        data[guild_key] = {}

    # Create user entry if it doesn't exist
    user_key = str(user_id)
    if user_key not in data[guild_key]:
        data[guild_key][user_key] = {
            "user_name": user_name,
            "warnings": []
        }

    # Update username (in case it changed)
    data[guild_key][user_key]["user_name"] = user_name

    # Add the new warning
    warning = {
        "type": warning_type,
        "reason": reason,
        "warned_by": warned_by,
        "timestamp": datetime.now().isoformat()
    }
    data[guild_key][user_key]["warnings"].append(warning)

    # Save the data
    _save_warnings(data)

    # Count warnings in the last 7 days
    return get_recent_warning_count(guild_id, user_id)


def get_recent_warning_count(guild_id: int, user_id: int, days: int = 7) -> int:
    """
    Get the number of warnings a user has received in the last N days.

    Args:
        guild_id: The Discord server ID
        user_id: The user's Discord ID
        days: Number of days to look back (default: 7)

    Returns:
        Number of warnings in the specified period
    """
    data = _load_warnings()

    guild_key = str(guild_id)
    user_key = str(user_id)

    if guild_key not in data or user_key not in data[guild_key]:
        return 0

    warnings = data[guild_key][user_key].get("warnings", [])
    cutoff = datetime.now() - timedelta(days=days)

    count = 0
    for warning in warnings:
        try:
            warning_time = datetime.fromisoformat(warning["timestamp"])
            if warning_time > cutoff:
                count += 1
        except Exception:
            pass

    return count


def get_user_warnings(guild_id: int, user_id: int) -> List[Dict]:
    """
    Get all warnings for a user.

    Args:
        guild_id: The Discord server ID
        user_id: The user's Discord ID

    Returns:
        List of warning dictionaries
    """
    data = _load_warnings()

    guild_key = str(guild_id)
    user_key = str(user_id)

    if guild_key not in data or user_key not in data[guild_key]:
        return []

    return data[guild_key][user_key].get("warnings", [])
