"""
Guess the Number Command
High-risk, high-reward gambling game

Rules:
- Guess a number between 1-50
- If correct: 500x payout!
- If wrong: Lose your bet
- 2% chance of winning (1/50)
"""

import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio

import config
from utils.logger import log_command, logger
from utils.economy_db import get_balance, add_coins, remove_coins, record_gamble


# Game configuration
MIN_NUMBER = 1
MAX_NUMBER = 50
MULTIPLIER = 500  # 500x payout for correct guess


class GuessNumber(commands.Cog):
    """Guess the number game command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="guessnumber", description="Guess 1-50 for 500x payout! High risk, high reward!")
    @app_commands.describe(
        bet="Amount of coins to bet",
        guess="Your guess (1-50)"
    )
    async def guessnumber(
        self,
        interaction: discord.Interaction,
        bet: int,
        guess: int
    ):
        """Play the guess the number game"""
        log_command(str(interaction.user), interaction.user.id, f"guessnumber {bet} {guess}", interaction.guild.name)

        # Validate guess
        if guess < MIN_NUMBER or guess > MAX_NUMBER:
            await interaction.response.send_message(
                f"Your guess must be between **{MIN_NUMBER}** and **{MAX_NUMBER}**!",
                ephemeral=True
            )
            return

        # Validate bet
        if bet <= 0:
            await interaction.response.send_message(
                "Bet must be a positive number!",
                ephemeral=True
            )
            return

        if bet > 1000:
            await interaction.response.send_message(
                "Maximum bet for this game is **1,000** coins! (It's very risky!)",
                ephemeral=True
            )
            return

        # Check balance
        balance = get_balance(interaction.guild.id, interaction.user.id)
        if balance < bet:
            await interaction.response.send_message(
                f"You don't have enough coins! Your balance: **{balance:,}** coins",
                ephemeral=True
            )
            return

        # Take the bet
        remove_coins(interaction.guild.id, interaction.user.id, bet)

        # Initial embed - suspense
        embed = discord.Embed(
            title="Guess the Number",
            description=f"You guessed **{guess}**...\n\nGenerating random number between 1-50...",
            color=discord.Color.gold()
        )
        embed.add_field(name="Your Bet", value=f"**{bet:,}** coins", inline=True)
        embed.add_field(name="Potential Win", value=f"**{bet * MULTIPLIER:,}** coins", inline=True)
        embed.add_field(
            name="Odds",
            value=f"1 in {MAX_NUMBER} chance (2%)",
            inline=True
        )
        embed.set_footer(text=f"Player: {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

        # Build suspense
        await asyncio.sleep(2)

        # Generate the winning number
        winning_number = random.randint(MIN_NUMBER, MAX_NUMBER)
        won = (guess == winning_number)

        if won:
            # JACKPOT!
            payout = bet * MULTIPLIER
            add_coins(interaction.guild.id, interaction.user.id, payout, source="guessnumber_jackpot")
            record_gamble(interaction.guild.id, interaction.user.id, bet, True, payout - bet)

            result_embed = discord.Embed(
                title="JACKPOT!!!",
                description=f"# The number was **{winning_number}**!\n\n"
                           f"🎉🎉🎉 **INCREDIBLE!** 🎉🎉🎉\n\n"
                           f"You guessed correctly and won **{payout:,}** coins!",
                color=discord.Color.gold()
            )
            result_embed.add_field(name="Your Guess", value=f"**{guess}**", inline=True)
            result_embed.add_field(name="Winning Number", value=f"**{winning_number}**", inline=True)
            result_embed.add_field(name="Multiplier", value=f"**{MULTIPLIER}x**", inline=True)
            result_embed.add_field(name="Your Winnings", value=f"**+{payout:,}** coins", inline=False)

            new_balance = get_balance(interaction.guild.id, interaction.user.id)
            result_embed.add_field(name="New Balance", value=f"**{new_balance:,}** coins", inline=True)

        else:
            # Lost
            record_gamble(interaction.guild.id, interaction.user.id, bet, False)

            # Determine how close they were
            difference = abs(guess - winning_number)
            if difference == 1:
                close_msg = "SO CLOSE! Just 1 off!"
            elif difference <= 5:
                close_msg = f"Close! Only {difference} away."
            elif difference <= 10:
                close_msg = f"Not bad, {difference} away."
            else:
                close_msg = f"Off by {difference}."

            result_embed = discord.Embed(
                title="Not This Time...",
                description=f"# The number was **{winning_number}**\n\n"
                           f"You guessed **{guess}**. {close_msg}\n\n"
                           f"You lost **{bet:,}** coins.",
                color=discord.Color.red()
            )
            result_embed.add_field(name="Your Guess", value=f"**{guess}**", inline=True)
            result_embed.add_field(name="Winning Number", value=f"**{winning_number}**", inline=True)
            result_embed.add_field(name="Difference", value=f"**{difference}**", inline=True)

            new_balance = get_balance(interaction.guild.id, interaction.user.id)
            result_embed.add_field(name="New Balance", value=f"**{new_balance:,}** coins", inline=True)

            # Encouragement
            result_embed.set_footer(text="The odds are 1 in 50... Keep trying!")

        await interaction.edit_original_response(embed=result_embed)


# Required setup function
async def setup(bot: commands.Bot):
    """Add the GuessNumber cog to the bot"""
    await bot.add_cog(GuessNumber(bot))
