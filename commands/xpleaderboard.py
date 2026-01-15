"""
XP Leaderboard Command - Shows the top users by XP/Level

Displays a ranked list of users sorted by their total XP,
showing their level, total XP, and rank position.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.leveling_db import get_xp_leaderboard, get_user_level_data
from utils.logger import logger


class XPLeaderboard(commands.Cog):
    """XP Leaderboard commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_rank_emoji(self, rank: int) -> str:
        """Get medal emoji for top 3 ranks"""
        if rank == 1:
            return "🥇"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        else:
            return f"`{rank}.`"

    def format_xp(self, xp: int) -> str:
        """Format XP number for display"""
        if xp >= 1000000:
            return f"{xp / 1000000:.1f}M"
        elif xp >= 1000:
            return f"{xp / 1000:.1f}K"
        return str(xp)

    @app_commands.command(name="xpleaderboard", description="View the server's XP leaderboard")
    @app_commands.describe(page="Page number to view (10 users per page)")
    async def xpleaderboard(self, interaction: discord.Interaction, page: Optional[int] = 1):
        """Display the XP leaderboard for the server"""

        # Log command usage
        logger.info(f"XP Leaderboard command used by {interaction.user} in {interaction.guild.name}")

        # Validate page number
        if page < 1:
            page = 1

        # Defer response while we fetch data
        await interaction.response.defer()

        try:
            # Get leaderboard data (fetch more than needed to determine total pages)
            # We'll fetch up to 100 users for pagination
            full_leaderboard = get_xp_leaderboard(interaction.guild.id, limit=100)

            if not full_leaderboard:
                embed = discord.Embed(
                    title="📊 XP Leaderboard",
                    description="No one has earned any XP yet!\nStart chatting or join voice channels to earn XP.",
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=embed)
                return

            # Calculate pagination
            per_page = 10
            total_users = len(full_leaderboard)
            total_pages = (total_users + per_page - 1) // per_page

            # Validate page number
            if page > total_pages:
                page = total_pages

            # Get slice for current page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_data = full_leaderboard[start_idx:end_idx]

            # Build the embed
            embed = discord.Embed(
                title="📊 XP Leaderboard",
                description=f"Top chatters in **{interaction.guild.name}**",
                color=discord.Color.blue()
            )

            # Build leaderboard text
            leaderboard_text = ""
            for idx, (user_id, level, total_xp) in enumerate(page_data):
                rank = start_idx + idx + 1
                rank_emoji = self.get_rank_emoji(rank)

                # Try to get user info
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    username = user.display_name
                except:
                    username = f"User {user_id}"

                # Truncate username if too long
                if len(username) > 15:
                    username = username[:12] + "..."

                # Format the line
                xp_formatted = self.format_xp(total_xp)
                leaderboard_text += f"{rank_emoji} **{username}** — Level {level} • {xp_formatted} XP\n"

            embed.add_field(name="Rankings", value=leaderboard_text, inline=False)

            # Add user's own rank at the bottom
            user_data = get_user_level_data(interaction.guild.id, interaction.user.id)
            user_rank = user_data["rank"]
            user_level = user_data["level"]
            user_xp = self.format_xp(user_data["total_xp"])

            embed.add_field(
                name="Your Rank",
                value=f"**#{user_rank}** — Level {user_level} • {user_xp} XP",
                inline=False
            )

            # Add pagination info in footer
            embed.set_footer(text=f"Page {page}/{total_pages} • {total_users} total users")

            # Add thumbnail
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error displaying XP leaderboard: {e}")
            await interaction.followup.send(
                "An error occurred while fetching the leaderboard. Please try again later.",
                ephemeral=True
            )

    @app_commands.command(name="levels", description="View XP requirements for each level")
    async def levels(self, interaction: discord.Interaction):
        """Display XP requirements for different levels"""

        logger.info(f"Levels command used by {interaction.user} in {interaction.guild.name}")

        # Import the XP calculation function
        from utils.leveling_db import xp_for_level, MILESTONE_REWARDS

        embed = discord.Embed(
            title="📈 Level Requirements",
            description="XP needed to reach each level and milestone rewards",
            color=discord.Color.gold()
        )

        # Show level requirements for key levels
        level_info = ""
        key_levels = [1, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100]

        for level in key_levels:
            xp_needed = xp_for_level(level)
            xp_formatted = self.format_xp(xp_needed)

            # Check if this level has a coin reward
            if level in MILESTONE_REWARDS:
                reward = MILESTONE_REWARDS[level]
                reward_formatted = f"{reward:,}"
                level_info += f"**Level {level}** — {xp_formatted} XP 💰 +{reward_formatted} coins\n"
            else:
                level_info += f"**Level {level}** — {xp_formatted} XP\n"

        embed.add_field(name="Level → XP Required", value=level_info, inline=False)

        # Add XP earning info
        xp_info = (
            "**Messages:** 15-25 XP per message (1 min cooldown)\n"
            "**Voice Chat:** 10 XP per minute in voice channels\n"
            "\n*Keep chatting and hanging out to level up!*"
        )
        embed.add_field(name="How to Earn XP", value=xp_info, inline=False)

        embed.set_footer(text="Milestone rewards are one-time bonuses!")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(XPLeaderboard(bot))
