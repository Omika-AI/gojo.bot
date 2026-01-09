"""
Achievement Stats Command
View detailed progress toward all achievements with progress bars
Sends via webhook if one exists in the channel
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import aiohttp

from utils.logger import log_command, logger
from utils.achievements_data import (
    get_all_achievements,
    get_user_stats,
    get_user_achievement_progress,
    format_progress_bar,
    format_stat_display
)
from utils.webhook_storage import get_channel_webhooks


class AchievementStats(commands.Cog):
    """View achievement progress"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="achievementstats", description="View detailed progress toward all achievements")
    @app_commands.describe(user="The user to check progress for (leave empty for yourself)")
    async def achievementstats(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Display detailed achievement progress with progress bars"""
        try:
            guild_name = interaction.guild.name if interaction.guild else "DM"
            log_command(str(interaction.user), interaction.user.id, "achievementstats", guild_name)

            # Check if in a guild
            if not interaction.guild:
                await interaction.response.send_message(
                    "This command can only be used in a server!",
                    ephemeral=True
                )
                return

            # Default to the command user
            target_user = user or interaction.user

            # Get user stats
            stats = get_user_stats(target_user.id)
            completed = stats.get("completed_achievements", [])
            all_achievements = get_all_achievements()

            # Build embed
            embed = discord.Embed(
                title=f"📊 {target_user.display_name}'s Achievement Progress",
                description=f"**{len(completed)}/{len(all_achievements)}** achievements completed",
                color=discord.Color.blue()
            )

            # Use display_avatar for reliability
            embed.set_thumbnail(url=target_user.display_avatar.url)

            # Show progress for each achievement
            for achievement in all_achievements:
                current, goal, percentage = get_user_achievement_progress(target_user.id, achievement.id)
                is_completed = achievement.id in completed

                # Format the progress display
                progress_bar = format_progress_bar(current, goal)
                current_display = format_stat_display(achievement.stat_key, current)
                goal_display = format_stat_display(achievement.stat_key, goal)

                if is_completed:
                    # Completed achievement
                    status = "✅ **COMPLETED!**"
                    field_value = f"{status}\n{progress_bar} 100%\n{current_display} / {goal_display}"
                else:
                    # In progress
                    field_value = f"{progress_bar} **{percentage:.0f}%**\n{current_display} / {goal_display}"

                embed.add_field(
                    name=f"{achievement.emoji} {achievement.name}",
                    value=field_value,
                    inline=True
                )

            # Add description of what each stat means
            embed.add_field(
                name="📖 How to Earn",
                value=(
                    "• **Chat God** - Send messages in any channel\n"
                    "• **Music Maestro** - Use /play to play songs\n"
                    "• **Karaoke Star** - Complete karaoke sessions\n"
                    "• **High Roller** - Win coins from gambling\n"
                    "• **Lucky Streak** - Win gambles consecutively"
                ),
                inline=False
            )

            embed.add_field(
                name="​",  # Zero-width space
                value=(
                    "• **Daily Devotee** - Maintain /claimdaily streak\n"
                    "• **Voice Veteran** - Time in voice channels\n"
                    "• **Command Master** - Use any bot commands\n"
                    "• **Wealthy Elite** - Reach 100k coins balance\n"
                    "• **Duet Partner** - Do /karaokeduet sessions"
                ),
                inline=False
            )

            embed.set_footer(text="Keep grinding to unlock achievements and earn special roles!")

            # Check for webhook in this channel to send via webhook
            webhooks = get_channel_webhooks(interaction.guild.id, interaction.channel.id)

            if webhooks:
                # Send via webhook
                webhook_data = webhooks[0]  # Use the first webhook
                webhook_url = webhook_data.get("url")

                if webhook_url:
                    # Acknowledge the interaction first
                    await interaction.response.defer(ephemeral=True)

                    try:
                        async with aiohttp.ClientSession() as session:
                            webhook = discord.Webhook.from_url(webhook_url, session=session)
                            await webhook.send(
                                embed=embed,
                                username=self.bot.user.display_name if self.bot.user else "Gojo",
                                avatar_url=self.bot.user.display_avatar.url if self.bot.user else None
                            )

                        await interaction.followup.send(
                            "Achievement stats sent!",
                            ephemeral=True
                        )
                    except Exception as e:
                        logger.error(f"Failed to send via webhook: {e}")
                        # Fallback to regular message
                        await interaction.followup.send(embed=embed)
                else:
                    await interaction.response.send_message(embed=embed)
            else:
                # No webhook, send regular message
                await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in /achievementstats command: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred while loading achievement stats. Please try again.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "An error occurred while loading achievement stats. Please try again.",
                        ephemeral=True
                    )
            except:
                pass


# Required setup function
async def setup(bot: commands.Bot):
    """Add the AchievementStats cog to the bot"""
    await bot.add_cog(AchievementStats(bot))
