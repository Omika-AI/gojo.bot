"""
Internationalization (i18n) - Multilingual Support

Provides translation functions for bot messages.
Supports multiple languages with fallback to English.
"""

import os
import json
from typing import Optional, Dict

from utils.server_config_db import get_server_language

# Translation files directory
TRANSLATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'translations')

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "da": "Dansk",
    "de": "Deutsch",
    "es": "Espanol",
    "fr": "Francais",
    "pt": "Portugues",
    "nl": "Nederlands",
    "it": "Italiano",
    "pl": "Polski",
    "ru": "Russkij",
    "ja": "Nihongo",
    "ko": "Hangugeo",
    "zh": "Zhongwen"
}

# Cache for loaded translations
_translations_cache: Dict[str, Dict] = {}


def _ensure_translations_dir():
    """Create translations directory if it doesn't exist"""
    os.makedirs(TRANSLATIONS_DIR, exist_ok=True)


def _load_language(lang_code: str) -> Dict:
    """Load translations for a specific language"""
    if lang_code in _translations_cache:
        return _translations_cache[lang_code]

    _ensure_translations_dir()
    file_path = os.path.join(TRANSLATIONS_DIR, f"{lang_code}.json")

    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                translations = json.load(f)
                _translations_cache[lang_code] = translations
                return translations
        except (json.JSONDecodeError, IOError):
            pass

    return {}


def _get_fallback() -> Dict:
    """Get English translations as fallback"""
    return _load_language("en")


def translate(key: str, guild_id: Optional[int] = None, lang: Optional[str] = None, **kwargs) -> str:
    """
    Get a translated string

    Args:
        key: Translation key (e.g., "welcome.message", "errors.no_permission")
        guild_id: Guild ID to get language setting from
        lang: Override language code
        **kwargs: Variables to interpolate into the string

    Returns:
        Translated string, or the key if not found
    """
    # Determine language
    if lang:
        language = lang
    elif guild_id:
        language = get_server_language(guild_id)
    else:
        language = "en"

    # Load translations
    translations = _load_language(language)

    # Navigate nested keys
    keys = key.split(".")
    value = translations

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            # Try fallback
            fallback = _get_fallback()
            value = fallback
            for k2 in keys:
                if isinstance(value, dict) and k2 in value:
                    value = value[k2]
                else:
                    return key  # Key not found
            break

    if not isinstance(value, str):
        return key

    # Interpolate variables
    try:
        return value.format(**kwargs)
    except KeyError:
        return value


def t(key: str, guild_id: Optional[int] = None, **kwargs) -> str:
    """Shorthand for translate()"""
    return translate(key, guild_id, **kwargs)


def get_supported_languages() -> Dict[str, str]:
    """Get dict of supported language codes and names"""
    return SUPPORTED_LANGUAGES.copy()


def is_supported(lang_code: str) -> bool:
    """Check if a language is supported"""
    return lang_code in SUPPORTED_LANGUAGES


def create_default_translations():
    """Create default English translation file"""
    _ensure_translations_dir()

    english = {
        "common": {
            "yes": "Yes",
            "no": "No",
            "enabled": "Enabled",
            "disabled": "Disabled",
            "success": "Success!",
            "error": "Error",
            "loading": "Loading...",
            "none": "None",
            "unknown": "Unknown"
        },
        "errors": {
            "no_permission": "You don't have permission to use this command!",
            "bot_no_permission": "I don't have permission to do that!",
            "invalid_user": "Invalid user!",
            "invalid_channel": "Invalid channel!",
            "invalid_role": "Invalid role!",
            "command_failed": "Command failed. Please try again.",
            "cooldown": "Please wait {seconds} seconds before using this command again.",
            "server_only": "This command can only be used in a server!"
        },
        "welcome": {
            "title": "Welcome!",
            "message": "Welcome to {server}, {user}!",
            "member_count": "You are member #{count}",
            "dm_message": "Welcome to **{server}**! Check out our rules and enjoy your stay!"
        },
        "goodbye": {
            "title": "Goodbye!",
            "message": "Goodbye {user}! We'll miss you!",
            "left": "{user} has left the server"
        },
        "economy": {
            "balance": "Balance",
            "coins": "coins",
            "daily_claimed": "You claimed your daily reward!",
            "daily_cooldown": "You can claim again in {time}",
            "not_enough": "You don't have enough coins!",
            "transferred": "Successfully transferred {amount} coins to {user}!"
        },
        "leveling": {
            "level_up": "Level Up!",
            "level_up_message": "Congratulations {user}! You reached level {level}!",
            "rank": "Rank",
            "xp": "XP",
            "level": "Level"
        },
        "moderation": {
            "warned": "{user} has been warned!",
            "kicked": "{user} has been kicked!",
            "banned": "{user} has been banned!",
            "unbanned": "{user} has been unbanned!",
            "muted": "{user} has been muted!",
            "unmuted": "{user} has been unmuted!",
            "reason": "Reason"
        },
        "games": {
            "trivia_correct": "Correct!",
            "trivia_wrong": "Wrong! The answer was: {answer}",
            "you_win": "You win!",
            "you_lose": "You lose!",
            "tie": "It's a tie!"
        },
        "reminders": {
            "reminder_set": "Reminder set!",
            "reminder_sent": "Reminder!",
            "no_reminders": "You don't have any reminders."
        },
        "giveaway": {
            "title": "GIVEAWAY!",
            "ended": "Giveaway Ended!",
            "winner": "Winner",
            "winners": "Winners",
            "no_entries": "No entries!",
            "enter": "Enter",
            "entries": "Entries"
        },
        "poll": {
            "title": "Poll",
            "ended": "Poll Ended",
            "votes": "votes",
            "total_votes": "Total votes"
        },
        "config": {
            "language_set": "Server language set to {language}!",
            "language_unsupported": "Language not supported!",
            "settings_updated": "Settings updated!"
        }
    }

    file_path = os.path.join(TRANSLATIONS_DIR, "en.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(english, f, indent=2, ensure_ascii=False)

    # Also create Danish as an example
    danish = {
        "common": {
            "yes": "Ja",
            "no": "Nej",
            "enabled": "Aktiveret",
            "disabled": "Deaktiveret",
            "success": "Succes!",
            "error": "Fejl",
            "loading": "Indlaeser...",
            "none": "Ingen",
            "unknown": "Ukendt"
        },
        "errors": {
            "no_permission": "Du har ikke tilladelse til at bruge denne kommando!",
            "bot_no_permission": "Jeg har ikke tilladelse til at goere det!",
            "invalid_user": "Ugyldig bruger!",
            "invalid_channel": "Ugyldig kanal!",
            "invalid_role": "Ugyldig rolle!",
            "command_failed": "Kommandoen mislykkedes. Proev igen.",
            "cooldown": "Vent venligst {seconds} sekunder foer du bruger denne kommando igen.",
            "server_only": "Denne kommando kan kun bruges paa en server!"
        },
        "welcome": {
            "title": "Velkommen!",
            "message": "Velkommen til {server}, {user}!",
            "member_count": "Du er medlem #{count}",
            "dm_message": "Velkommen til **{server}**! Tjek vores regler og nyd dit ophold!"
        },
        "goodbye": {
            "title": "Farvel!",
            "message": "Farvel {user}! Vi vil savne dig!",
            "left": "{user} har forladt serveren"
        },
        "economy": {
            "balance": "Saldo",
            "coins": "moenter",
            "daily_claimed": "Du har modtaget din daglige beloening!",
            "daily_cooldown": "Du kan kraeve igen om {time}",
            "not_enough": "Du har ikke nok moenter!",
            "transferred": "Overforslen af {amount} moenter til {user} lykkedes!"
        },
        "leveling": {
            "level_up": "Niveau Op!",
            "level_up_message": "Tillykke {user}! Du naaede niveau {level}!",
            "rank": "Rang",
            "xp": "XP",
            "level": "Niveau"
        },
        "moderation": {
            "warned": "{user} har faaet en advarsel!",
            "kicked": "{user} er blevet smidt ud!",
            "banned": "{user} er blevet bandlyst!",
            "unbanned": "{user} er ikke laengere bandlyst!",
            "muted": "{user} er blevet muted!",
            "unmuted": "{user} er ikke laengere muted!",
            "reason": "Aarsag"
        },
        "games": {
            "trivia_correct": "Rigtigt!",
            "trivia_wrong": "Forkert! Svaret var: {answer}",
            "you_win": "Du vinder!",
            "you_lose": "Du taber!",
            "tie": "Det er uafgjort!"
        },
        "reminders": {
            "reminder_set": "Paemindelse sat!",
            "reminder_sent": "Paemindelse!",
            "no_reminders": "Du har ingen paemindelser."
        },
        "giveaway": {
            "title": "GIVEAWAY!",
            "ended": "Giveaway Afsluttet!",
            "winner": "Vinder",
            "winners": "Vindere",
            "no_entries": "Ingen deltagere!",
            "enter": "Deltag",
            "entries": "Deltagere"
        },
        "poll": {
            "title": "Afstemning",
            "ended": "Afstemning Afsluttet",
            "votes": "stemmer",
            "total_votes": "Totale stemmer"
        },
        "config": {
            "language_set": "Serversprog sat til {language}!",
            "language_unsupported": "Sprog understøttes ikke!",
            "settings_updated": "Indstillinger opdateret!"
        }
    }

    file_path = os.path.join(TRANSLATIONS_DIR, "da.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(danish, f, indent=2, ensure_ascii=False)


# Create default translations on module load
create_default_translations()
