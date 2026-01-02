"""
Webhook Command
Create and send webhook messages with embeds directly from Discord
Administrator only - Step-by-step wizard interface

Commands:
- /webhook - Open the webhook builder wizard
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import aiohttp
import re

from utils.logger import log_command, logger
from utils.webhook_storage import (
    save_webhook,
    get_channel_webhooks,
    get_webhook_url,
    delete_webhook
)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FieldData:
    """Represents an embed field"""
    name: str
    value: str
    inline: bool = False


@dataclass
class EmbedData:
    """Represents a full embed configuration"""
    # Author
    author_name: Optional[str] = None
    author_url: Optional[str] = None
    author_icon_url: Optional[str] = None

    # Body
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    color: Optional[int] = None

    # Fields
    fields: List[FieldData] = field(default_factory=list)

    # Images
    thumbnail_url: Optional[str] = None
    image_url: Optional[str] = None

    # Footer
    footer_text: Optional[str] = None
    footer_icon_url: Optional[str] = None
    timestamp: bool = False

    def to_discord_embed(self) -> discord.Embed:
        """Convert to a Discord Embed object"""
        embed = discord.Embed(
            title=self.title,
            description=self.description,
            url=self.url if self.url else None,
            color=discord.Color(self.color) if self.color else discord.Color.blue()
        )

        if self.author_name:
            embed.set_author(
                name=self.author_name,
                url=self.author_url if self.author_url else None,
                icon_url=self.author_icon_url if self.author_icon_url else None
            )

        for f in self.fields:
            embed.add_field(name=f.name, value=f.value, inline=f.inline)

        # Only set thumbnail if URL is valid and not empty
        if self.thumbnail_url and self.thumbnail_url.strip():
            embed.set_thumbnail(url=self.thumbnail_url)

        # Only set image if URL is valid and not empty
        if self.image_url and self.image_url.strip():
            embed.set_image(url=self.image_url)

        if self.footer_text:
            embed.set_footer(
                text=self.footer_text,
                icon_url=self.footer_icon_url if self.footer_icon_url else None
            )

        if self.timestamp:
            embed.timestamp = datetime.utcnow()

        return embed

    def get_summary(self) -> str:
        """Get a short summary of this embed"""
        parts = []
        if self.title:
            parts.append(f"Title: {self.title[:30]}...")
        elif self.description:
            parts.append(f"Desc: {self.description[:30]}...")
        else:
            parts.append("Empty embed")

        if self.fields:
            parts.append(f"{len(self.fields)} fields")

        return " | ".join(parts)


@dataclass
class WebhookBuilderState:
    """Tracks the current state of the webhook builder for a user"""
    user_id: int
    channel_id: int
    guild_id: int

    # Webhook info
    webhook_url: Optional[str] = None
    webhook_id: Optional[int] = None

    # Profile overrides
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    # Message content
    content: Optional[str] = None
    thread_id: Optional[int] = None

    # Embeds (up to 10)
    embeds: List[EmbedData] = field(default_factory=list)

    # Current embed being edited
    current_embed_index: Optional[int] = None


# Store active builder states per user
active_builders: Dict[int, WebhookBuilderState] = {}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_color(color_str: str) -> Optional[int]:
    """Parse a color string (hex or name) to integer"""
    if not color_str:
        return None

    color_str = color_str.strip().lower()

    # Named colors
    color_names = {
        "red": 0xFF0000,
        "green": 0x00FF00,
        "blue": 0x0000FF,
        "yellow": 0xFFFF00,
        "orange": 0xFFA500,
        "purple": 0x800080,
        "pink": 0xFFC0CB,
        "white": 0xFFFFFF,
        "black": 0x000000,
        "gray": 0x808080,
        "grey": 0x808080,
        "cyan": 0x00FFFF,
        "magenta": 0xFF00FF,
        "gold": 0xFFD700,
        "blurple": 0x5865F2,
    }

    if color_str in color_names:
        return color_names[color_str]

    # Hex color
    if color_str.startswith("#"):
        color_str = color_str[1:]
    if color_str.startswith("0x"):
        color_str = color_str[2:]

    try:
        return int(color_str, 16)
    except ValueError:
        return None


def is_valid_url(url: str) -> bool:
    """Check if a string is a valid URL"""
    if not url:
        return True  # Empty is fine (optional)
    pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return bool(pattern.match(url))


def fix_url(url: str) -> Optional[str]:
    """
    Fix a URL by adding https:// if missing.
    Returns None if empty, the fixed URL otherwise.
    """
    if not url:
        return None

    url = url.strip()

    # If empty after stripping, return None
    if not url:
        return None

    # If it already has a scheme, return as-is
    if url.startswith('http://') or url.startswith('https://'):
        return url

    # If it looks like a domain, add https://
    # Check if it looks like a domain (has a dot and no spaces)
    if '.' in url and ' ' not in url:
        return f"https://{url}"

    # Return None for invalid URLs (no domain pattern)
    return None


# =============================================================================
# MODALS
# =============================================================================

class WebhookCreateModal(Modal):
    """Modal for creating a new webhook"""

    def __init__(self, parent_view: "WebhookSelectView"):
        super().__init__(title="Create New Webhook")
        self.parent_view = parent_view

        self.webhook_name = TextInput(
            label="Webhook Name",
            placeholder="Enter a name for the webhook",
            required=True,
            max_length=80
        )
        self.add_item(self.webhook_name)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Create the webhook in Discord
            channel = interaction.channel
            webhook = await channel.create_webhook(name=self.webhook_name.value)

            # Save to storage
            save_webhook(
                guild_id=interaction.guild.id,
                channel_id=channel.id,
                webhook_id=webhook.id,
                webhook_url=webhook.url,
                webhook_name=webhook.name,
                created_by=interaction.user.id
            )

            # Update the builder state
            state = active_builders.get(interaction.user.id)
            if state:
                state.webhook_url = webhook.url
                state.webhook_id = webhook.id

            # Move to next step
            await interaction.response.edit_message(
                content=f"**Webhook Created:** `{webhook.name}`\n\nNow let's set up your message!",
                embed=None,
                view=WebhookBuilderView(interaction.user.id)
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to create webhooks in this channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to create webhook: {e}")
            await interaction.response.send_message(
                f"Failed to create webhook: {e}",
                ephemeral=True
            )


class ProfileModal(Modal):
    """Modal for setting webhook profile overrides"""

    def __init__(self, state: WebhookBuilderState):
        super().__init__(title="Set Message Profile")
        self.state = state

        self.display_name = TextInput(
            label="Display Name (optional)",
            placeholder="Override the webhook's display name",
            required=False,
            max_length=80,
            default=state.display_name or ""
        )

        self.avatar_url = TextInput(
            label="Avatar URL (optional)",
            placeholder="https://example.com/avatar.png",
            required=False,
            max_length=500,
            default=state.avatar_url or ""
        )

        self.add_item(self.display_name)
        self.add_item(self.avatar_url)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.state.display_name = self.display_name.value or None
            # Fix URL by adding https:// if missing
            self.state.avatar_url = fix_url(self.avatar_url.value)

            await interaction.response.edit_message(
                content=self._get_status_message(),
                view=WebhookBuilderView(interaction.user.id)
            )
        except Exception as e:
            logger.error(f"Error in ProfileModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in ProfileModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass

    def _get_status_message(self) -> str:
        parts = ["**Webhook Message Builder**\n"]

        if self.state.display_name:
            parts.append(f"**Name:** {self.state.display_name}")
        if self.state.avatar_url:
            parts.append(f"**Avatar:** Set")
        if self.state.content:
            parts.append(f"**Content:** {self.state.content[:50]}...")
        if self.state.embeds:
            parts.append(f"**Embeds:** {len(self.state.embeds)}")

        return "\n".join(parts)


class ContentModal(Modal):
    """Modal for setting message content"""

    def __init__(self, state: WebhookBuilderState):
        super().__init__(title="Set Message Content")
        self.state = state

        self.content = TextInput(
            label="Message Content",
            placeholder="Enter your message text (optional if using embeds)",
            required=False,
            max_length=2000,
            style=discord.TextStyle.paragraph,
            default=state.content or ""
        )

        self.thread_id = TextInput(
            label="Thread ID (optional)",
            placeholder="Enter thread ID to send to a specific thread",
            required=False,
            max_length=20,
            default=str(state.thread_id) if state.thread_id else ""
        )

        self.add_item(self.content)
        self.add_item(self.thread_id)

    async def on_submit(self, interaction: discord.Interaction):
        self.state.content = self.content.value or None

        # Parse thread ID
        if self.thread_id.value:
            try:
                self.state.thread_id = int(self.thread_id.value)
            except ValueError:
                await interaction.response.send_message(
                    "Invalid thread ID! Please enter a valid number.",
                    ephemeral=True
                )
                return
        else:
            self.state.thread_id = None

        await interaction.response.edit_message(
            content=get_builder_status(self.state),
            view=WebhookBuilderView(interaction.user.id)
        )


class EmbedAuthorModal(Modal):
    """Modal for setting embed author"""

    def __init__(self, state: WebhookBuilderState, embed_index: int):
        super().__init__(title=f"Embed {embed_index + 1} - Author")
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        self.author_name = TextInput(
            label="Author Name",
            placeholder="Name displayed in the author section",
            required=False,
            max_length=256,
            default=self.embed.author_name or ""
        )

        self.author_url = TextInput(
            label="Author URL (optional)",
            placeholder="https://example.com",
            required=False,
            max_length=500,
            default=self.embed.author_url or ""
        )

        self.author_icon = TextInput(
            label="Author Icon URL (optional)",
            placeholder="https://example.com/icon.png",
            required=False,
            max_length=500,
            default=self.embed.author_icon_url or ""
        )

        self.add_item(self.author_name)
        self.add_item(self.author_url)
        self.add_item(self.author_icon)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.embed.author_name = self.author_name.value or None
            # Fix URLs by adding https:// if missing
            self.embed.author_url = fix_url(self.author_url.value)
            self.embed.author_icon_url = fix_url(self.author_icon.value)

            await interaction.response.edit_message(
                content=f"**Editing Embed {self.embed_index + 1}**\n{self.embed.get_summary()}",
                view=EmbedBuilderView(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error in EmbedAuthorModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in EmbedAuthorModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass


class EmbedBodyModal(Modal):
    """Modal for setting embed title, description, color"""

    def __init__(self, state: WebhookBuilderState, embed_index: int):
        super().__init__(title=f"Embed {embed_index + 1} - Body")
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        self.title = TextInput(
            label="Title",
            placeholder="Embed title",
            required=False,
            max_length=256,
            default=self.embed.title or ""
        )

        self.description = TextInput(
            label="Description",
            placeholder="Main embed text",
            required=False,
            max_length=4000,
            style=discord.TextStyle.paragraph,
            default=self.embed.description or ""
        )

        self.url = TextInput(
            label="Title URL (optional)",
            placeholder="https://example.com",
            required=False,
            max_length=500,
            default=self.embed.url or ""
        )

        self.color = TextInput(
            label="Color (hex or name)",
            placeholder="e.g., #FF0000 or red, blue, green",
            required=False,
            max_length=20,
            default=f"#{self.embed.color:06X}" if self.embed.color else ""
        )

        self.add_item(self.title)
        self.add_item(self.description)
        self.add_item(self.url)
        self.add_item(self.color)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.embed.title = self.title.value or None
            self.embed.description = self.description.value or None
            # Fix URL by adding https:// if missing
            self.embed.url = fix_url(self.url.value)
            self.embed.color = parse_color(self.color.value)

            await interaction.response.edit_message(
                content=f"**Editing Embed {self.embed_index + 1}**\n{self.embed.get_summary()}",
                view=EmbedBuilderView(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error in EmbedBodyModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in EmbedBodyModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass


class EmbedFieldModal(Modal):
    """Modal for adding a field to an embed"""

    def __init__(self, state: WebhookBuilderState, embed_index: int):
        super().__init__(title=f"Add Field to Embed {embed_index + 1}")
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        self.field_name = TextInput(
            label="Field Name",
            placeholder="Name/title of the field",
            required=True,
            max_length=256
        )

        self.field_value = TextInput(
            label="Field Value",
            placeholder="Content of the field",
            required=True,
            max_length=1024,
            style=discord.TextStyle.paragraph
        )

        self.inline = TextInput(
            label="Inline? (yes/no)",
            placeholder="yes or no - display fields side by side",
            required=False,
            max_length=3,
            default="no"
        )

        self.add_item(self.field_name)
        self.add_item(self.field_value)
        self.add_item(self.inline)

    async def on_submit(self, interaction: discord.Interaction):
        if len(self.embed.fields) >= 25:
            await interaction.response.send_message(
                "Maximum 25 fields per embed!",
                ephemeral=True
            )
            return

        inline = self.inline.value.lower() in ("yes", "y", "true", "1")

        self.embed.fields.append(FieldData(
            name=self.field_name.value,
            value=self.field_value.value,
            inline=inline
        ))

        await interaction.response.edit_message(
            content=f"**Editing Embed {self.embed_index + 1}**\nFields: {len(self.embed.fields)}",
            view=EmbedBuilderView(self.state, self.embed_index)
        )


class EmbedImagesModal(Modal):
    """Modal for setting embed images"""

    def __init__(self, state: WebhookBuilderState, embed_index: int):
        super().__init__(title=f"Embed {embed_index + 1} - Images")
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        self.thumbnail = TextInput(
            label="Thumbnail URL",
            placeholder="Small image in top-right corner",
            required=False,
            max_length=500,
            default=self.embed.thumbnail_url or ""
        )

        self.image = TextInput(
            label="Image URL",
            placeholder="Large image at bottom of embed",
            required=False,
            max_length=500,
            default=self.embed.image_url or ""
        )

        self.add_item(self.thumbnail)
        self.add_item(self.image)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Fix URLs by adding https:// if missing
            thumbnail_fixed = fix_url(self.thumbnail.value)
            image_fixed = fix_url(self.image.value)

            # Log for debugging
            logger.info(f"Images modal - Thumbnail input: '{self.thumbnail.value}' -> Fixed: '{thumbnail_fixed}'")
            logger.info(f"Images modal - Image input: '{self.image.value}' -> Fixed: '{image_fixed}'")

            self.embed.thumbnail_url = thumbnail_fixed
            self.embed.image_url = image_fixed

            # Show confirmation of what was set
            status_parts = [f"**Editing Embed {self.embed_index + 1}**"]
            if thumbnail_fixed:
                status_parts.append(f"Thumbnail: Set")
            if image_fixed:
                status_parts.append(f"Image: Set")
            if not thumbnail_fixed and not image_fixed:
                status_parts.append("No images set")

            await interaction.response.edit_message(
                content="\n".join(status_parts),
                view=EmbedBuilderView(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error in EmbedImagesModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in EmbedImagesModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass


class EmbedFooterModal(Modal):
    """Modal for setting embed footer"""

    def __init__(self, state: WebhookBuilderState, embed_index: int):
        super().__init__(title=f"Embed {embed_index + 1} - Footer")
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        self.footer_text = TextInput(
            label="Footer Text",
            placeholder="Text displayed at the bottom",
            required=False,
            max_length=2048,
            default=self.embed.footer_text or ""
        )

        self.footer_icon = TextInput(
            label="Footer Icon URL (optional)",
            placeholder="https://example.com/icon.png",
            required=False,
            max_length=500,
            default=self.embed.footer_icon_url or ""
        )

        self.timestamp = TextInput(
            label="Add Timestamp? (yes/no)",
            placeholder="yes or no - adds current time to footer",
            required=False,
            max_length=3,
            default="yes" if self.embed.timestamp else "no"
        )

        self.add_item(self.footer_text)
        self.add_item(self.footer_icon)
        self.add_item(self.timestamp)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.embed.footer_text = self.footer_text.value or None
            # Fix URL by adding https:// if missing
            self.embed.footer_icon_url = fix_url(self.footer_icon.value)
            self.embed.timestamp = self.timestamp.value.lower() in ("yes", "y", "true", "1")

            await interaction.response.edit_message(
                content=f"**Editing Embed {self.embed_index + 1}**\n{self.embed.get_summary()}",
                view=EmbedBuilderView(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error in EmbedFooterModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in EmbedFooterModal: {error}")
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

def get_builder_status(state: WebhookBuilderState) -> str:
    """Get the current status message for the builder"""
    parts = ["**Webhook Message Builder**\n"]

    if state.display_name:
        parts.append(f"**Name:** {state.display_name}")
    if state.avatar_url:
        parts.append("**Avatar:** Set")
    if state.content:
        preview = state.content[:100] + "..." if len(state.content) > 100 else state.content
        parts.append(f"**Content:** {preview}")
    if state.embeds:
        parts.append(f"**Embeds:** {len(state.embeds)}")
    if state.thread_id:
        parts.append(f"**Thread:** {state.thread_id}")

    if len(parts) == 1:
        parts.append("_No content set yet. Use the buttons below to build your message._")

    return "\n".join(parts)


class WebhookSelectView(View):
    """View for selecting or creating a webhook"""

    def __init__(self, user_id: int, channel: discord.TextChannel):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.channel = channel

        # Get existing webhooks
        webhooks = get_channel_webhooks(channel.guild.id, channel.id)

        if webhooks:
            # Add dropdown for existing webhooks
            options = [
                discord.SelectOption(
                    label=w["name"][:100],
                    value=str(w["id"]),
                    description=f"Created by user {w['created_by']}"
                )
                for w in webhooks[:25]  # Max 25 options
            ]

            select = Select(
                placeholder="Select an existing webhook...",
                options=options,
                custom_id="webhook_select"
            )
            select.callback = self.webhook_selected
            self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your webhook builder!",
                ephemeral=True
            )
            return False
        return True

    async def webhook_selected(self, interaction: discord.Interaction):
        """Handle webhook selection from dropdown"""
        webhook_id = int(interaction.data["values"][0])
        state = active_builders.get(self.user_id)

        if state:
            webhook_url = get_webhook_url(state.guild_id, state.channel_id, webhook_id)
            if webhook_url:
                state.webhook_url = webhook_url
                state.webhook_id = webhook_id

                await interaction.response.edit_message(
                    content="**Webhook selected!**\n\nNow let's set up your message.",
                    embed=None,
                    view=WebhookBuilderView(self.user_id)
                )
            else:
                await interaction.response.send_message(
                    "Webhook not found! It may have been deleted.",
                    ephemeral=True
                )

    @discord.ui.button(label="Create New Webhook", style=discord.ButtonStyle.success, row=1)
    async def create_new(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(WebhookCreateModal(self))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if self.user_id in active_builders:
            del active_builders[self.user_id]

        await interaction.response.edit_message(
            content="Webhook builder cancelled.",
            embed=None,
            view=None
        )
        self.stop()


class WebhookBuilderView(View):
    """Main webhook builder navigation view"""

    def __init__(self, user_id: int):
        super().__init__(timeout=600)  # 10 minute timeout
        self.user_id = user_id
        self.state = active_builders.get(user_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your webhook builder!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Set Profile", style=discord.ButtonStyle.secondary, row=0)
    async def set_profile(self, interaction: discord.Interaction, button: Button):
        if self.state:
            await interaction.response.send_modal(ProfileModal(self.state))

    @discord.ui.button(label="Set Content", style=discord.ButtonStyle.secondary, row=0)
    async def set_content(self, interaction: discord.Interaction, button: Button):
        if self.state:
            await interaction.response.send_modal(ContentModal(self.state))

    @discord.ui.button(label="Add Embed", style=discord.ButtonStyle.primary, row=0)
    async def add_embed(self, interaction: discord.Interaction, button: Button):
        if not self.state:
            return

        if len(self.state.embeds) >= 10:
            await interaction.response.send_message(
                "Maximum 10 embeds per message!",
                ephemeral=True
            )
            return

        # Create new embed and open builder
        self.state.embeds.append(EmbedData())
        embed_index = len(self.state.embeds) - 1

        await interaction.response.edit_message(
            content=f"**Creating Embed {embed_index + 1}**\n\nUse the buttons below to configure this embed.",
            view=EmbedBuilderView(self.state, embed_index)
        )

    @discord.ui.button(label="View Embeds", style=discord.ButtonStyle.secondary, row=1)
    async def view_embeds(self, interaction: discord.Interaction, button: Button):
        if not self.state or not self.state.embeds:
            await interaction.response.send_message(
                "No embeds added yet! Click 'Add Embed' to create one.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Current Embeds",
            color=discord.Color.blue()
        )

        for i, e in enumerate(self.state.embeds):
            embed.add_field(
                name=f"Embed {i + 1}",
                value=e.get_summary(),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Edit Embed", style=discord.ButtonStyle.secondary, row=1)
    async def edit_embed(self, interaction: discord.Interaction, button: Button):
        if not self.state or not self.state.embeds:
            await interaction.response.send_message(
                "No embeds to edit! Add one first.",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content="**Select an embed to edit:**",
            view=EmbedSelectView(self.state, "edit")
        )

    @discord.ui.button(label="Remove Embed", style=discord.ButtonStyle.danger, row=1)
    async def remove_embed(self, interaction: discord.Interaction, button: Button):
        if not self.state or not self.state.embeds:
            await interaction.response.send_message(
                "No embeds to remove!",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content="**Select an embed to remove:**",
            view=EmbedSelectView(self.state, "remove")
        )

    @discord.ui.button(label="Preview & Send", style=discord.ButtonStyle.success, row=2)
    async def preview_send(self, interaction: discord.Interaction, button: Button):
        if not self.state:
            return

        # Check we have content
        if not self.state.content and not self.state.embeds:
            await interaction.response.send_message(
                "Please add some content or at least one embed before sending!",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content="**Preview your message:**",
            view=ReviewView(self.state)
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=2)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if self.user_id in active_builders:
            del active_builders[self.user_id]

        await interaction.response.edit_message(
            content="Webhook builder cancelled.",
            embed=None,
            view=None
        )
        self.stop()


class EmbedSelectView(View):
    """View for selecting which embed to edit or remove"""

    def __init__(self, state: WebhookBuilderState, action: str):
        super().__init__(timeout=120)
        self.state = state
        self.action = action  # "edit" or "remove"

        # Create dropdown with embeds
        options = [
            discord.SelectOption(
                label=f"Embed {i + 1}",
                value=str(i),
                description=e.get_summary()[:100]
            )
            for i, e in enumerate(state.embeds)
        ]

        select = Select(
            placeholder=f"Select embed to {action}...",
            options=options
        )
        select.callback = self.embed_selected
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.user_id:
            await interaction.response.send_message(
                "This isn't your webhook builder!",
                ephemeral=True
            )
            return False
        return True

    async def embed_selected(self, interaction: discord.Interaction):
        embed_index = int(interaction.data["values"][0])

        if self.action == "edit":
            await interaction.response.edit_message(
                content=f"**Editing Embed {embed_index + 1}**",
                view=EmbedBuilderView(self.state, embed_index)
            )
        elif self.action == "remove":
            self.state.embeds.pop(embed_index)
            await interaction.response.edit_message(
                content=get_builder_status(self.state),
                view=WebhookBuilderView(self.state.user_id)
            )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content=get_builder_status(self.state),
            view=WebhookBuilderView(self.state.user_id)
        )


class EmbedBuilderView(View):
    """View for building a single embed"""

    def __init__(self, state: WebhookBuilderState, embed_index: int):
        super().__init__(timeout=300)
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.user_id:
            await interaction.response.send_message(
                "This isn't your webhook builder!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Author", style=discord.ButtonStyle.secondary, row=0)
    async def set_author(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.send_modal(
                EmbedAuthorModal(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error opening Author modal: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Body", style=discord.ButtonStyle.secondary, row=0)
    async def set_body(self, interaction: discord.Interaction, button: Button):
        try:
            # Ensure embed exists and get fresh reference
            if self.embed_index >= len(self.state.embeds):
                await interaction.response.send_message(
                    "Embed no longer exists! Please go back and try again.",
                    ephemeral=True
                )
                return
            await interaction.response.send_modal(
                EmbedBodyModal(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error opening Body modal: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.primary, row=0)
    async def add_field(self, interaction: discord.Interaction, button: Button):
        try:
            if len(self.embed.fields) >= 25:
                await interaction.response.send_message(
                    "Maximum 25 fields per embed!",
                    ephemeral=True
                )
                return
            await interaction.response.send_modal(
                EmbedFieldModal(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error opening Field modal: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Images", style=discord.ButtonStyle.secondary, row=1)
    async def set_images(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.send_modal(
                EmbedImagesModal(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error opening Images modal: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="Footer", style=discord.ButtonStyle.secondary, row=1)
    async def set_footer(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.send_modal(
                EmbedFooterModal(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error opening Footer modal: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @discord.ui.button(label="View Fields", style=discord.ButtonStyle.secondary, row=1)
    async def view_fields(self, interaction: discord.Interaction, button: Button):
        if not self.embed.fields:
            await interaction.response.send_message(
                "No fields added yet!",
                ephemeral=True
            )
            return

        embed = discord.Embed(title=f"Embed {self.embed_index + 1} Fields", color=discord.Color.blue())
        for i, f in enumerate(self.embed.fields):
            embed.add_field(
                name=f"Field {i + 1}: {f.name[:50]}",
                value=f"Value: {f.value[:100]}...\nInline: {f.inline}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Remove Field", style=discord.ButtonStyle.danger, row=2)
    async def remove_field(self, interaction: discord.Interaction, button: Button):
        if not self.embed.fields:
            await interaction.response.send_message(
                "No fields to remove!",
                ephemeral=True
            )
            return

        await interaction.response.edit_message(
            content=f"**Select a field to remove from Embed {self.embed_index + 1}:**",
            view=FieldSelectView(self.state, self.embed_index)
        )

    @discord.ui.button(label="Preview Embed", style=discord.ButtonStyle.primary, row=2)
    async def preview_embed(self, interaction: discord.Interaction, button: Button):
        try:
            preview = self.embed.to_discord_embed()
            await interaction.response.send_message(embed=preview, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"Error creating preview: {e}",
                ephemeral=True
            )

    @discord.ui.button(label="Done", style=discord.ButtonStyle.success, row=2)
    async def done(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content=get_builder_status(self.state),
            view=WebhookBuilderView(self.state.user_id)
        )


class FieldSelectView(View):
    """View for selecting a field to remove"""

    def __init__(self, state: WebhookBuilderState, embed_index: int):
        super().__init__(timeout=120)
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        options = [
            discord.SelectOption(
                label=f"Field {i + 1}: {f.name[:50]}",
                value=str(i),
                description=f.value[:100]
            )
            for i, f in enumerate(self.embed.fields)
        ]

        select = Select(placeholder="Select field to remove...", options=options)
        select.callback = self.field_selected
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.user_id:
            await interaction.response.send_message(
                "This isn't your webhook builder!",
                ephemeral=True
            )
            return False
        return True

    async def field_selected(self, interaction: discord.Interaction):
        field_index = int(interaction.data["values"][0])
        self.embed.fields.pop(field_index)

        await interaction.response.edit_message(
            content=f"**Editing Embed {self.embed_index + 1}**\nFields: {len(self.embed.fields)}",
            view=EmbedBuilderView(self.state, self.embed_index)
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content=f"**Editing Embed {self.embed_index + 1}**",
            view=EmbedBuilderView(self.state, self.embed_index)
        )


class ReviewView(View):
    """View for reviewing and sending the webhook message"""

    def __init__(self, state: WebhookBuilderState):
        super().__init__(timeout=300)
        self.state = state

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.user_id:
            await interaction.response.send_message(
                "This isn't your webhook builder!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Show Preview", style=discord.ButtonStyle.primary, row=0)
    async def show_preview(self, interaction: discord.Interaction, button: Button):
        embeds = [e.to_discord_embed() for e in self.state.embeds]

        preview_text = "**Preview:**\n"
        if self.state.display_name:
            preview_text += f"**From:** {self.state.display_name}\n"
        if self.state.content:
            preview_text += f"\n{self.state.content}"

        await interaction.response.send_message(
            content=preview_text if self.state.content or self.state.display_name else "Preview:",
            embeds=embeds[:10] if embeds else [],
            ephemeral=True
        )

    @discord.ui.button(label="Send Message", style=discord.ButtonStyle.success, row=0)
    async def send_message(self, interaction: discord.Interaction, button: Button):
        if not self.state.webhook_url:
            await interaction.response.send_message(
                "No webhook selected!",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Build embeds
            embeds = [e.to_discord_embed() for e in self.state.embeds]

            # Send via webhook
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(
                    self.state.webhook_url,
                    session=session
                )

                await webhook.send(
                    content=self.state.content,
                    username=self.state.display_name,
                    avatar_url=self.state.avatar_url,
                    embeds=embeds[:10] if embeds else discord.utils.MISSING,
                    thread=discord.Object(id=self.state.thread_id) if self.state.thread_id else discord.utils.MISSING
                )

            # Cleanup
            if self.state.user_id in active_builders:
                del active_builders[self.state.user_id]

            await interaction.followup.send(
                "Message sent successfully!",
                ephemeral=True
            )

            # Update the original message
            await interaction.edit_original_response(
                content="Webhook message sent!",
                view=None
            )

        except discord.NotFound:
            await interaction.followup.send(
                "Webhook not found! It may have been deleted.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to send webhook message: {e}")
            await interaction.followup.send(
                f"Failed to send message: {e}",
                ephemeral=True
            )

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, row=0)
    async def edit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content=get_builder_status(self.state),
            view=WebhookBuilderView(self.state.user_id)
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if self.state.user_id in active_builders:
            del active_builders[self.state.user_id]

        await interaction.response.edit_message(
            content="Webhook builder cancelled.",
            embed=None,
            view=None
        )
        self.stop()


# =============================================================================
# COG
# =============================================================================

class Webhook(commands.Cog):
    """Webhook management commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="webhook", description="Create and send webhook messages (Admin only)")
    async def webhook(self, interaction: discord.Interaction):
        """Open the webhook builder wizard"""
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="webhook",
            guild=interaction.guild.name if interaction.guild else None
        )

        # Check if in a server
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check for Administrator permission
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need **Administrator** permission to use this command!",
                ephemeral=True
            )
            return

        # Check bot permissions
        if not interaction.guild.me.guild_permissions.manage_webhooks:
            await interaction.response.send_message(
                "I need **Manage Webhooks** permission to use this command!",
                ephemeral=True
            )
            return

        # Initialize builder state
        state = WebhookBuilderState(
            user_id=interaction.user.id,
            channel_id=interaction.channel.id,
            guild_id=interaction.guild.id
        )
        active_builders[interaction.user.id] = state

        # Check for existing webhooks
        webhooks = get_channel_webhooks(interaction.guild.id, interaction.channel.id)

        embed = discord.Embed(
            title="Webhook Message Builder",
            description=(
                "Create and send custom webhook messages with embeds!\n\n"
                "**Step 1:** Select an existing webhook or create a new one.\n"
                "**Step 2:** Configure your message content and profile.\n"
                "**Step 3:** Add embeds with custom formatting.\n"
                "**Step 4:** Preview and send!"
            ),
            color=discord.Color.blue()
        )

        if webhooks:
            embed.add_field(
                name="Existing Webhooks",
                value=f"Found {len(webhooks)} webhook(s) in this channel.",
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            view=WebhookSelectView(interaction.user.id, interaction.channel),
            ephemeral=True
        )


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Webhook cog to the bot"""
    await bot.add_cog(Webhook(bot))
