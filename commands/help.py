"""
/help Command
Displays a list of all available bot commands and their descriptions
"""

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.logger import log_command


class Help(commands.Cog):
    """Cog for the help command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Shows all available commands")
    async def help(self, interaction: discord.Interaction):
        """
        Slash command that displays help information
        Usage: /help
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="help",
            guild=guild_name
        )

        # Create an embed for a nice looking help message
        embed = discord.Embed(
            title=f"{config.BOT_NAME} - Help",
            description=f"{config.BOT_DESCRIPTION}\n\nHere are all the available commands:",
            color=discord.Color.blue()
        )

        # Add bot info at the top
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # List of commands - Add new commands here as you create them
        commands_list = [
            {
                "name": "/help",
                "description": "Shows this help message with all available commands"
            },
            {
                "name": "/ping",
                "description": "Check if the bot is online"
            },
            {
                "name": "/timeout",
                "description": "Timeout a user (e.g. /timeout @user 10 Being annoying)"
            },
            {
                "name": "/dq",
                "description": "Get a random famous quote (Daily Quote)"
            },
        ]

        # Add each command to the embed
        for cmd in commands_list:
            embed.add_field(
                name=cmd["name"],
                value=cmd["description"],
                inline=False
            )

        # Add footer with version info
        embed.set_footer(text=f"Version {config.BOT_VERSION}")

        # Send the embed as a response
        await interaction.response.send_message(embed=embed)


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the Help cog to the bot"""
    await bot.add_cog(Help(bot))
