"""
/moderationpanel Command
Interactive moderation panel for moderators to manage users
Only users with moderation permissions can use this command

Features:
- Kick users
- Ban users (with optional message deletion)
- Timeout users (1 min to 28 days)
- Remove timeout
- Issue warnings
- Clear user's recent messages
- View user's warning history
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from datetime import timedelta, datetime
from typing import Optional

from utils.logger import log_command, logger
from utils.warnings_db import add_warning, get_user_warnings
from utils.moderation_logs import log_action, ModAction


def is_moderator(user: discord.Member) -> bool:
    """Check if a user has any moderation permissions"""
    perms = user.guild_permissions
    return (
        perms.administrator or
        perms.moderate_members or
        perms.kick_members or
        perms.ban_members or
        perms.manage_messages
    )


def can_moderate_target(moderator: discord.Member, target: discord.Member, bot_member: discord.Member) -> tuple[bool, str]:
    """
    Check if the moderator can take action against the target
    Returns (can_moderate, error_message)
    """
    # Can't moderate yourself
    if moderator.id == target.id:
        return False, "You can't moderate yourself!"

    # Can't moderate the bot
    if target.id == bot_member.id:
        return False, "You can't moderate me!"

    # Can't moderate server owner
    if target.id == target.guild.owner_id:
        return False, "You can't moderate the server owner!"

    # Can't moderate someone with higher or equal role
    if target.top_role >= moderator.top_role and not moderator.guild_permissions.administrator:
        return False, "You can't moderate someone with a higher or equal role!"

    # Check if bot can moderate the target
    if target.top_role >= bot_member.top_role:
        return False, "I can't moderate this user - their role is higher than mine!"

    return True, ""


# =============================================================================
# MODALS FOR INPUT
# =============================================================================

class TimeoutModal(Modal):
    """Modal for timeout duration and reason"""

    def __init__(self, target: discord.Member, panel_view: "ModerationPanelView"):
        super().__init__(title=f"Timeout {target.display_name}")
        self.target = target
        self.panel_view = panel_view

        self.duration = TextInput(
            label="Duration (in minutes)",
            placeholder="Enter 1-40320 (max 28 days)",
            required=True,
            max_length=5
        )
        self.reason = TextInput(
            label="Reason",
            placeholder="Why are you timing out this user?",
            required=True,
            max_length=500,
            style=discord.TextStyle.paragraph
        )

        self.add_item(self.duration)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.duration.value)
            if minutes < 1 or minutes > 40320:
                await interaction.response.send_message(
                    "❌ Duration must be between 1 and 40320 minutes (28 days)!",
                    ephemeral=True
                )
                return

            timeout_duration = timedelta(minutes=minutes)
            await self.target.timeout(
                timeout_duration,
                reason=f"{self.reason.value} (by {interaction.user})"
            )

            logger.info(f"User {self.target} timed out for {minutes} min by {interaction.user}: {self.reason.value}")

            # Log to moderation logs
            log_action(
                guild_id=interaction.guild.id,
                moderator_id=interaction.user.id,
                moderator_name=str(interaction.user),
                action=ModAction.TIMEOUT,
                target_id=self.target.id,
                target_name=str(self.target),
                reason=self.reason.value,
                details={"duration_minutes": minutes}
            )

            # Update the panel
            await interaction.response.edit_message(
                embed=self.panel_view.get_panel_embed(),
                view=self.panel_view
            )

            # Send confirmation
            await interaction.followup.send(
                f"✅ **{self.target.display_name}** has been timed out for **{minutes} minute(s)**!\n"
                f"**Reason:** {self.reason.value}",
                ephemeral=False
            )

        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number for duration!",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to timeout this user!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Timeout error: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong!",
                ephemeral=True
            )


class KickModal(Modal):
    """Modal for kick reason"""

    def __init__(self, target: discord.Member, panel_view: "ModerationPanelView"):
        super().__init__(title=f"Kick {target.display_name}")
        self.target = target
        self.panel_view = panel_view

        self.reason = TextInput(
            label="Reason",
            placeholder="Why are you kicking this user?",
            required=True,
            max_length=500,
            style=discord.TextStyle.paragraph
        )

        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.target.kick(reason=f"{self.reason.value} (by {interaction.user})")

            logger.info(f"User {self.target} kicked by {interaction.user}: {self.reason.value}")

            # Log to moderation logs
            log_action(
                guild_id=interaction.guild.id,
                moderator_id=interaction.user.id,
                moderator_name=str(interaction.user),
                action=ModAction.KICK,
                target_id=self.target.id,
                target_name=str(self.target),
                reason=self.reason.value
            )

            await interaction.response.send_message(
                f"✅ **{self.target.display_name}** has been kicked from the server!\n"
                f"**Reason:** {self.reason.value}",
                ephemeral=False
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to kick this user!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Kick error: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong!",
                ephemeral=True
            )


class BanModal(Modal):
    """Modal for ban reason and message deletion"""

    def __init__(self, target: discord.Member, panel_view: "ModerationPanelView"):
        super().__init__(title=f"Ban {target.display_name}")
        self.target = target
        self.panel_view = panel_view

        self.reason = TextInput(
            label="Reason",
            placeholder="Why are you banning this user?",
            required=True,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.delete_days = TextInput(
            label="Delete message history (days)",
            placeholder="0-7 (0 = don't delete, 7 = delete last 7 days)",
            required=False,
            max_length=1,
            default="0"
        )

        self.add_item(self.reason)
        self.add_item(self.delete_days)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            delete_days = int(self.delete_days.value or "0")
            delete_days = max(0, min(7, delete_days))  # Clamp between 0 and 7

            await self.target.ban(
                reason=f"{self.reason.value} (by {interaction.user})",
                delete_message_days=delete_days
            )

            logger.info(f"User {self.target} banned by {interaction.user}: {self.reason.value}")

            # Log to moderation logs
            log_action(
                guild_id=interaction.guild.id,
                moderator_id=interaction.user.id,
                moderator_name=str(interaction.user),
                action=ModAction.BAN,
                target_id=self.target.id,
                target_name=str(self.target),
                reason=self.reason.value,
                details={"delete_days": delete_days}
            )

            delete_text = f" (deleted {delete_days} days of messages)" if delete_days > 0 else ""

            await interaction.response.send_message(
                f"🔨 **{self.target.display_name}** has been banned from the server{delete_text}!\n"
                f"**Reason:** {self.reason.value}",
                ephemeral=False
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to ban this user!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Ban error: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong!",
                ephemeral=True
            )


class WarnModal(Modal):
    """Modal for warning type and reason"""

    def __init__(self, target: discord.Member, warning_type: str, panel_view: "ModerationPanelView"):
        super().__init__(title=f"Warn {target.display_name}")
        self.target = target
        self.warning_type = warning_type
        self.panel_view = panel_view

        self.reason = TextInput(
            label="Reason",
            placeholder="Why are you warning this user?",
            required=True,
            max_length=500,
            style=discord.TextStyle.paragraph
        )

        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Add the warning
            warning_count = add_warning(
                guild_id=interaction.guild.id,
                user_id=self.target.id,
                user_name=str(self.target),
                warning_type=self.warning_type,
                reason=self.reason.value,
                warned_by=str(interaction.user)
            )

            logger.info(f"Warning issued to {self.target} by {interaction.user}: {self.warning_type} - {self.reason.value}")

            # Log to moderation logs
            log_action(
                guild_id=interaction.guild.id,
                moderator_id=interaction.user.id,
                moderator_name=str(interaction.user),
                action=ModAction.WARN,
                target_id=self.target.id,
                target_name=str(self.target),
                reason=self.reason.value,
                details={"warning_type": self.warning_type, "total_warnings": warning_count}
            )

            # Update the panel
            await interaction.response.edit_message(
                embed=self.panel_view.get_panel_embed(),
                view=self.panel_view
            )

            # Send confirmation
            warning_msg = f"⚠️ **{self.target.display_name}** has been warned!\n"
            warning_msg += f"**Type:** {self.warning_type}\n"
            warning_msg += f"**Reason:** {self.reason.value}\n"
            warning_msg += f"**Total Warnings (7 days):** {warning_count}"

            await interaction.followup.send(warning_msg, ephemeral=False)

        except Exception as e:
            logger.error(f"Warning error: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong!",
                ephemeral=True
            )


class ClearMessagesModal(Modal):
    """Modal for clearing messages"""

    def __init__(self, target: discord.Member, panel_view: "ModerationPanelView"):
        super().__init__(title=f"Clear Messages - {target.display_name}")
        self.target = target
        self.panel_view = panel_view

        self.amount = TextInput(
            label="Number of messages to check",
            placeholder="Enter 1-100 (will delete this user's messages from last X messages)",
            required=True,
            max_length=3,
            default="50"
        )

        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            amount = max(1, min(100, amount))

            await interaction.response.defer(ephemeral=True)

            # Delete messages from this user in the current channel
            deleted = 0
            async for message in interaction.channel.history(limit=amount):
                if message.author.id == self.target.id:
                    try:
                        await message.delete()
                        deleted += 1
                    except:
                        pass

            logger.info(f"Cleared {deleted} messages from {self.target} by {interaction.user}")

            # Log to moderation logs
            log_action(
                guild_id=interaction.guild.id,
                moderator_id=interaction.user.id,
                moderator_name=str(interaction.user),
                action=ModAction.CLEAR,
                target_id=self.target.id,
                target_name=str(self.target),
                details={"messages_deleted": deleted, "channel": interaction.channel.name}
            )

            await interaction.followup.send(
                f"🧹 Deleted **{deleted}** message(s) from **{self.target.display_name}** in this channel!",
                ephemeral=True
            )

        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Clear messages error: {e}")
            await interaction.followup.send(
                "❌ Something went wrong!",
                ephemeral=True
            )


# =============================================================================
# MAIN PANEL VIEW
# =============================================================================

class ModerationPanelView(View):
    """Main moderation panel with action buttons"""

    def __init__(self, bot: commands.Bot, moderator: discord.Member, target: discord.Member, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.moderator = moderator
        self.target = target

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original moderator to use the panel"""
        if interaction.user.id != self.moderator.id:
            await interaction.response.send_message(
                "Only the moderator who opened this panel can use it!",
                ephemeral=True
            )
            return False
        return True

    def get_panel_embed(self) -> discord.Embed:
        """Build the moderation panel embed"""
        target = self.target

        # Get warning count
        warnings = get_user_warnings(target.guild.id, target.id)
        warning_count = len(warnings)
        recent_warnings = sum(1 for w in warnings if self._is_recent(w.get("timestamp", "")))

        # Check timeout status
        if target.timed_out_until:
            timeout_status = f"⏰ Until {target.timed_out_until.strftime('%Y-%m-%d %H:%M')}"
        else:
            timeout_status = "✅ Not timed out"

        embed = discord.Embed(
            title=f"🛡️ Moderation Panel",
            description=f"Managing **{target.display_name}** ({target.mention})",
            color=discord.Color.orange()
        )

        embed.set_thumbnail(url=target.display_avatar.url)

        # User info
        embed.add_field(
            name="👤 User Info",
            value=(
                f"**Username:** {target.name}\n"
                f"**ID:** `{target.id}`\n"
                f"**Joined:** {target.joined_at.strftime('%Y-%m-%d') if target.joined_at else 'Unknown'}\n"
                f"**Top Role:** {target.top_role.mention}"
            ),
            inline=True
        )

        # Moderation status
        embed.add_field(
            name="⚠️ Status",
            value=(
                f"**Timeout:** {timeout_status}\n"
                f"**Total Warnings:** {warning_count}\n"
                f"**Recent (7 days):** {recent_warnings}"
            ),
            inline=True
        )

        embed.add_field(
            name="🎮 Actions",
            value=(
                "Use the buttons below to take action:\n"
                "• **Timeout** - Mute temporarily\n"
                "• **Kick** - Remove from server\n"
                "• **Ban** - Permanently ban\n"
                "• **Warn** - Issue a warning\n"
                "• **Clear** - Delete messages\n"
                "• **Untimeout** - Remove timeout"
            ),
            inline=False
        )

        embed.set_footer(text=f"Panel opened by {self.moderator} • Expires in 5 minutes")

        return embed

    def _is_recent(self, timestamp: str, days: int = 7) -> bool:
        """Check if a timestamp is within the last N days"""
        try:
            ts = datetime.fromisoformat(timestamp)
            return (datetime.now() - ts).days < days
        except:
            return False

    @discord.ui.button(label="⏰ Timeout", style=discord.ButtonStyle.secondary, row=0)
    async def timeout_button(self, interaction: discord.Interaction, button: Button):
        """Open timeout modal"""
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "❌ You need 'Timeout Members' permission!",
                ephemeral=True
            )
            return

        can_mod, error = can_moderate_target(self.moderator, self.target, interaction.guild.me)
        if not can_mod:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return

        await interaction.response.send_modal(TimeoutModal(self.target, self))

    @discord.ui.button(label="👢 Kick", style=discord.ButtonStyle.danger, row=0)
    async def kick_button(self, interaction: discord.Interaction, button: Button):
        """Open kick modal"""
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message(
                "❌ You need 'Kick Members' permission!",
                ephemeral=True
            )
            return

        can_mod, error = can_moderate_target(self.moderator, self.target, interaction.guild.me)
        if not can_mod:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return

        await interaction.response.send_modal(KickModal(self.target, self))

    @discord.ui.button(label="🔨 Ban", style=discord.ButtonStyle.danger, row=0)
    async def ban_button(self, interaction: discord.Interaction, button: Button):
        """Open ban modal"""
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message(
                "❌ You need 'Ban Members' permission!",
                ephemeral=True
            )
            return

        can_mod, error = can_moderate_target(self.moderator, self.target, interaction.guild.me)
        if not can_mod:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return

        await interaction.response.send_modal(BanModal(self.target, self))

    @discord.ui.button(label="🟢 Warn Minor", style=discord.ButtonStyle.success, row=1)
    async def warn_minor_button(self, interaction: discord.Interaction, button: Button):
        """Issue minor warning"""
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ You need 'Manage Messages' permission!",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(WarnModal(self.target, "🟢 Minor", self))

    @discord.ui.button(label="🟡 Warn Medium", style=discord.ButtonStyle.secondary, row=1)
    async def warn_medium_button(self, interaction: discord.Interaction, button: Button):
        """Issue medium warning"""
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ You need 'Manage Messages' permission!",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(WarnModal(self.target, "🟡 Medium", self))

    @discord.ui.button(label="🔴 Warn Serious", style=discord.ButtonStyle.danger, row=1)
    async def warn_serious_button(self, interaction: discord.Interaction, button: Button):
        """Issue serious warning"""
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ You need 'Manage Messages' permission!",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(WarnModal(self.target, "🔴 Serious", self))

    @discord.ui.button(label="🧹 Clear Messages", style=discord.ButtonStyle.secondary, row=2)
    async def clear_button(self, interaction: discord.Interaction, button: Button):
        """Open clear messages modal"""
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ You need 'Manage Messages' permission!",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(ClearMessagesModal(self.target, self))

    @discord.ui.button(label="✅ Remove Timeout", style=discord.ButtonStyle.success, row=2)
    async def untimeout_button(self, interaction: discord.Interaction, button: Button):
        """Remove timeout from user"""
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "❌ You need 'Timeout Members' permission!",
                ephemeral=True
            )
            return

        if not self.target.timed_out_until:
            await interaction.response.send_message(
                "❌ This user is not timed out!",
                ephemeral=True
            )
            return

        try:
            await self.target.timeout(None, reason=f"Timeout removed by {interaction.user}")

            logger.info(f"Timeout removed from {self.target} by {interaction.user}")

            # Log to moderation logs
            log_action(
                guild_id=interaction.guild.id,
                moderator_id=interaction.user.id,
                moderator_name=str(interaction.user),
                action=ModAction.UNMUTE,
                target_id=self.target.id,
                target_name=str(self.target),
                reason="Timeout removed"
            )

            # Update the panel
            await interaction.response.edit_message(
                embed=self.get_panel_embed(),
                view=self
            )

            await interaction.followup.send(
                f"✅ Timeout removed from **{self.target.display_name}**!",
                ephemeral=False
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to remove the timeout!",
                ephemeral=True
            )

    @discord.ui.button(label="📋 View Warnings", style=discord.ButtonStyle.primary, row=2)
    async def view_warnings_button(self, interaction: discord.Interaction, button: Button):
        """View user's warning history"""
        warnings = get_user_warnings(self.target.guild.id, self.target.id)

        if not warnings:
            await interaction.response.send_message(
                f"✅ **{self.target.display_name}** has no warnings on record!",
                ephemeral=True
            )
            return

        # Sort by date (newest first)
        warnings_sorted = sorted(
            warnings,
            key=lambda w: w.get("timestamp", ""),
            reverse=True
        )[:10]  # Show last 10

        embed = discord.Embed(
            title=f"⚠️ Warnings for {self.target.display_name}",
            description=f"Showing last {len(warnings_sorted)} of {len(warnings)} total warnings",
            color=discord.Color.orange()
        )

        for i, w in enumerate(warnings_sorted, 1):
            try:
                ts = datetime.fromisoformat(w.get("timestamp", ""))
                date_str = ts.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = "Unknown"

            reason = w.get("reason", "No reason")
            if len(reason) > 100:
                reason = reason[:97] + "..."

            embed.add_field(
                name=f"#{i} - {w.get('type', 'Unknown')}",
                value=f"**Date:** {date_str}\n**Reason:** {reason}\n**By:** {w.get('warned_by', 'Unknown')}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="❌ Close Panel", style=discord.ButtonStyle.secondary, row=2)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        """Close the moderation panel by deleting the message"""
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self):
        """Disable all buttons when the view times out"""
        for item in self.children:
            item.disabled = True


class ModerationPanel(commands.Cog):
    """Cog for the moderation panel command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="moderationpanel", description="Open moderation panel for a user (Moderators only)")
    @app_commands.describe(user="The user to moderate")
    async def moderationpanel(self, interaction: discord.Interaction, user: discord.Member):
        """
        Slash command that opens an interactive moderation panel
        Usage: /moderationpanel @user
        Only moderators can use this command
        """
        # Log command usage
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command=f"moderationpanel {user}",
            guild=guild_name
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check if user is a moderator
        if not is_moderator(interaction.user):
            await interaction.response.send_message(
                "❌ You need moderation permissions to use this command!\n"
                "Required: Timeout Members, Kick Members, Ban Members, or Manage Messages",
                ephemeral=True
            )
            return

        # Basic checks
        can_mod, error = can_moderate_target(interaction.user, user, interaction.guild.me)
        if not can_mod:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return

        try:
            # Create and send the panel
            view = ModerationPanelView(self.bot, interaction.user, user)
            embed = view.get_panel_embed()

            await interaction.response.send_message(embed=embed, view=view)

            logger.info(f"Moderation panel opened for {user} by {interaction.user}")

        except Exception as e:
            logger.error(f"Failed to open moderation panel: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong while opening the panel.",
                ephemeral=True
            )


# Required setup function
async def setup(bot: commands.Bot):
    """Add the ModerationPanel cog to the bot"""
    await bot.add_cog(ModerationPanel(bot))
