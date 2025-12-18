"""
/warning Command
Issue warnings to users with different severity levels
Tracks warnings per user and notes repeat offenders
"""

import discord
from discord import app_commands
from discord.ext import commands
from enum import Enum

from utils.logger import log_command, logger
from utils.warnings_db import add_warning, get_recent_warning_count


class WarningType(Enum):
    """Types of warnings that can be issued"""
    verbal = "Verbal Warning"
    serious = "Serious Warning"
    shutup = "Shut Up Warning"


class Warning(commands.Cog):
    """Cog for the warning command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="warning", description="Issue a warning to a user")
    @app_commands.describe(
        user="The user to warn",
        warning_type="The type of warning to issue",
        reason="The reason for the warning"
    )
    @app_commands.choices(warning_type=[
        app_commands.Choice(name="Verbal Warning", value="verbal"),
        app_commands.Choice(name="Serious Warning", value="serious"),
        app_commands.Choice(name="Shut Up Warning", value="shutup"),
    ])
    async def warning(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        warning_type: str,
        reason: str
    ):
        """
        Slash command that issues a warning to a user
        Usage: /warning @user Verbal Warning Being rude
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command=f"warning {user} {warning_type} {reason}",
            guild=guild_name
        )

        # Check if the command is used in a server (not DMs)
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check if the user has permission to manage messages (mod permission)
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "You don't have permission to warn members!",
                ephemeral=True
            )
            return

        # Check if trying to warn themselves
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't warn yourself!",
                ephemeral=True
            )
            return

        # Check if trying to warn the bot
        if user.id == self.bot.user.id:
            await interaction.response.send_message(
                "You can't warn me!",
                ephemeral=True
            )
            return

        # Get the warning type display name
        warning_display = WarningType[warning_type].value

        # Add the warning to the database
        warning_count = add_warning(
            guild_id=interaction.guild.id,
            user_id=user.id,
            user_name=str(user),
            warning_type=warning_display,
            reason=reason,
            warned_by=str(interaction.user)
        )

        # Log the warning
        logger.info(f"Warning issued to {user} by {interaction.user}: {warning_display} - {reason}")

        # Set embed color based on warning type
        if warning_type == "verbal":
            color = discord.Color.yellow()
        elif warning_type == "serious":
            color = discord.Color.orange()
        else:  # shutup
            color = discord.Color.red()

        # Create the warning embed
        embed = discord.Embed(
            title="Warning Issued",
            color=color
        )

        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Warning Type", value=warning_display, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Issued By", value=interaction.user.mention, inline=True)

        # Add warning count if more than 1
        if warning_count > 1:
            embed.add_field(
                name="Warning Count",
                value=f"This is their **{warning_count}** warning in the last 7 days!",
                inline=False
            )
            embed.set_footer(text="Multiple warnings detected - consider further action")
        else:
            embed.set_footer(text="This is their first warning in the last 7 days")

        # Send the warning message
        await interaction.response.send_message(embed=embed)


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the Warning cog to the bot"""
    await bot.add_cog(Warning(bot))
