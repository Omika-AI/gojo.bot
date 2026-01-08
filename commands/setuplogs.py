"""
Setup Logs Command
Configure event logging for the server
Server Owner only - Creates a webhook in the specified channel for logging

Commands:
- /setuplogs - Set up event logging channel
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.logger import log_command, logger
from utils.event_logs_db import save_guild_config, get_guild_config, EventCategory


class SetupLogs(commands.Cog):
    """Setup event logging for the server"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setuplogs",
        description="Set up event logging channel (Server Owner only)"
    )
    @app_commands.describe(
        channel="The channel where event logs will be sent"
    )
    async def setuplogs(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        """Set up event logging for the server"""
        # Log the command usage
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="setuplogs",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check server owner permission
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the **Server Owner** can set up event logging!",
                ephemeral=True
            )
            return

        # Check bot permissions in the target channel
        bot_permissions = channel.permissions_for(interaction.guild.me)

        if not bot_permissions.manage_webhooks:
            await interaction.response.send_message(
                f"I need **Manage Webhooks** permission in {channel.mention} to set up logging!",
                ephemeral=True
            )
            return

        if not bot_permissions.send_messages:
            await interaction.response.send_message(
                f"I need **Send Messages** permission in {channel.mention}!",
                ephemeral=True
            )
            return

        # Check if logging is already configured
        existing_config = get_guild_config(interaction.guild.id)
        if existing_config:
            await interaction.response.send_message(
                f"Event logging is already configured!\n"
                f"Current log channel: <#{existing_config['channel_id']}>\n\n"
                f"Use `/editlogs` to change the logging channel.",
                ephemeral=True
            )
            return

        # Defer the response since webhook creation might take a moment
        await interaction.response.defer(ephemeral=True)

        try:
            # Create the logging webhook
            webhook = await channel.create_webhook(
                name="Gojo Event Logger",
                reason=f"Event logging setup by {interaction.user}"
            )

            # Save the configuration
            save_guild_config(
                guild_id=interaction.guild.id,
                webhook_id=webhook.id,
                webhook_url=webhook.url,
                channel_id=channel.id,
                configured_by=interaction.user.id
            )

            # Build success embed
            embed = discord.Embed(
                title="Event Logging Configured",
                description=f"Logs will be sent to {channel.mention}",
                color=discord.Color.green()
            )

            # List enabled categories
            categories = [cat.value.capitalize() for cat in EventCategory]
            embed.add_field(
                name="Enabled Categories",
                value="\n".join([f"- {cat}" for cat in categories]),
                inline=False
            )

            embed.add_field(
                name="What Gets Logged",
                value=(
                    "**Messages:** Edits, deletions, bulk deletes\n"
                    "**Members:** Joins, leaves, bans, role/nickname changes\n"
                    "**Voice:** Channel joins, leaves, moves, mutes\n"
                    "**Server:** Channel/role changes"
                ),
                inline=False
            )

            embed.add_field(
                name="Useful Commands",
                value=(
                    "`/editlogs` - Change the log channel\n"
                    "`/searchlogs` - Search through logs"
                ),
                inline=False
            )

            embed.set_footer(text="Logs are kept for 30 days")

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(f"Event logging configured for guild {interaction.guild.id} in channel {channel.id}")

        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to create webhooks in that channel!",
                ephemeral=True
            )
        except discord.HTTPException as e:
            logger.error(f"Failed to create logging webhook: {e}")
            await interaction.followup.send(
                f"Failed to create webhook: {e}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error setting up event logging: {e}")
            await interaction.followup.send(
                f"An error occurred while setting up logging: {e}",
                ephemeral=True
            )


# Required setup function
async def setup(bot: commands.Bot):
    """Add the SetupLogs cog to the bot"""
    await bot.add_cog(SetupLogs(bot))
