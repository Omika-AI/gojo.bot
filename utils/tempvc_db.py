"""
Temporary Voice Channel Database - Manages "Join to Create" voice channels

This module handles:
- Join-to-Create channel configuration
- Temporary VC creation and tracking
- VC ownership and permissions
- Automatic cleanup when empty
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# File path for storing temp VC data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
TEMPVC_FILE = os.path.join(DATA_DIR, 'tempvc.json')

# ============================================
# DEFAULT SETTINGS
# ============================================

DEFAULT_VC_NAME = "{user}'s Channel"
DEFAULT_USER_LIMIT = 0  # 0 = unlimited
DEFAULT_BITRATE = 64000  # 64kbps


# ============================================
# DATA PERSISTENCE FUNCTIONS
# ============================================

def _load_tempvc_data() -> dict:
    """Load temp VC data from JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(TEMPVC_FILE):
        try:
            with open(TEMPVC_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return {"guilds": {}}


def _save_tempvc_data(data: dict):
    """Save temp VC data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TEMPVC_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _ensure_guild_data(data: dict, guild_id: int) -> dict:
    """Ensure guild data structure exists"""
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {
            "join_to_create_channel": None,  # Channel ID users join to create a VC
            "category_id": None,  # Category where temp VCs are created
            "temp_channels": {},  # {channel_id: {owner_id, name, created_at, locked}}
            "default_name": DEFAULT_VC_NAME,
            "default_limit": DEFAULT_USER_LIMIT,
        }

    return data["guilds"][guild_str]


# ============================================
# CONFIGURATION FUNCTIONS
# ============================================

def setup_join_to_create(guild_id: int, channel_id: int, category_id: int) -> bool:
    """
    Set up the Join-to-Create channel for a guild

    Args:
        guild_id: The guild ID
        channel_id: The VC users join to create their own
        category_id: The category where temp VCs will be created

    Returns:
        success: bool
    """
    data = _load_tempvc_data()
    guild_data = _ensure_guild_data(data, guild_id)

    guild_data["join_to_create_channel"] = channel_id
    guild_data["category_id"] = category_id

    _save_tempvc_data(data)
    return True


def get_join_to_create_channel(guild_id: int) -> Optional[int]:
    """Get the Join-to-Create channel ID for a guild"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return None

    return data["guilds"][guild_str].get("join_to_create_channel")


def get_category_id(guild_id: int) -> Optional[int]:
    """Get the category ID where temp VCs are created"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return None

    return data["guilds"][guild_str].get("category_id")


def disable_join_to_create(guild_id: int) -> bool:
    """Disable the Join-to-Create feature for a guild"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)

    if guild_str in data["guilds"]:
        data["guilds"][guild_str]["join_to_create_channel"] = None
        data["guilds"][guild_str]["category_id"] = None
        _save_tempvc_data(data)

    return True


# ============================================
# TEMP VC MANAGEMENT FUNCTIONS
# ============================================

def create_temp_vc(guild_id: int, channel_id: int, owner_id: int, name: str) -> bool:
    """
    Register a newly created temporary VC

    Args:
        guild_id: The guild ID
        channel_id: The new VC's ID
        owner_id: The user who owns this VC
        name: The channel name

    Returns:
        success: bool
    """
    data = _load_tempvc_data()
    guild_data = _ensure_guild_data(data, guild_id)

    guild_data["temp_channels"][str(channel_id)] = {
        "owner_id": owner_id,
        "name": name,
        "created_at": datetime.utcnow().isoformat(),
        "locked": False,
        "user_limit": 0,
        "allowed_users": [],  # Users allowed even when locked
        "banned_users": [],   # Users banned from this VC
    }

    _save_tempvc_data(data)
    return True


def delete_temp_vc(guild_id: int, channel_id: int) -> bool:
    """
    Remove a temp VC from tracking (called when channel is deleted)

    Returns:
        success: bool
    """
    data = _load_tempvc_data()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str in data["guilds"]:
        if channel_str in data["guilds"][guild_str].get("temp_channels", {}):
            del data["guilds"][guild_str]["temp_channels"][channel_str]
            _save_tempvc_data(data)
            return True

    return False


def is_temp_vc(guild_id: int, channel_id: int) -> bool:
    """Check if a channel is a temporary VC"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data["guilds"]:
        return False

    return channel_str in data["guilds"][guild_str].get("temp_channels", {})


def get_temp_vc_info(guild_id: int, channel_id: int) -> Optional[Dict]:
    """Get info about a temp VC"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data["guilds"]:
        return None

    return data["guilds"][guild_str].get("temp_channels", {}).get(channel_str)


def get_vc_owner(guild_id: int, channel_id: int) -> Optional[int]:
    """Get the owner of a temp VC"""
    info = get_temp_vc_info(guild_id, channel_id)
    if info:
        return info.get("owner_id")
    return None


def is_vc_owner(guild_id: int, channel_id: int, user_id: int) -> bool:
    """Check if a user is the owner of a temp VC"""
    owner = get_vc_owner(guild_id, channel_id)
    return owner == user_id


def transfer_ownership(guild_id: int, channel_id: int, new_owner_id: int) -> bool:
    """Transfer ownership of a temp VC to another user"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data["guilds"]:
        return False

    vc_data = data["guilds"][guild_str].get("temp_channels", {}).get(channel_str)
    if not vc_data:
        return False

    vc_data["owner_id"] = new_owner_id
    _save_tempvc_data(data)
    return True


# ============================================
# VC SETTINGS FUNCTIONS
# ============================================

def set_vc_name(guild_id: int, channel_id: int, name: str) -> bool:
    """Set the name of a temp VC"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data["guilds"]:
        return False

    vc_data = data["guilds"][guild_str].get("temp_channels", {}).get(channel_str)
    if not vc_data:
        return False

    vc_data["name"] = name
    _save_tempvc_data(data)
    return True


def set_vc_limit(guild_id: int, channel_id: int, limit: int) -> bool:
    """Set the user limit of a temp VC"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data["guilds"]:
        return False

    vc_data = data["guilds"][guild_str].get("temp_channels", {}).get(channel_str)
    if not vc_data:
        return False

    vc_data["user_limit"] = limit
    _save_tempvc_data(data)
    return True


def set_vc_locked(guild_id: int, channel_id: int, locked: bool) -> bool:
    """Lock or unlock a temp VC"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data["guilds"]:
        return False

    vc_data = data["guilds"][guild_str].get("temp_channels", {}).get(channel_str)
    if not vc_data:
        return False

    vc_data["locked"] = locked
    _save_tempvc_data(data)
    return True


def is_vc_locked(guild_id: int, channel_id: int) -> bool:
    """Check if a temp VC is locked"""
    info = get_temp_vc_info(guild_id, channel_id)
    if info:
        return info.get("locked", False)
    return False


def allow_user(guild_id: int, channel_id: int, user_id: int) -> bool:
    """Allow a user to join a locked VC"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data["guilds"]:
        return False

    vc_data = data["guilds"][guild_str].get("temp_channels", {}).get(channel_str)
    if not vc_data:
        return False

    if user_id not in vc_data.get("allowed_users", []):
        if "allowed_users" not in vc_data:
            vc_data["allowed_users"] = []
        vc_data["allowed_users"].append(user_id)
        _save_tempvc_data(data)

    return True


def remove_allowed_user(guild_id: int, channel_id: int, user_id: int) -> bool:
    """Remove a user from the allowed list"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data["guilds"]:
        return False

    vc_data = data["guilds"][guild_str].get("temp_channels", {}).get(channel_str)
    if not vc_data:
        return False

    if user_id in vc_data.get("allowed_users", []):
        vc_data["allowed_users"].remove(user_id)
        _save_tempvc_data(data)

    return True


def is_user_allowed(guild_id: int, channel_id: int, user_id: int) -> bool:
    """Check if a user is allowed in a locked VC"""
    info = get_temp_vc_info(guild_id, channel_id)
    if info:
        # Owner is always allowed
        if info.get("owner_id") == user_id:
            return True
        return user_id in info.get("allowed_users", [])
    return False


def ban_user(guild_id: int, channel_id: int, user_id: int) -> bool:
    """Ban a user from a temp VC"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data["guilds"]:
        return False

    vc_data = data["guilds"][guild_str].get("temp_channels", {}).get(channel_str)
    if not vc_data:
        return False

    if user_id not in vc_data.get("banned_users", []):
        if "banned_users" not in vc_data:
            vc_data["banned_users"] = []
        vc_data["banned_users"].append(user_id)
        _save_tempvc_data(data)

    return True


def unban_user(guild_id: int, channel_id: int, user_id: int) -> bool:
    """Unban a user from a temp VC"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data["guilds"]:
        return False

    vc_data = data["guilds"][guild_str].get("temp_channels", {}).get(channel_str)
    if not vc_data:
        return False

    if user_id in vc_data.get("banned_users", []):
        vc_data["banned_users"].remove(user_id)
        _save_tempvc_data(data)

    return True


def is_user_banned(guild_id: int, channel_id: int, user_id: int) -> bool:
    """Check if a user is banned from a temp VC"""
    info = get_temp_vc_info(guild_id, channel_id)
    if info:
        return user_id in info.get("banned_users", [])
    return False


# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_all_temp_vcs(guild_id: int) -> List[Tuple[int, Dict]]:
    """Get all temp VCs in a guild"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return []

    temp_channels = data["guilds"][guild_str].get("temp_channels", {})
    return [(int(cid), info) for cid, info in temp_channels.items()]


def get_user_temp_vc(guild_id: int, user_id: int) -> Optional[int]:
    """Get the temp VC owned by a user (if any)"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return None

    for channel_id, info in data["guilds"][guild_str].get("temp_channels", {}).items():
        if info.get("owner_id") == user_id:
            return int(channel_id)

    return None


def get_default_name(guild_id: int) -> str:
    """Get the default name template for new VCs"""
    data = _load_tempvc_data()
    guild_str = str(guild_id)

    if guild_str in data["guilds"]:
        return data["guilds"][guild_str].get("default_name", DEFAULT_VC_NAME)

    return DEFAULT_VC_NAME


def set_default_name(guild_id: int, name_template: str) -> bool:
    """Set the default name template for new VCs"""
    data = _load_tempvc_data()
    guild_data = _ensure_guild_data(data, guild_id)

    guild_data["default_name"] = name_template
    _save_tempvc_data(data)
    return True
