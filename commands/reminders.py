"""
Personal Reminders System - Set reminders that DM you

Commands:
- /remind - Set a personal reminder
- /reminders - View your active reminders
- /reminder delete - Delete a reminder
- /reminder clear - Clear all your reminders
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, Literal
from datetime import datetime, timedelta
import re

from utils.reminders_db import (
    create_reminder,
    get_reminder,
    get_user_reminders,
    get_pending_reminders,
    complete_reminder,
    reschedule_reminder,
    delete_reminder,
    delete_all_user_reminders,
    cleanup_old_reminders,
    get_reminder_count
)
from utils.logger import logger


def parse_duration(duration_str: str) -> Optional[timedelta]:
    """Parse a duration string like '1h30m', '2d', '1w' into a timedelta"""
    if not duration_str:
        return None

    total_seconds = 0
    duration_str = duration_str.lower().strip()

    # Pattern for matching duration components
    pattern = r'(\d+)\s*([mhdw])'
    matches = re.findall(pattern, duration_str)

    if not matches:
        return None

    for amount, unit in matches:
        amount = int(amount)
        if unit == 'm':
            total_seconds += amount * 60
        elif unit == 'h':
            total_seconds += amount * 3600
        elif unit == 'd':
            total_seconds += amount * 86400
        elif unit == 'w':
            total_seconds += amount * 604800

    if total_seconds == 0:
        return None

    return timedelta(seconds=total_seconds)


class Reminders(commands.Cog):
    """Personal reminder system"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_reminders.start()
        self.cleanup_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()
        self.cleanup_reminders.cancel()

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        """Check for pending reminders and send them"""
        pending = get_pending_reminders()

        for reminder in pending:
            try:
                user = self.bot.get_user(reminder["user_id"])
                if not user:
                    user = await self.bot.fetch_user(reminder["user_id"])

                if user:
                    # Create embed
                    embed = discord.Embed(
                        title="Reminder!",
                        description=reminder["message"],
                        color=discord.Color.blue(),
                        timestamp=datetime.utcnow()
                    )

                    # Add context
                    guild = self.bot.get_guild(reminder["guild_id"])
                    if guild:
                        embed.set_footer(text=f"From: {guild.name}")

                    # Try to DM the user
                    try:
                        await user.send(embed=embed)
                        logger.info(f"Reminder sent to {user.name}: {reminder['message'][:50]}")
                    except discord.Forbidden:
                        # Can't DM user, try to send in the original channel
                        channel = self.bot.get_channel(reminder["channel_id"])
                        if channel:
                            await channel.send(
                                f"{user.mention} **Reminder** (couldn't DM you):",
                                embed=embed
                            )

                    # Handle repeat
                    if reminder.get("repeat"):
                        # Reschedule
                        if reminder["repeat"] == "daily":
                            new_time = datetime.utcnow() + timedelta(days=1)
                        elif reminder["repeat"] == "weekly":
                            new_time = datetime.utcnow() + timedelta(weeks=1)
                        else:
                            new_time = None

                        if new_time:
                            reschedule_reminder(reminder["reminder_id"], new_time.isoformat())
                        else:
                            complete_reminder(reminder["reminder_id"])
                    else:
                        complete_reminder(reminder["reminder_id"])

            except Exception as e:
                logger.error(f"Error sending reminder: {e}")
                complete_reminder(reminder["reminder_id"])

    @check_reminders.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=24)
    async def cleanup_reminders(self):
        """Clean up old completed reminders"""
        deleted = cleanup_old_reminders(30)  # Remove reminders older than 30 days
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old reminders")

    @cleanup_reminders.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    # ============================================
    # COMMANDS
    # ============================================

    @app_commands.command(name="remind", description="Set a personal reminder")
    @app_commands.describe(
        time="When to remind you (e.g., 1h, 30m, 1d, 1w, 2h30m)",
        message="What to remind you about",
        repeat="Make this a repeating reminder"
    )
    async def remind(
        self,
        interaction: discord.Interaction,
        time: str,
        message: str,
        repeat: Optional[Literal["daily", "weekly"]] = None
    ):
        """Set a personal reminder"""
        # Check reminder limit
        count = get_reminder_count(interaction.user.id)
        if count >= 25:
            await interaction.response.send_message(
                "You have too many active reminders! Delete some first.",
                ephemeral=True
            )
            return

        # Parse duration
        duration = parse_duration(time)
        if not duration:
            await interaction.response.send_message(
                "Invalid time format! Use formats like: `1h`, `30m`, `1d`, `1w`, `2h30m`",
                ephemeral=True
            )
            return

        # Calculate remind time
        remind_at = datetime.utcnow() + duration

        # Create reminder
        success, reminder_id, result = create_reminder(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message=message,
            remind_at=remind_at.isoformat(),
            repeat=repeat
        )

        if success:
            embed = discord.Embed(
                title="Reminder Set!",
                description=f"**Message:** {message}",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Remind At",
                value=f"<t:{int(remind_at.timestamp())}:F> (<t:{int(remind_at.timestamp())}:R>)",
                inline=False
            )
            if repeat:
                embed.add_field(name="Repeat", value=repeat.capitalize(), inline=True)
            embed.set_footer(text=f"Reminder ID: {reminder_id}")

            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Reminder set by {interaction.user.name}: {message[:30]}")
        else:
            await interaction.response.send_message(result, ephemeral=True)

    @app_commands.command(name="reminders", description="View your active reminders")
    async def reminders(self, interaction: discord.Interaction):
        """View all active reminders"""
        reminders = get_user_reminders(interaction.user.id)

        if not reminders:
            await interaction.response.send_message(
                "You don't have any active reminders!\nUse `/remind` to set one.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Your Reminders",
            color=discord.Color.blue()
        )

        for i, reminder in enumerate(reminders[:10], 1):
            remind_at = datetime.fromisoformat(reminder["remind_at"])
            repeat_text = f" (Repeats {reminder['repeat']})" if reminder.get("repeat") else ""

            # Truncate message if too long
            message = reminder["message"]
            if len(message) > 50:
                message = message[:47] + "..."

            embed.add_field(
                name=f"{i}. {message}",
                value=(
                    f"<t:{int(remind_at.timestamp())}:R>{repeat_text}\n"
                    f"ID: `{reminder['reminder_id']}`"
                ),
                inline=False
            )

        if len(reminders) > 10:
            embed.set_footer(text=f"Showing 10 of {len(reminders)} reminders")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    reminder_group = app_commands.Group(
        name="reminder",
        description="Manage your reminders"
    )

    @reminder_group.command(name="delete", description="Delete a specific reminder")
    @app_commands.describe(reminder_id="The ID of the reminder to delete")
    async def reminder_delete(self, interaction: discord.Interaction, reminder_id: int):
        """Delete a reminder"""
        success, message = delete_reminder(reminder_id, interaction.user.id)

        if success:
            embed = discord.Embed(
                title="Reminder Deleted",
                description="Your reminder has been removed.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @reminder_group.command(name="clear", description="Clear all your reminders")
    async def reminder_clear(self, interaction: discord.Interaction):
        """Clear all reminders"""
        deleted = delete_all_user_reminders(interaction.user.id)

        if deleted > 0:
            embed = discord.Embed(
                title="Reminders Cleared",
                description=f"Deleted **{deleted}** reminder(s).",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "You don't have any reminders to clear!",
                ephemeral=True
            )

    @reminder_group.command(name="info", description="View details of a specific reminder")
    @app_commands.describe(reminder_id="The ID of the reminder")
    async def reminder_info(self, interaction: discord.Interaction, reminder_id: int):
        """View reminder details"""
        reminder = get_reminder(reminder_id)

        if not reminder:
            await interaction.response.send_message("Reminder not found!", ephemeral=True)
            return

        if reminder["user_id"] != interaction.user.id:
            await interaction.response.send_message(
                "You can only view your own reminders!",
                ephemeral=True
            )
            return

        remind_at = datetime.fromisoformat(reminder["remind_at"])
        created_at = datetime.fromisoformat(reminder["created_at"])

        embed = discord.Embed(
            title=f"Reminder #{reminder_id}",
            description=reminder["message"],
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Remind At",
            value=f"<t:{int(remind_at.timestamp())}:F>",
            inline=True
        )
        embed.add_field(
            name="Created",
            value=f"<t:{int(created_at.timestamp())}:R>",
            inline=True
        )
        if reminder.get("repeat"):
            embed.add_field(name="Repeat", value=reminder["repeat"].capitalize(), inline=True)

        guild = self.bot.get_guild(reminder["guild_id"])
        if guild:
            embed.set_footer(text=f"Server: {guild.name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Add the Reminders cog to the bot"""
    await bot.add_cog(Reminders(bot))
