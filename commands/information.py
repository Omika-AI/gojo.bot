"""
/information Command
Displays bot information, features, and available commands
Shows only commands the user has permission to use

IMPORTANT: Update this file when adding new commands!
Last updated: 2026-01-08
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
    {
        "name": "/67",
        "description": "Unleash maximum cringe upon the server",
        "usage": "/67",
        "category": "fun",
        "permission": None
    },

    # Economy Commands (Everyone can use)
    {
        "name": "/balance",
        "description": "Check your coin balance and gambling stats",
        "usage": "/balance or /balance @user",
        "category": "economy",
        "permission": None
    },
    {
        "name": "/claimdaily",
        "description": "Claim daily coins (streak bonus increases rewards)",
        "usage": "/claimdaily",
        "category": "economy",
        "permission": None
    },
    {
        "name": "/leaderboard",
        "description": "View the top 10 richest users",
        "usage": "/leaderboard",
        "category": "economy",
        "permission": None
    },

    # Gambling Commands (Everyone can use)
    {
        "name": "/blackjack",
        "description": "Play blackjack against the dealer (1x-1.5x payout)",
        "usage": "/blackjack bet:100",
        "category": "gambling",
        "permission": None
    },
    {
        "name": "/roulette",
        "description": "Bet on red/black, odd/even, or ranges (2x-3x payout)",
        "usage": "/roulette bet:100 bet_type:red",
        "category": "gambling",
        "permission": None
    },
    {
        "name": "/roulettenumber",
        "description": "Bet on one or more numbers (36x for 1, 18x for 2, etc.)",
        "usage": "/roulettenumber bet:100 numbers:7 OR numbers:7, 17, 23 OR numbers:1-6",
        "category": "gambling",
        "permission": None
    },
    {
        "name": "/roulettetable",
        "description": "View the roulette betting table with all numbers and payouts",
        "usage": "/roulettetable",
        "category": "gambling",
        "permission": None
    },
    {
        "name": "/coinflip",
        "description": "Challenge someone to a coinflip duel for coins",
        "usage": "/coinflip opponent:@user bet:100",
        "category": "gambling",
        "permission": None
    },
    {
        "name": "/guessnumber",
        "description": "Guess 1-50 for 500x payout! (2% chance)",
        "usage": "/guessnumber bet:50 guess:25",
        "category": "gambling",
        "permission": None
    },

    # Music Commands (Everyone can use)
    {
        "name": "/play",
        "description": "Play a song immediately (or next if something is playing)",
        "usage": "/play query:song name OR /play query:<soundcloud link>",
        "category": "music",
        "permission": None
    },
    {
        "name": "/addsong",
        "description": "Add a song to the queue",
        "usage": "/addsong query:song name OR /addsong query:<soundcloud link>",
        "category": "music",
        "permission": None
    },
    {
        "name": "/playlist",
        "description": "Play a SoundCloud playlist or album",
        "usage": "/playlist url:<soundcloud playlist/album link>",
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
        "description": "View the music queue with remove buttons",
        "usage": "/queue",
        "category": "music",
        "permission": None
    },
    {
        "name": "/nowplaying",
        "description": "Show current song with Lyrics button (Genius integration)",
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
        "name": "/clearqueue",
        "description": "Clear all songs from the queue (Mods only)",
        "usage": "/clearqueue",
        "category": "music",
        "permission": "manage_messages"
    },
    {
        "name": "/audiostatus",
        "description": "Check current audio optimization settings for your server",
        "usage": "/audiostatus",
        "category": "music",
        "permission": None
    },
    {
        "name": "/karaokelist",
        "description": "View all available karaoke songs",
        "usage": "/karaokelist",
        "category": "karaoke",
        "permission": None
    },
    {
        "name": "/karaokesolo",
        "description": "Start a solo karaoke performance with spotlight and countdown",
        "usage": "/karaokesolo singer:@user",
        "category": "karaoke",
        "permission": None
    },
    {
        "name": "/karaokeduet",
        "description": "Start a duet with two singers taking alternating lines",
        "usage": "/karaokeduet singer1:@user1 singer2:@user2",
        "category": "karaoke",
        "permission": None
    },
    {
        "name": "/karaoke",
        "description": "Shows karaoke mode options (redirects to solo/duet)",
        "usage": "/karaoke",
        "category": "karaoke",
        "permission": None
    },

    # Achievement Commands (Everyone can use)
    {
        "name": "/achievements",
        "description": "View your unlocked achievements and progress",
        "usage": "/achievements or /achievements @user",
        "category": "achievements",
        "permission": None
    },
    {
        "name": "/achievementstats",
        "description": "View detailed progress toward all achievements with progress bars",
        "usage": "/achievementstats or /achievementstats user:@someone",
        "category": "achievements",
        "permission": None
    },

    # Leveling Commands (Everyone can use)
    {
        "name": "/rank",
        "description": "View your level and XP with a beautiful graphical rank card",
        "usage": "/rank or /rank @user",
        "category": "leveling",
        "permission": None
    },
    {
        "name": "/xpleaderboard",
        "description": "View the server's XP leaderboard sorted by total XP",
        "usage": "/xpleaderboard or /xpleaderboard page:2",
        "category": "leveling",
        "permission": None
    },
    {
        "name": "/levels",
        "description": "View XP requirements for each level and milestone rewards",
        "usage": "/levels",
        "category": "leveling",
        "permission": None
    },

    # Reputation Commands (Everyone can use)
    {
        "name": "/rep",
        "description": "Give a reputation point to a helpful member (1 per day)",
        "usage": "/rep @user",
        "category": "reputation",
        "permission": None
    },
    {
        "name": "/repcheck",
        "description": "Check reputation points for yourself or another user",
        "usage": "/repcheck or /repcheck @user",
        "category": "reputation",
        "permission": None
    },
    {
        "name": "/repleaderboard",
        "description": "View the most reputable members in the server",
        "usage": "/repleaderboard or /repleaderboard page:2",
        "category": "reputation",
        "permission": None
    },

    # Shop Commands (Everyone can use)
    {
        "name": "/shop",
        "description": "Browse the server shop for XP boosters, custom roles, and more",
        "usage": "/shop",
        "category": "shop",
        "permission": None
    },
    {
        "name": "/buy",
        "description": "Purchase an item from the shop",
        "usage": "/buy item:xp_boost_2h",
        "category": "shop",
        "permission": None
    },
    {
        "name": "/inventory",
        "description": "View your active shop items and purchases",
        "usage": "/inventory",
        "category": "shop",
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
    {
        "name": "/givecoins",
        "description": "Give coins to a user (preset amounts or custom)",
        "usage": "/givecoins @user",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/ultraoptimizemusic",
        "description": "Toggle ultra audio quality mode for maximum music quality",
        "usage": "/ultraoptimizemusic or /ultraoptimizemusic enable:True",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/backfill",
        "description": "Sync all historical data: messages, gambling wins, balance, and daily streaks to achievements",
        "usage": "/backfill or /backfill skip_messages:True (economy only)",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/syncstats",
        "description": "Sync economy data (gambling, balance, streaks) to achievement stats",
        "usage": "/syncstats or /syncstats user:@someone",
        "category": "admin",
        "permission": "administrator"
    },

    # Live Alerts Commands (Require administrator)
    {
        "name": "/livealerts setup",
        "description": "Set up the channel for live stream alerts",
        "usage": "/livealerts setup channel:#alerts",
        "category": "livealerts",
        "permission": "administrator"
    },
    {
        "name": "/livealerts add",
        "description": "Add a Twitch or YouTube streamer to track",
        "usage": "/livealerts add platform:twitch username:ninja",
        "category": "livealerts",
        "permission": "administrator"
    },
    {
        "name": "/livealerts remove",
        "description": "Remove a streamer from tracking",
        "usage": "/livealerts remove platform:twitch username:ninja",
        "category": "livealerts",
        "permission": "administrator"
    },
    {
        "name": "/livealerts list",
        "description": "List all tracked streamers and configuration",
        "usage": "/livealerts list",
        "category": "livealerts",
        "permission": None
    },
    {
        "name": "/livealerts role",
        "description": "Set a role to ping when someone goes live",
        "usage": "/livealerts role @StreamNotify",
        "category": "livealerts",
        "permission": "administrator"
    },

    # Auto News Commands (Require administrator)
    {
        "name": "/autonews setup",
        "description": "Set up the channel for automated news posts",
        "usage": "/autonews setup channel:#community-feed",
        "category": "autonews",
        "permission": "administrator"
    },
    {
        "name": "/autonews reddit",
        "description": "Add a subreddit to auto-post from",
        "usage": "/autonews reddit subreddit:gaming filter_type:hot",
        "category": "autonews",
        "permission": "administrator"
    },
    {
        "name": "/autonews rss",
        "description": "Add an RSS feed to auto-post from",
        "usage": "/autonews rss url:https://example.com/feed.xml",
        "category": "autonews",
        "permission": "administrator"
    },
    {
        "name": "/autonews remove",
        "description": "Remove a feed from tracking",
        "usage": "/autonews remove feed_type:reddit identifier:gaming",
        "category": "autonews",
        "permission": "administrator"
    },
    {
        "name": "/autonews list",
        "description": "List all configured news feeds",
        "usage": "/autonews list",
        "category": "autonews",
        "permission": None
    },

    # Support/Ticket Commands (Require administrator)
    {
        "name": "/ticket setup",
        "description": "Set up the ticket system with staff role and log channel",
        "usage": "/ticket setup staff_role:@Staff log_channel:#ticket-logs category:Tickets",
        "category": "support",
        "permission": "administrator"
    },
    {
        "name": "/ticket panel",
        "description": "Send a new ticket panel embed with Open Ticket button",
        "usage": "/ticket panel",
        "category": "support",
        "permission": "administrator"
    },
    {
        "name": "/ticket add",
        "description": "Add a user to the current ticket channel",
        "usage": "/ticket add user:@someone",
        "category": "support",
        "permission": None  # Staff or ticket owner can use
    },
    {
        "name": "/ticket remove",
        "description": "Remove a user from the current ticket channel",
        "usage": "/ticket remove user:@someone",
        "category": "support",
        "permission": "manage_messages"  # Staff only
    },

    # Owner Commands (Server Owner only)
    {
        "name": "/clearlogs",
        "description": "Clear all moderation logs (Server Owner only)",
        "usage": "/clearlogs",
        "category": "owner",
        "permission": "administrator"  # We check for owner in the command itself
    },
    {
        "name": "/setuplogs",
        "description": "Set up event logging channel (Server Owner only)",
        "usage": "/setuplogs #log-channel",
        "category": "owner",
        "permission": "administrator"
    },
    {
        "name": "/editlogs",
        "description": "Change the event logging channel (Server Owner only)",
        "usage": "/editlogs #new-log-channel",
        "category": "owner",
        "permission": "administrator"
    },
    {
        "name": "/searchlogs",
        "description": "Search event logs with text, user, or category filters (Server Owner only)",
        "usage": "/searchlogs search_text:badword OR /searchlogs user:@someone category:messages",
        "category": "owner",
        "permission": "administrator"
    },
    {
        "name": "/logstats",
        "description": "View event logging statistics (Server Owner only)",
        "usage": "/logstats",
        "category": "owner",
        "permission": "administrator"
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
    "economy": {
        "name": "Economy Commands",
        "emoji": "💰",
        "description": "Virtual currency and daily rewards"
    },
    "gambling": {
        "name": "Gambling Commands",
        "emoji": "🎰",
        "description": "Casino games with virtual coins"
    },
    "music": {
        "name": "Music Commands",
        "emoji": "🔊",
        "description": "Play music from SoundCloud in voice channels"
    },
    "karaoke": {
        "name": "Karaoke Commands",
        "emoji": "🎤",
        "description": "Sing along with synced lyrics and spotlight features"
    },
    "achievements": {
        "name": "Achievement Commands",
        "emoji": "🏆",
        "description": "Track progress and unlock achievements"
    },
    "leveling": {
        "name": "Leveling Commands",
        "emoji": "📊",
        "description": "XP, levels, and rank cards"
    },
    "reputation": {
        "name": "Reputation Commands",
        "emoji": "⭐",
        "description": "Social recognition for helpful members"
    },
    "shop": {
        "name": "Shop Commands",
        "emoji": "🛒",
        "description": "Spend coins on XP boosters and custom roles"
    },
    "moderation": {
        "name": "Moderation Commands",
        "emoji": "🛡️",
        "description": "Tools for server moderators"
    },
    "support": {
        "name": "Support Ticket Commands",
        "emoji": "🎫",
        "description": "Ticket system for user support"
    },
    "admin": {
        "name": "Admin Commands",
        "emoji": "👑",
        "description": "Powerful tools for administrators"
    },
    "livealerts": {
        "name": "Live Alert Commands",
        "emoji": "📺",
        "description": "Stream notifications for Twitch and YouTube"
    },
    "autonews": {
        "name": "Auto News Commands",
        "emoji": "📰",
        "description": "Automated news from Reddit and RSS feeds"
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
        # Page 1: About, Page 2: Features, then one page per category, then Credits
        self.categories_with_commands = [
            cat for cat in ["general", "fun", "economy", "gambling", "music", "karaoke", "achievements", "leveling", "reputation", "shop", "moderation", "support", "admin", "livealerts", "autonews", "owner"]
            if cat in self.accessible_commands
        ]
        # +3 for About, Features, and Credits pages
        self.total_pages = 3 + len(self.categories_with_commands)

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
        elif self.current_page == self.total_pages:
            # Last page is Credits
            return self._build_credits_embed()
        else:
            # Pages 3 to (total-1) are command categories
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
                "• **Page 3+:** Command Categories\n"
                f"• **Page {self.total_pages}:** Credits"
            ),
            inline=False
        )

        embed.set_footer(text=f"Requested by {self.user} • Use buttons to navigate")

        return embed

    def _build_features_embed(self) -> discord.Embed:
        """Build the features overview embed (Page 2) - Shows only public features"""
        embed = discord.Embed(
            title=f"✨ {config.BOT_NAME} Features",
            description=f"**Page 2/{self.total_pages}** - Features Overview",
            color=discord.Color.gold()
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Music Features (Everyone)
        embed.add_field(
            name="🔊 Music System",
            value=(
                "• **SoundCloud Integration** - Search and play from SoundCloud\n"
                "• **Search & Play** - Search for any song by name\n"
                "• **Direct Links** - Paste SoundCloud URLs directly\n"
                "• **Queue System** - Queue up multiple songs with remove buttons\n"
                "• **Playback Controls** - Pause, resume, skip, shuffle\n"
                "• **Volume Control** - Adjust volume as needed\n"
                "• **Lyrics** - View song lyrics via Genius integration\n"
                "• **Audio Optimization** - Smooth playback with Opus codec support"
            ),
            inline=False
        )

        # Karaoke Features (Everyone)
        embed.add_field(
            name="🎤 Karaoke System",
            value=(
                "• **Solo Mode** - Spotlight on a single singer with countdown\n"
                "• **Duet Mode** - Two singers with alternating lyric lines\n"
                "• **5-Second Countdown** - Get ready before the music starts\n"
                "• **Singer Spotlight** - Announces who's singing\n"
                "• **Synced Lyrics** - Real-time lyrics display while singing\n"
                "• **Song Library** - Browse available karaoke songs"
            ),
            inline=False
        )

        # Economy System (Everyone)
        embed.add_field(
            name="💰 Economy System",
            value=(
                "• **Virtual Coins** - Earn free coins (not purchasable with real money)\n"
                "• **Daily Claims** - Claim coins daily with streak bonuses\n"
                "• **Leaderboard** - Compete for the top spot\n"
                "• **Balance Tracking** - View your coins and gambling stats"
            ),
            inline=False
        )

        # Gambling System (Everyone)
        embed.add_field(
            name="🎰 Gambling Games",
            value=(
                "• **Blackjack** - Classic card game vs dealer (1x-1.5x payout)\n"
                "• **Roulette** - Bet on colors, numbers, or ranges (2x-36x payout)\n"
                "• **Multi-Number Roulette** - Bet on multiple numbers at once!\n"
                "• **Roulette Table** - View the visual betting table\n"
                "• **Coinflip Duel** - Challenge other players for coins\n"
                "• **Guess the Number** - High risk game with 500x payout!"
            ),
            inline=False
        )

        # Achievement Features (Everyone)
        embed.add_field(
            name="🏆 Achievement System",
            value=(
                "• **10 Unique Achievements** - Unlock achievements as you use the bot\n"
                "• **Progress Tracking** - View your progress toward each achievement\n"
                "• **Chat God** - Send 10,000 messages\n"
                "• **Voice Veteran** - Spend 50 hours in voice channels\n"
                "• **High Roller** - Win 50,000 coins from gambling\n"
                "• **Wealthy Elite** - Have 100,000 coins at once\n"
                "• **And More!** - Music, karaoke, daily streaks achievements"
            ),
            inline=False
        )

        # Leveling System (Everyone)
        embed.add_field(
            name="📊 Leveling System",
            value=(
                "• **Earn XP** - Get XP for messages (15-25 XP) and voice chat (10 XP/min)\n"
                "• **Level Up** - Progress through levels with increasing XP requirements\n"
                "• **Rank Cards** - Beautiful graphical rank cards with your avatar & stats\n"
                "• **XP Leaderboard** - Compete for the top spot in your server\n"
                "• **Milestone Rewards** - Earn bonus coins at levels 5, 10, 20, 50, 100!\n"
                "• **Level 10: 5,000 coins** - Plus other milestone bonuses"
            ),
            inline=False
        )

        # Reputation System (Everyone)
        embed.add_field(
            name="⭐ Reputation System",
            value=(
                "• **Give Rep** - Recognize helpful members with `/rep @user`\n"
                "• **Daily Limit** - One rep point per day to prevent spam\n"
                "• **Rep Leaderboard** - See who the most helpful members are\n"
                "• **Check Rep** - View anyone's reputation stats\n"
                "• **Social Recognition** - Build your server's community lore"
            ),
            inline=False
        )

        # Shop System (Everyone)
        embed.add_field(
            name="🛒 Server Shop",
            value=(
                "• **XP Boosters** - Double XP for 2h, 6h, or 24h\n"
                "• **Custom Roles** - Buy a custom colored role for 1 week or 1 month\n"
                "• **Browse & Buy** - Use `/shop` to see items, `/buy` to purchase\n"
                "• **Inventory** - Track your active items with `/inventory`\n"
                "• **Auto-Expiry** - Temporary items are automatically removed when expired"
            ),
            inline=False
        )

        # Fun Features (Everyone)
        embed.add_field(
            name="🎮 Fun & Entertainment",
            value=(
                "• **Daily Quotes** - Inspirational quotes from movies, anime & famous people\n"
                "• More fun features coming soon!"
            ),
            inline=False
        )

        # Staff-only features below
        perms = self.user.guild_permissions
        is_staff = perms.manage_messages or perms.moderate_members or perms.administrator

        # Ticket System (Staff)
        if is_staff:
            embed.add_field(
                name="🎫 Support Ticket System",
                value=(
                    "• **Button-Based Tickets** - Users click to open private support channels\n"
                    "• **Category Selection** - Support, Report, Appeal, or Other\n"
                    "• **Claim System** - Staff can claim tickets to handle them\n"
                    "• **Lock/Unlock** - Temporarily prevent user from typing\n"
                    "• **Transcripts** - Save ticket conversations to log channel\n"
                    "• **Safe Close** - Close with reopen option, delete confirmation"
                ),
                inline=False
            )

            embed.add_field(
                name="📺 Live Stream Alerts",
                value=(
                    "• **Twitch & YouTube** - Get alerts when streamers go live\n"
                    "• **Auto-Detection** - Bot checks every 5 minutes for new streams\n"
                    "• **Custom Channel** - Set which channel receives alerts\n"
                    "• **Role Pings** - Optionally ping a role when someone goes live\n"
                    "• **Rich Embeds** - Beautiful alerts with streamer info and links"
                ),
                inline=False
            )

            embed.add_field(
                name="📰 Auto News Feeds",
                value=(
                    "• **Reddit Integration** - Auto-post from any subreddit\n"
                    "• **RSS Support** - Subscribe to any RSS feed\n"
                    "• **Filter Options** - Choose hot, new, or top posts\n"
                    "• **Automatic Posts** - Bot fetches new content every 10 minutes\n"
                    "• **Rich Formatting** - Posts include titles, links, and thumbnails"
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

        # Note about more features for staff
        if is_staff:
            embed.add_field(
                name="🔒 Staff Features",
                value="*You have access to additional commands. Browse the category pages to see moderation, admin, and owner tools.*",
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
            "economy": discord.Color.from_rgb(255, 215, 0),  # Gold
            "gambling": discord.Color.purple(),
            "music": discord.Color.green(),
            "karaoke": discord.Color.magenta(),
            "achievements": discord.Color.from_rgb(255, 165, 0),  # Orange/Gold
            "leveling": discord.Color.from_rgb(88, 101, 242),  # Discord Blurple
            "reputation": discord.Color.gold(),  # Gold for reputation
            "shop": discord.Color.teal(),  # Teal for shop
            "moderation": discord.Color.orange(),
            "admin": discord.Color.red(),
            "livealerts": discord.Color.purple(),  # Purple for live alerts (Twitch)
            "autonews": discord.Color.from_rgb(255, 69, 0),  # Reddit orange
            "owner": discord.Color.dark_red()
        }
        return colors.get(category, discord.Color.blurple())

    def _build_credits_embed(self) -> discord.Embed:
        """Build the credits embed (Last Page)"""
        embed = discord.Embed(
            title="Credits",
            description=f"**Page {self.total_pages}/{self.total_pages}** - The Team Behind {config.BOT_NAME}",
            color=discord.Color.purple()
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Developer
        embed.add_field(
            name="Developer",
            value=(
                "**Fengus**\n"
                "Lead developer responsible for building and maintaining "
                f"all of {config.BOT_NAME}'s features and functionality."
            ),
            inline=False
        )

        # Owner/Overseer
        embed.add_field(
            name="Owner & Overseer",
            value=(
                "**Frederik \"NaCly\"**\n"
                "Owner of **Omika AI** and project overseer.\n"
                f"{config.BOT_NAME} is developed under the Omika AI umbrella."
            ),
            inline=False
        )

        # Project Info
        embed.add_field(
            name="About the Project",
            value=(
                f"**{config.BOT_NAME}** is a project developed under **Omika AI**.\n\n"
                "Named after the strongest sorcerer from Jujutsu Kaisen, "
                "this bot aims to provide powerful moderation, logging, "
                "and entertainment features for Discord servers."
            ),
            inline=False
        )

        # Special Thanks
        embed.add_field(
            name="Special Thanks",
            value=(
                "Thank you to everyone who uses and supports this bot!\n"
                "Your feedback helps make it better every day."
            ),
            inline=False
        )

        embed.set_footer(text=f"Requested by {self.user} • {config.BOT_NAME} v{config.BOT_VERSION}")

        return embed

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
