"""
Webhook Storage Utility
Handles saving and loading webhook data to/from JSON file
"""

import json
import os
from typing import Dict, Optional, List
from datetime import datetime

from utils.logger import logger

# Path to the webhooks data file
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
WEBHOOKS_FILE = os.path.join(DATA_DIR, "webhooks.json")


def _ensure_data_dir():
    """Make sure the data directory exists"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def _load_webhooks() -> Dict:
    """Load webhooks data from file"""
    _ensure_data_dir()

    if not os.path.exists(WEBHOOKS_FILE):
        return {}

    try:
        with open(WEBHOOKS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load webhooks data: {e}")
        return {}


def _save_webhooks(data: Dict) -> bool:
    """Save webhooks data to file"""
    _ensure_data_dir()

    try:
        with open(WEBHOOKS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        logger.error(f"Failed to save webhooks data: {e}")
        return False


def save_webhook(
    guild_id: int,
    channel_id: int,
    webhook_id: int,
    webhook_url: str,
    webhook_name: str,
    created_by: int
) -> bool:
    """
    Save a webhook to storage

    Args:
        guild_id: The server ID
        channel_id: The channel ID where webhook was created
        webhook_id: The webhook's ID
        webhook_url: The webhook URL for sending messages
        webhook_name: Display name of the webhook
        created_by: User ID who created the webhook

    Returns:
        True if saved successfully, False otherwise
    """
    data = _load_webhooks()

    # Convert IDs to strings for JSON compatibility
    guild_key = str(guild_id)
    channel_key = str(channel_id)
    webhook_key = str(webhook_id)

    # Initialize nested structure if needed
    if guild_key not in data:
        data[guild_key] = {}
    if channel_key not in data[guild_key]:
        data[guild_key][channel_key] = {}

    # Save webhook info
    data[guild_key][channel_key][webhook_key] = {
        "url": webhook_url,
        "name": webhook_name,
        "created_by": str(created_by),
        "created_at": datetime.utcnow().isoformat()
    }

    return _save_webhooks(data)


def get_channel_webhooks(guild_id: int, channel_id: int) -> List[Dict]:
    """
    Get all saved webhooks for a channel

    Args:
        guild_id: The server ID
        channel_id: The channel ID

    Returns:
        List of webhook info dicts with keys: id, url, name, created_by, created_at
    """
    data = _load_webhooks()

    guild_key = str(guild_id)
    channel_key = str(channel_id)

    if guild_key not in data or channel_key not in data[guild_key]:
        return []

    webhooks = []
    for webhook_id, info in data[guild_key][channel_key].items():
        webhooks.append({
            "id": int(webhook_id),
            "url": info["url"],
            "name": info["name"],
            "created_by": int(info["created_by"]),
            "created_at": info["created_at"]
        })

    return webhooks


def get_webhook_url(guild_id: int, channel_id: int, webhook_id: int) -> Optional[str]:
    """
    Get a specific webhook's URL

    Args:
        guild_id: The server ID
        channel_id: The channel ID
        webhook_id: The webhook ID

    Returns:
        The webhook URL or None if not found
    """
    data = _load_webhooks()

    guild_key = str(guild_id)
    channel_key = str(channel_id)
    webhook_key = str(webhook_id)

    try:
        return data[guild_key][channel_key][webhook_key]["url"]
    except KeyError:
        return None


def delete_webhook(guild_id: int, channel_id: int, webhook_id: int) -> bool:
    """
    Remove a webhook from storage

    Args:
        guild_id: The server ID
        channel_id: The channel ID
        webhook_id: The webhook ID

    Returns:
        True if deleted, False if not found or error
    """
    data = _load_webhooks()

    guild_key = str(guild_id)
    channel_key = str(channel_id)
    webhook_key = str(webhook_id)

    try:
        del data[guild_key][channel_key][webhook_key]

        # Clean up empty nested dicts
        if not data[guild_key][channel_key]:
            del data[guild_key][channel_key]
        if not data[guild_key]:
            del data[guild_key]

        return _save_webhooks(data)
    except KeyError:
        return False


def update_webhook_name(guild_id: int, channel_id: int, webhook_id: int, new_name: str) -> bool:
    """
    Update a webhook's display name in storage

    Args:
        guild_id: The server ID
        channel_id: The channel ID
        webhook_id: The webhook ID
        new_name: New display name

    Returns:
        True if updated, False if not found or error
    """
    data = _load_webhooks()

    guild_key = str(guild_id)
    channel_key = str(channel_id)
    webhook_key = str(webhook_id)

    try:
        data[guild_key][channel_key][webhook_key]["name"] = new_name
        return _save_webhooks(data)
    except KeyError:
        return False
