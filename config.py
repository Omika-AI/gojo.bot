"""
Configuration file for Gojo Discord Bot
Loads environment variables and stores bot settings
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Discord Bot Token - Required to connect to Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# OpenRouter API Key - Used for AI features
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OpenRouter API endpoint
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Spotify API Credentials - Used for music features
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Bot settings
BOT_NAME = "Gojo"
BOT_VERSION = "1.0.0"
BOT_DESCRIPTION = "A Discord bot with AI capabilities"

# Validate required environment variables
def validate_config() -> bool:
    """Check that all required environment variables are set"""
    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN is not set in .env file")
        return False
    return True
