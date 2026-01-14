"""
Ticket System Database Utilities
Handles all ticket data storage and retrieval using JSON files.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Path to the tickets database file
DATA_DIR = Path(__file__).parent.parent / "data"
TICKETS_FILE = DATA_DIR / "tickets.json"


def load_tickets() -> Dict[str, Any]:
    """Load all ticket data from the JSON file."""
    if not TICKETS_FILE.exists():
        return {}

    try:
        with open(TICKETS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_tickets(data: Dict[str, Any]) -> None:
    """Save ticket data to the JSON file."""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(TICKETS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_guild_config(guild_id: int) -> Optional[Dict[str, Any]]:
    """
    Get ticket configuration for a specific guild.
    Returns None if the guild hasn't set up tickets.
    """
    data = load_tickets()
    guild_str = str(guild_id)

    if guild_str not in data:
        return None

    return data[guild_str].get("config")


def set_guild_config(
    guild_id: int,
    staff_role_id: int,
    log_channel_id: int,
    ticket_channel_id: int,
    category_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Set or update ticket configuration for a guild.
    Returns the new config.
    """
    data = load_tickets()
    guild_str = str(guild_id)

    # Initialize guild data if it doesn't exist
    if guild_str not in data:
        data[guild_str] = {
            "config": {},
            "active_tickets": {}
        }

    # Update config
    data[guild_str]["config"] = {
        "staff_role": str(staff_role_id),
        "log_channel": str(log_channel_id),
        "ticket_channel": str(ticket_channel_id),
        "category_id": str(category_id) if category_id else None,
        "ticket_count": data[guild_str].get("config", {}).get("ticket_count", 0)
    }

    save_tickets(data)
    return data[guild_str]["config"]


def create_ticket(
    guild_id: int,
    channel_id: int,
    user_id: int,
    category: str
) -> int:
    """
    Create a new ticket record.
    Returns the ticket number.
    """
    data = load_tickets()
    guild_str = str(guild_id)

    if guild_str not in data:
        raise ValueError("Ticket system not configured for this guild")

    # Increment ticket count
    current_count = data[guild_str]["config"].get("ticket_count", 0)
    new_ticket_number = current_count + 1
    data[guild_str]["config"]["ticket_count"] = new_ticket_number

    # Create ticket record
    data[guild_str]["active_tickets"][str(channel_id)] = {
        "ticket_number": new_ticket_number,
        "user_id": str(user_id),
        "claimed_by": None,
        "category": category,
        "created_at": datetime.utcnow().isoformat(),
        "locked": False
    }

    save_tickets(data)
    return new_ticket_number


def get_ticket(guild_id: int, channel_id: int) -> Optional[Dict[str, Any]]:
    """
    Get ticket data by channel ID.
    Returns None if the ticket doesn't exist.
    """
    data = load_tickets()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data:
        return None

    return data[guild_str]["active_tickets"].get(channel_str)


def close_ticket(guild_id: int, channel_id: int) -> Optional[Dict[str, Any]]:
    """
    Remove a ticket from active tickets.
    Returns the ticket data before deletion, or None if not found.
    """
    data = load_tickets()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data:
        return None

    if channel_str not in data[guild_str]["active_tickets"]:
        return None

    # Get ticket data before deletion
    ticket_data = data[guild_str]["active_tickets"].pop(channel_str)

    save_tickets(data)
    return ticket_data


def claim_ticket(guild_id: int, channel_id: int, staff_id: int) -> bool:
    """
    Mark a ticket as claimed by a staff member.
    Returns True if successful, False if ticket not found.
    """
    data = load_tickets()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data:
        return False

    if channel_str not in data[guild_str]["active_tickets"]:
        return False

    data[guild_str]["active_tickets"][channel_str]["claimed_by"] = str(staff_id)

    save_tickets(data)
    return True


def lock_ticket(guild_id: int, channel_id: int) -> bool:
    """
    Mark a ticket as locked.
    Returns True if successful, False if ticket not found.
    """
    data = load_tickets()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data:
        return False

    if channel_str not in data[guild_str]["active_tickets"]:
        return False

    data[guild_str]["active_tickets"][channel_str]["locked"] = True

    save_tickets(data)
    return True


def unlock_ticket(guild_id: int, channel_id: int) -> bool:
    """
    Mark a ticket as unlocked.
    Returns True if successful, False if ticket not found.
    """
    data = load_tickets()
    guild_str = str(guild_id)
    channel_str = str(channel_id)

    if guild_str not in data:
        return False

    if channel_str not in data[guild_str]["active_tickets"]:
        return False

    data[guild_str]["active_tickets"][channel_str]["locked"] = False

    save_tickets(data)
    return True


def get_all_active_tickets(guild_id: int) -> Dict[str, Dict[str, Any]]:
    """
    Get all active tickets for a guild.
    Returns empty dict if none found.
    """
    data = load_tickets()
    guild_str = str(guild_id)

    if guild_str not in data:
        return {}

    return data[guild_str].get("active_tickets", {})


def format_ticket_number(number: int) -> str:
    """Format ticket number as 4-digit string (e.g., 0001)."""
    return f"{number:04d}"
