"""
Daily Quests Database - Manages daily quests and quest keys

This module handles:
- Daily quest generation and tracking
- Quest progress for each user
- Quest key rewards
- Quest reset at midnight UTC
"""

import os
import json
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

# File path for storing quest data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
QUESTS_FILE = os.path.join(DATA_DIR, 'quests.json')

# ============================================
# QUEST DEFINITIONS
# ============================================
# Each quest has:
# - id: unique identifier
# - name: display name
# - description: what the user needs to do
# - target: how many times to complete
# - track_type: what metric to track
# - reward_coins: bonus coins for this quest

QUEST_POOL = [
    # Gambling Quests
    {
        "id": "blackjack_games",
        "name": "Card Shark",
        "description": "Play {target} rounds of Blackjack",
        "target": 3,
        "track_type": "blackjack_games",
        "reward_coins": 100
    },
    {
        "id": "blackjack_wins",
        "name": "Lucky Hands",
        "description": "Win {target} games of Blackjack",
        "target": 2,
        "track_type": "blackjack_wins",
        "reward_coins": 200
    },
    {
        "id": "roulette_games",
        "name": "Spin Master",
        "description": "Play {target} rounds of Roulette",
        "target": 5,
        "track_type": "roulette_games",
        "reward_coins": 100
    },
    {
        "id": "roulette_wins",
        "name": "Fortune's Favorite",
        "description": "Win {target} roulette bets",
        "target": 3,
        "track_type": "roulette_wins",
        "reward_coins": 150
    },
    {
        "id": "coinflip_games",
        "name": "Coin Collector",
        "description": "Play {target} coinflip duels",
        "target": 3,
        "track_type": "coinflip_games",
        "reward_coins": 100
    },
    {
        "id": "gambling_total",
        "name": "High Roller",
        "description": "Bet a total of {target} coins today",
        "target": 1000,
        "track_type": "coins_bet",
        "reward_coins": 250
    },

    # Music Quests
    {
        "id": "music_minutes",
        "name": "Music Lover",
        "description": "Listen to {target} minutes of music",
        "target": 30,
        "track_type": "music_minutes",
        "reward_coins": 150
    },
    {
        "id": "songs_played",
        "name": "DJ Life",
        "description": "Play {target} songs",
        "target": 5,
        "track_type": "songs_played",
        "reward_coins": 100
    },
    {
        "id": "karaoke_songs",
        "name": "Karaoke Star",
        "description": "Sing {target} karaoke songs",
        "target": 2,
        "track_type": "karaoke_songs",
        "reward_coins": 200
    },

    # Social Quests
    {
        "id": "give_coins",
        "name": "Generous Soul",
        "description": "Give {target} coins to friends",
        "target": 500,
        "track_type": "coins_given",
        "reward_coins": 100
    },
    {
        "id": "give_rep",
        "name": "Reputation Builder",
        "description": "Give reputation to {target} member",
        "target": 1,
        "track_type": "rep_given",
        "reward_coins": 50
    },
    {
        "id": "messages_sent",
        "name": "Chatterbox",
        "description": "Send {target} messages",
        "target": 50,
        "track_type": "messages_sent",
        "reward_coins": 100
    },

    # Voice Quests
    {
        "id": "voice_minutes",
        "name": "Voice Champion",
        "description": "Spend {target} minutes in voice channels",
        "target": 30,
        "track_type": "voice_minutes",
        "reward_coins": 150
    },

    # Economy Quests
    {
        "id": "claim_daily",
        "name": "Daily Devotion",
        "description": "Claim your daily coins",
        "target": 1,
        "track_type": "daily_claimed",
        "reward_coins": 50
    },
    {
        "id": "check_balance",
        "name": "Accountant",
        "description": "Check your balance {target} times",
        "target": 3,
        "track_type": "balance_checks",
        "reward_coins": 25
    },

    # XP Quests
    {
        "id": "earn_xp",
        "name": "XP Hunter",
        "description": "Earn {target} XP today",
        "target": 200,
        "track_type": "xp_earned",
        "reward_coins": 150
    },
]

# Number of quests per day
DAILY_QUEST_COUNT = 3


# ============================================
# DATA PERSISTENCE FUNCTIONS
# ============================================

def _load_quests_data() -> dict:
    """Load quests data from JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(QUESTS_FILE):
        try:
            with open(QUESTS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return {"guilds": {}}


def _save_quests_data(data: dict):
    """Save quests data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(QUESTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _get_today_key() -> str:
    """Get today's date key for quest tracking (UTC)"""
    return datetime.utcnow().strftime("%Y-%m-%d")


def _get_user_data(guild_id: int, user_id: int) -> dict:
    """Get user's quest data for today, initializing if needed"""
    data = _load_quests_data()
    guild_str = str(guild_id)
    user_str = str(user_id)
    today = _get_today_key()

    # Initialize guild if needed
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"users": {}}

    # Initialize user if needed
    if user_str not in data["guilds"][guild_str]["users"]:
        data["guilds"][guild_str]["users"][user_str] = {
            "quest_keys": 0,
            "total_quests_completed": 0,
            "total_lootboxes_opened": 0,
            "daily_data": {}
        }

    user_data = data["guilds"][guild_str]["users"][user_str]

    # Check if we need to generate new daily quests
    if "daily_data" not in user_data:
        user_data["daily_data"] = {}

    if today not in user_data["daily_data"]:
        # Generate new daily quests
        user_data["daily_data"][today] = _generate_daily_quests()
        _save_quests_data(data)

    return user_data


def _generate_daily_quests() -> dict:
    """Generate a new set of daily quests"""
    # Select random quests from the pool
    selected_quests = random.sample(QUEST_POOL, min(DAILY_QUEST_COUNT, len(QUEST_POOL)))

    quests = {}
    for quest in selected_quests:
        quests[quest["id"]] = {
            "quest": quest,
            "progress": 0,
            "completed": False,
            "claimed": False
        }

    return {
        "quests": quests,
        "all_completed": False,
        "key_claimed": False
    }


# ============================================
# QUEST MANAGEMENT FUNCTIONS
# ============================================

def get_daily_quests(guild_id: int, user_id: int) -> List[Dict]:
    """
    Get the user's daily quests with their progress

    Returns list of dicts with:
    - quest: the quest definition
    - progress: current progress
    - completed: whether it's done
    - claimed: whether reward was claimed
    """
    user_data = _get_user_data(guild_id, user_id)
    today = _get_today_key()

    daily = user_data["daily_data"].get(today, {})
    quests = daily.get("quests", {})

    result = []
    for quest_id, quest_data in quests.items():
        result.append({
            "id": quest_id,
            "quest": quest_data["quest"],
            "progress": quest_data["progress"],
            "completed": quest_data["completed"],
            "claimed": quest_data["claimed"]
        })

    return result


def update_quest_progress(guild_id: int, user_id: int, track_type: str, amount: int = 1) -> List[Dict]:
    """
    Update progress for quests that track this type

    Args:
        guild_id: The guild ID
        user_id: The user ID
        track_type: The type of action (e.g., "blackjack_games", "music_minutes")
        amount: Amount to add (default 1)

    Returns:
        List of quests that were just completed (empty if none)
    """
    data = _load_quests_data()
    guild_str = str(guild_id)
    user_str = str(user_id)
    today = _get_today_key()

    # Initialize if needed
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"users": {}}
    if user_str not in data["guilds"][guild_str]["users"]:
        # Initialize user data which also generates quests
        _get_user_data(guild_id, user_id)
        data = _load_quests_data()

    user_data = data["guilds"][guild_str]["users"].get(user_str)
    if not user_data:
        return []

    daily = user_data.get("daily_data", {}).get(today)
    if not daily:
        return []

    newly_completed = []
    quests = daily.get("quests", {})

    for quest_id, quest_data in quests.items():
        quest = quest_data["quest"]

        # Check if this quest tracks this type
        if quest["track_type"] == track_type and not quest_data["completed"]:
            quest_data["progress"] += amount

            # Check if quest is now complete
            if quest_data["progress"] >= quest["target"]:
                quest_data["progress"] = quest["target"]  # Cap at target
                quest_data["completed"] = True
                newly_completed.append({
                    "id": quest_id,
                    "quest": quest,
                    "progress": quest_data["progress"]
                })

    _save_quests_data(data)
    return newly_completed


def claim_quest_reward(guild_id: int, user_id: int, quest_id: str) -> Tuple[bool, int]:
    """
    Claim the reward for a completed quest

    Returns:
        (success: bool, coins_reward: int)
    """
    data = _load_quests_data()
    guild_str = str(guild_id)
    user_str = str(user_id)
    today = _get_today_key()

    user_data = data["guilds"].get(guild_str, {}).get("users", {}).get(user_str)
    if not user_data:
        return False, 0

    daily = user_data.get("daily_data", {}).get(today)
    if not daily:
        return False, 0

    quest_data = daily.get("quests", {}).get(quest_id)
    if not quest_data:
        return False, 0

    # Check if completed and not claimed
    if not quest_data["completed"] or quest_data["claimed"]:
        return False, 0

    # Mark as claimed and increment counter
    quest_data["claimed"] = True
    user_data["total_quests_completed"] = user_data.get("total_quests_completed", 0) + 1

    coins = quest_data["quest"]["reward_coins"]

    _save_quests_data(data)
    return True, coins


def check_all_quests_completed(guild_id: int, user_id: int) -> Tuple[bool, bool]:
    """
    Check if all daily quests are completed

    Returns:
        (all_completed: bool, key_already_claimed: bool)
    """
    data = _load_quests_data()
    guild_str = str(guild_id)
    user_str = str(user_id)
    today = _get_today_key()

    user_data = data["guilds"].get(guild_str, {}).get("users", {}).get(user_str)
    if not user_data:
        return False, False

    daily = user_data.get("daily_data", {}).get(today)
    if not daily:
        return False, False

    quests = daily.get("quests", {})
    all_done = all(q["completed"] for q in quests.values())
    key_claimed = daily.get("key_claimed", False)

    return all_done, key_claimed


def claim_quest_key(guild_id: int, user_id: int) -> Tuple[bool, int]:
    """
    Claim a quest key for completing all daily quests

    Returns:
        (success: bool, total_keys: int)
    """
    data = _load_quests_data()
    guild_str = str(guild_id)
    user_str = str(user_id)
    today = _get_today_key()

    user_data = data["guilds"].get(guild_str, {}).get("users", {}).get(user_str)
    if not user_data:
        return False, 0

    daily = user_data.get("daily_data", {}).get(today)
    if not daily:
        return False, 0

    # Check if all quests completed
    quests = daily.get("quests", {})
    all_done = all(q["completed"] for q in quests.values())

    if not all_done:
        return False, user_data.get("quest_keys", 0)

    # Check if key already claimed
    if daily.get("key_claimed", False):
        return False, user_data.get("quest_keys", 0)

    # Award the key
    daily["key_claimed"] = True
    user_data["quest_keys"] = user_data.get("quest_keys", 0) + 1

    _save_quests_data(data)
    return True, user_data["quest_keys"]


def get_quest_keys(guild_id: int, user_id: int) -> int:
    """Get the number of quest keys a user has"""
    user_data = _get_user_data(guild_id, user_id)
    return user_data.get("quest_keys", 0)


def use_quest_key(guild_id: int, user_id: int) -> bool:
    """
    Use a quest key (for opening lootbox)

    Returns:
        success: bool
    """
    data = _load_quests_data()
    guild_str = str(guild_id)
    user_str = str(user_id)

    user_data = data["guilds"].get(guild_str, {}).get("users", {}).get(user_str)
    if not user_data:
        return False

    if user_data.get("quest_keys", 0) <= 0:
        return False

    user_data["quest_keys"] -= 1
    user_data["total_lootboxes_opened"] = user_data.get("total_lootboxes_opened", 0) + 1

    _save_quests_data(data)
    return True


def get_user_quest_stats(guild_id: int, user_id: int) -> Dict:
    """Get user's quest statistics"""
    user_data = _get_user_data(guild_id, user_id)

    return {
        "quest_keys": user_data.get("quest_keys", 0),
        "total_quests_completed": user_data.get("total_quests_completed", 0),
        "total_lootboxes_opened": user_data.get("total_lootboxes_opened", 0)
    }


def get_time_until_reset() -> str:
    """Get time remaining until quest reset (midnight UTC)"""
    now = datetime.utcnow()
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    diff = tomorrow - now

    hours = int(diff.total_seconds() // 3600)
    minutes = int((diff.total_seconds() % 3600) // 60)

    return f"{hours}h {minutes}m"
