"""
Edit Logs Command
Change the event logging channel
Server Owner only - Deletes old webhook and creates new one in specified channel

Commands:
- /editlogs - Change the logging channel
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.logger import log_command, logger
from utils.event_logs_db import save_guild_config, get_guild_config, delete_guild_config


class EditLogs(commands.Cog):
    """Edit event logging configuration"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="editlogs",
        description="Change the event logging channel (Server Owner only)"
    )
    @app_commands.describe(
        channel="The new channel where event logs will be sent"
    )
    async def editlogs(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        """Change the event logging channel"""
        # Log the command usage
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="editlogs",
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
                "Only the **Server Owner** can edit event logging settings!",
                ephemeral=True
            )
            return

        # Check if logging is configured
        existing_config = get_guild_config(interaction.guild.id)
        if not existing_config:
            await interaction.response.send_message(
                "Event logging is not set up yet!\n"
                "Use `/setuplogs` to configure logging first.",
                ephemeral=True
            )
            return

        # Check if it's the same channel
        if str(channel.id) == existing_config.get("channel_id"):
            await interaction.response.send_message(
                f"Logs are already being sent to {channel.mention}!",
                ephemeral=True
            )
            return

        # Check bot permissions in the new channel
        bot_permissions = channel.permissions_for(interaction.guild.me)

        if not bot_permissions.manage_webhooks:
            await interaction.response.send_message(
                f"I need **Manage Webhooks** permission in {channel.mention}!",
                ephemeral=True
            )
            return

        if not bot_permissions.send_messages:
            await interaction.response.send_message(
                f"I need **Send Messages** permission in {channel.mention}!",
                ephemeral=True
            )
            return

        # Defer the response since this might take a moment
        await interaction.response.defer(ephemeral=True)

        old_channel_id = existing_config.get("channel_id")
        old_webhook_id = existing_config.get("webhook_id")

        try:
            # Try to delete the old webhook
            if old_webhook_id:
                try:
                    old_channel = interaction.guild.get_channel(int(old_channel_id))
                    if old_channel:
                        webhooks = await old_channel.webhooks()
                        for webhook in webhooks:
                            if str(webhook.id) == old_webhook_id:
                                await webhook.delete(reason="Logging channel changed")
                                logger.info(f"Deleted old logging webhook {old_webhook_id}")
                                break
                except Exception as e:
                    # Log but continue - old webhook might already be deleted
                    logger.warning(f"Could not delete old webhook: {e}")

            # Create new webhook in the new channel
            new_webhook = await channel.create_webhook(
                name="Gojo Event Logger",
                reason=f"Event logging channel changed by {interaction.user}"
            )

            # Update the configuration
            save_guild_config(
                guild_id=interaction.guild.id,
                webhook_id=new_webhook.id,
                webhook_url=new_webhook.url,
                channel_id=channel.id,
                configured_by=interaction.user.id,
                enabled_categories=existing_config.get("enabled_categories")
            )

            # Build success embed
            embed = discord.Embed(
                title="Logging Channel Updated",
                description=f"Event logs will now be sent to {channel.mention}",
                color=discord.Color.green()
            )

            if old_channel_id:
                embed.add_field(
                    name="Previous Channel",
                    value=f"<#{old_channel_id}>",
                    inline=True
                )

            embed.add_field(
                name="New Channel",
                value=channel.mention,
                inline=True
            )

            embed.set_footer(text="All future events will be logged to the new channel")

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(f"Event logging channel changed for guild {interaction.guild.id} to {channel.id}")

        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to create webhooks in that channel!",
                ephemeral=True
            )
        except discord.HTTPException as e:
            logger.error(f"Failed to create logging webhook: {e}")
            await interaction.followup.send(
                f"Failed to update logging channel: {e}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error updating event logging: {e}")
            await interaction.followup.send(
                f"An error occurred while updating logging: {e}",
                ephemeral=True
            )


# Required setup function
async def setup(bot: commands.Bot):
    """Add the EditLogs cog to the bot"""
    await bot.add_cog(EditLogs(bot))
