"""
Reputation Command - Social recognition system

Allows users to give reputation points to helpful members.
Each user can give ONE rep point per day.

Commands:
- /rep @user - Give rep to someone
- /rep check [@user] - Check rep points
- /rep leaderboard - View most reputable members
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.reputation_db import (
    give_rep,
    get_rep_stats,
    get_rep_leaderboard,
    get_user_rep_rank,
    get_recent_rep_givers
)
from utils.logger import logger


class Reputation(commands.Cog):
    """Reputation system commands"""

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
            return f"`#{rank}`"

    @app_commands.command(name="rep", description="Give a reputation point to a helpful member (1 per day)")
    @app_commands.describe(user="The user to give rep to")
    async def rep(self, interaction: discord.Interaction, user: discord.Member):
        """Give reputation to another user"""

        logger.info(f"Rep command used by {interaction.user} for {user} in {interaction.guild.name}")

        # Can't rep bots
        if user.bot:
            await interaction.response.send_message(
                "You can't give rep to bots!",
                ephemeral=True
            )
            return

        # Can't rep yourself
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't give rep to yourself! Find someone helpful to appreciate.",
                ephemeral=True
            )
            return

        # Try to give rep
        success, message, new_total = give_rep(
            interaction.guild.id,
            interaction.user.id,
            user.id
        )

        if success:
            # Build success embed
            embed = discord.Embed(
                title="⭐ Reputation Given!",
                description=f"{interaction.user.mention} gave a rep point to {user.mention}!",
                color=discord.Color.gold()
            )
            embed.add_field(
                name=f"{user.display_name}'s Rep",
                value=f"**{new_total}** rep point{'s' if new_total != 1 else ''}",
                inline=True
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text="You can give rep again in 24 hours")

            await interaction.response.send_message(embed=embed)
            logger.info(f"[REP] {interaction.user} gave rep to {user} (now has {new_total} rep)")
        else:
            # Failed - on cooldown or other reason
            await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="repcheck", description="Check reputation points for yourself or another user")
    @app_commands.describe(user="The user to check (leave empty for yourself)")
    async def repcheck(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Check reputation stats"""

        target = user or interaction.user
        logger.info(f"Repcheck command used by {interaction.user} for {target} in {interaction.guild.name}")

        # Get rep stats
        stats = get_rep_stats(interaction.guild.id, target.id)
        rank = get_user_rep_rank(interaction.guild.id, target.id)
        recent_givers = get_recent_rep_givers(interaction.guild.id, target.id, limit=5)

        # Build embed
        embed = discord.Embed(
            title=f"⭐ {target.display_name}'s Reputation",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        # Rep points with rank
        rank_emoji = self.get_rank_emoji(rank)
        embed.add_field(
            name="Rep Points",
            value=f"**{stats['rep_points']}** {rank_emoji}",
            inline=True
        )

        # Rep given
        embed.add_field(
            name="Rep Given",
            value=f"**{stats['total_rep_given']}** to others",
            inline=True
        )

        # Can give rep status
        if stats['can_give_rep']:
            rep_status = "✅ Can give rep"
        else:
            if stats['next_rep_available']:
                # Calculate time remaining
                import datetime
                now = datetime.datetime.now()
                remaining = stats['next_rep_available'] - now
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                if hours > 0:
                    time_str = f"{hours}h {minutes}m"
                else:
                    time_str = f"{minutes}m"
                rep_status = f"⏳ Next rep in {time_str}"
            else:
                rep_status = "⏳ On cooldown"

        embed.add_field(
            name="Rep Status",
            value=rep_status,
            inline=True
        )

        # Recent rep givers
        if recent_givers:
            givers_text = ""
            for giver_info in recent_givers[:5]:
                try:
                    giver = await self.bot.fetch_user(int(giver_info["user_id"]))
                    givers_text += f"• {giver.display_name}\n"
                except:
                    givers_text += f"• Unknown User\n"

            if givers_text:
                embed.add_field(
                    name="Recent Rep From",
                    value=givers_text,
                    inline=False
                )

        embed.set_footer(text="Give rep with /rep @user")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="repleaderboard", description="View the most reputable members in the server")
    @app_commands.describe(page="Page number (10 users per page)")
    async def repleaderboard(self, interaction: discord.Interaction, page: Optional[int] = 1):
        """Display the reputation leaderboard"""

        logger.info(f"Repleaderboard command used by {interaction.user} in {interaction.guild.name}")

        if page < 1:
            page = 1

        await interaction.response.defer()

        try:
            # Get full leaderboard
            full_leaderboard = get_rep_leaderboard(interaction.guild.id, limit=100)

            if not full_leaderboard:
                embed = discord.Embed(
                    title="⭐ Reputation Leaderboard",
                    description="No one has received any rep yet!\nBe the first to recognize a helpful member with `/rep @user`",
                    color=discord.Color.gold()
                )
                await interaction.followup.send(embed=embed)
                return

            # Pagination
            per_page = 10
            total_users = len(full_leaderboard)
            total_pages = (total_users + per_page - 1) // per_page

            if page > total_pages:
                page = total_pages

            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_data = full_leaderboard[start_idx:end_idx]

            # Build embed
            embed = discord.Embed(
                title="⭐ Reputation Leaderboard",
                description=f"Most reputable members in **{interaction.guild.name}**",
                color=discord.Color.gold()
            )

            # Build leaderboard text
            leaderboard_text = ""
            for idx, (user_id, rep_points) in enumerate(page_data):
                rank = start_idx + idx + 1
                rank_emoji = self.get_rank_emoji(rank)

                try:
                    user = await self.bot.fetch_user(int(user_id))
                    username = user.display_name
                except:
                    username = f"User {user_id}"

                if len(username) > 15:
                    username = username[:12] + "..."

                leaderboard_text += f"{rank_emoji} **{username}** — {rep_points} rep\n"

            embed.add_field(name="Rankings", value=leaderboard_text, inline=False)

            # User's own rank
            user_stats = get_rep_stats(interaction.guild.id, interaction.user.id)
            user_rank = get_user_rep_rank(interaction.guild.id, interaction.user.id)

            embed.add_field(
                name="Your Reputation",
                value=f"**#{user_rank}** — {user_stats['rep_points']} rep",
                inline=False
            )

            embed.set_footer(text=f"Page {page}/{total_pages} • Give rep with /rep @user")

            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error displaying rep leaderboard: {e}")
            await interaction.followup.send(
                "An error occurred while fetching the leaderboard.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(Reputation(bot))
