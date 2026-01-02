"""
Moderation Logs Command
View all moderation actions in the server with filtering and pagination

Commands:
- /moderationlogs - View moderation action logs
- /modstats - View moderation statistics
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
from typing import Optional, List
from datetime import datetime

from utils.logger import log_command, logger
from utils.moderation_logs import (
    get_logs,
    get_total_logs,
    get_stats,
    get_user_history,
    get_moderator_activity,
    clear_logs,
    format_action_emoji,
    ModAction
)


# =============================================================================
# CONSTANTS
# =============================================================================

LOGS_PER_PAGE = 10


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_timestamp(iso_string: str) -> str:
    """Convert ISO timestamp to Discord timestamp"""
    try:
        dt = datetime.fromisoformat(iso_string)
        return f"<t:{int(dt.timestamp())}:R>"
    except:
        return iso_string


def create_log_embed(
    logs: List[dict],
    page: int,
    total_pages: int,
    title: str = "Moderation Logs",
    filter_info: Optional[str] = None
) -> discord.Embed:
    """Create an embed displaying logs"""
    embed = discord.Embed(
        title=f"\U0001f4dc {title}",
        color=discord.Color.blue()
    )

    if filter_info:
        embed.description = f"**Filters:** {filter_info}\n\n"
    else:
        embed.description = ""

    if not logs:
        embed.description += "*No moderation logs found.*"
    else:
        for log in logs:
            action = log.get("action", "unknown")
            emoji = format_action_emoji(action)
            timestamp = format_timestamp(log.get("timestamp", ""))

            # Build the log entry text
            mod = log.get("moderator", {})
            mod_name = mod.get("name", "Unknown")

            target = log.get("target", {})
            target_name = target.get("name")
            target_id = target.get("id")

            # Format the entry
            entry_parts = [f"**{action.upper()}** by {mod_name}"]

            if target_name:
                entry_parts.append(f"on **{target_name}**")

            reason = log.get("reason")
            if reason:
                # Truncate long reasons
                if len(reason) > 100:
                    reason = reason[:97] + "..."
                entry_parts.append(f"\n> Reason: {reason}")

            # Add details if present
            details = log.get("details", {})
            if details:
                detail_str = ", ".join(f"{k}: {v}" for k, v in details.items())
                if len(detail_str) > 80:
                    detail_str = detail_str[:77] + "..."
                entry_parts.append(f"\n> Details: {detail_str}")

            embed.add_field(
                name=f"{emoji} {timestamp}",
                value=" ".join(entry_parts),
                inline=False
            )

    embed.set_footer(text=f"Page {page}/{total_pages}")

    return embed


def create_stats_embed(stats: dict, guild_name: str) -> discord.Embed:
    """Create an embed displaying moderation statistics"""
    embed = discord.Embed(
        title=f"\U0001f4ca Moderation Statistics",
        description=f"**Server:** {guild_name}",
        color=discord.Color.gold()
    )

    # Action breakdown
    actions = stats.get("actions", {})
    if actions:
        action_text = []
        for action, count in sorted(actions.items(), key=lambda x: x[1], reverse=True):
            emoji = format_action_emoji(action)
            action_text.append(f"{emoji} **{action.title()}:** {count}")

        embed.add_field(
            name="\U0001f4cb Action Breakdown",
            value="\n".join(action_text) if action_text else "No actions recorded",
            inline=False
        )

    # Top moderators
    moderators = stats.get("moderators", {})
    if moderators:
        # Sort by total actions
        sorted_mods = sorted(
            moderators.items(),
            key=lambda x: x[1].get("total", 0),
            reverse=True
        )[:5]  # Top 5

        mod_text = []
        for i, (mod_id, mod_data) in enumerate(sorted_mods, 1):
            name = mod_data.get("name", "Unknown")
            total = mod_data.get("total", 0)
            medal = ["\U0001f947", "\U0001f948", "\U0001f949", "4\ufe0f\u20e3", "5\ufe0f\u20e3"][i-1]
            mod_text.append(f"{medal} **{name}:** {total} actions")

        embed.add_field(
            name="\U0001f3c6 Top Moderators",
            value="\n".join(mod_text) if mod_text else "No moderator data",
            inline=False
        )

    # Total
    total = stats.get("total", 0)
    embed.add_field(
        name="\U0001f522 Total Logged Actions",
        value=str(total),
        inline=True
    )

    return embed


# =============================================================================
# VIEWS
# =============================================================================

class LogsView(View):
    """View for navigating moderation logs"""

    def __init__(
        self,
        guild_id: int,
        user_id: int,
        page: int = 1,
        action_filter: Optional[ModAction] = None,
        moderator_filter: Optional[int] = None,
        target_filter: Optional[int] = None
    ):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user_id = user_id
        self.page = page
        self.action_filter = action_filter
        self.moderator_filter = moderator_filter
        self.target_filter = target_filter

        # Calculate total pages
        self.total_logs = get_total_logs(
            guild_id,
            action_filter=action_filter,
            moderator_filter=moderator_filter,
            target_filter=target_filter
        )
        self.total_pages = max(1, (self.total_logs + LOGS_PER_PAGE - 1) // LOGS_PER_PAGE)

        # Update button states
        self._update_buttons()

    def _update_buttons(self):
        """Update button enabled states based on current page"""
        # Find and update navigation buttons
        for item in self.children:
            if isinstance(item, Button):
                if item.custom_id == "first" or item.custom_id == "prev":
                    item.disabled = self.page <= 1
                elif item.custom_id == "next" or item.custom_id == "last":
                    item.disabled = self.page >= self.total_pages

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your logs view!",
                ephemeral=True
            )
            return False
        return True

    def get_logs_embed(self) -> discord.Embed:
        """Get the embed for the current page"""
        offset = (self.page - 1) * LOGS_PER_PAGE
        logs = get_logs(
            self.guild_id,
            limit=LOGS_PER_PAGE,
            offset=offset,
            action_filter=self.action_filter,
            moderator_filter=self.moderator_filter,
            target_filter=self.target_filter
        )

        # Build filter info string
        filter_parts = []
        if self.action_filter:
            filter_parts.append(f"Action: {self.action_filter.value}")
        if self.moderator_filter:
            filter_parts.append(f"Moderator ID: {self.moderator_filter}")
        if self.target_filter:
            filter_parts.append(f"Target ID: {self.target_filter}")

        filter_info = " | ".join(filter_parts) if filter_parts else None

        return create_log_embed(
            logs,
            self.page,
            self.total_pages,
            filter_info=filter_info
        )

    @discord.ui.button(label="\u23ee", style=discord.ButtonStyle.secondary, custom_id="first", row=0)
    async def first_page(self, interaction: discord.Interaction, button: Button):
        self.page = 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_logs_embed(), view=self)

    @discord.ui.button(label="\u25c0", style=discord.ButtonStyle.primary, custom_id="prev", row=0)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        self.page = max(1, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_logs_embed(), view=self)

    @discord.ui.button(label="\u25b6", style=discord.ButtonStyle.primary, custom_id="next", row=0)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.page = min(self.total_pages, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_logs_embed(), view=self)

    @discord.ui.button(label="\u23ed", style=discord.ButtonStyle.secondary, custom_id="last", row=0)
    async def last_page(self, interaction: discord.Interaction, button: Button):
        self.page = self.total_pages
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_logs_embed(), view=self)

    @discord.ui.button(label="Filter by Action", style=discord.ButtonStyle.secondary, row=1)
    async def filter_action(self, interaction: discord.Interaction, button: Button):
        """Open action filter dropdown"""
        await interaction.response.edit_message(view=ActionFilterView(self))

    @discord.ui.button(label="Clear Filters", style=discord.ButtonStyle.danger, row=1)
    async def clear_filters(self, interaction: discord.Interaction, button: Button):
        """Clear all filters"""
        self.action_filter = None
        self.moderator_filter = None
        self.target_filter = None
        self.page = 1

        # Recalculate total
        self.total_logs = get_total_logs(self.guild_id)
        self.total_pages = max(1, (self.total_logs + LOGS_PER_PAGE - 1) // LOGS_PER_PAGE)

        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_logs_embed(), view=self)


class ActionFilterView(View):
    """View for selecting action type filter"""

    def __init__(self, parent_view: LogsView):
        super().__init__(timeout=60)
        self.parent_view = parent_view

        # Create action type dropdown
        options = [
            discord.SelectOption(label="All Actions", value="all", description="Show all action types"),
            discord.SelectOption(label="\u26a0\ufe0f Warnings", value="warn"),
            discord.SelectOption(label="\u23f1\ufe0f Timeouts", value="timeout"),
            discord.SelectOption(label="\U0001f462 Kicks", value="kick"),
            discord.SelectOption(label="\U0001f528 Bans", value="ban"),
            discord.SelectOption(label="\u2705 Unbans", value="unban"),
            discord.SelectOption(label="\U0001f9f9 Message Clears", value="clear"),
            discord.SelectOption(label="\U0001f422 Slowmode", value="slowmode"),
            discord.SelectOption(label="\U0001f512 Channel Locks", value="lock"),
            discord.SelectOption(label="\U0001f4e2 ModTalk", value="modtalk"),
        ]

        select = Select(
            placeholder="Select action type to filter...",
            options=options
        )
        select.callback = self.action_selected
        self.add_item(select)

    async def action_selected(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]

        if value == "all":
            self.parent_view.action_filter = None
        else:
            try:
                self.parent_view.action_filter = ModAction(value)
            except:
                self.parent_view.action_filter = None

        # Reset to page 1 and recalculate
        self.parent_view.page = 1
        self.parent_view.total_logs = get_total_logs(
            self.parent_view.guild_id,
            action_filter=self.parent_view.action_filter,
            moderator_filter=self.parent_view.moderator_filter,
            target_filter=self.parent_view.target_filter
        )
        self.parent_view.total_pages = max(1, (self.parent_view.total_logs + LOGS_PER_PAGE - 1) // LOGS_PER_PAGE)
        self.parent_view._update_buttons()

        await interaction.response.edit_message(
            embed=self.parent_view.get_logs_embed(),
            view=self.parent_view
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            embed=self.parent_view.get_logs_embed(),
            view=self.parent_view
        )


# =============================================================================
# COG
# =============================================================================

class ModerationLogs(commands.Cog):
    """View moderation action logs"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="moderationlogs", description="View moderation action logs (Moderator only)")
    @app_commands.describe(
        user="Filter logs by target user",
        moderator="Filter logs by moderator"
    )
    async def moderationlogs(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.User] = None,
        moderator: Optional[discord.User] = None
    ):
        """View moderation logs with optional filters"""
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="moderationlogs",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check for Moderator permissions
        has_permission = (
            interaction.user.guild_permissions.manage_messages or
            interaction.user.guild_permissions.manage_guild or
            interaction.user.guild_permissions.administrator
        )

        if not has_permission:
            await interaction.response.send_message(
                "You need **Manage Messages** permission or higher to view moderation logs!",
                ephemeral=True
            )
            return

        # Create the view
        view = LogsView(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            target_filter=user.id if user else None,
            moderator_filter=moderator.id if moderator else None
        )

        await interaction.response.send_message(
            embed=view.get_logs_embed(),
            view=view,
            ephemeral=True
        )

    @app_commands.command(name="modstats", description="View moderation statistics (Moderator only)")
    async def modstats(self, interaction: discord.Interaction):
        """View moderation statistics"""
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="modstats",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check for Moderator permissions
        has_permission = (
            interaction.user.guild_permissions.manage_messages or
            interaction.user.guild_permissions.manage_guild or
            interaction.user.guild_permissions.administrator
        )

        if not has_permission:
            await interaction.response.send_message(
                "You need **Manage Messages** permission or higher to view moderation stats!",
                ephemeral=True
            )
            return

        stats = get_stats(interaction.guild.id)
        embed = create_stats_embed(stats, interaction.guild.name)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="userhistory", description="View moderation history for a user (Moderator only)")
    @app_commands.describe(user="The user to check history for")
    async def userhistory(self, interaction: discord.Interaction, user: discord.User):
        """View a user's moderation history"""
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="userhistory",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check for Moderator permissions
        has_permission = (
            interaction.user.guild_permissions.manage_messages or
            interaction.user.guild_permissions.manage_guild or
            interaction.user.guild_permissions.administrator
        )

        if not has_permission:
            await interaction.response.send_message(
                "You need **Manage Messages** permission or higher to view user history!",
                ephemeral=True
            )
            return

        history = get_user_history(interaction.guild.id, user.id, limit=20)

        embed = discord.Embed(
            title=f"\U0001f4cb Moderation History",
            description=f"**User:** {user.mention} ({user.id})",
            color=discord.Color.orange()
        )

        if not history:
            embed.add_field(
                name="No History",
                value=f"{user.display_name} has no moderation history in this server.",
                inline=False
            )
        else:
            for log in history[:10]:  # Show last 10
                action = log.get("action", "unknown")
                emoji = format_action_emoji(action)
                timestamp = format_timestamp(log.get("timestamp", ""))
                mod = log.get("moderator", {}).get("name", "Unknown")
                reason = log.get("reason", "No reason provided")

                if len(reason) > 100:
                    reason = reason[:97] + "..."

                embed.add_field(
                    name=f"{emoji} {action.upper()} - {timestamp}",
                    value=f"By: {mod}\nReason: {reason}",
                    inline=False
                )

        total = len(history)
        embed.set_footer(text=f"Showing {min(10, total)} of {total} total actions")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="modactivity", description="View a moderator's action history (Moderator only)")
    @app_commands.describe(moderator="The moderator to check activity for (leave empty for yourself)")
    async def modactivity(
        self,
        interaction: discord.Interaction,
        moderator: Optional[discord.User] = None
    ):
        """View what actions a moderator has taken"""
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="modactivity",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check for Moderator permissions
        has_permission = (
            interaction.user.guild_permissions.manage_messages or
            interaction.user.guild_permissions.manage_guild or
            interaction.user.guild_permissions.administrator
        )

        if not has_permission:
            await interaction.response.send_message(
                "You need **Manage Messages** permission or higher to view moderator activity!",
                ephemeral=True
            )
            return

        # Default to self if no moderator specified
        target_mod = moderator or interaction.user

        activity = get_moderator_activity(interaction.guild.id, target_mod.id, limit=25)

        embed = discord.Embed(
            title=f"\U0001f6e1\ufe0f Moderator Activity",
            description=f"**Moderator:** {target_mod.mention} ({target_mod.id})",
            color=discord.Color.blue()
        )

        if not activity:
            embed.add_field(
                name="No Activity",
                value=f"{target_mod.display_name} has no recorded moderation actions in this server.",
                inline=False
            )
        else:
            for log in activity[:15]:  # Show last 15
                action = log.get("action", "unknown")
                emoji = format_action_emoji(action)
                timestamp = format_timestamp(log.get("timestamp", ""))

                target = log.get("target", {})
                target_name = target.get("name", "N/A")
                reason = log.get("reason", "No reason")

                if len(reason) > 80:
                    reason = reason[:77] + "..."

                # Build value text
                if target_name != "N/A":
                    value = f"**Target:** {target_name}\n**Reason:** {reason}"
                else:
                    # For actions without a target (like modtalk)
                    details = log.get("details", {})
                    if details:
                        detail_str = ", ".join(f"{k}: {v}" for k, v in details.items() if v)
                        value = f"**Details:** {detail_str}" if detail_str else "No details"
                    else:
                        value = f"**Reason:** {reason}"

                embed.add_field(
                    name=f"{emoji} {action.upper()} - {timestamp}",
                    value=value,
                    inline=False
                )

        total = len(activity)
        embed.set_footer(text=f"Showing {min(15, total)} of {total} recorded actions")

        await interaction.response.send_message(embed=embed, ephemeral=True)

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

        # Confirmation view
        class ConfirmView(View):
            def __init__(self):
                super().__init__(timeout=30)
                self.confirmed = False

            @discord.ui.button(label="Yes, Clear All Logs", style=discord.ButtonStyle.danger)
            async def confirm(self, inter: discord.Interaction, button: Button):
                self.confirmed = True
                clear_logs(interaction.guild.id)
                await inter.response.edit_message(
                    content="\u2705 All moderation logs have been cleared.",
                    view=None
                )
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, inter: discord.Interaction, button: Button):
                await inter.response.edit_message(
                    content="Log clearing cancelled.",
                    view=None
                )
                self.stop()

        await interaction.response.send_message(
            "\u26a0\ufe0f **Warning:** This will permanently delete all moderation logs for this server. "
            "This action cannot be undone!\n\nAre you sure you want to continue?",
            view=ConfirmView(),
            ephemeral=True
        )


# Required setup function
async def setup(bot: commands.Bot):
    """Add the ModerationLogs cog to the bot"""
    await bot.add_cog(ModerationLogs(bot))
