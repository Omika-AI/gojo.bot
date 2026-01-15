"""
Custom Commands Database - Allows admins to create custom bot responses

Schema:
- guild_id: Server ID
- command_name: Trigger keyword (e.g., "rules")
- response_type: "text", "embed", "role_add", "role_remove", "image"
- response_content: The content to send
- embed_data: JSON for embed customization (title, description, color, image)
- role_id: Role to add/remove (if type is role_*)
- created_by: User ID who created the command
- created_at: Timestamp
- uses: Number of times command was used
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, List

# File path for storing custom commands data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
CUSTOM_COMMANDS_FILE = os.path.join(DATA_DIR, 'custom_commands.json')


def _load_data() -> dict:
    """Load custom commands data from JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(CUSTOM_COMMANDS_FILE):
        try:
            with open(CUSTOM_COMMANDS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return {"guilds": {}}


def _save_data(data: dict):
    """Save custom commands data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CUSTOM_COMMANDS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _ensure_guild(data: dict, guild_id: int) -> dict:
    """Ensure guild data structure exists"""
    guild_str = str(guild_id)
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {"commands": {}}
    return data["guilds"][guild_str]


# ============================================
# COMMAND MANAGEMENT
# ============================================

def create_custom_command(
    guild_id: int,
    command_name: str,
    response_type: str,
    response_content: str,
    created_by: int,
    embed_data: Optional[Dict] = None,
    role_id: Optional[int] = None
) -> tuple[bool, str]:
    """
    Create a new custom command

    Args:
        guild_id: Server ID
        command_name: Trigger keyword (case-insensitive)
        response_type: "text", "embed", "role_add", "role_remove", "image"
        response_content: The content to send
        created_by: User ID who created the command
        embed_data: Optional embed customization
        role_id: Optional role ID for role commands

    Returns:
        (success, message)
    """
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)

    # Normalize command name
    command_name = command_name.lower().strip()

    # Check if command already exists
    if command_name in guild_data["commands"]:
        return False, f"Command `{command_name}` already exists!"

    # Validate response type
    valid_types = ["text", "embed", "role_add", "role_remove", "image"]
    if response_type not in valid_types:
        return False, f"Invalid response type. Must be one of: {', '.join(valid_types)}"

    # Create command entry
    guild_data["commands"][command_name] = {
        "response_type": response_type,
        "response_content": response_content,
        "embed_data": embed_data,
        "role_id": role_id,
        "created_by": created_by,
        "created_at": datetime.utcnow().isoformat(),
        "uses": 0
    }

    _save_data(data)
    return True, f"Custom command `{command_name}` created successfully!"


def delete_custom_command(guild_id: int, command_name: str) -> tuple[bool, str]:
    """Delete a custom command"""
    data = _load_data()
    guild_str = str(guild_id)
    command_name = command_name.lower().strip()

    if guild_str not in data["guilds"]:
        return False, "No custom commands found for this server."

    if command_name not in data["guilds"][guild_str]["commands"]:
        return False, f"Command `{command_name}` does not exist."

    del data["guilds"][guild_str]["commands"][command_name]
    _save_data(data)
    return True, f"Command `{command_name}` deleted successfully!"


def edit_custom_command(
    guild_id: int,
    command_name: str,
    response_content: Optional[str] = None,
    response_type: Optional[str] = None,
    embed_data: Optional[Dict] = None,
    role_id: Optional[int] = None
) -> tuple[bool, str]:
    """Edit an existing custom command"""
    data = _load_data()
    guild_str = str(guild_id)
    command_name = command_name.lower().strip()

    if guild_str not in data["guilds"]:
        return False, "No custom commands found for this server."

    if command_name not in data["guilds"][guild_str]["commands"]:
        return False, f"Command `{command_name}` does not exist."

    cmd = data["guilds"][guild_str]["commands"][command_name]

    if response_content is not None:
        cmd["response_content"] = response_content
    if response_type is not None:
        cmd["response_type"] = response_type
    if embed_data is not None:
        cmd["embed_data"] = embed_data
    if role_id is not None:
        cmd["role_id"] = role_id

    _save_data(data)
    return True, f"Command `{command_name}` updated successfully!"


def get_custom_command(guild_id: int, command_name: str) -> Optional[Dict]:
    """Get a custom command by name"""
    data = _load_data()
    guild_str = str(guild_id)
    command_name = command_name.lower().strip()

    if guild_str not in data["guilds"]:
        return None

    return data["guilds"][guild_str]["commands"].get(command_name)


def increment_command_uses(guild_id: int, command_name: str):
    """Increment the use counter for a command"""
    data = _load_data()
    guild_str = str(guild_id)
    command_name = command_name.lower().strip()

    if guild_str in data["guilds"]:
        if command_name in data["guilds"][guild_str]["commands"]:
            data["guilds"][guild_str]["commands"][command_name]["uses"] += 1
            _save_data(data)


def list_custom_commands(guild_id: int) -> List[Dict]:
    """Get all custom commands for a guild"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return []

    commands = []
    for name, cmd_data in data["guilds"][guild_str]["commands"].items():
        commands.append({
            "name": name,
            **cmd_data
        })

    return sorted(commands, key=lambda x: x["name"])


def get_command_count(guild_id: int) -> int:
    """Get total number of custom commands for a guild"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return 0

    return len(data["guilds"][guild_str]["commands"])
