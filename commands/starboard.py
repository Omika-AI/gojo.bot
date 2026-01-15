"""
Starboard System - Community message curation

When a message gets enough star reactions, it gets posted to a hall of fame channel.

Commands:
- /starboard setup - Set up the starboard channel
- /starboard threshold - Set minimum stars required
- /starboard disable - Disable starboard
- /starboard stats - View starboard statistics
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import json
import os
from datetime import datetime

from utils.logger import logger

# Database path
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
STARBOARD_FILE = os.path.join(DATA_DIR, 'starboard.json')


def load_starboard_data() -> dict:
    """Load starboard configuration"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(STARBOARD_FILE):
        try:
            with open(STARBOARD_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_starboard_data(data: dict):
    """Save starboard configuration"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STARBOARD_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_guild_config(guild_id: int) -> dict:
    """Get starboard config for a guild"""
    data = load_starboard_data()
    return data.get(str(guild_id), {
        "enabled": False,
        "channel_id": None,
        "threshold": 3,
        "emoji": "⭐",
        "self_star": False,
        "starred_messages": {},
        "total_stars": 0
    })


def save_guild_config(guild_id: int, config: dict):
    """Save starboard config for a guild"""
    data = load_starboard_data()
    data[str(guild_id)] = config
    save_starboard_data(data)


class Starboard(commands.Cog):
    """Starboard system for community message curation"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    starboard_group = app_commands.Group(
        name="starboard",
        description="Configure the starboard system"
    )

    @starboard_group.command(name="setup", description="Set up the starboard channel")
    @app_commands.describe(channel="The channel to post starred messages to")
    @app_commands.default_permissions(administrator=True)
    async def starboard_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        """Set up starboard"""
        config = get_guild_config(interaction.guild.id)
        config["enabled"] = True
        config["channel_id"] = channel.id
        save_guild_config(interaction.guild.id, config)

        embed = discord.Embed(
            title="⭐ Starboard Enabled",
            description=f"Starred messages will be posted to {channel.mention}",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="Current Settings",
            value=(
                f"**Threshold:** {config['threshold']} stars\n"
                f"**Emoji:** {config['emoji']}\n"
                f"**Self-starring:** {'Allowed' if config['self_star'] else 'Not allowed'}"
            )
        )
        embed.set_footer(text="Use /starboard threshold to change required stars")

        await interaction.response.send_message(embed=embed)
        logger.info(f"Starboard enabled in {interaction.guild.name}")

    @starboard_group.command(name="threshold", description="Set minimum stars required")
    @app_commands.describe(stars="Number of stars required (1-25)")
    @app_commands.default_permissions(administrator=True)
    async def starboard_threshold(
        self,
        interaction: discord.Interaction,
        stars: app_commands.Range[int, 1, 25]
    ):
        """Set star threshold"""
        config = get_guild_config(interaction.guild.id)
        config["threshold"] = stars
        save_guild_config(interaction.guild.id, config)

        await interaction.response.send_message(
            f"⭐ Messages now need **{stars}** star(s) to be posted to the starboard!",
            ephemeral=True
        )

    @starboard_group.command(name="emoji", description="Set the starboard emoji")
    @app_commands.describe(emoji="The emoji to use (default: ⭐)")
    @app_commands.default_permissions(administrator=True)
    async def starboard_emoji(
        self,
        interaction: discord.Interaction,
        emoji: str
    ):
        """Set starboard emoji"""
        # Validate emoji (basic check)
        if len(emoji) > 50:
            await interaction.response.send_message(
                "Invalid emoji!",
                ephemeral=True
            )
            return

        config = get_guild_config(interaction.guild.id)
        config["emoji"] = emoji
        save_guild_config(interaction.guild.id, config)

        await interaction.response.send_message(
            f"Starboard emoji set to {emoji}!",
            ephemeral=True
        )

    @starboard_group.command(name="selfstar", description="Allow/disallow self-starring")
    @app_commands.describe(allowed="Whether users can star their own messages")
    @app_commands.default_permissions(administrator=True)
    async def starboard_selfstar(
        self,
        interaction: discord.Interaction,
        allowed: bool
    ):
        """Toggle self-starring"""
        config = get_guild_config(interaction.guild.id)
        config["self_star"] = allowed
        save_guild_config(interaction.guild.id, config)

        status = "allowed" if allowed else "not allowed"
        await interaction.response.send_message(
            f"Self-starring is now **{status}**!",
            ephemeral=True
        )

    @starboard_group.command(name="disable", description="Disable the starboard")
    @app_commands.default_permissions(administrator=True)
    async def starboard_disable(self, interaction: discord.Interaction):
        """Disable starboard"""
        config = get_guild_config(interaction.guild.id)
        config["enabled"] = False
        save_guild_config(interaction.guild.id, config)

        await interaction.response.send_message(
            "⭐ Starboard has been disabled.",
            ephemeral=True
        )

    @starboard_group.command(name="stats", description="View starboard statistics")
    async def starboard_stats(self, interaction: discord.Interaction):
        """View starboard stats"""
        config = get_guild_config(interaction.guild.id)

        if not config["enabled"]:
            await interaction.response.send_message(
                "Starboard is not enabled on this server!",
                ephemeral=True
            )
            return

        starred_count = len(config.get("starred_messages", {}))
        total_stars = config.get("total_stars", 0)

        embed = discord.Embed(
            title="⭐ Starboard Statistics",
            color=discord.Color.gold()
        )

        channel = self.bot.get_channel(config["channel_id"])
        channel_mention = channel.mention if channel else "Not set"

        embed.add_field(
            name="Configuration",
            value=(
                f"**Channel:** {channel_mention}\n"
                f"**Threshold:** {config['threshold']} stars\n"
                f"**Emoji:** {config['emoji']}"
            ),
            inline=True
        )

        embed.add_field(
            name="Statistics",
            value=(
                f"**Starred Messages:** {starred_count}\n"
                f"**Total Stars Given:** {total_stars}"
            ),
            inline=True
        )

        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle star reactions"""
        if not payload.guild_id:
            return

        config = get_guild_config(payload.guild_id)
        if not config["enabled"] or not config["channel_id"]:
            return

        # Check if it's the star emoji
        emoji_str = str(payload.emoji)
        if emoji_str != config["emoji"] and payload.emoji.name != config["emoji"]:
            return

        # Get the channel and message
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except:
            return

        # Don't star bot messages
        if message.author.bot:
            return

        # Check self-starring
        if not config["self_star"] and payload.user_id == message.author.id:
            return

        # Count star reactions
        star_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == config["emoji"] or getattr(reaction.emoji, 'name', None) == config["emoji"]:
                # Get users who reacted
                users = [user async for user in reaction.users()]
                # Filter out self-stars if not allowed
                if not config["self_star"]:
                    users = [u for u in users if u.id != message.author.id]
                star_count = len(users)
                break

        # Check if threshold is met
        if star_count < config["threshold"]:
            return

        # Get starboard channel
        starboard_channel = self.bot.get_channel(config["channel_id"])
        if not starboard_channel:
            return

        # Check if already starred
        msg_key = str(message.id)
        if msg_key in config.get("starred_messages", {}):
            # Update existing starboard message
            try:
                star_msg_id = config["starred_messages"][msg_key]
                star_msg = await starboard_channel.fetch_message(star_msg_id)
                embed = self._create_star_embed(message, star_count, config["emoji"])
                await star_msg.edit(content=f"{config['emoji']} **{star_count}** | {channel.mention}", embed=embed)
            except:
                pass
            return

        # Create new starboard entry
        embed = self._create_star_embed(message, star_count, config["emoji"])

        try:
            star_msg = await starboard_channel.send(
                content=f"{config['emoji']} **{star_count}** | {channel.mention}",
                embed=embed
            )

            # Save to config
            if "starred_messages" not in config:
                config["starred_messages"] = {}
            config["starred_messages"][msg_key] = star_msg.id
            config["total_stars"] = config.get("total_stars", 0) + star_count
            save_guild_config(payload.guild_id, config)

            logger.info(f"Message starred in {channel.guild.name}: {star_count} stars")

        except Exception as e:
            logger.error(f"Failed to post to starboard: {e}")

    def _create_star_embed(self, message: discord.Message, star_count: int, emoji: str) -> discord.Embed:
        """Create embed for starboard message"""
        embed = discord.Embed(
            description=message.content[:2048] if message.content else None,
            color=discord.Color.gold(),
            timestamp=message.created_at
        )

        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )

        # Add image if present
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image'):
                    embed.set_image(url=attachment.url)
                    break

        # Add jump link
        embed.add_field(
            name="Original",
            value=f"[Jump to message]({message.jump_url})",
            inline=False
        )

        embed.set_footer(text=f"ID: {message.id}")

        return embed


async def setup(bot: commands.Bot):
    """Add the Starboard cog to the bot"""
    await bot.add_cog(Starboard(bot))
