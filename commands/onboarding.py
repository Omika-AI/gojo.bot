"""
Onboarding & Dashboard Commands

Commands:
- /setup - Interactive setup wizard for server admins
- /start - Getting started guide for new users
- /dashboard - Quick overview of bot features and server setup

Features:
- Step-by-step server configuration
- Interactive buttons for easy navigation
- Welcome embed when bot joins a server
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
from typing import Optional

import config
from utils.logger import logger


# ============================================
# SETUP WIZARD VIEWS
# ============================================

class SetupCategorySelect(Select):
    """Select menu for choosing what to set up"""

    def __init__(self):
        options = [
            discord.SelectOption(
                label="Moderation Logs",
                value="logs",
                description="Set up a channel for moderation logs",
                emoji="📋"
            ),
            discord.SelectOption(
                label="Live Alerts",
                value="live",
                description="Set up Twitch/YouTube live notifications",
                emoji="📺"
            ),
            discord.SelectOption(
                label="Auto News",
                value="news",
                description="Set up Reddit/RSS news feeds",
                emoji="📰"
            ),
            discord.SelectOption(
                label="Support Tickets",
                value="tickets",
                description="Set up a ticket support system",
                emoji="🎫"
            ),
            discord.SelectOption(
                label="Temp Voice Channels",
                value="tempvc",
                description="Set up Join-to-Create voice channels",
                emoji="🔊"
            ),
            discord.SelectOption(
                label="Economy Settings",
                value="economy",
                description="Configure economy and shop settings",
                emoji="💰"
            ),
            discord.SelectOption(
                label="Leveling System",
                value="leveling",
                description="Configure XP and leveling",
                emoji="📊"
            ),
        ]

        super().__init__(
            placeholder="Choose what to set up...",
            options=options,
            custom_id="setup_category_select"
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]

        if category == "logs":
            embed = discord.Embed(
                title="Moderation Logs Setup",
                description=(
                    "To set up moderation logs, use:\n\n"
                    "**`/setuplogs #channel`**\n\n"
                    "This will log all moderation actions like:\n"
                    "• Timeouts and warnings\n"
                    "• Bans and kicks\n"
                    "• Message deletions\n"
                    "• User reports"
                ),
                color=discord.Color.blue()
            )

        elif category == "live":
            embed = discord.Embed(
                title="Live Alerts Setup",
                description=(
                    "To set up live streaming alerts:\n\n"
                    "**1. Set the alerts channel:**\n"
                    "`/livealerts setup #channel`\n\n"
                    "**2. Add streamers to track:**\n"
                    "`/livealerts add twitch username`\n"
                    "`/livealerts add youtube @handle`\n\n"
                    "**3. (Optional) Set a ping role:**\n"
                    "`/livealerts role @StreamAlerts`"
                ),
                color=discord.Color.purple()
            )

        elif category == "news":
            embed = discord.Embed(
                title="Auto News Setup",
                description=(
                    "To set up automatic news feeds:\n\n"
                    "**1. Set the news channel:**\n"
                    "`/autonews setup #channel`\n\n"
                    "**2. Add Reddit feeds:**\n"
                    "`/autonews reddit subreddit [hot/new/top]`\n\n"
                    "**3. Add RSS feeds:**\n"
                    "`/autonews rss [feed URL]`"
                ),
                color=discord.Color.orange()
            )

        elif category == "tickets":
            embed = discord.Embed(
                title="Support Tickets Setup",
                description=(
                    "To set up a ticket support system:\n\n"
                    "**1. Configure ticket settings:**\n"
                    "`/ticket setup #category @support-role`\n\n"
                    "**2. Create a ticket panel:**\n"
                    "`/ticket panel #channel`\n\n"
                    "Users can then click a button to create tickets!"
                ),
                color=discord.Color.green()
            )

        elif category == "tempvc":
            embed = discord.Embed(
                title="Temp Voice Channels Setup",
                description=(
                    "To set up Join-to-Create voice channels:\n\n"
                    "**1. Create a voice channel** (e.g., '➕ Create VC')\n\n"
                    "**2. Create a category** for temp VCs\n\n"
                    "**3. Run the setup command:**\n"
                    "`/tempvc setup #join-channel #category`\n\n"
                    "When users join the channel, they'll get their own private VC!"
                ),
                color=discord.Color.blue()
            )

        elif category == "economy":
            embed = discord.Embed(
                title="Economy Settings",
                description=(
                    "The economy system works automatically!\n\n"
                    "**How users earn coins:**\n"
                    "• `/claimdaily` - Daily rewards\n"
                    "• Level up milestones\n"
                    "• Winning games\n"
                    "• Daily quest rewards\n\n"
                    "**Admin commands:**\n"
                    "`/givecoins @user amount` - Give coins to someone\n\n"
                    "**Shop commands:**\n"
                    "Users can use `/shop` to buy items!"
                ),
                color=discord.Color.gold()
            )

        elif category == "leveling":
            embed = discord.Embed(
                title="Leveling System",
                description=(
                    "The leveling system works automatically!\n\n"
                    "**How users earn XP:**\n"
                    "• Sending messages (with cooldown)\n"
                    "• Time spent in voice channels\n\n"
                    "**User commands:**\n"
                    "`/rank` - Check your level\n"
                    "`/xpleaderboard` - Server rankings\n"
                    "`/levels` - XP requirements\n\n"
                    "**Shop items:**\n"
                    "Users can buy XP boosters from `/shop`!"
                ),
                color=discord.Color.green()
            )

        else:
            embed = discord.Embed(
                title="Setup",
                description="Select an option from the menu.",
                color=discord.Color.blue()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class SetupWizardView(View):
    """Main setup wizard view"""

    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(SetupCategorySelect())

    @discord.ui.button(label="Quick Start Guide", style=discord.ButtonStyle.primary, emoji="📖", row=1)
    async def quick_start(self, interaction: discord.Interaction, button: Button):
        """Show quick start guide"""
        embed = discord.Embed(
            title="Quick Start Guide",
            description="Get your server set up in minutes!",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Step 1: Moderation",
            value="`/setuplogs #mod-logs`\nSet up a channel for mod actions",
            inline=False
        )

        embed.add_field(
            name="Step 2: Tickets (Optional)",
            value="`/ticket setup #tickets @Staff`\n`/ticket panel #support`",
            inline=False
        )

        embed.add_field(
            name="Step 3: Voice Channels (Optional)",
            value="`/tempvc setup #join-vc #temp-vcs`\nSet up Join-to-Create VCs",
            inline=False
        )

        embed.add_field(
            name="That's It!",
            value=(
                "Economy, leveling, and achievements work automatically.\n"
                "Use `/help` to see all available commands!"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Check Server Status", style=discord.ButtonStyle.secondary, emoji="✅", row=1)
    async def check_status(self, interaction: discord.Interaction, button: Button):
        """Check what's currently set up"""
        # Import here to avoid circular imports
        from utils.live_alerts_db import get_alert_channel, get_news_channel, get_all_streamers
        from utils.tempvc_db import get_join_to_create_channel

        guild = interaction.guild
        status_items = []

        # Check moderation logs
        # Would need to add a check for this

        # Check live alerts
        alert_channel = get_alert_channel(guild.id)
        if alert_channel:
            channel = guild.get_channel(alert_channel)
            status_items.append(f"**Live Alerts:** {channel.mention if channel else 'Channel not found'}")
        else:
            status_items.append("**Live Alerts:** Not configured")

        # Check auto news
        news_channel = get_news_channel(guild.id)
        if news_channel:
            channel = guild.get_channel(news_channel)
            status_items.append(f"**Auto News:** {channel.mention if channel else 'Channel not found'}")
        else:
            status_items.append("**Auto News:** Not configured")

        # Check temp VCs
        jtc_channel = get_join_to_create_channel(guild.id)
        if jtc_channel:
            channel = guild.get_channel(jtc_channel)
            status_items.append(f"**Temp VCs:** {channel.mention if channel else 'Channel not found'}")
        else:
            status_items.append("**Temp VCs:** Not configured")

        # Always active features
        status_items.append("**Economy:** Active (automatic)")
        status_items.append("**Leveling:** Active (automatic)")
        status_items.append("**Achievements:** Active (automatic)")

        embed = discord.Embed(
            title=f"Server Status: {guild.name}",
            description="\n".join(status_items),
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================
# USER GUIDE VIEWS
# ============================================

class UserGuideView(View):
    """View for user getting started guide"""

    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="How to Earn Money", style=discord.ButtonStyle.success, emoji="💰", row=0)
    async def earn_money(self, interaction: discord.Interaction, button: Button):
        """Show how to earn coins"""
        embed = discord.Embed(
            title="How to Earn Coins",
            description="There are many ways to earn coins!",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="Daily Rewards",
            value="`/claimdaily` - Claim free coins every 24 hours!",
            inline=False
        )

        embed.add_field(
            name="Level Up Bonuses",
            value="Reach level milestones (10, 25, 50, etc.) for big rewards!",
            inline=False
        )

        embed.add_field(
            name="Daily Quests",
            value="`/quests` - Complete quests for coins and lootbox keys!",
            inline=False
        )

        embed.add_field(
            name="Gambling (Risky!)",
            value=(
                "`/blackjack` - Play blackjack\n"
                "`/roulette` - Bet on roulette\n"
                "`/coinflip` - 50/50 coin flip"
            ),
            inline=False
        )

        embed.add_field(
            name="Stock Market",
            value="`/invest @user` - Buy shares in active members and sell for profit!",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="How to Use Music", style=discord.ButtonStyle.primary, emoji="🎵", row=0)
    async def use_music(self, interaction: discord.Interaction, button: Button):
        """Show music commands"""
        embed = discord.Embed(
            title="Music Commands",
            description="Play music in voice channels!",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Basic Commands",
            value=(
                "`/play [song]` - Play a song or add to queue\n"
                "`/pause` - Pause playback\n"
                "`/resume` - Resume playback\n"
                "`/skip` - Skip current song\n"
                "`/stop` - Stop and clear queue"
            ),
            inline=False
        )

        embed.add_field(
            name="Queue Management",
            value=(
                "`/queue` - View the current queue\n"
                "`/nowplaying` - See what's playing\n"
                "`/shuffle` - Shuffle the queue"
            ),
            inline=False
        )

        embed.add_field(
            name="Playlists",
            value=(
                "`/playlist create [name]` - Create a playlist\n"
                "`/addsong [playlist] [song]` - Add song to playlist\n"
                "`/playlist play [name]` - Play a playlist"
            ),
            inline=False
        )

        embed.add_field(
            name="Karaoke",
            value="`/karaoke` - Start karaoke mode with lyrics!",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="How to Level Up", style=discord.ButtonStyle.secondary, emoji="📊", row=0)
    async def level_up(self, interaction: discord.Interaction, button: Button):
        """Show leveling info"""
        embed = discord.Embed(
            title="Leveling System",
            description="Earn XP and level up!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Earning XP",
            value=(
                "**Messages:** 15-25 XP per message (60s cooldown)\n"
                "**Voice Chat:** 10 XP per minute\n"
                "**XP Boosters:** Buy from `/shop` for 1.5x or 2x XP!"
            ),
            inline=False
        )

        embed.add_field(
            name="Check Your Progress",
            value=(
                "`/rank` - See your level and XP\n"
                "`/xpleaderboard` - Server rankings\n"
                "`/levels` - XP requirements for each level"
            ),
            inline=False
        )

        embed.add_field(
            name="Level Rewards",
            value=(
                "**Level 10:** 500 coins\n"
                "**Level 25:** 2,000 coins\n"
                "**Level 50:** 5,000 coins\n"
                "**Level 100:** 15,000 coins"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="All Features", style=discord.ButtonStyle.secondary, emoji="📋", row=1)
    async def all_features(self, interaction: discord.Interaction, button: Button):
        """Show all features"""
        embed = discord.Embed(
            title=f"{config.BOT_NAME} Features",
            description="Here's everything I can do!",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Economy",
            value="Daily rewards, coins, gambling, stock market",
            inline=True
        )

        embed.add_field(
            name="Leveling",
            value="XP, levels, rank cards, leaderboards",
            inline=True
        )

        embed.add_field(
            name="Achievements",
            value="50+ achievements to unlock",
            inline=True
        )

        embed.add_field(
            name="Music",
            value="Play songs, playlists, queue management",
            inline=True
        )

        embed.add_field(
            name="Karaoke",
            value="Sing with synced lyrics",
            inline=True
        )

        embed.add_field(
            name="Shop",
            value="XP boosters, custom roles, role colors",
            inline=True
        )

        embed.add_field(
            name="Daily Quests",
            value="Complete quests for rewards",
            inline=True
        )

        embed.add_field(
            name="Stock Market",
            value="Invest in active members",
            inline=True
        )

        embed.add_field(
            name="Reputation",
            value="Give and receive rep points",
            inline=True
        )

        embed.add_field(
            name="Voice Channels",
            value="Create private temp VCs",
            inline=True
        )

        embed.add_field(
            name="VC Signal",
            value="Invite friends to voice",
            inline=True
        )

        embed.add_field(
            name="Moderation",
            value="Timeouts, warnings, logs",
            inline=True
        )

        embed.set_footer(text="Use /help to see all commands!")

        await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================
# WELCOME EMBED VIEW (for when bot joins)
# ============================================

class WelcomeView(View):
    """View shown when bot joins a new server"""

    def __init__(self):
        super().__init__(timeout=None)  # Persistent view

    @discord.ui.button(label="Getting Started", style=discord.ButtonStyle.primary, emoji="🚀", custom_id="welcome_start")
    async def getting_started(self, interaction: discord.Interaction, button: Button):
        """Show getting started guide"""
        embed = discord.Embed(
            title="Getting Started",
            description="Let me help you set things up!",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="For Server Admins",
            value="Use `/setup` to configure the bot for your server!",
            inline=False
        )

        embed.add_field(
            name="For Everyone",
            value="Use `/start` to learn how to use all the features!",
            inline=False
        )

        embed.add_field(
            name="Quick Commands",
            value=(
                "`/help` - See all commands\n"
                "`/information` - Detailed command info\n"
                "`/claimdaily` - Get your daily coins!"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Admin Setup", style=discord.ButtonStyle.success, emoji="⚙️", custom_id="welcome_admin")
    async def admin_setup(self, interaction: discord.Interaction, button: Button):
        """Show admin setup options"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need Administrator permission to access setup!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Admin Quick Setup",
            description="Here's how to set up the main features:",
            color=discord.Color.green()
        )

        embed.add_field(
            name="1. Moderation Logs",
            value="`/setuplogs #mod-logs`",
            inline=False
        )

        embed.add_field(
            name="2. Support Tickets",
            value="`/ticket setup #tickets @Staff`",
            inline=False
        )

        embed.add_field(
            name="3. Temp Voice Channels",
            value="`/tempvc setup #join-vc #category`",
            inline=False
        )

        embed.add_field(
            name="Full Setup Wizard",
            value="Use `/setup` for the complete configuration wizard!",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="All Commands", style=discord.ButtonStyle.secondary, emoji="📜", custom_id="welcome_commands")
    async def all_commands(self, interaction: discord.Interaction, button: Button):
        """Show link to help command"""
        await interaction.response.send_message(
            "Use `/help` to see all available commands, or `/information` for detailed descriptions!",
            ephemeral=True
        )


# ============================================
# MAIN COG
# ============================================

class Onboarding(commands.Cog):
    """Onboarding and setup commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Interactive setup wizard for server administrators")
    @app_commands.default_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        """Open the setup wizard"""

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"{config.BOT_NAME} Setup Wizard",
            description=(
                "Welcome to the setup wizard!\n\n"
                "Select a category below to get started, or click "
                "**Quick Start Guide** for a step-by-step setup."
            ),
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Available Setup Options",
            value=(
                "📋 **Moderation Logs** - Track mod actions\n"
                "📺 **Live Alerts** - Stream notifications\n"
                "📰 **Auto News** - Reddit/RSS feeds\n"
                "🎫 **Support Tickets** - Ticket system\n"
                "🔊 **Temp VCs** - Join-to-Create channels\n"
                "💰 **Economy** - Coins and shop\n"
                "📊 **Leveling** - XP system"
            ),
            inline=False
        )

        embed.set_footer(text=f"{config.BOT_NAME} v{config.BOT_VERSION}")

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        view = SetupWizardView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Setup wizard opened by {interaction.user} in {interaction.guild.name}")

    @app_commands.command(name="start", description="Getting started guide for new users")
    async def start(self, interaction: discord.Interaction):
        """Show the getting started guide"""

        embed = discord.Embed(
            title=f"Welcome to {config.BOT_NAME}!",
            description=(
                "I'm here to make your server experience awesome!\n\n"
                "Click the buttons below to learn about different features."
            ),
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Quick Start",
            value=(
                "`/claimdaily` - Get free coins every day!\n"
                "`/quests` - Complete quests for rewards\n"
                "`/rank` - Check your level\n"
                "`/help` - See all commands"
            ),
            inline=False
        )

        embed.set_footer(text="Click a button below to learn more!")

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        view = UserGuideView()
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"Start guide shown to {interaction.user}")

    @app_commands.command(name="dashboard", description="Quick overview of your server's bot configuration")
    @app_commands.default_permissions(manage_guild=True)
    async def dashboard(self, interaction: discord.Interaction):
        """Show server dashboard"""

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Import here to avoid circular imports
        from utils.live_alerts_db import get_alert_channel, get_news_channel, get_all_streamers, get_all_feeds
        from utils.tempvc_db import get_join_to_create_channel, get_all_temp_vcs

        guild = interaction.guild

        embed = discord.Embed(
            title=f"Dashboard: {guild.name}",
            description="Overview of your server's configuration",
            color=discord.Color.blue()
        )

        # Server stats
        embed.add_field(
            name="Server Stats",
            value=(
                f"**Members:** {guild.member_count}\n"
                f"**Channels:** {len(guild.channels)}\n"
                f"**Roles:** {len(guild.roles)}"
            ),
            inline=True
        )

        # Live alerts
        alert_channel = get_alert_channel(guild.id)
        streamers = get_all_streamers(guild.id)
        embed.add_field(
            name="Live Alerts",
            value=(
                f"**Status:** {'Enabled' if alert_channel else 'Disabled'}\n"
                f"**Tracked:** {len(streamers)} streamer(s)"
            ),
            inline=True
        )

        # Auto news
        news_channel = get_news_channel(guild.id)
        feeds = get_all_feeds(guild.id)
        embed.add_field(
            name="Auto News",
            value=(
                f"**Status:** {'Enabled' if news_channel else 'Disabled'}\n"
                f"**Feeds:** {len(feeds)} feed(s)"
            ),
            inline=True
        )

        # Temp VCs
        jtc_channel = get_join_to_create_channel(guild.id)
        temp_vcs = get_all_temp_vcs(guild.id)
        embed.add_field(
            name="Temp Voice Channels",
            value=(
                f"**Status:** {'Enabled' if jtc_channel else 'Disabled'}\n"
                f"**Active VCs:** {len(temp_vcs)}"
            ),
            inline=True
        )

        # Quick actions
        embed.add_field(
            name="Quick Actions",
            value=(
                "`/setup` - Configure features\n"
                "`/help` - View all commands\n"
                "`/modstats` - Moderation stats"
            ),
            inline=False
        )

        embed.set_footer(text=f"{config.BOT_NAME} v{config.BOT_VERSION}")

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        await interaction.response.send_message(embed=embed)
        logger.info(f"Dashboard viewed by {interaction.user} in {guild.name}")


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Onboarding cog to the bot"""
    await bot.add_cog(Onboarding(bot))

    # Register persistent view for welcome messages
    bot.add_view(WelcomeView())
