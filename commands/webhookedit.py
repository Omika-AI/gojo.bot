"""
Webhook Edit Command
Edit existing webhook messages using a dropdown menu interface
Administrator only

Commands:
- /webhookedit <message_link> - Edit an existing webhook message
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
from typing import Optional, List, Dict
import re
import aiohttp

from utils.logger import log_command, logger

# Import shared classes from webhook.py
from commands.webhook import (
    EmbedData,
    FieldData,
    parse_color,
    is_valid_url,
    fix_url
)


# =============================================================================
# MESSAGE LINK PARSER
# =============================================================================

def parse_message_link(link: str) -> Optional[Dict[str, int]]:
    """
    Parse a Discord message link into guild_id, channel_id, message_id

    Formats:
    - https://discord.com/channels/123/456/789
    - https://discordapp.com/channels/123/456/789
    - https://canary.discord.com/channels/123/456/789
    - https://ptb.discord.com/channels/123/456/789

    Returns:
        Dict with guild_id, channel_id, message_id or None if invalid
    """
    pattern = r'https?://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)'
    match = re.match(pattern, link)

    if match:
        return {
            "guild_id": int(match.group(1)),
            "channel_id": int(match.group(2)),
            "message_id": int(match.group(3))
        }

    return None


# =============================================================================
# EDIT STATE
# =============================================================================

class WebhookEditState:
    """Tracks the current edit state for a user"""

    def __init__(
        self,
        user_id: int,
        guild_id: int,
        channel_id: int,
        message_id: int,
        webhook: discord.Webhook,
        original_message: discord.WebhookMessage
    ):
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id = message_id
        self.webhook = webhook
        self.original_message = original_message

        # Editable content
        self.content = original_message.content or ""
        self.embeds = self._parse_embeds(original_message.embeds)

        # Track changes
        self.has_changes = False

    def _parse_embeds(self, embeds: List[discord.Embed]) -> List[EmbedData]:
        """Convert discord.Embed objects to EmbedData"""
        result = []
        for embed in embeds:
            data = EmbedData(
                title=embed.title,
                description=embed.description,
                url=embed.url,
                color=embed.color.value if embed.color else None
            )

            # Author
            if embed.author:
                data.author_name = embed.author.name
                data.author_url = embed.author.url
                data.author_icon_url = embed.author.icon_url

            # Fields
            for field in embed.fields:
                data.fields.append(FieldData(
                    name=field.name,
                    value=field.value,
                    inline=field.inline
                ))

            # Images
            if embed.thumbnail:
                data.thumbnail_url = embed.thumbnail.url
            if embed.image:
                data.image_url = embed.image.url

            # Footer
            if embed.footer:
                data.footer_text = embed.footer.text
                data.footer_icon_url = embed.footer.icon_url

            if embed.timestamp:
                data.timestamp = True

            result.append(data)

        return result


# Store active edit states
active_editors: Dict[int, WebhookEditState] = {}


# =============================================================================
# MODALS
# =============================================================================

class EditContentModal(Modal):
    """Modal for editing message content"""

    def __init__(self, state: WebhookEditState):
        super().__init__(title="Edit Message Content")
        self.state = state

        self.content = TextInput(
            label="Message Content",
            placeholder="Enter message text (can be empty if using embeds)",
            required=False,
            max_length=2000,
            style=discord.TextStyle.paragraph,
            default=state.content or ""
        )

        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.state.content = self.content.value
            self.state.has_changes = True

            await interaction.response.edit_message(
                content=get_edit_status(self.state),
                view=WebhookEditView(self.state)
            )
        except Exception as e:
            logger.error(f"Error in EditContentModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in EditContentModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass


class EditEmbedAuthorModal(Modal):
    """Modal for editing embed author"""

    def __init__(self, state: WebhookEditState, embed_index: int):
        super().__init__(title=f"Edit Embed {embed_index + 1} Author")
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        self.author_name = TextInput(
            label="Author Name",
            required=False,
            max_length=256,
            default=self.embed.author_name or ""
        )

        self.author_url = TextInput(
            label="Author URL (optional)",
            required=False,
            max_length=500,
            default=self.embed.author_url or ""
        )

        self.author_icon = TextInput(
            label="Author Icon URL (optional)",
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
            self.state.has_changes = True

            await interaction.response.edit_message(
                content=f"**Editing Embed {self.embed_index + 1}**",
                view=EditEmbedView(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error in EditEmbedAuthorModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in EditEmbedAuthorModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass


class EditEmbedBodyModal(Modal):
    """Modal for editing embed body"""

    def __init__(self, state: WebhookEditState, embed_index: int):
        super().__init__(title=f"Edit Embed {embed_index + 1} Body")
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        self.title = TextInput(
            label="Title",
            required=False,
            max_length=256,
            default=self.embed.title or ""
        )

        self.description = TextInput(
            label="Description",
            required=False,
            max_length=4000,
            style=discord.TextStyle.paragraph,
            default=self.embed.description or ""
        )

        self.url = TextInput(
            label="Title URL (optional)",
            required=False,
            max_length=500,
            default=self.embed.url or ""
        )

        self.color = TextInput(
            label="Color (hex or name)",
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
            self.state.has_changes = True

            await interaction.response.edit_message(
                content=f"**Editing Embed {self.embed_index + 1}**",
                view=EditEmbedView(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error in EditEmbedBodyModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in EditEmbedBodyModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass


class EditEmbedFieldModal(Modal):
    """Modal for adding a new field"""

    def __init__(self, state: WebhookEditState, embed_index: int):
        super().__init__(title=f"Add Field to Embed {embed_index + 1}")
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        self.field_name = TextInput(
            label="Field Name",
            required=True,
            max_length=256
        )

        self.field_value = TextInput(
            label="Field Value",
            required=True,
            max_length=1024,
            style=discord.TextStyle.paragraph
        )

        self.inline = TextInput(
            label="Inline? (yes/no)",
            required=False,
            max_length=3,
            default="no"
        )

        self.add_item(self.field_name)
        self.add_item(self.field_value)
        self.add_item(self.inline)

    async def on_submit(self, interaction: discord.Interaction):
        try:
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
            self.state.has_changes = True

            await interaction.response.edit_message(
                content=f"**Editing Embed {self.embed_index + 1}** - Fields: {len(self.embed.fields)}",
                view=EditEmbedView(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error in EditEmbedFieldModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in EditEmbedFieldModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass


class EditEmbedImagesModal(Modal):
    """Modal for editing embed images"""

    def __init__(self, state: WebhookEditState, embed_index: int):
        super().__init__(title=f"Edit Embed {embed_index + 1} Images")
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        self.thumbnail = TextInput(
            label="Thumbnail URL",
            required=False,
            max_length=500,
            default=self.embed.thumbnail_url or ""
        )

        self.image = TextInput(
            label="Image URL",
            required=False,
            max_length=500,
            default=self.embed.image_url or ""
        )

        self.add_item(self.thumbnail)
        self.add_item(self.image)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Fix URLs by adding https:// if missing
            self.embed.thumbnail_url = fix_url(self.thumbnail.value)
            self.embed.image_url = fix_url(self.image.value)
            self.state.has_changes = True

            await interaction.response.edit_message(
                content=f"**Editing Embed {self.embed_index + 1}**",
                view=EditEmbedView(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error in EditEmbedImagesModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in EditEmbedImagesModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass


class EditEmbedFooterModal(Modal):
    """Modal for editing embed footer"""

    def __init__(self, state: WebhookEditState, embed_index: int):
        super().__init__(title=f"Edit Embed {embed_index + 1} Footer")
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        self.footer_text = TextInput(
            label="Footer Text",
            required=False,
            max_length=2048,
            default=self.embed.footer_text or ""
        )

        self.footer_icon = TextInput(
            label="Footer Icon URL (optional)",
            required=False,
            max_length=500,
            default=self.embed.footer_icon_url or ""
        )

        self.timestamp = TextInput(
            label="Add Timestamp? (yes/no)",
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
            self.state.has_changes = True

            await interaction.response.edit_message(
                content=f"**Editing Embed {self.embed_index + 1}**",
                view=EditEmbedView(self.state, self.embed_index)
            )
        except Exception as e:
            logger.error(f"Error in EditEmbedFooterModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in EditEmbedFooterModal: {error}")
        try:
            await interaction.response.send_message(
                "Something went wrong! Please try again.",
                ephemeral=True
            )
        except:
            pass


class NewEmbedModal(Modal):
    """Modal for creating a new embed with basic info"""

    def __init__(self, state: WebhookEditState):
        super().__init__(title="Add New Embed")
        self.state = state

        self.title = TextInput(
            label="Title",
            required=False,
            max_length=256
        )

        self.description = TextInput(
            label="Description",
            required=False,
            max_length=4000,
            style=discord.TextStyle.paragraph
        )

        self.color = TextInput(
            label="Color (hex or name)",
            placeholder="e.g., #FF0000 or red, blue, green",
            required=False,
            max_length=20
        )

        self.add_item(self.title)
        self.add_item(self.description)
        self.add_item(self.color)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if len(self.state.embeds) >= 10:
                await interaction.response.send_message(
                    "Maximum 10 embeds per message!",
                    ephemeral=True
                )
                return

            new_embed = EmbedData(
                title=self.title.value or None,
                description=self.description.value or None,
                color=parse_color(self.color.value)
            )

            self.state.embeds.append(new_embed)
            self.state.has_changes = True
            embed_index = len(self.state.embeds) - 1

            await interaction.response.edit_message(
                content=f"**Editing Embed {embed_index + 1}**\n\nUse the options to configure this embed.",
                view=EditEmbedView(self.state, embed_index)
            )
        except Exception as e:
            logger.error(f"Error in NewEmbedModal: {e}")
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"Modal error in NewEmbedModal: {error}")
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

def get_edit_status(state: WebhookEditState) -> str:
    """Get the current status message for the editor"""
    parts = ["**Webhook Message Editor**\n"]

    if state.content:
        preview = state.content[:100] + "..." if len(state.content) > 100 else state.content
        parts.append(f"**Content:** {preview}")

    parts.append(f"**Embeds:** {len(state.embeds)}")

    if state.has_changes:
        parts.append("\n_Changes pending - click Save to apply_")

    return "\n".join(parts)


class WebhookEditView(View):
    """Main dropdown menu for editing webhook messages"""

    def __init__(self, state: WebhookEditState):
        super().__init__(timeout=600)
        self.state = state

        # Build the main options dropdown
        self._build_dropdown()

    def _build_dropdown(self):
        """Build the edit options dropdown"""
        options = [
            discord.SelectOption(
                label="Edit Content",
                value="edit_content",
                description="Edit the message text",
                emoji="✏️"
            ),
            discord.SelectOption(
                label="Add Embed",
                value="add_embed",
                description="Add a new embed to the message",
                emoji="➕"
            ),
        ]

        # Add embed edit options if there are embeds
        if self.state.embeds:
            options.append(discord.SelectOption(
                label="Edit Embed",
                value="edit_embed",
                description="Modify an existing embed",
                emoji="📝"
            ))
            options.append(discord.SelectOption(
                label="Remove Embed",
                value="remove_embed",
                description="Delete an embed from the message",
                emoji="🗑️"
            ))

        options.extend([
            discord.SelectOption(
                label="Preview",
                value="preview",
                description="See how the message will look",
                emoji="👁️"
            ),
            discord.SelectOption(
                label="Save Changes",
                value="save",
                description="Apply all changes to the message",
                emoji="💾"
            ),
            discord.SelectOption(
                label="Cancel",
                value="cancel",
                description="Discard changes and exit",
                emoji="❌"
            ),
        ])

        select = Select(
            placeholder="Select an action...",
            options=options
        )
        select.callback = self.option_selected
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.user_id:
            await interaction.response.send_message(
                "This isn't your editor!",
                ephemeral=True
            )
            return False
        return True

    async def option_selected(self, interaction: discord.Interaction):
        action = interaction.data["values"][0]

        if action == "edit_content":
            await interaction.response.send_modal(EditContentModal(self.state))

        elif action == "add_embed":
            if len(self.state.embeds) >= 10:
                await interaction.response.send_message(
                    "Maximum 10 embeds per message!",
                    ephemeral=True
                )
                return
            await interaction.response.send_modal(NewEmbedModal(self.state))

        elif action == "edit_embed":
            if not self.state.embeds:
                await interaction.response.send_message(
                    "No embeds to edit!",
                    ephemeral=True
                )
                return
            await interaction.response.edit_message(
                content="**Select an embed to edit:**",
                view=EmbedSelectView(self.state, "edit")
            )

        elif action == "remove_embed":
            if not self.state.embeds:
                await interaction.response.send_message(
                    "No embeds to remove!",
                    ephemeral=True
                )
                return
            await interaction.response.edit_message(
                content="**Select an embed to remove:**",
                view=EmbedSelectView(self.state, "remove")
            )

        elif action == "preview":
            embeds = [e.to_discord_embed() for e in self.state.embeds]
            await interaction.response.send_message(
                content=self.state.content or "(No content)",
                embeds=embeds,
                ephemeral=True
            )

        elif action == "save":
            await self.save_changes(interaction)

        elif action == "cancel":
            if self.state.user_id in active_editors:
                del active_editors[self.state.user_id]

            await interaction.response.edit_message(
                content="Edit cancelled. No changes were saved.",
                view=None
            )
            self.stop()

    async def save_changes(self, interaction: discord.Interaction):
        """Save changes to the webhook message"""
        if not self.state.has_changes:
            await interaction.response.send_message(
                "No changes to save!",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            embeds = [e.to_discord_embed() for e in self.state.embeds]

            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(
                    self.state.webhook.url,
                    session=session
                )

                await webhook.edit_message(
                    self.state.message_id,
                    content=self.state.content or None,
                    embeds=embeds if embeds else []
                )

            # Cleanup
            if self.state.user_id in active_editors:
                del active_editors[self.state.user_id]

            await interaction.followup.send(
                "Changes saved successfully!",
                ephemeral=True
            )

            await interaction.edit_original_response(
                content="Message updated successfully!",
                view=None
            )

        except discord.NotFound:
            await interaction.followup.send(
                "Message or webhook not found! The message may have been deleted.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to edit webhook message: {e}")
            await interaction.followup.send(
                f"Failed to save changes: {e}",
                ephemeral=True
            )


class EmbedSelectView(View):
    """View for selecting which embed to edit or remove"""

    def __init__(self, state: WebhookEditState, action: str):
        super().__init__(timeout=120)
        self.state = state
        self.action = action

        options = []
        for i, embed in enumerate(state.embeds):
            summary = embed.get_summary() if hasattr(embed, 'get_summary') else f"Embed {i + 1}"
            options.append(discord.SelectOption(
                label=f"Embed {i + 1}",
                value=str(i),
                description=summary[:100]
            ))

        select = Select(
            placeholder=f"Select embed to {action}...",
            options=options
        )
        select.callback = self.embed_selected
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.user_id:
            await interaction.response.send_message(
                "This isn't your editor!",
                ephemeral=True
            )
            return False
        return True

    async def embed_selected(self, interaction: discord.Interaction):
        embed_index = int(interaction.data["values"][0])

        if self.action == "edit":
            await interaction.response.edit_message(
                content=f"**Editing Embed {embed_index + 1}**",
                view=EditEmbedView(self.state, embed_index)
            )
        elif self.action == "remove":
            self.state.embeds.pop(embed_index)
            self.state.has_changes = True
            await interaction.response.edit_message(
                content=get_edit_status(self.state),
                view=WebhookEditView(self.state)
            )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content=get_edit_status(self.state),
            view=WebhookEditView(self.state)
        )


class EditEmbedView(View):
    """View for editing a single embed with dropdown options"""

    def __init__(self, state: WebhookEditState, embed_index: int):
        super().__init__(timeout=300)
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        # Build dropdown
        self._build_dropdown()

    def _build_dropdown(self):
        options = [
            discord.SelectOption(
                label="Edit Author",
                value="author",
                description="Set author name, URL, and icon",
                emoji="👤"
            ),
            discord.SelectOption(
                label="Edit Body",
                value="body",
                description="Set title, description, URL, color",
                emoji="📄"
            ),
            discord.SelectOption(
                label="Add Field",
                value="add_field",
                description="Add a new field to the embed",
                emoji="➕"
            ),
            discord.SelectOption(
                label="Edit Images",
                value="images",
                description="Set thumbnail and main image",
                emoji="🖼️"
            ),
            discord.SelectOption(
                label="Edit Footer",
                value="footer",
                description="Set footer text, icon, timestamp",
                emoji="📝"
            ),
            discord.SelectOption(
                label="Preview Embed",
                value="preview",
                description="See how this embed looks",
                emoji="👁️"
            ),
            discord.SelectOption(
                label="Done",
                value="done",
                description="Return to main menu",
                emoji="✅"
            ),
        ]

        # Add remove field option if there are fields
        if self.embed.fields:
            options.insert(3, discord.SelectOption(
                label="Remove Field",
                value="remove_field",
                description=f"Remove a field ({len(self.embed.fields)} fields)",
                emoji="🗑️"
            ))

        select = Select(
            placeholder="Select what to edit...",
            options=options
        )
        select.callback = self.option_selected
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.user_id:
            await interaction.response.send_message(
                "This isn't your editor!",
                ephemeral=True
            )
            return False
        return True

    async def option_selected(self, interaction: discord.Interaction):
        action = interaction.data["values"][0]

        if action == "author":
            await interaction.response.send_modal(
                EditEmbedAuthorModal(self.state, self.embed_index)
            )

        elif action == "body":
            await interaction.response.send_modal(
                EditEmbedBodyModal(self.state, self.embed_index)
            )

        elif action == "add_field":
            if len(self.embed.fields) >= 25:
                await interaction.response.send_message(
                    "Maximum 25 fields per embed!",
                    ephemeral=True
                )
                return
            await interaction.response.send_modal(
                EditEmbedFieldModal(self.state, self.embed_index)
            )

        elif action == "remove_field":
            if not self.embed.fields:
                await interaction.response.send_message(
                    "No fields to remove!",
                    ephemeral=True
                )
                return
            await interaction.response.edit_message(
                content="**Select a field to remove:**",
                view=FieldSelectView(self.state, self.embed_index)
            )

        elif action == "images":
            await interaction.response.send_modal(
                EditEmbedImagesModal(self.state, self.embed_index)
            )

        elif action == "footer":
            await interaction.response.send_modal(
                EditEmbedFooterModal(self.state, self.embed_index)
            )

        elif action == "preview":
            try:
                preview = self.embed.to_discord_embed()
                await interaction.response.send_message(embed=preview, ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(
                    f"Error creating preview: {e}",
                    ephemeral=True
                )

        elif action == "done":
            await interaction.response.edit_message(
                content=get_edit_status(self.state),
                view=WebhookEditView(self.state)
            )


class FieldSelectView(View):
    """View for selecting a field to remove"""

    def __init__(self, state: WebhookEditState, embed_index: int):
        super().__init__(timeout=120)
        self.state = state
        self.embed_index = embed_index
        self.embed = state.embeds[embed_index]

        options = []
        for i, field in enumerate(self.embed.fields):
            options.append(discord.SelectOption(
                label=f"Field {i + 1}: {field.name[:50]}",
                value=str(i),
                description=field.value[:100]
            ))

        select = Select(placeholder="Select field to remove...", options=options)
        select.callback = self.field_selected
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.user_id:
            await interaction.response.send_message(
                "This isn't your editor!",
                ephemeral=True
            )
            return False
        return True

    async def field_selected(self, interaction: discord.Interaction):
        field_index = int(interaction.data["values"][0])
        self.embed.fields.pop(field_index)
        self.state.has_changes = True

        await interaction.response.edit_message(
            content=f"**Editing Embed {self.embed_index + 1}** - Fields: {len(self.embed.fields)}",
            view=EditEmbedView(self.state, self.embed_index)
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(
            content=f"**Editing Embed {self.embed_index + 1}**",
            view=EditEmbedView(self.state, self.embed_index)
        )


# =============================================================================
# COG
# =============================================================================

class WebhookEdit(commands.Cog):
    """Webhook edit command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="webhookedit", description="Edit an existing webhook message (Admin only)")
    @app_commands.describe(message_link="The Discord message link to edit")
    async def webhookedit(self, interaction: discord.Interaction, message_link: str):
        """Edit an existing webhook message"""
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command=f"webhookedit {message_link}",
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

        # Parse the message link
        parsed = parse_message_link(message_link)
        if not parsed:
            await interaction.response.send_message(
                "Invalid message link! Please provide a valid Discord message link.\n"
                "Example: `https://discord.com/channels/123456/789012/345678`",
                ephemeral=True
            )
            return

        # Verify the message is from this guild
        if parsed["guild_id"] != interaction.guild.id:
            await interaction.response.send_message(
                "That message is from a different server!",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Get the channel
            channel = interaction.guild.get_channel(parsed["channel_id"])
            if not channel:
                await interaction.followup.send(
                    "I couldn't find that channel. It may have been deleted or I don't have access.",
                    ephemeral=True
                )
                return

            # Fetch the message
            try:
                message = await channel.fetch_message(parsed["message_id"])
            except discord.NotFound:
                await interaction.followup.send(
                    "Message not found! It may have been deleted.",
                    ephemeral=True
                )
                return

            # Check if it's a webhook message
            if not message.webhook_id:
                await interaction.followup.send(
                    "That message was not sent by a webhook! "
                    "This command can only edit webhook messages.",
                    ephemeral=True
                )
                return

            # Get the webhooks in the channel
            webhooks = await channel.webhooks()
            webhook = None

            for wh in webhooks:
                if wh.id == message.webhook_id:
                    webhook = wh
                    break

            if not webhook:
                await interaction.followup.send(
                    "The webhook that sent this message no longer exists! "
                    "You cannot edit this message.",
                    ephemeral=True
                )
                return

            # Create edit state
            state = WebhookEditState(
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                channel_id=channel.id,
                message_id=message.id,
                webhook=webhook,
                original_message=message
            )
            active_editors[interaction.user.id] = state

            # Show the editor
            embed = discord.Embed(
                title="Webhook Message Editor",
                description=(
                    f"**Channel:** {channel.mention}\n"
                    f"**Message ID:** {message.id}\n"
                    f"**Webhook:** {webhook.name}\n\n"
                    f"**Current Content:** {message.content[:200] + '...' if message.content and len(message.content) > 200 else message.content or '(empty)'}\n"
                    f"**Embeds:** {len(message.embeds)}"
                ),
                color=discord.Color.blue()
            )

            await interaction.followup.send(
                embed=embed,
                view=WebhookEditView(state),
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to access that channel or its webhooks!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in webhookedit: {e}")
            await interaction.followup.send(
                f"An error occurred: {e}",
                ephemeral=True
            )


# Required setup function
async def setup(bot: commands.Bot):
    """Add the WebhookEdit cog to the bot"""
    await bot.add_cog(WebhookEdit(bot))
