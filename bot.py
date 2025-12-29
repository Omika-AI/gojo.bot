"""
Gojo Discord Bot - Main Entry Point
This is the main file that starts the bot and loads all commands
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import signal
from pathlib import Path

import config
from utils.logger import logger, log_startup, log_shutdown, log_error

# Create the bot instance with required intents
# Intents control what events the bot can receive from Discord
intents = discord.Intents.default()
intents.message_content = True  # Allows bot to read message content
intents.members = True  # Allows bot to access member info (for adminprofile command)
intents.presences = True  # Allows bot to see user status (online/offline/etc)

# Create the bot with a command prefix (for text commands) and intents
bot = commands.Bot(command_prefix="!", intents=intents)

# Remove default help command so we can use our own
bot.remove_command("help")


@bot.event
async def on_ready():
    """Called when the bot successfully connects to Discord"""
    logger.info("=" * 50)
    logger.info(f"{config.BOT_NAME} is now online!")
    logger.info(f"Bot Version: {config.BOT_VERSION}")
    logger.info(f"Logged in as: {bot.user.name}")
    logger.info(f"Bot ID: {bot.user.id}")
    logger.info(f"Connected to {len(bot.guilds)} server(s)")
    logger.info("=" * 50)

    # Sync slash commands with Discord
    # This makes the /commands appear in Discord
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        log_error(e, "Failed to sync commands")


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Called when the bot joins a new server"""
    logger.info(f"Joined new server: {guild.name} (ID: {guild.id})")


@bot.event
async def on_guild_remove(guild: discord.Guild):
    """Called when the bot is removed from a server"""
    logger.info(f"Removed from server: {guild.name} (ID: {guild.id})")


@bot.event
async def on_command_error(ctx, error):
    """Global error handler for text commands"""
    log_error(error, f"Command error in {ctx.command}")


async def load_commands():
    """Load all command files from the commands directory"""
    commands_path = Path(__file__).parent / "commands"
    loaded_count = 0

    # Loop through all .py files in the commands folder
    for filename in os.listdir(commands_path):
        if filename.endswith(".py") and filename != "__init__.py":
            # Load the command as an extension
            try:
                await bot.load_extension(f"commands.{filename[:-3]}")
                logger.info(f"Loaded command: {filename}")
                loaded_count += 1
            except Exception as e:
                log_error(e, f"Failed to load {filename}")

    logger.info(f"Total commands loaded: {loaded_count}")


async def main():
    """Main function to start the bot"""
    # Log startup
    log_startup()

    # Validate configuration before starting
    if not config.validate_config():
        logger.error("Bot cannot start due to configuration errors.")
        logger.error("Please check your .env file and try again.")
        return

    # Load all commands from the commands folder
    await load_commands()

    # Start the bot with the Discord token
    try:
        logger.info("Connecting to Discord...")
        await bot.start(config.DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid Discord token. Please check your .env file.")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        log_error(e, "Failed to start bot")
    finally:
        log_shutdown()


# Handle graceful shutdown on SIGTERM (from manage.sh stop)
def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Received shutdown signal...")
    asyncio.create_task(bot.close())


# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


# Run the bot
if __name__ == "__main__":
    asyncio.run(main())
