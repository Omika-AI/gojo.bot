"""
/clearmessages Command
Bulk delete messages from a channel with optional filters
Owner-only command for server management

Commands:
- /clearmessages amount - Delete x messages from current channel
- /clearmessages amount user - Delete x messages from a specific user
- /clearmessages amount user channel - Delete from a specific channel
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime, timedelta, timezone

from utils.logger import log_command, logger


class ClearMessages(commands.Cog):
    """Bulk message deletion command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="clearmessages",
        description="[Owner] Bulk delete messages from a channel"
    )
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        user="(Optional) Only delete messages from this user",
        channel="(Optional) Delete from a different channel instead"
    )
    async def clearmessages(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
        user: Optional[discord.Member] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        """
        Bulk delete messages from a channel
        Only the server owner can use this command
        """
        # Log command usage
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="clearmessages",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check if user is the server owner
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can use this command!",
                ephemeral=True
            )
            return

        # Determine target channel
        target_channel = channel or interaction.channel

        # Check bot permissions in target channel
        if not target_channel.permissions_for(interaction.guild.me).manage_messages:
            await interaction.response.send_message(
                f"I don't have permission to delete messages in {target_channel.mention}!",
                ephemeral=True
            )
            return

        # Defer response since this might take a moment
        await interaction.response.defer(ephemeral=True)

        try:
            deleted_count = 0

            # Discord only allows bulk delete for messages < 14 days old
            fourteen_days_ago = datetime.now(timezone.utc) - timedelta(days=14)

            if user:
                # Delete messages from specific user
                def check(msg):
                    return msg.author.id == user.id and msg.created_at > fourteen_days_ago

                # Fetch and filter messages
                messages_to_delete = []
                async for message in target_channel.history(limit=500):  # Search through more messages
                    if check(message):
                        messages_to_delete.append(message)
                        if len(messages_to_delete) >= amount:
                            break

                # Bulk delete in chunks of 100
                for i in range(0, len(messages_to_delete), 100):
                    chunk = messages_to_delete[i:i + 100]
                    if len(chunk) == 1:
                        await chunk[0].delete()
                    else:
                        await target_channel.delete_messages(chunk)
                    deleted_count += len(chunk)

            else:
                # Delete any messages (no user filter)
                def check(msg):
                    return msg.created_at > fourteen_days_ago

                # Purge messages
                deleted = await target_channel.purge(limit=amount, check=check)
                deleted_count = len(deleted)

            # Build response
            embed = discord.Embed(
                title="Messages Cleared",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Deleted",
                value=f"**{deleted_count}** message(s)",
                inline=True
            )

            embed.add_field(
                name="Channel",
                value=target_channel.mention,
                inline=True
            )

            if user:
                embed.add_field(
                    name="From User",
                    value=user.mention,
                    inline=True
                )

            embed.set_footer(text=f"Requested by {interaction.user.display_name}")

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Log the action
            logger.info(
                f"[CLEAR] {interaction.user} deleted {deleted_count} messages "
                f"in #{target_channel.name} (guild: {interaction.guild.name})"
                f"{f' from user {user}' if user else ''}"
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to delete messages!",
                ephemeral=True
            )
        except discord.HTTPException as e:
            if "older than 14 days" in str(e):
                await interaction.followup.send(
                    "Some messages couldn't be deleted because they're older than 14 days. "
                    "Discord doesn't allow bulk deletion of messages older than 14 days.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"An error occurred while deleting messages: {e}",
                    ephemeral=True
                )
                logger.error(f"Error in clearmessages: {e}")


async def setup(bot: commands.Bot):
    """Add the ClearMessages cog to the bot"""
    await bot.add_cog(ClearMessages(bot))
