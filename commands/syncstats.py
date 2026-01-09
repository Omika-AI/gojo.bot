"""
Sync Stats Command
Synchronize economy data (gambling wins, balance, daily streak) to achievement stats
This allows retroactive tracking of achievements based on existing economy data

Admin-only command
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import json
from pathlib import Path

from utils.logger import log_command, logger
from utils.achievements_data import (
    load_user_progress,
    save_user_progress,
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


class SyncStats(commands.Cog):
    """Sync economy data to achievement stats"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="syncstats",
        description="[Admin] Sync economy data (gambling, balance, streaks) to achievement stats"
    )
    @app_commands.describe(
        user="Sync stats for a specific user only (optional - syncs all if not specified)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def syncstats(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Sync economy data to achievement stats"""
        try:
            guild_name = interaction.guild.name if interaction.guild else "DM"
            log_command(str(interaction.user), interaction.user.id, "syncstats", guild_name)

            if not interaction.guild:
                await interaction.response.send_message(
                    "This command can only be used in a server!",
                    ephemeral=True
                )
                return

            await interaction.response.defer()

            # Load economy data
            economy_data = load_economy_data()
            guild_id = str(interaction.guild.id)

            if guild_id not in economy_data.get("guilds", {}):
                await interaction.followup.send(
                    "No economy data found for this server!",
                    ephemeral=True
                )
                return

            guild_economy = economy_data["guilds"][guild_id].get("users", {})

            if not guild_economy:
                await interaction.followup.send(
                    "No user economy data found!",
                    ephemeral=True
                )
                return

            # Filter to specific user if provided
            if user:
                user_id = str(user.id)
                if user_id not in guild_economy:
                    await interaction.followup.send(
                        f"{user.mention} has no economy data to sync!",
                        ephemeral=True
                    )
                    return
                users_to_sync = {user_id: guild_economy[user_id]}
            else:
                users_to_sync = guild_economy

            # Load achievement progress
            achievement_data = load_user_progress()

            # Track changes
            users_updated = 0
            achievements_unlocked = 0
            stats_updated = {
                "gambling_winnings": 0,
                "peak_balance": 0,
                "max_daily_streak": 0
            }

            # Sync each user
            for user_id, eco_stats in users_to_sync.items():
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
                updated = False

                # Sync gambling winnings (total_won from economy)
                total_won = eco_stats.get("total_won", 0)
                if total_won > user_data.get("gambling_winnings", 0):
                    user_data["gambling_winnings"] = total_won
                    stats_updated["gambling_winnings"] += 1
                    updated = True

                # Sync peak balance (highest balance ever)
                current_balance = eco_stats.get("balance", 0)
                total_earned = eco_stats.get("total_earned", 0)
                # Use total_earned as a proxy for peak balance if it's higher
                peak = max(current_balance, total_earned, user_data.get("peak_balance", 0))
                if peak > user_data.get("peak_balance", 0):
                    user_data["peak_balance"] = peak
                    stats_updated["peak_balance"] += 1
                    updated = True

                # Sync daily streak
                daily_streak = eco_stats.get("daily_streak", 0)
                if daily_streak > user_data.get("max_daily_streak", 0):
                    user_data["max_daily_streak"] = daily_streak
                    stats_updated["max_daily_streak"] += 1
                    updated = True

                if updated:
                    users_updated += 1

            # Save updated achievement data
            save_user_progress(achievement_data)

            # Check for newly unlocked achievements
            for user_id in users_to_sync.keys():
                newly_completed = check_and_complete_achievements(int(user_id))
                achievements_unlocked += len(newly_completed)

            # Build result embed
            embed = discord.Embed(
                title="Stats Sync Complete!",
                description="Economy data has been synced to achievement stats.",
                color=discord.Color.green()
            )

            if user:
                embed.add_field(
                    name="User Synced",
                    value=user.mention,
                    inline=False
                )
            else:
                embed.add_field(
                    name="Users Processed",
                    value=f"{len(users_to_sync)} users",
                    inline=True
                )

            embed.add_field(
                name="Users Updated",
                value=f"{users_updated}",
                inline=True
            )

            embed.add_field(
                name="Achievements Unlocked",
                value=f"{achievements_unlocked}",
                inline=True
            )

            # Show what was synced
            sync_details = []
            if stats_updated["gambling_winnings"] > 0:
                sync_details.append(f"Gambling winnings: {stats_updated['gambling_winnings']} users")
            if stats_updated["peak_balance"] > 0:
                sync_details.append(f"Peak balance: {stats_updated['peak_balance']} users")
            if stats_updated["max_daily_streak"] > 0:
                sync_details.append(f"Daily streak: {stats_updated['max_daily_streak']} users")

            if sync_details:
                embed.add_field(
                    name="Stats Updated",
                    value="\n".join(sync_details),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Note",
                    value="No stats needed updating (achievement data was already up to date)",
                    inline=False
                )

            embed.set_footer(text="Use /achievementstats to see updated progress!")

            await interaction.followup.send(embed=embed)

            logger.info(
                f"Stats sync complete: {users_updated} users updated, "
                f"{achievements_unlocked} achievements unlocked"
            )

        except Exception as e:
            logger.error(f"Error in /syncstats command: {e}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f"An error occurred during sync: {str(e)[:100]}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"An error occurred during sync: {str(e)[:100]}",
                        ephemeral=True
                    )
            except:
                pass

    @syncstats.error
    async def syncstats_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle permission errors"""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need **Administrator** permission to use this command!",
                ephemeral=True
            )
        else:
            logger.error(f"Syncstats command error: {error}")
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )


# Required setup function
async def setup(bot: commands.Bot):
    """Add the SyncStats cog to the bot"""
    await bot.add_cog(SyncStats(bot))
