"""
Welcome & Goodbye System - Visual welcome/goodbye cards with configuration

Commands:
- /welcome enable - Enable welcome messages
- /welcome channel - Set the welcome channel
- /welcome message - Set custom welcome message
- /welcome image - Enable/disable welcome card images
- /welcome background - Set custom background image
- /welcome dm - Configure DM welcome messages
- /welcome test - Test the welcome card

- /goodbye enable - Enable goodbye messages
- /goodbye channel - Set the goodbye channel
- /goodbye message - Set custom goodbye message
- /goodbye image - Enable/disable goodbye card images
- /goodbye test - Test the goodbye card

- /autorole add - Add auto-assign role
- /autorole remove - Remove auto-assign role
- /autorole list - List auto-assign roles
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.server_config_db import (
    get_welcome_config,
    set_welcome_enabled,
    set_welcome_channel,
    set_welcome_message,
    set_welcome_image,
    set_welcome_background,
    set_welcome_dm,
    get_goodbye_config,
    set_goodbye_enabled,
    set_goodbye_channel,
    set_goodbye_message,
    set_goodbye_image,
    get_auto_role_config,
    set_auto_role_enabled,
    add_auto_role,
    remove_auto_role,
    clear_auto_roles
)
from utils.card_generator import (
    create_welcome_card,
    create_goodbye_card,
    image_to_bytes
)
from utils.logger import logger


class Welcome(commands.Cog):
    """Welcome and goodbye system with visual cards"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ============================================
    # WELCOME COMMANDS
    # ============================================

    welcome_group = app_commands.Group(name="welcome", description="Configure welcome messages")

    @welcome_group.command(name="enable", description="Enable or disable welcome messages")
    @app_commands.describe(enabled="Enable welcome messages")
    @app_commands.default_permissions(administrator=True)
    async def welcome_enable(self, interaction: discord.Interaction, enabled: bool):
        """Enable/disable welcome messages"""
        success, message = set_welcome_enabled(interaction.guild.id, enabled)
        await interaction.response.send_message(message, ephemeral=True)
        logger.info(f"Welcome {'enabled' if enabled else 'disabled'} in {interaction.guild.name}")

    @welcome_group.command(name="channel", description="Set the channel for welcome messages")
    @app_commands.describe(channel="The channel to send welcome messages in")
    @app_commands.default_permissions(administrator=True)
    async def welcome_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set welcome channel"""
        success, message = set_welcome_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(f"Welcome channel set to {channel.mention}!", ephemeral=True)
        logger.info(f"Welcome channel set to #{channel.name} in {interaction.guild.name}")

    @welcome_group.command(name="message", description="Set the welcome message (use {user}, {server}, {member_count})")
    @app_commands.describe(message="The welcome message with placeholders")
    @app_commands.default_permissions(administrator=True)
    async def welcome_message(self, interaction: discord.Interaction, message: str):
        """Set welcome message"""
        success, result = set_welcome_message(interaction.guild.id, message)

        embed = discord.Embed(
            title="Welcome Message Updated",
            description=f"**New message:**\n{message}",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Available Placeholders",
            value=(
                "`{user}` - User mention\n"
                "`{username}` - Username\n"
                "`{server}` - Server name\n"
                "`{member_count}` - Member count"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @welcome_group.command(name="image", description="Enable or disable welcome card images")
    @app_commands.describe(enabled="Enable welcome card images")
    @app_commands.default_permissions(administrator=True)
    async def welcome_image_cmd(self, interaction: discord.Interaction, enabled: bool):
        """Enable/disable welcome images"""
        success, message = set_welcome_image(interaction.guild.id, enabled)
        await interaction.response.send_message(message, ephemeral=True)

    @welcome_group.command(name="background", description="Set a custom background image for welcome cards")
    @app_commands.describe(url="Image URL (leave empty to reset to default)")
    @app_commands.default_permissions(administrator=True)
    async def welcome_background(self, interaction: discord.Interaction, url: Optional[str] = None):
        """Set custom background"""
        success, message = set_welcome_background(interaction.guild.id, url)
        await interaction.response.send_message(message, ephemeral=True)

    @welcome_group.command(name="dm", description="Configure DM welcome messages")
    @app_commands.describe(
        enabled="Send DM to new members",
        message="Custom DM message (optional)"
    )
    @app_commands.default_permissions(administrator=True)
    async def welcome_dm(self, interaction: discord.Interaction, enabled: bool, message: Optional[str] = None):
        """Configure DM welcome"""
        success, result = set_welcome_dm(interaction.guild.id, enabled, message)
        await interaction.response.send_message(result, ephemeral=True)

    @welcome_group.command(name="test", description="Test the welcome card with yourself")
    @app_commands.default_permissions(administrator=True)
    async def welcome_test(self, interaction: discord.Interaction):
        """Test welcome card"""
        await interaction.response.defer()

        config = get_welcome_config(interaction.guild.id)

        if config["use_image"]:
            # Generate welcome card
            card = await create_welcome_card(
                avatar_url=interaction.user.display_avatar.url,
                username=interaction.user.display_name,
                member_count=interaction.guild.member_count,
                server_name=interaction.guild.name,
                background_url=config.get("background_url"),
                custom_message=config.get("message")
            )

            buffer = image_to_bytes(card)
            file = discord.File(buffer, filename="welcome_test.png")

            # Format message
            message = config.get("message", "Welcome to {server}, {user}!")
            message = message.replace("{user}", interaction.user.mention)
            message = message.replace("{username}", interaction.user.display_name)
            message = message.replace("{server}", interaction.guild.name)
            message = message.replace("{member_count}", str(interaction.guild.member_count))

            await interaction.followup.send(content=message, file=file)
        else:
            # Text only
            message = config.get("message", "Welcome to {server}, {user}!")
            message = message.replace("{user}", interaction.user.mention)
            message = message.replace("{username}", interaction.user.display_name)
            message = message.replace("{server}", interaction.guild.name)
            message = message.replace("{member_count}", str(interaction.guild.member_count))

            embed = discord.Embed(
                title=f"Welcome to {interaction.guild.name}!",
                description=message,
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            await interaction.followup.send(embed=embed)

    @welcome_group.command(name="status", description="View current welcome configuration")
    @app_commands.default_permissions(administrator=True)
    async def welcome_status(self, interaction: discord.Interaction):
        """View welcome config"""
        config = get_welcome_config(interaction.guild.id)

        channel = interaction.guild.get_channel(config["channel_id"]) if config["channel_id"] else None

        embed = discord.Embed(
            title="Welcome Configuration",
            color=discord.Color.blue()
        )
        embed.add_field(name="Enabled", value="Yes" if config["enabled"] else "No", inline=True)
        embed.add_field(name="Channel", value=channel.mention if channel else "Not set", inline=True)
        embed.add_field(name="Image Cards", value="Yes" if config["use_image"] else "No", inline=True)
        embed.add_field(name="Custom Background", value="Yes" if config.get("background_url") else "Default", inline=True)
        embed.add_field(name="DM Enabled", value="Yes" if config["dm_enabled"] else "No", inline=True)
        embed.add_field(name="Message", value=config.get("message", "Default")[:100], inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================================
    # GOODBYE COMMANDS
    # ============================================

    goodbye_group = app_commands.Group(name="goodbye", description="Configure goodbye messages")

    @goodbye_group.command(name="enable", description="Enable or disable goodbye messages")
    @app_commands.describe(enabled="Enable goodbye messages")
    @app_commands.default_permissions(administrator=True)
    async def goodbye_enable(self, interaction: discord.Interaction, enabled: bool):
        """Enable/disable goodbye messages"""
        success, message = set_goodbye_enabled(interaction.guild.id, enabled)
        await interaction.response.send_message(message, ephemeral=True)

    @goodbye_group.command(name="channel", description="Set the channel for goodbye messages")
    @app_commands.describe(channel="The channel to send goodbye messages in")
    @app_commands.default_permissions(administrator=True)
    async def goodbye_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set goodbye channel"""
        success, message = set_goodbye_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(f"Goodbye channel set to {channel.mention}!", ephemeral=True)

    @goodbye_group.command(name="message", description="Set the goodbye message")
    @app_commands.describe(message="The goodbye message")
    @app_commands.default_permissions(administrator=True)
    async def goodbye_message(self, interaction: discord.Interaction, message: str):
        """Set goodbye message"""
        success, result = set_goodbye_message(interaction.guild.id, message)
        await interaction.response.send_message(result, ephemeral=True)

    @goodbye_group.command(name="image", description="Enable or disable goodbye card images")
    @app_commands.describe(enabled="Enable goodbye card images")
    @app_commands.default_permissions(administrator=True)
    async def goodbye_image_cmd(self, interaction: discord.Interaction, enabled: bool):
        """Enable/disable goodbye images"""
        success, message = set_goodbye_image(interaction.guild.id, enabled)
        await interaction.response.send_message(message, ephemeral=True)

    @goodbye_group.command(name="test", description="Test the goodbye card with yourself")
    @app_commands.default_permissions(administrator=True)
    async def goodbye_test(self, interaction: discord.Interaction):
        """Test goodbye card"""
        await interaction.response.defer()

        config = get_goodbye_config(interaction.guild.id)

        if config["use_image"]:
            card = await create_goodbye_card(
                avatar_url=interaction.user.display_avatar.url,
                username=interaction.user.display_name,
                server_name=interaction.guild.name
            )

            buffer = image_to_bytes(card)
            file = discord.File(buffer, filename="goodbye_test.png")

            message = config.get("message", "Goodbye {user}! We'll miss you!")
            message = message.replace("{user}", interaction.user.display_name)
            message = message.replace("{server}", interaction.guild.name)

            await interaction.followup.send(content=message, file=file)
        else:
            message = config.get("message", "Goodbye {user}! We'll miss you!")
            message = message.replace("{user}", interaction.user.display_name)
            message = message.replace("{server}", interaction.guild.name)

            embed = discord.Embed(
                title="Goodbye!",
                description=message,
                color=discord.Color.orange()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            await interaction.followup.send(embed=embed)

    # ============================================
    # AUTO ROLE COMMANDS
    # ============================================

    autorole_group = app_commands.Group(name="autorole", description="Configure auto-assign roles")

    @autorole_group.command(name="enable", description="Enable or disable auto roles")
    @app_commands.describe(enabled="Enable auto roles")
    @app_commands.default_permissions(administrator=True)
    async def autorole_enable(self, interaction: discord.Interaction, enabled: bool):
        """Enable/disable auto roles"""
        success, message = set_auto_role_enabled(interaction.guild.id, enabled)
        await interaction.response.send_message(message, ephemeral=True)

    @autorole_group.command(name="add", description="Add a role to auto-assign on join")
    @app_commands.describe(role="The role to auto-assign")
    @app_commands.default_permissions(administrator=True)
    async def autorole_add(self, interaction: discord.Interaction, role: discord.Role):
        """Add auto role"""
        # Check if role can be assigned
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "I can't assign this role - it's higher than my highest role!",
                ephemeral=True
            )
            return

        if role.managed:
            await interaction.response.send_message(
                "This role is managed by an integration and can't be auto-assigned!",
                ephemeral=True
            )
            return

        success, message = add_auto_role(interaction.guild.id, role.id)
        await interaction.response.send_message(
            f"Auto role {role.mention} added!" if success else message,
            ephemeral=True
        )

    @autorole_group.command(name="remove", description="Remove a role from auto-assign")
    @app_commands.describe(role="The role to remove")
    @app_commands.default_permissions(administrator=True)
    async def autorole_remove(self, interaction: discord.Interaction, role: discord.Role):
        """Remove auto role"""
        success, message = remove_auto_role(interaction.guild.id, role.id)
        await interaction.response.send_message(message, ephemeral=True)

    @autorole_group.command(name="list", description="List all auto-assign roles")
    @app_commands.default_permissions(administrator=True)
    async def autorole_list(self, interaction: discord.Interaction):
        """List auto roles"""
        config = get_auto_role_config(interaction.guild.id)

        embed = discord.Embed(
            title="Auto-Assign Roles",
            color=discord.Color.blue()
        )
        embed.add_field(name="Enabled", value="Yes" if config["enabled"] else "No", inline=False)

        if config["role_ids"]:
            roles = []
            for role_id in config["role_ids"]:
                role = interaction.guild.get_role(role_id)
                if role:
                    roles.append(role.mention)
                else:
                    roles.append(f"Deleted role ({role_id})")

            embed.add_field(name="Roles", value="\n".join(roles), inline=False)
        else:
            embed.add_field(name="Roles", value="No auto roles configured", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @autorole_group.command(name="clear", description="Remove all auto-assign roles")
    @app_commands.default_permissions(administrator=True)
    async def autorole_clear(self, interaction: discord.Interaction):
        """Clear all auto roles"""
        success, message = clear_auto_roles(interaction.guild.id)
        await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    """Add the Welcome cog to the bot"""
    await bot.add_cog(Welcome(bot))
