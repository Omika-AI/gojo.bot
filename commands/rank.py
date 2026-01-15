"""
Rank Command - Displays a beautiful graphical rank card

This command generates an image showing:
- User's avatar
- Current level and XP progress
- Progress bar to next level
- Rank position in the server
- Total messages and voice time
"""

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Optional

from utils.leveling_db import get_user_level_data, get_guild_user_count
from utils.logger import logger


class Rank(commands.Cog):
    """Rank card generation commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def download_avatar(self, user: discord.User) -> Optional[Image.Image]:
        """Download and return user's avatar as a PIL Image"""
        try:
            # Get avatar URL (use default if none)
            avatar_url = user.display_avatar.url

            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as response:
                    if response.status == 200:
                        data = await response.read()
                        return Image.open(io.BytesIO(data)).convert("RGBA")
        except Exception as e:
            logger.error(f"Failed to download avatar: {e}")
        return None

    def create_circular_avatar(self, avatar: Image.Image, size: int = 150) -> Image.Image:
        """Create a circular avatar with anti-aliasing"""
        # Resize avatar to desired size
        avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)

        # Create circular mask
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)

        # Apply mask
        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        output.paste(avatar, mask=mask)

        return output

    def create_progress_bar(
        self,
        width: int,
        height: int,
        progress: float,
        bg_color: tuple = (50, 50, 60),
        fill_color_start: tuple = (88, 101, 242),  # Discord blurple
        fill_color_end: tuple = (114, 137, 218)    # Lighter blurple
    ) -> Image.Image:
        """Create a gradient progress bar"""
        bar = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(bar)

        # Draw background with rounded corners
        radius = height // 2
        draw.rounded_rectangle(
            [(0, 0), (width - 1, height - 1)],
            radius=radius,
            fill=bg_color
        )

        # Calculate fill width
        fill_width = int((width - 4) * (progress / 100))
        if fill_width > radius:
            # Create gradient fill
            gradient = Image.new("RGBA", (fill_width, height - 4), fill_color_start)
            for x in range(fill_width):
                # Linear interpolation for gradient
                ratio = x / max(fill_width - 1, 1)
                r = int(fill_color_start[0] + (fill_color_end[0] - fill_color_start[0]) * ratio)
                g = int(fill_color_start[1] + (fill_color_end[1] - fill_color_start[1]) * ratio)
                b = int(fill_color_start[2] + (fill_color_end[2] - fill_color_start[2]) * ratio)
                for y in range(height - 4):
                    gradient.putpixel((x, y), (r, g, b, 255))

            # Create mask for rounded corners on fill
            fill_mask = Image.new("L", (fill_width, height - 4), 0)
            fill_draw = ImageDraw.Draw(fill_mask)
            fill_draw.rounded_rectangle(
                [(0, 0), (fill_width - 1, height - 5)],
                radius=radius - 2,
                fill=255
            )

            # Paste gradient with mask
            bar.paste(gradient, (2, 2), fill_mask)

        return bar

    def get_rank_color(self, rank: int) -> tuple:
        """Get color based on rank (gold, silver, bronze, or default)"""
        if rank == 1:
            return (255, 215, 0)     # Gold
        elif rank == 2:
            return (192, 192, 192)   # Silver
        elif rank == 3:
            return (205, 127, 50)    # Bronze
        else:
            return (255, 255, 255)   # White

    def format_number(self, num: int) -> str:
        """Format large numbers (1000 -> 1K, 1000000 -> 1M)"""
        if num >= 1000000:
            return f"{num / 1000000:.1f}M"
        elif num >= 1000:
            return f"{num / 1000:.1f}K"
        return str(num)

    def create_rank_card(
        self,
        avatar: Image.Image,
        username: str,
        discriminator: str,
        level: int,
        xp: int,
        xp_needed: int,
        total_xp: int,
        rank: int,
        total_users: int,
        messages: int,
        voice_minutes: int,
        progress: float
    ) -> Image.Image:
        """
        Create the complete rank card image

        Args:
            avatar: User's avatar image
            username: User's display name
            discriminator: User's discriminator or "0" for new usernames
            level: Current level
            xp: Current XP in this level
            xp_needed: XP needed to reach next level
            total_xp: Total XP earned
            rank: User's rank in the server
            total_users: Total users in leaderboard
            messages: Total messages sent
            voice_minutes: Total voice channel minutes
            progress: Percentage to next level
        """
        # Card dimensions
        card_width = 934
        card_height = 282

        # Create base card with gradient background
        card = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))

        # Create gradient background
        for y in range(card_height):
            for x in range(card_width):
                # Dark gradient from top-left to bottom-right
                ratio = (x + y) / (card_width + card_height)
                r = int(30 + ratio * 15)
                g = int(33 + ratio * 15)
                b = int(36 + ratio * 20)
                card.putpixel((x, y), (r, g, b, 255))

        draw = ImageDraw.Draw(card)

        # Add subtle border
        draw.rounded_rectangle(
            [(0, 0), (card_width - 1, card_height - 1)],
            radius=20,
            outline=(88, 101, 242, 100),
            width=2
        )

        # Load fonts (use default if custom fonts not available)
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            font_xlarge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except:
            # Fallback to default font
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
            font_xlarge = ImageFont.load_default()

        # Position constants
        avatar_size = 150
        avatar_x = 40
        avatar_y = (card_height - avatar_size) // 2

        # Draw avatar background circle (glow effect)
        glow_radius = avatar_size // 2 + 5
        glow_center = (avatar_x + avatar_size // 2, avatar_y + avatar_size // 2)
        draw.ellipse(
            [
                (glow_center[0] - glow_radius, glow_center[1] - glow_radius),
                (glow_center[0] + glow_radius, glow_center[1] + glow_radius)
            ],
            outline=(88, 101, 242, 150),
            width=3
        )

        # Add circular avatar
        circular_avatar = self.create_circular_avatar(avatar, avatar_size)
        card.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)

        # Text starting position (after avatar)
        text_x = avatar_x + avatar_size + 30

        # Draw username
        username_display = username[:20] + "..." if len(username) > 20 else username
        draw.text((text_x, 35), username_display, fill=(255, 255, 255), font=font_large)

        # Draw discriminator (if not "0")
        if discriminator and discriminator != "0":
            username_width = draw.textlength(username_display, font=font_large)
            draw.text(
                (text_x + username_width + 10, 45),
                f"#{discriminator}",
                fill=(150, 150, 150),
                font=font_medium
            )

        # Draw rank badge (top right)
        rank_text = f"#{rank}"
        rank_color = self.get_rank_color(rank)
        rank_x = card_width - 120
        draw.text((rank_x, 30), "RANK", fill=(150, 150, 150), font=font_small)
        draw.text((rank_x, 50), rank_text, fill=rank_color, font=font_xlarge)

        # Draw level badge
        level_x = rank_x - 150
        draw.text((level_x, 30), "LEVEL", fill=(150, 150, 150), font=font_small)
        draw.text((level_x, 50), str(level), fill=(88, 101, 242), font=font_xlarge)

        # Progress bar position
        bar_x = text_x
        bar_y = 140
        bar_width = card_width - bar_x - 40
        bar_height = 30

        # Draw progress bar
        progress_bar = self.create_progress_bar(bar_width, bar_height, progress)
        card.paste(progress_bar, (bar_x, bar_y), progress_bar)

        # XP text on progress bar
        xp_text = f"{self.format_number(xp)} / {self.format_number(xp_needed)} XP"
        xp_width = draw.textlength(xp_text, font=font_small)
        draw.text(
            (bar_x + bar_width - xp_width - 10, bar_y + 5),
            xp_text,
            fill=(255, 255, 255),
            font=font_small
        )

        # Progress percentage
        progress_text = f"{progress:.1f}%"
        draw.text((bar_x + 10, bar_y + 5), progress_text, fill=(255, 255, 255), font=font_small)

        # Stats row at bottom
        stats_y = 200
        stats_spacing = 180

        # Total XP
        draw.text((text_x, stats_y), "Total XP", fill=(150, 150, 150), font=font_small)
        draw.text((text_x, stats_y + 20), self.format_number(total_xp), fill=(255, 255, 255), font=font_medium)

        # Messages
        draw.text((text_x + stats_spacing, stats_y), "Messages", fill=(150, 150, 150), font=font_small)
        draw.text((text_x + stats_spacing, stats_y + 20), self.format_number(messages), fill=(255, 255, 255), font=font_medium)

        # Voice time
        voice_hours = voice_minutes // 60
        voice_mins = voice_minutes % 60
        voice_text = f"{voice_hours}h {voice_mins}m" if voice_hours > 0 else f"{voice_mins}m"
        draw.text((text_x + stats_spacing * 2, stats_y), "Voice Time", fill=(150, 150, 150), font=font_small)
        draw.text((text_x + stats_spacing * 2, stats_y + 20), voice_text, fill=(255, 255, 255), font=font_medium)

        # Server rank position
        rank_pos_text = f"of {total_users}"
        draw.text((text_x + stats_spacing * 3, stats_y), "Server Rank", fill=(150, 150, 150), font=font_small)
        draw.text((text_x + stats_spacing * 3, stats_y + 20), f"#{rank} {rank_pos_text}", fill=(255, 255, 255), font=font_medium)

        return card

    @app_commands.command(name="rank", description="View your level and XP with a beautiful rank card")
    @app_commands.describe(user="The user to view (leave empty for yourself)")
    async def rank(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Display a graphical rank card for a user"""

        # Log command usage
        logger.info(f"Rank command used by {interaction.user} in {interaction.guild.name}")

        # Default to command user if no user specified
        target_user = user or interaction.user

        # Defer response since image generation takes time
        await interaction.response.defer()

        try:
            # Get user's level data
            level_data = get_user_level_data(interaction.guild.id, target_user.id)
            total_users = get_guild_user_count(interaction.guild.id)

            # Download avatar
            avatar = await self.download_avatar(target_user)
            if avatar is None:
                # Create default avatar if download fails
                avatar = Image.new("RGBA", (128, 128), (88, 101, 242, 255))
                draw = ImageDraw.Draw(avatar)
                # Draw first letter of username
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
                except:
                    font = ImageFont.load_default()
                letter = target_user.display_name[0].upper()
                bbox = draw.textbbox((0, 0), letter, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                draw.text(
                    ((128 - text_width) // 2, (128 - text_height) // 2 - 10),
                    letter,
                    fill=(255, 255, 255),
                    font=font
                )

            # Create rank card
            rank_card = self.create_rank_card(
                avatar=avatar,
                username=target_user.display_name,
                discriminator=target_user.discriminator,
                level=level_data["level"],
                xp=level_data["xp"],
                xp_needed=level_data["xp_needed"],
                total_xp=level_data["total_xp"],
                rank=level_data["rank"],
                total_users=max(total_users, 1),
                messages=level_data["messages"],
                voice_minutes=level_data["voice_minutes"],
                progress=level_data["progress"]
            )

            # Convert to bytes for Discord
            buffer = io.BytesIO()
            rank_card.save(buffer, format="PNG")
            buffer.seek(0)

            # Send the image
            file = discord.File(buffer, filename=f"rank_{target_user.id}.png")
            await interaction.followup.send(file=file)

            logger.info(f"Rank card generated for {target_user} (Level {level_data['level']})")

        except Exception as e:
            logger.error(f"Error generating rank card: {e}")
            await interaction.followup.send(
                "An error occurred while generating your rank card. Please try again later.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(Rank(bot))
