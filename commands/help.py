"""
/help Command
Displays a quick overview of all available bot commands organized by category
Shows only commands the user has permission to use

IMPORTANT: Update this file when adding new commands!
"""

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.logger import log_command, logger


def user_has_permission(user: discord.Member, permission: str) -> bool:
    """Check if a user has a specific permission"""
    if permission is None:
        return True
    return getattr(user.guild_permissions, permission, False)


class Help(commands.Cog):
    """Cog for the help command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Shows all available commands")
    async def help(self, interaction: discord.Interaction):
        """
        Slash command that displays help information
        Usage: /help
        Shows only commands the user has permission to use
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="help",
            guild=guild_name
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command works best in a server!",
                ephemeral=True
            )
            return

        # Get user permissions
        perms = interaction.user.guild_permissions
        is_mod = perms.manage_messages or perms.moderate_members
        is_admin = perms.administrator
        is_owner = interaction.user.id == interaction.guild.owner_id

        # Create the embed
        embed = discord.Embed(
            title=f"{config.BOT_NAME} - Commands",
            description="Here's a quick overview of available commands.\nUse `/information` for detailed descriptions.",
            color=discord.Color.blue()
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # General Commands (Everyone)
        general_cmds = "`/help` `/ping` `/information` `/dq`"
        embed.add_field(
            name="📌 General",
            value=general_cmds,
            inline=False
        )

        # Economy Commands (Everyone)
        economy_cmds = "`/balance` `/claimdaily` `/leaderboard`"
        embed.add_field(
            name="💰 Economy",
            value=economy_cmds,
            inline=False
        )

        # Gambling Commands (Everyone)
        gambling_cmds = "`/blackjack` `/roulette` `/roulettenumber` `/roulettetable` `/coinflip` `/guessnumber`"
        embed.add_field(
            name="🎰 Gambling",
            value=gambling_cmds,
            inline=False
        )

        # Music Commands (Everyone)
        music_cmds = "`/play` `/addsong` `/playlist` `/queue` `/nowplaying` `/pause` `/resume` `/skip` `/stop` `/volume` `/shuffle` `/audiostatus`"
        embed.add_field(
            name="🔊 Music",
            value=music_cmds,
            inline=False
        )

        # Karaoke Commands (Everyone)
        karaoke_cmds = "`/karaokelist` `/karaokesolo` `/karaokeduet` `/karaoke`"
        embed.add_field(
            name="🎤 Karaoke",
            value=karaoke_cmds,
            inline=False
        )

        # Moderation Commands (Mods only)
        if is_mod or is_admin:
            mod_cmds = "`/moderationpanel` `/timeout` `/warning` `/modtalk` `/moderationlogs` `/modstats` `/userhistory` `/modactivity` `/clearqueue`"
            embed.add_field(
                name="🛡️ Moderation",
                value=mod_cmds,
                inline=False
            )

        # Admin Commands (Admins only)
        if is_admin:
            admin_cmds = "`/adminprofile` `/webhook` `/webhookedit` `/givecoins` `/ultraoptimizemusic`"
            embed.add_field(
                name="👑 Admin",
                value=admin_cmds,
                inline=False
            )

        # Owner Commands (Server Owner only)
        if is_owner:
            owner_cmds = "`/setuplogs` `/editlogs` `/searchlogs` `/logstats` `/clearlogs`"
            embed.add_field(
                name="🔐 Owner",
                value=owner_cmds,
                inline=False
            )

        # Footer
        embed.set_footer(text=f"{config.BOT_NAME} v{config.BOT_VERSION} • Use /information for details")

        await interaction.response.send_message(embed=embed)


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the Help cog to the bot"""
    await bot.add_cog(Help(bot))
