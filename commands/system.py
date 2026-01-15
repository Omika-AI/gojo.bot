"""
System Health Dashboard - Owner-only bot monitoring

Commands:
- /system - View bot health and performance metrics
- /system errors - View recent error logs
- /system servers - View server statistics
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import psutil
import os
import sys

import config
from utils.logger import logger

# Store recent errors in memory
RECENT_ERRORS = []
MAX_ERRORS = 50


def log_error(error_msg: str):
    """Log an error to the recent errors list"""
    RECENT_ERRORS.append({
        "timestamp": datetime.utcnow(),
        "message": str(error_msg)[:500]
    })
    # Keep only recent errors
    while len(RECENT_ERRORS) > MAX_ERRORS:
        RECENT_ERRORS.pop(0)


class System(commands.Cog):
    """System health monitoring for bot owners"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = datetime.utcnow()

    system_group = app_commands.Group(
        name="system",
        description="Bot system health and monitoring (Owner only)"
    )

    def is_bot_owner(self, user_id: int) -> bool:
        """Check if user is bot owner (defined in config or first guild owner)"""
        # Check if OWNER_ID is defined in config
        owner_id = getattr(config, 'OWNER_ID', None)
        if owner_id and user_id == owner_id:
            return True
        # Fallback: check if user owns any server the bot is in
        for guild in self.bot.guilds:
            if guild.owner_id == user_id:
                return True
        return False

    @system_group.command(name="health", description="View bot health and performance metrics")
    async def system_health(self, interaction: discord.Interaction):
        """Display system health dashboard"""
        if not self.is_bot_owner(interaction.user.id):
            await interaction.response.send_message(
                "This command is only available to bot owners.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Calculate uptime
        uptime = datetime.utcnow() - self.start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        # Get system metrics
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent(interval=0.1)

        # Get latency
        latency = round(self.bot.latency * 1000, 2)

        # Latency status
        if latency < 100:
            latency_status = "Excellent"
            latency_emoji = "🟢"
        elif latency < 200:
            latency_status = "Good"
            latency_emoji = "🟡"
        else:
            latency_status = "Poor"
            latency_emoji = "🔴"

        embed = discord.Embed(
            title="🖥️ System Health Dashboard",
            description=f"**{config.BOT_NAME}** v{config.BOT_VERSION}",
            color=discord.Color.green() if latency < 200 else discord.Color.orange(),
            timestamp=datetime.utcnow()
        )

        # Connection Status
        embed.add_field(
            name="📡 Connection",
            value=(
                f"{latency_emoji} **Latency:** {latency}ms ({latency_status})\n"
                f"**WebSocket:** {'Connected' if not self.bot.is_closed() else 'Disconnected'}\n"
                f"**Uptime:** {uptime_str}"
            ),
            inline=True
        )

        # Resource Usage
        embed.add_field(
            name="💾 Resources",
            value=(
                f"**Memory:** {memory_mb:.1f} MB\n"
                f"**CPU:** {cpu_percent:.1f}%\n"
                f"**Python:** {sys.version.split()[0]}"
            ),
            inline=True
        )

        # Bot Statistics
        total_users = sum(g.member_count for g in self.bot.guilds if g.member_count)
        total_channels = sum(len(g.channels) for g in self.bot.guilds)

        embed.add_field(
            name="📊 Statistics",
            value=(
                f"**Servers:** {len(self.bot.guilds)}\n"
                f"**Users:** {total_users:,}\n"
                f"**Channels:** {total_channels:,}"
            ),
            inline=True
        )

        # Cogs Status
        loaded_cogs = len(self.bot.cogs)
        embed.add_field(
            name="⚙️ Modules",
            value=(
                f"**Loaded Cogs:** {loaded_cogs}\n"
                f"**Slash Commands:** {len(self.bot.tree.get_commands())}\n"
                f"**Recent Errors:** {len(RECENT_ERRORS)}"
            ),
            inline=True
        )

        # Database check (simple file check)
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        db_exists = os.path.exists(db_path)
        db_status = "🟢 Connected" if db_exists else "🔴 Missing"

        embed.add_field(
            name="🗄️ Database",
            value=(
                f"**Status:** {db_status}\n"
                f"**Type:** JSON Files\n"
                f"**Path:** ./data/"
            ),
            inline=True
        )

        # Quick Actions
        embed.add_field(
            name="🔧 Quick Commands",
            value=(
                "`/system errors` - View recent errors\n"
                "`/system servers` - Server breakdown\n"
                "`/system clear` - Clear error logs"
            ),
            inline=False
        )

        embed.set_footer(text=f"Requested by {interaction.user}")

        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"System health checked by {interaction.user}")

    @system_group.command(name="errors", description="View recent error logs")
    async def system_errors(self, interaction: discord.Interaction):
        """View recent errors"""
        if not self.is_bot_owner(interaction.user.id):
            await interaction.response.send_message(
                "This command is only available to bot owners.",
                ephemeral=True
            )
            return

        if not RECENT_ERRORS:
            await interaction.response.send_message(
                "No recent errors logged! Everything is running smoothly.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🚨 Recent Errors",
            description=f"Showing last {min(10, len(RECENT_ERRORS))} errors",
            color=discord.Color.red()
        )

        for i, error in enumerate(reversed(RECENT_ERRORS[-10:]), 1):
            time_ago = datetime.utcnow() - error["timestamp"]
            if time_ago.total_seconds() < 60:
                time_str = f"{int(time_ago.total_seconds())}s ago"
            elif time_ago.total_seconds() < 3600:
                time_str = f"{int(time_ago.total_seconds() / 60)}m ago"
            else:
                time_str = f"{int(time_ago.total_seconds() / 3600)}h ago"

            # Truncate message
            msg = error["message"]
            if len(msg) > 200:
                msg = msg[:197] + "..."

            embed.add_field(
                name=f"Error {i} ({time_str})",
                value=f"```{msg}```",
                inline=False
            )

        embed.set_footer(text=f"Total errors logged: {len(RECENT_ERRORS)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @system_group.command(name="servers", description="View server statistics breakdown")
    async def system_servers(self, interaction: discord.Interaction):
        """View server breakdown"""
        if not self.is_bot_owner(interaction.user.id):
            await interaction.response.send_message(
                "This command is only available to bot owners.",
                ephemeral=True
            )
            return

        # Sort servers by member count
        servers = sorted(self.bot.guilds, key=lambda g: g.member_count or 0, reverse=True)

        embed = discord.Embed(
            title="🌐 Server Breakdown",
            description=f"**Total Servers:** {len(servers)}",
            color=discord.Color.blue()
        )

        # Top 10 servers
        server_list = []
        for i, guild in enumerate(servers[:10], 1):
            owner = guild.owner.name if guild.owner else "Unknown"
            server_list.append(
                f"**{i}.** {guild.name}\n"
                f"   Members: {guild.member_count:,} | Owner: {owner}"
            )

        embed.add_field(
            name="Top 10 Servers by Members",
            value="\n".join(server_list) if server_list else "No servers",
            inline=False
        )

        # Server size distribution
        small = sum(1 for g in servers if (g.member_count or 0) < 100)
        medium = sum(1 for g in servers if 100 <= (g.member_count or 0) < 1000)
        large = sum(1 for g in servers if (g.member_count or 0) >= 1000)

        embed.add_field(
            name="Size Distribution",
            value=(
                f"**Small (<100):** {small}\n"
                f"**Medium (100-999):** {medium}\n"
                f"**Large (1000+):** {large}"
            ),
            inline=True
        )

        # Total reach
        total_members = sum(g.member_count or 0 for g in servers)
        embed.add_field(
            name="Total Reach",
            value=f"**{total_members:,}** users across all servers",
            inline=True
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @system_group.command(name="clear", description="Clear the error log")
    async def system_clear(self, interaction: discord.Interaction):
        """Clear error logs"""
        if not self.is_bot_owner(interaction.user.id):
            await interaction.response.send_message(
                "This command is only available to bot owners.",
                ephemeral=True
            )
            return

        count = len(RECENT_ERRORS)
        RECENT_ERRORS.clear()

        await interaction.response.send_message(
            f"Cleared {count} error(s) from the log.",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    """Add the System cog to the bot"""
    await bot.add_cog(System(bot))
