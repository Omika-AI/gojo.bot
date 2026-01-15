"""
Leveling Database - Manages user XP, levels, and progression

This module handles:
- XP storage and retrieval per user per guild
- Level calculations based on XP
- XP rewards for messages and voice activity
- Milestone rewards (bonus coins at certain levels)
"""

import os
import json
import math
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List

# File path for storing leveling data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
LEVELING_FILE = os.path.join(DATA_DIR, 'leveling.json')

# ============================================
# XP CONFIGURATION
# ============================================

# XP earned per message (randomized between min and max)
MESSAGE_XP_MIN = 15
MESSAGE_XP_MAX = 25

# XP earned per minute in voice channel
VOICE_XP_PER_MINUTE = 10

# Cooldown between earning XP from messages (in seconds)
# This prevents spam-farming XP
MESSAGE_XP_COOLDOWN = 60  # 1 minute

# Level calculation formula: XP needed = base * (level ^ exponent)
# Level 1: 100 XP, Level 2: 255 XP, Level 10: 6310 XP, etc.
XP_BASE = 100
XP_EXPONENT = 1.8

# ============================================
# MILESTONE REWARDS (Level -> Coin Bonus)
# ============================================

MILESTONE_REWARDS = {
    5: 1000,      # Level 5: 1,000 coins
    10: 5000,     # Level 10: 5,000 coins
    15: 7500,     # Level 15: 7,500 coins
    20: 10000,    # Level 20: 10,000 coins
    25: 15000,    # Level 25: 15,000 coins
    30: 20000,    # Level 30: 20,000 coins
    40: 30000,    # Level 40: 30,000 coins
    50: 50000,    # Level 50: 50,000 coins
    75: 75000,    # Level 75: 75,000 coins
    100: 100000,  # Level 100: 100,000 coins
}


# ============================================
# DATA PERSISTENCE FUNCTIONS
# ============================================

def _load_leveling_data() -> dict:
    """Load leveling data from JSON file"""
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(LEVELING_FILE):
        try:
            with open(LEVELING_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Return default structure if file doesn't exist or is corrupted
    return {"guilds": {}}


def _save_leveling_data(data: dict):
    """Save leveling data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LEVELING_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _get_user_data(guild_id: int, user_id: int) -> dict:
    """Get user's leveling data, creating default if doesn't exist"""
    data = _load_leveling_data()
    guild_str = str(guild_id)
    user_str = str(user_id)

    # Initialize guild if needed
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"users": {}}

    # Initialize user if needed
    if user_str not in data["guilds"][guild_str]["users"]:
        data["guilds"][guild_str]["users"][user_str] = {
            "xp": 0,
            "level": 0,
            "total_xp": 0,
            "messages": 0,
            "voice_minutes": 0,
            "last_xp_time": None,
            "claimed_milestones": []
        }
        _save_leveling_data(data)

    return data["guilds"][guild_str]["users"][user_str]


# ============================================
# LEVEL CALCULATION FUNCTIONS
# ============================================

def xp_for_level(level: int) -> int:
    """Calculate total XP needed to reach a specific level"""
    if level <= 0:
        return 0
    return int(XP_BASE * (level ** XP_EXPONENT))


def level_from_xp(total_xp: int) -> int:
    """Calculate level from total XP"""
    if total_xp <= 0:
        return 0
    # Solve: total_xp = base * (level ^ exponent)
    # level = (total_xp / base) ^ (1/exponent)
    level = int((total_xp / XP_BASE) ** (1 / XP_EXPONENT))

    # Verify and adjust (due to floating point)
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    while level > 0 and xp_for_level(level) > total_xp:
        level -= 1

    return level


def xp_progress_in_level(total_xp: int) -> Tuple[int, int, float]:
    """
    Get XP progress within current level

    Returns:
        (current_xp_in_level, xp_needed_for_next_level, percentage)
    """
    level = level_from_xp(total_xp)
    xp_for_current = xp_for_level(level)
    xp_for_next = xp_for_level(level + 1)

    current_progress = total_xp - xp_for_current
    xp_needed = xp_for_next - xp_for_current

    percentage = (current_progress / xp_needed * 100) if xp_needed > 0 else 100

    return current_progress, xp_needed, percentage


# ============================================
# XP MANAGEMENT FUNCTIONS
# ============================================

def get_user_level_data(guild_id: int, user_id: int) -> dict:
    """
    Get complete level data for a user

    Returns dict with:
        - xp: current XP in level
        - level: current level
        - total_xp: all-time XP
        - xp_needed: XP needed for next level
        - progress: percentage to next level
        - messages: total messages counted
        - voice_minutes: total voice minutes
        - rank: position in guild leaderboard
    """
    user_data = _get_user_data(guild_id, user_id)
    total_xp = user_data["total_xp"]
    level = level_from_xp(total_xp)
    current_xp, xp_needed, progress = xp_progress_in_level(total_xp)

    # Get rank in guild
    rank = get_user_rank(guild_id, user_id)

    return {
        "xp": current_xp,
        "level": level,
        "total_xp": total_xp,
        "xp_needed": xp_needed,
        "progress": progress,
        "messages": user_data["messages"],
        "voice_minutes": user_data["voice_minutes"],
        "rank": rank
    }


def add_message_xp(guild_id: int, user_id: int) -> Tuple[bool, int, Optional[int], Optional[int]]:
    """
    Add XP for sending a message (with cooldown)

    Returns:
        (xp_added: bool, xp_amount: int, new_level: Optional[int], coin_reward: Optional[int])
        - xp_added: True if XP was added (not on cooldown)
        - xp_amount: Amount of XP added (0 if on cooldown)
        - new_level: New level if leveled up, None otherwise
        - coin_reward: Milestone coin reward if applicable
    """
    import random

    data = _load_leveling_data()
    guild_str = str(guild_id)
    user_str = str(user_id)

    # Initialize structures if needed
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"users": {}}
    if user_str not in data["guilds"][guild_str]["users"]:
        data["guilds"][guild_str]["users"][user_str] = {
            "xp": 0,
            "level": 0,
            "total_xp": 0,
            "messages": 0,
            "voice_minutes": 0,
            "last_xp_time": None,
            "claimed_milestones": []
        }

    user_data = data["guilds"][guild_str]["users"][user_str]
    now = datetime.now()

    # Always increment message counter
    user_data["messages"] += 1

    # Check cooldown
    if user_data["last_xp_time"]:
        last_time = datetime.fromisoformat(user_data["last_xp_time"])
        if (now - last_time).total_seconds() < MESSAGE_XP_COOLDOWN:
            _save_leveling_data(data)
            return False, 0, None, None

    # Calculate XP to add
    xp_amount = random.randint(MESSAGE_XP_MIN, MESSAGE_XP_MAX)

    # Check for XP boost from shop
    try:
        from utils.shop_db import has_active_xp_boost
        has_boost, multiplier = has_active_xp_boost(guild_id, user_id)
        if has_boost:
            xp_amount = int(xp_amount * multiplier)
    except:
        pass  # Shop module not available, no boost

    old_level = level_from_xp(user_data["total_xp"])

    # Add XP
    user_data["total_xp"] += xp_amount
    user_data["last_xp_time"] = now.isoformat()

    # Check for level up
    new_level = level_from_xp(user_data["total_xp"])
    leveled_up = new_level > old_level

    # Check for milestone rewards
    coin_reward = None
    if leveled_up:
        user_data["level"] = new_level
        for milestone_level, reward in MILESTONE_REWARDS.items():
            if old_level < milestone_level <= new_level:
                if milestone_level not in user_data.get("claimed_milestones", []):
                    coin_reward = reward
                    if "claimed_milestones" not in user_data:
                        user_data["claimed_milestones"] = []
                    user_data["claimed_milestones"].append(milestone_level)
                    break

    _save_leveling_data(data)

    return True, xp_amount, new_level if leveled_up else None, coin_reward


def add_voice_xp(guild_id: int, user_id: int, minutes: int = 1) -> Tuple[int, Optional[int], Optional[int]]:
    """
    Add XP for time spent in voice channel

    Args:
        guild_id: The guild ID
        user_id: The user ID
        minutes: Number of minutes to add XP for

    Returns:
        (xp_amount, new_level if leveled up else None, coin_reward if milestone else None)
    """
    data = _load_leveling_data()
    guild_str = str(guild_id)
    user_str = str(user_id)

    # Calculate XP with potential boost
    xp_amount = VOICE_XP_PER_MINUTE * minutes

    # Check for XP boost from shop
    try:
        from utils.shop_db import has_active_xp_boost
        has_boost, multiplier = has_active_xp_boost(guild_id, user_id)
        if has_boost:
            xp_amount = int(xp_amount * multiplier)
    except:
        pass  # Shop module not available, no boost

    # Initialize structures if needed
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"users": {}}
    if user_str not in data["guilds"][guild_str]["users"]:
        data["guilds"][guild_str]["users"][user_str] = {
            "xp": 0,
            "level": 0,
            "total_xp": 0,
            "messages": 0,
            "voice_minutes": 0,
            "last_xp_time": None,
            "claimed_milestones": []
        }

    user_data = data["guilds"][guild_str]["users"][user_str]

    # XP already calculated above with boost applied
    old_level = level_from_xp(user_data["total_xp"])

    # Add XP and track voice minutes
    user_data["total_xp"] += xp_amount
    user_data["voice_minutes"] += minutes

    # Check for level up
    new_level = level_from_xp(user_data["total_xp"])
    leveled_up = new_level > old_level

    # Check for milestone rewards
    coin_reward = None
    if leveled_up:
        user_data["level"] = new_level
        for milestone_level, reward in MILESTONE_REWARDS.items():
            if old_level < milestone_level <= new_level:
                if milestone_level not in user_data.get("claimed_milestones", []):
                    coin_reward = reward
                    if "claimed_milestones" not in user_data:
                        user_data["claimed_milestones"] = []
                    user_data["claimed_milestones"].append(milestone_level)
                    break

    _save_leveling_data(data)

    return xp_amount, new_level if leveled_up else None, coin_reward


def get_user_rank(guild_id: int, user_id: int) -> int:
    """Get user's rank in the guild leaderboard (1-based)"""
    data = _load_leveling_data()
    guild_str = str(guild_id)
    user_str = str(user_id)

    if guild_str not in data["guilds"]:
        return 1

    users = data["guilds"][guild_str].get("users", {})
    if not users:
        return 1

    # Sort users by total_xp descending
    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1].get("total_xp", 0),
        reverse=True
    )

    # Find user's position
    for i, (uid, _) in enumerate(sorted_users):
        if uid == user_str:
            return i + 1

    return len(sorted_users) + 1


def get_xp_leaderboard(guild_id: int, limit: int = 10) -> List[Tuple[str, int, int]]:
    """
    Get the XP leaderboard for a guild

    Returns:
        List of (user_id, level, total_xp) tuples sorted by XP
    """
    data = _load_leveling_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return []

    users = data["guilds"][guild_str].get("users", {})
    if not users:
        return []

    # Sort by total_xp descending
    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1].get("total_xp", 0),
        reverse=True
    )[:limit]

    result = []
    for user_id, user_data in sorted_users:
        total_xp = user_data.get("total_xp", 0)
        level = level_from_xp(total_xp)
        result.append((user_id, level, total_xp))

    return result


def get_guild_user_count(guild_id: int) -> int:
    """Get the number of users with XP data in a guild"""
    data = _load_leveling_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return 0

    return len(data["guilds"][guild_str].get("users", {}))
