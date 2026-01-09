"""
Karaoke List Command
Displays all available karaoke songs with their details
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.logger import log_command
from utils.karaoke_data import get_all_songs


class KaraokeList(commands.Cog):
    """Shows available karaoke songs"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="karaokelist", description="View all available karaoke songs")
    async def karaokelist(self, interaction: discord.Interaction):
        """Display a list of all karaoke songs"""
        log_command(str(interaction.user), interaction.user.id, "karaokelist", interaction.guild.name)

        # Get all available songs
        songs = get_all_songs()

        if not songs:
            await interaction.response.send_message(
                "No karaoke songs available at the moment!",
                ephemeral=True
            )
            return

        # Create embed with song list
        embed = discord.Embed(
            title="🎤 Karaoke Song Library",
            description="Here are all the songs you can sing!",
            color=discord.Color.magenta()
        )

        # Song emoji mapping
        emojis = {
            "happier": "😊",
            "stereo_hearts": "💕",
            "viva_la_vida": "👑",
            "something_blue": "💙"
        }

        # Build song list with details
        for i, song in enumerate(songs, 1):
            emoji = emojis.get(song.id, "🎵")

            # Format duration as mm:ss
            mins = song.duration // 60
            secs = song.duration % 60
            duration_str = f"{mins}:{secs:02d}"

            embed.add_field(
                name=f"{emoji} {i}. {song.title}",
                value=f"**Artist:** {song.artist}\n**Duration:** {duration_str}",
                inline=True
            )

        embed.add_field(
            name="\n🎯 How to Sing",
            value=(
                "Use one of these commands to start singing:\n"
                "• `/karaokesolo @user` - Solo performance\n"
                "• `/karaokeduet @user1 @user2` - Duet performance\n\n"
                "*The spotlight will be on you!*"
            ),
            inline=False
        )

        embed.set_footer(text=f"Requested by {interaction.user.display_name} | {len(songs)} songs available")

        await interaction.response.send_message(embed=embed)


# Required setup function
async def setup(bot: commands.Bot):
    """Add the KaraokeList cog to the bot"""
    await bot.add_cog(KaraokeList(bot))
