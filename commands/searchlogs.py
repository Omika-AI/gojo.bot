"""
Search Logs Command
Search through event logs with filters
Server Owner only - Supports user, category, and text search

Commands:
- /searchlogs - Search event logs
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
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


def create_search_embed(
    logs: List[dict],
    page: int,
    total_pages: int,
    total_results: int,
    filter_info: Optional[str] = None
) -> discord.Embed:
    """Create an embed displaying search results"""
    embed = discord.Embed(
        title="Event Log Search Results",
        color=discord.Color.blue()
    )

    if filter_info:
        embed.description = f"**Filters:** {filter_info}\n**Results:** {total_results}\n\n"
    else:
        embed.description = f"**Results:** {total_results}\n\n"

    if not logs:
        embed.description += "*No logs found matching your search.*"
    else:
        for log in logs:
            event_type = log.get("event_type", "unknown")
            category = log.get("category", "unknown")
            emoji = format_event_emoji(event_type)
            timestamp = format_timestamp(log.get("timestamp", ""))

            # Get user info
            user = log.get("user", {})
            user_name = user.get("name", "Unknown")
            user_id = user.get("id", "Unknown")

            # Format event type nicely
            event_display = event_type.replace("_", " ").title()

            # Build the entry
            entry_parts = [f"**{event_display}** by **{user_name}** ({user_id})"]

            # Add channel if present
            channel = log.get("channel", {})
            channel_id = channel.get("id")
            if channel_id:
                entry_parts.append(f"in <#{channel_id}>")

            # Add target if present
            target = log.get("target", {})
            target_name = target.get("name")
            if target_name:
                entry_parts.append(f"\nTarget: **{target_name}**")

            # Add before/after for edits
            before = log.get("before")
            after = log.get("after")

            if before and after:
                # Truncate long content
                before_short = before[:50] + "..." if len(before) > 50 else before
                after_short = after[:50] + "..." if len(after) > 50 else after
                entry_parts.append(f"\n`{before_short}` -> `{after_short}`")
            elif before:
                before_short = before[:80] + "..." if len(before) > 80 else before
                entry_parts.append(f"\nContent: `{before_short}`")

            embed.add_field(
                name=f"{emoji} {timestamp} [{category.upper()}]",
                value=" ".join(entry_parts),
                inline=False
            )

    embed.set_footer(text=f"Page {page}/{total_pages} | Logs kept for 30 days")

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
            color_int = format_category_color(cat)
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
    """View for navigating search results with pagination"""

    def __init__(
        self,
        guild_id: int,
        user_id: int,
        query: Optional[str] = None,
        user_filter: Optional[int] = None,
        category_filter: Optional[str] = None,
        page: int = 1
    ):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user_id = user_id
        self.query = query
        self.user_filter = user_filter
        self.category_filter = category_filter
        self.page = page

        # Get results to calculate total pages
        _, self.total_results = search_logs(
            guild_id=guild_id,
            query=query,
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
        # Find and update the navigation buttons
        for item in self.children:
            if isinstance(item, Button):
                if item.custom_id == "first" or item.custom_id == "prev":
                    item.disabled = self.page <= 1
                elif item.custom_id == "next" or item.custom_id == "last":
                    item.disabled = self.page >= self.total_pages

    def get_filter_info(self) -> Optional[str]:
        """Get a string describing active filters"""
        filters = []
        if self.query:
            filters.append(f"Query: `{self.query}`")
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
            query=self.query,
            user_filter=self.user_filter,
            category_filter=self.category_filter,
            limit=LOGS_PER_PAGE,
            offset=offset
        )

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

    @discord.ui.button(label="<<", style=discord.ButtonStyle.secondary, custom_id="first")
    async def first_page(self, interaction: discord.Interaction, button: Button):
        """Go to first page"""
        self.page = 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.get_embed(), view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary, custom_id="prev")
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        """Go to previous page"""
        if self.page > 1:
            self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.get_embed(), view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary, custom_id="next")
    async def next_page(self, interaction: discord.Interaction, button: Button):
        """Go to next page"""
        if self.page < self.total_pages:
            self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.get_embed(), view=self)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary, custom_id="last")
    async def last_page(self, interaction: discord.Interaction, button: Button):
        """Go to last page"""
        self.page = self.total_pages
        self._update_buttons()
        await interaction.response.edit_message(embed=await self.get_embed(), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="close")
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
        description="Search event logs (Server Owner only)"
    )
    @app_commands.describe(
        user="Filter logs by a specific user",
        category="Filter by category (messages, members, voice, server, commands)",
        query="Search text in log content"
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
        user: Optional[discord.User] = None,
        category: Optional[str] = None,
        query: Optional[str] = None
    ):
        """Search event logs"""
        # Log the command usage
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

        # Check server owner permission
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the **Server Owner** can search event logs!",
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
            query=query,
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
        description="View event logging statistics (Server Owner only)"
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

        # Check server owner permission
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the **Server Owner** can view log statistics!",
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
