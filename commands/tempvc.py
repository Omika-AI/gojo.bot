"""
Temporary Voice Channel Commands - "Join to Create" Voice Channels

Commands:
- /tempvc setup - Set up the Join-to-Create channel (Admin)
- /tempvc disable - Disable temp VCs (Admin)
- /tempvc panel - Open control panel for your VC

Features:
- Users join a designated channel to create their own private VC
- VC owners can rename, set limits, lock, kick, allow, and ban users
- Channels are automatically deleted when empty
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
from typing import Optional

from utils.tempvc_db import (
    setup_join_to_create,
    get_join_to_create_channel,
    get_category_id,
    disable_join_to_create,
    create_temp_vc,
    delete_temp_vc,
    is_temp_vc,
    get_temp_vc_info,
    get_vc_owner,
    is_vc_owner,
    transfer_ownership,
    set_vc_name,
    set_vc_limit,
    set_vc_locked,
    is_vc_locked,
    allow_user,
    remove_allowed_user,
    is_user_allowed,
    ban_user,
    unban_user,
    is_user_banned,
    get_default_name,
    DEFAULT_VC_NAME,
    DEFAULT_USER_LIMIT,
    DEFAULT_BITRATE
)
from utils.logger import logger


# ============================================
# MODALS FOR USER INPUT
# ============================================

class RenameVCModal(Modal):
    """Modal for renaming a temp VC"""

    def __init__(self, channel: discord.VoiceChannel):
        super().__init__(title="Rename Your Voice Channel")
        self.channel = channel

        self.name_input = TextInput(
            label="New Channel Name",
            placeholder="Enter a new name for your channel...",
            default=channel.name,
            max_length=100,
            required=True
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.name_input.value.strip()

        if not new_name:
            await interaction.response.send_message(
                "Channel name cannot be empty!",
                ephemeral=True
            )
            return

        try:
            # Update Discord channel
            await self.channel.edit(name=new_name)

            # Update database
            set_vc_name(interaction.guild.id, self.channel.id, new_name)

            await interaction.response.send_message(
                f"Channel renamed to **{new_name}**!",
                ephemeral=True
            )
            logger.info(f"Temp VC {self.channel.id} renamed to '{new_name}' by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to rename this channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error renaming temp VC: {e}")
            await interaction.response.send_message(
                "An error occurred while renaming the channel.",
                ephemeral=True
            )


class SetLimitModal(Modal):
    """Modal for setting user limit on a temp VC"""

    def __init__(self, channel: discord.VoiceChannel):
        super().__init__(title="Set User Limit")
        self.channel = channel

        current_limit = channel.user_limit if channel.user_limit > 0 else "No limit"

        self.limit_input = TextInput(
            label="User Limit (0 = unlimited)",
            placeholder="Enter a number from 0-99...",
            default=str(channel.user_limit),
            max_length=2,
            required=True
        )
        self.add_item(self.limit_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(self.limit_input.value)
            if limit < 0 or limit > 99:
                raise ValueError("Invalid limit")
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number between 0 and 99!",
                ephemeral=True
            )
            return

        try:
            # Update Discord channel
            await self.channel.edit(user_limit=limit)

            # Update database
            set_vc_limit(interaction.guild.id, self.channel.id, limit)

            limit_text = f"**{limit}** users" if limit > 0 else "**unlimited**"
            await interaction.response.send_message(
                f"User limit set to {limit_text}!",
                ephemeral=True
            )
            logger.info(f"Temp VC {self.channel.id} limit set to {limit} by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to edit this channel!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error setting temp VC limit: {e}")
            await interaction.response.send_message(
                "An error occurred while setting the limit.",
                ephemeral=True
            )


# ============================================
# USER SELECT MENUS
# ============================================

class KickUserSelect(Select):
    """Select menu for kicking users from temp VC"""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        self.channel = channel
        self.owner_id = owner_id

        # Get members in the channel (excluding the owner)
        options = []
        for member in channel.members:
            if member.id != owner_id:
                options.append(discord.SelectOption(
                    label=member.display_name,
                    value=str(member.id),
                    description=f"Kick {member.display_name} from the channel"
                ))

        if not options:
            options.append(discord.SelectOption(
                label="No users to kick",
                value="none",
                description="You're the only one here!"
            ))

        super().__init__(
            placeholder="Select a user to kick...",
            options=options[:25],  # Discord limit
            custom_id="kick_user_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "There's no one to kick!",
                ephemeral=True
            )
            return

        user_id = int(self.values[0])
        member = interaction.guild.get_member(user_id)

        if member and member in self.channel.members:
            try:
                await member.move_to(None)  # Disconnect from voice
                await interaction.response.send_message(
                    f"**{member.display_name}** has been kicked from the channel!",
                    ephemeral=True
                )
                logger.info(f"User {member} kicked from temp VC {self.channel.id} by {interaction.user}")
            except discord.Forbidden:
                await interaction.response.send_message(
                    "I don't have permission to kick this user!",
                    ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "That user is no longer in the channel.",
                ephemeral=True
            )


class AllowUserSelect(Select):
    """Select menu for allowing users into locked temp VC"""

    def __init__(self, channel: discord.VoiceChannel, guild: discord.Guild):
        self.channel = channel

        # Get online members not in the channel
        options = []
        for member in guild.members:
            if not member.bot and member not in channel.members:
                options.append(discord.SelectOption(
                    label=member.display_name,
                    value=str(member.id),
                    description=f"Allow {member.display_name} to join"
                ))

        if not options:
            options.append(discord.SelectOption(
                label="No users available",
                value="none"
            ))

        super().__init__(
            placeholder="Select a user to allow...",
            options=options[:25],
            custom_id="allow_user_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "No users available to allow!",
                ephemeral=True
            )
            return

        user_id = int(self.values[0])
        member = interaction.guild.get_member(user_id)

        if member:
            # Add to database
            allow_user(interaction.guild.id, self.channel.id, user_id)

            # Update channel permissions
            await self.channel.set_permissions(member, connect=True)

            await interaction.response.send_message(
                f"**{member.display_name}** can now join your channel!",
                ephemeral=True
            )
            logger.info(f"User {member} allowed in temp VC {self.channel.id} by {interaction.user}")
        else:
            await interaction.response.send_message(
                "That user was not found.",
                ephemeral=True
            )


class BanUserSelect(Select):
    """Select menu for banning users from temp VC"""

    def __init__(self, channel: discord.VoiceChannel, guild: discord.Guild, owner_id: int):
        self.channel = channel
        self.owner_id = owner_id

        # Get members (excluding owner)
        options = []
        for member in guild.members:
            if not member.bot and member.id != owner_id:
                options.append(discord.SelectOption(
                    label=member.display_name,
                    value=str(member.id),
                    description=f"Ban {member.display_name} from joining"
                ))

        if not options:
            options.append(discord.SelectOption(
                label="No users available",
                value="none"
            ))

        super().__init__(
            placeholder="Select a user to ban...",
            options=options[:25],
            custom_id="ban_user_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "No users available to ban!",
                ephemeral=True
            )
            return

        user_id = int(self.values[0])
        member = interaction.guild.get_member(user_id)

        if member:
            # Add to database
            ban_user(interaction.guild.id, self.channel.id, user_id)

            # Update channel permissions
            await self.channel.set_permissions(member, connect=False)

            # Kick if in channel
            if member in self.channel.members:
                await member.move_to(None)

            await interaction.response.send_message(
                f"**{member.display_name}** has been banned from your channel!",
                ephemeral=True
            )
            logger.info(f"User {member} banned from temp VC {self.channel.id} by {interaction.user}")
        else:
            await interaction.response.send_message(
                "That user was not found.",
                ephemeral=True
            )


class TransferOwnerSelect(Select):
    """Select menu for transferring VC ownership"""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        self.channel = channel
        self.owner_id = owner_id

        # Get members in the channel (excluding the owner)
        options = []
        for member in channel.members:
            if member.id != owner_id and not member.bot:
                options.append(discord.SelectOption(
                    label=member.display_name,
                    value=str(member.id),
                    description=f"Transfer ownership to {member.display_name}"
                ))

        if not options:
            options.append(discord.SelectOption(
                label="No users available",
                value="none",
                description="No one else is in the channel!"
            ))

        super().__init__(
            placeholder="Select new owner...",
            options=options[:25],
            custom_id="transfer_owner_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "There's no one to transfer ownership to!",
                ephemeral=True
            )
            return

        new_owner_id = int(self.values[0])
        new_owner = interaction.guild.get_member(new_owner_id)

        if new_owner and new_owner in self.channel.members:
            # Update database
            transfer_ownership(interaction.guild.id, self.channel.id, new_owner_id)

            await interaction.response.send_message(
                f"Ownership transferred to **{new_owner.display_name}**!\n"
                f"They now control this channel.",
                ephemeral=True
            )

            # Notify new owner
            try:
                embed = discord.Embed(
                    title="You're Now the Channel Owner!",
                    description=f"**{interaction.user.display_name}** transferred ownership of **{self.channel.name}** to you.",
                    color=discord.Color.gold()
                )
                embed.add_field(
                    name="Controls",
                    value="Use `/tempvc panel` to manage your channel!",
                    inline=False
                )
                await new_owner.send(embed=embed)
            except discord.Forbidden:
                pass  # Can't DM user

            logger.info(f"Temp VC {self.channel.id} ownership transferred from {interaction.user} to {new_owner}")
        else:
            await interaction.response.send_message(
                "That user is no longer in the channel.",
                ephemeral=True
            )


# ============================================
# VC CONTROL PANEL VIEW
# ============================================

class VCControlPanel(View):
    """Main control panel for temp VC owners"""

    def __init__(self, channel: discord.VoiceChannel, owner_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.channel = channel
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only the owner can use these controls"""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the channel owner can use these controls!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.primary, emoji="✏️", row=0)
    async def rename_button(self, interaction: discord.Interaction, button: Button):
        """Open rename modal"""
        modal = RenameVCModal(self.channel)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Set Limit", style=discord.ButtonStyle.primary, emoji="👥", row=0)
    async def limit_button(self, interaction: discord.Interaction, button: Button):
        """Open user limit modal"""
        modal = SetLimitModal(self.channel)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Lock/Unlock", style=discord.ButtonStyle.secondary, emoji="🔒", row=0)
    async def lock_button(self, interaction: discord.Interaction, button: Button):
        """Toggle channel lock"""
        is_locked = is_vc_locked(interaction.guild.id, self.channel.id)

        try:
            # Toggle lock state
            everyone_role = interaction.guild.default_role

            if is_locked:
                # Unlock - allow everyone to connect
                await self.channel.set_permissions(everyone_role, connect=True)
                set_vc_locked(interaction.guild.id, self.channel.id, False)
                await interaction.response.send_message(
                    "Channel **unlocked**! Anyone can join now.",
                    ephemeral=True
                )
            else:
                # Lock - deny everyone, keep current members
                await self.channel.set_permissions(everyone_role, connect=False)

                # Allow current members
                for member in self.channel.members:
                    await self.channel.set_permissions(member, connect=True)

                set_vc_locked(interaction.guild.id, self.channel.id, True)
                await interaction.response.send_message(
                    "Channel **locked**! Only you can allow new users.",
                    ephemeral=True
                )

            logger.info(f"Temp VC {self.channel.id} {'unlocked' if is_locked else 'locked'} by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to modify channel permissions!",
                ephemeral=True
            )

    @discord.ui.button(label="Kick User", style=discord.ButtonStyle.danger, emoji="👢", row=1)
    async def kick_button(self, interaction: discord.Interaction, button: Button):
        """Open kick user select"""
        view = View(timeout=60)
        view.add_item(KickUserSelect(self.channel, self.owner_id))

        await interaction.response.send_message(
            "Select a user to kick:",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="Allow User", style=discord.ButtonStyle.success, emoji="✅", row=1)
    async def allow_button(self, interaction: discord.Interaction, button: Button):
        """Open allow user select"""
        view = View(timeout=60)
        view.add_item(AllowUserSelect(self.channel, interaction.guild))

        await interaction.response.send_message(
            "Select a user to allow into your locked channel:",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="Ban User", style=discord.ButtonStyle.danger, emoji="🚫", row=1)
    async def ban_button(self, interaction: discord.Interaction, button: Button):
        """Open ban user select"""
        view = View(timeout=60)
        view.add_item(BanUserSelect(self.channel, interaction.guild, self.owner_id))

        await interaction.response.send_message(
            "Select a user to ban from your channel:",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="Transfer", style=discord.ButtonStyle.secondary, emoji="👑", row=2)
    async def transfer_button(self, interaction: discord.Interaction, button: Button):
        """Open transfer ownership select"""
        view = View(timeout=60)
        view.add_item(TransferOwnerSelect(self.channel, self.owner_id))

        await interaction.response.send_message(
            "Select a user to transfer ownership to:",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="Delete Channel", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def delete_button(self, interaction: discord.Interaction, button: Button):
        """Delete the temp VC"""
        try:
            # Remove from database
            delete_temp_vc(interaction.guild.id, self.channel.id)

            # Delete the channel
            await self.channel.delete(reason=f"Deleted by owner {interaction.user}")

            await interaction.response.send_message(
                "Channel deleted!",
                ephemeral=True
            )
            logger.info(f"Temp VC {self.channel.id} deleted by owner {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to delete this channel!",
                ephemeral=True
            )


# ============================================
# MAIN COG
# ============================================

class TempVC(commands.Cog):
    """Temporary Voice Channel commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    tempvc_group = app_commands.Group(name="tempvc", description="Temporary voice channel commands")

    @tempvc_group.command(name="setup", description="Set up Join-to-Create voice channels")
    @app_commands.describe(
        channel="The voice channel users join to create their own VC",
        category="The category where temp VCs will be created"
    )
    @app_commands.default_permissions(administrator=True)
    async def tempvc_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        category: discord.CategoryChannel
    ):
        """Set up the Join-to-Create system"""

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check bot permissions
        bot_member = interaction.guild.me
        if not bot_member.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "I need **Manage Channels** permission to create temporary VCs!",
                ephemeral=True
            )
            return

        if not bot_member.guild_permissions.move_members:
            await interaction.response.send_message(
                "I need **Move Members** permission to manage temporary VCs!",
                ephemeral=True
            )
            return

        # Set up in database
        setup_join_to_create(interaction.guild.id, channel.id, category.id)

        embed = discord.Embed(
            title="Temporary VCs Configured!",
            description="Join-to-Create system is now active.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Join-to-Create Channel",
            value=channel.mention,
            inline=True
        )
        embed.add_field(
            name="VC Category",
            value=category.name,
            inline=True
        )
        embed.add_field(
            name="How It Works",
            value=(
                "1. Users join the Join-to-Create channel\n"
                "2. A new private VC is created for them\n"
                "3. They can rename, lock, and manage their VC\n"
                "4. When empty, the VC is automatically deleted"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed)
        logger.info(f"Temp VC system set up in {interaction.guild.name} by {interaction.user}")

    @tempvc_group.command(name="disable", description="Disable the Join-to-Create system")
    @app_commands.default_permissions(administrator=True)
    async def tempvc_disable(self, interaction: discord.Interaction):
        """Disable the Join-to-Create system"""

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        disable_join_to_create(interaction.guild.id)

        await interaction.response.send_message(
            "Join-to-Create system has been **disabled**.\n"
            "Existing temp VCs will remain until they're empty.",
            ephemeral=True
        )
        logger.info(f"Temp VC system disabled in {interaction.guild.name} by {interaction.user}")

    @tempvc_group.command(name="panel", description="Open the control panel for your voice channel")
    async def tempvc_panel(self, interaction: discord.Interaction):
        """Open the VC control panel"""

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check if user is in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "You need to be in a voice channel to use this!",
                ephemeral=True
            )
            return

        channel = interaction.user.voice.channel

        # Check if it's a temp VC
        if not is_temp_vc(interaction.guild.id, channel.id):
            await interaction.response.send_message(
                "This is not a temporary voice channel!",
                ephemeral=True
            )
            return

        # Check if user is the owner
        owner_id = get_vc_owner(interaction.guild.id, channel.id)
        if owner_id != interaction.user.id:
            owner = interaction.guild.get_member(owner_id)
            owner_name = owner.display_name if owner else "Unknown"
            await interaction.response.send_message(
                f"Only the channel owner (**{owner_name}**) can use the control panel!",
                ephemeral=True
            )
            return

        # Get channel info
        vc_info = get_temp_vc_info(interaction.guild.id, channel.id)
        is_locked = vc_info.get("locked", False)
        user_limit = channel.user_limit

        embed = discord.Embed(
            title=f"Control Panel: {channel.name}",
            description="Use the buttons below to manage your voice channel.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Status",
            value=f"{'Locked' if is_locked else 'Unlocked'}",
            inline=True
        )
        embed.add_field(
            name="User Limit",
            value=f"{user_limit if user_limit > 0 else 'Unlimited'}",
            inline=True
        )
        embed.add_field(
            name="Members",
            value=f"{len(channel.members)}",
            inline=True
        )

        view = VCControlPanel(channel, interaction.user.id)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"VC control panel opened for {channel.name} by {interaction.user}")


# Required setup function
async def setup(bot: commands.Bot):
    """Add the TempVC cog to the bot"""
    await bot.add_cog(TempVC(bot))
