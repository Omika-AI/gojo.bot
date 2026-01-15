"""
Auto-Thread System - Automatically create threads for new messages

Keeps channels clean by forcing discussions into threads.

Commands:
- /autothread setup - Enable auto-threading for a channel
- /autothread disable - Disable auto-threading
- /autothread list - List channels with auto-threading
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import json
import os

from utils.logger import logger

# Database path
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
AUTOTHREAD_FILE = os.path.join(DATA_DIR, 'autothread.json')


def load_autothread_data() -> dict:
    """Load auto-thread configuration"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(AUTOTHREAD_FILE):
        try:
            with open(AUTOTHREAD_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_autothread_data(data: dict):
    """Save auto-thread configuration"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(AUTOTHREAD_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_guild_autothread(guild_id: int) -> dict:
    """Get auto-thread config for a guild"""
    data = load_autothread_data()
    return data.get(str(guild_id), {"channels": {}})


def save_guild_autothread(guild_id: int, config: dict):
    """Save auto-thread config for a guild"""
    data = load_autothread_data()
    data[str(guild_id)] = config
    save_autothread_data(data)


class AutoThread(commands.Cog):
    """Auto-threading system for organized discussions"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    autothread_group = app_commands.Group(
        name="autothread",
        description="Configure automatic thread creation"
    )

    @autothread_group.command(name="setup", description="Enable auto-threading for a channel")
    @app_commands.describe(
        channel="The channel to enable auto-threading in",
        thread_name="Format for thread names (use {user} and {count})",
        add_voting="Add upvote/downvote buttons to threads"
    )
    @app_commands.default_permissions(administrator=True)
    async def autothread_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        thread_name: str = "Discussion by {user}",
        add_voting: bool = False
    ):
        """Enable auto-threading for a channel"""
        config = get_guild_autothread(interaction.guild.id)

        config["channels"][str(channel.id)] = {
            "enabled": True,
            "thread_name": thread_name,
            "add_voting": add_voting,
            "threads_created": 0
        }

        save_guild_autothread(interaction.guild.id, config)

        embed = discord.Embed(
            title="🧵 Auto-Threading Enabled",
            description=f"New messages in {channel.mention} will automatically get threads.",
            color=discord.Color.green()
        )
        embed.add_field(name="Thread Name Format", value=f"`{thread_name}`", inline=True)
        embed.add_field(name="Voting Buttons", value="Yes" if add_voting else "No", inline=True)
        embed.set_footer(text="All discussions will be organized into threads!")

        await interaction.response.send_message(embed=embed)
        logger.info(f"Auto-thread enabled in #{channel.name} ({interaction.guild.name})")

    @autothread_group.command(name="disable", description="Disable auto-threading for a channel")
    @app_commands.describe(channel="The channel to disable auto-threading in")
    @app_commands.default_permissions(administrator=True)
    async def autothread_disable(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        """Disable auto-threading"""
        config = get_guild_autothread(interaction.guild.id)

        if str(channel.id) in config.get("channels", {}):
            del config["channels"][str(channel.id)]
            save_guild_autothread(interaction.guild.id, config)

        await interaction.response.send_message(
            f"🧵 Auto-threading disabled for {channel.mention}",
            ephemeral=True
        )

    @autothread_group.command(name="list", description="List channels with auto-threading enabled")
    @app_commands.default_permissions(administrator=True)
    async def autothread_list(self, interaction: discord.Interaction):
        """List auto-thread channels"""
        config = get_guild_autothread(interaction.guild.id)

        embed = discord.Embed(
            title="🧵 Auto-Thread Channels",
            color=discord.Color.blue()
        )

        channels_info = []
        for channel_id, settings in config.get("channels", {}).items():
            if settings.get("enabled"):
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    voting = "✅" if settings.get("add_voting") else "❌"
                    created = settings.get("threads_created", 0)
                    channels_info.append(
                        f"{channel.mention}\n"
                        f"└ Voting: {voting} | Threads: {created}"
                    )

        if channels_info:
            embed.description = "\n\n".join(channels_info)
        else:
            embed.description = "No channels have auto-threading enabled."

        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Create threads for new messages in configured channels"""
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return

        # Check if channel has auto-threading
        config = get_guild_autothread(message.guild.id)
        channel_config = config.get("channels", {}).get(str(message.channel.id))

        if not channel_config or not channel_config.get("enabled"):
            return

        # Don't create threads for messages that are already in threads
        if isinstance(message.channel, discord.Thread):
            return

        try:
            # Generate thread name
            thread_name = channel_config.get("thread_name", "Discussion by {user}")
            count = channel_config.get("threads_created", 0) + 1
            thread_name = thread_name.format(user=message.author.display_name, count=count)

            # Truncate if too long
            if len(thread_name) > 100:
                thread_name = thread_name[:97] + "..."

            # Create thread
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440  # 24 hours
            )

            # Update count
            channel_config["threads_created"] = count
            save_guild_autothread(message.guild.id, config)

            # Add voting buttons if enabled
            if channel_config.get("add_voting"):
                view = VotingView()
                await thread.send(
                    "💬 **Discussion Thread**\nVote on this post!",
                    view=view
                )

            logger.debug(f"Auto-thread created: {thread_name}")

        except discord.Forbidden:
            logger.warning(f"Missing permissions to create thread in {message.channel}")
        except Exception as e:
            logger.error(f"Error creating auto-thread: {e}")


class VotingView(discord.ui.View):
    """Voting buttons for auto-threads"""

    def __init__(self):
        super().__init__(timeout=None)
        self.upvotes = set()
        self.downvotes = set()

    @discord.ui.button(label="0", style=discord.ButtonStyle.success, emoji="👍", custom_id="upvote")
    async def upvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Upvote button"""
        user_id = interaction.user.id

        # Remove from downvotes if present
        self.downvotes.discard(user_id)

        # Toggle upvote
        if user_id in self.upvotes:
            self.upvotes.discard(user_id)
        else:
            self.upvotes.add(user_id)

        # Update buttons
        self.children[0].label = str(len(self.upvotes))
        self.children[1].label = str(len(self.downvotes))

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="0", style=discord.ButtonStyle.danger, emoji="👎", custom_id="downvote")
    async def downvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Downvote button"""
        user_id = interaction.user.id

        # Remove from upvotes if present
        self.upvotes.discard(user_id)

        # Toggle downvote
        if user_id in self.downvotes:
            self.downvotes.discard(user_id)
        else:
            self.downvotes.add(user_id)

        # Update buttons
        self.children[0].label = str(len(self.upvotes))
        self.children[1].label = str(len(self.downvotes))

        await interaction.response.edit_message(view=self)


async def setup(bot: commands.Bot):
    """Add the AutoThread cog to the bot"""
    await bot.add_cog(AutoThread(bot))
