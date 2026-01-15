"""
/help Command
Displays a quick overview of all available bot commands organized by category
Shows only commands the user has permission to use

IMPORTANT: Update this file when adding new commands!
NOTE: Discord embeds have a 25 field limit - keep categories consolidated!
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

        # ==================== EVERYONE COMMANDS ====================

        # General Commands
        embed.add_field(
            name="📌 General",
            value="`/help` `/ping` `/information` `/invitegojo` `/dq` `/67` `/start` `/remind` `/reminders`",
            inline=False
        )

        # Games & Fun
        embed.add_field(
            name="🎮 Games & Fun",
            value="`/trivia` `/minesweeper` `/connect4` `/tictactoe` `/rps` `/8ball` `/roll`",
            inline=False
        )

        # Profile & Customization
        embed.add_field(
            name="🎨 Profile",
            value="`/profile` `/profilecard` `/profilecolor` `/profilepresets` `/profilemotto` `/profilebanner` `/profilebadges` `/profilefeature`",
            inline=False
        )

        # Economy & Gambling + Vault
        embed.add_field(
            name="💰 Economy & Gambling",
            value="`/balance` `/claimdaily` `/leaderboard` `/blackjack` `/roulette` `/roulettenumber` `/coinflip` `/guessnumber`",
            inline=False
        )

        # Vault (Shared Economy)
        embed.add_field(
            name="🏦 Vault & Stocks",
            value="`/vault create` `/vault deposit` `/vault withdraw` `/vault info` `/vault join` `/vault list` | `/invest` `/sell` `/portfolio` `/stockprice`",
            inline=False
        )

        # Shop & Quests
        embed.add_field(
            name="🛒 Shop & Quests",
            value="`/shop` `/buy` `/inventory` `/quests` `/questkeys` `/lootbox` `/lootboxodds`",
            inline=False
        )

        # Leveling & Milestones
        embed.add_field(
            name="📊 Leveling & Milestones",
            value="`/xpleaderboard` `/levels` `/rep` `/repleaderboard` `/milestones` `/serverhistory`",
            inline=False
        )

        # Music & Karaoke
        embed.add_field(
            name="🎵 Music & Karaoke",
            value="`/play` `/playlist` `/queue` `/nowplaying` `/pause` `/skip` `/stop` `/volume` `/shuffle` | `/karaoke`",
            inline=False
        )

        # Voice Channels
        embed.add_field(
            name="🔊 Voice Channels",
            value="`/tempvc panel` `/vcsignal` `/vclink` `/audiostatus`",
            inline=False
        )

        # ==================== MODERATOR COMMANDS ====================

        if is_mod or is_admin:
            embed.add_field(
                name="🛡️ Moderation",
                value="`/moderationpanel` `/moderationdatabase` `/modtalk` `/clearqueue`",
                inline=False
            )

        # ==================== ADMIN COMMANDS ====================

        if is_admin:
            # Core Admin
            embed.add_field(
                name="👑 Admin Core",
                value="`/adminprofile` `/webhook` `/givecoins` `/setup` `/dashboard` `/backfill` `/syncstats`",
                inline=False
            )

            # Giveaways, Polls & Custom Commands
            embed.add_field(
                name="🎉 Giveaways & Polls",
                value="`/giveaway start` `/giveaway end` `/giveaway reroll` | `/poll create` `/poll end` | `/customcmd create` `/customcmd list`",
                inline=False
            )

            # Reaction Roles & Member Management
            embed.add_field(
                name="👋 Roles & Members",
                value="`/reactionrole create` `/reactionrole addrole` | `/welcome enable` `/welcome channel` | `/goodbye enable` | `/autorole add`",
                inline=False
            )

            # Voice, Language & Feeds
            embed.add_field(
                name="📺 Voice, Language & Feeds",
                value="`/tempvc setup` | `/language set` `/language list` | `/livealerts setup` `/livealerts add` | `/autonews setup`",
                inline=False
            )

            # Tickets, Starboard & Threads
            embed.add_field(
                name="🎫 Tickets & Starboard",
                value="`/ticket setup` `/ticket panel` | `/starboard setup` `/starboard threshold` | `/autothread setup` `/autothread list`",
                inline=False
            )

            # Server Config, Reports & Security
            embed.add_field(
                name="⚙️ Config & Security",
                value="`/serverconfig view` `/serverconfig toggle` | `/serverreports setup` | `/antiscam enable` `/antiscam settings`",
                inline=False
            )

        # ==================== OWNER COMMANDS ====================

        if is_owner:
            embed.add_field(
                name="🔐 Owner (Logs & System)",
                value="`/setuplogs` `/editlogs` `/clearlogs` `/clearmessages` | `/system health` `/system errors` `/system servers`",
                inline=False
            )

        # Footer
        embed.set_footer(text=f"{config.BOT_NAME} v{config.BOT_VERSION} • Use /information for details")

        await interaction.response.send_message(embed=embed)


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the Help cog to the bot"""
    await bot.add_cog(Help(bot))
