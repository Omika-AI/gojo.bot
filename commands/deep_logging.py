"""
Deep Logging System - Comprehensive event tracking

Automatically logs:
- Message edits and deletions
- Member joins, leaves, bans, unbans
- Role and nickname changes
- Voice channel activity
- Channel/role create/delete/update
- Moderation actions

All events are sent to the configured logging channel via webhook.
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import aiohttp

from utils.event_logs_db import (
    is_logging_enabled,
    get_guild_config,
    save_event_log,
    format_event_emoji,
    format_category_color,
    cleanup_old_logs
)
from utils.logger import logger


class DeepLogging(commands.Cog):
    """Deep event logging system"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_cache = {}  # For storing messages before deletion
        self.cleanup_task.start()

    def cog_unload(self):
        self.cleanup_task.cancel()

    @tasks.loop(hours=24)
    async def cleanup_task(self):
        """Clean up old logs every 24 hours"""
        for guild in self.bot.guilds:
            if is_logging_enabled(guild.id):
                cleanup_old_logs(guild.id, days=30)

    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    async def send_log(self, guild_id: int, embed: discord.Embed):
        """Send a log message via webhook"""
        config = get_guild_config(guild_id)
        if not config or not config.get("webhook_url"):
            return

        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(
                    config["webhook_url"],
                    session=session
                )
                await webhook.send(embed=embed, username="Gojo Logger")
        except Exception as e:
            logger.error(f"Failed to send log: {e}")

    # ============================================
    # MESSAGE EVENTS
    # ============================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Cache messages for potential deletion logging"""
        if message.guild and not message.author.bot:
            key = f"{message.guild.id}_{message.id}"
            self.message_cache[key] = {
                "content": message.content,
                "author_id": message.author.id,
                "author_name": str(message.author),
                "channel_id": message.channel.id,
                "channel_name": message.channel.name,
                "timestamp": datetime.utcnow()
            }

            # Limit cache size
            if len(self.message_cache) > 10000:
                oldest = sorted(
                    self.message_cache.items(),
                    key=lambda x: x[1]["timestamp"]
                )[:1000]
                for k, _ in oldest:
                    del self.message_cache[k]

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log message edits"""
        if not before.guild or before.author.bot:
            return

        if not is_logging_enabled(before.guild.id, "messages"):
            return

        if before.content == after.content:
            return

        # Save to database
        save_event_log(
            guild_id=before.guild.id,
            category="messages",
            event_type="message_edit",
            user_id=before.author.id,
            user_name=str(before.author),
            user_display_name=before.author.display_name,
            channel_id=before.channel.id,
            channel_name=before.channel.name,
            before=before.content[:1000],
            after=after.content[:1000]
        )

        # Send webhook
        embed = discord.Embed(
            title=f"{format_event_emoji('message_edit')} Message Edited",
            color=format_category_color("messages"),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{before.author.mention} ({before.author})", inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before.content[:1000] or "*Empty*", inline=False)
        embed.add_field(name="After", value=after.content[:1000] or "*Empty*", inline=False)
        embed.add_field(name="Jump", value=f"[Go to message]({after.jump_url})", inline=False)
        embed.set_footer(text=f"User ID: {before.author.id}")

        await self.send_log(before.guild.id, embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log message deletions"""
        if not message.guild or message.author.bot:
            return

        if not is_logging_enabled(message.guild.id, "messages"):
            return

        # Get cached content if message wasn't cached before
        content = message.content
        author = message.author
        key = f"{message.guild.id}_{message.id}"

        if key in self.message_cache:
            cached = self.message_cache[key]
            content = cached["content"]
            del self.message_cache[key]

        save_event_log(
            guild_id=message.guild.id,
            category="messages",
            event_type="message_delete",
            user_id=author.id,
            user_name=str(author),
            user_display_name=author.display_name,
            channel_id=message.channel.id,
            channel_name=message.channel.name,
            before=content[:1000] if content else "*No content*"
        )

        embed = discord.Embed(
            title=f"{format_event_emoji('message_delete')} Message Deleted",
            color=format_category_color("messages"),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{author.mention} ({author})", inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Content", value=content[:1000] if content else "*No content*", inline=False)
        embed.set_footer(text=f"Message ID: {message.id}")

        await self.send_log(message.guild.id, embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list):
        """Log bulk message deletions"""
        if not messages:
            return

        message = messages[0]
        if not message.guild:
            return

        if not is_logging_enabled(message.guild.id, "messages"):
            return

        save_event_log(
            guild_id=message.guild.id,
            category="messages",
            event_type="bulk_delete",
            user_id=self.bot.user.id,
            user_name="System",
            channel_id=message.channel.id,
            channel_name=message.channel.name,
            details={"count": len(messages)}
        )

        embed = discord.Embed(
            title=f"{format_event_emoji('bulk_delete')} Bulk Delete",
            description=f"**{len(messages)}** messages were deleted",
            color=format_category_color("messages"),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)

        await self.send_log(message.guild.id, embed)

    # ============================================
    # MEMBER EVENTS
    # ============================================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Log member joins"""
        if not is_logging_enabled(member.guild.id, "members"):
            return

        save_event_log(
            guild_id=member.guild.id,
            category="members",
            event_type="member_join",
            user_id=member.id,
            user_name=str(member),
            user_display_name=member.display_name,
            details={
                "account_created": member.created_at.isoformat(),
                "member_count": member.guild.member_count
            }
        )

        embed = discord.Embed(
            title=f"{format_event_emoji('member_join')} Member Joined",
            color=format_category_color("members"),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="User", value=f"{member.mention} ({member})", inline=False)
        embed.add_field(name="Account Age", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Member Count", value=str(member.guild.member_count), inline=True)
        embed.set_footer(text=f"User ID: {member.id}")

        await self.send_log(member.guild.id, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leaves/kicks"""
        if not is_logging_enabled(member.guild.id, "members"):
            return

        save_event_log(
            guild_id=member.guild.id,
            category="members",
            event_type="member_leave",
            user_id=member.id,
            user_name=str(member),
            user_display_name=member.display_name,
            details={"roles": [r.name for r in member.roles[1:]]}  # Exclude @everyone
        )

        embed = discord.Embed(
            title=f"{format_event_emoji('member_leave')} Member Left",
            color=format_category_color("members"),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="User", value=f"{member.mention} ({member})", inline=False)

        if len(member.roles) > 1:
            roles = [r.mention for r in member.roles[1:]][:10]
            embed.add_field(name="Roles", value=" ".join(roles), inline=False)

        embed.set_footer(text=f"User ID: {member.id}")

        await self.send_log(member.guild.id, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Log member bans"""
        if not is_logging_enabled(guild.id, "members"):
            return

        save_event_log(
            guild_id=guild.id,
            category="members",
            event_type="member_ban",
            user_id=user.id,
            user_name=str(user)
        )

        embed = discord.Embed(
            title=f"{format_event_emoji('member_ban')} Member Banned",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="User", value=f"{user.mention} ({user})", inline=False)
        embed.set_footer(text=f"User ID: {user.id}")

        await self.send_log(guild.id, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Log member unbans"""
        if not is_logging_enabled(guild.id, "members"):
            return

        save_event_log(
            guild_id=guild.id,
            category="members",
            event_type="member_unban",
            user_id=user.id,
            user_name=str(user)
        )

        embed = discord.Embed(
            title=f"{format_event_emoji('member_unban')} Member Unbanned",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user.mention} ({user})", inline=False)
        embed.set_footer(text=f"User ID: {user.id}")

        await self.send_log(guild.id, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log role and nickname changes"""
        if not is_logging_enabled(before.guild.id, "members"):
            return

        # Nickname change
        if before.nick != after.nick:
            save_event_log(
                guild_id=before.guild.id,
                category="members",
                event_type="member_nickname_change",
                user_id=after.id,
                user_name=str(after),
                before=before.nick or before.name,
                after=after.nick or after.name
            )

            embed = discord.Embed(
                title=f"{format_event_emoji('member_nickname_change')} Nickname Changed",
                color=format_category_color("members"),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{after.mention} ({after})", inline=False)
            embed.add_field(name="Before", value=before.nick or "*No nickname*", inline=True)
            embed.add_field(name="After", value=after.nick or "*No nickname*", inline=True)
            embed.set_footer(text=f"User ID: {after.id}")

            await self.send_log(before.guild.id, embed)

        # Role changes
        before_roles = set(before.roles)
        after_roles = set(after.roles)

        added = after_roles - before_roles
        removed = before_roles - after_roles

        if added:
            for role in added:
                save_event_log(
                    guild_id=before.guild.id,
                    category="members",
                    event_type="member_role_add",
                    user_id=after.id,
                    user_name=str(after),
                    details={"role_id": role.id, "role_name": role.name}
                )

            embed = discord.Embed(
                title=f"{format_event_emoji('member_role_add')} Roles Added",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{after.mention} ({after})", inline=False)
            embed.add_field(name="Roles Added", value=" ".join(r.mention for r in added), inline=False)
            embed.set_footer(text=f"User ID: {after.id}")

            await self.send_log(before.guild.id, embed)

        if removed:
            for role in removed:
                save_event_log(
                    guild_id=before.guild.id,
                    category="members",
                    event_type="member_role_remove",
                    user_id=after.id,
                    user_name=str(after),
                    details={"role_id": role.id, "role_name": role.name}
                )

            embed = discord.Embed(
                title=f"{format_event_emoji('member_role_remove')} Roles Removed",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{after.mention} ({after})", inline=False)
            embed.add_field(name="Roles Removed", value=" ".join(r.mention for r in removed), inline=False)
            embed.set_footer(text=f"User ID: {after.id}")

            await self.send_log(before.guild.id, embed)

    # ============================================
    # VOICE EVENTS
    # ============================================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """Log voice channel activity"""
        if not is_logging_enabled(member.guild.id, "voice"):
            return

        # Join
        if before.channel is None and after.channel is not None:
            save_event_log(
                guild_id=member.guild.id,
                category="voice",
                event_type="voice_join",
                user_id=member.id,
                user_name=str(member),
                channel_id=after.channel.id,
                channel_name=after.channel.name
            )

            embed = discord.Embed(
                title=f"{format_event_emoji('voice_join')} Voice Join",
                color=format_category_color("voice"),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member.mention}", inline=True)
            embed.add_field(name="Channel", value=after.channel.mention, inline=True)
            embed.set_footer(text=f"User ID: {member.id}")

            await self.send_log(member.guild.id, embed)

        # Leave
        elif before.channel is not None and after.channel is None:
            save_event_log(
                guild_id=member.guild.id,
                category="voice",
                event_type="voice_leave",
                user_id=member.id,
                user_name=str(member),
                channel_id=before.channel.id,
                channel_name=before.channel.name
            )

            embed = discord.Embed(
                title=f"{format_event_emoji('voice_leave')} Voice Leave",
                color=format_category_color("voice"),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member.mention}", inline=True)
            embed.add_field(name="Channel", value=before.channel.mention, inline=True)
            embed.set_footer(text=f"User ID: {member.id}")

            await self.send_log(member.guild.id, embed)

        # Move
        elif before.channel != after.channel and before.channel is not None and after.channel is not None:
            save_event_log(
                guild_id=member.guild.id,
                category="voice",
                event_type="voice_move",
                user_id=member.id,
                user_name=str(member),
                before=before.channel.name,
                after=after.channel.name
            )

            embed = discord.Embed(
                title=f"{format_event_emoji('voice_move')} Voice Move",
                color=format_category_color("voice"),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{member.mention}", inline=False)
            embed.add_field(name="From", value=before.channel.mention, inline=True)
            embed.add_field(name="To", value=after.channel.mention, inline=True)
            embed.set_footer(text=f"User ID: {member.id}")

            await self.send_log(member.guild.id, embed)

    # ============================================
    # SERVER EVENTS
    # ============================================

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Log channel creation"""
        if not is_logging_enabled(channel.guild.id, "server"):
            return

        save_event_log(
            guild_id=channel.guild.id,
            category="server",
            event_type="channel_create",
            user_id=self.bot.user.id,
            user_name="System",
            channel_id=channel.id,
            channel_name=channel.name,
            details={"type": str(channel.type)}
        )

        embed = discord.Embed(
            title=f"{format_event_emoji('channel_create')} Channel Created",
            color=format_category_color("server"),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Type", value=str(channel.type), inline=True)
        embed.set_footer(text=f"Channel ID: {channel.id}")

        await self.send_log(channel.guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Log channel deletion"""
        if not is_logging_enabled(channel.guild.id, "server"):
            return

        save_event_log(
            guild_id=channel.guild.id,
            category="server",
            event_type="channel_delete",
            user_id=self.bot.user.id,
            user_name="System",
            channel_id=channel.id,
            channel_name=channel.name
        )

        embed = discord.Embed(
            title=f"{format_event_emoji('channel_delete')} Channel Deleted",
            color=format_category_color("server"),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Channel", value=f"#{channel.name}", inline=True)
        embed.add_field(name="Type", value=str(channel.type), inline=True)
        embed.set_footer(text=f"Channel ID: {channel.id}")

        await self.send_log(channel.guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Log role creation"""
        if not is_logging_enabled(role.guild.id, "server"):
            return

        save_event_log(
            guild_id=role.guild.id,
            category="server",
            event_type="role_create",
            user_id=self.bot.user.id,
            user_name="System",
            details={"role_id": role.id, "role_name": role.name}
        )

        embed = discord.Embed(
            title=f"{format_event_emoji('role_create')} Role Created",
            color=role.color if role.color.value else format_category_color("server"),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Role", value=role.mention, inline=True)
        embed.set_footer(text=f"Role ID: {role.id}")

        await self.send_log(role.guild.id, embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Log role deletion"""
        if not is_logging_enabled(role.guild.id, "server"):
            return

        save_event_log(
            guild_id=role.guild.id,
            category="server",
            event_type="role_delete",
            user_id=self.bot.user.id,
            user_name="System",
            details={"role_name": role.name}
        )

        embed = discord.Embed(
            title=f"{format_event_emoji('role_delete')} Role Deleted",
            color=format_category_color("server"),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Role", value=f"@{role.name}", inline=True)
        embed.set_footer(text=f"Role ID: {role.id}")

        await self.send_log(role.guild.id, embed)


async def setup(bot: commands.Bot):
    """Add the DeepLogging cog to the bot"""
    await bot.add_cog(DeepLogging(bot))
