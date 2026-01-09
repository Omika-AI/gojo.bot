"""
Roulette Game Command
Play European roulette with virtual coins

Bet Types:
- Number (0-36): 36x payout (single number)
- Multiple Numbers: Payout scales based on coverage
  - 2 numbers: 18x | 3 numbers: 12x | 4 numbers: 9x
  - 5 numbers: 7x | 6 numbers: 6x | More: lower multiplier
- Red/Black: 2x payout
- Odd/Even: 2x payout
- Low (1-18)/High (19-36): 2x payout
- Dozens (1-12, 13-24, 25-36): 3x payout
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Button
import random
import asyncio
from typing import List, Set, Optional

import config
from utils.logger import log_command, logger
from utils.economy_db import get_balance, add_coins, remove_coins, record_gamble
from utils.achievements_data import update_user_stat, check_and_complete_achievements, get_user_stats


# Roulette wheel configuration
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}

# Payout multipliers based on how many numbers you bet on
# Real casino-style payouts: (37 / numbers_bet) rounded down
NUMBER_PAYOUTS = {
    1: 36,   # Single number: 35:1 + original = 36x
    2: 18,   # Split: 17:1 + original = 18x
    3: 12,   # Street: 11:1 + original = 12x
    4: 9,    # Corner: 8:1 + original = 9x
    5: 7,    # Five number: ~6:1 + original
    6: 6,    # Line: 5:1 + original = 6x
}

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


def get_multiplier_for_numbers(count: int) -> int:
    """Get the payout multiplier based on how many numbers are bet on"""
    if count in NUMBER_PAYOUTS:
        return NUMBER_PAYOUTS[count]
    # For more than 6 numbers, calculate: floor(37 / count)
    # Minimum multiplier is 2x
    return max(2, 37 // count)


def parse_numbers(numbers_str: str) -> tuple[List[int], str]:
    """
    Parse a string of numbers into a list.
    Supports: "7, 17, 23" or "7 17 23" or "7,17,23" or ranges "1-6"
    Returns: (list of numbers, error message or empty string)
    """
    numbers = set()
    errors = []

    # Replace commas with spaces and split
    parts = numbers_str.replace(',', ' ').split()

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check for range (e.g., "1-6")
        if '-' in part and not part.startswith('-'):
            try:
                start, end = part.split('-', 1)
                start, end = int(start), int(end)
                if start > end:
                    start, end = end, start
                for n in range(start, end + 1):
                    if 0 <= n <= 36:
                        numbers.add(n)
                    else:
                        errors.append(f"{n} is not valid (0-36)")
            except ValueError:
                errors.append(f"'{part}' is not a valid range")
        else:
            try:
                n = int(part)
                if 0 <= n <= 36:
                    numbers.add(n)
                else:
                    errors.append(f"{n} is not valid (0-36)")
            except ValueError:
                errors.append(f"'{part}' is not a number")

    error_msg = ", ".join(errors[:3])  # Limit error messages
    if len(errors) > 3:
        error_msg += f" (+{len(errors)-3} more errors)"

    return sorted(list(numbers)), error_msg


def build_roulette_table_embed() -> discord.Embed:
    """Build a visual roulette table embed"""
    embed = discord.Embed(
        title="🎰 Roulette Betting Table",
        description="Place your bets! Numbers are colored: 🟢 Green (0) | 🔴 Red | ⚫ Black",
        color=discord.Color.dark_green()
    )

    # Build the visual table using emoji
    # European roulette layout: 0 at top, then 3 columns of 12 rows

    # Zero row
    zero_row = "```\n         ┌─────┐\n         │  0  │ 🟢\n         └─────┘\n```"

    # Build the main grid - 3 columns, numbers 1-36
    # Layout: Column 1 (1,4,7..34), Column 2 (2,5,8..35), Column 3 (3,6,9..36)
    table_lines = []
    table_lines.append("```")
    table_lines.append("┌────┬────┬────┐")

    for row in range(12):
        n1 = row * 3 + 1  # Column 1
        n2 = row * 3 + 2  # Column 2
        n3 = row * 3 + 3  # Column 3

        # Get color indicators
        c1 = "R" if n1 in RED_NUMBERS else "B"
        c2 = "R" if n2 in RED_NUMBERS else "B"
        c3 = "R" if n3 in RED_NUMBERS else "B"

        table_lines.append(f"│{n1:2}{c1} │{n2:2}{c2} │{n3:2}{c3} │")
        if row < 11:
            table_lines.append("├────┼────┼────┤")

    table_lines.append("└────┴────┴────┘")
    table_lines.append("  R=Red  B=Black")
    table_lines.append("```")

    embed.add_field(
        name="🟢 Zero",
        value="Single number: **36x** payout",
        inline=True
    )

    embed.add_field(
        name="📊 Number Grid",
        value="\n".join(table_lines),
        inline=False
    )

    # Payout info
    payout_text = (
        "**Single Number (1):** 36x\n"
        "**2 Numbers:** 18x\n"
        "**3 Numbers:** 12x\n"
        "**4 Numbers:** 9x\n"
        "**5 Numbers:** 7x\n"
        "**6 Numbers:** 6x\n"
        "**More:** Lower multiplier"
    )
    embed.add_field(name="💰 Multi-Number Payouts", value=payout_text, inline=True)

    # Outside bets
    outside_text = (
        "🔴 **Red** / ⚫ **Black:** 2x\n"
        "**Odd / Even:** 2x\n"
        "**Low (1-18) / High (19-36):** 2x\n"
        "**Dozens (1-12, 13-24, 25-36):** 3x"
    )
    embed.add_field(name="🎯 Outside Bets", value=outside_text, inline=True)

    embed.add_field(
        name="📝 How to Bet Multiple Numbers",
        value=(
            "Use `/roulettenumber` with multiple numbers:\n"
            "• Comma-separated: `7, 17, 23, 32`\n"
            "• Space-separated: `7 17 23 32`\n"
            "• Ranges: `1-6` (bets on 1,2,3,4,5,6)\n"
            "• Mixed: `0, 7, 13-18, 32`"
        ),
        inline=False
    )

    embed.set_footer(text="Use /roulette for color/range bets • /roulettenumber for number bets")

    return embed


def format_numbers_display(numbers: List[int]) -> str:
    """Format a list of numbers for display with colors"""
    if len(numbers) == 1:
        n = numbers[0]
        return f"{get_color_emoji(n)} **{n}**"

    # Group by color for nicer display
    parts = []
    for n in sorted(numbers):
        parts.append(f"{get_color_emoji(n)}{n}")

    # Join with spaces, max ~10 per line
    if len(parts) <= 10:
        return " ".join(parts)
    else:
        lines = []
        for i in range(0, len(parts), 10):
            lines.append(" ".join(parts[i:i+10]))
        return "\n".join(lines)


class Roulette(commands.Cog):
    """Roulette game command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="roulettetable", description="View the roulette betting table and payout information")
    async def roulette_table(self, interaction: discord.Interaction):
        """Display the visual roulette table"""
        log_command(str(interaction.user), interaction.user.id, "roulettetable", interaction.guild.name)

        embed = build_roulette_table_embed()
        await interaction.response.send_message(embed=embed)

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

    @app_commands.command(name="roulettenumber", description="Bet on specific numbers (single or multiple) - up to 36x payout!")
    @app_commands.describe(
        bet="Amount of coins to bet",
        numbers="Numbers to bet on (e.g., '7' or '7, 17, 23' or '1-6' for a range)"
    )
    async def roulette_number(
        self,
        interaction: discord.Interaction,
        bet: int,
        numbers: str
    ):
        """Play roulette with specific number bet(s)"""
        log_command(str(interaction.user), interaction.user.id, f"roulettenumber {bet} {numbers}", interaction.guild.name)

        # Parse the numbers
        parsed_numbers, error = parse_numbers(numbers)

        if error:
            await interaction.response.send_message(
                f"Error parsing numbers: {error}",
                ephemeral=True
            )
            return

        if not parsed_numbers:
            await interaction.response.send_message(
                "Please provide at least one valid number (0-36)!\n"
                "Examples: `7` or `7, 17, 23` or `1-6`",
                ephemeral=True
            )
            return

        if len(parsed_numbers) > 18:
            await interaction.response.send_message(
                "You can bet on at most **18 numbers** at once!\n"
                f"You selected {len(parsed_numbers)} numbers.",
                ephemeral=True
            )
            return

        # Play with multiple numbers
        await self._play_roulette_numbers(interaction, bet, parsed_numbers)

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
        user_id = interaction.user.id
        if won:
            payout = bet * multiplier
            add_coins(interaction.guild.id, interaction.user.id, payout, source="roulette_win")
            profit = payout - bet
            record_gamble(interaction.guild.id, interaction.user.id, bet, True, profit)
            result_color = discord.Color.green()
            result_text = f"**YOU WIN!** +{profit:,} coins"

            # Track achievements
            try:
                update_user_stat(user_id, "gambling_winnings", increment=profit)
                stats = get_user_stats(user_id)
                current_streak = stats.get("current_win_streak", 0) + 1
                update_user_stat(user_id, "current_win_streak", value=current_streak)
                update_user_stat(user_id, "max_win_streak", value=current_streak)
                check_and_complete_achievements(user_id)
            except:
                pass
        else:
            record_gamble(interaction.guild.id, interaction.user.id, bet, False)
            result_color = discord.Color.red()
            result_text = f"**You lose!** -{bet:,} coins"

            # Reset win streak
            try:
                update_user_stat(user_id, "current_win_streak", value=0)
            except:
                pass

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

    async def _play_roulette_numbers(self, interaction: discord.Interaction, bet: int, numbers: List[int]):
        """Play roulette with multiple number bets"""
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

        # Calculate multiplier based on number count
        num_count = len(numbers)
        multiplier = get_multiplier_for_numbers(num_count)

        # Take the bet
        remove_coins(interaction.guild.id, interaction.user.id, bet)

        # Build bet display
        numbers_display = format_numbers_display(numbers)

        # Initial embed - spinning
        embed = discord.Embed(
            title="🎰 Roulette - Multi-Number Bet",
            description="The wheel is spinning...",
            color=discord.Color.gold()
        )
        embed.add_field(
            name=f"Your Bet ({num_count} number{'s' if num_count > 1 else ''})",
            value=f"**{bet:,}** coins on:\n{numbers_display}",
            inline=False
        )
        embed.add_field(
            name="Potential Payout",
            value=f"**{multiplier}x** = **{bet * multiplier:,}** coins",
            inline=True
        )
        embed.set_footer(text=f"Player: {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

        # Animate spinning
        await asyncio.sleep(1.5)

        # Spin the wheel
        result = random.randint(0, 36)
        won = result in numbers

        # Calculate payout
        user_id = interaction.user.id
        if won:
            payout = bet * multiplier
            add_coins(interaction.guild.id, interaction.user.id, payout, source="roulette_win")
            profit = payout - bet
            record_gamble(interaction.guild.id, interaction.user.id, bet, True, profit)
            result_color = discord.Color.green()
            result_text = f"**YOU WIN!** +{profit:,} coins"

            # Track achievements
            try:
                update_user_stat(user_id, "gambling_winnings", increment=profit)
                stats = get_user_stats(user_id)
                current_streak = stats.get("current_win_streak", 0) + 1
                update_user_stat(user_id, "current_win_streak", value=current_streak)
                update_user_stat(user_id, "max_win_streak", value=current_streak)
                check_and_complete_achievements(user_id)
            except:
                pass
        else:
            record_gamble(interaction.guild.id, interaction.user.id, bet, False)
            result_color = discord.Color.red()
            result_text = f"**You lose!** -{bet:,} coins"

            # Reset win streak
            try:
                update_user_stat(user_id, "current_win_streak", value=0)
            except:
                pass

        # Result embed
        result_embed = discord.Embed(
            title="🎰 Roulette - Multi-Number Bet",
            color=result_color
        )

        # Show the result with emphasis
        result_embed.add_field(
            name="The ball landed on...",
            value=f"# {get_color_emoji(result)} {result}",
            inline=False
        )

        # Show if result was in their numbers
        if won:
            result_embed.add_field(
                name="Match!",
                value=f"{get_color_emoji(result)} **{result}** was in your selection!",
                inline=False
            )

        result_embed.add_field(
            name=f"Your Numbers ({num_count})",
            value=numbers_display,
            inline=False
        )

        result_embed.add_field(
            name="Bet",
            value=f"**{bet:,}** coins\n({multiplier}x payout)",
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
