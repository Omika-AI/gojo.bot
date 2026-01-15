"""
Server Configuration Database - Central config for server settings

Schema:
- guild_id: Server ID
- language: Server language code ("en", "da", "de", etc.)
- welcome:
  - enabled: bool
  - channel_id: Channel for welcome messages
  - message: Custom welcome message (with placeholders)
  - use_image: Whether to generate welcome cards
  - background_url: Custom background image URL
  - dm_enabled: Send DM to new members
  - dm_message: Custom DM message
- goodbye:
  - enabled: bool
  - channel_id: Channel for goodbye messages
  - message: Custom goodbye message
  - use_image: Whether to generate goodbye cards
- auto_role:
  - enabled: bool
  - role_ids: List of roles to assign on join
"""

import os
import json
from typing import Optional, Dict, List

# File path for storing server config data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
SERVER_CONFIG_FILE = os.path.join(DATA_DIR, 'server_config.json')

# Default settings
DEFAULT_WELCOME_MESSAGE = "Welcome to {server}, {user}! You are member #{member_count}!"
DEFAULT_GOODBYE_MESSAGE = "Goodbye {user}! We'll miss you!"
DEFAULT_DM_MESSAGE = "Welcome to **{server}**! Check out our rules and enjoy your stay!"


def _load_data() -> dict:
    """Load server config data from JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(SERVER_CONFIG_FILE):
        try:
            with open(SERVER_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return {"guilds": {}}


def _save_data(data: dict):
    """Save server config data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SERVER_CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _ensure_guild(data: dict, guild_id: int) -> dict:
    """Ensure guild data structure exists with defaults"""
    guild_str = str(guild_id)
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {
            "language": "en",
            "welcome": {
                "enabled": False,
                "channel_id": None,
                "message": DEFAULT_WELCOME_MESSAGE,
                "use_image": True,
                "background_url": None,
                "dm_enabled": False,
                "dm_message": DEFAULT_DM_MESSAGE
            },
            "goodbye": {
                "enabled": False,
                "channel_id": None,
                "message": DEFAULT_GOODBYE_MESSAGE,
                "use_image": False
            },
            "auto_role": {
                "enabled": False,
                "role_ids": []
            }
        }
    return data["guilds"][guild_str]


# ============================================
# LANGUAGE SETTINGS
# ============================================

def get_server_language(guild_id: int) -> str:
    """Get the server's language code"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str in data["guilds"]:
        return data["guilds"][guild_str].get("language", "en")

    return "en"


def set_server_language(guild_id: int, language: str) -> tuple[bool, str]:
    """Set the server's language"""
    # Supported languages
    supported = ["en", "da", "de", "es", "fr", "pt", "nl", "it", "pl", "ru", "ja", "ko", "zh"]

    if language not in supported:
        return False, f"Unsupported language. Supported: {', '.join(supported)}"

    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["language"] = language
    _save_data(data)

    return True, f"Server language set to: {language}"


# ============================================
# WELCOME SETTINGS
# ============================================

def get_welcome_config(guild_id: int) -> Dict:
    """Get welcome configuration for a guild"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    return guild_data["welcome"]


def set_welcome_enabled(guild_id: int, enabled: bool) -> tuple[bool, str]:
    """Enable or disable welcome messages"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["welcome"]["enabled"] = enabled
    _save_data(data)
    return True, f"Welcome messages {'enabled' if enabled else 'disabled'}!"


def set_welcome_channel(guild_id: int, channel_id: int) -> tuple[bool, str]:
    """Set the welcome channel"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["welcome"]["channel_id"] = channel_id
    _save_data(data)
    return True, "Welcome channel set!"


def set_welcome_message(guild_id: int, message: str) -> tuple[bool, str]:
    """Set the welcome message template"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["welcome"]["message"] = message
    _save_data(data)
    return True, "Welcome message updated!"


def set_welcome_image(guild_id: int, use_image: bool) -> tuple[bool, str]:
    """Enable or disable welcome card images"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["welcome"]["use_image"] = use_image
    _save_data(data)
    return True, f"Welcome images {'enabled' if use_image else 'disabled'}!"


def set_welcome_background(guild_id: int, background_url: Optional[str]) -> tuple[bool, str]:
    """Set custom background URL for welcome cards"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["welcome"]["background_url"] = background_url
    _save_data(data)
    return True, "Welcome background updated!" if background_url else "Welcome background reset to default!"


def set_welcome_dm(guild_id: int, enabled: bool, message: Optional[str] = None) -> tuple[bool, str]:
    """Set DM welcome settings"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["welcome"]["dm_enabled"] = enabled
    if message:
        guild_data["welcome"]["dm_message"] = message
    _save_data(data)
    return True, f"Welcome DMs {'enabled' if enabled else 'disabled'}!"


# ============================================
# GOODBYE SETTINGS
# ============================================

def get_goodbye_config(guild_id: int) -> Dict:
    """Get goodbye configuration for a guild"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    return guild_data["goodbye"]


def set_goodbye_enabled(guild_id: int, enabled: bool) -> tuple[bool, str]:
    """Enable or disable goodbye messages"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["goodbye"]["enabled"] = enabled
    _save_data(data)
    return True, f"Goodbye messages {'enabled' if enabled else 'disabled'}!"


def set_goodbye_channel(guild_id: int, channel_id: int) -> tuple[bool, str]:
    """Set the goodbye channel"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["goodbye"]["channel_id"] = channel_id
    _save_data(data)
    return True, "Goodbye channel set!"


def set_goodbye_message(guild_id: int, message: str) -> tuple[bool, str]:
    """Set the goodbye message template"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["goodbye"]["message"] = message
    _save_data(data)
    return True, "Goodbye message updated!"


def set_goodbye_image(guild_id: int, use_image: bool) -> tuple[bool, str]:
    """Enable or disable goodbye card images"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["goodbye"]["use_image"] = use_image
    _save_data(data)
    return True, f"Goodbye images {'enabled' if use_image else 'disabled'}!"


# ============================================
# AUTO ROLE SETTINGS
# ============================================

def get_auto_role_config(guild_id: int) -> Dict:
    """Get auto role configuration for a guild"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    return guild_data["auto_role"]


def set_auto_role_enabled(guild_id: int, enabled: bool) -> tuple[bool, str]:
    """Enable or disable auto roles"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["auto_role"]["enabled"] = enabled
    _save_data(data)
    return True, f"Auto roles {'enabled' if enabled else 'disabled'}!"


def add_auto_role(guild_id: int, role_id: int) -> tuple[bool, str]:
    """Add a role to auto-assign on join"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)

    if role_id in guild_data["auto_role"]["role_ids"]:
        return False, "Role is already in auto-role list!"

    guild_data["auto_role"]["role_ids"].append(role_id)
    _save_data(data)
    return True, "Auto role added!"


def remove_auto_role(guild_id: int, role_id: int) -> tuple[bool, str]:
    """Remove a role from auto-assign"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)

    if role_id not in guild_data["auto_role"]["role_ids"]:
        return False, "Role is not in auto-role list!"

    guild_data["auto_role"]["role_ids"].remove(role_id)
    _save_data(data)
    return True, "Auto role removed!"


def clear_auto_roles(guild_id: int) -> tuple[bool, str]:
    """Clear all auto roles"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    guild_data["auto_role"]["role_ids"] = []
    _save_data(data)
    return True, "All auto roles cleared!"


# ============================================
# FULL CONFIG
# ============================================

def get_full_config(guild_id: int) -> Dict:
    """Get the full configuration for a guild"""
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)
    return guild_data


def reset_config(guild_id: int) -> tuple[bool, str]:
    """Reset all configuration to defaults"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str in data["guilds"]:
        del data["guilds"][guild_str]

    _ensure_guild(data, guild_id)
    _save_data(data)
    return True, "Configuration reset to defaults!"
