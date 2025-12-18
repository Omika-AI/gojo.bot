"""
/dq Command (Daily Quote)
Sends a random famous quote from movies, books, and famous people
"""

import discord
from discord import app_commands
from discord.ext import commands
import random

from utils.logger import log_command


# Collection of famous quotes
QUOTES = [
    # Star Wars - Yoda
    {
        "quote": "Do or do not. There is no try.",
        "author": "Yoda",
        "source": "Star Wars"
    },
    {
        "quote": "Fear is the path to the dark side. Fear leads to anger, anger leads to hate, hate leads to suffering.",
        "author": "Yoda",
        "source": "Star Wars"
    },
    {
        "quote": "The greatest teacher, failure is.",
        "author": "Yoda",
        "source": "Star Wars"
    },
    {
        "quote": "In a dark place we find ourselves, and a little more knowledge lights our way.",
        "author": "Yoda",
        "source": "Star Wars"
    },

    # Star Wars - Others
    {
        "quote": "May the Force be with you.",
        "author": "Obi-Wan Kenobi",
        "source": "Star Wars"
    },
    {
        "quote": "I find your lack of faith disturbing.",
        "author": "Darth Vader",
        "source": "Star Wars"
    },
    {
        "quote": "Never tell me the odds!",
        "author": "Han Solo",
        "source": "Star Wars"
    },

    # Harry Potter - Dumbledore
    {
        "quote": "It does not do to dwell on dreams and forget to live.",
        "author": "Albus Dumbledore",
        "source": "Harry Potter"
    },
    {
        "quote": "Happiness can be found even in the darkest of times, if one only remembers to turn on the light.",
        "author": "Albus Dumbledore",
        "source": "Harry Potter"
    },
    {
        "quote": "It is our choices that show what we truly are, far more than our abilities.",
        "author": "Albus Dumbledore",
        "source": "Harry Potter"
    },
    {
        "quote": "Words are, in my not-so-humble opinion, our most inexhaustible source of magic.",
        "author": "Albus Dumbledore",
        "source": "Harry Potter"
    },
    {
        "quote": "To the well-organized mind, death is but the next great adventure.",
        "author": "Albus Dumbledore",
        "source": "Harry Potter"
    },

    # Harry Potter - Others
    {
        "quote": "It takes a great deal of bravery to stand up to our enemies, but just as much to stand up to our friends.",
        "author": "Albus Dumbledore",
        "source": "Harry Potter"
    },
    {
        "quote": "After all this time? Always.",
        "author": "Severus Snape",
        "source": "Harry Potter"
    },

    # Lord of the Rings
    {
        "quote": "Even the smallest person can change the course of the future.",
        "author": "Galadriel",
        "source": "Lord of the Rings"
    },
    {
        "quote": "All we have to decide is what to do with the time that is given us.",
        "author": "Gandalf",
        "source": "Lord of the Rings"
    },
    {
        "quote": "A wizard is never late, nor is he early. He arrives precisely when he means to.",
        "author": "Gandalf",
        "source": "Lord of the Rings"
    },
    {
        "quote": "Not all those who wander are lost.",
        "author": "Bilbo Baggins",
        "source": "Lord of the Rings"
    },

    # The Dark Knight
    {
        "quote": "Why so serious?",
        "author": "The Joker",
        "source": "The Dark Knight"
    },
    {
        "quote": "It's not who I am underneath, but what I do that defines me.",
        "author": "Batman",
        "source": "Batman Begins"
    },
    {
        "quote": "You either die a hero, or you live long enough to see yourself become the villain.",
        "author": "Harvey Dent",
        "source": "The Dark Knight"
    },

    # Marvel
    {
        "quote": "I am Iron Man.",
        "author": "Tony Stark",
        "source": "Iron Man"
    },
    {
        "quote": "With great power comes great responsibility.",
        "author": "Uncle Ben",
        "source": "Spider-Man"
    },
    {
        "quote": "I can do this all day.",
        "author": "Steve Rogers",
        "source": "Captain America"
    },

    # Anime - Naruto
    {
        "quote": "I'm not gonna run away, I never go back on my word! That's my nindo: my ninja way!",
        "author": "Naruto Uzumaki",
        "source": "Naruto"
    },
    {
        "quote": "When people are protecting something truly special to them, they truly can become as strong as they can be.",
        "author": "Naruto Uzumaki",
        "source": "Naruto"
    },

    # Jujutsu Kaisen
    {
        "quote": "Throughout Heaven and Earth, I alone am the honored one.",
        "author": "Gojo Satoru",
        "source": "Jujutsu Kaisen"
    },
    {
        "quote": "Don't worry, I'm the strongest.",
        "author": "Gojo Satoru",
        "source": "Jujutsu Kaisen"
    },

    # Real People
    {
        "quote": "The only way to do great work is to love what you do.",
        "author": "Steve Jobs",
        "source": "Real Life"
    },
    {
        "quote": "In the middle of difficulty lies opportunity.",
        "author": "Albert Einstein",
        "source": "Real Life"
    },
    {
        "quote": "Be the change you wish to see in the world.",
        "author": "Mahatma Gandhi",
        "source": "Real Life"
    },
    {
        "quote": "The only thing we have to fear is fear itself.",
        "author": "Franklin D. Roosevelt",
        "source": "Real Life"
    },
    {
        "quote": "I have a dream.",
        "author": "Martin Luther King Jr.",
        "source": "Real Life"
    },
]


class DailyQuote(commands.Cog):
    """Cog for the daily quote command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="dq", description="Get a random famous quote")
    async def dq(self, interaction: discord.Interaction):
        """
        Slash command that sends a random famous quote
        Usage: /dq
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="dq",
            guild=guild_name
        )

        # Pick a random quote
        quote_data = random.choice(QUOTES)

        # Create an embed for the quote
        embed = discord.Embed(
            description=f'*"{quote_data["quote"]}"*',
            color=discord.Color.gold()
        )

        # Add author and source
        embed.set_footer(text=f"— {quote_data['author']} ({quote_data['source']})")

        # Send the quote
        await interaction.response.send_message(embed=embed)


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the DailyQuote cog to the bot"""
    await bot.add_cog(DailyQuote(bot))
