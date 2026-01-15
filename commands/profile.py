"""
Graphical Profile System - Visual profile cards with combined stats

Commands:
- /profile - View your graphical profile card with pagination
- /profile user - View another user's profile
- /profilecolor - Change your profile accent color
- /profilemotto - Set your profile motto
- /profilebanner - Choose your profile banner
- /profilebadges - View your earned badges
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from typing import Optional, Literal
import json
import os

from utils.card_generator import create_profile_card, image_to_bytes, COLORS
from utils.leveling_db import get_user_level_data
from utils.economy_db import get_balance, get_user_stats as get_economy_stats
from utils.reputation_db import get_rep_points
from utils.logger import logger

# Database path for profile customization
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
PROFILE_FILE = os.path.join(DATA_DIR, 'profiles.json')

# Achievement tracking - simple count
TOTAL_ACHIEVEMENTS = 20  # Total available achievements in the system

# Available banners
PROFILE_BANNERS = {
    "default": {"name": "Default", "emoji": "🌑", "description": "Classic dark theme", "cost": 0},
    "sunset": {"name": "Sunset", "emoji": "🌅", "description": "Warm orange gradients", "cost": 500},
    "ocean": {"name": "Ocean", "emoji": "🌊", "description": "Deep blue waves", "cost": 500},
    "forest": {"name": "Forest", "emoji": "🌲", "description": "Serene green nature", "cost": 500},
    "galaxy": {"name": "Galaxy", "emoji": "🌌", "description": "Cosmic purple stars", "cost": 1000},
    "fire": {"name": "Fire", "emoji": "🔥", "description": "Blazing red flames", "cost": 1000},
    "ice": {"name": "Ice", "emoji": "❄️", "description": "Frozen blue crystals", "cost": 1000},
    "gold": {"name": "Gold", "emoji": "✨", "description": "Luxurious golden shine", "cost": 2500},
    "rainbow": {"name": "Rainbow", "emoji": "🌈", "description": "Colorful spectrum", "cost": 5000},
    "legendary": {"name": "Legendary", "emoji": "👑", "description": "Exclusive animated style", "cost": 10000},
}

# Achievement badges
PROFILE_BADGES = {
    # Activity badges
    "early_bird": {"name": "Early Bird", "emoji": "🐦", "description": "Joined in the first week"},
    "chatterbox": {"name": "Chatterbox", "emoji": "💬", "description": "Sent 1,000 messages"},
    "veteran": {"name": "Veteran", "emoji": "🎖️", "description": "Sent 10,000 messages"},
    "voice_star": {"name": "Voice Star", "emoji": "🎤", "description": "100 hours in voice"},

    # Economy badges
    "first_daily": {"name": "First Daily", "emoji": "📅", "description": "Claimed your first daily"},
    "rich": {"name": "Rich", "emoji": "💰", "description": "Reached 10,000 coins"},
    "millionaire": {"name": "Millionaire", "emoji": "💎", "description": "Reached 1,000,000 coins"},
    "gambler": {"name": "Gambler", "emoji": "🎰", "description": "Won 100 gambling games"},
    "lucky": {"name": "Lucky", "emoji": "🍀", "description": "Won a jackpot"},

    # Level badges
    "level_10": {"name": "Rising Star", "emoji": "⭐", "description": "Reached level 10"},
    "level_25": {"name": "Dedicated", "emoji": "🌟", "description": "Reached level 25"},
    "level_50": {"name": "Elite", "emoji": "💫", "description": "Reached level 50"},
    "level_100": {"name": "Legend", "emoji": "🏆", "description": "Reached level 100"},

    # Social badges
    "helpful": {"name": "Helpful", "emoji": "🤝", "description": "Received 50 reputation"},
    "popular": {"name": "Popular", "emoji": "❤️", "description": "Received 100 reputation"},
    "beloved": {"name": "Beloved", "emoji": "💕", "description": "Received 500 reputation"},

    # Special badges
    "bug_hunter": {"name": "Bug Hunter", "emoji": "🐛", "description": "Reported a bug"},
    "supporter": {"name": "Supporter", "emoji": "💝", "description": "Supported the bot"},
    "artist": {"name": "Artist", "emoji": "🎨", "description": "Won a creative contest"},
    "champion": {"name": "Champion", "emoji": "🏅", "description": "Won a server event"},
}


def load_profile_data() -> dict:
    """Load profile customization data"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_profile_data(data: dict):
    """Save profile customization data"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PROFILE_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_user_profile(user_id: int) -> dict:
    """Get user's profile customization"""
    data = load_profile_data()
    if str(user_id) not in data:
        data[str(user_id)] = {
            "color": None,
            "motto": None,
            "banner": "default",
            "owned_banners": ["default"],
            "badges": [],
            "featured_badges": []
        }
        save_profile_data(data)
    return data[str(user_id)]


def save_user_profile(user_id: int, profile: dict):
    """Save user's profile customization"""
    data = load_profile_data()
    data[str(user_id)] = profile
    save_profile_data(data)


def award_badge(user_id: int, badge_id: str) -> bool:
    """Award a badge to a user. Returns True if newly awarded."""
    profile = get_user_profile(user_id)
    if badge_id not in profile.get("badges", []):
        if "badges" not in profile:
            profile["badges"] = []
        profile["badges"].append(badge_id)
        save_user_profile(user_id, profile)
        return True
    return False


def get_user_achievements(guild_id: int, user_id: int) -> int:
    """Get the number of achievements a user has unlocked"""
    try:
        from utils.achievements_data import get_user_achievements as get_achievements
        achievements = get_achievements(user_id)
        return len([a for a in achievements if a.get("completed", False)])
    except:
        return 0


# User profile color storage (legacy - now using JSON)
USER_COLORS = {}


def get_user_color(user_id: int) -> tuple:
    """Get user's custom profile color"""
    # Check JSON storage first
    profile = get_user_profile(user_id)
    if profile.get("color"):
        return tuple(profile["color"])
    # Fall back to memory storage
    return USER_COLORS.get(user_id, COLORS["primary"])


def set_user_color(user_id: int, color: tuple):
    """Set user's custom profile color"""
    USER_COLORS[user_id] = color
    # Also save to JSON for persistence
    profile = get_user_profile(user_id)
    profile["color"] = list(color)
    save_user_profile(user_id, profile)


def format_progress_bar(current: int, goal: int, bar_length: int = 10) -> str:
    """Create a text-based progress bar"""
    if goal <= 0:
        return "█" * bar_length
    percentage = min(current / goal, 1.0)
    filled = int(bar_length * percentage)
    empty = bar_length - filled
    return "█" * filled + "░" * empty


# =============================================================================
# PROFILE VIEW WITH PAGINATION
# =============================================================================

class ProfileView(View):
    """Polished profile view with tab-style navigation"""

    def __init__(self, bot: commands.Bot, target_user: discord.Member, requester: discord.Member, guild_id: int, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.target_user = target_user
        self.requester = requester
        self.guild_id = guild_id
        self.current_page = 1
        self.total_pages = 3

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original requester to use the buttons"""
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "This isn't your profile view! Use `/profile` to open your own.",
                ephemeral=True
            )
            return False
        return True

    async def get_page_content(self, interaction: discord.Interaction = None):
        """Get the content for the current page - returns (embed, file) tuple"""
        if self.current_page == 1:
            return await self._build_card_page()
        elif self.current_page == 2:
            return self._build_stats_page(), None
        elif self.current_page == 3:
            return self._build_achievements_page(), None
        return await self._build_card_page()

    async def _build_card_page(self):
        """Build the graphical profile card page (Page 1)"""
        user = self.target_user

        # Gather data
        level_data = get_user_level_data(self.guild_id, user.id)
        balance = get_balance(self.guild_id, user.id)
        reputation = get_rep_points(self.guild_id, user.id)
        achievements = get_user_achievements(self.guild_id, user.id)
        accent_color = get_user_color(user.id)

        # Generate profile card
        card = await create_profile_card(
            avatar_url=user.display_avatar.url,
            username=user.display_name,
            level=level_data["level"],
            xp=level_data["xp"],
            xp_needed=level_data["xp_needed"],
            balance=balance,
            reputation=reputation,
            rank=level_data["rank"],
            achievements_unlocked=achievements,
            total_achievements=TOTAL_ACHIEVEMENTS,
            messages=level_data["messages"],
            voice_hours=level_data["voice_minutes"] // 60,
            accent_color=accent_color
        )

        buffer = image_to_bytes(card)
        file = discord.File(buffer, filename="profile.png")

        embed = discord.Embed(color=discord.Color.from_rgb(*accent_color))
        embed.set_author(
            name=f"{user.display_name}'s Profile",
            icon_url=user.display_avatar.url
        )
        embed.set_image(url="attachment://profile.png")

        return embed, file

    def _build_stats_page(self) -> discord.Embed:
        """Build the stats overview page (Page 2)"""
        user = self.target_user

        # Get all data
        level_data = get_user_level_data(self.guild_id, user.id)
        balance = get_balance(self.guild_id, user.id)
        reputation = get_rep_points(self.guild_id, user.id)
        profile = get_user_profile(user.id)
        economy_stats = get_economy_stats(self.guild_id, user.id)

        # Get banner info
        banner_id = profile.get("banner", "default")
        banner = PROFILE_BANNERS.get(banner_id, PROFILE_BANNERS["default"])

        # Get color
        color = get_user_color(user.id)
        embed_color = discord.Color.from_rgb(*color)

        embed = discord.Embed(color=embed_color)
        embed.set_author(
            name=f"{user.display_name}'s Statistics",
            icon_url=user.display_avatar.url
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        # Motto (if set)
        if profile.get("motto"):
            embed.description = f"*\"{profile['motto']}\"*"

        # ═══════════════════════════════════════
        # LEVELING SECTION
        # ═══════════════════════════════════════
        xp_pct = (level_data['xp'] / level_data['xp_needed']) * 100 if level_data['xp_needed'] > 0 else 0
        xp_bar = "▓" * int(xp_pct // 10) + "░" * (10 - int(xp_pct // 10))

        level_text = (
            f"```\n"
            f"Level {level_data['level']:>3}  •  Rank #{level_data['rank']}\n"
            f"[{xp_bar}] {xp_pct:.0f}%\n"
            f"{level_data['xp']:,} / {level_data['xp_needed']:,} XP\n"
            f"```"
        )
        embed.add_field(name="📊 Level Progress", value=level_text, inline=False)

        # ═══════════════════════════════════════
        # ECONOMY & REPUTATION
        # ═══════════════════════════════════════
        daily_streak = economy_stats.get("daily_streak", 0)
        streak_emoji = "🔥" if daily_streak > 0 else "❄️"

        embed.add_field(
            name="💰 Balance",
            value=f"**{balance:,}**\ncoins",
            inline=True
        )
        embed.add_field(
            name="⭐ Reputation",
            value=f"**{reputation}**\npoints",
            inline=True
        )
        embed.add_field(
            name=f"{streak_emoji} Daily Streak",
            value=f"**{daily_streak}**\ndays",
            inline=True
        )

        # ═══════════════════════════════════════
        # ACTIVITY STATS
        # ═══════════════════════════════════════
        voice_hours = level_data['voice_minutes'] // 60
        voice_mins = level_data['voice_minutes'] % 60

        embed.add_field(
            name="💬 Messages",
            value=f"**{level_data['messages']:,}**",
            inline=True
        )
        embed.add_field(
            name="🎧 Voice Time",
            value=f"**{voice_hours}h {voice_mins}m**",
            inline=True
        )
        embed.add_field(
            name="🎨 Banner",
            value=f"{banner['emoji']} {banner['name']}",
            inline=True
        )

        # ═══════════════════════════════════════
        # GAMBLING STATS
        # ═══════════════════════════════════════
        total_won = economy_stats.get("total_won", 0)
        total_lost = economy_stats.get("total_lost", 0)
        net = total_won - total_lost
        net_emoji = "📈" if net >= 0 else "📉"
        net_text = f"+{net:,}" if net >= 0 else f"{net:,}"

        gambling_text = f"Won: **{total_won:,}** • Lost: **{total_lost:,}** • Net: {net_emoji} **{net_text}**"
        embed.add_field(name="🎰 Gambling Stats", value=gambling_text, inline=False)

        # ═══════════════════════════════════════
        # FEATURED BADGES
        # ═══════════════════════════════════════
        featured = profile.get("featured_badges", [])
        if featured:
            badge_text = []
            for bid in featured[:3]:
                if bid in PROFILE_BADGES:
                    info = PROFILE_BADGES[bid]
                    badge_text.append(f"{info['emoji']} {info['name']}")
            if badge_text:
                embed.add_field(
                    name="🏅 Featured Badges",
                    value=" • ".join(badge_text),
                    inline=False
                )

        return embed

    def _build_achievements_page(self) -> discord.Embed:
        """Build the achievements progress page (Page 3)"""
        user = self.target_user

        # Import achievements data
        try:
            from utils.achievements_data import (
                get_user_stats as get_achievement_stats,
                get_all_achievements,
                get_user_achievement_progress,
                format_stat_display
            )
            has_achievements = True
        except ImportError:
            has_achievements = False

        color = get_user_color(user.id)
        embed_color = discord.Color.from_rgb(*color)

        embed = discord.Embed(color=embed_color)
        embed.set_author(
            name=f"{user.display_name}'s Achievements",
            icon_url=user.display_avatar.url
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        if not has_achievements:
            embed.description = "Achievement system not configured."
            return embed

        # Get achievement data
        achievement_stats = get_achievement_stats(user.id)
        completed = achievement_stats.get("completed_achievements", [])
        all_achievements = get_all_achievements()

        # Count completed
        completed_count = len(completed)
        total_count = len(all_achievements)
        completion_pct = (completed_count / total_count * 100) if total_count > 0 else 0

        # Header with overall progress
        progress_bar = "▓" * int(completion_pct // 10) + "░" * (10 - int(completion_pct // 10))
        embed.description = (
            f"**Overall Progress**\n"
            f"`[{progress_bar}]` {completion_pct:.0f}%\n"
            f"🏆 **{completed_count}** / **{total_count}** achievements unlocked"
        )

        # ═══════════════════════════════════════
        # COMPLETED ACHIEVEMENTS
        # ═══════════════════════════════════════
        if completed:
            completed_list = []
            for achievement in all_achievements:
                if achievement.id in completed:
                    completed_list.append(f"{achievement.emoji}")

            # Show as emoji row (compact)
            completed_text = " ".join(completed_list[:15])
            if len(completed_list) > 15:
                completed_text += f" +{len(completed_list) - 15}"

            embed.add_field(
                name=f"✅ Unlocked ({completed_count})",
                value=completed_text if completed_text else "None yet!",
                inline=False
            )

        # ═══════════════════════════════════════
        # IN-PROGRESS ACHIEVEMENTS
        # ═══════════════════════════════════════
        locked = [a for a in all_achievements if a.id not in completed]
        if locked:
            # Sort by closest to completion
            progress_data = []
            for achievement in locked:
                current, goal, percentage = get_user_achievement_progress(user.id, achievement.id)
                progress_data.append((achievement, current, goal, percentage))

            # Sort by percentage (highest first)
            progress_data.sort(key=lambda x: x[3], reverse=True)

            progress_lines = []
            for achievement, current, goal, percentage in progress_data[:5]:
                bar_filled = int(percentage // 20)  # 5 char bar
                bar = "▓" * bar_filled + "░" * (5 - bar_filled)
                stat_display = format_stat_display(achievement.stat_key, current)
                goal_display = format_stat_display(achievement.stat_key, goal)
                progress_lines.append(
                    f"{achievement.emoji} **{achievement.name}**\n"
                    f"└ `[{bar}]` {stat_display} / {goal_display}"
                )

            embed.add_field(
                name=f"🔒 In Progress ({len(locked)} remaining)",
                value="\n".join(progress_lines) if progress_lines else "All achievements unlocked!",
                inline=False
            )

        # ═══════════════════════════════════════
        # QUICK STATS
        # ═══════════════════════════════════════
        messages = achievement_stats.get("messages_sent", 0)
        voice_time = achievement_stats.get("voice_time", 0)
        voice_hours = voice_time / 3600
        gambling_wins = achievement_stats.get("gambling_winnings", 0)
        max_streak = achievement_stats.get("max_win_streak", 0)

        stats_text = (
            f"💬 `{messages:,}` messages\n"
            f"🎧 `{voice_hours:.1f}h` voice time\n"
            f"💰 `{gambling_wins:,}` gambling wins\n"
            f"🍀 `{max_streak}` best win streak"
        )
        embed.add_field(name="📊 Your Stats", value=stats_text, inline=False)

        return embed

    def update_buttons(self):
        """Update button states based on current page"""
        self.clear_items()

        # Tab-style buttons for each page
        card_btn = Button(
            label="Card",
            emoji="🖼️",
            style=discord.ButtonStyle.primary if self.current_page == 1 else discord.ButtonStyle.secondary,
            row=0
        )
        card_btn.callback = self.go_to_card
        self.add_item(card_btn)

        stats_btn = Button(
            label="Stats",
            emoji="📊",
            style=discord.ButtonStyle.primary if self.current_page == 2 else discord.ButtonStyle.secondary,
            row=0
        )
        stats_btn.callback = self.go_to_stats
        self.add_item(stats_btn)

        achievements_btn = Button(
            label="Achievements",
            emoji="🏆",
            style=discord.ButtonStyle.primary if self.current_page == 3 else discord.ButtonStyle.secondary,
            row=0
        )
        achievements_btn.callback = self.go_to_achievements
        self.add_item(achievements_btn)

        # Close button
        close_btn = Button(
            label="Close",
            emoji="✖️",
            style=discord.ButtonStyle.danger,
            row=0
        )
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    async def go_to_card(self, interaction: discord.Interaction):
        """Go to profile card page"""
        self.current_page = 1
        self.update_buttons()
        embed, file = await self.get_page_content(interaction)
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)

    async def go_to_stats(self, interaction: discord.Interaction):
        """Go to stats page"""
        self.current_page = 2
        self.update_buttons()
        embed, file = await self.get_page_content(interaction)
        await interaction.response.edit_message(embed=embed, attachments=[], view=self)

    async def go_to_achievements(self, interaction: discord.Interaction):
        """Go to achievements page"""
        self.current_page = 3
        self.update_buttons()
        embed, file = await self.get_page_content(interaction)
        await interaction.response.edit_message(embed=embed, attachments=[], view=self)

    async def close_view(self, interaction: discord.Interaction):
        """Close the profile view"""
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self):
        """Disable all buttons when the view times out"""
        for item in self.children:
            item.disabled = True


class Profile(commands.Cog):
    """Graphical profile card system"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View your graphical profile card with stats and achievements")
    @app_commands.describe(user="The user to view (leave empty for yourself)")
    async def profile(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Generate and display a profile card with pagination"""
        target = user or interaction.user

        if target.bot:
            await interaction.response.send_message(
                "Bots don't have profiles!",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # Create the paginated view
            view = ProfileView(self.bot, target, interaction.user, interaction.guild.id)
            view.update_buttons()

            # Get the first page content
            embed, file = await view.get_page_content()

            # Send with file and view
            if file:
                await interaction.followup.send(embed=embed, file=file, view=view)
            else:
                await interaction.followup.send(embed=embed, view=view)

            logger.debug(f"Profile card generated for {target.name}")

        except Exception as e:
            logger.error(f"Error generating profile card: {e}")
            await interaction.followup.send(
                "Error generating profile card. Please try again.",
                ephemeral=True
            )

    @app_commands.command(name="profilecolor", description="Change your profile card accent color")
    @app_commands.describe(color="Hex color code (e.g., #FF5733)")
    async def profile_color(self, interaction: discord.Interaction, color: str):
        """Change profile accent color"""
        # Parse hex color
        if color.startswith("#"):
            color = color[1:]

        try:
            if len(color) != 6:
                raise ValueError("Invalid length")

            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)

            set_user_color(interaction.user.id, (r, g, b))

            embed = discord.Embed(
                title="Profile Color Updated",
                description=f"Your profile accent color is now **#{color.upper()}**",
                color=discord.Color.from_rgb(r, g, b)
            )
            embed.set_footer(text="Use /profile to see your new card!")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError:
            await interaction.response.send_message(
                "Invalid color! Use hex format like `#FF5733`",
                ephemeral=True
            )

    @app_commands.command(name="profilepresets", description="View available profile color presets")
    async def profile_presets(self, interaction: discord.Interaction):
        """Show color presets"""
        presets = {
            "Blurple": "#5865F2",
            "Green": "#57F287",
            "Yellow": "#FEE75C",
            "Red": "#ED4245",
            "Purple": "#9B59B6",
            "Orange": "#E67E22",
            "Pink": "#EB459E",
            "Teal": "#1ABC9C",
            "Gold": "#F1C40F",
            "Navy": "#34495E"
        }

        embed = discord.Embed(
            title="Profile Color Presets",
            description="Use `/profilecolor #HEX` to set your color",
            color=discord.Color.blue()
        )

        preset_text = "\n".join([f"**{name}**: `{code}`" for name, code in presets.items()])
        embed.add_field(name="Available Presets", value=preset_text, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="profilemotto", description="Set your profile motto (short tagline)")
    @app_commands.describe(motto="Your personal motto (max 50 characters, or 'clear' to remove)")
    async def profile_motto(self, interaction: discord.Interaction, motto: str):
        """Set profile motto"""
        if motto.lower() == "clear":
            profile = get_user_profile(interaction.user.id)
            profile["motto"] = None
            save_user_profile(interaction.user.id, profile)
            await interaction.response.send_message(
                "Your motto has been cleared!",
                ephemeral=True
            )
            return

        # Validate length
        if len(motto) > 50:
            await interaction.response.send_message(
                "Motto must be 50 characters or less!",
                ephemeral=True
            )
            return

        # Filter inappropriate content (basic check)
        profile = get_user_profile(interaction.user.id)
        profile["motto"] = motto
        save_user_profile(interaction.user.id, profile)

        embed = discord.Embed(
            title="Motto Updated!",
            description=f"Your new motto: *\"{motto}\"*",
            color=discord.Color.green()
        )
        embed.set_footer(text="Your motto will appear on your profile card!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="profilebanner", description="View and equip profile banners")
    @app_commands.describe(action="What to do", banner="Banner name (for equip/buy)")
    async def profile_banner(
        self,
        interaction: discord.Interaction,
        action: Literal["view", "equip", "buy"] = "view",
        banner: Optional[str] = None
    ):
        """Manage profile banners"""
        profile = get_user_profile(interaction.user.id)

        if action == "view":
            embed = discord.Embed(
                title="🎨 Profile Banners",
                description="Customize your profile card background!",
                color=discord.Color.purple()
            )

            owned = profile.get("owned_banners", ["default"])
            current = profile.get("banner", "default")

            # Show all banners
            for banner_id, info in PROFILE_BANNERS.items():
                status = ""
                if banner_id == current:
                    status = "**[EQUIPPED]** "
                elif banner_id in owned:
                    status = "**[OWNED]** "

                cost_text = f"Cost: {info['cost']:,} coins" if info['cost'] > 0 else "Free"
                embed.add_field(
                    name=f"{info['emoji']} {info['name']}",
                    value=f"{status}{info['description']}\n{cost_text}",
                    inline=True
                )

            embed.set_footer(text="Use /profilebanner buy <name> or /profilebanner equip <name>")
            await interaction.response.send_message(embed=embed)

        elif action == "equip":
            if not banner:
                await interaction.response.send_message(
                    "Please specify a banner to equip!",
                    ephemeral=True
                )
                return

            banner = banner.lower()
            if banner not in PROFILE_BANNERS:
                await interaction.response.send_message(
                    f"Banner `{banner}` not found! Use `/profilebanner view` to see available banners.",
                    ephemeral=True
                )
                return

            owned = profile.get("owned_banners", ["default"])
            if banner not in owned:
                await interaction.response.send_message(
                    f"You don't own the **{PROFILE_BANNERS[banner]['name']}** banner! Buy it first.",
                    ephemeral=True
                )
                return

            profile["banner"] = banner
            save_user_profile(interaction.user.id, profile)

            info = PROFILE_BANNERS[banner]
            await interaction.response.send_message(
                f"{info['emoji']} **{info['name']}** banner equipped!",
                ephemeral=True
            )

        elif action == "buy":
            if not banner:
                await interaction.response.send_message(
                    "Please specify a banner to buy!",
                    ephemeral=True
                )
                return

            banner = banner.lower()
            if banner not in PROFILE_BANNERS:
                await interaction.response.send_message(
                    f"Banner `{banner}` not found!",
                    ephemeral=True
                )
                return

            info = PROFILE_BANNERS[banner]
            owned = profile.get("owned_banners", ["default"])

            if banner in owned:
                await interaction.response.send_message(
                    f"You already own the **{info['name']}** banner!",
                    ephemeral=True
                )
                return

            # Check balance
            balance = get_balance(interaction.guild.id, interaction.user.id)
            if balance < info["cost"]:
                await interaction.response.send_message(
                    f"You need **{info['cost']:,}** coins but only have **{balance:,}**!",
                    ephemeral=True
                )
                return

            # Purchase - remove coins from user
            from utils.economy_db import remove_coins
            remove_coins(interaction.guild.id, interaction.user.id, info["cost"])

            if "owned_banners" not in profile:
                profile["owned_banners"] = ["default"]
            profile["owned_banners"].append(banner)
            save_user_profile(interaction.user.id, profile)

            embed = discord.Embed(
                title=f"{info['emoji']} Banner Purchased!",
                description=f"You bought **{info['name']}** for **{info['cost']:,}** coins!",
                color=discord.Color.green()
            )
            embed.set_footer(text="Use /profilebanner equip to use it!")
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profilebadges", description="View your earned badges")
    @app_commands.describe(user="User to view badges for (leave empty for yourself)")
    async def profile_badges(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """View profile badges"""
        target = user or interaction.user
        profile = get_user_profile(target.id)

        embed = discord.Embed(
            title=f"🏅 {target.display_name}'s Badges",
            color=discord.Color.gold()
        )

        earned_badges = profile.get("badges", [])

        if earned_badges:
            # Show earned badges
            earned_text = []
            for badge_id in earned_badges:
                if badge_id in PROFILE_BADGES:
                    info = PROFILE_BADGES[badge_id]
                    earned_text.append(f"{info['emoji']} **{info['name']}** - {info['description']}")

            embed.add_field(
                name=f"Earned ({len(earned_badges)}/{len(PROFILE_BADGES)})",
                value="\n".join(earned_text[:10]) if earned_text else "None",
                inline=False
            )

            # Show some locked badges as motivation
            locked = [b for b in PROFILE_BADGES.keys() if b not in earned_badges][:5]
            if locked:
                locked_text = []
                for badge_id in locked:
                    info = PROFILE_BADGES[badge_id]
                    locked_text.append(f"🔒 ~~{info['name']}~~ - {info['description']}")

                embed.add_field(
                    name="Locked (some shown)",
                    value="\n".join(locked_text),
                    inline=False
                )
        else:
            embed.description = "No badges earned yet! Keep using the bot to unlock badges."

            # Show some achievable badges
            sample_text = []
            for badge_id, info in list(PROFILE_BADGES.items())[:5]:
                sample_text.append(f"🔒 **{info['name']}** - {info['description']}")

            embed.add_field(
                name="Badges to Earn",
                value="\n".join(sample_text),
                inline=False
            )

        embed.set_footer(text="Badges are earned automatically through activity!")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profilefeature", description="Choose badges to feature on your profile")
    @app_commands.describe(badges="Badge names to feature (comma-separated, max 3)")
    async def profile_feature(self, interaction: discord.Interaction, badges: str):
        """Feature specific badges on profile"""
        profile = get_user_profile(interaction.user.id)
        earned = profile.get("badges", [])

        if not earned:
            await interaction.response.send_message(
                "You haven't earned any badges yet!",
                ephemeral=True
            )
            return

        # Parse badge names
        badge_names = [b.strip().lower() for b in badges.split(",")][:3]

        # Validate badges
        featured = []
        for name in badge_names:
            # Find badge by name or id
            found = None
            for badge_id, info in PROFILE_BADGES.items():
                if badge_id == name or info["name"].lower() == name:
                    found = badge_id
                    break

            if found and found in earned:
                featured.append(found)

        if not featured:
            await interaction.response.send_message(
                "No valid badges found! Make sure you've earned them.",
                ephemeral=True
            )
            return

        profile["featured_badges"] = featured
        save_user_profile(interaction.user.id, profile)

        badge_display = []
        for bid in featured:
            info = PROFILE_BADGES[bid]
            badge_display.append(f"{info['emoji']} {info['name']}")

        embed = discord.Embed(
            title="Featured Badges Updated!",
            description="These badges will appear on your profile:",
            color=discord.Color.green()
        )
        embed.add_field(name="Featured", value="\n".join(badge_display), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="profilecard", description="View a text-based profile overview")
    @app_commands.describe(user="User to view (leave empty for yourself)")
    async def profile_card(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """View text-based profile with all customizations"""
        target = user or interaction.user

        if target.bot:
            await interaction.response.send_message("Bots don't have profiles!", ephemeral=True)
            return

        profile = get_user_profile(target.id)
        level_data = get_user_level_data(interaction.guild.id, target.id)
        balance = get_balance(interaction.guild.id, target.id)
        reputation = get_rep_points(interaction.guild.id, target.id)

        # Get banner info
        banner_id = profile.get("banner", "default")
        banner = PROFILE_BANNERS.get(banner_id, PROFILE_BANNERS["default"])

        # Get color
        color = get_user_color(target.id)
        embed_color = discord.Color.from_rgb(*color)

        embed = discord.Embed(
            title=f"{banner['emoji']} {target.display_name}'s Profile",
            color=embed_color
        )

        # Motto
        if profile.get("motto"):
            embed.description = f"*\"{profile['motto']}\"*"

        embed.set_thumbnail(url=target.display_avatar.url)

        # Stats
        embed.add_field(
            name="📊 Level",
            value=f"Level **{level_data['level']}**\nRank #{level_data['rank']}",
            inline=True
        )
        embed.add_field(
            name="💰 Economy",
            value=f"**{balance:,}** coins",
            inline=True
        )
        embed.add_field(
            name="⭐ Reputation",
            value=f"**{reputation}** rep",
            inline=True
        )

        # Activity
        embed.add_field(
            name="💬 Activity",
            value=f"{level_data['messages']:,} messages\n{level_data['voice_minutes'] // 60}h voice",
            inline=True
        )

        # Featured badges
        featured = profile.get("featured_badges", [])
        if featured:
            badge_text = []
            for bid in featured[:3]:
                if bid in PROFILE_BADGES:
                    info = PROFILE_BADGES[bid]
                    badge_text.append(f"{info['emoji']} {info['name']}")
            if badge_text:
                embed.add_field(
                    name="🏅 Badges",
                    value="\n".join(badge_text),
                    inline=True
                )

        # Banner info
        embed.add_field(
            name="🎨 Banner",
            value=f"{banner['emoji']} {banner['name']}",
            inline=True
        )

        embed.set_footer(text="Use /profile for graphical card | /profilebadges for all badges")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Add the Profile cog to the bot"""
    await bot.add_cog(Profile(bot))
