"""
Event Logger Utility
Builds and sends webhook embeds for Discord event logging
Handles all event types with color-coded, formatted embeds
"""

import discord
import aiohttp
from typing import Optional, List, Dict, Any
from datetime import datetime

from utils.logger import logger
from utils.event_logs_db import (
    get_guild_config,
    is_logging_enabled,
    save_event_log,
    format_event_emoji,
    format_category_color
)


class EventLogger:
    """
    Handles building and sending event log embeds via webhooks
    """

    def __init__(self):
        self.bot_name = "Gojo Logger"
        self.bot_avatar = None  # Can be set to a URL if desired

    async def send_log(
        self,
        guild_id: int,
        category: str,
        event_type: str,
        title: str,
        description: str,
        user_id: int,
        user_name: str,
        user_display_name: Optional[str] = None,
        user_avatar_url: Optional[str] = None,
        target_id: Optional[int] = None,
        target_name: Optional[str] = None,
        channel_id: Optional[int] = None,
        channel_name: Optional[str] = None,
        before: Optional[str] = None,
        after: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None,
        details: Optional[Dict] = None,
        color: Optional[int] = None
    ) -> bool:
        """
        Send a log entry to the guild's logging channel via webhook

        Args:
            guild_id: The server ID
            category: Event category (messages, members, etc.)
            event_type: Specific event type
            title: Embed title
            description: Embed description
            user_id: User who triggered the event
            user_name: User's username
            user_display_name: User's display name
            user_avatar_url: User's avatar URL
            target_id: Target user ID (if applicable)
            target_name: Target user name (if applicable)
            channel_id: Channel ID where event occurred
            channel_name: Channel name
            before: State before change
            after: State after change
            fields: Additional embed fields
            details: Extra details for storage
            color: Embed color (uses category color if not specified)

        Returns:
            True if sent successfully
        """
        # Check if logging is enabled for this guild and category
        if not is_logging_enabled(guild_id, category):
            return False

        config = get_guild_config(guild_id)
        if not config or not config.get("webhook_url"):
            return False

        # Save to searchable database
        save_event_log(
            guild_id=guild_id,
            category=category,
            event_type=event_type,
            user_id=user_id,
            user_name=user_name,
            user_display_name=user_display_name,
            target_id=target_id,
            target_name=target_name,
            channel_id=channel_id,
            channel_name=channel_name,
            before=before,
            after=after,
            details=details
        )

        # Build the embed
        embed = self._build_embed(
            category=category,
            event_type=event_type,
            title=title,
            description=description,
            user_id=user_id,
            user_name=user_name,
            user_avatar_url=user_avatar_url,
            channel_id=channel_id,
            before=before,
            after=after,
            fields=fields,
            color=color
        )

        # Send via webhook
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(
                    config["webhook_url"],
                    session=session
                )

                await webhook.send(
                    embed=embed,
                    username=self.bot_name,
                    avatar_url=self.bot_avatar
                )

            return True

        except discord.NotFound:
            logger.error(f"Webhook not found for guild {guild_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to send event log for guild {guild_id}: {e}")
            return False

    def _build_embed(
        self,
        category: str,
        event_type: str,
        title: str,
        description: str,
        user_id: int,
        user_name: str,
        user_avatar_url: Optional[str] = None,
        channel_id: Optional[int] = None,
        before: Optional[str] = None,
        after: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None,
        color: Optional[int] = None
    ) -> discord.Embed:
        """
        Build a Discord embed for the log entry

        Returns:
            Discord Embed object
        """
        emoji = format_event_emoji(event_type)
        embed_color = color or format_category_color(category)

        embed = discord.Embed(
            title=f"{emoji} {title}",
            description=description,
            color=embed_color,
            timestamp=datetime.utcnow()
        )

        # Set author with user info
        embed.set_author(
            name=f"{user_name} ({user_id})",
            icon_url=user_avatar_url if user_avatar_url else None
        )

        # Add channel info if provided
        if channel_id:
            embed.add_field(
                name="Channel",
                value=f"<#{channel_id}>",
                inline=True
            )

        # Add before/after for edits
        if before is not None:
            # Truncate long content
            before_display = before[:1020] + "..." if len(before) > 1020 else before
            embed.add_field(
                name="Before",
                value=before_display or "*Empty*",
                inline=False
            )

        if after is not None:
            after_display = after[:1020] + "..." if len(after) > 1020 else after
            embed.add_field(
                name="After",
                value=after_display or "*Empty*",
                inline=False
            )

        # Add any additional fields
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get("name", "Field"),
                    value=field.get("value", "N/A"),
                    inline=field.get("inline", True)
                )

        # Set footer with category
        embed.set_footer(text=f"{category.capitalize()} Logs")

        return embed

    # ==================== MESSAGE EVENTS ====================

    async def log_message_edit(
        self,
        guild_id: int,
        user: discord.User,
        channel: discord.TextChannel,
        before_content: str,
        after_content: str,
        message_id: int
    ) -> bool:
        """Log a message edit event"""
        return await self.send_log(
            guild_id=guild_id,
            category="messages",
            event_type="message_edit",
            title="Message Edited",
            description=f"A message was edited in {channel.mention}",
            user_id=user.id,
            user_name=str(user),
            user_avatar_url=user.display_avatar.url if user.display_avatar else None,
            channel_id=channel.id,
            channel_name=channel.name,
            before=before_content,
            after=after_content,
            fields=[
                {"name": "Message ID", "value": str(message_id), "inline": True}
            ],
            details={"message_id": message_id}
        )

    async def log_message_delete(
        self,
        guild_id: int,
        user: discord.User,
        channel: discord.TextChannel,
        content: str,
        message_id: int
    ) -> bool:
        """Log a message delete event"""
        return await self.send_log(
            guild_id=guild_id,
            category="messages",
            event_type="message_delete",
            title="Message Deleted",
            description=f"A message was deleted in {channel.mention}",
            user_id=user.id,
            user_name=str(user),
            user_avatar_url=user.display_avatar.url if user.display_avatar else None,
            channel_id=channel.id,
            channel_name=channel.name,
            before=content,
            fields=[
                {"name": "Message ID", "value": str(message_id), "inline": True}
            ],
            details={"message_id": message_id}
        )

    async def log_bulk_delete(
        self,
        guild_id: int,
        channel: discord.TextChannel,
        count: int,
        messages: List[discord.Message]
    ) -> bool:
        """Log a bulk message delete event"""
        # Get the first few message authors for context
        authors = set()
        for msg in messages[:10]:
            if msg.author:
                authors.add(str(msg.author))

        return await self.send_log(
            guild_id=guild_id,
            category="messages",
            event_type="bulk_delete",
            title="Bulk Messages Deleted",
            description=f"**{count}** messages were deleted in {channel.mention}",
            user_id=0,  # System action, no specific user
            user_name="System",
            channel_id=channel.id,
            channel_name=channel.name,
            fields=[
                {"name": "Message Count", "value": str(count), "inline": True},
                {"name": "Authors (sample)", "value": ", ".join(list(authors)[:5]) or "Unknown", "inline": False}
            ],
            details={"count": count}
        )

    # ==================== MEMBER EVENTS ====================

    async def log_member_join(
        self,
        member: discord.Member
    ) -> bool:
        """Log a member join event"""
        account_age = datetime.utcnow() - member.created_at.replace(tzinfo=None)
        age_str = f"{account_age.days} days old"

        return await self.send_log(
            guild_id=member.guild.id,
            category="members",
            event_type="member_join",
            title="Member Joined",
            description=f"{member.mention} joined the server",
            user_id=member.id,
            user_name=str(member),
            user_display_name=member.display_name,
            user_avatar_url=member.display_avatar.url if member.display_avatar else None,
            fields=[
                {"name": "Account Created", "value": f"<t:{int(member.created_at.timestamp())}:R>", "inline": True},
                {"name": "Account Age", "value": age_str, "inline": True},
                {"name": "Member Count", "value": str(member.guild.member_count), "inline": True}
            ],
            details={"account_age_days": account_age.days}
        )

    async def log_member_leave(
        self,
        member: discord.Member
    ) -> bool:
        """Log a member leave event"""
        # Calculate how long they were a member
        if member.joined_at:
            duration = datetime.utcnow() - member.joined_at.replace(tzinfo=None)
            duration_str = f"{duration.days} days"
        else:
            duration_str = "Unknown"

        roles = [role.name for role in member.roles if role.name != "@everyone"]

        return await self.send_log(
            guild_id=member.guild.id,
            category="members",
            event_type="member_leave",
            title="Member Left",
            description=f"{member.mention} left the server",
            user_id=member.id,
            user_name=str(member),
            user_display_name=member.display_name,
            user_avatar_url=member.display_avatar.url if member.display_avatar else None,
            fields=[
                {"name": "Time in Server", "value": duration_str, "inline": True},
                {"name": "Roles", "value": ", ".join(roles[:5]) or "None", "inline": False}
            ],
            details={"roles": roles}
        )

    async def log_member_ban(
        self,
        guild: discord.Guild,
        user: discord.User,
        moderator: Optional[discord.User] = None,
        reason: Optional[str] = None
    ) -> bool:
        """Log a member ban event"""
        fields = []
        if moderator:
            fields.append({"name": "Moderator", "value": f"{moderator.mention} ({moderator.id})", "inline": True})
        fields.append({"name": "Reason", "value": reason or "No reason provided", "inline": False})

        return await self.send_log(
            guild_id=guild.id,
            category="members",
            event_type="member_ban",
            title="Member Banned",
            description=f"**{user}** was banned from the server",
            user_id=user.id,
            user_name=str(user),
            user_avatar_url=user.display_avatar.url if user.display_avatar else None,
            target_id=moderator.id if moderator else None,
            target_name=str(moderator) if moderator else None,
            fields=fields,
            details={"reason": reason},
            color=0xE74C3C  # Red for bans
        )

    async def log_member_unban(
        self,
        guild: discord.Guild,
        user: discord.User,
        moderator: Optional[discord.User] = None
    ) -> bool:
        """Log a member unban event"""
        fields = []
        if moderator:
            fields.append({"name": "Moderator", "value": f"{moderator.mention} ({moderator.id})", "inline": True})

        return await self.send_log(
            guild_id=guild.id,
            category="members",
            event_type="member_unban",
            title="Member Unbanned",
            description=f"**{user}** was unbanned from the server",
            user_id=user.id,
            user_name=str(user),
            user_avatar_url=user.display_avatar.url if user.display_avatar else None,
            target_id=moderator.id if moderator else None,
            target_name=str(moderator) if moderator else None,
            fields=fields,
            color=0x2ECC71  # Green for unbans
        )

    async def log_role_change(
        self,
        member: discord.Member,
        added_roles: List[discord.Role],
        removed_roles: List[discord.Role]
    ) -> bool:
        """Log role add/remove events"""
        if added_roles:
            event_type = "member_role_add"
            title = "Role Added"
            role_names = ", ".join([r.name for r in added_roles])
            description = f"Roles added to {member.mention}"
        else:
            event_type = "member_role_remove"
            title = "Role Removed"
            role_names = ", ".join([r.name for r in removed_roles])
            description = f"Roles removed from {member.mention}"

        return await self.send_log(
            guild_id=member.guild.id,
            category="members",
            event_type=event_type,
            title=title,
            description=description,
            user_id=member.id,
            user_name=str(member),
            user_display_name=member.display_name,
            user_avatar_url=member.display_avatar.url if member.display_avatar else None,
            fields=[
                {"name": "Roles", "value": role_names, "inline": False}
            ],
            details={
                "added": [r.name for r in added_roles],
                "removed": [r.name for r in removed_roles]
            }
        )

    async def log_nickname_change(
        self,
        member: discord.Member,
        before_nick: Optional[str],
        after_nick: Optional[str]
    ) -> bool:
        """Log nickname change event"""
        return await self.send_log(
            guild_id=member.guild.id,
            category="members",
            event_type="member_nickname_change",
            title="Nickname Changed",
            description=f"{member.mention} changed their nickname",
            user_id=member.id,
            user_name=str(member),
            user_display_name=member.display_name,
            user_avatar_url=member.display_avatar.url if member.display_avatar else None,
            before=before_nick or "*No nickname*",
            after=after_nick or "*No nickname*"
        )

    # ==================== VOICE EVENTS ====================

    async def log_voice_join(
        self,
        member: discord.Member,
        channel: discord.VoiceChannel
    ) -> bool:
        """Log voice channel join"""
        return await self.send_log(
            guild_id=member.guild.id,
            category="voice",
            event_type="voice_join",
            title="Voice Channel Joined",
            description=f"{member.mention} joined a voice channel",
            user_id=member.id,
            user_name=str(member),
            user_display_name=member.display_name,
            user_avatar_url=member.display_avatar.url if member.display_avatar else None,
            channel_id=channel.id,
            channel_name=channel.name,
            fields=[
                {"name": "Channel", "value": channel.name, "inline": True},
                {"name": "Members in Channel", "value": str(len(channel.members)), "inline": True}
            ]
        )

    async def log_voice_leave(
        self,
        member: discord.Member,
        channel: discord.VoiceChannel
    ) -> bool:
        """Log voice channel leave"""
        return await self.send_log(
            guild_id=member.guild.id,
            category="voice",
            event_type="voice_leave",
            title="Voice Channel Left",
            description=f"{member.mention} left a voice channel",
            user_id=member.id,
            user_name=str(member),
            user_display_name=member.display_name,
            user_avatar_url=member.display_avatar.url if member.display_avatar else None,
            channel_id=channel.id,
            channel_name=channel.name
        )

    async def log_voice_move(
        self,
        member: discord.Member,
        before_channel: discord.VoiceChannel,
        after_channel: discord.VoiceChannel
    ) -> bool:
        """Log voice channel move"""
        return await self.send_log(
            guild_id=member.guild.id,
            category="voice",
            event_type="voice_move",
            title="Voice Channel Moved",
            description=f"{member.mention} moved to a different voice channel",
            user_id=member.id,
            user_name=str(member),
            user_display_name=member.display_name,
            user_avatar_url=member.display_avatar.url if member.display_avatar else None,
            before=before_channel.name,
            after=after_channel.name,
            fields=[
                {"name": "From", "value": before_channel.name, "inline": True},
                {"name": "To", "value": after_channel.name, "inline": True}
            ]
        )

    async def log_voice_mute(
        self,
        member: discord.Member,
        muted: bool,
        server_mute: bool = False
    ) -> bool:
        """Log voice mute/unmute"""
        event_type = "voice_server_mute" if server_mute else "voice_mute"
        action = "muted" if muted else "unmuted"
        mute_type = "Server " if server_mute else "Self-"

        return await self.send_log(
            guild_id=member.guild.id,
            category="voice",
            event_type=event_type,
            title=f"{mute_type}Mute {'Enabled' if muted else 'Disabled'}",
            description=f"{member.mention} was {action}",
            user_id=member.id,
            user_name=str(member),
            user_display_name=member.display_name,
            user_avatar_url=member.display_avatar.url if member.display_avatar else None,
            fields=[
                {"name": "Status", "value": action.capitalize(), "inline": True},
                {"name": "Type", "value": f"{mute_type}Mute", "inline": True}
            ]
        )

    async def log_voice_deafen(
        self,
        member: discord.Member,
        deafened: bool,
        server_deafen: bool = False
    ) -> bool:
        """Log voice deafen/undeafen"""
        event_type = "voice_server_deafen" if server_deafen else "voice_deafen"
        action = "deafened" if deafened else "undeafened"
        deafen_type = "Server " if server_deafen else "Self-"

        return await self.send_log(
            guild_id=member.guild.id,
            category="voice",
            event_type=event_type,
            title=f"{deafen_type}Deafen {'Enabled' if deafened else 'Disabled'}",
            description=f"{member.mention} was {action}",
            user_id=member.id,
            user_name=str(member),
            user_display_name=member.display_name,
            user_avatar_url=member.display_avatar.url if member.display_avatar else None,
            fields=[
                {"name": "Status", "value": action.capitalize(), "inline": True},
                {"name": "Type", "value": f"{deafen_type}Deafen", "inline": True}
            ]
        )

    # ==================== SERVER EVENTS ====================

    async def log_channel_create(
        self,
        channel: discord.abc.GuildChannel
    ) -> bool:
        """Log channel creation"""
        channel_type = str(channel.type).replace("_", " ").title()

        return await self.send_log(
            guild_id=channel.guild.id,
            category="server",
            event_type="channel_create",
            title="Channel Created",
            description=f"A new {channel_type} channel was created",
            user_id=0,
            user_name="System",
            channel_id=channel.id,
            channel_name=channel.name,
            fields=[
                {"name": "Name", "value": channel.name, "inline": True},
                {"name": "Type", "value": channel_type, "inline": True}
            ]
        )

    async def log_channel_delete(
        self,
        channel: discord.abc.GuildChannel
    ) -> bool:
        """Log channel deletion"""
        channel_type = str(channel.type).replace("_", " ").title()

        return await self.send_log(
            guild_id=channel.guild.id,
            category="server",
            event_type="channel_delete",
            title="Channel Deleted",
            description=f"A {channel_type} channel was deleted",
            user_id=0,
            user_name="System",
            fields=[
                {"name": "Name", "value": channel.name, "inline": True},
                {"name": "Type", "value": channel_type, "inline": True}
            ],
            color=0xE74C3C  # Red for deletions
        )

    async def log_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel
    ) -> bool:
        """Log channel update"""
        changes = []

        if before.name != after.name:
            changes.append(f"Name: `{before.name}` -> `{after.name}`")

        # Check for text channel specific changes
        if hasattr(before, 'topic') and hasattr(after, 'topic'):
            if before.topic != after.topic:
                changes.append(f"Topic changed")

        if hasattr(before, 'slowmode_delay') and hasattr(after, 'slowmode_delay'):
            if before.slowmode_delay != after.slowmode_delay:
                changes.append(f"Slowmode: {before.slowmode_delay}s -> {after.slowmode_delay}s")

        if not changes:
            changes.append("Permissions or other settings changed")

        return await self.send_log(
            guild_id=after.guild.id,
            category="server",
            event_type="channel_update",
            title="Channel Updated",
            description=f"Channel {after.mention} was modified",
            user_id=0,
            user_name="System",
            channel_id=after.id,
            channel_name=after.name,
            fields=[
                {"name": "Changes", "value": "\n".join(changes), "inline": False}
            ]
        )

    async def log_role_create(
        self,
        role: discord.Role
    ) -> bool:
        """Log role creation"""
        return await self.send_log(
            guild_id=role.guild.id,
            category="server",
            event_type="role_create",
            title="Role Created",
            description=f"A new role was created: {role.mention}",
            user_id=0,
            user_name="System",
            fields=[
                {"name": "Name", "value": role.name, "inline": True},
                {"name": "Color", "value": str(role.color), "inline": True},
                {"name": "Position", "value": str(role.position), "inline": True}
            ],
            color=role.color.value if role.color.value != 0 else 0x2ECC71
        )

    async def log_role_delete(
        self,
        role: discord.Role
    ) -> bool:
        """Log role deletion"""
        return await self.send_log(
            guild_id=role.guild.id,
            category="server",
            event_type="role_delete",
            title="Role Deleted",
            description=f"A role was deleted: **{role.name}**",
            user_id=0,
            user_name="System",
            fields=[
                {"name": "Name", "value": role.name, "inline": True}
            ],
            color=0xE74C3C  # Red for deletions
        )

    async def log_role_update(
        self,
        before: discord.Role,
        after: discord.Role
    ) -> bool:
        """Log role update"""
        changes = []

        if before.name != after.name:
            changes.append(f"Name: `{before.name}` -> `{after.name}`")

        if before.color != after.color:
            changes.append(f"Color: `{before.color}` -> `{after.color}`")

        if before.hoist != after.hoist:
            changes.append(f"Hoisted: `{before.hoist}` -> `{after.hoist}`")

        if before.mentionable != after.mentionable:
            changes.append(f"Mentionable: `{before.mentionable}` -> `{after.mentionable}`")

        if before.permissions != after.permissions:
            changes.append("Permissions changed")

        if not changes:
            return False  # No visible changes

        return await self.send_log(
            guild_id=after.guild.id,
            category="server",
            event_type="role_update",
            title="Role Updated",
            description=f"Role {after.mention} was modified",
            user_id=0,
            user_name="System",
            fields=[
                {"name": "Changes", "value": "\n".join(changes), "inline": False}
            ],
            color=after.color.value if after.color.value != 0 else 0xFFA500
        )

    # ==================== COMMAND EVENTS ====================

    async def log_command_use(
        self,
        guild_id: int,
        user: discord.User,
        command_name: str,
        channel: discord.TextChannel,
        user_type: str = "Member"
    ) -> bool:
        """
        Log command usage

        Args:
            guild_id: The server ID
            user: The user who used the command
            command_name: Name of the command used
            channel: Channel where command was used
            user_type: Type of user (Member, Moderator, Admin, Owner)

        Returns:
            True if logged successfully
        """
        # Color based on user type
        type_colors = {
            "Owner": 0xFF0000,       # Red
            "Admin": 0xE74C3C,       # Dark Red
            "Moderator": 0xF39C12,   # Orange
            "Member": 0x00CED1       # Cyan
        }
        color = type_colors.get(user_type, 0x00CED1)

        # Emoji based on user type
        type_emojis = {
            "Owner": "\U0001f451",    # Crown
            "Admin": "\U0001f6e1\ufe0f",  # Shield
            "Moderator": "\U0001f6e0\ufe0f",  # Hammer and wrench
            "Member": "\U0001f464"    # Bust
        }
        type_emoji = type_emojis.get(user_type, "\U0001f464")

        return await self.send_log(
            guild_id=guild_id,
            category="commands",
            event_type="command_use",
            title="Command Used",
            description=f"{user.mention} used `/{command_name}`",
            user_id=user.id,
            user_name=str(user),
            user_avatar_url=user.display_avatar.url if user.display_avatar else None,
            channel_id=channel.id,
            channel_name=channel.name,
            fields=[
                {"name": "Command", "value": f"`/{command_name}`", "inline": True},
                {"name": "User Type", "value": f"{type_emoji} {user_type}", "inline": True},
                {"name": "Channel", "value": channel.mention, "inline": True}
            ],
            details={
                "command": command_name,
                "user_type": user_type
            },
            color=color
        )
