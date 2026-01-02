"""
ModTalk Command
Allows moderators to send messages through the bot in any channel
Useful for official announcements and moderator communications

Commands:
- /modtalk - Open the ModTalk interface to send a message as the bot
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
from typing import Optional, List

from utils.logger import log_command, logger
from utils.moderation_logs import log_action, ModAction


# =============================================================================
# STATE TRACKING
# =============================================================================

class ModTalkState:
    """Tracks the current state of a modtalk session"""

    def __init__(self, user_id: int, guild_id: int):
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id: Optional[int] = None
        self.message: Optional[str] = None
        self.include_command: bool = False
        self.command_text: Optional[str] = None


# Store active modtalk states per user
active_modtalks: dict[int, ModTalkState] = {}


# =============================================================================
# MODALS
# =============================================================================

class MessageModal(Modal):
    """Modal for entering the message to send"""

    def __init__(self, state: ModTalkState):
        super().__init__(title="Compose Message")
        self.state = state

        self.message_content = TextInput(
            label="Message",
            placeholder="Enter the message you want the bot to send...",
            required=True,
            max_length=2000,
            style=discord.TextStyle.paragraph
        )

        self.add_item(self.message_content)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.state.message = self.message_content.value

            await interaction.response.edit_message(
                content=get_status_message(self.state),
                view=ModTalkView(self.state)
            )
        except Exception as e:
            logger.error(f"Error in MessageModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in MessageModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass


class CommandModal(Modal):
    """Modal for entering a command prefix to include"""

    def __init__(self, state: ModTalkState):
        super().__init__(title="Add Command Prefix")
        self.state = state

        self.command_input = TextInput(
            label="Command/Prefix",
            placeholder="e.g., !warn, [ANNOUNCEMENT], [IMPORTANT]",
            required=True,
            max_length=100
        )

        self.add_item(self.command_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.state.include_command = True
            self.state.command_text = self.command_input.value

            await interaction.response.edit_message(
                content=get_status_message(self.state),
                view=ModTalkView(self.state)
            )
        except Exception as e:
            logger.error(f"Error in CommandModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in CommandModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass


# =============================================================================
# VIEWS
# =============================================================================

def get_status_message(state: ModTalkState) -> str:
    """Get the current status message"""
    parts = ["**ModTalk - Send Message as Bot**\n"]

    if state.channel_id:
        parts.append(f"**Channel:** <#{state.channel_id}>")
    else:
        parts.append("**Channel:** _Not selected_")

    if state.message:
        preview = state.message[:100] + "..." if len(state.message) > 100 else state.message
        parts.append(f"**Message:** {preview}")
    else:
        parts.append("**Message:** _Not set_")

    if state.include_command and state.command_text:
        parts.append(f"**Prefix:** `{state.command_text}`")

    return "\n".join(parts)


class ChannelSelectView(View):
    """View for selecting a channel"""

    def __init__(self, state: ModTalkState, channels: List[discord.TextChannel]):
        super().__init__(timeout=300)
        self.state = state

        # Create channel dropdown (max 25 options)
        options = []
        for channel in channels[:25]:
            options.append(discord.SelectOption(
                label=f"#{channel.name}"[:100],
                value=str(channel.id),
                description=f"ID: {channel.id}"[:100]
            ))

        if options:
            select = Select(
                placeholder="Select a channel...",
                options=options
            )
            select.callback = self.channel_selected
            self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.user_id:
            await interaction.response.send_message(
                "This isn't your ModTalk session!",
                ephemeral=True
            )
            return False
        return True

    async def channel_selected(self, interaction: discord.Interaction):
        try:
            self.state.channel_id = int(interaction.data["values"][0])

            await interaction.response.edit_message(
                content=get_status_message(self.state),
                view=ModTalkView(self.state)
            )
        except Exception as e:
            logger.error(f"Error selecting channel: {e}")
            await interaction.response.send_message(
                f"Error: {e}",
                ephemeral=True
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if self.state.user_id in active_modtalks:
            del active_modtalks[self.state.user_id]

        await interaction.response.edit_message(
            content="ModTalk cancelled.",
            view=None
        )
        self.stop()


class ModTalkView(View):
    """Main ModTalk view with all options"""

    def __init__(self, state: ModTalkState):
        super().__init__(timeout=300)
        self.state = state

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.user_id:
            await interaction.response.send_message(
                "This isn't your ModTalk session!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Select Channel", style=discord.ButtonStyle.primary, row=0)
    async def select_channel(self, interaction: discord.Interaction, button: Button):
        try:
            # Get all text channels the bot can send to
            guild = interaction.guild
            channels = [
                c for c in guild.text_channels
                if c.permissions_for(guild.me).send_messages
            ]

            if not channels:
                await interaction.response.send_message(
                    "I don't have permission to send messages in any channels!",
                    ephemeral=True
                )
                return

            await interaction.response.edit_message(
                content="**Select a channel to send the message to:**",
                view=ChannelSelectView(self.state, channels)
            )
        except Exception as e:
            logger.error(f"Error in select_channel: {e}")
            await interaction.response.send_message(
                f"Error: {e}",
                ephemeral=True
            )

    @discord.ui.button(label="Write Message", style=discord.ButtonStyle.primary, row=0)
    async def write_message(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.send_modal(MessageModal(self.state))
        except Exception as e:
            logger.error(f"Error opening message modal: {e}")
            await interaction.response.send_message(
                f"Error: {e}",
                ephemeral=True
            )

    @discord.ui.button(label="Add Prefix", style=discord.ButtonStyle.secondary, row=1)
    async def add_command(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.send_modal(CommandModal(self.state))
        except Exception as e:
            logger.error(f"Error opening command modal: {e}")
            await interaction.response.send_message(
                f"Error: {e}",
                ephemeral=True
            )

    @discord.ui.button(label="Remove Prefix", style=discord.ButtonStyle.secondary, row=1)
    async def remove_command(self, interaction: discord.Interaction, button: Button):
        self.state.include_command = False
        self.state.command_text = None

        await interaction.response.edit_message(
            content=get_status_message(self.state),
            view=ModTalkView(self.state)
        )

    @discord.ui.button(label="Preview", style=discord.ButtonStyle.secondary, row=2)
    async def preview(self, interaction: discord.Interaction, button: Button):
        if not self.state.message:
            await interaction.response.send_message(
                "No message to preview! Write a message first.",
                ephemeral=True
            )
            return

        # Build the full message
        full_message = self._build_message()

        await interaction.response.send_message(
            f"**Preview:**\n{full_message}",
            ephemeral=True
        )

    @discord.ui.button(label="Send", style=discord.ButtonStyle.success, row=2)
    async def send_message(self, interaction: discord.Interaction, button: Button):
        # Validate
        if not self.state.channel_id:
            await interaction.response.send_message(
                "Please select a channel first!",
                ephemeral=True
            )
            return

        if not self.state.message:
            await interaction.response.send_message(
                "Please write a message first!",
                ephemeral=True
            )
            return

        try:
            # Get the channel
            channel = interaction.guild.get_channel(self.state.channel_id)
            if not channel:
                await interaction.response.send_message(
                    "Channel not found! It may have been deleted.",
                    ephemeral=True
                )
                return

            # Check permissions
            if not channel.permissions_for(interaction.guild.me).send_messages:
                await interaction.response.send_message(
                    f"I don't have permission to send messages in {channel.mention}!",
                    ephemeral=True
                )
                return

            # Build and send the message
            full_message = self._build_message()
            await channel.send(full_message)

            # Log the action
            logger.info(f"ModTalk: {interaction.user} ({interaction.user.id}) sent message to #{channel.name}")

            # Log to moderation logs
            log_action(
                guild_id=interaction.guild.id,
                moderator_id=interaction.user.id,
                moderator_name=str(interaction.user),
                action=ModAction.MODTALK,
                details={
                    "channel": channel.name,
                    "prefix": self.state.command_text if self.state.include_command else None
                }
            )

            # Cleanup
            if self.state.user_id in active_modtalks:
                del active_modtalks[self.state.user_id]

            await interaction.response.edit_message(
                content=f"Message sent successfully to {channel.mention}!",
                view=None
            )
            self.stop()

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to send messages in that channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error sending modtalk message: {e}")
            await interaction.response.send_message(
                f"Failed to send message: {e}",
                ephemeral=True
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if self.state.user_id in active_modtalks:
            del active_modtalks[self.state.user_id]

        await interaction.response.edit_message(
            content="ModTalk cancelled.",
            view=None
        )
        self.stop()

    def _build_message(self) -> str:
        """Build the full message with optional prefix"""
        if self.state.include_command and self.state.command_text:
            return f"{self.state.command_text} {self.state.message}"
        return self.state.message


# =============================================================================
# COG
# =============================================================================

class ModTalk(commands.Cog):
    """ModTalk command for moderators to communicate through the bot"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="modtalk", description="Send a message as the bot (Moderator only)")
    async def modtalk(self, interaction: discord.Interaction):
        """Open the ModTalk interface"""
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="modtalk",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check for Moderator permissions (Manage Messages or higher)
        has_permission = (
            interaction.user.guild_permissions.manage_messages or
            interaction.user.guild_permissions.manage_guild or
            interaction.user.guild_permissions.administrator
        )

        if not has_permission:
            await interaction.response.send_message(
                "You need **Manage Messages** permission or higher to use this command!",
                ephemeral=True
            )
            return

        # Initialize state
        state = ModTalkState(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id
        )
        active_modtalks[interaction.user.id] = state

        # Show the interface
        embed = discord.Embed(
            title="ModTalk",
            description=(
                "Send messages through the bot as a moderator.\n\n"
                "**How to use:**\n"
                "1. Select the channel to send to\n"
                "2. Write your message\n"
                "3. Optionally add a prefix (like `[ANNOUNCEMENT]`)\n"
                "4. Preview and send!"
            ),
            color=discord.Color.blue()
        )

        await interaction.response.send_message(
            embed=embed,
            view=ModTalkView(state),
            ephemeral=True
        )


# Required setup function
async def setup(bot: commands.Bot):
    """Add the ModTalk cog to the bot"""
    await bot.add_cog(ModTalk(bot))
