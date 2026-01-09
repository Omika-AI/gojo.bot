"""
Backfill Command
Scan historical messages and sync economy data to achievement stats
This allows the bot to count messages sent before it started tracking
and sync gambling/economy stats to achievements

Admin-only command due to the API-intensive nature of scanning history
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from utils.logger import log_command, logger
from utils.achievements_data import (
    load_user_progress,
    save_user_progress,
    update_user_stat,
    check_and_complete_achievements
)

# Path to economy data
ECONOMY_FILE = Path(__file__).parent.parent / "data" / "economy.json"


def load_economy_data() -> dict:
    """Load economy data from file"""
    if ECONOMY_FILE.exists():
        try:
            with open(ECONOMY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading economy data: {e}")
    return {"guilds": {}}


class Backfill(commands.Cog):
    """Backfill historical message counts for achievements"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.is_scanning = False  # Prevent multiple scans at once

    @app_commands.command(
        name="backfill",
        description="[Admin] Sync all historical data: messages, gambling, balance, streaks"
    )
    @app_commands.describe(
        limit_per_channel="Max messages to scan per channel (default: 10000, max: 100000)",
        days_back="Only scan messages from the last X days (optional, scans all if not set)",
        skip_messages="Skip message scanning and only sync economy data (faster)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def backfill(
        self,
        interaction: discord.Interaction,
        limit_per_channel: Optional[int] = 10000,
        days_back: Optional[int] = None,
        skip_messages: Optional[bool] = False
    ):
        """Scan message history and sync economy data to achievement stats"""
        try:
            guild_name = interaction.guild.name if interaction.guild else "DM"
            log_command(str(interaction.user), interaction.user.id, "backfill", guild_name)

            # Check if in a guild
            if not interaction.guild:
                await interaction.response.send_message(
                    "This command can only be used in a server!",
                    ephemeral=True
                )
                return

            # Check if already scanning
            if self.is_scanning:
                await interaction.response.send_message(
                    "A scan is already in progress! Please wait for it to finish.",
                    ephemeral=True
                )
                return

            # Validate limit
            if limit_per_channel > 100000:
                limit_per_channel = 100000
            if limit_per_channel < 100:
                limit_per_channel = 100

            # Calculate date limit if days_back is set
            after_date = None
            if days_back:
                after_date = datetime.utcnow() - timedelta(days=days_back)

            # Defer since this will take a while
            await interaction.response.defer()

            self.is_scanning = True

            # Track results
            user_message_counts = {}
            total_messages = 0
            channels_scanned = 0
            errors = []
            updated_users = 0
            achievements_unlocked = 0
            economy_synced = 0

            # =====================================================
            # PART 1: MESSAGE SCANNING (unless skipped)
            # =====================================================
            if not skip_messages:
                # Get all text channels the bot can see
                text_channels = [
                    ch for ch in interaction.guild.channels
                    if isinstance(ch, discord.TextChannel)
                    and ch.permissions_for(interaction.guild.me).read_message_history
                ]

                if not text_channels:
                    errors.append("No channels accessible for message scanning")
                else:
                    # Create initial progress embed
                    embed = discord.Embed(
                        title="📊 Backfill in Progress",
                        description="Scanning message history and syncing economy data...",
                        color=discord.Color.blue()
                    )
                    embed.add_field(
                        name="Status",
                        value=f"Starting scan of {len(text_channels)} channels...",
                        inline=False
                    )
                    if days_back:
                        embed.add_field(
                            name="Date Range",
                            value=f"Last {days_back} days",
                            inline=True
                        )
                    embed.add_field(
                        name="Limit per Channel",
                        value=f"{limit_per_channel:,} messages",
                        inline=True
                    )

                    progress_msg = await interaction.followup.send(embed=embed)

                    # Scan each channel
                    for channel in text_channels:
                        try:
                            channel_messages = 0

                            # Fetch message history with rate limiting built-in
                            async for message in channel.history(
                                limit=limit_per_channel,
                                after=after_date,
                                oldest_first=False
                            ):
                                # Skip bot messages
                                if message.author.bot:
                                    continue

                                user_id = str(message.author.id)
                                user_message_counts[user_id] = user_message_counts.get(user_id, 0) + 1
                                total_messages += 1
                                channel_messages += 1

                                # Update progress every 500 messages
                                if total_messages % 500 == 0:
                                    embed.set_field_at(
                                        0,
                                        name="Status",
                                        value=(
                                            f"Scanning: **#{channel.name}**\n"
                                            f"Channels: {channels_scanned + 1}/{len(text_channels)}\n"
                                            f"Messages found: {total_messages:,}\n"
                                            f"Users found: {len(user_message_counts)}"
                                        ),
                                        inline=False
                                    )
                                    try:
                                        await progress_msg.edit(embed=embed)
                                    except:
                                        pass

                                    await asyncio.sleep(0.1)

                            channels_scanned += 1
                            logger.info(f"Backfill: Scanned #{channel.name} - {channel_messages} messages")

                        except discord.Forbidden:
                            errors.append(f"No access to #{channel.name}")
                        except Exception as e:
                            errors.append(f"Error in #{channel.name}: {str(e)[:50]}")
                            logger.error(f"Backfill error in {channel.name}: {e}")

                    # Update progress
                    embed.set_field_at(
                        0,
                        name="Status",
                        value=f"Updating {len(user_message_counts)} user message records...",
                        inline=False
                    )
                    try:
                        await progress_msg.edit(embed=embed)
                    except:
                        pass
            else:
                # Skip messages mode - just show economy sync
                embed = discord.Embed(
                    title="📊 Backfill in Progress",
                    description="Syncing economy data to achievements (message scan skipped)...",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Status",
                    value="Syncing economy data...",
                    inline=False
                )
                progress_msg = await interaction.followup.send(embed=embed)

            # =====================================================
            # PART 2: UPDATE MESSAGE COUNTS (if scanned)
            # =====================================================
            if user_message_counts:
                for user_id, message_count in user_message_counts.items():
                    try:
                        data = load_user_progress()

                        if user_id not in data:
                            data[user_id] = {
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

                        current = data[user_id].get("messages_sent", 0)
                        if message_count > current:
                            data[user_id]["messages_sent"] = message_count
                            updated_users += 1

                        save_user_progress(data)

                    except Exception as e:
                        logger.error(f"Error updating user {user_id} messages: {e}")

            # =====================================================
            # PART 3: SYNC ECONOMY DATA
            # =====================================================
            embed.set_field_at(
                0,
                name="Status",
                value="Syncing economy data (gambling, balance, streaks)...",
                inline=False
            )
            try:
                await progress_msg.edit(embed=embed)
            except:
                pass

            # Load economy data
            economy_data = load_economy_data()
            guild_id = str(interaction.guild.id)
            guild_economy = economy_data.get("guilds", {}).get(guild_id, {}).get("users", {})

            if guild_economy:
                achievement_data = load_user_progress()

                for user_id, eco_stats in guild_economy.items():
                    try:
                        # Initialize user if not exists
                        if user_id not in achievement_data:
                            achievement_data[user_id] = {
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

                        user_data = achievement_data[user_id]
                        synced = False

                        # Sync gambling winnings
                        total_won = eco_stats.get("total_won", 0)
                        if total_won > user_data.get("gambling_winnings", 0):
                            user_data["gambling_winnings"] = total_won
                            synced = True

                        # Sync peak balance
                        current_balance = eco_stats.get("balance", 0)
                        total_earned = eco_stats.get("total_earned", 0)
                        peak = max(current_balance, total_earned, user_data.get("peak_balance", 0))
                        if peak > user_data.get("peak_balance", 0):
                            user_data["peak_balance"] = peak
                            synced = True

                        # Sync daily streak
                        daily_streak = eco_stats.get("daily_streak", 0)
                        if daily_streak > user_data.get("max_daily_streak", 0):
                            user_data["max_daily_streak"] = daily_streak
                            synced = True

                        if synced:
                            economy_synced += 1

                    except Exception as e:
                        logger.error(f"Error syncing economy for user {user_id}: {e}")

                save_user_progress(achievement_data)

            # =====================================================
            # PART 4: CHECK ACHIEVEMENTS FOR ALL USERS
            # =====================================================
            embed.set_field_at(
                0,
                name="Status",
                value="Checking for newly unlocked achievements...",
                inline=False
            )
            try:
                await progress_msg.edit(embed=embed)
            except:
                pass

            # Get all users to check
            all_users = set(user_message_counts.keys()) | set(guild_economy.keys())
            for user_id in all_users:
                try:
                    newly_completed = check_and_complete_achievements(int(user_id))
                    achievements_unlocked += len(newly_completed)
                except Exception as e:
                    logger.error(f"Error checking achievements for {user_id}: {e}")

            # =====================================================
            # FINAL RESULTS
            # =====================================================
            self.is_scanning = False

            embed = discord.Embed(
                title="✅ Backfill Complete!",
                description="All historical data has been synced to achievements.",
                color=discord.Color.green()
            )

            # Build results summary
            results = []
            if not skip_messages:
                results.append(f"**Channels scanned:** {channels_scanned}")
                results.append(f"**Messages counted:** {total_messages:,}")
                results.append(f"**Message stats updated:** {updated_users} users")
            else:
                results.append("**Messages:** Skipped (use without skip_messages to scan)")

            results.append(f"**Economy synced:** {economy_synced} users")
            results.append(f"**Achievements unlocked:** {achievements_unlocked}")

            embed.add_field(
                name="📊 Results",
                value="\n".join(results),
                inline=False
            )

            # Show what was synced
            embed.add_field(
                name="📋 Data Synced",
                value=(
                    "• Message counts (Chat God achievement)\n"
                    "• Gambling winnings (High Roller achievement)\n"
                    "• Peak balance (Wealthy Elite achievement)\n"
                    "• Daily streak (Daily Devotee achievement)"
                ),
                inline=False
            )

            if errors:
                error_text = "\n".join(errors[:5])
                if len(errors) > 5:
                    error_text += f"\n...and {len(errors) - 5} more"
                embed.add_field(
                    name="⚠️ Issues",
                    value=error_text,
                    inline=False
                )

            embed.set_footer(text="Use /achievementstats to see updated progress!")

            await progress_msg.edit(embed=embed)

            logger.info(
                f"Backfill complete: {total_messages} messages, {economy_synced} economy synced, "
                f"{achievements_unlocked} achievements"
            )

        except Exception as e:
            self.is_scanning = False
            logger.error(f"Error in /backfill command: {e}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f"An error occurred during backfill: {str(e)[:100]}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"An error occurred during backfill: {str(e)[:100]}",
                        ephemeral=True
                    )
            except:
                pass

    @backfill.error
    async def backfill_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle permission errors"""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need **Administrator** permission to use this command!",
                ephemeral=True
            )
        else:
            logger.error(f"Backfill command error: {error}")
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Backfill cog to the bot"""
    await bot.add_cog(Backfill(bot))
