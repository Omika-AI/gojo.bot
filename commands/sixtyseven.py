"""
/67 Command
The most cringe command ever created. You have been warned.
"""

import discord
from discord import app_commands
from discord.ext import commands
import random

from utils.logger import log_command


class SixtySeven(commands.Cog):
    """Cog for the ultimate cringe command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="67", description="Unleash maximum cringe upon the server")
    async def sixtyseven(self, interaction: discord.Interaction):
        """
        The most cringe command you'll ever use
        Usage: /67
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="67",
            guild=guild_name
        )

        # Collection of absolutely cursed cringe messages
        cringe_messages = [
            f"OwO whats this?? *notices {interaction.user.display_name}'s bulgy wulgy* UwU you're so warm... *nuzzles your necky wecky* hehe~ you smell like doritos and broken dreams >///<",

            f"*teleports behind you* nothing personnel, kid... *unsheathes katana made of pure anime power* {interaction.user.display_name}-senpai... forgive me... I must go all out, just this once... *turns into super saiyan while crying anime tears*",

            f"RAWR XD *glomps {interaction.user.display_name}* ur so random!! holds up spork~ im so quirky and different from other girls/boys!! *does the naruto run around the server* BELIEVE IT DATTEBAYO!!!",

            f"hewwo {interaction.user.display_name}-chan!! (◕ᴗ◕✿) *giggles and blushes* y-you want to go to the anime convention with me?? *fidgets nervously* i-i made you a bento box... *drops spaghetti everywhere* BAKA!! ITS NOT LIKE I LIKE YOU OR ANYTHING!!",

            f"*adjusts fedora* M'lady {interaction.user.display_name}... *tips hat respectfully* I see you are also a person of culture... Perhaps you'd like to discuss the intricacies of anime waifus over some mountain dew? *unsheathes katana* I will protect your honor with my blade...",

            f"OMG {interaction.user.display_name}!! *screams in fangirl* YOU'RE LITERALLY SO VALID AND SLAY!! periodt bestie no cap fr fr!! *does the griddy* you ate and left no crumbs!! mother is mothering!! its giving main character energy!! 💅✨🔥",

            f"Greetings, {interaction.user.display_name}. I have studied the blade while you were partying. I have mastered the blockchain while you had premarital hand holding. And now that the server is on fire and the mods need me, you have the audacity to come to me for help? *adjusts glasses that flash menacingly*",

            f"*walks into server with both hands in pockets* yo... *doesn't make eye contact with {interaction.user.display_name}* ...whatever... *kicks a rock* its not like i care about this server or anything... *secretly writes your name in death note but with hearts* ...baka...",

            f"AWOOOGA *jaw drops to floor, eyes pop out of sockets accompanied by trumpets, heart beats out of chest* HUMINA HUMINA HUMINA *slams fist on table* ZAMN {interaction.user.display_name}!! *picks up jaw* Is that a discord user?? *dusts off jacket*",

            f"When I was 7 I watched my first anime and I've been saying 'nani' instead of 'what' ever since. {interaction.user.display_name}, you wouldn't understand... *sits in the corner of the server with my headphones playing sad naruto music* ...I'm just built different...",
        ]

        # Pick a random cringe message
        message = random.choice(cringe_messages)

        # Create an embed for maximum cringe presentation
        embed = discord.Embed(
            title="✨🌸 CRINGE ALERT 🌸✨",
            description=message,
            color=discord.Color.from_rgb(255, 105, 180)  # Hot pink for maximum cringe
        )
        embed.set_footer(text="uwu powered by cringe energy owo | You asked for this...")

        await interaction.response.send_message(embed=embed)


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the SixtySeven cog to the bot"""
    await bot.add_cog(SixtySeven(bot))
