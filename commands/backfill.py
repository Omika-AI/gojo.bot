"""
Backfill Command
Scan historical messages to update achievement stats (messages_sent)
This allows the bot to count messages sent before it started tracking

Admin-only command due to the API-intensive nature of scanning history
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import asyncio
from datetime import datetime, timedelta

from utils.logger import log_command, logger
from utils.achievements_data import (
    load_user_progress,
    save_user_progress,
    update_user_stat,
    check_and_complete_achievements
)


class Backfill(commands.Cog):
    """Backfill historical message counts for achievements"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.is_scanning = False  # Prevent multiple scans at once

    @app_commands.command(
        name="backfill",
        description="[Admin] Scan message history to update achievement message counts"
    )
    @app_commands.describe(
        limit_per_channel="Max messages to scan per channel (default: 10000, max: 100000)",
        days_back="Only scan messages from the last X days (optional, scans all if not set)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def backfill(
        self,
        interaction: discord.Interaction,
        limit_per_channel: Optional[int] = 10000,
        days_back: Optional[int] = None
    ):
        """Scan message history and update message counts for all users"""
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

            # Get all text channels the bot can see
            text_channels = [
                ch for ch in interaction.guild.channels
                if isinstance(ch, discord.TextChannel)
                and ch.permissions_for(interaction.guild.me).read_message_history
            ]

            if not text_channels:
                await interaction.followup.send(
                    "I don't have permission to read message history in any channels!",
                    ephemeral=True
                )
                self.is_scanning = False
                return

            # Create initial progress embed
            embed = discord.Embed(
                title="📊 Backfill in Progress",
                description="Scanning message history to update achievement stats...",
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

            # Track message counts per user
            user_message_counts = {}
            total_messages = 0
            channels_scanned = 0
            errors = []

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

                        # Update progress every 500 messages to avoid rate limits on edits
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
                                pass  # Ignore edit failures

                            # Small delay to be nice to the API
                            await asyncio.sleep(0.1)

                    channels_scanned += 1
                    logger.info(f"Backfill: Scanned #{channel.name} - {channel_messages} messages")

                except discord.Forbidden:
                    errors.append(f"No access to #{channel.name}")
                except Exception as e:
                    errors.append(f"Error in #{channel.name}: {str(e)[:50]}")
                    logger.error(f"Backfill error in {channel.name}: {e}")

            # Now update user stats
            embed.set_field_at(
                0,
                name="Status",
                value=f"Updating {len(user_message_counts)} user records...",
                inline=False
            )
            try:
                await progress_msg.edit(embed=embed)
            except:
                pass

            # Load current progress and update
            updated_users = 0
            achievements_unlocked = 0

            for user_id, message_count in user_message_counts.items():
                try:
                    # Update the messages_sent stat (add to existing)
                    # We use the backfill count directly since this is a one-time sync
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

                    # Set the messages_sent to the backfill count
                    # (only if it's higher than current, to avoid losing progress)
                    current = data[user_id].get("messages_sent", 0)
                    if message_count > current:
                        data[user_id]["messages_sent"] = message_count
                        updated_users += 1

                    save_user_progress(data)

                    # Check for newly unlocked achievements
                    newly_completed = check_and_complete_achievements(int(user_id))
                    achievements_unlocked += len(newly_completed)

                except Exception as e:
                    logger.error(f"Error updating user {user_id}: {e}")

            # Final status
            self.is_scanning = False

            embed = discord.Embed(
                title="✅ Backfill Complete!",
                description="Message history has been scanned and stats updated.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📊 Results",
                value=(
                    f"**Channels scanned:** {channels_scanned}/{len(text_channels)}\n"
                    f"**Messages counted:** {total_messages:,}\n"
                    f"**Users found:** {len(user_message_counts)}\n"
                    f"**Users updated:** {updated_users}\n"
                    f"**Achievements unlocked:** {achievements_unlocked}"
                ),
                inline=False
            )

            if errors:
                error_text = "\n".join(errors[:5])  # Show max 5 errors
                if len(errors) > 5:
                    error_text += f"\n...and {len(errors) - 5} more"
                embed.add_field(
                    name="⚠️ Issues",
                    value=error_text,
                    inline=False
                )

            embed.set_footer(text="Users can now use /achievementstats to see updated progress!")

            await progress_msg.edit(embed=embed)

            logger.info(
                f"Backfill complete: {total_messages} messages, "
                f"{len(user_message_counts)} users, {achievements_unlocked} achievements"
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
