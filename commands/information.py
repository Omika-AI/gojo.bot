"""
/information Command
Displays bot information, features, and available commands
Shows only commands the user has permission to use

IMPORTANT: Update this file when adding new commands!
Last updated: 2026-01-02
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from typing import List, Dict

import config
from utils.logger import log_command, logger


# =============================================================================
# COMMAND REGISTRY - UPDATE THIS WHEN ADDING NEW COMMANDS
# =============================================================================
# Each command entry contains:
# - name: The command name (e.g., "/ping")
# - description: What the command does
# - usage: Example usage
# - category: Which category it belongs to
# - permission: Required permission (None = everyone, or discord permission name)
#
# Categories: "general", "moderation", "admin", "fun"
# =============================================================================

COMMANDS_REGISTRY = [
    # General Commands (Everyone can use)
    {
        "name": "/ping",
        "description": "Check if the bot is online and responsive",
        "usage": "/ping",
        "category": "general",
        "permission": None
    },
    {
        "name": "/help",
        "description": "Shows a quick list of all commands",
        "usage": "/help",
        "category": "general",
        "permission": None
    },
    {
        "name": "/information",
        "description": "Detailed bot info and command guide (this command)",
        "usage": "/information",
        "category": "general",
        "permission": None
    },
    {
        "name": "/dq",
        "description": "Get a random inspirational quote from movies, anime, and famous people",
        "usage": "/dq",
        "category": "fun",
        "permission": None
    },

    # Music Commands (Everyone can use)
    {
        "name": "/play",
        "description": "Play a song from Spotify link or search query",
        "usage": "/play Bohemian Rhapsody OR /play <spotify link>",
        "category": "music",
        "permission": None
    },
    {
        "name": "/pause",
        "description": "Pause the currently playing song",
        "usage": "/pause",
        "category": "music",
        "permission": None
    },
    {
        "name": "/resume",
        "description": "Resume a paused song",
        "usage": "/resume",
        "category": "music",
        "permission": None
    },
    {
        "name": "/skip",
        "description": "Skip to the next song in queue",
        "usage": "/skip",
        "category": "music",
        "permission": None
    },
    {
        "name": "/stop",
        "description": "Stop music and leave the voice channel",
        "usage": "/stop",
        "category": "music",
        "permission": None
    },
    {
        "name": "/queue",
        "description": "View the current music queue",
        "usage": "/queue",
        "category": "music",
        "permission": None
    },
    {
        "name": "/nowplaying",
        "description": "Show details about the current song",
        "usage": "/nowplaying",
        "category": "music",
        "permission": None
    },
    {
        "name": "/volume",
        "description": "Adjust the music volume (0-100)",
        "usage": "/volume 50",
        "category": "music",
        "permission": None
    },
    {
        "name": "/shuffle",
        "description": "Shuffle the songs in the queue",
        "usage": "/shuffle",
        "category": "music",
        "permission": None
    },
    {
        "name": "/clear",
        "description": "Clear all songs from the queue",
        "usage": "/clear",
        "category": "music",
        "permission": None
    },

    # Moderation Commands (Require specific permissions)
    {
        "name": "/moderationpanel",
        "description": "Interactive panel with all moderation tools (kick, ban, timeout, warn, clear messages)",
        "usage": "/moderationpanel @user",
        "category": "moderation",
        "permission": "moderate_members"
    },
    {
        "name": "/timeout",
        "description": "Temporarily mute a user for a specified time",
        "usage": "/timeout @user 10 Being disruptive",
        "category": "moderation",
        "permission": "moderate_members"
    },
    {
        "name": "/warning",
        "description": "Issue a warning to a user (Minor/Medium/Serious)",
        "usage": "/warning @user Medium Breaking rules",
        "category": "moderation",
        "permission": "manage_messages"
    },
    {
        "name": "/modtalk",
        "description": "Send a message as the bot in any channel",
        "usage": "/modtalk",
        "category": "moderation",
        "permission": "manage_messages"
    },
    {
        "name": "/moderationlogs",
        "description": "View all moderation actions with filters",
        "usage": "/moderationlogs or /moderationlogs @user",
        "category": "moderation",
        "permission": "manage_messages"
    },
    {
        "name": "/modstats",
        "description": "View moderation statistics and top moderators",
        "usage": "/modstats",
        "category": "moderation",
        "permission": "manage_messages"
    },
    {
        "name": "/userhistory",
        "description": "View a user's moderation history",
        "usage": "/userhistory @user",
        "category": "moderation",
        "permission": "manage_messages"
    },
    {
        "name": "/modactivity",
        "description": "View a moderator's action history",
        "usage": "/modactivity or /modactivity @moderator",
        "category": "moderation",
        "permission": "manage_messages"
    },

    # Admin Commands (Require administrator)
    {
        "name": "/adminprofile",
        "description": "View detailed member profile with warnings and server stats (3 pages)",
        "usage": "/adminprofile @user",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/webhook",
        "description": "Create and send webhook messages with embeds",
        "usage": "/webhook",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/webhookedit",
        "description": "Edit an existing webhook message",
        "usage": "/webhookedit <message_link>",
        "category": "admin",
        "permission": "administrator"
    },

    # Owner Commands (Server Owner only)
    {
        "name": "/clearlogs",
        "description": "Clear all moderation logs (Server Owner only)",
        "usage": "/clearlogs",
        "category": "owner",
        "permission": "administrator"  # We check for owner in the command itself
    },
]

# Category display info
CATEGORY_INFO = {
    "general": {
        "name": "General Commands",
        "emoji": "📌",
        "description": "Basic commands everyone can use"
    },
    "fun": {
        "name": "Fun Commands",
        "emoji": "🎮",
        "description": "Entertainment and fun features"
    },
    "music": {
        "name": "Music Commands",
        "emoji": "🎵",
        "description": "Play music from Spotify in voice channels"
    },
    "moderation": {
        "name": "Moderation Commands",
        "emoji": "🛡️",
        "description": "Tools for server moderators"
    },
    "admin": {
        "name": "Admin Commands",
        "emoji": "👑",
        "description": "Powerful tools for administrators"
    },
    "owner": {
        "name": "Owner Commands",
        "emoji": "🔐",
        "description": "Exclusive commands for the server owner"
    }
}


def user_has_permission(user: discord.Member, permission: str) -> bool:
    """Check if a user has a specific permission"""
    if permission is None:
        return True
    return getattr(user.guild_permissions, permission, False)


def get_user_commands(user: discord.Member) -> Dict[str, List[Dict]]:
    """Get all commands the user has access to, organized by category"""
    accessible = {}

    for cmd in COMMANDS_REGISTRY:
        if user_has_permission(user, cmd["permission"]):
            category = cmd["category"]
            if category not in accessible:
                accessible[category] = []
            accessible[category].append(cmd)

    return accessible


class InformationView(View):
    """View with buttons to navigate between information pages"""

    def __init__(self, bot: commands.Bot, user: discord.Member, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user = user
        self.current_page = 1
        self.accessible_commands = get_user_commands(user)

        # Calculate total pages based on accessible categories
        # Page 1: About, Page 2: Features, then one page per category with commands
        self.categories_with_commands = [
            cat for cat in ["general", "fun", "music", "moderation", "admin", "owner"]
            if cat in self.accessible_commands
        ]
        self.total_pages = 2 + len(self.categories_with_commands)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to use the buttons"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "Only the person who ran the command can use these buttons!",
                ephemeral=True
            )
            return False
        return True

    def get_page_embed(self) -> discord.Embed:
        """Get the embed for the current page"""
        if self.current_page == 1:
            return self._build_about_embed()
        elif self.current_page == 2:
            return self._build_features_embed()
        else:
            # Pages 3+ are command categories
            category_index = self.current_page - 3
            if 0 <= category_index < len(self.categories_with_commands):
                category = self.categories_with_commands[category_index]
                return self._build_category_embed(category)
            return self._build_about_embed()

    def _build_about_embed(self) -> discord.Embed:
        """Build the about/introduction embed (Page 1)"""
        embed = discord.Embed(
            title=f"📖 About {config.BOT_NAME}",
            description=f"**Page 1/{self.total_pages}** - Introduction",
            color=discord.Color.blue()
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Bot introduction
        embed.add_field(
            name="🤖 What is Gojo?",
            value=(
                f"**{config.BOT_NAME}** is a powerful Discord bot designed to help "
                "manage your server with moderation tools, fun commands, and useful utilities.\n\n"
                "Named after the strongest sorcerer from Jujutsu Kaisen, this bot aims to be "
                "the strongest helper in your server!"
            ),
            inline=False
        )

        # Quick stats
        total_commands = len(COMMANDS_REGISTRY)
        user_accessible = sum(len(cmds) for cmds in self.accessible_commands.values())

        embed.add_field(
            name="📊 Quick Stats",
            value=(
                f"**Bot Version:** {config.BOT_VERSION}\n"
                f"**Total Commands:** {total_commands}\n"
                f"**Your Accessible Commands:** {user_accessible}\n"
                f"**Servers:** {len(self.bot.guilds)}"
            ),
            inline=True
        )

        # Your access level
        perms = self.user.guild_permissions
        if perms.administrator:
            access_level = "👑 Administrator"
            access_desc = "You have full access to all commands!"
        elif perms.manage_messages or perms.moderate_members:
            access_level = "🛡️ Moderator"
            access_desc = "You have access to moderation commands"
        else:
            access_level = "👤 Member"
            access_desc = "You have access to general commands"

        embed.add_field(
            name="🔑 Your Access Level",
            value=f"**{access_level}**\n{access_desc}",
            inline=True
        )

        embed.add_field(
            name="📚 Navigation",
            value=(
                "Use the **Previous** and **Next** buttons below to browse:\n"
                "• **Page 2:** Features Overview\n"
                "• **Page 3+:** Command Categories"
            ),
            inline=False
        )

        embed.set_footer(text=f"Requested by {self.user} • Use buttons to navigate")

        return embed

    def _build_features_embed(self) -> discord.Embed:
        """Build the features overview embed (Page 2)"""
        embed = discord.Embed(
            title=f"✨ {config.BOT_NAME} Features",
            description=f"**Page 2/{self.total_pages}** - Features Overview",
            color=discord.Color.gold()
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Moderation Features
        embed.add_field(
            name="🛡️ Moderation System",
            value=(
                "• **Timeout System** - Temporarily mute disruptive users\n"
                "• **Warning System** - Track user warnings with severity levels\n"
                "• **Moderation Logs** - Track all mod actions with filters\n"
                "• **Mod Activity** - View what actions moderators have taken\n"
                "• **ModTalk** - Send messages as the bot\n"
                "• **Admin Profiles** - Detailed member stats and permissions"
            ),
            inline=False
        )

        # Fun Features
        embed.add_field(
            name="🎮 Fun & Entertainment",
            value=(
                "• **Daily Quotes** - Inspirational quotes from movies, anime & famous people\n"
                "• More fun features coming soon!"
            ),
            inline=False
        )

        # Music Features
        embed.add_field(
            name="🎵 Music System",
            value=(
                "• **Spotify Integration** - Play songs from Spotify links\n"
                "• **Search & Play** - Search for any song by name\n"
                "• **Queue System** - Queue up multiple songs\n"
                "• **Playback Controls** - Pause, resume, skip, stop\n"
                "• **Volume Control** - Adjust volume as needed"
            ),
            inline=False
        )

        # Utility Features
        embed.add_field(
            name="🔧 Utilities",
            value=(
                "• **Webhook Manager** - Create and edit webhook messages with embeds\n"
                "• **Server Stats** - Track member join positions and activity\n"
                "• **Permission Viewer** - See what permissions users have\n"
                "• **Role Information** - View role details and hierarchies"
            ),
            inline=False
        )

        # Coming Soon
        embed.add_field(
            name="🚀 Coming Soon",
            value=(
                "• AI Chat Features (OpenRouter integration)\n"
                "• Auto-moderation\n"
                "• Custom welcome messages\n"
                "• And more!"
            ),
            inline=False
        )

        embed.set_footer(text=f"Requested by {self.user} • Use buttons to navigate")

        return embed

    def _build_category_embed(self, category: str) -> discord.Embed:
        """Build a command category embed"""
        cat_info = CATEGORY_INFO.get(category, {
            "name": category.title(),
            "emoji": "📁",
            "description": "Commands"
        })

        commands_list = self.accessible_commands.get(category, [])

        embed = discord.Embed(
            title=f"{cat_info['emoji']} {cat_info['name']}",
            description=f"**Page {self.current_page}/{self.total_pages}** - {cat_info['description']}",
            color=self._get_category_color(category)
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # List commands in this category
        for cmd in commands_list:
            # Add permission indicator
            if cmd["permission"]:
                perm_text = f"\n🔒 *Requires: {cmd['permission'].replace('_', ' ').title()}*"
            else:
                perm_text = ""

            embed.add_field(
                name=f"**{cmd['name']}**",
                value=f"{cmd['description']}\n📝 `{cmd['usage']}`{perm_text}",
                inline=False
            )

        # Show command count
        embed.set_footer(
            text=f"{len(commands_list)} command(s) • Requested by {self.user} • Use buttons to navigate"
        )

        return embed

    def _get_category_color(self, category: str) -> discord.Color:
        """Get the color for a category"""
        colors = {
            "general": discord.Color.blue(),
            "fun": discord.Color.gold(),
            "music": discord.Color.green(),
            "moderation": discord.Color.orange(),
            "admin": discord.Color.red(),
            "owner": discord.Color.dark_red()
        }
        return colors.get(category, discord.Color.blurple())

    def update_buttons(self):
        """Update button states based on current page"""
        self.clear_items()

        # Previous button
        prev_btn = Button(
            label="◀️ Previous",
            style=discord.ButtonStyle.secondary,
            custom_id="prev_page",
            disabled=(self.current_page == 1)
        )
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)

        # Page indicator
        page_btn = Button(
            label=f"Page {self.current_page}/{self.total_pages}",
            style=discord.ButtonStyle.primary,
            disabled=True
        )
        self.add_item(page_btn)

        # Next button
        next_btn = Button(
            label="Next ▶️",
            style=discord.ButtonStyle.secondary,
            custom_id="next_page",
            disabled=(self.current_page == self.total_pages)
        )
        next_btn.callback = self.next_page
        self.add_item(next_btn)

    async def prev_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if self.current_page > 1:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    async def on_timeout(self):
        """Disable all buttons when the view times out"""
        for item in self.children:
            item.disabled = True


class Information(commands.Cog):
    """Cog for the information command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="information", description="Learn about the bot and see available commands")
    async def information(self, interaction: discord.Interaction):
        """
        Slash command that displays bot information and available commands
        Usage: /information
        Shows only commands the user has permission to use
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="information",
            guild=guild_name
        )

        # Check if in a server (needed for permission checking)
        if not interaction.guild:
            await interaction.response.send_message(
                "This command works best in a server! Some features may be limited in DMs.",
                ephemeral=True
            )
            return

        try:
            # Create the paginated view
            view = InformationView(self.bot, interaction.user)
            view.update_buttons()

            # Send the first page
            embed = view.get_page_embed()
            await interaction.response.send_message(embed=embed, view=view)

            logger.info(f"Information command used by {interaction.user}")

        except Exception as e:
            logger.error(f"Failed to show information: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong while loading information.",
                ephemeral=True
            )


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the Information cog to the bot"""
    await bot.add_cog(Information(bot))
