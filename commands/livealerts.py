"""
Live Alerts Command - Stream notifications for Twitch/YouTube

Allows admins to set up live stream alerts for content creators.
When a tracked streamer goes live, Gojo posts an embed in the designated channel.

Commands:
- /livealerts setup - Set up the alerts channel
- /livealerts add - Add a streamer to track
- /livealerts remove - Remove a streamer
- /livealerts list - List tracked streamers
- /livealerts role - Set mention role for alerts
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal

from utils.live_alerts_db import (
    set_alert_channel,
    get_alert_channel,
    add_streamer,
    remove_streamer,
    get_streamers,
    set_mention_role,
    get_mention_role
)
from utils.logger import logger


class LiveAlerts(commands.Cog):
    """Live stream alert commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Create command group
    alerts_group = app_commands.Group(
        name="livealerts",
        description="Manage live stream alerts for Twitch and YouTube"
    )

    @alerts_group.command(name="setup", description="Set up the channel for live stream alerts")
    @app_commands.describe(channel="The channel to post alerts in")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set up the alerts channel"""

        logger.info(f"Live alerts setup by {interaction.user} in {interaction.guild.name}")

        # Set the channel
        set_alert_channel(interaction.guild.id, channel.id)

        embed = discord.Embed(
            title="📺 Live Alerts Setup Complete",
            description=f"Live stream alerts will now be posted in {channel.mention}",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="Next Steps",
            value=(
                "1. Add streamers with `/livealerts add`\n"
                "2. Optionally set a mention role with `/livealerts role`\n"
                "3. Gojo will check for live streams every 5 minutes"
            ),
            inline=False
        )
        embed.set_footer(text="Supported platforms: Twitch, YouTube")

        await interaction.response.send_message(embed=embed)

    @alerts_group.command(name="add", description="Add a streamer to track for live alerts")
    @app_commands.describe(
        platform="The streaming platform",
        username="The streamer's username or channel ID"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add(
        self,
        interaction: discord.Interaction,
        platform: Literal["twitch", "youtube"],
        username: str
    ):
        """Add a streamer to track"""

        logger.info(f"Adding streamer {username} ({platform}) in {interaction.guild.name}")

        # Check if alerts channel is set up
        alert_channel = get_alert_channel(interaction.guild.id)
        if not alert_channel:
            await interaction.response.send_message(
                "Please set up an alerts channel first with `/livealerts setup`",
                ephemeral=True
            )
            return

        # Clean up the username
        username = username.strip().lstrip('@')

        # For YouTube, accept channel URLs and extract the handle/ID
        if platform == "youtube":
            if "youtube.com" in username or "youtu.be" in username:
                # Try to extract channel handle
                if "/@" in username:
                    username = username.split("/@")[1].split("/")[0].split("?")[0]
                elif "/channel/" in username:
                    username = username.split("/channel/")[1].split("/")[0].split("?")[0]
                elif "/c/" in username:
                    username = username.split("/c/")[1].split("/")[0].split("?")[0]

        # Add the streamer
        success, message = add_streamer(interaction.guild.id, platform, username)

        if success:
            embed = discord.Embed(
                title="✅ Streamer Added",
                description=f"Now tracking **{username}** on **{platform.title()}**",
                color=discord.Color.green()
            )

            # Add platform-specific info
            if platform == "twitch":
                embed.add_field(
                    name="Twitch Profile",
                    value=f"https://twitch.tv/{username}",
                    inline=False
                )
            elif platform == "youtube":
                embed.add_field(
                    name="Note",
                    value="YouTube live checking works best with channel handles (@username)",
                    inline=False
                )

            embed.set_footer(text="Alerts will be posted when they go live")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)

    @alerts_group.command(name="remove", description="Remove a streamer from tracking")
    @app_commands.describe(
        platform="The streaming platform",
        username="The streamer's username"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(
        self,
        interaction: discord.Interaction,
        platform: Literal["twitch", "youtube"],
        username: str
    ):
        """Remove a streamer from tracking"""

        logger.info(f"Removing streamer {username} ({platform}) in {interaction.guild.name}")

        success, message = remove_streamer(interaction.guild.id, platform, username.strip())

        if success:
            embed = discord.Embed(
                title="✅ Streamer Removed",
                description=f"Stopped tracking **{username}** on **{platform.title()}**",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)

    @alerts_group.command(name="list", description="List all tracked streamers")
    async def list_streamers(self, interaction: discord.Interaction):
        """List all tracked streamers"""

        logger.info(f"Live alerts list viewed by {interaction.user} in {interaction.guild.name}")

        streamers = get_streamers(interaction.guild.id)
        alert_channel_id = get_alert_channel(interaction.guild.id)
        mention_role_id = get_mention_role(interaction.guild.id)

        embed = discord.Embed(
            title="📺 Live Stream Alerts",
            color=discord.Color.purple()
        )

        # Alert channel
        if alert_channel_id:
            channel = interaction.guild.get_channel(alert_channel_id)
            embed.add_field(
                name="Alert Channel",
                value=channel.mention if channel else "Channel not found",
                inline=True
            )
        else:
            embed.add_field(
                name="Alert Channel",
                value="Not set up - use `/livealerts setup`",
                inline=True
            )

        # Mention role
        if mention_role_id:
            role = interaction.guild.get_role(mention_role_id)
            embed.add_field(
                name="Mention Role",
                value=role.mention if role else "Role not found",
                inline=True
            )
        else:
            embed.add_field(
                name="Mention Role",
                value="None (no pings)",
                inline=True
            )

        # Streamers by platform
        if streamers:
            twitch_streamers = [s for s in streamers if s["platform"] == "twitch"]
            youtube_streamers = [s for s in streamers if s["platform"] == "youtube"]

            if twitch_streamers:
                twitch_list = "\n".join([
                    f"• **{s['username']}** ({s.get('last_status', 'unknown')})"
                    for s in twitch_streamers
                ])
                embed.add_field(
                    name="🟣 Twitch",
                    value=twitch_list,
                    inline=False
                )

            if youtube_streamers:
                youtube_list = "\n".join([
                    f"• **{s['username']}** ({s.get('last_status', 'unknown')})"
                    for s in youtube_streamers
                ])
                embed.add_field(
                    name="🔴 YouTube",
                    value=youtube_list,
                    inline=False
                )
        else:
            embed.add_field(
                name="Tracked Streamers",
                value="No streamers being tracked.\nAdd one with `/livealerts add`",
                inline=False
            )

        embed.set_footer(text="Gojo checks for live streams every 5 minutes")
        await interaction.response.send_message(embed=embed)

    @alerts_group.command(name="role", description="Set a role to mention when someone goes live")
    @app_commands.describe(role="The role to ping (leave empty to disable)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_role(self, interaction: discord.Interaction, role: Optional[discord.Role] = None):
        """Set the mention role for alerts"""

        logger.info(f"Live alerts role set by {interaction.user} in {interaction.guild.name}")

        set_mention_role(interaction.guild.id, role.id if role else None)

        if role:
            embed = discord.Embed(
                title="✅ Mention Role Set",
                description=f"{role.mention} will be pinged when tracked streamers go live",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="✅ Mention Role Disabled",
                description="No role will be pinged for live alerts",
                color=discord.Color.orange()
            )

        await interaction.response.send_message(embed=embed)

    # Error handlers
    @setup.error
    @add.error
    @remove.error
    @set_role.error
    async def alerts_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need **Administrator** permission to manage live alerts.",
                ephemeral=True
            )
        else:
            logger.error(f"Live alerts error: {error}")
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(LiveAlerts(bot))
