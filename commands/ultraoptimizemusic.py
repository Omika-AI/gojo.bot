"""
Ultra Optimize Music Command
Admin-only command to enable ultra audio optimization mode for the server.

Ultra mode provides:
- Maximum audio quality settings
- Enhanced buffering to prevent micro-stutters
- Multi-threaded audio processing
- Higher quality resampling

This is recommended for:
- Servers with good internet connections
- Discord boosted servers (higher bitrate limits)
- Users who prioritize audio quality over latency
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.logger import log_command, logger
from utils.audio_optimization import (
    set_ultra_mode,
    is_ultra_mode_enabled,
    get_optimization_status,
    AUDIO_OPTIMIZATION_ENABLED
)


class UltraOptimizeMusic(commands.Cog):
    """Admin command to toggle ultra audio optimization"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ultraoptimizemusic",
        description="Toggle ultra audio quality mode (Admin only)"
    )
    @app_commands.describe(
        enable="Enable or disable ultra optimization (leave empty to toggle)"
    )
    async def ultraoptimizemusic(
        self,
        interaction: discord.Interaction,
        enable: bool = None
    ):
        """
        Toggle ultra audio optimization mode for this server.
        Only administrators can use this command.
        """
        log_command(
            str(interaction.user),
            interaction.user.id,
            f"ultraoptimizemusic {enable}",
            interaction.guild.name
        )

        # Check if user is administrator
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need **Administrator** permission to use this command!",
                ephemeral=True
            )
            return

        # Check if base optimization is enabled
        if not AUDIO_OPTIMIZATION_ENABLED:
            await interaction.response.send_message(
                "Audio optimization is currently disabled globally.\n"
                "Contact the bot developer to enable it.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild.id
        current_status = is_ultra_mode_enabled(guild_id)

        # Determine new status
        if enable is None:
            # Toggle mode
            new_status = not current_status
        else:
            new_status = enable

        # Set the new status
        set_ultra_mode(guild_id, new_status)

        # Get detailed status for embed
        status_info = get_optimization_status(guild_id)

        # Create response embed
        if new_status:
            embed = discord.Embed(
                title="Ultra Audio Mode Enabled",
                description=(
                    "Maximum audio quality mode is now **active** for this server.\n\n"
                    "**What this does:**\n"
                    "- Prefers Opus codec (Discord native) for zero re-encoding\n"
                    "- Enhanced input buffering (prevents audio stutters)\n"
                    "- Multi-threaded audio processing\n"
                    "- High-quality dithering for smoother audio\n"
                    "- Larger analysis buffers for better format detection\n\n"
                    "**Best for:** Boosted servers, high-quality music listening sessions"
                ),
                color=discord.Color.gold()
            )
            embed.add_field(
                name="Note",
                value=(
                    "Ultra mode may slightly increase song load times but provides "
                    "noticeably smoother playback. If you experience issues, "
                    "run this command again to disable it."
                ),
                inline=False
            )
        else:
            embed = discord.Embed(
                title="Ultra Audio Mode Disabled",
                description=(
                    "Switched back to **standard optimized** audio mode.\n\n"
                    "Standard mode still includes:\n"
                    "- Opus/AAC codec preference\n"
                    "- Async resampling for smooth playback\n"
                    "- Auto-reconnection on network issues\n"
                    "- 48kHz/Stereo output (Discord native)"
                ),
                color=discord.Color.blue()
            )

        embed.set_footer(text=f"Mode: {status_info['mode'].title()}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="audiostatus",
        description="Check current audio optimization status"
    )
    async def audiostatus(self, interaction: discord.Interaction):
        """Show current audio optimization settings for this server"""
        log_command(
            str(interaction.user),
            interaction.user.id,
            "audiostatus",
            interaction.guild.name
        )

        guild_id = interaction.guild.id
        status = get_optimization_status(guild_id)

        # Create status embed
        embed = discord.Embed(
            title="Audio Optimization Status",
            description=status['description'],
            color=discord.Color.gold() if status['mode'] == 'ultra'
                  else discord.Color.green() if status['enabled']
                  else discord.Color.grey()
        )

        # Features list
        features = status['features']
        feature_text = ""
        feature_text += f"{'Enabled' if features['opus_passthrough'] else 'Disabled'} - Opus Passthrough\n"
        feature_text += f"{'Enabled' if features['async_resampling'] else 'Disabled'} - Async Resampling\n"
        feature_text += f"{'Enabled' if features['enhanced_buffering'] else 'Disabled'} - Enhanced Buffering\n"
        feature_text += f"{'Enabled' if features['multi_threaded_filters'] else 'Disabled'} - Multi-threaded Filters\n"

        embed.add_field(name="Features", value=f"```\n{feature_text}```", inline=False)

        # Mode explanation
        if status['mode'] == 'ultra':
            embed.add_field(
                name="Ultra Mode",
                value="Maximum quality settings are active. Use `/ultraoptimizemusic` to disable.",
                inline=False
            )
        elif status['mode'] == 'optimized':
            embed.add_field(
                name="Standard Optimized",
                value="Balanced quality and performance. Admins can use `/ultraoptimizemusic` to enable ultra mode.",
                inline=False
            )
        else:
            embed.add_field(
                name="Basic Mode",
                value="Optimization is disabled globally.",
                inline=False
            )

        embed.set_footer(text=f"Server: {interaction.guild.name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


# Required setup function
async def setup(bot: commands.Bot):
    """Add the UltraOptimizeMusic cog to the bot"""
    await bot.add_cog(UltraOptimizeMusic(bot))
