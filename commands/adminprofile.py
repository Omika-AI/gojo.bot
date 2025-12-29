"""
/adminprofile Command
Display detailed profile stats for a Discord member with multiple pages
Only users with Administrator permission can use this command

Pages:
1. Profile Overview - Basic user info, badges, permissions
2. Warning History - All past warnings with reasons
3. Server Stats - Server-specific activity and stats
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from datetime import datetime
from typing import Optional

from utils.logger import log_command, logger
from utils.warnings_db import get_user_warnings


class AdminProfileView(View):
    """View with buttons to navigate between profile pages"""

    def __init__(self, bot: commands.Bot, target_user: discord.Member, requester: discord.Member, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.target_user = target_user
        self.requester = requester
        self.current_page = 1
        self.total_pages = 3
        self.warnings_page = 0  # For paginating through warnings
        self.warnings_per_page = 5

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original requester to use the buttons"""
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "Only the person who ran the command can use these buttons!",
                ephemeral=True
            )
            return False
        return True

    def get_page_embed(self) -> discord.Embed:
        """Get the embed for the current page"""
        if self.current_page == 1:
            return self._build_overview_embed()
        elif self.current_page == 2:
            return self._build_warnings_embed()
        elif self.current_page == 3:
            return self._build_server_stats_embed()
        return self._build_overview_embed()

    def _build_overview_embed(self) -> discord.Embed:
        """Build the profile overview embed (Page 1)"""
        user = self.target_user

        # Calculate account age
        account_created = user.created_at
        account_age = datetime.utcnow() - account_created.replace(tzinfo=None)
        account_age_days = account_age.days

        # Calculate time in server
        joined_at = user.joined_at
        if joined_at:
            time_in_server = datetime.utcnow() - joined_at.replace(tzinfo=None)
            time_in_server_days = time_in_server.days
        else:
            time_in_server_days = "Unknown"

        # Get user's roles (excluding @everyone)
        roles = [role.mention for role in user.roles if role.name != "@everyone"]
        roles_text = ", ".join(roles) if roles else "No roles"
        if len(roles_text) > 1024:
            roles_text = roles_text[:1000] + "... (truncated)"

        # Get key permissions
        permissions = []
        perms = user.guild_permissions
        if perms.administrator:
            permissions.append("👑 Administrator")
        if perms.manage_guild:
            permissions.append("⚙️ Manage Server")
        if perms.manage_roles:
            permissions.append("🎭 Manage Roles")
        if perms.manage_channels:
            permissions.append("📁 Manage Channels")
        if perms.manage_messages:
            permissions.append("📝 Manage Messages")
        if perms.kick_members:
            permissions.append("👢 Kick Members")
        if perms.ban_members:
            permissions.append("🔨 Ban Members")
        if perms.moderate_members:
            permissions.append("⏰ Timeout Members")
        if perms.mention_everyone:
            permissions.append("📢 Mention Everyone")
        permissions_text = "\n".join(permissions) if permissions else "No special permissions"

        # Get status
        status_emoji = {
            discord.Status.online: "🟢 Online",
            discord.Status.idle: "🟡 Idle",
            discord.Status.dnd: "🔴 Do Not Disturb",
            discord.Status.offline: "⚫ Offline"
        }
        status_text = status_emoji.get(user.status, "⚫ Unknown")

        # Bot status
        bot_status = "🤖 Yes" if user.bot else "👤 No"

        # Boost status
        if user.premium_since:
            boost_text = f"💎 Since {user.premium_since.strftime('%Y-%m-%d')}"
        else:
            boost_text = "Not boosting"

        # Build badges
        flags = user.public_flags
        badges = []
        if flags.staff:
            badges.append("⚡ Discord Staff")
        if flags.partner:
            badges.append("👑 Partner")
        if flags.hypesquad:
            badges.append("🏠 HypeSquad Events")
        if flags.bug_hunter:
            badges.append("🐛 Bug Hunter")
        if flags.bug_hunter_level_2:
            badges.append("🐛 Bug Hunter Level 2")
        if flags.hypesquad_bravery:
            badges.append("🟠 HypeSquad Bravery")
        if flags.hypesquad_brilliance:
            badges.append("🟣 HypeSquad Brilliance")
        if flags.hypesquad_balance:
            badges.append("🟢 HypeSquad Balance")
        if flags.early_supporter:
            badges.append("💎 Early Supporter")
        if flags.verified_bot_developer:
            badges.append("🤖 Verified Bot Developer")
        if flags.active_developer:
            badges.append("👨‍💻 Active Developer")
        if flags.discord_certified_moderator:
            badges.append("🛡️ Certified Moderator")
        if flags.verified_bot:
            badges.append("✅ Verified Bot")
        if user.premium_since:
            badges.append("💜 Server Booster")
        badges_text = "\n".join(badges) if badges else "None detected\n*(Nitro, Quest badges hidden by Discord)*"

        # Create embed
        embed = discord.Embed(
            title=f"📋 Profile: {user.display_name}",
            description="**Page 1/3** - Profile Overview",
            color=user.color if user.color != discord.Color.default() else discord.Color.blue()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(
            name="👤 Basic Info",
            value=f"**Username:** {user.name}\n**Display Name:** {user.display_name}\n**User ID:** `{user.id}`\n**Bot Account:** {bot_status}",
            inline=True
        )

        embed.add_field(
            name="📊 Status",
            value=f"**Current Status:** {status_text}\n**Top Role:** {user.top_role.mention}\n**Server Booster:** {boost_text}",
            inline=True
        )

        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(
            name="📅 Account Dates",
            value=f"**Created:** {account_created.strftime('%Y-%m-%d %H:%M')}\n**Account Age:** {account_age_days} days\n**Joined Server:** {joined_at.strftime('%Y-%m-%d %H:%M') if joined_at else 'Unknown'}\n**Time in Server:** {time_in_server_days} days",
            inline=True
        )

        embed.add_field(
            name="🏅 Discord Badges",
            value=badges_text,
            inline=True
        )

        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(name="🔐 Key Permissions", value=permissions_text, inline=False)
        embed.add_field(name=f"🎭 Roles ({len(roles)})", value=roles_text, inline=False)

        embed.set_footer(text=f"Requested by {self.requester} • Use buttons to navigate")

        return embed

    def _build_warnings_embed(self) -> discord.Embed:
        """Build the warning history embed (Page 2)"""
        user = self.target_user
        guild = user.guild

        # Get ALL warnings for this user
        all_warnings = get_user_warnings(guild.id, user.id)

        # Sort warnings by date (newest first)
        all_warnings_sorted = sorted(
            all_warnings,
            key=lambda w: w.get("timestamp", ""),
            reverse=True
        )

        total_warnings = len(all_warnings_sorted)

        # Calculate pagination for warnings
        total_warning_pages = max(1, (total_warnings + self.warnings_per_page - 1) // self.warnings_per_page)
        self.warnings_page = min(self.warnings_page, total_warning_pages - 1)
        self.warnings_page = max(0, self.warnings_page)

        start_idx = self.warnings_page * self.warnings_per_page
        end_idx = start_idx + self.warnings_per_page
        current_warnings = all_warnings_sorted[start_idx:end_idx]

        # Create embed
        embed = discord.Embed(
            title=f"⚠️ Warning History: {user.display_name}",
            description=f"**Page 2/3** - Warning History\n**Total Warnings:** {total_warnings}",
            color=discord.Color.orange() if total_warnings > 0 else discord.Color.green()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        if total_warnings == 0:
            embed.add_field(
                name="✅ Clean Record",
                value="This user has no warnings on record!",
                inline=False
            )
        else:
            # Show warning stats
            minor_count = sum(1 for w in all_warnings if "Minor" in w.get("type", ""))
            medium_count = sum(1 for w in all_warnings if "Medium" in w.get("type", ""))
            serious_count = sum(1 for w in all_warnings if "Serious" in w.get("type", ""))

            embed.add_field(
                name="📊 Warning Breakdown",
                value=f"🟢 Minor: **{minor_count}**\n🟡 Medium: **{medium_count}**\n🔴 Serious: **{serious_count}**",
                inline=True
            )

            # Calculate warning page info
            embed.add_field(
                name="📄 Viewing",
                value=f"Warnings **{start_idx + 1}-{min(end_idx, total_warnings)}** of **{total_warnings}**\n(Page {self.warnings_page + 1}/{total_warning_pages})",
                inline=True
            )

            embed.add_field(name="\u200b", value="\u200b", inline=True)

            # Display each warning
            for i, warning in enumerate(current_warnings, start=start_idx + 1):
                try:
                    ts = datetime.fromisoformat(warning.get("timestamp", ""))
                    date_str = ts.strftime("%Y-%m-%d %H:%M")
                except:
                    date_str = "Unknown date"

                warning_type = warning.get("type", "Unknown")
                reason = warning.get("reason", "No reason provided")
                warned_by = warning.get("warned_by", "Unknown")

                # Truncate reason if too long
                if len(reason) > 200:
                    reason = reason[:197] + "..."

                embed.add_field(
                    name=f"#{i} - {warning_type}",
                    value=f"**Date:** {date_str}\n**Reason:** {reason}\n**By:** {warned_by}",
                    inline=False
                )

        embed.set_footer(text=f"Requested by {self.requester} • Use ◀️ ▶️ to scroll warnings")

        return embed

    def _build_server_stats_embed(self) -> discord.Embed:
        """Build the server stats embed (Page 3)"""
        user = self.target_user
        guild = user.guild

        # Create embed
        embed = discord.Embed(
            title=f"📈 Server Stats: {user.display_name}",
            description=f"**Page 3/3** - Server Activity & Stats",
            color=discord.Color.purple()
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        # Join position (when they joined relative to others)
        members_sorted = sorted(guild.members, key=lambda m: m.joined_at or datetime.min)
        try:
            join_position = members_sorted.index(user) + 1
        except ValueError:
            join_position = "Unknown"

        # Calculate how long they've been a member
        if user.joined_at:
            time_in_server = datetime.utcnow() - user.joined_at.replace(tzinfo=None)
            years = time_in_server.days // 365
            months = (time_in_server.days % 365) // 30
            days = time_in_server.days % 30

            if years > 0:
                time_str = f"{years}y {months}m {days}d"
            elif months > 0:
                time_str = f"{months}m {days}d"
            else:
                time_str = f"{days} days"
        else:
            time_str = "Unknown"

        embed.add_field(
            name="📊 Membership",
            value=f"**Join Position:** #{join_position} of {guild.member_count}\n**Time in Server:** {time_str}\n**Joined:** {user.joined_at.strftime('%Y-%m-%d') if user.joined_at else 'Unknown'}",
            inline=True
        )

        # Role info
        user_roles = [r for r in user.roles if r.name != "@everyone"]
        highest_role = user.top_role
        hoisted_roles = [r for r in user_roles if r.hoist]

        embed.add_field(
            name="🎭 Role Info",
            value=f"**Total Roles:** {len(user_roles)}\n**Highest Role:** {highest_role.mention}\n**Displayed Roles:** {len(hoisted_roles)}",
            inline=True
        )

        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Communication permissions
        can_text = "✅" if user.guild_permissions.send_messages else "❌"
        can_voice = "✅" if user.guild_permissions.connect else "❌"
        can_stream = "✅" if user.guild_permissions.stream else "❌"
        can_attach = "✅" if user.guild_permissions.attach_files else "❌"
        can_embed = "✅" if user.guild_permissions.embed_links else "❌"
        can_react = "✅" if user.guild_permissions.add_reactions else "❌"

        embed.add_field(
            name="💬 Communication",
            value=f"{can_text} Send Messages\n{can_voice} Join Voice\n{can_stream} Stream\n{can_attach} Attach Files\n{can_embed} Embed Links\n{can_react} Add Reactions",
            inline=True
        )

        # Current voice state
        voice_state = user.voice
        if voice_state and voice_state.channel:
            voice_info = f"**Channel:** {voice_state.channel.mention}\n"
            voice_info += f"**Muted:** {'Yes' if voice_state.self_mute or voice_state.mute else 'No'}\n"
            voice_info += f"**Deafened:** {'Yes' if voice_state.self_deaf or voice_state.deaf else 'No'}\n"
            voice_info += f"**Streaming:** {'Yes' if voice_state.self_stream else 'No'}"
        else:
            voice_info = "Not in voice channel"

        embed.add_field(
            name="🔊 Voice Status",
            value=voice_info,
            inline=True
        )

        # Timeout status
        if user.timed_out_until:
            timeout_until = user.timed_out_until.strftime("%Y-%m-%d %H:%M")
            timeout_info = f"⏰ **Timed out until:**\n{timeout_until}"
        else:
            timeout_info = "✅ Not timed out"

        embed.add_field(
            name="🚫 Timeout Status",
            value=timeout_info,
            inline=True
        )

        # Get warning count for quick reference
        all_warnings = get_user_warnings(guild.id, user.id)
        warning_count = len(all_warnings)

        embed.add_field(
            name="⚠️ Warnings",
            value=f"**Total on Record:** {warning_count}\n*(See Page 2 for details)*",
            inline=True
        )

        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.set_footer(text=f"Requested by {self.requester} • Use buttons to navigate")

        return embed

    def update_buttons(self):
        """Update button states based on current page"""
        # Clear and re-add buttons with correct states
        self.clear_items()

        # Previous page button
        prev_btn = Button(label="◀️ Previous", style=discord.ButtonStyle.secondary, custom_id="prev_page")
        prev_btn.disabled = (self.current_page == 1)
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)

        # Page indicator (not clickable)
        page_btn = Button(label=f"Page {self.current_page}/{self.total_pages}", style=discord.ButtonStyle.primary, disabled=True)
        self.add_item(page_btn)

        # Next page button
        next_btn = Button(label="Next ▶️", style=discord.ButtonStyle.secondary, custom_id="next_page")
        next_btn.disabled = (self.current_page == self.total_pages)
        next_btn.callback = self.next_page
        self.add_item(next_btn)

        # Add warning navigation buttons on page 2
        if self.current_page == 2:
            all_warnings = get_user_warnings(self.target_user.guild.id, self.target_user.id)
            total_warnings = len(all_warnings)
            total_warning_pages = max(1, (total_warnings + self.warnings_per_page - 1) // self.warnings_per_page)

            if total_warning_pages > 1:
                # Previous warnings button
                prev_warn_btn = Button(label="⬅️ Older", style=discord.ButtonStyle.danger, custom_id="prev_warnings")
                prev_warn_btn.disabled = (self.warnings_page >= total_warning_pages - 1)
                prev_warn_btn.callback = self.prev_warnings
                self.add_item(prev_warn_btn)

                # Next warnings button
                next_warn_btn = Button(label="Newer ➡️", style=discord.ButtonStyle.success, custom_id="next_warnings")
                next_warn_btn.disabled = (self.warnings_page == 0)
                next_warn_btn.callback = self.next_warnings
                self.add_item(next_warn_btn)

    async def prev_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if self.current_page > 1:
            self.current_page -= 1
            self.warnings_page = 0  # Reset warnings pagination
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.warnings_page = 0  # Reset warnings pagination
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    async def prev_warnings(self, interaction: discord.Interaction):
        """Show older warnings"""
        self.warnings_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    async def next_warnings(self, interaction: discord.Interaction):
        """Show newer warnings"""
        if self.warnings_page > 0:
            self.warnings_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    async def on_timeout(self):
        """Disable all buttons when the view times out"""
        for item in self.children:
            item.disabled = True


class AdminProfile(commands.Cog):
    """Cog for the adminprofile command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="adminprofile", description="View detailed profile stats for a member (Admin only)")
    @app_commands.describe(user="The member to view profile stats for")
    async def adminprofile(self, interaction: discord.Interaction, user: discord.Member):
        """
        Slash command that displays detailed profile stats for a user with pagination
        Usage: /adminprofile @user
        Only administrators can use this command
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command=f"adminprofile {user}",
            guild=guild_name
        )

        # Check if the command is used in a server (not DMs)
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check if the user has Administrator permission
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need **Administrator** permission to use this command!",
                ephemeral=True
            )
            return

        try:
            # Create the paginated view
            view = AdminProfileView(self.bot, user, interaction.user)
            view.update_buttons()

            # Send the first page
            embed = view.get_page_embed()
            await interaction.response.send_message(embed=embed, view=view)

            logger.info(f"Admin profile viewed for {user} by {interaction.user}")

        except Exception as e:
            logger.error(f"Failed to get profile for {user}: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong while fetching the profile.",
                ephemeral=True
            )


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the AdminProfile cog to the bot"""
    await bot.add_cog(AdminProfile(bot))
