"""
Reaction Roles System - Self-assign roles via buttons or dropdowns

Commands:
- /reactionrole create - Create a new reaction role panel
- /reactionrole addrole - Add a role to an existing panel
- /reactionrole removerole - Remove a role from a panel
- /reactionrole delete - Delete a reaction role panel
- /reactionrole list - List all reaction role panels
- /reactionrole edit - Edit panel title/description

Modes:
- single: Users can only have ONE role from the panel
- multiple: Users can have MULTIPLE roles from the panel
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
from typing import Optional, Literal, List

from utils.reaction_roles_db import (
    create_reaction_panel,
    delete_reaction_panel,
    get_panel_by_message,
    get_all_panels,
    add_role_to_panel,
    remove_role_from_panel,
    update_panel_mode
)
from utils.logger import logger


# ============================================
# VIEW COMPONENTS
# ============================================

class RoleButton(Button):
    """A button for reaction roles"""

    def __init__(self, role_id: int, emoji: str, label: str, mode: str):
        self.role_id = role_id
        self.mode = mode
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=label,
            emoji=emoji if emoji else None,
            custom_id=f"rrole_{role_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle button click"""
        role = interaction.guild.get_role(self.role_id)

        if not role:
            await interaction.response.send_message(
                "This role no longer exists!",
                ephemeral=True
            )
            return

        member = interaction.user

        # Check if user has the role
        if role in member.roles:
            # Remove role
            try:
                await member.remove_roles(role, reason="Reaction role removed")
                await interaction.response.send_message(
                    f"Removed the **{role.name}** role!",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "I don't have permission to remove this role!",
                    ephemeral=True
                )
        else:
            # Add role (check mode for single-select)
            if self.mode == "single":
                # Get panel to find other roles
                panel = get_panel_by_message(interaction.guild.id, interaction.message.id)
                if panel:
                    # Remove other roles from panel first
                    for role_data in panel["roles"]:
                        other_role = interaction.guild.get_role(role_data["role_id"])
                        if other_role and other_role in member.roles and other_role.id != self.role_id:
                            try:
                                await member.remove_roles(other_role, reason="Single-select reaction role swap")
                            except discord.Forbidden:
                                pass

            try:
                await member.add_roles(role, reason="Reaction role added")
                await interaction.response.send_message(
                    f"Added the **{role.name}** role!",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "I don't have permission to add this role!",
                    ephemeral=True
                )


class RoleSelect(Select):
    """A dropdown for reaction roles"""

    def __init__(self, roles: List[dict], mode: str, guild: discord.Guild):
        self.mode = mode
        self.guild = guild

        options = []
        for role_data in roles[:25]:  # Max 25 options
            role = guild.get_role(role_data["role_id"])
            if role:
                options.append(discord.SelectOption(
                    label=role_data["label"] or role.name,
                    value=str(role_data["role_id"]),
                    description=role_data.get("description", "")[:100] if role_data.get("description") else None,
                    emoji=role_data["emoji"] if role_data.get("emoji") else None
                ))

        super().__init__(
            placeholder="Select a role...",
            min_values=0,
            max_values=len(options) if mode == "multiple" else 1,
            options=options,
            custom_id="rrole_select"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle dropdown selection"""
        member = interaction.user

        # Get selected role IDs
        selected_ids = set(int(v) for v in self.values)

        # Get all role IDs from the dropdown
        all_role_ids = set(int(opt.value) for opt in self.options)

        # Determine roles to add and remove
        roles_to_add = []
        roles_to_remove = []

        for role_id in all_role_ids:
            role = self.guild.get_role(role_id)
            if not role:
                continue

            if role_id in selected_ids and role not in member.roles:
                roles_to_add.append(role)
            elif role_id not in selected_ids and role in member.roles:
                roles_to_remove.append(role)

        try:
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason="Reaction role added")
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Reaction role removed")

            # Build response message
            changes = []
            if roles_to_add:
                changes.append(f"Added: {', '.join(r.name for r in roles_to_add)}")
            if roles_to_remove:
                changes.append(f"Removed: {', '.join(r.name for r in roles_to_remove)}")

            if changes:
                await interaction.response.send_message(
                    "\n".join(changes),
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "No role changes made.",
                    ephemeral=True
                )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to manage these roles!",
                ephemeral=True
            )


class ReactionRoleView(View):
    """Persistent view for reaction roles"""

    def __init__(self, panel: dict, guild: discord.Guild):
        super().__init__(timeout=None)

        if panel["panel_type"] == "buttons":
            # Add buttons for each role
            for role_data in panel["roles"][:25]:
                self.add_item(RoleButton(
                    role_id=role_data["role_id"],
                    emoji=role_data.get("emoji", ""),
                    label=role_data.get("label", ""),
                    mode=panel["mode"]
                ))
        else:
            # Add dropdown
            self.add_item(RoleSelect(
                roles=panel["roles"],
                mode=panel["mode"],
                guild=guild
            ))


# ============================================
# COG
# ============================================

class ReactionRoles(commands.Cog):
    """Reaction role system with buttons and dropdowns"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Register persistent views on cog load"""
        # This will be called when the cog is loaded
        # We need to restore views for all panels
        for guild in self.bot.guilds:
            panels = get_all_panels(guild.id)
            for panel in panels:
                view = ReactionRoleView(panel, guild)
                self.bot.add_view(view, message_id=panel["message_id"])

    # ============================================
    # COMMAND GROUP
    # ============================================

    reactionrole_group = app_commands.Group(
        name="reactionrole",
        description="Create and manage self-assign role panels"
    )

    @reactionrole_group.command(name="create", description="Create a new reaction role panel")
    @app_commands.describe(
        panel_type="Use buttons or a dropdown menu",
        mode="Single role or multiple roles allowed",
        title="Panel title",
        description="Panel description"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def rr_create(
        self,
        interaction: discord.Interaction,
        panel_type: Literal["buttons", "dropdown"],
        mode: Literal["single", "multiple"],
        title: str,
        description: Optional[str] = None
    ):
        """Create a new reaction role panel"""
        await interaction.response.defer()

        # Create the embed
        embed = discord.Embed(
            title=title,
            description=description or "Click below to get your roles!",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Mode: {mode.capitalize()} select")

        # Send the message first (without view - will add roles later)
        msg = await interaction.channel.send(embed=embed)

        # Create panel in database
        success, message = create_reaction_panel(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=msg.id,
            panel_type=panel_type,
            title=title,
            description=description or "",
            roles=[],
            mode=mode,
            created_by=interaction.user.id
        )

        if success:
            await interaction.followup.send(
                f"Reaction role panel created!\n"
                f"Now add roles using `/reactionrole addrole`\n"
                f"Message ID: `{msg.id}`",
                ephemeral=True
            )
            logger.info(f"Reaction role panel created in {interaction.guild.name}")
        else:
            await msg.delete()
            await interaction.followup.send(message, ephemeral=True)

    @reactionrole_group.command(name="addrole", description="Add a role to a reaction role panel")
    @app_commands.describe(
        message_id="The message ID of the panel",
        role="The role to add",
        emoji="Emoji for the button/option (optional)",
        label="Button label or option text (optional)"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def rr_addrole(
        self,
        interaction: discord.Interaction,
        message_id: str,
        role: discord.Role,
        emoji: Optional[str] = None,
        label: Optional[str] = None
    ):
        """Add a role to a panel"""
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message(
                "Invalid message ID!",
                ephemeral=True
            )
            return

        # Check if role can be assigned
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "I can't assign this role - it's higher than my highest role!",
                ephemeral=True
            )
            return

        if role.managed:
            await interaction.response.send_message(
                "This role is managed by an integration and cannot be assigned!",
                ephemeral=True
            )
            return

        # Add role to panel
        success, message = add_role_to_panel(
            guild_id=interaction.guild.id,
            message_id=msg_id,
            role_id=role.id,
            emoji=emoji or "",
            label=label or role.name,
            description=""
        )

        if not success:
            await interaction.response.send_message(message, ephemeral=True)
            return

        # Update the message with new view
        panel = get_panel_by_message(interaction.guild.id, msg_id)
        if panel:
            try:
                channel = interaction.guild.get_channel(panel["channel_id"])
                msg = await channel.fetch_message(msg_id)

                # Create new view
                view = ReactionRoleView(panel, interaction.guild)

                # Update embed with role list
                embed = msg.embeds[0] if msg.embeds else discord.Embed(title=panel["title"])

                role_list = []
                for rd in panel["roles"]:
                    r = interaction.guild.get_role(rd["role_id"])
                    if r:
                        role_list.append(f"{rd.get('emoji', '')} {r.mention}")

                if role_list:
                    embed.clear_fields()
                    embed.add_field(name="Available Roles", value="\n".join(role_list), inline=False)

                await msg.edit(embed=embed, view=view)
                self.bot.add_view(view, message_id=msg_id)

                await interaction.response.send_message(
                    f"Added {role.mention} to the panel!",
                    ephemeral=True
                )
                logger.info(f"Role {role.name} added to reaction panel in {interaction.guild.name}")

            except discord.NotFound:
                await interaction.response.send_message(
                    "Could not find the panel message!",
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"Error updating panel: {e}",
                    ephemeral=True
                )
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @reactionrole_group.command(name="removerole", description="Remove a role from a panel")
    @app_commands.describe(
        message_id="The message ID of the panel",
        role="The role to remove"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def rr_removerole(
        self,
        interaction: discord.Interaction,
        message_id: str,
        role: discord.Role
    ):
        """Remove a role from a panel"""
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
            return

        success, message = remove_role_from_panel(
            guild_id=interaction.guild.id,
            message_id=msg_id,
            role_id=role.id
        )

        if not success:
            await interaction.response.send_message(message, ephemeral=True)
            return

        # Update the message
        panel = get_panel_by_message(interaction.guild.id, msg_id)
        if panel:
            try:
                channel = interaction.guild.get_channel(panel["channel_id"])
                msg = await channel.fetch_message(msg_id)

                view = ReactionRoleView(panel, interaction.guild)

                # Update embed
                embed = msg.embeds[0] if msg.embeds else discord.Embed(title=panel["title"])

                role_list = []
                for rd in panel["roles"]:
                    r = interaction.guild.get_role(rd["role_id"])
                    if r:
                        role_list.append(f"{rd.get('emoji', '')} {r.mention}")

                embed.clear_fields()
                if role_list:
                    embed.add_field(name="Available Roles", value="\n".join(role_list), inline=False)
                else:
                    embed.add_field(name="Roles", value="No roles configured", inline=False)

                await msg.edit(embed=embed, view=view)
                self.bot.add_view(view, message_id=msg_id)

                await interaction.response.send_message(
                    f"Removed {role.mention} from the panel!",
                    ephemeral=True
                )

            except Exception as e:
                await interaction.response.send_message(f"Error: {e}", ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @reactionrole_group.command(name="delete", description="Delete a reaction role panel")
    @app_commands.describe(message_id="The message ID of the panel to delete")
    @app_commands.default_permissions(manage_roles=True)
    async def rr_delete(self, interaction: discord.Interaction, message_id: str):
        """Delete a reaction role panel"""
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
            return

        panel = get_panel_by_message(interaction.guild.id, msg_id)

        if not panel:
            await interaction.response.send_message("Panel not found!", ephemeral=True)
            return

        # Delete from database
        success, message = delete_reaction_panel(interaction.guild.id, msg_id)

        if success:
            # Try to delete the message too
            try:
                channel = interaction.guild.get_channel(panel["channel_id"])
                msg = await channel.fetch_message(msg_id)
                await msg.delete()
            except:
                pass

            await interaction.response.send_message(
                "Reaction role panel deleted!",
                ephemeral=True
            )
            logger.info(f"Reaction role panel deleted in {interaction.guild.name}")
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @reactionrole_group.command(name="list", description="List all reaction role panels")
    @app_commands.default_permissions(manage_roles=True)
    async def rr_list(self, interaction: discord.Interaction):
        """List all panels"""
        panels = get_all_panels(interaction.guild.id)

        if not panels:
            await interaction.response.send_message(
                "No reaction role panels have been created yet!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Reaction Role Panels",
            color=discord.Color.blue()
        )

        for i, panel in enumerate(panels[:25], 1):
            channel = interaction.guild.get_channel(panel["channel_id"])
            roles_count = len(panel["roles"])

            embed.add_field(
                name=f"{i}. {panel['title']}",
                value=(
                    f"Channel: {channel.mention if channel else 'Unknown'}\n"
                    f"Type: {panel['panel_type']} | Mode: {panel['mode']}\n"
                    f"Roles: {roles_count} | Message ID: `{panel['message_id']}`"
                ),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @reactionrole_group.command(name="mode", description="Change panel mode (single/multiple)")
    @app_commands.describe(
        message_id="The message ID of the panel",
        mode="New selection mode"
    )
    @app_commands.default_permissions(manage_roles=True)
    async def rr_mode(
        self,
        interaction: discord.Interaction,
        message_id: str,
        mode: Literal["single", "multiple"]
    ):
        """Change panel mode"""
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
            return

        success, message = update_panel_mode(interaction.guild.id, msg_id, mode)

        if success:
            # Update the view
            panel = get_panel_by_message(interaction.guild.id, msg_id)
            if panel:
                try:
                    channel = interaction.guild.get_channel(panel["channel_id"])
                    msg = await channel.fetch_message(msg_id)

                    view = ReactionRoleView(panel, interaction.guild)

                    # Update footer
                    embed = msg.embeds[0] if msg.embeds else discord.Embed(title=panel["title"])
                    embed.set_footer(text=f"Mode: {mode.capitalize()} select")

                    await msg.edit(embed=embed, view=view)
                    self.bot.add_view(view, message_id=msg_id)

                except Exception as e:
                    logger.error(f"Error updating panel: {e}")

            await interaction.response.send_message(
                f"Panel mode changed to **{mode}**!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    """Add the ReactionRoles cog to the bot"""
    await bot.add_cog(ReactionRoles(bot))
