"""
/timeout Command
Timeout (mute) a user for a specified amount of time
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta

from utils.logger import log_command, logger


class Timeout(commands.Cog):
    """Cog for the timeout command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="timeout", description="Timeout a user for a specified time")
    @app_commands.describe(
        user="The user to timeout",
        minutes="How long to timeout the user (in minutes)",
        reason="The reason for the timeout"
    )
    async def timeout(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        minutes: int,
        reason: str
    ):
        """
        Slash command that timeouts a user
        Usage: /timeout @user 10 Being annoying
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command=f"timeout {user} {minutes}min reason: {reason}",
            guild=guild_name
        )

        # Check if the command is used in a server (not DMs)
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check if the user has permission to timeout members
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "You don't have permission to timeout members!",
                ephemeral=True
            )
            return

        # Check if the bot has permission to timeout members
        if not interaction.guild.me.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "I don't have permission to timeout members! Please give me the 'Timeout Members' permission.",
                ephemeral=True
            )
            return

        # Check if trying to timeout themselves
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't timeout yourself!",
                ephemeral=True
            )
            return

        # Check if trying to timeout the bot
        if user.id == self.bot.user.id:
            await interaction.response.send_message(
                "You can't timeout me!",
                ephemeral=True
            )
            return

        # Check if the target user has a higher role than the command user
        if user.top_role >= interaction.user.top_role:
            await interaction.response.send_message(
                "You can't timeout someone with a higher or equal role!",
                ephemeral=True
            )
            return

        # Validate minutes (Discord allows max 28 days = 40320 minutes)
        if minutes < 1:
            await interaction.response.send_message(
                "Timeout must be at least 1 minute!",
                ephemeral=True
            )
            return

        if minutes > 40320:
            await interaction.response.send_message(
                "Timeout can't be longer than 28 days (40320 minutes)!",
                ephemeral=True
            )
            return

        # Try to timeout the user
        try:
            # Convert minutes to timedelta
            timeout_duration = timedelta(minutes=minutes)

            # Apply the timeout
            await user.timeout(timeout_duration, reason=f"{reason} (by {interaction.user})")

            # Log success
            logger.info(f"User {user} was timed out for {minutes} minutes by {interaction.user}. Reason: {reason}")

            # Send success message
            await interaction.response.send_message(
                f"**{user.display_name}** has been timed out for **{minutes} minute(s)**!\n**Reason:** {reason}"
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I can't timeout this user! They might have a higher role than me.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to timeout {user}: {e}")
            await interaction.response.send_message(
                f"Something went wrong while trying to timeout the user.",
                ephemeral=True
            )


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the Timeout cog to the bot"""
    await bot.add_cog(Timeout(bot))
