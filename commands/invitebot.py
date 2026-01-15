"""
/invitebot Command - Get the bot invite link

Commands:
- /invitebot - Get a link to add Gojo to your server
"""

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.logger import log_command, logger


class InviteBot(commands.Cog):
    """Cog for the invite bot command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="invitebot", description="Get the link to add Gojo to your server")
    async def invitebot(self, interaction: discord.Interaction):
        """
        Slash command that displays the bot invite link
        Usage: /invitebot
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else "DM"
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="invitebot",
            guild=guild_name
        )

        # Get bot's client ID
        bot_id = self.bot.user.id

        # Permission integer for all features the bot needs
        # Includes: Administrator (for full functionality)
        # You can use a more specific permission value if preferred
        permissions = discord.Permissions(
            administrator=True  # Full access for all features
        )

        # Generate invite URL
        invite_url = discord.utils.oauth_url(
            bot_id,
            permissions=permissions,
            scopes=["bot", "applications.commands"]
        )

        # Create embed
        embed = discord.Embed(
            title=f"Invite {config.BOT_NAME} to Your Server!",
            description=(
                f"Click the button below to add **{config.BOT_NAME}** to your Discord server!\n\n"
                f"**{config.BOT_NAME}** comes packed with features:"
            ),
            color=discord.Color.blue()
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Feature highlights
        embed.add_field(
            name="Features Include",
            value=(
                "- Music & Karaoke System\n"
                "- Economy & Gambling Games\n"
                "- Leveling & Achievements\n"
                "- Moderation Tools\n"
                "- Giveaways & Polls\n"
                "- Reaction Roles\n"
                "- Welcome/Goodbye Cards\n"
                "- And 90+ more commands!"
            ),
            inline=False
        )

        embed.add_field(
            name="Requirements",
            value="The bot requires **Administrator** permission for full functionality.",
            inline=False
        )

        embed.set_footer(text=f"{config.BOT_NAME} v{config.BOT_VERSION}")

        # Create button with invite link
        view = InviteView(invite_url)

        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"Invite link requested by {interaction.user}")


class InviteView(discord.ui.View):
    """View with invite button"""

    def __init__(self, invite_url: str):
        super().__init__(timeout=None)  # Button doesn't expire

        # Add invite button (link button)
        self.add_item(
            discord.ui.Button(
                label="Add to Server",
                style=discord.ButtonStyle.link,
                url=invite_url,
                emoji="🤖"
            )
        )

        # Add support server button (optional - you can add your support server link)
        # self.add_item(
        #     discord.ui.Button(
        #         label="Support Server",
        #         style=discord.ButtonStyle.link,
        #         url="https://discord.gg/your-support-server",
        #         emoji="💬"
        #     )
        # )


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the InviteBot cog to the bot"""
    await bot.add_cog(InviteBot(bot))
