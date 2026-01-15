"""
Custom Commands System - Admin-defined command responses

Commands:
- /customcmd create - Create a new custom command
- /customcmd delete - Delete a custom command
- /customcmd edit - Edit an existing custom command
- /customcmd list - List all custom commands
- /customcmd info - View details of a custom command
- /customcmd prefix - Set the trigger prefix (default: !)

How it works:
1. Admins create commands like "rules" with a response
2. Users type !rules (or whatever prefix is set)
3. Bot responds with the configured message

Supported response types:
- text: Simple text message
- embed: Rich embed message
- role_add: Add a role to the user
- role_remove: Remove a role from the user
- image: Send an image from URL
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal

from utils.custom_commands_db import (
    create_custom_command,
    delete_custom_command,
    edit_custom_command,
    get_custom_command,
    list_custom_commands,
    get_command_count,
    increment_command_uses
)
from utils.server_config_db import get_full_config, _load_data, _save_data, _ensure_guild
from utils.logger import logger


class CustomCommands(commands.Cog):
    """Custom command system for server admins"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ============================================
    # HELPER FUNCTIONS
    # ============================================

    def get_prefix(self, guild_id: int) -> str:
        """Get the custom command prefix for a guild"""
        data = _load_data()
        guild_str = str(guild_id)
        if guild_str in data["guilds"]:
            return data["guilds"][guild_str].get("custom_cmd_prefix", "!")
        return "!"

    def set_prefix(self, guild_id: int, prefix: str) -> tuple[bool, str]:
        """Set the custom command prefix"""
        data = _load_data()
        guild_data = _ensure_guild(data, guild_id)
        guild_data["custom_cmd_prefix"] = prefix
        _save_data(data)
        return True, f"Custom command prefix set to `{prefix}`"

    # ============================================
    # COMMAND GROUP
    # ============================================

    customcmd_group = app_commands.Group(
        name="customcmd",
        description="Create and manage custom commands"
    )

    @customcmd_group.command(name="create", description="Create a new custom command")
    @app_commands.describe(
        name="Command trigger name (e.g., 'rules')",
        response_type="Type of response",
        content="The response content (text, embed description, or image URL)",
        role="Role to add/remove (only for role_add/role_remove types)",
        embed_title="Title for embed response",
        embed_color="Color for embed (hex like #FF5733)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def customcmd_create(
        self,
        interaction: discord.Interaction,
        name: str,
        response_type: Literal["text", "embed", "role_add", "role_remove", "image"],
        content: str,
        role: Optional[discord.Role] = None,
        embed_title: Optional[str] = None,
        embed_color: Optional[str] = None
    ):
        """Create a new custom command"""
        # Validate role for role commands
        if response_type in ["role_add", "role_remove"] and not role:
            await interaction.response.send_message(
                "You must specify a role for role_add/role_remove commands!",
                ephemeral=True
            )
            return

        # Build embed data if applicable
        embed_data = None
        if response_type == "embed":
            embed_data = {
                "title": embed_title or name.capitalize(),
                "description": content,
                "color": embed_color or "#5865F2"
            }

        role_id = role.id if role else None

        success, message = create_custom_command(
            guild_id=interaction.guild.id,
            command_name=name,
            response_type=response_type,
            response_content=content,
            created_by=interaction.user.id,
            embed_data=embed_data,
            role_id=role_id
        )

        if success:
            prefix = self.get_prefix(interaction.guild.id)
            embed = discord.Embed(
                title="Custom Command Created",
                description=f"Command `{prefix}{name}` has been created!",
                color=discord.Color.green()
            )
            embed.add_field(name="Type", value=response_type, inline=True)
            embed.add_field(name="Trigger", value=f"`{prefix}{name}`", inline=True)
            if role:
                embed.add_field(name="Role", value=role.mention, inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Custom command '{name}' created in {interaction.guild.name}")
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @customcmd_group.command(name="delete", description="Delete a custom command")
    @app_commands.describe(name="Command name to delete")
    @app_commands.default_permissions(manage_guild=True)
    async def customcmd_delete(self, interaction: discord.Interaction, name: str):
        """Delete a custom command"""
        success, message = delete_custom_command(interaction.guild.id, name)

        if success:
            embed = discord.Embed(
                title="Command Deleted",
                description=f"Custom command `{name}` has been deleted.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Custom command '{name}' deleted in {interaction.guild.name}")
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @customcmd_group.command(name="edit", description="Edit an existing custom command")
    @app_commands.describe(
        name="Command name to edit",
        content="New response content",
        response_type="New response type",
        role="New role (for role commands)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def customcmd_edit(
        self,
        interaction: discord.Interaction,
        name: str,
        content: Optional[str] = None,
        response_type: Optional[Literal["text", "embed", "role_add", "role_remove", "image"]] = None,
        role: Optional[discord.Role] = None
    ):
        """Edit an existing custom command"""
        if not any([content, response_type, role]):
            await interaction.response.send_message(
                "You must provide at least one field to edit!",
                ephemeral=True
            )
            return

        embed_data = None
        if response_type == "embed" and content:
            embed_data = {
                "title": name.capitalize(),
                "description": content,
                "color": "#5865F2"
            }

        role_id = role.id if role else None

        success, message = edit_custom_command(
            guild_id=interaction.guild.id,
            command_name=name,
            response_content=content,
            response_type=response_type,
            embed_data=embed_data,
            role_id=role_id
        )

        if success:
            embed = discord.Embed(
                title="Command Updated",
                description=f"Custom command `{name}` has been updated.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Custom command '{name}' edited in {interaction.guild.name}")
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @customcmd_group.command(name="list", description="List all custom commands")
    @app_commands.default_permissions(manage_guild=True)
    async def customcmd_list(self, interaction: discord.Interaction):
        """List all custom commands"""
        commands_list = list_custom_commands(interaction.guild.id)
        prefix = self.get_prefix(interaction.guild.id)

        if not commands_list:
            await interaction.response.send_message(
                "No custom commands have been created yet.\n"
                f"Use `/customcmd create` to create one!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Custom Commands",
            description=f"Prefix: `{prefix}`\nTotal: {len(commands_list)} commands",
            color=discord.Color.blue()
        )

        # Group by type
        by_type = {}
        for cmd in commands_list:
            cmd_type = cmd["response_type"]
            if cmd_type not in by_type:
                by_type[cmd_type] = []
            by_type[cmd_type].append(cmd)

        for cmd_type, cmds in by_type.items():
            cmd_list = ", ".join([f"`{prefix}{c['name']}`" for c in cmds])
            embed.add_field(
                name=f"{cmd_type.replace('_', ' ').title()} ({len(cmds)})",
                value=cmd_list[:1024],
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @customcmd_group.command(name="info", description="View details of a custom command")
    @app_commands.describe(name="Command name")
    @app_commands.default_permissions(manage_guild=True)
    async def customcmd_info(self, interaction: discord.Interaction, name: str):
        """View command details"""
        cmd = get_custom_command(interaction.guild.id, name)

        if not cmd:
            await interaction.response.send_message(
                f"Command `{name}` not found.",
                ephemeral=True
            )
            return

        prefix = self.get_prefix(interaction.guild.id)
        creator = interaction.guild.get_member(cmd["created_by"])

        embed = discord.Embed(
            title=f"Command: {prefix}{name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Type", value=cmd["response_type"], inline=True)
        embed.add_field(name="Uses", value=str(cmd["uses"]), inline=True)
        embed.add_field(
            name="Created By",
            value=creator.mention if creator else "Unknown",
            inline=True
        )

        # Show content preview
        content = cmd["response_content"]
        if len(content) > 200:
            content = content[:200] + "..."
        embed.add_field(name="Content", value=content, inline=False)

        if cmd.get("role_id"):
            role = interaction.guild.get_role(cmd["role_id"])
            embed.add_field(
                name="Role",
                value=role.mention if role else "Deleted role",
                inline=True
            )

        embed.set_footer(text=f"Created: {cmd['created_at'][:10]}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @customcmd_group.command(name="prefix", description="Set the trigger prefix for custom commands")
    @app_commands.describe(prefix="The prefix to use (e.g., !, ?, .)")
    @app_commands.default_permissions(manage_guild=True)
    async def customcmd_prefix(self, interaction: discord.Interaction, prefix: str):
        """Set the command prefix"""
        if len(prefix) > 5:
            await interaction.response.send_message(
                "Prefix must be 5 characters or less!",
                ephemeral=True
            )
            return

        success, message = self.set_prefix(interaction.guild.id, prefix)

        embed = discord.Embed(
            title="Prefix Updated",
            description=f"Custom commands will now be triggered with `{prefix}`\n"
                        f"Example: `{prefix}rules`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Custom command prefix set to '{prefix}' in {interaction.guild.name}")

    # ============================================
    # MESSAGE LISTENER
    # ============================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for custom command triggers"""
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return

        # Get the prefix for this guild
        prefix = self.get_prefix(message.guild.id)

        # Check if message starts with prefix
        if not message.content.startswith(prefix):
            return

        # Extract command name
        content = message.content[len(prefix):].strip()
        if not content:
            return

        # Get the first word as command name
        command_name = content.split()[0].lower()

        # Check if custom command exists
        cmd = get_custom_command(message.guild.id, command_name)
        if not cmd:
            return

        # Execute the command based on type
        try:
            response_type = cmd["response_type"]

            if response_type == "text":
                # Simple text response
                await message.channel.send(cmd["response_content"])

            elif response_type == "embed":
                # Embed response
                embed_data = cmd.get("embed_data", {})
                color_hex = embed_data.get("color", "#5865F2")
                if color_hex.startswith("#"):
                    color_hex = color_hex[1:]
                color = int(color_hex, 16)

                embed = discord.Embed(
                    title=embed_data.get("title", command_name.capitalize()),
                    description=embed_data.get("description", cmd["response_content"]),
                    color=color
                )
                if embed_data.get("image"):
                    embed.set_image(url=embed_data["image"])

                await message.channel.send(embed=embed)

            elif response_type == "image":
                # Image response
                embed = discord.Embed(color=discord.Color.blue())
                embed.set_image(url=cmd["response_content"])
                await message.channel.send(embed=embed)

            elif response_type == "role_add":
                # Add role to user
                role = message.guild.get_role(cmd["role_id"])
                if role:
                    if role in message.author.roles:
                        await message.channel.send(
                            f"{message.author.mention}, you already have the {role.name} role!"
                        )
                    else:
                        await message.author.add_roles(role, reason="Custom command role add")
                        await message.channel.send(
                            f"{message.author.mention}, you've been given the {role.name} role!"
                        )
                else:
                    await message.channel.send("The configured role no longer exists.")

            elif response_type == "role_remove":
                # Remove role from user
                role = message.guild.get_role(cmd["role_id"])
                if role:
                    if role not in message.author.roles:
                        await message.channel.send(
                            f"{message.author.mention}, you don't have the {role.name} role!"
                        )
                    else:
                        await message.author.remove_roles(role, reason="Custom command role remove")
                        await message.channel.send(
                            f"{message.author.mention}, the {role.name} role has been removed!"
                        )
                else:
                    await message.channel.send("The configured role no longer exists.")

            # Increment use counter
            increment_command_uses(message.guild.id, command_name)
            logger.debug(f"Custom command '{command_name}' used in {message.guild.name}")

        except discord.Forbidden:
            await message.channel.send("I don't have permission to do that!")
        except Exception as e:
            logger.error(f"Error executing custom command: {e}")


async def setup(bot: commands.Bot):
    """Add the CustomCommands cog to the bot"""
    await bot.add_cog(CustomCommands(bot))
