"""
Achievements Command
View your or another user's earned achievements
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
    get_achievement_role_id
)
from utils.webhook_storage import get_channel_webhooks


class Achievements(commands.Cog):
    """View achievements"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="achievements", description="View your or another user's achievements")
    @app_commands.describe(user="The user to check achievements for (leave empty for yourself)")
    async def achievements(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Display a user's earned achievements"""
        try:
            guild_name = interaction.guild.name if interaction.guild else "DM"
            log_command(str(interaction.user), interaction.user.id, "achievements", guild_name)

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
                title=f"🏆 {target_user.display_name}'s Achievements",
                description=f"**{len(completed)}/{len(all_achievements)}** achievements unlocked",
                color=discord.Color.gold() if completed else discord.Color.light_grey()
            )

            # Use display_avatar for reliability
            embed.set_thumbnail(url=target_user.display_avatar.url)

            # Completed achievements
            if completed:
                completed_list = []
                for achievement in all_achievements:
                    if achievement.id in completed:
                        role_id = get_achievement_role_id(achievement.id)
                        role_text = ""
                        if role_id:
                            role = interaction.guild.get_role(role_id)
                            if role:
                                role_text = f" → {role.mention}"
                        completed_list.append(f"{achievement.emoji} **{achievement.name}**{role_text}")

                embed.add_field(
                    name="✅ Completed",
                    value="\n".join(completed_list) if completed_list else "None yet!",
                    inline=False
                )

            # Locked achievements
            locked = [a for a in all_achievements if a.id not in completed]
            if locked:
                locked_list = []
                for achievement in locked[:5]:  # Show first 5 locked
                    locked_list.append(f"🔒 ~~{achievement.name}~~ - *{achievement.description}*")

                if len(locked) > 5:
                    locked_list.append(f"*...and {len(locked) - 5} more*")

                embed.add_field(
                    name="🔒 Locked",
                    value="\n".join(locked_list),
                    inline=False
                )

            embed.set_footer(text="Use /achievementstats to see detailed progress")

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
                            "Achievement info sent!",
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
            logger.error(f"Error in /achievements command: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred while loading achievements. Please try again.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "An error occurred while loading achievements. Please try again.",
                        ephemeral=True
                    )
            except:
                pass


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Achievements cog to the bot"""
    await bot.add_cog(Achievements(bot))
