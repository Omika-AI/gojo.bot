"""
Gojo Discord Bot - Main Entry Point
This is the main file that starts the bot and loads all commands
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
from pathlib import Path

import config

# Create the bot instance with required intents
# Intents control what events the bot can receive from Discord
intents = discord.Intents.default()
intents.message_content = True  # Allows bot to read message content

# Create the bot with a command prefix (for text commands) and intents
bot = commands.Bot(command_prefix="!", intents=intents)

# Remove default help command so we can use our own
bot.remove_command("help")


@bot.event
async def on_ready():
    """Called when the bot successfully connects to Discord"""
    print(f"=" * 50)
    print(f"{config.BOT_NAME} is now online!")
    print(f"Bot Version: {config.BOT_VERSION}")
    print(f"Logged in as: {bot.user.name}")
    print(f"Bot ID: {bot.user.id}")
    print(f"=" * 50)

    # Sync slash commands with Discord
    # This makes the /commands appear in Discord
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


async def load_commands():
    """Load all command files from the commands directory"""
    commands_path = Path(__file__).parent / "commands"

    # Loop through all .py files in the commands folder
    for filename in os.listdir(commands_path):
        if filename.endswith(".py") and filename != "__init__.py":
            # Load the command as an extension
            try:
                await bot.load_extension(f"commands.{filename[:-3]}")
                print(f"Loaded command: {filename}")
            except Exception as e:
                print(f"Failed to load {filename}: {e}")


async def main():
    """Main function to start the bot"""
    # Validate configuration before starting
    if not config.validate_config():
        print("Bot cannot start due to configuration errors.")
        print("Please check your .env file and try again.")
        return

    # Load all commands from the commands folder
    await load_commands()

    # Start the bot with the Discord token
    try:
        await bot.start(config.DISCORD_TOKEN)
    except discord.LoginFailure:
        print("ERROR: Invalid Discord token. Please check your .env file.")
    except Exception as e:
        print(f"ERROR: Failed to start bot: {e}")


# Run the bot
if __name__ == "__main__":
    asyncio.run(main())
