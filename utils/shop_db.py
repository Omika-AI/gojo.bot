"""
Shop Database - Manages the server shop and purchases

This module handles:
- Shop items and pricing
- User purchases and inventory
- Temporary items (XP boosters, custom roles)
- Expiration tracking
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from enum import Enum


# File path for storing shop data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
SHOP_FILE = os.path.join(DATA_DIR, 'shop.json')


# ============================================
# SHOP ITEM DEFINITIONS
# ============================================

class ShopItem:
    """Represents an item in the shop"""
    def __init__(self, item_id: str, name: str, description: str, price: int,
                 duration_hours: Optional[int] = None, category: str = "misc"):
        self.item_id = item_id
        self.name = name
        self.description = description
        self.price = price
        self.duration_hours = duration_hours  # None = permanent
        self.category = category

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "duration_hours": self.duration_hours,
            "category": self.category
        }


# Default shop items
SHOP_ITEMS = {
    # XP Boosters
    "xp_boost_2h": ShopItem(
        item_id="xp_boost_2h",
        name="XP Booster (2 Hours)",
        description="Double XP from messages and voice for 2 hours",
        price=2500,
        duration_hours=2,
        category="boosters"
    ),
    "xp_boost_6h": ShopItem(
        item_id="xp_boost_6h",
        name="XP Booster (6 Hours)",
        description="Double XP from messages and voice for 6 hours",
        price=6000,
        duration_hours=6,
        category="boosters"
    ),
    "xp_boost_24h": ShopItem(
        item_id="xp_boost_24h",
        name="XP Booster (24 Hours)",
        description="Double XP from messages and voice for 24 hours",
        price=20000,
        duration_hours=24,
        category="boosters"
    ),

    # Custom Roles
    "custom_role_1w": ShopItem(
        item_id="custom_role_1w",
        name="Custom Color Role (1 Week)",
        description="Get a custom colored role with your chosen name for 1 week",
        price=10000,
        duration_hours=168,  # 7 days
        category="roles"
    ),
    "custom_role_1m": ShopItem(
        item_id="custom_role_1m",
        name="Custom Color Role (1 Month)",
        description="Get a custom colored role with your chosen name for 1 month",
        price=35000,
        duration_hours=720,  # 30 days
        category="roles"
    ),

    # Fun Items
    "nickname_change": ShopItem(
        item_id="nickname_change",
        name="Nickname Change Token",
        description="Change another user's nickname for 24 hours (with limits)",
        price=5000,
        duration_hours=24,
        category="fun"
    ),
    "highlight_message": ShopItem(
        item_id="highlight_message",
        name="Message Highlight",
        description="Your next message will be pinned for 1 hour",
        price=1500,
        duration_hours=1,
        category="fun"
    ),
}


# ============================================
# DATA PERSISTENCE FUNCTIONS
# ============================================

def _load_shop_data() -> dict:
    """Load shop data from JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(SHOP_FILE):
        try:
            with open(SHOP_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # Default structure
    return {
        "guilds": {}
    }


def _save_shop_data(data: dict):
    """Save shop data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SHOP_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _get_user_data(guild_id: int, user_id: int) -> dict:
    """Get user's shop data, creating default if doesn't exist"""
    data = _load_shop_data()
    guild_str = str(guild_id)
    user_str = str(user_id)

    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"users": {}, "custom_roles": {}}

    if user_str not in data["guilds"][guild_str]["users"]:
        data["guilds"][guild_str]["users"][user_str] = {
            "purchases": [],      # List of {item_id, purchased_at, expires_at, active, metadata}
            "total_spent": 0
        }
        _save_shop_data(data)

    return data["guilds"][guild_str]["users"][user_str]


# ============================================
# SHOP FUNCTIONS
# ============================================

def get_shop_items() -> List[ShopItem]:
    """Get all available shop items"""
    return list(SHOP_ITEMS.values())


def get_item(item_id: str) -> Optional[ShopItem]:
    """Get a specific shop item"""
    return SHOP_ITEMS.get(item_id)


def get_items_by_category(category: str) -> List[ShopItem]:
    """Get all items in a category"""
    return [item for item in SHOP_ITEMS.values() if item.category == category]


# ============================================
# PURCHASE FUNCTIONS
# ============================================

def purchase_item(guild_id: int, user_id: int, item_id: str, metadata: dict = None) -> Tuple[bool, str, Optional[dict]]:
    """
    Process a purchase

    Args:
        guild_id: The guild ID
        user_id: The user ID
        item_id: The item to purchase
        metadata: Additional data (e.g., role color, role name)

    Returns:
        (success, message, purchase_data)
    """
    # Get the item
    item = get_item(item_id)
    if not item:
        return False, "Item not found", None

    # Check if user already has an active version of this item (for non-stackable items)
    if item.category in ["boosters", "roles"]:
        active = get_active_item(guild_id, user_id, item_id)
        if active and item.category == "boosters":
            return False, "You already have an active XP booster! Wait for it to expire.", None
        if active and item.category == "roles":
            return False, "You already have an active custom role! Wait for it to expire or let it be replaced.", None

    data = _load_shop_data()
    guild_str = str(guild_id)
    user_str = str(user_id)

    # Initialize if needed
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"users": {}, "custom_roles": {}}
    if user_str not in data["guilds"][guild_str]["users"]:
        data["guilds"][guild_str]["users"][user_str] = {
            "purchases": [],
            "total_spent": 0
        }

    # Calculate expiration
    now = datetime.now()
    expires_at = None
    if item.duration_hours:
        expires_at = (now + timedelta(hours=item.duration_hours)).isoformat()

    # Create purchase record
    purchase = {
        "item_id": item_id,
        "purchased_at": now.isoformat(),
        "expires_at": expires_at,
        "active": True,
        "metadata": metadata or {}
    }

    data["guilds"][guild_str]["users"][user_str]["purchases"].append(purchase)
    data["guilds"][guild_str]["users"][user_str]["total_spent"] += item.price

    _save_shop_data(data)

    return True, f"Successfully purchased {item.name}!", purchase


def get_active_item(guild_id: int, user_id: int, item_id: str) -> Optional[dict]:
    """Get an active (non-expired) purchase of a specific item"""
    user_data = _get_user_data(guild_id, user_id)
    now = datetime.now()

    for purchase in user_data["purchases"]:
        if purchase["item_id"] == item_id and purchase["active"]:
            # Check if expired
            if purchase["expires_at"]:
                expires = datetime.fromisoformat(purchase["expires_at"])
                if now >= expires:
                    continue  # Expired
            return purchase

    return None


def has_active_xp_boost(guild_id: int, user_id: int) -> Tuple[bool, float]:
    """
    Check if user has an active XP boost

    Returns:
        (has_boost, multiplier)
    """
    # Check all XP boost items
    for item_id in ["xp_boost_2h", "xp_boost_6h", "xp_boost_24h"]:
        active = get_active_item(guild_id, user_id, item_id)
        if active:
            return True, 2.0  # Double XP

    return False, 1.0


def get_user_purchases(guild_id: int, user_id: int, active_only: bool = False) -> List[dict]:
    """Get user's purchase history"""
    user_data = _get_user_data(guild_id, user_id)
    purchases = user_data.get("purchases", [])

    if active_only:
        now = datetime.now()
        active_purchases = []
        for purchase in purchases:
            if not purchase["active"]:
                continue
            if purchase["expires_at"]:
                expires = datetime.fromisoformat(purchase["expires_at"])
                if now >= expires:
                    continue
            active_purchases.append(purchase)
        return active_purchases

    return purchases


def get_user_total_spent(guild_id: int, user_id: int) -> int:
    """Get total coins spent by user"""
    user_data = _get_user_data(guild_id, user_id)
    return user_data.get("total_spent", 0)


def deactivate_purchase(guild_id: int, user_id: int, item_id: str) -> bool:
    """Manually deactivate a purchase (e.g., when role is removed)"""
    data = _load_shop_data()
    guild_str = str(guild_id)
    user_str = str(user_id)

    if guild_str not in data["guilds"]:
        return False
    if user_str not in data["guilds"][guild_str]["users"]:
        return False

    for purchase in data["guilds"][guild_str]["users"][user_str]["purchases"]:
        if purchase["item_id"] == item_id and purchase["active"]:
            purchase["active"] = False
            _save_shop_data(data)
            return True

    return False


# ============================================
# CUSTOM ROLE TRACKING
# ============================================

def store_custom_role(guild_id: int, user_id: int, role_id: int, expires_at: str):
    """Store a custom role for tracking expiration"""
    data = _load_shop_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"users": {}, "custom_roles": {}}

    if "custom_roles" not in data["guilds"][guild_str]:
        data["guilds"][guild_str]["custom_roles"] = {}

    data["guilds"][guild_str]["custom_roles"][str(role_id)] = {
        "user_id": str(user_id),
        "expires_at": expires_at,
        "created_at": datetime.now().isoformat()
    }

    _save_shop_data(data)


def get_expired_custom_roles(guild_id: int) -> List[Tuple[int, int]]:
    """
    Get all expired custom roles in a guild

    Returns:
        List of (role_id, user_id) tuples
    """
    data = _load_shop_data()
    guild_str = str(guild_id)
    now = datetime.now()

    if guild_str not in data["guilds"]:
        return []

    custom_roles = data["guilds"][guild_str].get("custom_roles", {})
    expired = []

    for role_id_str, role_data in custom_roles.items():
        expires = datetime.fromisoformat(role_data["expires_at"])
        if now >= expires:
            expired.append((int(role_id_str), int(role_data["user_id"])))

    return expired


def remove_custom_role_tracking(guild_id: int, role_id: int):
    """Remove a custom role from tracking after it's deleted"""
    data = _load_shop_data()
    guild_str = str(guild_id)
    role_str = str(role_id)

    if guild_str not in data["guilds"]:
        return

    if "custom_roles" not in data["guilds"][guild_str]:
        return

    if role_str in data["guilds"][guild_str]["custom_roles"]:
        del data["guilds"][guild_str]["custom_roles"][role_str]
        _save_shop_data(data)


def get_all_guilds_with_custom_roles() -> List[int]:
    """Get all guild IDs that have custom roles to check"""
    data = _load_shop_data()
    guilds = []

    for guild_str, guild_data in data.get("guilds", {}).items():
        if guild_data.get("custom_roles"):
            guilds.append(int(guild_str))

    return guilds


# ============================================
# CLEANUP FUNCTIONS
# ============================================

def cleanup_expired_purchases(guild_id: int, user_id: int) -> int:
    """
    Mark expired purchases as inactive

    Returns:
        Number of purchases cleaned up
    """
    data = _load_shop_data()
    guild_str = str(guild_id)
    user_str = str(user_id)
    now = datetime.now()
    cleaned = 0

    if guild_str not in data["guilds"]:
        return 0
    if user_str not in data["guilds"][guild_str]["users"]:
        return 0

    for purchase in data["guilds"][guild_str]["users"][user_str]["purchases"]:
        if purchase["active"] and purchase["expires_at"]:
            expires = datetime.fromisoformat(purchase["expires_at"])
            if now >= expires:
                purchase["active"] = False
                cleaned += 1

    if cleaned > 0:
        _save_shop_data(data)

    return cleaned
