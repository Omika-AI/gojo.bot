"""
Event Listeners Cog
Listens to Discord events and logs them via webhooks
Handles message, member, voice, and server events

This cog is automatically loaded and runs in the background
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime

from utils.logger import logger
from utils.event_logger import EventLogger
from utils.event_logs_db import (
    is_logging_enabled,
    cleanup_old_logs,
    get_guild_config
)


class EventListeners(commands.Cog):
    """Listen to Discord events and log them"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.event_logger = EventLogger()
        # Start the cleanup task
        self.cleanup_task.start()

    def cog_unload(self):
        """Cancel tasks when cog is unloaded"""
        self.cleanup_task.cancel()

    # ==================== CLEANUP TASK ====================

    @tasks.loop(hours=24)
    async def cleanup_task(self):
        """Runs daily to clean up old logs (older than 30 days)"""
        logger.info("Running daily event log cleanup...")
        for guild in self.bot.guilds:
            try:
                removed = cleanup_old_logs(guild.id, days=30)
                if removed > 0:
                    logger.info(f"Cleaned up {removed} old event logs for guild {guild.id}")
            except Exception as e:
                logger.error(f"Error cleaning up logs for guild {guild.id}: {e}")

    @cleanup_task.before_loop
    async def before_cleanup(self):
        """Wait until bot is ready before starting cleanup task"""
        await self.bot.wait_until_ready()

    # ==================== MESSAGE EVENTS ====================

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log message edits"""
        # Skip if no guild (DMs)
        if not before.guild:
            return

        # Skip bot messages
        if before.author.bot:
            return

        # Skip if content didn't change (could be embed load)
        if before.content == after.content:
            return

        # Skip if logging not enabled
        if not is_logging_enabled(before.guild.id, "messages"):
            return

        try:
            await self.event_logger.log_message_edit(
                guild_id=before.guild.id,
                user=before.author,
                channel=before.channel,
                before_content=before.content or "*No content*",
                after_content=after.content or "*No content*",
                message_id=before.id
            )
        except Exception as e:
            logger.error(f"Error logging message edit: {e}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log message deletions"""
        # Skip if no guild (DMs)
        if not message.guild:
            return

        # Skip bot messages
        if message.author.bot:
            return

        # Skip if logging not enabled
        if not is_logging_enabled(message.guild.id, "messages"):
            return

        try:
            await self.event_logger.log_message_delete(
                guild_id=message.guild.id,
                user=message.author,
                channel=message.channel,
                content=message.content or "*No content*",
                message_id=message.id
            )
        except Exception as e:
            logger.error(f"Error logging message delete: {e}")

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list):
        """Log bulk message deletions"""
        if not messages:
            return

        # Get guild from first message
        first_message = messages[0]
        if not first_message.guild:
            return

        # Skip if logging not enabled
        if not is_logging_enabled(first_message.guild.id, "messages"):
            return

        try:
            await self.event_logger.log_bulk_delete(
                guild_id=first_message.guild.id,
                channel=first_message.channel,
                count=len(messages),
                messages=messages
            )
        except Exception as e:
            logger.error(f"Error logging bulk message delete: {e}")

    # ==================== MEMBER EVENTS ====================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Log member joins"""
        if not is_logging_enabled(member.guild.id, "members"):
            return

        try:
            await self.event_logger.log_member_join(member)
        except Exception as e:
            logger.error(f"Error logging member join: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leaves"""
        if not is_logging_enabled(member.guild.id, "members"):
            return

        try:
            await self.event_logger.log_member_leave(member)
        except Exception as e:
            logger.error(f"Error logging member leave: {e}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Log member bans"""
        if not is_logging_enabled(guild.id, "members"):
            return

        try:
            # Try to get moderator and reason from audit log
            moderator = None
            reason = None

            try:
                async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=5):
                    if entry.target.id == user.id:
                        moderator = entry.user
                        reason = entry.reason
                        break
            except discord.Forbidden:
                pass  # No audit log permission

            await self.event_logger.log_member_ban(
                guild=guild,
                user=user,
                moderator=moderator,
                reason=reason
            )
        except Exception as e:
            logger.error(f"Error logging member ban: {e}")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Log member unbans"""
        if not is_logging_enabled(guild.id, "members"):
            return

        try:
            # Try to get moderator from audit log
            moderator = None

            try:
                async for entry in guild.audit_logs(action=discord.AuditLogAction.unban, limit=5):
                    if entry.target.id == user.id:
                        moderator = entry.user
                        break
            except discord.Forbidden:
                pass  # No audit log permission

            await self.event_logger.log_member_unban(
                guild=guild,
                user=user,
                moderator=moderator
            )
        except Exception as e:
            logger.error(f"Error logging member unban: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log member updates (roles, nickname)"""
        if not is_logging_enabled(before.guild.id, "members"):
            return

        try:
            # Check for role changes
            added_roles = set(after.roles) - set(before.roles)
            removed_roles = set(before.roles) - set(after.roles)

            if added_roles or removed_roles:
                await self.event_logger.log_role_change(
                    member=after,
                    added_roles=list(added_roles),
                    removed_roles=list(removed_roles)
                )

            # Check for nickname changes
            if before.nick != after.nick:
                await self.event_logger.log_nickname_change(
                    member=after,
                    before_nick=before.nick,
                    after_nick=after.nick
                )

        except Exception as e:
            logger.error(f"Error logging member update: {e}")

    # ==================== VOICE EVENTS ====================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """Log voice state changes"""
        if not is_logging_enabled(member.guild.id, "voice"):
            return

        try:
            # Voice channel join
            if before.channel is None and after.channel is not None:
                await self.event_logger.log_voice_join(member, after.channel)

            # Voice channel leave
            elif before.channel is not None and after.channel is None:
                await self.event_logger.log_voice_leave(member, before.channel)

            # Voice channel move
            elif before.channel is not None and after.channel is not None and before.channel != after.channel:
                await self.event_logger.log_voice_move(member, before.channel, after.channel)

            # Self mute change
            if before.self_mute != after.self_mute:
                await self.event_logger.log_voice_mute(member, after.self_mute, server_mute=False)

            # Server mute change
            if before.mute != after.mute:
                await self.event_logger.log_voice_mute(member, after.mute, server_mute=True)

            # Self deafen change
            if before.self_deaf != after.self_deaf:
                await self.event_logger.log_voice_deafen(member, after.self_deaf, server_deafen=False)

            # Server deafen change
            if before.deaf != after.deaf:
                await self.event_logger.log_voice_deafen(member, after.deaf, server_deafen=True)

        except Exception as e:
            logger.error(f"Error logging voice state update: {e}")

    # ==================== SERVER EVENTS ====================

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Log channel creation"""
        if not is_logging_enabled(channel.guild.id, "server"):
            return

        try:
            await self.event_logger.log_channel_create(channel)
        except Exception as e:
            logger.error(f"Error logging channel create: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Log channel deletion"""
        if not is_logging_enabled(channel.guild.id, "server"):
            return

        try:
            await self.event_logger.log_channel_delete(channel)
        except Exception as e:
            logger.error(f"Error logging channel delete: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel
    ):
        """Log channel updates"""
        if not is_logging_enabled(after.guild.id, "server"):
            return

        try:
            await self.event_logger.log_channel_update(before, after)
        except Exception as e:
            logger.error(f"Error logging channel update: {e}")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Log role creation"""
        if not is_logging_enabled(role.guild.id, "server"):
            return

        try:
            await self.event_logger.log_role_create(role)
        except Exception as e:
            logger.error(f"Error logging role create: {e}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Log role deletion"""
        if not is_logging_enabled(role.guild.id, "server"):
            return

        try:
            await self.event_logger.log_role_delete(role)
        except Exception as e:
            logger.error(f"Error logging role delete: {e}")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Log role updates"""
        if not is_logging_enabled(after.guild.id, "server"):
            return

        try:
            await self.event_logger.log_role_update(before, after)
        except Exception as e:
            logger.error(f"Error logging role update: {e}")


# Required setup function
async def setup(bot: commands.Bot):
    """Add the EventListeners cog to the bot"""
    await bot.add_cog(EventListeners(bot))
    logger.info("Event listeners cog loaded - logging Discord events")
