"""
Giveaways & Polls Database - Timed events with button entries

Schema for Giveaways:
- guild_id: Server ID
- giveaway_id: Unique ID
- message_id: Message with the giveaway
- channel_id: Channel containing the giveaway
- prize: What's being given away
- winners_count: Number of winners to pick
- host_id: User who created the giveaway
- ends_at: Timestamp when giveaway ends
- entries: List of user IDs who entered
- ended: Whether giveaway has ended
- winner_ids: List of winner user IDs (after ending)

Schema for Polls:
- guild_id: Server ID
- poll_id: Unique ID
- message_id: Message with the poll
- channel_id: Channel containing the poll
- question: The poll question
- options: List of {label, emoji, votes: [user_ids]}
- host_id: User who created the poll
- ends_at: Optional end timestamp
- ended: Whether poll has ended
- multiple_votes: Whether users can vote multiple options
"""

import os
import json
import random
from datetime import datetime
from typing import Optional, Dict, List

# File path for storing giveaways data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
GIVEAWAYS_FILE = os.path.join(DATA_DIR, 'giveaways.json')


def _load_data() -> dict:
    """Load giveaways/polls data from JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(GIVEAWAYS_FILE):
        try:
            with open(GIVEAWAYS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return {"guilds": {}}


def _save_data(data: dict):
    """Save giveaways/polls data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(GIVEAWAYS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _ensure_guild(data: dict, guild_id: int) -> dict:
    """Ensure guild data structure exists"""
    guild_str = str(guild_id)
    if guild_str not in data["guilds"]:
        data["guilds"][guild_str] = {
            "giveaways": [],
            "polls": [],
            "next_giveaway_id": 1,
            "next_poll_id": 1
        }
    return data["guilds"][guild_str]


# ============================================
# GIVEAWAY MANAGEMENT
# ============================================

def create_giveaway(
    guild_id: int,
    channel_id: int,
    message_id: int,
    prize: str,
    winners_count: int,
    host_id: int,
    ends_at: str,
    required_role_id: Optional[int] = None
) -> tuple[bool, int, str]:
    """
    Create a new giveaway

    Returns:
        (success, giveaway_id, message)
    """
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)

    giveaway_id = guild_data["next_giveaway_id"]
    guild_data["next_giveaway_id"] += 1

    giveaway = {
        "giveaway_id": giveaway_id,
        "message_id": message_id,
        "channel_id": channel_id,
        "prize": prize,
        "winners_count": winners_count,
        "host_id": host_id,
        "ends_at": ends_at,
        "created_at": datetime.utcnow().isoformat(),
        "entries": [],
        "ended": False,
        "winner_ids": [],
        "required_role_id": required_role_id
    }

    guild_data["giveaways"].append(giveaway)
    _save_data(data)
    return True, giveaway_id, "Giveaway created successfully!"


def enter_giveaway(guild_id: int, message_id: int, user_id: int) -> tuple[bool, str]:
    """Enter a user into a giveaway"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "Giveaway not found."

    for giveaway in data["guilds"][guild_str]["giveaways"]:
        if giveaway["message_id"] == message_id:
            if giveaway["ended"]:
                return False, "This giveaway has ended!"

            if user_id in giveaway["entries"]:
                return False, "You're already entered!"

            giveaway["entries"].append(user_id)
            _save_data(data)
            return True, f"You're entered! ({len(giveaway['entries'])} total entries)"

    return False, "Giveaway not found."


def leave_giveaway(guild_id: int, message_id: int, user_id: int) -> tuple[bool, str]:
    """Remove a user from a giveaway"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "Giveaway not found."

    for giveaway in data["guilds"][guild_str]["giveaways"]:
        if giveaway["message_id"] == message_id:
            if user_id in giveaway["entries"]:
                giveaway["entries"].remove(user_id)
                _save_data(data)
                return True, "You've left the giveaway."
            return False, "You weren't entered."

    return False, "Giveaway not found."


def end_giveaway(guild_id: int, message_id: int) -> tuple[bool, List[int], str]:
    """
    End a giveaway and pick winners

    Returns:
        (success, winner_ids, message)
    """
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, [], "Giveaway not found."

    for giveaway in data["guilds"][guild_str]["giveaways"]:
        if giveaway["message_id"] == message_id:
            if giveaway["ended"]:
                return False, giveaway["winner_ids"], "Giveaway already ended!"

            entries = giveaway["entries"]
            winners_count = min(giveaway["winners_count"], len(entries))

            if len(entries) == 0:
                giveaway["ended"] = True
                giveaway["winner_ids"] = []
                _save_data(data)
                return True, [], "No entries! No winner."

            # Pick random winners
            winners = random.sample(entries, winners_count)
            giveaway["winner_ids"] = winners
            giveaway["ended"] = True
            _save_data(data)

            return True, winners, f"Winners selected! ({len(winners)} winner(s))"

    return False, [], "Giveaway not found."


def reroll_giveaway(guild_id: int, message_id: int, count: int = 1) -> tuple[bool, List[int], str]:
    """Reroll winners for an ended giveaway"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, [], "Giveaway not found."

    for giveaway in data["guilds"][guild_str]["giveaways"]:
        if giveaway["message_id"] == message_id:
            if not giveaway["ended"]:
                return False, [], "Giveaway hasn't ended yet!"

            entries = giveaway["entries"]
            # Exclude previous winners if possible
            available = [e for e in entries if e not in giveaway["winner_ids"]]
            if not available:
                available = entries

            if not available:
                return False, [], "No entries to reroll from!"

            new_winners = random.sample(available, min(count, len(available)))
            giveaway["winner_ids"].extend(new_winners)
            _save_data(data)

            return True, new_winners, f"Rerolled {len(new_winners)} new winner(s)!"

    return False, [], "Giveaway not found."


def get_giveaway(guild_id: int, message_id: int) -> Optional[Dict]:
    """Get a giveaway by message ID"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return None

    for giveaway in data["guilds"][guild_str]["giveaways"]:
        if giveaway["message_id"] == message_id:
            return giveaway

    return None


def get_active_giveaways(guild_id: int) -> List[Dict]:
    """Get all active (not ended) giveaways for a guild"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return []

    return [g for g in data["guilds"][guild_str]["giveaways"] if not g["ended"]]


def get_all_giveaways(guild_id: int) -> List[Dict]:
    """Get all giveaways for a guild"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return []

    return data["guilds"][guild_str]["giveaways"]


def delete_giveaway(guild_id: int, message_id: int) -> tuple[bool, str]:
    """Delete a giveaway"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "Giveaway not found."

    giveaways = data["guilds"][guild_str]["giveaways"]
    for i, giveaway in enumerate(giveaways):
        if giveaway["message_id"] == message_id:
            giveaways.pop(i)
            _save_data(data)
            return True, "Giveaway deleted!"

    return False, "Giveaway not found."


# ============================================
# POLL MANAGEMENT
# ============================================

def create_poll(
    guild_id: int,
    channel_id: int,
    message_id: int,
    question: str,
    options: List[Dict],
    host_id: int,
    ends_at: Optional[str] = None,
    multiple_votes: bool = False
) -> tuple[bool, int, str]:
    """
    Create a new poll

    Args:
        options: List of {label, emoji}

    Returns:
        (success, poll_id, message)
    """
    data = _load_data()
    guild_data = _ensure_guild(data, guild_id)

    poll_id = guild_data["next_poll_id"]
    guild_data["next_poll_id"] += 1

    # Initialize votes for each option
    poll_options = []
    for opt in options:
        poll_options.append({
            "label": opt["label"],
            "emoji": opt.get("emoji", ""),
            "votes": []
        })

    poll = {
        "poll_id": poll_id,
        "message_id": message_id,
        "channel_id": channel_id,
        "question": question,
        "options": poll_options,
        "host_id": host_id,
        "created_at": datetime.utcnow().isoformat(),
        "ends_at": ends_at,
        "ended": False,
        "multiple_votes": multiple_votes
    }

    guild_data["polls"].append(poll)
    _save_data(data)
    return True, poll_id, "Poll created successfully!"


def vote_poll(guild_id: int, message_id: int, user_id: int, option_index: int) -> tuple[bool, str]:
    """Cast a vote in a poll"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "Poll not found."

    for poll in data["guilds"][guild_str]["polls"]:
        if poll["message_id"] == message_id:
            if poll["ended"]:
                return False, "This poll has ended!"

            if option_index < 0 or option_index >= len(poll["options"]):
                return False, "Invalid option."

            # Check if user already voted
            if not poll["multiple_votes"]:
                for opt in poll["options"]:
                    if user_id in opt["votes"]:
                        # Remove old vote
                        opt["votes"].remove(user_id)
                        break

            # Add vote to selected option
            if user_id in poll["options"][option_index]["votes"]:
                return False, "You already voted for this option!"

            poll["options"][option_index]["votes"].append(user_id)
            _save_data(data)
            return True, f"Vote cast for: {poll['options'][option_index]['label']}"

    return False, "Poll not found."


def unvote_poll(guild_id: int, message_id: int, user_id: int, option_index: int) -> tuple[bool, str]:
    """Remove a vote from a poll option"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "Poll not found."

    for poll in data["guilds"][guild_str]["polls"]:
        if poll["message_id"] == message_id:
            if poll["ended"]:
                return False, "This poll has ended!"

            if option_index < 0 or option_index >= len(poll["options"]):
                return False, "Invalid option."

            if user_id in poll["options"][option_index]["votes"]:
                poll["options"][option_index]["votes"].remove(user_id)
                _save_data(data)
                return True, "Vote removed."

            return False, "You haven't voted for this option."

    return False, "Poll not found."


def end_poll(guild_id: int, message_id: int) -> tuple[bool, Dict, str]:
    """End a poll and get results"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, {}, "Poll not found."

    for poll in data["guilds"][guild_str]["polls"]:
        if poll["message_id"] == message_id:
            poll["ended"] = True
            _save_data(data)
            return True, poll, "Poll ended!"

    return False, {}, "Poll not found."


def get_poll(guild_id: int, message_id: int) -> Optional[Dict]:
    """Get a poll by message ID"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return None

    for poll in data["guilds"][guild_str]["polls"]:
        if poll["message_id"] == message_id:
            return poll

    return None


def get_active_polls(guild_id: int) -> List[Dict]:
    """Get all active polls for a guild"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return []

    return [p for p in data["guilds"][guild_str]["polls"] if not p["ended"]]


def delete_poll(guild_id: int, message_id: int) -> tuple[bool, str]:
    """Delete a poll"""
    data = _load_data()
    guild_str = str(guild_id)

    if guild_str not in data["guilds"]:
        return False, "Poll not found."

    polls = data["guilds"][guild_str]["polls"]
    for i, poll in enumerate(polls):
        if poll["message_id"] == message_id:
            polls.pop(i)
            _save_data(data)
            return True, "Poll deleted!"

    return False, "Poll not found."
