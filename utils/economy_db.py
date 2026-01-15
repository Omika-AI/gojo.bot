"""
Economy Database Utility
Handles virtual currency storage, retrieval, and transactions
Uses JSON file for persistent storage

Currency: Coins (virtual, non-purchasable)
NOTE: This is a GLOBAL economy - balances are shared across all servers!
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from utils.logger import logger
from utils.achievements_data import update_user_stat as update_achievement_stat, check_and_complete_achievements

# Path to the economy data file
ECONOMY_FILE = "data/economy.json"

# Default values
DEFAULT_BALANCE = 0
DAILY_BASE_AMOUNT = 100  # Base daily claim amount
DAILY_STREAK_BONUS = 10  # Extra coins per day of streak
MAX_STREAK_BONUS = 500   # Maximum bonus from streak (50 days)


def _ensure_data_dir():
    """Ensure the data directory exists"""
    os.makedirs("data", exist_ok=True)


def _load_economy_data() -> dict:
    """Load economy data from file"""
    _ensure_data_dir()
    if os.path.exists(ECONOMY_FILE):
        try:
            with open(ECONOMY_FILE, 'r') as f:
                data = json.load(f)
                # Check if we need to migrate from old guild-based format
                if "guilds" in data and "users" not in data:
                    data = _migrate_to_global(data)
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading economy data: {e}")
            return {"users": {}}
    return {"users": {}}


def _migrate_to_global(old_data: dict) -> dict:
    """
    Migrate from guild-based economy to global economy.
    Combines balances from all guilds, taking the highest balance for each user.
    """
    logger.info("Migrating economy data from guild-based to global...")
    new_data = {"users": {}}

    for guild_id, guild_data in old_data.get("guilds", {}).items():
        for user_id, user_data in guild_data.get("users", {}).items():
            if user_id not in new_data["users"]:
                # First time seeing this user, copy their data
                new_data["users"][user_id] = user_data.copy()
            else:
                # User exists in multiple guilds - merge by taking higher values
                existing = new_data["users"][user_id]
                # Take the higher balance
                if user_data.get("balance", 0) > existing.get("balance", 0):
                    existing["balance"] = user_data["balance"]
                # Sum up total earned, gambled, won, lost across all servers
                existing["total_earned"] = existing.get("total_earned", 0) + user_data.get("total_earned", 0)
                existing["total_gambled"] = existing.get("total_gambled", 0) + user_data.get("total_gambled", 0)
                existing["total_won"] = existing.get("total_won", 0) + user_data.get("total_won", 0)
                existing["total_lost"] = existing.get("total_lost", 0) + user_data.get("total_lost", 0)
                # Keep the better streak
                if user_data.get("daily_streak", 0) > existing.get("daily_streak", 0):
                    existing["daily_streak"] = user_data["daily_streak"]
                    existing["last_daily"] = user_data.get("last_daily")

    # Save the migrated data
    _save_economy_data(new_data)
    logger.info(f"Migration complete! Migrated {len(new_data['users'])} users to global economy.")
    return new_data


def _save_economy_data(data: dict):
    """Save economy data to file"""
    _ensure_data_dir()
    try:
        with open(ECONOMY_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        logger.error(f"Error saving economy data: {e}")


def _get_user_data(user_id: int) -> dict:
    """Get or create user data (GLOBAL - no guild needed)"""
    data = _load_economy_data()
    user_str = str(user_id)

    if user_str not in data["users"]:
        data["users"][user_str] = {
            "balance": DEFAULT_BALANCE,
            "last_daily": None,
            "daily_streak": 0,
            "total_earned": 0,
            "total_gambled": 0,
            "total_won": 0,
            "total_lost": 0
        }
        _save_economy_data(data)

    return data["users"][user_str]


def _update_user_data(user_id: int, user_data: dict):
    """Update user data (GLOBAL - no guild needed)"""
    data = _load_economy_data()
    user_str = str(user_id)
    data["users"][user_str] = user_data
    _save_economy_data(data)


# =============================================================================
# PUBLIC FUNCTIONS (guild_id is now optional/ignored for backwards compatibility)
# =============================================================================

def get_balance(guild_id: int, user_id: int) -> int:
    """Get a user's coin balance (GLOBAL - guild_id ignored)"""
    user_data = _get_user_data(user_id)
    return user_data["balance"]


def add_coins(guild_id: int, user_id: int, amount: int, source: str = "unknown") -> int:
    """Add coins to a user's balance. Returns new balance. (GLOBAL - guild_id ignored)"""
    user_data = _get_user_data(user_id)
    user_data["balance"] += amount
    user_data["total_earned"] += amount
    _update_user_data(user_id, user_data)
    logger.info(f"Added {amount} coins to user {user_id} (source: {source})")

    # Track peak_balance achievement
    try:
        update_achievement_stat(user_id, "peak_balance", value=user_data["balance"])
        check_and_complete_achievements(user_id)
    except:
        pass

    return user_data["balance"]


def remove_coins(guild_id: int, user_id: int, amount: int) -> Tuple[bool, int]:
    """
    Remove coins from a user's balance. (GLOBAL - guild_id ignored)
    Returns (success, new_balance).
    Fails if user doesn't have enough coins.
    """
    user_data = _get_user_data(user_id)

    if user_data["balance"] < amount:
        return False, user_data["balance"]

    user_data["balance"] -= amount
    _update_user_data(user_id, user_data)
    return True, user_data["balance"]


def transfer_coins(guild_id: int, from_user: int, to_user: int, amount: int) -> Tuple[bool, str]:
    """
    Transfer coins between users. (GLOBAL - guild_id ignored)
    Returns (success, message).
    """
    from_data = _get_user_data(from_user)

    if from_data["balance"] < amount:
        return False, "Insufficient balance"

    # Remove from sender
    from_data["balance"] -= amount
    _update_user_data(from_user, from_data)

    # Add to receiver
    add_coins(0, to_user, amount, source="transfer")

    return True, "Transfer successful"


def set_balance(guild_id: int, user_id: int, amount: int) -> int:
    """Set a user's balance to a specific amount (admin use) (GLOBAL - guild_id ignored)"""
    user_data = _get_user_data(user_id)
    user_data["balance"] = amount
    _update_user_data(user_id, user_data)
    return amount


def claim_daily(guild_id: int, user_id: int) -> Tuple[bool, int, int, str]:
    """
    Claim daily coins. (GLOBAL - guild_id ignored)
    Returns (success, amount_claimed, new_streak, message).
    """
    user_data = _get_user_data(user_id)
    now = datetime.utcnow()

    # Check if already claimed today
    if user_data["last_daily"]:
        last_claim = datetime.fromisoformat(user_data["last_daily"])
        time_since_claim = now - last_claim

        # If claimed less than 24 hours ago, deny
        if time_since_claim < timedelta(hours=20):  # 20 hours to be lenient
            hours_left = 20 - (time_since_claim.total_seconds() / 3600)
            return False, 0, user_data["daily_streak"], f"You can claim again in {hours_left:.1f} hours"

        # Check if streak is maintained (within 48 hours)
        if time_since_claim < timedelta(hours=48):
            user_data["daily_streak"] += 1
        else:
            # Streak broken
            user_data["daily_streak"] = 1
    else:
        # First time claiming
        user_data["daily_streak"] = 1

    # Calculate amount with streak bonus
    streak_bonus = min(user_data["daily_streak"] * DAILY_STREAK_BONUS, MAX_STREAK_BONUS)
    total_amount = DAILY_BASE_AMOUNT + streak_bonus

    # Update user data
    user_data["balance"] += total_amount
    user_data["total_earned"] += total_amount
    user_data["last_daily"] = now.isoformat()
    _update_user_data(user_id, user_data)

    return True, total_amount, user_data["daily_streak"], "Daily claimed!"


def get_daily_streak(guild_id: int, user_id: int) -> int:
    """Get a user's current daily streak (GLOBAL - guild_id ignored)"""
    user_data = _get_user_data(user_id)
    return user_data["daily_streak"]


def record_gamble(guild_id: int, user_id: int, bet_amount: int, won: bool, win_amount: int = 0):
    """Record a gambling transaction for statistics (GLOBAL - guild_id ignored)"""
    user_data = _get_user_data(user_id)
    user_data["total_gambled"] += bet_amount

    if won:
        user_data["total_won"] += win_amount
    else:
        user_data["total_lost"] += bet_amount

    _update_user_data(user_id, user_data)


def get_user_stats(guild_id: int, user_id: int) -> dict:
    """Get a user's full statistics (GLOBAL - guild_id ignored)"""
    return _get_user_data(user_id)


def get_leaderboard(guild_id: int, limit: int = 10) -> List[Tuple[str, int]]:
    """Get the top users by balance (GLOBAL leaderboard - guild_id ignored)"""
    data = _load_economy_data()
    users = data.get("users", {})

    # Sort by balance
    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1].get("balance", 0),
        reverse=True
    )

    # Return top users
    return [(user_id, user_data.get("balance", 0)) for user_id, user_data in sorted_users[:limit]]


def get_gambling_leaderboard(guild_id: int, limit: int = 10) -> List[Tuple[str, int]]:
    """Get the top users by total winnings (GLOBAL leaderboard - guild_id ignored)"""
    data = _load_economy_data()
    users = data.get("users", {})

    # Sort by net gambling profit (won - lost)
    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1].get("total_won", 0) - x[1].get("total_lost", 0),
        reverse=True
    )

    return [(user_id, user_data.get("total_won", 0) - user_data.get("total_lost", 0))
            for user_id, user_data in sorted_users[:limit]]
