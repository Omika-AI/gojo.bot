"""
Ticket System Command
Creates and manages support tickets with button interactions.
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from datetime import datetime
import asyncio
import io

from utils.logger import log_command, logger
from utils.tickets_db import (
    get_guild_config,
    set_guild_config,
    create_ticket,
    get_ticket,
    close_ticket,
    reopen_ticket,
    delete_ticket,
    claim_ticket,
    lock_ticket,
    unlock_ticket,
    format_ticket_number
)

# Colors for embeds
COLOR_BLUE = 0x5865F2      # Discord blurple
COLOR_GREEN = 0x57F287     # Success green
COLOR_RED = 0xED4245       # Danger red
COLOR_ORANGE = 0xFFA500    # Warning orange
COLOR_GRAY = 0x99AAB5      # Gray


# ==================== CATEGORY SELECT ====================

class CategorySelect(Select):
    """Dropdown for selecting ticket category."""

    def __init__(self):
        options = [
            discord.SelectOption(
                label="Support",
                value="support",
                description="General help and questions",
                emoji="🎫"
            ),
            discord.SelectOption(
                label="Report",
                value="report",
                description="Report a user or issue",
                emoji="🚨"
            ),
            discord.SelectOption(
                label="Appeal",
                value="appeal",
                description="Ban or mute appeals",
                emoji="⚖️"
            ),
            discord.SelectOption(
                label="Other",
                value="other",
                description="Something else",
                emoji="📝"
            ),
        ]
        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle category selection and create the ticket."""
        category = self.values[0]
        await create_ticket_channel(interaction, category)


class CategorySelectView(View):
    """View containing the category dropdown."""

    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(CategorySelect())

    async def on_timeout(self):
        """Disable the select when it times out."""
        for item in self.children:
            item.disabled = True


# ==================== TICKET PANEL VIEW ====================

class TicketPanelView(View):
    """Persistent view for the ticket panel with Open Ticket button."""

    def __init__(self):
        # timeout=None makes the view persistent
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.success,
        custom_id="ticket_panel_open",
        emoji="📩"
    )
    async def open_ticket_button(self, interaction: discord.Interaction, button: Button):
        """Handle the Open Ticket button click."""
        # Check if ticket system is configured
        config = get_guild_config(interaction.guild_id)
        if not config:
            await interaction.response.send_message(
                "❌ Ticket system is not configured. An admin needs to run `/ticket setup` first.",
                ephemeral=True
            )
            return

        # Show category selection
        embed = discord.Embed(
            title="📋 Select a Category",
            description="Please select the category that best describes your issue.",
            color=COLOR_BLUE
        )
        view = CategorySelectView()

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ==================== TICKET CONTROL VIEW ====================

class TicketControlView(View):
    """View with control buttons inside a ticket channel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_claim",
        emoji="🙋"
    )
    async def claim_button(self, interaction: discord.Interaction, button: Button):
        """Handle the Claim button click."""
        config = get_guild_config(interaction.guild_id)
        if not config:
            await interaction.response.send_message("❌ Ticket system not configured.", ephemeral=True)
            return

        # Check if user has staff role
        staff_role_id = int(config["staff_role"])
        staff_role = interaction.guild.get_role(staff_role_id)
        if staff_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Only staff members can claim tickets.",
                ephemeral=True
            )
            return

        ticket = get_ticket(interaction.guild_id, interaction.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
            return

        if ticket["claimed_by"]:
            claimer = interaction.guild.get_member(int(ticket["claimed_by"]))
            claimer_name = claimer.display_name if claimer else "Unknown"
            await interaction.response.send_message(
                f"❌ This ticket is already claimed by **{claimer_name}**.",
                ephemeral=True
            )
            return

        # Claim the ticket
        claim_ticket(interaction.guild_id, interaction.channel_id, interaction.user.id)

        # Update the ticket embed
        await interaction.response.send_message(
            f"✅ **{interaction.user.display_name}** has claimed this ticket!",
            allowed_mentions=discord.AllowedMentions.none()
        )

        logger.info(f"Ticket in #{interaction.channel.name} claimed by {interaction.user}")

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close",
        emoji="🔒"
    )
    async def close_button(self, interaction: discord.Interaction, button: Button):
        """Handle the Close button click."""
        config = get_guild_config(interaction.guild_id)
        if not config:
            await interaction.response.send_message("❌ Ticket system not configured.", ephemeral=True)
            return

        ticket = get_ticket(interaction.guild_id, interaction.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
            return

        # Check if user is staff or ticket owner
        staff_role_id = int(config["staff_role"])
        staff_role = interaction.guild.get_role(staff_role_id)
        is_staff = staff_role in interaction.user.roles
        is_owner = str(interaction.user.id) == ticket["user_id"]

        if not is_staff and not is_owner:
            await interaction.response.send_message(
                "❌ Only staff members or the ticket owner can close this ticket.",
                ephemeral=True
            )
            return

        # Show confirmation
        confirm_view = CloseConfirmView(interaction.user.id)
        embed = discord.Embed(
            title="⚠️ Close Ticket?",
            description="Are you sure you want to close this ticket?\nA transcript will be saved before closing.",
            color=COLOR_ORANGE
        )
        await interaction.response.send_message(embed=embed, view=confirm_view)

    @discord.ui.button(
        label="Lock",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_lock",
        emoji="🔐"
    )
    async def lock_button(self, interaction: discord.Interaction, button: Button):
        """Handle the Lock button click."""
        config = get_guild_config(interaction.guild_id)
        if not config:
            await interaction.response.send_message("❌ Ticket system not configured.", ephemeral=True)
            return

        # Check if user has staff role
        staff_role_id = int(config["staff_role"])
        staff_role = interaction.guild.get_role(staff_role_id)
        if staff_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Only staff members can lock tickets.",
                ephemeral=True
            )
            return

        ticket = get_ticket(interaction.guild_id, interaction.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
            return

        if ticket["locked"]:
            await interaction.response.send_message("❌ This ticket is already locked.", ephemeral=True)
            return

        # Lock the ticket - remove user's send message permission
        ticket_owner = interaction.guild.get_member(int(ticket["user_id"]))
        if ticket_owner:
            await interaction.channel.set_permissions(
                ticket_owner,
                view_channel=True,
                send_messages=False,
                read_message_history=True
            )

        lock_ticket(interaction.guild_id, interaction.channel_id)

        await interaction.response.send_message(
            f"🔐 Ticket locked by **{interaction.user.display_name}**. The user can no longer send messages."
        )
        logger.info(f"Ticket #{interaction.channel.name} locked by {interaction.user}")

    @discord.ui.button(
        label="Unlock",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_unlock",
        emoji="🔓"
    )
    async def unlock_button(self, interaction: discord.Interaction, button: Button):
        """Handle the Unlock button click."""
        config = get_guild_config(interaction.guild_id)
        if not config:
            await interaction.response.send_message("❌ Ticket system not configured.", ephemeral=True)
            return

        # Check if user has staff role
        staff_role_id = int(config["staff_role"])
        staff_role = interaction.guild.get_role(staff_role_id)
        if staff_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Only staff members can unlock tickets.",
                ephemeral=True
            )
            return

        ticket = get_ticket(interaction.guild_id, interaction.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
            return

        if not ticket["locked"]:
            await interaction.response.send_message("❌ This ticket is not locked.", ephemeral=True)
            return

        # Unlock the ticket - restore user's send message permission
        ticket_owner = interaction.guild.get_member(int(ticket["user_id"]))
        if ticket_owner:
            await interaction.channel.set_permissions(
                ticket_owner,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        unlock_ticket(interaction.guild_id, interaction.channel_id)

        await interaction.response.send_message(
            f"🔓 Ticket unlocked by **{interaction.user.display_name}**. The user can now send messages again."
        )
        logger.info(f"Ticket #{interaction.channel.name} unlocked by {interaction.user}")


# ==================== CLOSE CONFIRMATION VIEW ====================

class CloseConfirmView(View):
    """Confirmation view for closing a ticket."""

    def __init__(self, user_id: int):
        super().__init__(timeout=30)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to confirm."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Only the person who initiated the close can confirm.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Yes, Close", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_close(self, interaction: discord.Interaction, button: Button):
        """Confirm closing the ticket."""
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🔒 Closing Ticket...",
                description="Generating transcript and closing the ticket.",
                color=COLOR_ORANGE
            ),
            view=None
        )

        config = get_guild_config(interaction.guild_id)
        ticket = get_ticket(interaction.guild_id, interaction.channel_id)

        if not ticket:
            return

        # Generate transcript
        transcript = await generate_transcript(interaction.channel, ticket)

        # Get ticket owner
        ticket_owner = interaction.guild.get_member(int(ticket["user_id"]))

        # Create summary embed for logs
        ticket_number = format_ticket_number(ticket["ticket_number"])
        created_at = datetime.fromisoformat(ticket["created_at"])
        closed_at = datetime.utcnow()
        duration = closed_at - created_at

        # Calculate duration string
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            duration_str = f"{hours}h {minutes}m"
        else:
            duration_str = f"{minutes}m {seconds}s"

        # Get message count
        message_count = len([m async for m in interaction.channel.history(limit=None)])

        # Get claimer info
        claimer_str = "Unclaimed"
        if ticket["claimed_by"]:
            claimer = interaction.guild.get_member(int(ticket["claimed_by"]))
            claimer_str = claimer.display_name if claimer else "Unknown"

        log_embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_number} Closed",
            color=COLOR_ORANGE,
            timestamp=closed_at
        )
        log_embed.add_field(name="Opened By", value=ticket_owner.mention if ticket_owner else "Unknown", inline=True)
        log_embed.add_field(name="Category", value=ticket["category"].title(), inline=True)
        log_embed.add_field(name="Claimed By", value=claimer_str, inline=True)
        log_embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="Duration", value=duration_str, inline=True)
        log_embed.add_field(name="Messages", value=str(message_count), inline=True)

        # Send to log channel
        if config["log_channel"]:
            log_channel = interaction.guild.get_channel(int(config["log_channel"]))
            if log_channel:
                file = discord.File(
                    io.BytesIO(transcript.encode()),
                    filename=f"transcript-{ticket_number}.txt"
                )
                await log_channel.send(embed=log_embed, file=file)

        # Try to DM the ticket owner
        if ticket_owner:
            try:
                dm_embed = discord.Embed(
                    title=f"🎫 Your Ticket #{ticket_number} Has Been Closed",
                    description=f"Your ticket in **{interaction.guild.name}** has been closed.",
                    color=COLOR_BLUE
                )
                dm_embed.add_field(name="Category", value=ticket["category"].title(), inline=True)
                dm_embed.add_field(name="Duration", value=duration_str, inline=True)

                dm_file = discord.File(
                    io.BytesIO(transcript.encode()),
                    filename=f"transcript-{ticket_number}.txt"
                )
                await ticket_owner.send(embed=dm_embed, file=dm_file)
            except discord.Forbidden:
                # User has DMs disabled
                pass

        # Mark ticket as closed in database (but don't delete)
        close_ticket(interaction.guild_id, interaction.channel_id)

        # Lock the channel - remove everyone's send permission except staff
        staff_role = interaction.guild.get_role(int(config["staff_role"]))
        if ticket_owner:
            await interaction.channel.set_permissions(
                ticket_owner,
                view_channel=True,
                send_messages=False,
                read_message_history=True
            )

        logger.info(f"Ticket #{ticket_number} closed by {interaction.user} in {interaction.guild.name}")

        # Send closed message with reopen/delete buttons
        closed_embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=(
                "This ticket has been closed. The transcript has been saved.\n\n"
                "**Options:**\n"
                "• Click **Open Again** to reopen this ticket\n"
                "• Click **Delete** to permanently delete this channel"
            ),
            color=COLOR_RED,
            timestamp=closed_at
        )
        closed_embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
        closed_embed.add_field(name="Duration", value=duration_str, inline=True)

        await interaction.channel.send(embed=closed_embed, view=ClosedTicketView())

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_close(self, interaction: discord.Interaction, button: Button):
        """Cancel closing the ticket."""
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅ Cancelled",
                description="The ticket will remain open.",
                color=COLOR_GREEN
            ),
            view=None
        )


# ==================== CLOSED TICKET VIEW ====================

class ClosedTicketView(View):
    """View with Open Again and Delete buttons for closed tickets."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Again",
        style=discord.ButtonStyle.success,
        custom_id="ticket_reopen",
        emoji="🔓"
    )
    async def reopen_button(self, interaction: discord.Interaction, button: Button):
        """Reopen the closed ticket."""
        config = get_guild_config(interaction.guild_id)
        if not config:
            await interaction.response.send_message("❌ Ticket system not configured.", ephemeral=True)
            return

        # Check if user has staff role
        staff_role_id = int(config["staff_role"])
        staff_role = interaction.guild.get_role(staff_role_id)
        if staff_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Only staff members can reopen tickets.",
                ephemeral=True
            )
            return

        ticket = get_ticket(interaction.guild_id, interaction.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ Ticket data not found.", ephemeral=True)
            return

        # Reopen the ticket in database
        reopen_ticket(interaction.guild_id, interaction.channel_id)

        # Restore user permissions
        ticket_owner = interaction.guild.get_member(int(ticket["user_id"]))
        if ticket_owner:
            await interaction.channel.set_permissions(
                ticket_owner,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True
            )

        ticket_number = format_ticket_number(ticket["ticket_number"])

        # Update the message
        reopen_embed = discord.Embed(
            title="🔓 Ticket Reopened",
            description=f"This ticket has been reopened by {interaction.user.mention}.",
            color=COLOR_GREEN,
            timestamp=datetime.utcnow()
        )

        await interaction.response.edit_message(embed=reopen_embed, view=None)

        # Send notification
        await interaction.channel.send(
            f"📬 {ticket_owner.mention if ticket_owner else 'User'}, your ticket has been reopened!",
            view=TicketControlView()
        )

        logger.info(f"Ticket #{ticket_number} reopened by {interaction.user} in {interaction.guild.name}")

    @discord.ui.button(
        label="Delete",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_delete",
        emoji="🗑️"
    )
    async def delete_button(self, interaction: discord.Interaction, button: Button):
        """Show delete confirmation."""
        config = get_guild_config(interaction.guild_id)
        if not config:
            await interaction.response.send_message("❌ Ticket system not configured.", ephemeral=True)
            return

        # Check if user has staff role
        staff_role_id = int(config["staff_role"])
        staff_role = interaction.guild.get_role(staff_role_id)
        if staff_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Only staff members can delete tickets.",
                ephemeral=True
            )
            return

        # Show delete confirmation
        confirm_embed = discord.Embed(
            title="⚠️ Delete Ticket?",
            description=(
                "Are you sure you want to **permanently delete** this ticket channel?\n\n"
                "**This action cannot be undone!**"
            ),
            color=COLOR_RED
        )

        await interaction.response.edit_message(embed=confirm_embed, view=DeleteConfirmView(interaction.user.id))

    @discord.ui.button(
        label="Transcript",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_transcript_closed",
        emoji="📜"
    )
    async def transcript_button(self, interaction: discord.Interaction, button: Button):
        """Generate and send transcript to the log channel."""
        config = get_guild_config(interaction.guild_id)
        if not config:
            await interaction.response.send_message("❌ Ticket system not configured.", ephemeral=True)
            return

        # Check if user has staff role
        staff_role_id = int(config["staff_role"])
        staff_role = interaction.guild.get_role(staff_role_id)
        if staff_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Only staff members can save transcripts.",
                ephemeral=True
            )
            return

        ticket = get_ticket(interaction.guild_id, interaction.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ Ticket data not found.", ephemeral=True)
            return

        # Check if log channel is configured
        if not config.get("log_channel"):
            await interaction.response.send_message("❌ No log channel configured.", ephemeral=True)
            return

        log_channel = interaction.guild.get_channel(int(config["log_channel"]))
        if not log_channel:
            await interaction.response.send_message("❌ Log channel not found.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Generate transcript
        transcript = await generate_transcript(interaction.channel, ticket)
        ticket_number = format_ticket_number(ticket["ticket_number"])

        # Get ticket owner
        ticket_owner = interaction.guild.get_member(int(ticket["user_id"]))

        # Create embed for log channel
        log_embed = discord.Embed(
            title=f"📜 Transcript Saved - Ticket #{ticket_number}",
            color=COLOR_BLUE,
            timestamp=datetime.utcnow()
        )
        log_embed.add_field(name="Opened By", value=ticket_owner.mention if ticket_owner else "Unknown", inline=True)
        log_embed.add_field(name="Category", value=ticket["category"].title(), inline=True)
        log_embed.add_field(name="Saved By", value=interaction.user.mention, inline=True)

        # Send transcript to log channel
        file = discord.File(
            io.BytesIO(transcript.encode()),
            filename=f"transcript-{ticket_number}.txt"
        )
        await log_channel.send(embed=log_embed, file=file)

        # Confirm to staff
        await interaction.followup.send(
            f"✅ Transcript saved to {log_channel.mention}",
            ephemeral=True
        )
        logger.info(f"Transcript saved for #{interaction.channel.name} by {interaction.user}")


# ==================== DELETE CONFIRMATION VIEW ====================

class DeleteConfirmView(View):
    """Final confirmation view for deleting a ticket."""

    def __init__(self, user_id: int):
        super().__init__(timeout=30)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to confirm."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Only the person who initiated the delete can confirm.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Yes, Delete Forever", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_delete(self, interaction: discord.Interaction, button: Button):
        """Confirm deleting the ticket."""
        ticket = get_ticket(interaction.guild_id, interaction.channel_id)
        ticket_number = format_ticket_number(ticket["ticket_number"]) if ticket else "Unknown"

        # Remove from database
        delete_ticket(interaction.guild_id, interaction.channel_id)

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🗑️ Deleting Channel...",
                description="This channel will be deleted in 3 seconds.",
                color=COLOR_RED
            ),
            view=None
        )

        logger.info(f"Ticket #{ticket_number} deleted by {interaction.user} in {interaction.guild.name}")

        await asyncio.sleep(3)
        await interaction.channel.delete(reason=f"Ticket #{ticket_number} deleted by {interaction.user}")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_delete(self, interaction: discord.Interaction, button: Button):
        """Cancel deleting the ticket."""
        # Go back to the closed ticket view
        closed_embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=(
                "This ticket has been closed. The transcript has been saved.\n\n"
                "**Options:**\n"
                "• Click **Open Again** to reopen this ticket\n"
                "• Click **Delete** to permanently delete this channel"
            ),
            color=COLOR_RED
        )

        await interaction.response.edit_message(embed=closed_embed, view=ClosedTicketView())


# ==================== HELPER FUNCTIONS ====================

async def generate_transcript(channel: discord.TextChannel, ticket: dict) -> str:
    """Generate a plain text transcript of the ticket."""
    ticket_number = format_ticket_number(ticket["ticket_number"])
    created_at = datetime.fromisoformat(ticket["created_at"])
    closed_at = datetime.utcnow()

    # Build header
    lines = [
        f"{'=' * 50}",
        f"TICKET #{ticket_number} TRANSCRIPT",
        f"{'=' * 50}",
        f"Category: {ticket['category'].title()}",
        f"Created: {created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Closed: {closed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"{'=' * 50}",
        ""
    ]

    # Fetch all messages (oldest first)
    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        messages.append(msg)

    # Format each message
    for msg in messages:
        timestamp = msg.created_at.strftime("%H:%M:%S")
        author = f"{msg.author.display_name}"

        # Handle message content
        content = msg.content if msg.content else ""

        # Handle attachments
        if msg.attachments:
            attachment_names = [a.filename for a in msg.attachments]
            if content:
                content += f" [Attachments: {', '.join(attachment_names)}]"
            else:
                content = f"[Attachments: {', '.join(attachment_names)}]"

        # Handle embeds (just note them)
        if msg.embeds and not content:
            content = "[Embed]"

        if content:
            lines.append(f"[{timestamp}] {author}: {content}")

    lines.append("")
    lines.append(f"{'=' * 50}")
    lines.append(f"END OF TRANSCRIPT - {len(messages)} messages")
    lines.append(f"{'=' * 50}")

    return "\n".join(lines)


async def create_ticket_channel(interaction: discord.Interaction, category: str) -> None:
    """Create a new ticket channel for the user."""
    config = get_guild_config(interaction.guild_id)

    if not config:
        await interaction.response.send_message(
            "❌ Ticket system is not configured.",
            ephemeral=True
        )
        return

    guild = interaction.guild
    user = interaction.user

    # Get staff role
    staff_role = guild.get_role(int(config["staff_role"]))
    if not staff_role:
        await interaction.response.send_message(
            "❌ Staff role not found. Please contact an administrator.",
            ephemeral=True
        )
        return

    # Get category (if set)
    ticket_category = None
    if config.get("category_id"):
        ticket_category = guild.get_channel(int(config["category_id"]))

    # Create ticket in database first to get the number
    try:
        ticket_number = create_ticket(
            guild_id=guild.id,
            channel_id=0,  # Placeholder, will update after channel creation
            user_id=user.id,
            category=category
        )
    except ValueError as e:
        await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)
        return

    ticket_number_str = format_ticket_number(ticket_number)
    channel_name = f"ticket-{ticket_number_str}-{user.name[:10].lower()}"

    # Set up permissions
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True
        ),
        staff_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            manage_messages=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True
        )
    }

    # Create the channel
    try:
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=ticket_category,
            overwrites=overwrites,
            reason=f"Ticket #{ticket_number_str} opened by {user}"
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to create channels.",
            ephemeral=True
        )
        return

    # Update ticket record with actual channel ID
    from utils.tickets_db import load_tickets, save_tickets
    data = load_tickets()
    guild_str = str(guild.id)

    # Find and update the ticket (it has channel_id = 0)
    for ch_id, tkt in list(data[guild_str]["active_tickets"].items()):
        if tkt["ticket_number"] == ticket_number and ch_id == "0":
            # Remove old entry and add with correct channel ID
            del data[guild_str]["active_tickets"]["0"]
            data[guild_str]["active_tickets"][str(ticket_channel.id)] = tkt
            save_tickets(data)
            break

    # Create welcome embed
    category_emojis = {
        "support": "🎫",
        "report": "🚨",
        "appeal": "⚖️",
        "other": "📝"
    }

    welcome_embed = discord.Embed(
        title=f"{category_emojis.get(category, '📋')} Ticket #{ticket_number_str} - {category.title()}",
        description=(
            f"Welcome {user.mention}!\n\n"
            "A staff member will be with you shortly.\n"
            "Please describe your issue in detail while you wait."
        ),
        color=COLOR_GREEN,
        timestamp=datetime.utcnow()
    )
    welcome_embed.add_field(name="Category", value=category.title(), inline=True)
    welcome_embed.add_field(name="Status", value="🟢 Open", inline=True)
    welcome_embed.set_footer(text="Use the buttons below to manage this ticket")

    # Send welcome message with control buttons
    await ticket_channel.send(
        content=f"{user.mention} {staff_role.mention}",
        embed=welcome_embed,
        view=TicketControlView(),
        allowed_mentions=discord.AllowedMentions(users=True, roles=True)
    )

    # Confirm to user
    await interaction.response.send_message(
        f"✅ Your ticket has been created: {ticket_channel.mention}",
        ephemeral=True
    )

    logger.info(f"Ticket #{ticket_number_str} created by {user} in {guild.name} - Category: {category}")


# ==================== TICKET COMMAND COG ====================

class Ticket(commands.Cog):
    """Ticket system commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Register persistent views when the cog loads
    async def cog_load(self):
        """Called when the cog is loaded."""
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketControlView())
        self.bot.add_view(ClosedTicketView())

    # Command group for ticket commands
    ticket_group = app_commands.Group(name="ticket", description="Ticket system commands")

    @ticket_group.command(name="setup", description="Set up the ticket system")
    @app_commands.describe(
        staff_role="Role that can manage tickets",
        log_channel="Channel where transcripts are sent",
        category="Category for ticket channels (optional)"
    )
    @app_commands.default_permissions(administrator=True)
    async def ticket_setup(
        self,
        interaction: discord.Interaction,
        staff_role: discord.Role,
        log_channel: discord.TextChannel,
        category: discord.CategoryChannel = None
    ):
        """Set up the ticket system and send the ticket panel."""
        log_command(interaction.user.name, interaction.user.id, "ticket setup", interaction.guild.name)

        # Save configuration
        set_guild_config(
            guild_id=interaction.guild_id,
            staff_role_id=staff_role.id,
            log_channel_id=log_channel.id,
            ticket_channel_id=interaction.channel_id,
            category_id=category.id if category else None
        )

        # Create panel embed
        panel_embed = discord.Embed(
            title="🎫 Support Tickets",
            description=(
                "Need help? Click the button below to open a support ticket.\n\n"
                "**How it works:**\n"
                "1. Click the **Open Ticket** button below\n"
                "2. Select a category for your issue\n"
                "3. A private channel will be created for you\n"
                "4. Describe your issue and wait for staff\n\n"
                "Please be patient and provide as much detail as possible!"
            ),
            color=COLOR_BLUE
        )
        panel_embed.set_footer(text="Click the button below to open a ticket")

        # Send panel with button
        await interaction.channel.send(embed=panel_embed, view=TicketPanelView())

        # Confirm setup
        await interaction.response.send_message(
            f"✅ Ticket system configured!\n"
            f"• **Staff Role:** {staff_role.mention}\n"
            f"• **Log Channel:** {log_channel.mention}\n"
            f"• **Category:** {category.mention if category else 'None (channels will be created at top)'}\n\n"
            f"The ticket panel has been sent above.",
            ephemeral=True
        )

        logger.info(f"Ticket system set up in {interaction.guild.name} by {interaction.user}")

    @ticket_group.command(name="panel", description="Send a new ticket panel")
    @app_commands.default_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        """Send a new ticket panel embed."""
        log_command(interaction.user.name, interaction.user.id, "ticket panel", interaction.guild.name)

        config = get_guild_config(interaction.guild_id)
        if not config:
            await interaction.response.send_message(
                "❌ Ticket system not configured. Run `/ticket setup` first.",
                ephemeral=True
            )
            return

        # Create panel embed
        panel_embed = discord.Embed(
            title="🎫 Support Tickets",
            description=(
                "Need help? Click the button below to open a support ticket.\n\n"
                "**How it works:**\n"
                "1. Click the **Open Ticket** button below\n"
                "2. Select a category for your issue\n"
                "3. A private channel will be created for you\n"
                "4. Describe your issue and wait for staff\n\n"
                "Please be patient and provide as much detail as possible!"
            ),
            color=COLOR_BLUE
        )
        panel_embed.set_footer(text="Click the button below to open a ticket")

        await interaction.channel.send(embed=panel_embed, view=TicketPanelView())
        await interaction.response.send_message("✅ Ticket panel sent!", ephemeral=True)

    @ticket_group.command(name="add", description="Add a user to the current ticket")
    @app_commands.describe(user="The user to add to this ticket")
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        """Add a user to the current ticket channel."""
        log_command(interaction.user.name, interaction.user.id, "ticket add", interaction.guild.name)

        ticket = get_ticket(interaction.guild_id, interaction.channel_id)
        if not ticket:
            await interaction.response.send_message(
                "❌ This command can only be used inside a ticket channel.",
                ephemeral=True
            )
            return

        config = get_guild_config(interaction.guild_id)
        staff_role = interaction.guild.get_role(int(config["staff_role"]))

        # Check if user is staff or ticket owner
        is_staff = staff_role in interaction.user.roles
        is_owner = str(interaction.user.id) == ticket["user_id"]

        if not is_staff and not is_owner:
            await interaction.response.send_message(
                "❌ Only staff or the ticket owner can add users.",
                ephemeral=True
            )
            return

        # Add user to channel
        await interaction.channel.set_permissions(
            user,
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )

        await interaction.response.send_message(
            f"✅ {user.mention} has been added to this ticket."
        )
        logger.info(f"{user} added to ticket #{interaction.channel.name} by {interaction.user}")

    @ticket_group.command(name="remove", description="Remove a user from the current ticket")
    @app_commands.describe(user="The user to remove from this ticket")
    async def ticket_remove(self, interaction: discord.Interaction, user: discord.Member):
        """Remove a user from the current ticket channel."""
        log_command(interaction.user.name, interaction.user.id, "ticket remove", interaction.guild.name)

        ticket = get_ticket(interaction.guild_id, interaction.channel_id)
        if not ticket:
            await interaction.response.send_message(
                "❌ This command can only be used inside a ticket channel.",
                ephemeral=True
            )
            return

        config = get_guild_config(interaction.guild_id)
        staff_role = interaction.guild.get_role(int(config["staff_role"]))

        # Only staff can remove users
        if staff_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Only staff can remove users from tickets.",
                ephemeral=True
            )
            return

        # Can't remove the ticket owner
        if str(user.id) == ticket["user_id"]:
            await interaction.response.send_message(
                "❌ You cannot remove the ticket owner.",
                ephemeral=True
            )
            return

        # Remove user from channel
        await interaction.channel.set_permissions(user, overwrite=None)

        await interaction.response.send_message(
            f"✅ {user.mention} has been removed from this ticket."
        )
        logger.info(f"{user} removed from ticket #{interaction.channel.name} by {interaction.user}")


# ==================== SETUP FUNCTION ====================

async def setup(bot: commands.Bot):
    """Add the Ticket cog to the bot."""
    await bot.add_cog(Ticket(bot))
