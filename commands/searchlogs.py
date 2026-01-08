"""
Search Logs Command
Search through event logs with filters
Server Owner and Admins - Supports user, category, and text search

Commands:
- /searchlogs - Search event logs with text, user, or category filters
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from typing import Optional, List
from datetime import datetime

from utils.logger import log_command, logger
from utils.event_logs_db import (
    search_logs,
    get_stats,
    get_guild_config,
    format_event_emoji,
    format_category_color,
    EventCategory
)


# =============================================================================
# CONSTANTS
# =============================================================================

LOGS_PER_PAGE = 5  # Reduced to show more detail per entry


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_timestamp(iso_string: str) -> str:
    """Convert ISO timestamp to Discord timestamp"""
    try:
        dt = datetime.fromisoformat(iso_string)
        return f"<t:{int(dt.timestamp())}:f>"
    except:
        return iso_string


def format_timestamp_relative(iso_string: str) -> str:
    """Convert ISO timestamp to relative Discord timestamp"""
    try:
        dt = datetime.fromisoformat(iso_string)
        return f"<t:{int(dt.timestamp())}:R>"
    except:
        return iso_string


def create_search_embed(
    logs: List[dict],
    page: int,
    total_pages: int,
    total_results: int,
    filter_info: Optional[str] = None
) -> discord.Embed:
    """Create an embed displaying search results with numbered entries"""
    embed = discord.Embed(
        title="Event Log Search Results",
        color=discord.Color.blue()
    )

    desc_parts = []
    if filter_info:
        desc_parts.append(f"**Filters:** {filter_info}")
    desc_parts.append(f"**Total Results:** {total_results}")
    desc_parts.append("\n*Click a number button below to see full details*\n")
    embed.description = "\n".join(desc_parts)

    if not logs:
        embed.description += "\n*No logs found matching your search.*"
    else:
        for i, log in enumerate(logs, 1):
            event_type = log.get("event_type", "unknown")
            category = log.get("category", "unknown")
            emoji = format_event_emoji(event_type)
            timestamp = format_timestamp_relative(log.get("timestamp", ""))

            # Get user info
            user = log.get("user", {})
            user_name = user.get("name", "Unknown")
            user_id = user.get("id", "Unknown")

            # Format event type nicely
            event_display = event_type.replace("_", " ").title()

            # Build the entry with number
            entry_parts = [f"**{event_display}** by `{user_name}`"]

            # Add channel if present
            channel = log.get("channel", {})
            channel_id = channel.get("id")
            if channel_id:
                entry_parts.append(f"in <#{channel_id}>")

            # Add content preview for message events
            before = log.get("before", "")
            after = log.get("after", "")

            if event_type == "message_delete" and before:
                # Show deleted message preview
                preview = before[:100] + "..." if len(before) > 100 else before
                entry_parts.append(f"\n> {preview}")
            elif event_type == "message_edit" and before and after:
                # Show edit preview
                before_short = before[:40] + "..." if len(before) > 40 else before
                after_short = after[:40] + "..." if len(after) > 40 else after
                entry_parts.append(f"\n> `{before_short}` → `{after_short}`")
            elif before:
                preview = before[:80] + "..." if len(before) > 80 else before
                entry_parts.append(f"\n> {preview}")

            embed.add_field(
                name=f"`{i}.` {emoji} {timestamp}",
                value=" ".join(entry_parts),
                inline=False
            )

    embed.set_footer(text=f"Page {page}/{total_pages} | Click number to view full details")

    return embed


def create_detail_embed(log: dict) -> discord.Embed:
    """Create a detailed embed for a single log entry"""
    event_type = log.get("event_type", "unknown")
    category = log.get("category", "unknown")
    emoji = format_event_emoji(event_type)
    color = format_category_color(category)

    event_display = event_type.replace("_", " ").title()

    embed = discord.Embed(
        title=f"{emoji} {event_display} - Full Details",
        color=color,
        timestamp=datetime.fromisoformat(log.get("timestamp", datetime.utcnow().isoformat()))
    )

    # User info
    user = log.get("user", {})
    user_name = user.get("name", "Unknown")
    user_id = user.get("id", "Unknown")
    user_display = user.get("display_name", user_name)

    embed.add_field(
        name="User",
        value=f"**Name:** {user_name}\n**Display:** {user_display}\n**ID:** `{user_id}`",
        inline=True
    )

    # Channel info
    channel = log.get("channel", {})
    channel_id = channel.get("id")
    channel_name = channel.get("name", "Unknown")
    if channel_id:
        embed.add_field(
            name="Channel",
            value=f"<#{channel_id}>\n`{channel_name}`",
            inline=True
        )

    # Target info (if present)
    target = log.get("target", {})
    target_name = target.get("name")
    target_id = target.get("id")
    if target_name:
        embed.add_field(
            name="Target",
            value=f"**Name:** {target_name}\n**ID:** `{target_id}`",
            inline=True
        )

    # Before content (full)
    before = log.get("before")
    if before:
        # Split into chunks if too long
        if len(before) > 1024:
            embed.add_field(
                name="Before / Original Content",
                value=before[:1020] + "...",
                inline=False
            )
            if len(before) > 1024:
                embed.add_field(
                    name="Before (continued)",
                    value="..." + before[1020:2040],
                    inline=False
                )
        else:
            embed.add_field(
                name="Before / Original Content",
                value=before or "*Empty*",
                inline=False
            )

    # After content (full)
    after = log.get("after")
    if after:
        if len(after) > 1024:
            embed.add_field(
                name="After / New Content",
                value=after[:1020] + "...",
                inline=False
            )
        else:
            embed.add_field(
                name="After / New Content",
                value=after or "*Empty*",
                inline=False
            )

    # Additional details
    details = log.get("details", {})
    if details:
        detail_text = "\n".join([f"**{k}:** {v}" for k, v in details.items()])
        if len(detail_text) > 1024:
            detail_text = detail_text[:1020] + "..."
        embed.add_field(
            name="Additional Details",
            value=detail_text,
            inline=False
        )

    # Log ID and category
    embed.set_footer(text=f"Log ID: {log.get('id', 'N/A')} | Category: {category.upper()}")

    return embed


def create_stats_embed(stats: dict, guild_name: str) -> discord.Embed:
    """Create an embed displaying event log statistics"""
    embed = discord.Embed(
        title="Event Log Statistics",
        description=f"**Server:** {guild_name}",
        color=discord.Color.gold()
    )

    # Category breakdown
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

    # Total
    total = stats.get("total", 0)
    embed.add_field(
        name="Total Events Logged",
        value=str(total),
        inline=True
    )

    embed.set_footer(text="Use /searchlogs to search through logs")

    return embed


# =============================================================================
# VIEWS
# =============================================================================

class SearchLogsView(View):
    """View for navigating search results with pagination and detail view"""

    def __init__(
        self,
        guild_id: int,
        user_id: int,
        search_text: Optional[str] = None,
        user_filter: Optional[int] = None,
        category_filter: Optional[str] = None,
        page: int = 1
    ):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user_id = user_id
        self.search_text = search_text
        self.user_filter = user_filter
        self.category_filter = category_filter
        self.page = page
        self.current_logs = []  # Store current page logs for detail view

        # Get results to calculate total pages
        _, self.total_results = search_logs(
            guild_id=guild_id,
            query=search_text,
            user_filter=user_filter,
            category_filter=category_filter,
            limit=1,
            offset=0
        )

        self.total_pages = max(1, (self.total_results + LOGS_PER_PAGE - 1) // LOGS_PER_PAGE)

        # Update button states
        self._update_buttons()

    def _update_buttons(self):
        """Update button disabled states based on current page"""
        for item in self.children:
            if isinstance(item, Button):
                if item.custom_id == "first" or item.custom_id == "prev":
                    item.disabled = self.page <= 1
                elif item.custom_id == "next" or item.custom_id == "last":
                    item.disabled = self.page >= self.total_pages

    def get_filter_info(self) -> Optional[str]:
        """Get a string describing active filters"""
        filters = []
        if self.search_text:
            filters.append(f"Text: `{self.search_text}`")
        if self.user_filter:
            filters.append(f"User: <@{self.user_filter}>")
        if self.category_filter:
            filters.append(f"Category: `{self.category_filter}`")

        return ", ".join(filters) if filters else None

    async def get_embed(self) -> discord.Embed:
        """Get the current page embed"""
        offset = (self.page - 1) * LOGS_PER_PAGE

        logs, total = search_logs(
            guild_id=self.guild_id,
            query=self.search_text,
            user_filter=self.user_filter,
            category_filter=self.category_filter,
            limit=LOGS_PER_PAGE,
            offset=offset
        )

        # Store logs for detail view
        self.current_logs = logs

        return create_search_embed(
            logs=logs,
            page=self.page,
            total_pages=self.total_pages,
            total_results=total,
            filter_info=self.get_filter_info()
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to interact"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your search! Use `/searchlogs` to search.",
                ephemeral=True
            )
            return False
        return True

    async def show_detail(self, interaction: discord.Interaction, index: int):
        """Show detailed view of a specific log entry"""
        if index < 1 or index > len(self.current_logs):
            await interaction.response.send_message(
                f"Invalid entry number. Choose between 1 and {len(self.current_logs)}.",
                ephemeral=True
            )
            return

        log = self.current_logs[index - 1]
        embed = create_detail_embed(log)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Number buttons for selecting log entries
    @discord.ui.button(label="1", style=discord.ButtonStyle.secondary, custom_id="detail_1", row=0)
    async def detail_1(self, interaction: discord.Interaction, button: Button):
        await self.show_detail(interaction, 1)

    @discord.ui.button(label="2", style=discord.ButtonStyle.secondary, custom_id="detail_2", row=0)
    async def detail_2(self, interaction: discord.Interaction, button: Button):
        await self.show_detail(interaction, 2)

    @discord.ui.button(label="3", style=discord.ButtonStyle.secondary, custom_id="detail_3", row=0)
    async def detail_3(self, interaction: discord.Interaction, button: Button):
        await self.show_detail(interaction, 3)

    @discord.ui.button(label="4", style=discord.ButtonStyle.secondary, custom_id="detail_4", row=0)
    async def detail_4(self, interaction: discord.Interaction, button: Button):
        await self.show_detail(interaction, 4)

    @discord.ui.button(label="5", style=discord.ButtonStyle.secondary, custom_id="detail_5", row=0)
    async def detail_5(self, interaction: discord.Interaction, button: Button):
        await self.show_detail(interaction, 5)

    # Navigation buttons
    @discord.ui.button(label="<<", style=discord.ButtonStyle.primary, custom_id="first", row=1)
    async def first_page(self, interaction: discord.Interaction, button: Button):
        """Go to first page"""
        self.page = 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.get_embed(), view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary, custom_id="prev", row=1)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        """Go to previous page"""
        if self.page > 1:
            self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.get_embed(), view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary, custom_id="next", row=1)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        """Go to next page"""
        if self.page < self.total_pages:
            self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.get_embed(), view=self)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.primary, custom_id="last", row=1)
    async def last_page(self, interaction: discord.Interaction, button: Button):
        """Go to last page"""
        self.page = self.total_pages
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.get_embed(), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="close", row=1)
    async def close(self, interaction: discord.Interaction, button: Button):
        """Close the search results"""
        await interaction.response.edit_message(content="Search closed.", embed=None, view=None)
        self.stop()


# =============================================================================
# COG
# =============================================================================

class SearchLogs(commands.Cog):
    """Search through event logs"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="searchlogs",
        description="Search event logs (Owner/Admin only)"
    )
    @app_commands.describe(
        search_text="Search for specific words or sentences in messages (e.g., 'bad word')",
        user="Filter logs by a specific user",
        category="Filter by category (messages, members, voice, server, commands)"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="Messages", value="messages"),
        app_commands.Choice(name="Members", value="members"),
        app_commands.Choice(name="Voice", value="voice"),
        app_commands.Choice(name="Server", value="server"),
        app_commands.Choice(name="Commands", value="commands"),
        app_commands.Choice(name="Moderation", value="moderation")
    ])
    async def searchlogs(
        self,
        interaction: discord.Interaction,
        search_text: Optional[str] = None,
        user: Optional[discord.User] = None,
        category: Optional[str] = None
    ):
        """
        Search event logs

        Examples:
        - /searchlogs search_text:badword - Find messages containing "badword"
        - /searchlogs user:@someone - See all logs related to someone
        - /searchlogs category:Messages - See only message logs
        - /searchlogs search_text:hello user:@someone - Combined search
        """
        # Log the command usage (to internal log only, not to webhook)
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="searchlogs",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check server owner or admin permission
        is_owner = interaction.user.id == interaction.guild.owner_id
        is_admin = interaction.user.guild_permissions.administrator

        if not is_owner and not is_admin:
            await interaction.response.send_message(
                "Only the **Server Owner** or **Administrators** can search event logs!",
                ephemeral=True
            )
            return

        # Check if logging is configured
        config = get_guild_config(interaction.guild.id)
        if not config:
            await interaction.response.send_message(
                "Event logging is not set up yet!\n"
                "Use `/setuplogs` to configure logging first.",
                ephemeral=True
            )
            return

        # Create the search view
        view = SearchLogsView(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            search_text=search_text,
            user_filter=user.id if user else None,
            category_filter=category
        )

        # Get the first page
        embed = await view.get_embed()

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

    @app_commands.command(
        name="logstats",
        description="View event logging statistics (Owner/Admin only)"
    )
    async def logstats(self, interaction: discord.Interaction):
        """View event log statistics"""
        # Log the command usage
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="logstats",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check server owner or admin permission
        is_owner = interaction.user.id == interaction.guild.owner_id
        is_admin = interaction.user.guild_permissions.administrator

        if not is_owner and not is_admin:
            await interaction.response.send_message(
                "Only the **Server Owner** or **Administrators** can view log statistics!",
                ephemeral=True
            )
            return

        # Check if logging is configured
        config = get_guild_config(interaction.guild.id)
        if not config:
            await interaction.response.send_message(
                "Event logging is not set up yet!\n"
                "Use `/setuplogs` to configure logging first.",
                ephemeral=True
            )
            return

        # Get statistics
        stats = get_stats(interaction.guild.id)

        # Create stats embed
        embed = create_stats_embed(stats, interaction.guild.name)

        # Add config info
        embed.add_field(
            name="Log Channel",
            value=f"<#{config['channel_id']}>",
            inline=True
        )

        configured_at = config.get("configured_at", "Unknown")
        if configured_at != "Unknown":
            try:
                dt = datetime.fromisoformat(configured_at)
                configured_at = f"<t:{int(dt.timestamp())}:R>"
            except:
                pass

        embed.add_field(
            name="Configured",
            value=configured_at,
            inline=True
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


# Required setup function
async def setup(bot: commands.Bot):
    """Add the SearchLogs cog to the bot"""
    await bot.add_cog(SearchLogs(bot))
