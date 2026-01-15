"""
Server Health Weekly Reports - Automated server statistics

Provides server admins with weekly automated reports about server activity,
engagement metrics, and health indicators.

Commands:
- /serverreports setup - Set up weekly report channel
- /serverreports disable - Disable weekly reports
- /serverreports now - Generate a report immediately
- /serverreports settings - View current settings
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, Literal
import json
import os
from datetime import datetime, timedelta

from utils.logger import logger

# Database paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
REPORTS_CONFIG_FILE = os.path.join(DATA_DIR, 'server_reports.json')
STATS_FILE = os.path.join(DATA_DIR, 'server_stats.json')


def load_reports_config() -> dict:
    """Load reports configuration"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(REPORTS_CONFIG_FILE):
        try:
            with open(REPORTS_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_reports_config(data: dict):
    """Save reports configuration"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPORTS_CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def load_stats() -> dict:
    """Load server statistics"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_stats(data: dict):
    """Save server statistics"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_guild_config(guild_id: int) -> dict:
    """Get report config for a guild"""
    data = load_reports_config()
    if str(guild_id) not in data:
        data[str(guild_id)] = {
            "enabled": False,
            "channel_id": None,
            "frequency": "weekly",  # weekly, daily
            "day": 0,  # 0 = Monday for weekly
            "hour": 9,  # 9 AM
            "last_report": None,
            "include_leaderboard": True,
            "include_activity": True,
            "include_moderation": True
        }
        save_reports_config(data)
    return data[str(guild_id)]


def save_guild_config(guild_id: int, config: dict):
    """Save report config for a guild"""
    data = load_reports_config()
    data[str(guild_id)] = config
    save_reports_config(data)


def get_guild_stats(guild_id: int) -> dict:
    """Get stats for a guild"""
    data = load_stats()
    if str(guild_id) not in data:
        data[str(guild_id)] = {
            "messages_today": 0,
            "messages_week": 0,
            "voice_minutes_week": 0,
            "new_members_week": 0,
            "left_members_week": 0,
            "active_users": [],
            "top_channels": {},
            "commands_used": 0,
            "last_reset": datetime.utcnow().isoformat()
        }
        save_stats(data)
    return data[str(guild_id)]


def save_guild_stats(guild_id: int, stats: dict):
    """Save stats for a guild"""
    data = load_stats()
    data[str(guild_id)] = stats
    save_stats(data)


def increment_message_count(guild_id: int, channel_id: int, user_id: int):
    """Increment message count for tracking"""
    stats = get_guild_stats(guild_id)
    stats["messages_today"] = stats.get("messages_today", 0) + 1
    stats["messages_week"] = stats.get("messages_week", 0) + 1

    # Track channel activity
    if "top_channels" not in stats:
        stats["top_channels"] = {}
    channel_key = str(channel_id)
    stats["top_channels"][channel_key] = stats["top_channels"].get(channel_key, 0) + 1

    # Track active users
    if "active_users" not in stats:
        stats["active_users"] = []
    if user_id not in stats["active_users"]:
        stats["active_users"].append(user_id)

    save_guild_stats(guild_id, stats)


def record_member_join(guild_id: int):
    """Record a member joining"""
    stats = get_guild_stats(guild_id)
    stats["new_members_week"] = stats.get("new_members_week", 0) + 1
    save_guild_stats(guild_id, stats)


def record_member_leave(guild_id: int):
    """Record a member leaving"""
    stats = get_guild_stats(guild_id)
    stats["left_members_week"] = stats.get("left_members_week", 0) + 1
    save_guild_stats(guild_id, stats)


class ServerReports(commands.Cog):
    """Automated server health reports"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.report_task.start()

    def cog_unload(self):
        self.report_task.cancel()

    serverreports_group = app_commands.Group(
        name="serverreports",
        description="Configure automated server reports"
    )

    @tasks.loop(hours=1)
    async def report_task(self):
        """Check if any servers need reports"""
        data = load_reports_config()
        current_time = datetime.utcnow()

        for guild_id_str, config in data.items():
            if not config.get("enabled") or not config.get("channel_id"):
                continue

            guild_id = int(guild_id_str)
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            # Check if it's time for a report
            should_send = False
            last_report = config.get("last_report")

            if config.get("frequency") == "weekly":
                # Weekly: check if it's the right day and hour
                if current_time.weekday() == config.get("day", 0):
                    if current_time.hour == config.get("hour", 9):
                        if not last_report or (
                            datetime.fromisoformat(last_report) < current_time - timedelta(days=6)
                        ):
                            should_send = True
            else:
                # Daily: check if it's the right hour
                if current_time.hour == config.get("hour", 9):
                    if not last_report or (
                        datetime.fromisoformat(last_report) < current_time - timedelta(hours=23)
                    ):
                        should_send = True

            if should_send:
                await self._send_report(guild, config)
                config["last_report"] = current_time.isoformat()
                save_guild_config(guild_id, config)

    @report_task.before_loop
    async def before_report_task(self):
        await self.bot.wait_until_ready()

    async def _send_report(self, guild: discord.Guild, config: dict):
        """Generate and send a server report"""
        channel = self.bot.get_channel(config["channel_id"])
        if not channel:
            return

        stats = get_guild_stats(guild.id)

        # Create the report embed
        embed = discord.Embed(
            title=f"📊 {guild.name} Weekly Report",
            description=f"Server health summary for the past week",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        # Member stats
        embed.add_field(
            name="👥 Members",
            value=(
                f"**Total:** {guild.member_count:,}\n"
                f"**Joined:** +{stats.get('new_members_week', 0)}\n"
                f"**Left:** -{stats.get('left_members_week', 0)}\n"
                f"**Net Change:** {stats.get('new_members_week', 0) - stats.get('left_members_week', 0):+d}"
            ),
            inline=True
        )

        # Activity stats
        active_count = len(stats.get("active_users", []))
        engagement = (active_count / guild.member_count * 100) if guild.member_count > 0 else 0

        embed.add_field(
            name="💬 Activity",
            value=(
                f"**Messages:** {stats.get('messages_week', 0):,}\n"
                f"**Active Users:** {active_count}\n"
                f"**Engagement:** {engagement:.1f}%\n"
                f"**Commands:** {stats.get('commands_used', 0):,}"
            ),
            inline=True
        )

        # Health indicator
        health_score = self._calculate_health(stats, guild)
        health_emoji = "🟢" if health_score >= 70 else "🟡" if health_score >= 40 else "🔴"
        health_text = "Excellent" if health_score >= 70 else "Good" if health_score >= 40 else "Needs Attention"

        embed.add_field(
            name="❤️ Server Health",
            value=f"{health_emoji} **{health_text}** ({health_score}/100)",
            inline=True
        )

        # Top channels
        if config.get("include_activity", True) and stats.get("top_channels"):
            sorted_channels = sorted(
                stats["top_channels"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]

            channel_text = []
            for ch_id, count in sorted_channels:
                ch = guild.get_channel(int(ch_id))
                if ch:
                    channel_text.append(f"#{ch.name}: {count:,} msgs")

            if channel_text:
                embed.add_field(
                    name="🏆 Most Active Channels",
                    value="\n".join(channel_text),
                    inline=False
                )

        # Recommendations
        recommendations = self._generate_recommendations(stats, guild)
        if recommendations:
            embed.add_field(
                name="💡 Recommendations",
                value="\n".join(f"• {r}" for r in recommendations[:3]),
                inline=False
            )

        embed.set_footer(text="Weekly report • Use /serverreports to configure")

        try:
            await channel.send(embed=embed)
            logger.info(f"Weekly report sent for {guild.name}")

            # Reset weekly stats
            stats["messages_week"] = 0
            stats["new_members_week"] = 0
            stats["left_members_week"] = 0
            stats["active_users"] = []
            stats["top_channels"] = {}
            stats["commands_used"] = 0
            stats["last_reset"] = datetime.utcnow().isoformat()
            save_guild_stats(guild.id, stats)

        except Exception as e:
            logger.error(f"Failed to send report for {guild.name}: {e}")

    def _calculate_health(self, stats: dict, guild: discord.Guild) -> int:
        """Calculate a health score for the server (0-100)"""
        score = 50  # Base score

        # Activity bonus
        messages = stats.get("messages_week", 0)
        if messages > 1000:
            score += 20
        elif messages > 500:
            score += 15
        elif messages > 100:
            score += 10
        elif messages > 50:
            score += 5

        # Engagement bonus
        active = len(stats.get("active_users", []))
        if guild.member_count > 0:
            engagement = active / guild.member_count
            if engagement > 0.3:
                score += 15
            elif engagement > 0.2:
                score += 10
            elif engagement > 0.1:
                score += 5

        # Growth bonus/penalty
        growth = stats.get("new_members_week", 0) - stats.get("left_members_week", 0)
        if growth > 10:
            score += 10
        elif growth > 5:
            score += 5
        elif growth < -10:
            score -= 10
        elif growth < -5:
            score -= 5

        return max(0, min(100, score))

    def _generate_recommendations(self, stats: dict, guild: discord.Guild) -> list:
        """Generate recommendations based on stats"""
        recommendations = []

        messages = stats.get("messages_week", 0)
        active = len(stats.get("active_users", []))

        if messages < 50:
            recommendations.append("Activity is low - consider hosting events or discussions")

        if guild.member_count > 0:
            engagement = active / guild.member_count
            if engagement < 0.1:
                recommendations.append("Many members are inactive - try @everyone announcements")

        growth = stats.get("new_members_week", 0) - stats.get("left_members_week", 0)
        if growth < 0:
            recommendations.append("Server is losing members - review recent changes")

        left = stats.get("left_members_week", 0)
        if left > 10:
            recommendations.append("High member turnover - consider improving onboarding")

        if not recommendations:
            recommendations.append("Server is healthy! Keep up the good work")

        return recommendations

    @serverreports_group.command(name="setup", description="Set up automated server reports")
    @app_commands.describe(
        channel="Channel to post reports to",
        frequency="How often to send reports",
        day="Day of week for weekly reports (0=Monday, 6=Sunday)",
        hour="Hour to send reports (0-23, UTC)"
    )
    @app_commands.default_permissions(administrator=True)
    async def reports_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        frequency: Literal["weekly", "daily"] = "weekly",
        day: app_commands.Range[int, 0, 6] = 0,
        hour: app_commands.Range[int, 0, 23] = 9
    ):
        """Set up server reports"""
        config = get_guild_config(interaction.guild.id)
        config["enabled"] = True
        config["channel_id"] = channel.id
        config["frequency"] = frequency
        config["day"] = day
        config["hour"] = hour
        save_guild_config(interaction.guild.id, config)

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        embed = discord.Embed(
            title="📊 Server Reports Enabled",
            description=f"Reports will be posted to {channel.mention}",
            color=discord.Color.green()
        )

        if frequency == "weekly":
            embed.add_field(
                name="Schedule",
                value=f"Every **{days[day]}** at **{hour}:00 UTC**",
                inline=False
            )
        else:
            embed.add_field(
                name="Schedule",
                value=f"Every day at **{hour}:00 UTC**",
                inline=False
            )

        embed.add_field(
            name="What's Included",
            value=(
                "• Member growth statistics\n"
                "• Activity metrics\n"
                "• Top active channels\n"
                "• Server health score\n"
                "• Recommendations"
            ),
            inline=False
        )

        embed.set_footer(text="Use /serverreports now to generate a report immediately")
        await interaction.response.send_message(embed=embed)

    @serverreports_group.command(name="disable", description="Disable automated server reports")
    @app_commands.default_permissions(administrator=True)
    async def reports_disable(self, interaction: discord.Interaction):
        """Disable reports"""
        config = get_guild_config(interaction.guild.id)
        config["enabled"] = False
        save_guild_config(interaction.guild.id, config)

        await interaction.response.send_message(
            "📊 Server reports have been disabled.",
            ephemeral=True
        )

    @serverreports_group.command(name="now", description="Generate a server report immediately")
    @app_commands.default_permissions(administrator=True)
    async def reports_now(self, interaction: discord.Interaction):
        """Generate report now"""
        await interaction.response.defer()

        config = get_guild_config(interaction.guild.id)

        if not config.get("channel_id"):
            # Send to current channel if not configured
            config["channel_id"] = interaction.channel.id

        await self._send_report(interaction.guild, config)

        await interaction.followup.send(
            "📊 Report generated!",
            ephemeral=True
        )

    @serverreports_group.command(name="settings", description="View current report settings")
    @app_commands.default_permissions(administrator=True)
    async def reports_settings(self, interaction: discord.Interaction):
        """View settings"""
        config = get_guild_config(interaction.guild.id)

        embed = discord.Embed(
            title="📊 Server Report Settings",
            color=discord.Color.blue()
        )

        status = "✅ Enabled" if config.get("enabled") else "❌ Disabled"
        embed.add_field(name="Status", value=status, inline=True)

        channel = None
        if config.get("channel_id"):
            channel = self.bot.get_channel(config["channel_id"])
        embed.add_field(
            name="Channel",
            value=channel.mention if channel else "Not set",
            inline=True
        )

        embed.add_field(
            name="Frequency",
            value=config.get("frequency", "weekly").title(),
            inline=True
        )

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if config.get("frequency") == "weekly":
            embed.add_field(
                name="Schedule",
                value=f"{days[config.get('day', 0)]} at {config.get('hour', 9)}:00 UTC",
                inline=True
            )
        else:
            embed.add_field(
                name="Schedule",
                value=f"Daily at {config.get('hour', 9)}:00 UTC",
                inline=True
            )

        last = config.get("last_report")
        if last:
            last_dt = datetime.fromisoformat(last)
            embed.add_field(
                name="Last Report",
                value=last_dt.strftime("%B %d, %Y at %H:%M UTC"),
                inline=True
            )

        await interaction.response.send_message(embed=embed)

    # Event listeners for stat tracking
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track message activity"""
        if message.author.bot or not message.guild:
            return
        increment_message_count(message.guild.id, message.channel.id, message.author.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Track member joins"""
        record_member_join(member.guild.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Track member leaves"""
        record_member_leave(member.guild.id)


async def setup(bot: commands.Bot):
    """Add the ServerReports cog to the bot"""
    await bot.add_cog(ServerReports(bot))
