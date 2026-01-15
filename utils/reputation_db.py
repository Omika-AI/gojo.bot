"""
Reputation Database - Manages user reputation points

This module handles:
- Rep points storage per user per guild
- Daily rep giving limit (one per day per user)
- Tracking who gave rep to whom
- Rep leaderboard
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict

# File path for storing reputation data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
REPUTATION_FILE = os.path.join(DATA_DIR, 'reputation.json')


# ============================================
# DATA PERSISTENCE FUNCTIONS
# ============================================

def _load_reputation_data() -> dict:
    """Load reputation data from JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(REPUTATION_FILE):
        try:
            with open(REPUTATION_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Return default structure if file doesn't exist or is corrupted
    return {"guilds": {}}


def _save_reputation_data(data: dict):
    """Save reputation data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPUTATION_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _get_user_data(guild_id: int, user_id: int) -> dict:
    """Get user's reputation data, creating default if doesn't exist"""
    data = _load_reputation_data()
    guild_str = str(guild_id)
    user_str = str(user_id)

    # Initialize guild if needed
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"users": {}}

    # Initialize user if needed
    if user_str not in data["guilds"][guild_str]["users"]:
        data["guilds"][guild_str]["users"][user_str] = {
            "rep_points": 0,
            "rep_received_from": [],  # List of {user_id, timestamp}
            "last_rep_given": None,   # Timestamp of last rep given
            "total_rep_given": 0
        }
        _save_reputation_data(data)

    return data["guilds"][guild_str]["users"][user_str]


# ============================================
# REPUTATION FUNCTIONS
# ============================================

def get_rep_points(guild_id: int, user_id: int) -> int:
    """Get user's total reputation points"""
    user_data = _get_user_data(guild_id, user_id)
    return user_data["rep_points"]


def get_rep_stats(guild_id: int, user_id: int) -> dict:
    """
    Get complete reputation stats for a user

    Returns dict with:
        - rep_points: Total rep received
        - total_rep_given: Total rep given to others
        - can_give_rep: Whether user can give rep today
        - next_rep_available: When they can give rep again (if on cooldown)
    """
    user_data = _get_user_data(guild_id, user_id)

    can_give = True
    next_available = None

    if user_data["last_rep_given"]:
        last_given = datetime.fromisoformat(user_data["last_rep_given"])
        # Rep resets at midnight (24 hour cooldown)
        next_available = last_given + timedelta(hours=24)
        if datetime.now() < next_available:
            can_give = False

    return {
        "rep_points": user_data["rep_points"],
        "total_rep_given": user_data["total_rep_given"],
        "can_give_rep": can_give,
        "next_rep_available": next_available
    }


def give_rep(guild_id: int, giver_id: int, receiver_id: int) -> Tuple[bool, str, int]:
    """
    Give a reputation point to another user

    Args:
        guild_id: The guild ID
        giver_id: The user giving rep
        receiver_id: The user receiving rep

    Returns:
        (success: bool, message: str, new_rep_total: int)
    """
    # Can't give rep to yourself
    if giver_id == receiver_id:
        return False, "You can't give rep to yourself!", 0

    data = _load_reputation_data()
    guild_str = str(guild_id)
    giver_str = str(giver_id)
    receiver_str = str(receiver_id)

    # Initialize guild if needed
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"users": {}}

    # Initialize giver if needed
    if giver_str not in data["guilds"][guild_str]["users"]:
        data["guilds"][guild_str]["users"][giver_str] = {
            "rep_points": 0,
            "rep_received_from": [],
            "last_rep_given": None,
            "total_rep_given": 0
        }

    # Initialize receiver if needed
    if receiver_str not in data["guilds"][guild_str]["users"]:
        data["guilds"][guild_str]["users"][receiver_str] = {
            "rep_points": 0,
            "rep_received_from": [],
            "last_rep_given": None,
            "total_rep_given": 0
        }

    giver_data = data["guilds"][guild_str]["users"][giver_str]
    receiver_data = data["guilds"][guild_str]["users"][receiver_str]

    now = datetime.now()

    # Check if giver can give rep (24 hour cooldown)
    if giver_data["last_rep_given"]:
        last_given = datetime.fromisoformat(giver_data["last_rep_given"])
        time_since = now - last_given

        if time_since < timedelta(hours=24):
            # Calculate time remaining
            time_remaining = timedelta(hours=24) - time_since
            hours = int(time_remaining.total_seconds() // 3600)
            minutes = int((time_remaining.total_seconds() % 3600) // 60)

            if hours > 0:
                time_str = f"{hours}h {minutes}m"
            else:
                time_str = f"{minutes}m"

            return False, f"You can give rep again in **{time_str}**", 0

    # Give the rep!
    receiver_data["rep_points"] += 1
    receiver_data["rep_received_from"].append({
        "user_id": giver_str,
        "timestamp": now.isoformat()
    })

    # Update giver stats
    giver_data["last_rep_given"] = now.isoformat()
    giver_data["total_rep_given"] += 1

    _save_reputation_data(data)

    return True, "Rep given successfully!", receiver_data["rep_points"]


def get_rep_leaderboard(guild_id: int, limit: int = 10) -> List[Tuple[str, int]]:
    """
    Get the reputation leaderboard for a guild

    Returns:
        List of (user_id, rep_points) tuples sorted by rep
    """
    data = _load_reputation_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return []

    users = data["guilds"][guild_str].get("users", {})
    if not users:
        return []

    # Sort by rep_points descending
    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1].get("rep_points", 0),
        reverse=True
    )[:limit]

    return [(user_id, user_data.get("rep_points", 0)) for user_id, user_data in sorted_users]


def get_user_rep_rank(guild_id: int, user_id: int) -> int:
    """Get user's rank in the reputation leaderboard (1-based)"""
    data = _load_reputation_data()
    guild_str = str(guild_id)
    user_str = str(user_id)

    if guild_str not in data["guilds"]:
        return 1

    users = data["guilds"][guild_str].get("users", {})
    if not users:
        return 1

    # Sort users by rep_points descending
    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1].get("rep_points", 0),
        reverse=True
    )

    # Find user's position
    for i, (uid, _) in enumerate(sorted_users):
        if uid == user_str:
            return i + 1

    return len(sorted_users) + 1


def get_recent_rep_givers(guild_id: int, user_id: int, limit: int = 5) -> List[Dict]:
    """
    Get the most recent users who gave rep to this user

    Returns:
        List of {user_id, timestamp} dicts
    """
    user_data = _get_user_data(guild_id, user_id)
    rep_received = user_data.get("rep_received_from", [])

    # Return most recent first
    return sorted(
        rep_received,
        key=lambda x: x.get("timestamp", ""),
        reverse=True
    )[:limit]
