"""
Reaction Roles Database - Persistent self-assign role system

Schema:
- guild_id: Server ID
- panels: List of reaction role panels
  - message_id: The message with buttons/selects
  - channel_id: Channel containing the message
  - panel_type: "buttons" or "dropdown"
  - title: Panel title
  - description: Panel description
  - roles: List of {role_id, emoji, label, description}
  - mode: "single" (one role) or "multiple" (many roles)
  - created_by: User ID
  - created_at: Timestamp
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, List

# File path for storing reaction roles data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
REACTION_ROLES_FILE = os.path.join(DATA_DIR, 'reaction_roles.json')


def _load_data() -> dict:
    """Load reaction roles data from JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(REACTION_ROLES_FILE):
        try:
            with open(REACTION_ROLES_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return {"guilds": {}}


def _save_data(data: dict):
    """Save reaction roles data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REACTION_ROLES_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _ensure_guild(data: dict, guild_id: int) -> dict:
    """Ensure guild data structure exists"""
    guild_str = str(guild_id)
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"panels": []}
    return data["guilds"][guild_str]


# ============================================
# PANEL MANAGEMENT
# ============================================

def create_reaction_panel(
    guild_id: int,
    channel_id: int,
    message_id: int,
    panel_type: str,
    title: str,
    description: str,
    roles: List[Dict],
    mode: str,
    created_by: int
) -> tuple[bool, str]:
    """
    Create a new reaction role panel

    Args:
        guild_id: Server ID
        channel_id: Channel ID
        message_id: Message ID with the panel
        panel_type: "buttons" or "dropdown"
        title: Panel title
        description: Panel description
        roles: List of {role_id, emoji, label, description}
        mode: "single" or "multiple"
        created_by: User ID who created the panel

    Returns:
        (success, message)
    """
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)

    # Check if panel already exists for this message
    for panel in guild_data["panels"]:
        if panel["message_id"] == message_id:
            return False, "A reaction role panel already exists on this message!"

    # Create panel entry
    panel = {
        "message_id": message_id,
        "channel_id": channel_id,
        "panel_type": panel_type,
        "title": title,
        "description": description,
        "roles": roles,
        "mode": mode,
        "created_by": created_by,
        "created_at": datetime.utcnow().isoformat()
    }

    guild_data["panels"].append(panel)
    _save_data(data)
    return True, "Reaction role panel created successfully!"


def delete_reaction_panel(guild_id: int, message_id: int) -> tuple[bool, str]:
    """Delete a reaction role panel"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "No reaction role panels found for this server."

    panels = data["guilds"][guild_str]["panels"]
    for i, panel in enumerate(panels):
        if panel["message_id"] == message_id:
            panels.pop(i)
            _save_data(data)
            return True, "Reaction role panel deleted successfully!"

    return False, "Panel not found."


def get_panel_by_message(guild_id: int, message_id: int) -> Optional[Dict]:
    """Get a reaction role panel by message ID"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return None

    for panel in data["guilds"][guild_str]["panels"]:
        if panel["message_id"] == message_id:
            return panel

    return None


def get_all_panels(guild_id: int) -> List[Dict]:
    """Get all reaction role panels for a guild"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return []

    return data["guilds"][guild_str]["panels"]


def add_role_to_panel(
    guild_id: int,
    message_id: int,
    role_id: int,
    emoji: str,
    label: str,
    description: str = ""
) -> tuple[bool, str]:
    """Add a role to an existing panel"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "No panels found."

    for panel in data["guilds"][guild_str]["panels"]:
        if panel["message_id"] == message_id:
            # Check if role already exists
            for role in panel["roles"]:
                if role["role_id"] == role_id:
                    return False, "This role is already in the panel!"

            # Add role
            panel["roles"].append({
                "role_id": role_id,
                "emoji": emoji,
                "label": label,
                "description": description
            })
            _save_data(data)
            return True, "Role added to panel!"

    return False, "Panel not found."


def remove_role_from_panel(guild_id: int, message_id: int, role_id: int) -> tuple[bool, str]:
    """Remove a role from a panel"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "No panels found."

    for panel in data["guilds"][guild_str]["panels"]:
        if panel["message_id"] == message_id:
            for i, role in enumerate(panel["roles"]):
                if role["role_id"] == role_id:
                    panel["roles"].pop(i)
                    _save_data(data)
                    return True, "Role removed from panel!"
            return False, "Role not found in panel."

    return False, "Panel not found."


def update_panel_mode(guild_id: int, message_id: int, mode: str) -> tuple[bool, str]:
    """Update panel mode (single/multiple)"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "No panels found."

    for panel in data["guilds"][guild_str]["panels"]:
        if panel["message_id"] == message_id:
            panel["mode"] = mode
            _save_data(data)
            return True, f"Panel mode set to {mode}!"

    return False, "Panel not found."
