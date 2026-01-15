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
from utils.shop_db import has_active_xp_boost, get_expired_custom_roles, remove_custom_role_tracking, get_all_guilds_with_custom_roles
from utils.live_alerts_db import get_all_guilds_with_streamers, get_alert_channel, get_mention_role, update_streamer_status, get_all_guilds_with_feeds, get_news_channel, update_feed_last_post
from utils.quests_db import update_quest_progress
from utils.stocks_db import record_member_activity
from utils.tempvc_db import (
    get_join_to_create_channel,
    get_category_id,
    create_temp_vc,
    delete_temp_vc,
    is_temp_vc,
    get_default_name,
    get_vc_owner,
    transfer_ownership
)
import time
import aiohttp

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

    # Start background tasks
    bot.loop.create_task(voice_xp_task())
    bot.loop.create_task(live_alerts_task())
    bot.loop.create_task(auto_news_task())
    bot.loop.create_task(shop_cleanup_task())


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Called when the bot joins a new server - send welcome message"""
    logger.info(f"Joined new server: {guild.name} (ID: {guild.id})")

    # Try to send a welcome message to the first available text channel
    try:
        # Import the welcome view
        from commands.onboarding import WelcomeView

        # Find a suitable channel to send the welcome message
        target_channel = None

        # First, try to find a "general", "welcome", or "bot" channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                name_lower = channel.name.lower()
                if any(word in name_lower for word in ['general', 'welcome', 'bot', 'chat']):
                    target_channel = channel
                    break

        # Fallback to the first channel we can send to
        if not target_channel:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    target_channel = channel
                    break

        if target_channel:
            embed = discord.Embed(
                title=f"Thanks for adding {config.BOT_NAME}!",
                description=(
                    "I'm here to make your server more fun and engaging!\n\n"
                    "**What I can do:**\n"
                    "• Economy system with coins, gambling, and shops\n"
                    "• Leveling with XP and rank cards\n"
                    "• 50+ achievements to unlock\n"
                    "• Music player with playlists\n"
                    "• Daily quests and lootboxes\n"
                    "• Community stock market\n"
                    "• Moderation tools\n"
                    "• And much more!"
                ),
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Get Started",
                value=(
                    "**Admins:** Use `/setup` to configure the bot\n"
                    "**Everyone:** Use `/start` to learn the features\n"
                    "**Commands:** Use `/help` to see all commands"
                ),
                inline=False
            )

            embed.set_footer(text=f"{config.BOT_NAME} v{config.BOT_VERSION}")

            if bot.user:
                embed.set_thumbnail(url=bot.user.display_avatar.url)

            view = WelcomeView()
            await target_channel.send(embed=embed, view=view)
            logger.info(f"Sent welcome message to #{target_channel.name} in {guild.name}")

    except Exception as e:
        logger.error(f"Error sending welcome message to {guild.name}: {e}")


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

            # Track message for daily quests
            update_quest_progress(message.guild.id, message.author.id, "messages_sent", 1)

            # Track XP earned for quests (if XP was actually added)
            if xp_added and xp_amount > 0:
                update_quest_progress(message.guild.id, message.author.id, "xp_earned", xp_amount)

            # Track activity for stock market
            try:
                record_member_activity(message.guild.id, message.author.id, "messages", 1)
                if xp_added and xp_amount > 0:
                    record_member_activity(message.guild.id, message.author.id, "xp_earned", xp_amount)
            except:
                pass

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
    """Track voice channel time for achievements and XP, and handle temp VCs"""
    # Ignore bots
    if member.bot:
        return

    try:
        # =============================================
        # TEMP VC HANDLING
        # =============================================

        # Check if user joined the "Join to Create" channel
        if after.channel is not None:
            jtc_channel_id = get_join_to_create_channel(member.guild.id)

            if jtc_channel_id and after.channel.id == jtc_channel_id:
                # User joined the Join-to-Create channel - create a new temp VC
                category_id = get_category_id(member.guild.id)
                category = member.guild.get_channel(category_id) if category_id else None

                if category:
                    try:
                        # Get default name template
                        name_template = get_default_name(member.guild.id)
                        channel_name = name_template.replace("{user}", member.display_name)

                        # Create the new voice channel
                        new_channel = await member.guild.create_voice_channel(
                            name=channel_name,
                            category=category,
                            reason=f"Temp VC created for {member.display_name}"
                        )

                        # Give the owner permission to manage
                        await new_channel.set_permissions(
                            member,
                            connect=True,
                            speak=True,
                            stream=True,
                            mute_members=True,
                            deafen_members=True,
                            move_members=True
                        )

                        # Register in database
                        create_temp_vc(member.guild.id, new_channel.id, member.id, channel_name)

                        # Move the user to their new channel
                        await member.move_to(new_channel)

                        logger.info(f"[TEMP VC] Created '{channel_name}' for {member.name} in {member.guild.name}")

                        # Send a welcome message via DM
                        try:
                            embed = discord.Embed(
                                title="Your Voice Channel is Ready!",
                                description=f"I've created **{channel_name}** for you!",
                                color=discord.Color.green()
                            )
                            embed.add_field(
                                name="Controls",
                                value=(
                                    "Use `/tempvc panel` to:\n"
                                    "• Rename your channel\n"
                                    "• Set a user limit\n"
                                    "• Lock/unlock the channel\n"
                                    "• Kick, allow, or ban users\n"
                                    "• Transfer ownership"
                                ),
                                inline=False
                            )
                            embed.set_footer(text="The channel will be deleted when everyone leaves.")
                            await member.send(embed=embed)
                        except discord.Forbidden:
                            pass  # Can't DM user

                    except discord.Forbidden:
                        logger.error(f"[TEMP VC] No permission to create VC in {member.guild.name}")
                    except Exception as e:
                        logger.error(f"[TEMP VC] Error creating temp VC: {e}")

        # Check if a temp VC became empty (need to delete it)
        if before.channel is not None:
            if is_temp_vc(member.guild.id, before.channel.id):
                # Check if the channel is now empty
                if len(before.channel.members) == 0:
                    try:
                        # Delete from database
                        delete_temp_vc(member.guild.id, before.channel.id)

                        # Delete the Discord channel
                        await before.channel.delete(reason="Temp VC empty - auto cleanup")
                        logger.info(f"[TEMP VC] Deleted empty temp VC '{before.channel.name}' in {member.guild.name}")
                    except discord.NotFound:
                        # Channel already deleted
                        delete_temp_vc(member.guild.id, before.channel.id)
                    except discord.Forbidden:
                        logger.error(f"[TEMP VC] No permission to delete VC in {member.guild.name}")
                    except Exception as e:
                        logger.error(f"[TEMP VC] Error deleting temp VC: {e}")

                # Check if owner left - transfer ownership to next person
                elif member.id == get_vc_owner(member.guild.id, before.channel.id):
                    # Owner left but channel not empty - transfer to first remaining member
                    remaining_members = [m for m in before.channel.members if not m.bot]
                    if remaining_members:
                        new_owner = remaining_members[0]
                        transfer_ownership(member.guild.id, before.channel.id, new_owner.id)
                        logger.info(f"[TEMP VC] Ownership transferred to {new_owner.name} in '{before.channel.name}'")

                        # Notify new owner
                        try:
                            embed = discord.Embed(
                                title="You're Now the Channel Owner!",
                                description=f"The previous owner left, so you now control **{before.channel.name}**!",
                                color=discord.Color.gold()
                            )
                            embed.add_field(
                                name="Controls",
                                value="Use `/tempvc panel` to manage your channel!",
                                inline=False
                            )
                            await new_owner.send(embed=embed)
                        except discord.Forbidden:
                            pass

        # =============================================
        # XP & ACHIEVEMENTS TRACKING
        # =============================================

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
        logger.error(f"Error in voice state update: {e}")


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

                    # Track voice minutes for daily quests
                    update_quest_progress(guild_id, user_id, "voice_minutes", minutes_elapsed)

                    # Track XP earned for quests
                    if xp_amount > 0:
                        update_quest_progress(guild_id, user_id, "xp_earned", xp_amount)

                    # Track activity for stock market
                    try:
                        record_member_activity(guild_id, user_id, "voice_minutes", minutes_elapsed)
                        if xp_amount > 0:
                            record_member_activity(guild_id, user_id, "xp_earned", xp_amount)
                    except:
                        pass

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


async def live_alerts_task():
    """Background task to check if tracked streamers are live"""
    await bot.wait_until_ready()
    logger.info("[LIVE ALERTS] Live alerts background task started")

    while not bot.is_closed():
        try:
            guilds_with_streamers = get_all_guilds_with_streamers()

            for guild_id, streamers in guilds_with_streamers:
                guild = bot.get_guild(guild_id)
                if not guild:
                    continue

                alert_channel_id = get_alert_channel(guild_id)
                if not alert_channel_id:
                    continue

                alert_channel = guild.get_channel(alert_channel_id)
                if not alert_channel:
                    continue

                mention_role_id = get_mention_role(guild_id)

                for streamer in streamers:
                    try:
                        platform = streamer["platform"]
                        username = streamer["username"]
                        last_status = streamer.get("last_status", "offline")

                        is_live = False
                        stream_title = ""
                        stream_url = ""
                        thumbnail_url = ""

                        # Check Twitch
                        if platform == "twitch":
                            async with aiohttp.ClientSession() as session:
                                # Use Twitch's public endpoint (no auth needed for basic check)
                                url = f"https://decapi.me/twitch/uptime/{username}"
                                async with session.get(url) as response:
                                    if response.status == 200:
                                        text = await response.text()
                                        is_live = "offline" not in text.lower()
                                        if is_live:
                                            stream_url = f"https://twitch.tv/{username}"
                                            stream_title = f"{username} is now live on Twitch!"

                        # Check YouTube (using RSS feed)
                        elif platform == "youtube":
                            async with aiohttp.ClientSession() as session:
                                # Try to check if channel has a live stream
                                # This is a simplified check - full implementation would use YouTube API
                                url = f"https://www.youtube.com/@{username}/live"
                                async with session.get(url, allow_redirects=False) as response:
                                    # If it doesn't redirect, there might be a live stream
                                    is_live = response.status == 200
                                    if is_live:
                                        stream_url = f"https://www.youtube.com/@{username}/live"
                                        stream_title = f"{username} is now live on YouTube!"

                        # Send notification if went live
                        if is_live and last_status != "live":
                            embed = discord.Embed(
                                title=f"🔴 {username} is LIVE!",
                                description=stream_title,
                                color=discord.Color.red() if platform == "youtube" else discord.Color.purple(),
                                url=stream_url
                            )
                            embed.add_field(name="Platform", value=platform.title(), inline=True)
                            embed.add_field(name="Watch Now", value=f"[Click Here]({stream_url})", inline=True)
                            embed.set_footer(text=f"Live Alert • {platform.title()}")

                            # Build message content
                            content = ""
                            if mention_role_id:
                                role = guild.get_role(mention_role_id)
                                if role:
                                    content = role.mention

                            await alert_channel.send(content=content if content else None, embed=embed)
                            logger.info(f"[LIVE ALERT] {username} went live on {platform} in {guild.name}")

                        # Update status
                        new_status = "live" if is_live else "offline"
                        if new_status != last_status:
                            update_streamer_status(guild_id, platform, username, new_status, notified=is_live)

                    except Exception as e:
                        logger.error(f"Error checking streamer {streamer.get('username')}: {e}")

        except Exception as e:
            logger.error(f"Error in live alerts task: {e}")

        # Check every 5 minutes
        await asyncio.sleep(300)


async def auto_news_task():
    """Background task to fetch and post news from Reddit/RSS feeds"""
    await bot.wait_until_ready()
    logger.info("[AUTO NEWS] Auto news background task started")

    while not bot.is_closed():
        try:
            guilds_with_feeds = get_all_guilds_with_feeds()

            for guild_id, feeds in guilds_with_feeds:
                guild = bot.get_guild(guild_id)
                if not guild:
                    continue

                news_channel_id = get_news_channel(guild_id)
                if not news_channel_id:
                    continue

                news_channel = guild.get_channel(news_channel_id)
                if not news_channel:
                    continue

                for feed in feeds:
                    try:
                        feed_type = feed["type"]
                        feed_url = feed["url"]
                        last_post_id = feed.get("last_post_id")

                        if feed_type == "reddit":
                            # Parse subreddit and filter from URL
                            parts = feed_url.split("/")
                            subreddit = parts[0]
                            filter_type = parts[1] if len(parts) > 1 else "hot"

                            async with aiohttp.ClientSession() as session:
                                url = f"https://www.reddit.com/r/{subreddit}/{filter_type}.json?limit=1"
                                headers = {"User-Agent": "GojoBot/1.0"}
                                async with session.get(url, headers=headers) as response:
                                    if response.status == 200:
                                        data = await response.json()
                                        posts = data.get("data", {}).get("children", [])

                                        if posts:
                                            post = posts[0]["data"]
                                            post_id = post.get("id")

                                            # Only post if it's new
                                            if post_id and post_id != last_post_id:
                                                title = post.get("title", "No title")[:256]
                                                author = post.get("author", "Unknown")
                                                score = post.get("score", 0)
                                                permalink = f"https://reddit.com{post.get('permalink', '')}"
                                                thumbnail = post.get("thumbnail", "")

                                                embed = discord.Embed(
                                                    title=title,
                                                    url=permalink,
                                                    color=discord.Color.orange()
                                                )
                                                embed.set_author(name=f"r/{subreddit}", url=f"https://reddit.com/r/{subreddit}")
                                                embed.add_field(name="Author", value=f"u/{author}", inline=True)
                                                embed.add_field(name="Score", value=f"⬆️ {score:,}", inline=True)

                                                # Add image if available
                                                if thumbnail and thumbnail.startswith("http"):
                                                    embed.set_thumbnail(url=thumbnail)

                                                # Check for image post
                                                post_url = post.get("url", "")
                                                if any(ext in post_url for ext in [".jpg", ".jpeg", ".png", ".gif"]):
                                                    embed.set_image(url=post_url)

                                                embed.set_footer(text="Reddit • Auto News")

                                                await news_channel.send(embed=embed)
                                                update_feed_last_post(guild_id, feed_type, feed_url, post_id)
                                                logger.info(f"[AUTO NEWS] Posted from r/{subreddit} in {guild.name}")

                        elif feed_type == "rss":
                            # RSS feed parsing would require feedparser library
                            # For now, skip RSS feeds or add basic support
                            pass

                    except Exception as e:
                        logger.error(f"Error fetching feed {feed.get('url')}: {e}")

        except Exception as e:
            logger.error(f"Error in auto news task: {e}")

        # Check every 10 minutes
        await asyncio.sleep(600)


async def shop_cleanup_task():
    """Background task to clean up expired shop items (custom roles, etc.)"""
    await bot.wait_until_ready()
    logger.info("[SHOP] Shop cleanup background task started")

    while not bot.is_closed():
        try:
            guilds = get_all_guilds_with_custom_roles()

            for guild_id in guilds:
                guild = bot.get_guild(guild_id)
                if not guild:
                    continue

                # Get expired custom roles
                expired_roles = get_expired_custom_roles(guild_id)

                for role_id, user_id in expired_roles:
                    try:
                        role = guild.get_role(role_id)
                        if role:
                            # Remove the role from the user
                            member = guild.get_member(user_id)
                            if member:
                                await member.remove_roles(role, reason="Custom role expired")

                            # Delete the role
                            await role.delete(reason="Custom role expired")
                            logger.info(f"[SHOP] Deleted expired custom role '{role.name}' in {guild.name}")

                        # Remove from tracking
                        remove_custom_role_tracking(guild_id, role_id)

                    except discord.Forbidden:
                        logger.error(f"No permission to delete role {role_id} in {guild.name}")
                        remove_custom_role_tracking(guild_id, role_id)
                    except Exception as e:
                        logger.error(f"Error cleaning up role {role_id}: {e}")

        except Exception as e:
            logger.error(f"Error in shop cleanup task: {e}")

        # Check every 5 minutes
        await asyncio.sleep(300)


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
