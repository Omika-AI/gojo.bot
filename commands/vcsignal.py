"""
VC Signal Command - "Ghost" ping friends to join your voice channel

Commands:
- /vcsignal @user [message] - Send a private invite to join your VC

Features:
- Sends a DM to the target user with join button
- Shows who invited them and which channel
- Cooldown to prevent spam
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from datetime import datetime, timedelta
from typing import Optional, Dict

from utils.logger import logger

# Cooldown tracking: {user_id: last_signal_time}
signal_cooldowns: Dict[int, datetime] = {}
SIGNAL_COOLDOWN_SECONDS = 60  # 1 minute cooldown


class JoinVCView(View):
    """View with button to join voice channel"""

    def __init__(self, channel: discord.VoiceChannel, inviter: discord.Member):
        super().__init__(timeout=300)  # 5 minute timeout
        self.channel = channel
        self.inviter = inviter

        # Add a link-style button that shows the channel info
        # Note: Can't actually make a button join VC, but we can give clear instructions

    @discord.ui.button(label="Join Voice Channel", style=discord.ButtonStyle.success, emoji="🔊")
    async def join_button(self, interaction: discord.Interaction, button: Button):
        """Show instructions to join"""
        # Check if channel still exists
        guild = self.inviter.guild
        channel = guild.get_channel(self.channel.id)

        if not channel:
            await interaction.response.send_message(
                "Sorry, that voice channel no longer exists!",
                ephemeral=True
            )
            return

        # Check if user is in the guild
        member = guild.get_member(interaction.user.id)
        if not member:
            await interaction.response.send_message(
                "You need to be in the server to join the voice channel!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Join Instructions",
            description=(
                f"To join **{channel.name}**:\n\n"
                f"1. Go to **{guild.name}**\n"
                f"2. Find the voice channel: **{channel.name}**\n"
                f"3. Click on it to join!\n\n"
                f"**{self.inviter.display_name}** is waiting for you!"
            ),
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Notify the inviter
        try:
            notify_embed = discord.Embed(
                title="Signal Acknowledged!",
                description=f"**{interaction.user.display_name}** saw your VC signal and may be joining soon!",
                color=discord.Color.green()
            )
            await self.inviter.send(embed=notify_embed)
        except discord.Forbidden:
            pass  # Can't DM inviter

    @discord.ui.button(label="Can't Join Right Now", style=discord.ButtonStyle.secondary, emoji="❌")
    async def decline_button(self, interaction: discord.Interaction, button: Button):
        """Decline the invitation"""
        await interaction.response.send_message(
            f"No worries! I'll let **{self.inviter.display_name}** know.",
            ephemeral=True
        )

        # Notify the inviter
        try:
            notify_embed = discord.Embed(
                title="Signal Response",
                description=f"**{interaction.user.display_name}** can't join right now.",
                color=discord.Color.orange()
            )
            await self.inviter.send(embed=notify_embed)
        except discord.Forbidden:
            pass


class VCSignal(commands.Cog):
    """VC Signal command for inviting friends to voice"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="vcsignal", description="Send a private signal to a friend to join your voice channel")
    @app_commands.describe(
        user="The user to signal",
        message="Optional custom message to include"
    )
    async def vcsignal(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        message: Optional[str] = None
    ):
        """Send a VC signal to another user"""

        logger.info(f"VC signal from {interaction.user} to {user}")

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check if user is in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "You need to be in a voice channel to send a signal!",
                ephemeral=True
            )
            return

        channel = interaction.user.voice.channel

        # Can't signal yourself
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't signal yourself!",
                ephemeral=True
            )
            return

        # Can't signal bots
        if user.bot:
            await interaction.response.send_message(
                "You can't send signals to bots!",
                ephemeral=True
            )
            return

        # Check if target is already in the channel
        if user in channel.members:
            await interaction.response.send_message(
                f"**{user.display_name}** is already in your voice channel!",
                ephemeral=True
            )
            return

        # Check cooldown
        now = datetime.utcnow()
        last_signal = signal_cooldowns.get(interaction.user.id)
        if last_signal:
            time_passed = (now - last_signal).total_seconds()
            if time_passed < SIGNAL_COOLDOWN_SECONDS:
                remaining = int(SIGNAL_COOLDOWN_SECONDS - time_passed)
                await interaction.response.send_message(
                    f"Please wait **{remaining}** seconds before sending another signal!",
                    ephemeral=True
                )
                return

        # Update cooldown
        signal_cooldowns[interaction.user.id] = now

        # Create the signal embed
        embed = discord.Embed(
            title="VC Signal Received!",
            description=f"**{interaction.user.display_name}** wants you to join their voice channel!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Server",
            value=interaction.guild.name,
            inline=True
        )
        embed.add_field(
            name="Voice Channel",
            value=channel.name,
            inline=True
        )
        embed.add_field(
            name="People in Channel",
            value=f"{len(channel.members)} user(s)",
            inline=True
        )

        if message:
            embed.add_field(
                name="Message",
                value=f'"{message}"',
                inline=False
            )

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="Click the button below to respond!")

        # Create the view with buttons
        view = JoinVCView(channel, interaction.user)

        # Try to send DM
        try:
            await user.send(embed=embed, view=view)

            await interaction.response.send_message(
                f"Signal sent to **{user.display_name}**! They'll receive a DM with your invitation.",
                ephemeral=True
            )
            logger.info(f"VC signal sent from {interaction.user} to {user} for channel {channel.name}")

        except discord.Forbidden:
            await interaction.response.send_message(
                f"Couldn't send signal to **{user.display_name}** - they have DMs disabled!\n"
                f"Try mentioning them in chat instead.",
                ephemeral=True
            )

    @app_commands.command(name="vclink", description="Get a shareable link/info for your current voice channel")
    async def vclink(self, interaction: discord.Interaction):
        """Get voice channel info to share"""

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check if user is in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "You need to be in a voice channel!",
                ephemeral=True
            )
            return

        channel = interaction.user.voice.channel

        embed = discord.Embed(
            title=f"Join: {channel.name}",
            description=(
                f"**{interaction.user.display_name}** invites you to join their voice channel!\n\n"
                f"**Server:** {interaction.guild.name}\n"
                f"**Channel:** {channel.name}\n"
                f"**Current Members:** {len(channel.members)}"
            ),
            color=discord.Color.green()
        )

        if channel.user_limit > 0:
            embed.add_field(
                name="Slots",
                value=f"{len(channel.members)}/{channel.user_limit}",
                inline=True
            )

        # List who's in the channel
        member_list = ", ".join([m.display_name for m in channel.members[:10]])
        if len(channel.members) > 10:
            member_list += f" +{len(channel.members) - 10} more"

        embed.add_field(
            name="Who's There",
            value=member_list or "Empty",
            inline=False
        )

        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text="Share this embed to invite friends!")

        await interaction.response.send_message(embed=embed)


# Required setup function
async def setup(bot: commands.Bot):
    """Add the VCSignal cog to the bot"""
    await bot.add_cog(VCSignal(bot))
