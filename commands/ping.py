"""
/ping Command
Simple command to check if the bot is online
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.logger import log_command


class Ping(commands.Cog):
    """Cog for the ping command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check if the bot is online")
    async def ping(self, interaction: discord.Interaction):
        """
        Slash command that responds with Pong
        Usage: /ping
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="ping",
            guild=guild_name
        )

        # Send the response
        await interaction.response.send_message("Pong Bitch")


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the Ping cog to the bot"""
    await bot.add_cog(Ping(bot))
