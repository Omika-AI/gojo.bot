"""
Graphical Profile System - Visual profile cards with combined stats

Commands:
- /profile - View your graphical profile card
- /profile user - View another user's profile
- /profile color - Change your profile accent color
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.card_generator import create_profile_card, image_to_bytes, COLORS
from utils.leveling_db import get_user_level_data
from utils.economy_db import get_balance
from utils.reputation_db import get_rep_points
from utils.logger import logger

# Achievement tracking - simple count
TOTAL_ACHIEVEMENTS = 20  # Total available achievements in the system


def get_user_achievements(guild_id: int, user_id: int) -> int:
    """Get the number of achievements a user has unlocked"""
    try:
        from utils.achievements_data import get_user_achievements as get_achievements
        achievements = get_achievements(user_id)
        return len([a for a in achievements if a.get("completed", False)])
    except:
        return 0


# User profile color storage
USER_COLORS = {}


def get_user_color(user_id: int) -> tuple:
    """Get user's custom profile color"""
    return USER_COLORS.get(user_id, COLORS["primary"])


def set_user_color(user_id: int, color: tuple):
    """Set user's custom profile color"""
    USER_COLORS[user_id] = color


class Profile(commands.Cog):
    """Graphical profile card system"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View your graphical profile card")
    @app_commands.describe(user="The user to view (leave empty for yourself)")
    async def profile(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Generate and display a profile card"""
        target = user or interaction.user

        if target.bot:
            await interaction.response.send_message(
                "Bots don't have profiles!",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # Gather all user data
            level_data = get_user_level_data(interaction.guild.id, target.id)
            balance = get_balance(interaction.guild.id, target.id)
            reputation = get_rep_points(interaction.guild.id, target.id)
            achievements = get_user_achievements(interaction.guild.id, target.id)

            # Get accent color
            accent_color = get_user_color(target.id)

            # Generate profile card
            card = await create_profile_card(
                avatar_url=target.display_avatar.url,
                username=target.display_name,
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

            # Convert to file
            buffer = image_to_bytes(card)
            file = discord.File(buffer, filename="profile.png")

            # Send
            await interaction.followup.send(file=file)
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


async def setup(bot: commands.Bot):
    """Add the Profile cog to the bot"""
    await bot.add_cog(Profile(bot))
