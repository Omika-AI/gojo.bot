"""
Achievements Data Module
Handles achievement definitions, progress tracking, and role rewards

Achievements grant Discord roles when completed.
Admins can configure role IDs later via /achievementsetup
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Path to achievements data file
DATA_DIR = Path(__file__).parent.parent / "data"
ACHIEVEMENTS_FILE = DATA_DIR / "achievements.json"
USER_PROGRESS_FILE = DATA_DIR / "user_achievements.json"


@dataclass
class Achievement:
    """Definition of an achievement"""
    id: str
    name: str
    description: str
    emoji: str
    goal: int
    stat_key: str  # Which stat to track
    role_id: Optional[int] = None  # Discord role ID to grant (set by admin)

    def check_completed(self, current_value: int) -> bool:
        """Check if achievement is completed"""
        return current_value >= self.goal


# =============================================================================
# ACHIEVEMENT DEFINITIONS - 10 Creative Achievements
# =============================================================================

ACHIEVEMENTS: Dict[str, Achievement] = {
    "chat_god": Achievement(
        id="chat_god",
        name="Chat God",
        description="Send 10,000 messages in any channel",
        emoji="💬",
        goal=10000,
        stat_key="messages_sent"
    ),
    "music_maestro": Achievement(
        id="music_maestro",
        name="Music Maestro",
        description="Play 100 songs with the bot",
        emoji="🎵",
        goal=100,
        stat_key="songs_played"
    ),
    "karaoke_star": Achievement(
        id="karaoke_star",
        name="Karaoke Star",
        description="Complete 25 karaoke sessions",
        emoji="🎤",
        goal=25,
        stat_key="karaoke_sessions"
    ),
    "high_roller": Achievement(
        id="high_roller",
        name="High Roller",
        description="Win 50,000 coins from gambling",
        emoji="🎰",
        goal=50000,
        stat_key="gambling_winnings"
    ),
    "lucky_streak": Achievement(
        id="lucky_streak",
        name="Lucky Streak",
        description="Win 10 gambles in a row",
        emoji="🍀",
        goal=10,
        stat_key="max_win_streak"
    ),
    "daily_devotee": Achievement(
        id="daily_devotee",
        name="Daily Devotee",
        description="Claim daily rewards 30 days in a row",
        emoji="📅",
        goal=30,
        stat_key="max_daily_streak"
    ),
    "voice_veteran": Achievement(
        id="voice_veteran",
        name="Voice Veteran",
        description="Spend 50 hours in voice channels",
        emoji="🎧",
        goal=180000,  # 50 hours in seconds
        stat_key="voice_time"
    ),
    "command_master": Achievement(
        id="command_master",
        name="Command Master",
        description="Use 500 bot commands",
        emoji="⚡",
        goal=500,
        stat_key="commands_used"
    ),
    "wealthy_elite": Achievement(
        id="wealthy_elite",
        name="Wealthy Elite",
        description="Have 100,000 coins at once",
        emoji="💎",
        goal=100000,
        stat_key="peak_balance"
    ),
    "duet_partner": Achievement(
        id="duet_partner",
        name="Duet Partner",
        description="Complete 10 karaoke duets",
        emoji="👯",
        goal=10,
        stat_key="karaoke_duets"
    ),
}


# =============================================================================
# DATA STORAGE FUNCTIONS
# =============================================================================

def _ensure_data_dir():
    """Ensure data directory exists"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_achievement_config() -> Dict:
    """Load achievement configuration (role IDs set by admins)"""
    _ensure_data_dir()
    if ACHIEVEMENTS_FILE.exists():
        try:
            with open(ACHIEVEMENTS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"role_ids": {}}


def save_achievement_config(config: Dict):
    """Save achievement configuration"""
    _ensure_data_dir()
    with open(ACHIEVEMENTS_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def load_user_progress() -> Dict:
    """Load all user progress data"""
    _ensure_data_dir()
    if USER_PROGRESS_FILE.exists():
        try:
            with open(USER_PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_user_progress(data: Dict):
    """Save user progress data"""
    _ensure_data_dir()
    with open(USER_PROGRESS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_user_stats(user_id: int) -> Dict:
    """Get a user's achievement stats"""
    data = load_user_progress()
    user_key = str(user_id)

    if user_key not in data:
        data[user_key] = {
            "messages_sent": 0,
            "songs_played": 0,
            "karaoke_sessions": 0,
            "karaoke_duets": 0,
            "gambling_winnings": 0,
            "max_win_streak": 0,
            "current_win_streak": 0,
            "max_daily_streak": 0,
            "voice_time": 0,
            "commands_used": 0,
            "peak_balance": 0,
            "completed_achievements": []
        }
        save_user_progress(data)

    return data[user_key]


def update_user_stat(user_id: int, stat_key: str, value: int = None, increment: int = None) -> Dict:
    """Update a user's stat. Use value for absolute, increment for adding."""
    data = load_user_progress()
    user_key = str(user_id)

    if user_key not in data:
        get_user_stats(user_id)  # Initialize
        data = load_user_progress()

    if increment is not None:
        data[user_key][stat_key] = data[user_key].get(stat_key, 0) + increment
    elif value is not None:
        # For "max" stats, only update if new value is higher
        if stat_key.startswith("max_") or stat_key == "peak_balance":
            data[user_key][stat_key] = max(data[user_key].get(stat_key, 0), value)
        else:
            data[user_key][stat_key] = value

    save_user_progress(data)
    return data[user_key]


def mark_achievement_completed(user_id: int, achievement_id: str):
    """Mark an achievement as completed for a user"""
    data = load_user_progress()
    user_key = str(user_id)

    if user_key not in data:
        get_user_stats(user_id)
        data = load_user_progress()

    if achievement_id not in data[user_key].get("completed_achievements", []):
        if "completed_achievements" not in data[user_key]:
            data[user_key]["completed_achievements"] = []
        data[user_key]["completed_achievements"].append(achievement_id)
        save_user_progress(data)


def get_achievement_role_id(achievement_id: str) -> Optional[int]:
    """Get the role ID for an achievement (if configured by admin)"""
    config = load_achievement_config()
    return config.get("role_ids", {}).get(achievement_id)


def set_achievement_role_id(achievement_id: str, role_id: int):
    """Set the role ID for an achievement (admin only)"""
    config = load_achievement_config()
    if "role_ids" not in config:
        config["role_ids"] = {}
    config["role_ids"][achievement_id] = role_id
    save_achievement_config(config)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_achievements() -> List[Achievement]:
    """Get all achievement definitions"""
    return list(ACHIEVEMENTS.values())


def get_achievement_by_id(achievement_id: str) -> Optional[Achievement]:
    """Get an achievement by its ID"""
    return ACHIEVEMENTS.get(achievement_id)


def get_user_achievement_progress(user_id: int, achievement_id: str) -> Tuple[int, int, float]:
    """
    Get user's progress on an achievement
    Returns: (current_value, goal, percentage)
    """
    achievement = get_achievement_by_id(achievement_id)
    if not achievement:
        return (0, 0, 0.0)

    stats = get_user_stats(user_id)
    current = stats.get(achievement.stat_key, 0)
    percentage = min(100.0, (current / achievement.goal) * 100)

    return (current, achievement.goal, percentage)


def check_and_complete_achievements(user_id: int) -> List[Achievement]:
    """
    Check all achievements and return list of newly completed ones
    """
    stats = get_user_stats(user_id)
    completed = stats.get("completed_achievements", [])
    newly_completed = []

    for achievement_id, achievement in ACHIEVEMENTS.items():
        if achievement_id in completed:
            continue

        current_value = stats.get(achievement.stat_key, 0)
        if achievement.check_completed(current_value):
            mark_achievement_completed(user_id, achievement_id)
            newly_completed.append(achievement)

    return newly_completed


def format_progress_bar(current: int, goal: int, bar_length: int = 15) -> str:
    """Format a progress bar string"""
    percentage = min(1.0, current / goal) if goal > 0 else 0
    filled = int(bar_length * percentage)
    bar = "▓" * filled + "░" * (bar_length - filled)
    return f"`[{bar}]`"


def format_stat_display(stat_key: str, value: int) -> str:
    """Format a stat value for display"""
    if stat_key == "voice_time":
        # Convert seconds to hours
        hours = value / 3600
        return f"{hours:.1f} hours"
    elif stat_key in ["gambling_winnings", "peak_balance"]:
        return f"{value:,} coins"
    else:
        return f"{value:,}"
