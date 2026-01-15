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
from utils.achievements_data import update_user_stat, check_and_complete_achievements
from utils.leveling_db import add_message_xp, add_voice_xp
from utils.economy_db import add_coins
import time

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

# Track when users join voice channels (for voice_time achievement and XP)
# Stores: {user_id: {"time": timestamp, "guild_id": guild_id, "last_xp_minute": timestamp}}
voice_join_times: dict[int, dict] = {}


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

    # Start the voice XP background task
    bot.loop.create_task(voice_xp_task())


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


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Global error handler for slash commands"""
    # Log the error with full details
    command_name = interaction.command.name if interaction.command else "Unknown"
    log_error(error, f"Slash command error in /{command_name}")

    # Try to respond to the user
    error_msg = f"An error occurred: {str(error)}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(error_msg, ephemeral=True)
        else:
            await interaction.response.send_message(error_msg, ephemeral=True)
    except Exception:
        pass  # Can't respond, just log it


@bot.event
async def on_message(message: discord.Message):
    """Track messages sent for achievements and XP"""
    # Ignore bot messages
    if message.author.bot:
        return

    # Only track in guilds (not DMs)
    if message.guild:
        try:
            # Increment message count for achievements
            update_user_stat(message.author.id, "messages_sent", increment=1)
            # Check for newly completed achievements
            check_and_complete_achievements(message.author.id)

            # Add XP for the message (leveling system)
            xp_added, xp_amount, new_level, coin_reward = add_message_xp(
                message.guild.id,
                message.author.id
            )

            # If user leveled up, send a congratulations message
            if new_level is not None:
                # Build level up message
                level_msg = f"**{message.author.mention} leveled up to Level {new_level}!**"

                # If there's a coin reward for reaching a milestone
                if coin_reward is not None:
                    add_coins(message.guild.id, message.author.id, coin_reward, source="level_milestone")
                    level_msg += f"\n**Milestone Bonus:** You earned **{coin_reward:,} coins** for reaching Level {new_level}!"

                # Send level up notification
                try:
                    await message.channel.send(level_msg)
                    logger.info(f"[LEVEL UP] {message.author} reached Level {new_level} in {message.guild.name}")
                except discord.Forbidden:
                    pass  # Can't send messages in this channel

        except Exception as e:
            logger.error(f"Error tracking message for achievements/XP: {e}")

    # Process commands (important for prefix commands to work)
    await bot.process_commands(message)


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """Track voice channel time for achievements and XP"""
    # Ignore bots
    if member.bot:
        return

    try:
        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            # Store guild_id along with join time for XP tracking
            voice_join_times[member.id] = {
                "time": time.time(),
                "guild_id": member.guild.id,
                "last_xp_minute": time.time()
            }
            logger.info(f"[VC JOIN] {member.name} ({member.id}) joined #{after.channel.name} in {member.guild.name}")

        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            if member.id in voice_join_times:
                join_data = voice_join_times.pop(member.id)
                join_time = join_data["time"]
                guild_id = join_data["guild_id"]
                time_spent = int(time.time() - join_time)

                if time_spent > 0:
                    # Format time for logging
                    hours = time_spent // 3600
                    minutes = (time_spent % 3600) // 60
                    seconds = time_spent % 60
                    time_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"

                    # Update achievements
                    update_user_stat(member.id, "voice_time", increment=time_spent)
                    check_and_complete_achievements(member.id)

                    logger.info(f"[VC LEAVE] {member.name} ({member.id}) left #{before.channel.name} after {time_str}")
            else:
                # User was in VC before bot started tracking
                logger.info(f"[VC LEAVE] {member.name} ({member.id}) left #{before.channel.name} (time not tracked - joined before bot)")

        # User switched channels (still in voice, just moved)
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            logger.info(f"[VC SWITCH] {member.name} ({member.id}) moved from #{before.channel.name} to #{after.channel.name}")

    except Exception as e:
        logger.error(f"Error tracking voice time: {e}")


async def voice_xp_task():
    """Background task to award XP every minute to users in voice channels"""
    await bot.wait_until_ready()
    logger.info("[VOICE XP] Voice XP background task started")

    while not bot.is_closed():
        try:
            current_time = time.time()

            # Iterate through all tracked voice users
            for user_id, join_data in list(voice_join_times.items()):
                last_xp_minute = join_data.get("last_xp_minute", join_data["time"])
                guild_id = join_data["guild_id"]

                # Check if a minute has passed since last XP award
                minutes_elapsed = int((current_time - last_xp_minute) / 60)

                if minutes_elapsed >= 1:
                    # Award XP for each minute
                    xp_amount, new_level, coin_reward = add_voice_xp(guild_id, user_id, minutes_elapsed)

                    # Update the last XP time
                    voice_join_times[user_id]["last_xp_minute"] = current_time

                    # If user leveled up, try to notify them
                    if new_level is not None:
                        try:
                            # Find the user and their voice channel
                            guild = bot.get_guild(guild_id)
                            if guild:
                                member = guild.get_member(user_id)
                                if member and member.voice and member.voice.channel:
                                    # Build level up message
                                    level_msg = f"**{member.mention} leveled up to Level {new_level}!**"

                                    # If there's a coin reward for reaching a milestone
                                    if coin_reward is not None:
                                        add_coins(guild_id, user_id, coin_reward, source="level_milestone")
                                        level_msg += f"\n**Milestone Bonus:** You earned **{coin_reward:,} coins** for reaching Level {new_level}!"

                                    # Try to find a text channel to send the notification
                                    # Prefer a general or chat channel
                                    text_channel = None
                                    for channel in guild.text_channels:
                                        if channel.permissions_for(guild.me).send_messages:
                                            if any(name in channel.name.lower() for name in ['general', 'chat', 'bot', 'level']):
                                                text_channel = channel
                                                break
                                    if text_channel is None:
                                        # Fallback to first writable channel
                                        for channel in guild.text_channels:
                                            if channel.permissions_for(guild.me).send_messages:
                                                text_channel = channel
                                                break

                                    if text_channel:
                                        await text_channel.send(level_msg)
                                        logger.info(f"[LEVEL UP] {member} reached Level {new_level} in {guild.name} (from voice)")
                        except Exception as e:
                            logger.error(f"Error sending voice level up notification: {e}")

        except Exception as e:
            logger.error(f"Error in voice XP task: {e}")

        # Check every 30 seconds
        await asyncio.sleep(30)


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
