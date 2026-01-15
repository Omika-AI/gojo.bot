"""
/clearlogs Command
Clear all moderation logs - Server Owner only
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button

from utils.logger import log_command, logger
from utils.moderation_logs import clear_logs


class ClearLogsConfirmView(View):
    """Confirmation view for clearing logs"""

    def __init__(self, user_id: int, guild_id: int):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your view!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Yes, Clear All Logs", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        clear_logs(self.guild_id)
        logger.info(f"Moderation logs cleared by {interaction.user} in {interaction.guild.name}")
        await interaction.response.edit_message(
            content="\u2705 All moderation logs have been cleared.",
            embed=None,
            view=None
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content="Log clearing cancelled.",
            embed=None,
            view=None
        )


class ClearLogs(commands.Cog):
    """Clear moderation logs - Server Owner only"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="clearlogs", description="Clear all moderation logs (Server Owner only)")
    async def clearlogs(self, interaction: discord.Interaction):
        """Clear all moderation logs - Server Owner only"""
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="clearlogs",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Server Owner only
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the **Server Owner** can clear moderation logs!",
                ephemeral=True
            )
            return

        # Show confirmation
        embed = discord.Embed(
            title="\u26a0\ufe0f Clear All Moderation Logs?",
            description=(
                "**Warning:** This will permanently delete all moderation logs for this server.\n"
                "This action **cannot be undone!**\n\n"
                "Are you sure you want to continue?"
            ),
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed,
            view=ClearLogsConfirmView(interaction.user.id, interaction.guild.id),
            ephemeral=True
        )


# Required setup function
async def setup(bot: commands.Bot):
    """Add the ClearLogs cog to the bot"""
    await bot.add_cog(ClearLogs(bot))
