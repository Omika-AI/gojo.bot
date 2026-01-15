"""
/moderationdatabase Command
Unified moderation database interface for viewing logs, statistics, and user history

Features (accessible via buttons):
- View Moderation Logs
- Moderation Statistics
- User History
- Moderator Activity
- Search Event Logs
- Event Log Statistics
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from typing import Optional, List
from datetime import datetime

from utils.logger import log_command, logger
from utils.moderation_logs import (
    get_logs,
    get_total_logs,
    get_stats as get_mod_stats,
    get_user_history,
    get_moderator_activity,
    format_action_emoji,
    ModAction
)
from utils.event_logs_db import (
    search_logs,
    get_stats as get_event_stats,
    get_guild_config,
    format_event_emoji,
    format_category_color,
    EventCategory
)


# =============================================================================
# CONSTANTS
# =============================================================================

LOGS_PER_PAGE = 10
EVENT_LOGS_PER_PAGE = 5


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


def format_timestamp_full(iso_string: str) -> str:
    """Convert ISO timestamp to full Discord timestamp"""
    try:
        dt = datetime.fromisoformat(iso_string)
        return f"<t:{int(dt.timestamp())}:f>"
    except:
        return iso_string


def create_log_embed(
    logs: List[dict],
    page: int,
    total_pages: int,
    title: str = "Moderation Logs",
    filter_info: Optional[str] = None
) -> discord.Embed:
    """Create an embed displaying moderation logs"""
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

            mod = log.get("moderator", {})
            mod_name = mod.get("name", "Unknown")

            target = log.get("target", {})
            target_name = target.get("name")

            entry_parts = [f"**{action.upper()}** by {mod_name}"]

            if target_name:
                entry_parts.append(f"on **{target_name}**")

            reason = log.get("reason")
            if reason:
                if len(reason) > 100:
                    reason = reason[:97] + "..."
                entry_parts.append(f"\n> Reason: {reason}")

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


def create_mod_stats_embed(stats: dict, guild_name: str) -> discord.Embed:
    """Create an embed displaying moderation statistics"""
    embed = discord.Embed(
        title=f"\U0001f4ca Moderation Statistics",
        description=f"**Server:** {guild_name}",
        color=discord.Color.gold()
    )

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

    moderators = stats.get("moderators", {})
    if moderators:
        sorted_mods = sorted(
            moderators.items(),
            key=lambda x: x[1].get("total", 0),
            reverse=True
        )[:5]

        mod_text = []
        medals = ["\U0001f947", "\U0001f948", "\U0001f949", "4\ufe0f\u20e3", "5\ufe0f\u20e3"]
        for i, (mod_id, mod_data) in enumerate(sorted_mods, 1):
            name = mod_data.get("name", "Unknown")
            total = mod_data.get("total", 0)
            medal = medals[i-1] if i <= len(medals) else f"{i}."
            mod_text.append(f"{medal} **{name}:** {total} actions")

        embed.add_field(
            name="\U0001f3c6 Top Moderators",
            value="\n".join(mod_text) if mod_text else "No moderator data",
            inline=False
        )

    total = stats.get("total", 0)
    embed.add_field(
        name="\U0001f522 Total Logged Actions",
        value=str(total),
        inline=True
    )

    return embed


# =============================================================================
# SUB-VIEWS FOR EACH FEATURE
# =============================================================================

class ModLogsView(View):
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

        self.total_logs = get_total_logs(
            guild_id,
            action_filter=action_filter,
            moderator_filter=moderator_filter,
            target_filter=target_filter
        )
        self.total_pages = max(1, (self.total_logs + LOGS_PER_PAGE - 1) // LOGS_PER_PAGE)
        self._update_buttons()

    def _update_buttons(self):
        for item in self.children:
            if isinstance(item, Button):
                if item.custom_id == "first" or item.custom_id == "prev":
                    item.disabled = self.page <= 1
                elif item.custom_id == "next" or item.custom_id == "last":
                    item.disabled = self.page >= self.total_pages

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your view!", ephemeral=True)
            return False
        return True

    def get_logs_embed(self) -> discord.Embed:
        offset = (self.page - 1) * LOGS_PER_PAGE
        logs = get_logs(
            self.guild_id,
            limit=LOGS_PER_PAGE,
            offset=offset,
            action_filter=self.action_filter,
            moderator_filter=self.moderator_filter,
            target_filter=self.target_filter
        )

        filter_parts = []
        if self.action_filter:
            filter_parts.append(f"Action: {self.action_filter.value}")
        if self.moderator_filter:
            filter_parts.append(f"Moderator ID: {self.moderator_filter}")
        if self.target_filter:
            filter_parts.append(f"Target ID: {self.target_filter}")

        filter_info = " | ".join(filter_parts) if filter_parts else None

        return create_log_embed(logs, self.page, self.total_pages, filter_info=filter_info)

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

    @discord.ui.button(label="Back to Menu", style=discord.ButtonStyle.danger, row=1)
    async def back_to_menu(self, interaction: discord.Interaction, button: Button):
        view = ModerationDatabaseMainView(interaction.user.id, interaction.guild.id)
        await interaction.response.edit_message(embed=view.get_main_embed(), view=view)


class UserHistoryModal(Modal):
    """Modal for entering user to check history"""

    def __init__(self, user_id: int, guild_id: int):
        super().__init__(title="User History Lookup")
        self.viewer_id = user_id
        self.guild_id = guild_id

        self.user_input = TextInput(
            label="User ID or @mention",
            placeholder="Enter user ID (e.g., 123456789) or @username",
            required=True,
            max_length=100
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_text = self.user_input.value.strip()

        # Parse user ID from mention or direct ID
        import re
        mention_match = re.match(r'<@!?(\d+)>', user_text)
        if mention_match:
            user_id = int(mention_match.group(1))
        elif user_text.isdigit():
            user_id = int(user_text)
        else:
            # Try to find by name
            member = discord.utils.find(
                lambda m: m.name.lower() == user_text.lower() or m.display_name.lower() == user_text.lower(),
                interaction.guild.members
            )
            if member:
                user_id = member.id
            else:
                await interaction.response.send_message(
                    f"Could not find user `{user_text}`. Try using their ID instead.",
                    ephemeral=True
                )
                return

        # Get user info
        user = interaction.guild.get_member(user_id) or await interaction.client.fetch_user(user_id)
        history = get_user_history(self.guild_id, user_id, limit=20)

        embed = discord.Embed(
            title=f"\U0001f4cb Moderation History",
            description=f"**User:** {user.mention if hasattr(user, 'mention') else user} ({user_id})",
            color=discord.Color.orange()
        )

        if not history:
            embed.add_field(
                name="No History",
                value="This user has no moderation history in this server.",
                inline=False
            )
        else:
            for log in history[:10]:
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

        # Create back button view
        view = BackToMenuView(self.viewer_id, self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)


class ModActivityModal(Modal):
    """Modal for entering moderator to check activity"""

    def __init__(self, user_id: int, guild_id: int):
        super().__init__(title="Moderator Activity Lookup")
        self.viewer_id = user_id
        self.guild_id = guild_id

        self.mod_input = TextInput(
            label="Moderator ID or @mention (leave empty for yourself)",
            placeholder="Enter mod ID or @username, or leave blank",
            required=False,
            max_length=100
        )
        self.add_item(self.mod_input)

    async def on_submit(self, interaction: discord.Interaction):
        mod_text = self.mod_input.value.strip()

        if not mod_text:
            target_mod = interaction.user
            mod_id = interaction.user.id
        else:
            import re
            mention_match = re.match(r'<@!?(\d+)>', mod_text)
            if mention_match:
                mod_id = int(mention_match.group(1))
            elif mod_text.isdigit():
                mod_id = int(mod_text)
            else:
                member = discord.utils.find(
                    lambda m: m.name.lower() == mod_text.lower() or m.display_name.lower() == mod_text.lower(),
                    interaction.guild.members
                )
                if member:
                    mod_id = member.id
                else:
                    await interaction.response.send_message(
                        f"Could not find moderator `{mod_text}`.",
                        ephemeral=True
                    )
                    return

            target_mod = interaction.guild.get_member(mod_id) or await interaction.client.fetch_user(mod_id)

        activity = get_moderator_activity(self.guild_id, mod_id, limit=25)

        embed = discord.Embed(
            title=f"\U0001f6e1\ufe0f Moderator Activity",
            description=f"**Moderator:** {target_mod.mention if hasattr(target_mod, 'mention') else target_mod}",
            color=discord.Color.blue()
        )

        if not activity:
            embed.add_field(
                name="No Activity",
                value="This moderator has no recorded actions in this server.",
                inline=False
            )
        else:
            for log in activity[:15]:
                action = log.get("action", "unknown")
                emoji = format_action_emoji(action)
                timestamp = format_timestamp(log.get("timestamp", ""))

                target = log.get("target", {})
                target_name = target.get("name", "N/A")
                reason = log.get("reason", "No reason")

                if len(reason) > 80:
                    reason = reason[:77] + "..."

                if target_name != "N/A":
                    value = f"**Target:** {target_name}\n**Reason:** {reason}"
                else:
                    value = f"**Reason:** {reason}"

                embed.add_field(
                    name=f"{emoji} {action.upper()} - {timestamp}",
                    value=value,
                    inline=False
                )

        total = len(activity)
        embed.set_footer(text=f"Showing {min(15, total)} of {total} recorded actions")

        view = BackToMenuView(self.viewer_id, self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)


class SearchLogsModal(Modal):
    """Modal for searching event logs"""

    def __init__(self, user_id: int, guild_id: int):
        super().__init__(title="Search Event Logs")
        self.viewer_id = user_id
        self.guild_id = guild_id

        self.search_text = TextInput(
            label="Search Text (optional)",
            placeholder="Enter words to search for in messages",
            required=False,
            max_length=200
        )
        self.user_filter = TextInput(
            label="User ID (optional)",
            placeholder="Filter by user ID",
            required=False,
            max_length=20
        )
        self.category = TextInput(
            label="Category (optional)",
            placeholder="messages, members, voice, server, commands, moderation",
            required=False,
            max_length=20
        )

        self.add_item(self.search_text)
        self.add_item(self.user_filter)
        self.add_item(self.category)

    async def on_submit(self, interaction: discord.Interaction):
        search = self.search_text.value.strip() or None
        user_id = int(self.user_filter.value.strip()) if self.user_filter.value.strip().isdigit() else None
        category = self.category.value.strip().lower() if self.category.value.strip() else None

        # Validate category
        valid_categories = ["messages", "members", "voice", "server", "commands", "moderation"]
        if category and category not in valid_categories:
            await interaction.response.send_message(
                f"Invalid category. Use one of: {', '.join(valid_categories)}",
                ephemeral=True
            )
            return

        # Search logs
        logs, total = search_logs(
            guild_id=self.guild_id,
            query=search,
            user_filter=user_id,
            category_filter=category,
            limit=10,
            offset=0
        )

        embed = discord.Embed(
            title="Event Log Search Results",
            color=discord.Color.blue()
        )

        filter_parts = []
        if search:
            filter_parts.append(f"Text: `{search}`")
        if user_id:
            filter_parts.append(f"User: <@{user_id}>")
        if category:
            filter_parts.append(f"Category: `{category}`")

        embed.description = f"**Filters:** {', '.join(filter_parts) if filter_parts else 'None'}\n**Total Results:** {total}\n"

        if not logs:
            embed.description += "\n*No logs found matching your search.*"
        else:
            for i, log in enumerate(logs[:10], 1):
                event_type = log.get("event_type", "unknown")
                emoji = format_event_emoji(event_type)
                timestamp = format_timestamp(log.get("timestamp", ""))

                user = log.get("user", {})
                user_name = user.get("name", "Unknown")

                event_display = event_type.replace("_", " ").title()
                entry = f"**{event_display}** by `{user_name}`"

                before = log.get("before", "")
                if before:
                    preview = before[:80] + "..." if len(before) > 80 else before
                    entry += f"\n> {preview}"

                embed.add_field(
                    name=f"{emoji} {timestamp}",
                    value=entry,
                    inline=False
                )

        embed.set_footer(text=f"Showing {min(10, total)} of {total} results")

        view = BackToMenuView(self.viewer_id, self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)


class BackToMenuView(View):
    """Simple view with back to menu button"""

    def __init__(self, user_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your view!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Back to Menu", style=discord.ButtonStyle.primary, emoji="\u2b05")
    async def back_to_menu(self, interaction: discord.Interaction, button: Button):
        view = ModerationDatabaseMainView(self.user_id, self.guild_id)
        await interaction.response.edit_message(embed=view.get_main_embed(), view=view)


# =============================================================================
# MAIN VIEW
# =============================================================================

class ModerationDatabaseMainView(View):
    """Main menu view for moderation database with buttons"""

    def __init__(self, user_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return False
        return True

    def get_main_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="\U0001f4be Moderation Database",
            description="Click a button below to access moderation data.",
            color=discord.Color.dark_blue()
        )

        embed.add_field(
            name="\U0001f4dc Moderation Logs",
            value="View all moderation actions",
            inline=True
        )
        embed.add_field(
            name="\U0001f4ca Mod Statistics",
            value="Action breakdown & top mods",
            inline=True
        )
        embed.add_field(
            name="\U0001f464 User History",
            value="Check a user's mod history",
            inline=True
        )
        embed.add_field(
            name="\U0001f6e1 Mod Activity",
            value="View moderator's actions",
            inline=True
        )
        embed.add_field(
            name="\U0001f50d Search Logs",
            value="Search event logs",
            inline=True
        )
        embed.add_field(
            name="\U0001f4c8 Event Stats",
            value="Event logging statistics",
            inline=True
        )

        return embed

    @discord.ui.button(label="Mod Logs", style=discord.ButtonStyle.primary, emoji="\U0001f4dc", row=0)
    async def mod_logs_btn(self, interaction: discord.Interaction, button: Button):
        """View moderation logs"""
        view = ModLogsView(guild_id=self.guild_id, user_id=self.user_id)
        await interaction.response.edit_message(embed=view.get_logs_embed(), view=view)

    @discord.ui.button(label="Mod Stats", style=discord.ButtonStyle.primary, emoji="\U0001f4ca", row=0)
    async def mod_stats_btn(self, interaction: discord.Interaction, button: Button):
        """View moderation statistics"""
        stats = get_mod_stats(self.guild_id)
        embed = create_mod_stats_embed(stats, interaction.guild.name)
        view = BackToMenuView(self.user_id, self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="User History", style=discord.ButtonStyle.primary, emoji="\U0001f464", row=0)
    async def user_history_btn(self, interaction: discord.Interaction, button: Button):
        """Check a user's moderation history"""
        await interaction.response.send_modal(UserHistoryModal(self.user_id, self.guild_id))

    @discord.ui.button(label="Mod Activity", style=discord.ButtonStyle.secondary, emoji="\U0001f6e1", row=1)
    async def mod_activity_btn(self, interaction: discord.Interaction, button: Button):
        """View a moderator's action history"""
        await interaction.response.send_modal(ModActivityModal(self.user_id, self.guild_id))

    @discord.ui.button(label="Search Logs", style=discord.ButtonStyle.secondary, emoji="\U0001f50d", row=1)
    async def search_logs_btn(self, interaction: discord.Interaction, button: Button):
        """Search through event logs"""
        config = get_guild_config(self.guild_id)
        if not config:
            await interaction.response.send_message(
                "Event logging is not set up yet! Use `/setuplogs` to configure logging first.",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(SearchLogsModal(self.user_id, self.guild_id))

    @discord.ui.button(label="Event Stats", style=discord.ButtonStyle.secondary, emoji="\U0001f4c8", row=1)
    async def event_stats_btn(self, interaction: discord.Interaction, button: Button):
        """View event logging statistics"""
        config = get_guild_config(self.guild_id)
        if not config:
            await interaction.response.send_message(
                "Event logging is not set up yet! Use `/setuplogs` to configure logging first.",
                ephemeral=True
            )
            return

        stats = get_event_stats(self.guild_id)
        embed = discord.Embed(
            title="Event Log Statistics",
            description=f"**Server:** {interaction.guild.name}",
            color=discord.Color.gold()
        )

        categories = stats.get("categories", {})
        if categories:
            cat_text = []
            for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                cat_text.append(f"**{cat.title()}:** {count}")
            embed.add_field(
                name="Category Breakdown",
                value="\n".join(cat_text) if cat_text else "No events logged",
                inline=False
            )

        total = stats.get("total", 0)
        embed.add_field(name="Total Events Logged", value=str(total), inline=True)
        embed.add_field(name="Log Channel", value=f"<#{config['channel_id']}>", inline=True)

        view = BackToMenuView(self.user_id, self.guild_id)
        await interaction.response.edit_message(embed=embed, view=view)


# =============================================================================
# COG
# =============================================================================

class ModerationDatabase(commands.Cog):
    """Unified moderation database interface"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="moderationdatabase",
        description="Access moderation logs, statistics, and user history (Moderator only)"
    )
    async def moderationdatabase(self, interaction: discord.Interaction):
        """Open the moderation database interface"""
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="moderationdatabase",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check for moderator permissions
        has_permission = (
            interaction.user.guild_permissions.manage_messages or
            interaction.user.guild_permissions.manage_guild or
            interaction.user.guild_permissions.administrator
        )

        if not has_permission:
            await interaction.response.send_message(
                "You need **Manage Messages** permission or higher to access the moderation database!",
                ephemeral=True
            )
            return

        # Show the main menu
        view = ModerationDatabaseMainView(interaction.user.id, interaction.guild.id)
        await interaction.response.send_message(
            embed=view.get_main_embed(),
            view=view,
            ephemeral=True
        )


# Required setup function
async def setup(bot: commands.Bot):
    """Add the ModerationDatabase cog to the bot"""
    await bot.add_cog(ModerationDatabase(bot))
