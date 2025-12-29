"""
/adminprofile Command
Display detailed profile stats for a Discord member
Only users with Administrator permission can use this command
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from utils.logger import log_command, logger


class AdminProfile(commands.Cog):
    """Cog for the adminprofile command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="adminprofile", description="View detailed profile stats for a member (Admin only)")
    @app_commands.describe(user="The member to view profile stats for")
    async def adminprofile(self, interaction: discord.Interaction, user: discord.Member):
        """
        Slash command that displays detailed profile stats for a user
        Usage: /adminprofile @user
        Only administrators can use this command
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command=f"adminprofile {user}",
            guild=guild_name
        )

        # Check if the command is used in a server (not DMs)
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check if the user has Administrator permission
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need **Administrator** permission to use this command!",
                ephemeral=True
            )
            return

        try:
            # Calculate account age
            account_created = user.created_at
            account_age = datetime.utcnow() - account_created.replace(tzinfo=None)
            account_age_days = account_age.days

            # Calculate time in server
            joined_at = user.joined_at
            if joined_at:
                time_in_server = datetime.utcnow() - joined_at.replace(tzinfo=None)
                time_in_server_days = time_in_server.days
            else:
                time_in_server_days = "Unknown"

            # Get user's roles (excluding @everyone)
            roles = [role.mention for role in user.roles if role.name != "@everyone"]
            roles_text = ", ".join(roles) if roles else "No roles"

            # Truncate roles if too long
            if len(roles_text) > 1024:
                roles_text = roles_text[:1000] + "... (truncated)"

            # Get key permissions
            permissions = []
            perms = user.guild_permissions
            if perms.administrator:
                permissions.append("👑 Administrator")
            if perms.manage_guild:
                permissions.append("⚙️ Manage Server")
            if perms.manage_roles:
                permissions.append("🎭 Manage Roles")
            if perms.manage_channels:
                permissions.append("📁 Manage Channels")
            if perms.manage_messages:
                permissions.append("📝 Manage Messages")
            if perms.kick_members:
                permissions.append("👢 Kick Members")
            if perms.ban_members:
                permissions.append("🔨 Ban Members")
            if perms.moderate_members:
                permissions.append("⏰ Timeout Members")
            if perms.mention_everyone:
                permissions.append("📢 Mention Everyone")

            permissions_text = "\n".join(permissions) if permissions else "No special permissions"

            # Get status
            status_emoji = {
                discord.Status.online: "🟢 Online",
                discord.Status.idle: "🟡 Idle",
                discord.Status.dnd: "🔴 Do Not Disturb",
                discord.Status.offline: "⚫ Offline"
            }
            status_text = status_emoji.get(user.status, "⚫ Unknown")

            # Check if user is a bot
            bot_status = "🤖 Yes" if user.bot else "👤 No"

            # Check if boosting
            if user.premium_since:
                boost_text = f"💎 Since {user.premium_since.strftime('%Y-%m-%d')}"
            else:
                boost_text = "Not boosting"

            # Create the embed
            embed = discord.Embed(
                title=f"📋 Profile: {user.display_name}",
                color=user.color if user.color != discord.Color.default() else discord.Color.blue()
            )

            # Set user avatar as thumbnail
            embed.set_thumbnail(url=user.display_avatar.url)

            # Basic Info section
            embed.add_field(
                name="👤 Basic Info",
                value=(
                    f"**Username:** {user.name}\n"
                    f"**Display Name:** {user.display_name}\n"
                    f"**User ID:** `{user.id}`\n"
                    f"**Bot Account:** {bot_status}"
                ),
                inline=True
            )

            # Status section
            embed.add_field(
                name="📊 Status",
                value=(
                    f"**Current Status:** {status_text}\n"
                    f"**Top Role:** {user.top_role.mention}\n"
                    f"**Server Booster:** {boost_text}"
                ),
                inline=True
            )

            # Add a blank field for formatting
            embed.add_field(name="\u200b", value="\u200b", inline=True)

            # Dates section
            embed.add_field(
                name="📅 Account Dates",
                value=(
                    f"**Created:** {account_created.strftime('%Y-%m-%d %H:%M')}\n"
                    f"**Account Age:** {account_age_days} days\n"
                    f"**Joined Server:** {joined_at.strftime('%Y-%m-%d %H:%M') if joined_at else 'Unknown'}\n"
                    f"**Time in Server:** {time_in_server_days} days"
                ),
                inline=True
            )

            # Flags section (badges)
            # Note: Discord API doesn't expose Nitro, Quest, or Apprentice badges for privacy
            flags = user.public_flags
            badges = []
            if flags.staff:
                badges.append("⚡ Discord Staff")
            if flags.partner:
                badges.append("👑 Partner")
            if flags.hypesquad:
                badges.append("🏠 HypeSquad Events")
            if flags.bug_hunter:
                badges.append("🐛 Bug Hunter")
            if flags.bug_hunter_level_2:
                badges.append("🐛 Bug Hunter Level 2")
            if flags.hypesquad_bravery:
                badges.append("🟠 HypeSquad Bravery")
            if flags.hypesquad_brilliance:
                badges.append("🟣 HypeSquad Brilliance")
            if flags.hypesquad_balance:
                badges.append("🟢 HypeSquad Balance")
            if flags.early_supporter:
                badges.append("💎 Early Supporter")
            if flags.verified_bot_developer:
                badges.append("🤖 Verified Bot Developer")
            if flags.active_developer:
                badges.append("👨‍💻 Active Developer")
            if flags.discord_certified_moderator:
                badges.append("🛡️ Certified Moderator")
            if flags.verified_bot:
                badges.append("✅ Verified Bot")

            # Check for server booster (this IS detectable)
            if user.premium_since:
                badges.append("💜 Server Booster")

            badges_text = "\n".join(badges) if badges else "None detected\n*(Nitro, Quest & some badges are hidden by Discord)*"

            embed.add_field(
                name="🏅 Discord Badges",
                value=badges_text,
                inline=True
            )

            # Add a blank field for formatting
            embed.add_field(name="\u200b", value="\u200b", inline=True)

            # Permissions section
            embed.add_field(
                name="🔐 Key Permissions",
                value=permissions_text,
                inline=False
            )

            # Roles section
            embed.add_field(
                name=f"🎭 Roles ({len(roles)})",
                value=roles_text,
                inline=False
            )

            # Footer
            embed.set_footer(
                text=f"Requested by {interaction.user}",
                icon_url=interaction.user.display_avatar.url
            )

            # Send the embed
            await interaction.response.send_message(embed=embed)

            logger.info(f"Admin profile viewed for {user} by {interaction.user}")

        except Exception as e:
            logger.error(f"Failed to get profile for {user}: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong while fetching the profile.",
                ephemeral=True
            )


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the AdminProfile cog to the bot"""
    await bot.add_cog(AdminProfile(bot))
