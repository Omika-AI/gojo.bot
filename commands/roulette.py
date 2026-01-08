"""
Roulette Game Command
Play European roulette with virtual coins

Bet Types:
- Number (0-36): 35x payout
- Red/Black: 2x payout
- Odd/Even: 2x payout
- Low (1-18)/High (19-36): 2x payout
- Dozens (1-12, 13-24, 25-36): 3x payout
"""

import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio

import config
from utils.logger import log_command, logger
from utils.economy_db import get_balance, add_coins, remove_coins, record_gamble


# Roulette wheel configuration
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}

# Bet type choices
BET_TYPES = [
    app_commands.Choice(name="Red (2x)", value="red"),
    app_commands.Choice(name="Black (2x)", value="black"),
    app_commands.Choice(name="Odd (2x)", value="odd"),
    app_commands.Choice(name="Even (2x)", value="even"),
    app_commands.Choice(name="Low 1-18 (2x)", value="low"),
    app_commands.Choice(name="High 19-36 (2x)", value="high"),
    app_commands.Choice(name="1st Dozen 1-12 (3x)", value="dozen1"),
    app_commands.Choice(name="2nd Dozen 13-24 (3x)", value="dozen2"),
    app_commands.Choice(name="3rd Dozen 25-36 (3x)", value="dozen3"),
]


def get_number_color(number: int) -> str:
    """Get the color of a roulette number"""
    if number == 0:
        return "green"
    elif number in RED_NUMBERS:
        return "red"
    else:
        return "black"


def get_color_emoji(number: int) -> str:
    """Get emoji for a roulette number"""
    if number == 0:
        return "🟢"
    elif number in RED_NUMBERS:
        return "🔴"
    else:
        return "⚫"


def check_win(bet_type: str, number: int) -> tuple[bool, int]:
    """
    Check if bet wins and return (won, multiplier)
    Multiplier is the total payout (e.g., 2x means you get 2x your bet back including original)
    """
    if bet_type == "red":
        return number in RED_NUMBERS, 2
    elif bet_type == "black":
        return number in BLACK_NUMBERS, 2
    elif bet_type == "odd":
        return number > 0 and number % 2 == 1, 2
    elif bet_type == "even":
        return number > 0 and number % 2 == 0, 2
    elif bet_type == "low":
        return 1 <= number <= 18, 2
    elif bet_type == "high":
        return 19 <= number <= 36, 2
    elif bet_type == "dozen1":
        return 1 <= number <= 12, 3
    elif bet_type == "dozen2":
        return 13 <= number <= 24, 3
    elif bet_type == "dozen3":
        return 25 <= number <= 36, 3
    elif bet_type.isdigit():
        target = int(bet_type)
        return number == target, 36
    return False, 0


def get_bet_display(bet_type: str) -> str:
    """Get display name for bet type"""
    displays = {
        "red": "🔴 Red",
        "black": "⚫ Black",
        "odd": "Odd",
        "even": "Even",
        "low": "Low (1-18)",
        "high": "High (19-36)",
        "dozen1": "1st Dozen (1-12)",
        "dozen2": "2nd Dozen (13-24)",
        "dozen3": "3rd Dozen (25-36)",
    }
    if bet_type.isdigit():
        num = int(bet_type)
        return f"{get_color_emoji(num)} Number {num}"
    return displays.get(bet_type, bet_type)


class Roulette(commands.Cog):
    """Roulette game command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="roulette", description="Play roulette - bet on colors, numbers, or ranges")
    @app_commands.describe(
        bet="Amount of coins to bet",
        bet_type="What to bet on (colors, odd/even, ranges)"
    )
    @app_commands.choices(bet_type=BET_TYPES)
    async def roulette(
        self,
        interaction: discord.Interaction,
        bet: int,
        bet_type: app_commands.Choice[str]
    ):
        """Play roulette with color/range bets"""
        log_command(str(interaction.user), interaction.user.id, f"roulette {bet} {bet_type.value}", interaction.guild.name)

        await self._play_roulette(interaction, bet, bet_type.value)

    @app_commands.command(name="roulettenumber", description="Bet on a specific number (0-36) - 36x payout!")
    @app_commands.describe(
        bet="Amount of coins to bet",
        number="Number to bet on (0-36)"
    )
    async def roulette_number(
        self,
        interaction: discord.Interaction,
        bet: int,
        number: int
    ):
        """Play roulette with a specific number bet"""
        log_command(str(interaction.user), interaction.user.id, f"roulettenumber {bet} {number}", interaction.guild.name)

        # Validate number
        if number < 0 or number > 36:
            await interaction.response.send_message(
                "Number must be between 0 and 36!",
                ephemeral=True
            )
            return

        await self._play_roulette(interaction, bet, str(number))

    async def _play_roulette(self, interaction: discord.Interaction, bet: int, bet_type: str):
        """Core roulette game logic"""
        # Validate bet
        if bet <= 0:
            await interaction.response.send_message(
                "Bet must be a positive number!",
                ephemeral=True
            )
            return

        if bet > 10000:
            await interaction.response.send_message(
                "Maximum bet is **10,000** coins!",
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

        # Initial embed - spinning
        embed = discord.Embed(
            title="🎰 Roulette",
            description="The wheel is spinning...",
            color=discord.Color.gold()
        )
        embed.add_field(name="Your Bet", value=f"**{bet:,}** coins on {get_bet_display(bet_type)}", inline=False)
        embed.set_footer(text=f"Player: {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

        # Animate spinning
        await asyncio.sleep(1.5)

        # Spin the wheel
        result = random.randint(0, 36)
        won, multiplier = check_win(bet_type, result)

        # Calculate payout
        if won:
            payout = bet * multiplier
            add_coins(interaction.guild.id, interaction.user.id, payout, source="roulette_win")
            profit = payout - bet
            record_gamble(interaction.guild.id, interaction.user.id, bet, True, profit)
            result_color = discord.Color.green()
            result_text = f"**YOU WIN!** +{profit:,} coins"
        else:
            record_gamble(interaction.guild.id, interaction.user.id, bet, False)
            result_color = discord.Color.red()
            result_text = f"**You lose!** -{bet:,} coins"

        # Result embed
        result_embed = discord.Embed(
            title="🎰 Roulette",
            color=result_color
        )

        # Show the result
        result_embed.add_field(
            name="The ball landed on...",
            value=f"# {get_color_emoji(result)} {result}",
            inline=False
        )

        result_embed.add_field(
            name="Your Bet",
            value=f"**{bet:,}** coins on {get_bet_display(bet_type)}",
            inline=True
        )

        result_embed.add_field(
            name="Result",
            value=result_text,
            inline=True
        )

        # Show new balance
        new_balance = get_balance(interaction.guild.id, interaction.user.id)
        result_embed.add_field(
            name="New Balance",
            value=f"**{new_balance:,}** coins",
            inline=True
        )

        result_embed.set_footer(text=f"Player: {interaction.user.display_name}")

        await interaction.edit_original_response(embed=result_embed)


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Roulette cog to the bot"""
    await bot.add_cog(Roulette(bot))
