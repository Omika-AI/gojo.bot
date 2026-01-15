"""
Reminders Database - Personal reminder system

Schema:
- user_id: User who set the reminder
- reminder_id: Unique ID
- guild_id: Server where reminder was set (for context)
- channel_id: Channel where reminder was set
- message: Reminder message
- remind_at: Timestamp when to remind
- created_at: When reminder was created
- completed: Whether reminder was sent
- repeat: Optional repeat interval ("daily", "weekly", None)
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, List

# File path for storing reminders data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
REMINDERS_FILE = os.path.join(DATA_DIR, 'reminders.json')


def _load_data() -> dict:
    """Load reminders data from JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return {"reminders": [], "next_id": 1}


def _save_data(data: dict):
    """Save reminders data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REMINDERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


# ============================================
# REMINDER MANAGEMENT
# ============================================

def create_reminder(
    user_id: int,
    guild_id: int,
    channel_id: int,
    message: str,
    remind_at: str,
    repeat: Optional[str] = None
) -> tuple[bool, int, str]:
    """
    Create a new reminder

    Args:
        user_id: User who set the reminder
        guild_id: Server ID
        channel_id: Channel ID
        message: Reminder message
        remind_at: ISO timestamp when to remind
        repeat: Optional "daily" or "weekly"

    Returns:
        (success, reminder_id, message)
    """
    data = _load_data()

    reminder_id = data["next_id"]
    data["next_id"] += 1

    reminder = {
        "reminder_id": reminder_id,
        "user_id": user_id,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "message": message,
        "remind_at": remind_at,
        "created_at": datetime.utcnow().isoformat(),
        "completed": False,
        "repeat": repeat
    }

    data["reminders"].append(reminder)
    _save_data(data)
    return True, reminder_id, "Reminder set!"


def get_reminder(reminder_id: int) -> Optional[Dict]:
    """Get a reminder by ID"""
    data = _load_data()

    for reminder in data["reminders"]:
        if reminder["reminder_id"] == reminder_id:
            return reminder

    return None


def get_user_reminders(user_id: int, include_completed: bool = False) -> List[Dict]:
    """Get all reminders for a user"""
    data = _load_data()

    reminders = []
    for reminder in data["reminders"]:
        if reminder["user_id"] == user_id:
            if include_completed or not reminder["completed"]:
                reminders.append(reminder)

    return sorted(reminders, key=lambda x: x["remind_at"])


def get_pending_reminders() -> List[Dict]:
    """Get all reminders that need to be sent (remind_at <= now)"""
    data = _load_data()
    now = datetime.utcnow().isoformat()

    pending = []
    for reminder in data["reminders"]:
        if not reminder["completed"] and reminder["remind_at"] <= now:
            pending.append(reminder)

    return pending


def complete_reminder(reminder_id: int) -> tuple[bool, str]:
    """Mark a reminder as completed"""
    data = _load_data()

    for reminder in data["reminders"]:
        if reminder["reminder_id"] == reminder_id:
            reminder["completed"] = True
            _save_data(data)
            return True, "Reminder completed!"

    return False, "Reminder not found."


def reschedule_reminder(reminder_id: int, new_remind_at: str) -> tuple[bool, str]:
    """Reschedule a reminder (for repeating reminders)"""
    data = _load_data()

    for reminder in data["reminders"]:
        if reminder["reminder_id"] == reminder_id:
            reminder["remind_at"] = new_remind_at
            reminder["completed"] = False
            _save_data(data)
            return True, "Reminder rescheduled!"

    return False, "Reminder not found."


def delete_reminder(reminder_id: int, user_id: int) -> tuple[bool, str]:
    """Delete a reminder (user must own it)"""
    data = _load_data()

    for i, reminder in enumerate(data["reminders"]):
        if reminder["reminder_id"] == reminder_id:
            if reminder["user_id"] != user_id:
                return False, "You can only delete your own reminders!"
            data["reminders"].pop(i)
            _save_data(data)
            return True, "Reminder deleted!"

    return False, "Reminder not found."


def delete_all_user_reminders(user_id: int) -> int:
    """Delete all reminders for a user, returns count deleted"""
    data = _load_data()

    original_count = len(data["reminders"])
    data["reminders"] = [r for r in data["reminders"] if r["user_id"] != user_id]
    deleted = original_count - len(data["reminders"])

    _save_data(data)
    return deleted


def cleanup_old_reminders(days: int = 30) -> int:
    """Remove completed reminders older than X days"""
    data = _load_data()
    from datetime import timedelta

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    original_count = len(data["reminders"])

    data["reminders"] = [
        r for r in data["reminders"]
        if not r["completed"] or r["created_at"] > cutoff
    ]

    deleted = original_count - len(data["reminders"])
    if deleted > 0:
        _save_data(data)

    return deleted


def get_reminder_count(user_id: int) -> int:
    """Get count of active reminders for a user"""
    data = _load_data()

    count = 0
    for reminder in data["reminders"]:
        if reminder["user_id"] == user_id and not reminder["completed"]:
            count += 1

    return count
