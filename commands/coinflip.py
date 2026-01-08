"""
Coinflip Duel Command
Challenge another user to a coin flip for coins

Features:
- Challenge any user for a bet amount
- Challenged user must accept or decline
- Challenger picks heads or tails
- Winner takes both bets
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio

import config
from utils.logger import log_command, logger
from utils.economy_db import get_balance, add_coins, remove_coins, record_gamble


class CoinflipChallengeView(View):
    """View for accepting/declining a coinflip challenge"""

    def __init__(
        self,
        challenger: discord.Member,
        target: discord.Member,
        bet: int,
        guild_id: int,
        timeout: float = 60
    ):
        super().__init__(timeout=timeout)
        self.challenger = challenger
        self.target = target
        self.bet = bet
        self.guild_id = guild_id
        self.accepted = None
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target.id:
            await interaction.response.send_message(
                f"Only {self.target.mention} can respond to this challenge!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        """Accept the challenge"""
        # Check if target has enough coins
        target_balance = get_balance(self.guild_id, self.target.id)
        if target_balance < self.bet:
            await interaction.response.send_message(
                f"You don't have enough coins! Your balance: **{target_balance:,}** coins",
                ephemeral=True
            )
            return

        self.accepted = True
        self._disable_all()

        # Take bet from target (challenger's bet was already taken)
        remove_coins(self.guild_id, self.target.id, self.bet)

        # Show choice screen for challenger
        choice_embed = discord.Embed(
            title="Coinflip Duel - Choose Your Side",
            description=f"{self.challenger.mention}, pick **Heads** or **Tails**!",
            color=discord.Color.gold()
        )
        choice_embed.add_field(name="Bet", value=f"**{self.bet:,}** coins each", inline=True)
        choice_embed.add_field(name="Total Pot", value=f"**{self.bet * 2:,}** coins", inline=True)
        choice_embed.add_field(
            name="Players",
            value=f"{self.challenger.mention} vs {self.target.mention}",
            inline=False
        )

        choice_view = CoinflipChoiceView(
            self.challenger, self.target, self.bet, self.guild_id
        )

        await interaction.response.edit_message(embed=choice_embed, view=choice_view)
        choice_view.message = self.message
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline_button(self, interaction: discord.Interaction, button: Button):
        """Decline the challenge"""
        self.accepted = False
        self._disable_all()

        # Refund challenger's bet
        add_coins(self.guild_id, self.challenger.id, self.bet, source="coinflip_declined")

        embed = discord.Embed(
            title="Coinflip Challenge Declined",
            description=f"{self.target.mention} declined the challenge.\nBet has been refunded to {self.challenger.mention}.",
            color=discord.Color.grey()
        )

        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    def _disable_all(self):
        """Disable all buttons"""
        for item in self.children:
            item.disabled = True

    async def on_timeout(self):
        """Handle timeout - refund bet"""
        if self.accepted is None:
            # Refund challenger's bet
            add_coins(self.guild_id, self.challenger.id, self.bet, source="coinflip_timeout")

            embed = discord.Embed(
                title="Coinflip Challenge Expired",
                description=f"{self.target.mention} didn't respond in time.\nBet has been refunded to {self.challenger.mention}.",
                color=discord.Color.grey()
            )

            self._disable_all()
            if self.message:
                try:
                    await self.message.edit(embed=embed, view=self)
                except:
                    pass


class CoinflipChoiceView(View):
    """View for choosing heads or tails"""

    def __init__(
        self,
        challenger: discord.Member,
        target: discord.Member,
        bet: int,
        guild_id: int,
        timeout: float = 30
    ):
        super().__init__(timeout=timeout)
        self.challenger = challenger
        self.target = target
        self.bet = bet
        self.guild_id = guild_id
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.challenger.id:
            await interaction.response.send_message(
                f"Only {self.challenger.mention} can choose!",
                ephemeral=True
            )
            return False
        return True

    async def _flip_coin(self, interaction: discord.Interaction, choice: str):
        """Flip the coin and determine winner"""
        self._disable_all()

        # Show flipping animation
        flip_embed = discord.Embed(
            title="Coinflip Duel",
            description="🪙 Flipping the coin...",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=flip_embed, view=None)

        await asyncio.sleep(1.5)

        # Flip result
        result = random.choice(["heads", "tails"])
        challenger_won = (choice == result)

        if challenger_won:
            winner = self.challenger
            loser = self.target
        else:
            winner = self.target
            loser = self.challenger

        # Give winnings to winner
        total_pot = self.bet * 2
        add_coins(self.guild_id, winner.id, total_pot, source="coinflip_win")

        # Record gambling stats
        record_gamble(self.guild_id, winner.id, self.bet, True, self.bet)
        record_gamble(self.guild_id, loser.id, self.bet, False)

        # Result embed
        result_emoji = "🪙" if result == "heads" else "🪙"
        result_embed = discord.Embed(
            title="Coinflip Duel - Result",
            description=f"The coin landed on **{result.upper()}**!",
            color=discord.Color.green() if challenger_won else discord.Color.red()
        )

        result_embed.add_field(
            name="Winner",
            value=f"🎉 {winner.mention} wins **{total_pot:,}** coins!",
            inline=False
        )

        result_embed.add_field(
            name=f"{self.challenger.display_name}'s Pick",
            value=choice.capitalize(),
            inline=True
        )

        result_embed.add_field(
            name="Result",
            value=result.capitalize(),
            inline=True
        )

        await interaction.edit_original_response(embed=result_embed, view=None)
        self.stop()

    @discord.ui.button(label="Heads", style=discord.ButtonStyle.primary, emoji="🪙")
    async def heads_button(self, interaction: discord.Interaction, button: Button):
        await self._flip_coin(interaction, "heads")

    @discord.ui.button(label="Tails", style=discord.ButtonStyle.primary, emoji="🪙")
    async def tails_button(self, interaction: discord.Interaction, button: Button):
        await self._flip_coin(interaction, "tails")

    def _disable_all(self):
        """Disable all buttons"""
        for item in self.children:
            item.disabled = True

    async def on_timeout(self):
        """Handle timeout - random choice"""
        if self.message:
            # Pick random choice for challenger
            choice = random.choice(["heads", "tails"])

            # Flip result
            result = random.choice(["heads", "tails"])
            challenger_won = (choice == result)

            if challenger_won:
                winner = self.challenger
                loser = self.target
            else:
                winner = self.target
                loser = self.challenger

            # Give winnings to winner
            total_pot = self.bet * 2
            add_coins(self.guild_id, winner.id, total_pot, source="coinflip_win")

            # Record gambling stats
            record_gamble(self.guild_id, winner.id, self.bet, True, self.bet)
            record_gamble(self.guild_id, loser.id, self.bet, False)

            result_embed = discord.Embed(
                title="Coinflip Duel - Result",
                description=f"*{self.challenger.display_name} didn't pick in time - random choice made*\n\n"
                           f"The coin landed on **{result.upper()}**!",
                color=discord.Color.green() if challenger_won else discord.Color.red()
            )

            result_embed.add_field(
                name="Winner",
                value=f"🎉 {winner.mention} wins **{total_pot:,}** coins!",
                inline=False
            )

            try:
                await self.message.edit(embed=result_embed, view=None)
            except:
                pass


class Coinflip(commands.Cog):
    """Coinflip duel command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="Challenge someone to a coinflip duel for coins")
    @app_commands.describe(
        opponent="The user you want to challenge",
        bet="Amount of coins to bet"
    )
    async def coinflip(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member,
        bet: int
    ):
        """Challenge another user to a coinflip"""
        log_command(str(interaction.user), interaction.user.id, f"coinflip {opponent} {bet}", interaction.guild.name)

        # Validate
        if opponent.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't challenge yourself!",
                ephemeral=True
            )
            return

        if opponent.bot:
            await interaction.response.send_message(
                "You can't challenge a bot!",
                ephemeral=True
            )
            return

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

        # Check challenger's balance
        challenger_balance = get_balance(interaction.guild.id, interaction.user.id)
        if challenger_balance < bet:
            await interaction.response.send_message(
                f"You don't have enough coins! Your balance: **{challenger_balance:,}** coins",
                ephemeral=True
            )
            return

        # Check opponent's balance
        opponent_balance = get_balance(interaction.guild.id, opponent.id)
        if opponent_balance < bet:
            await interaction.response.send_message(
                f"{opponent.mention} doesn't have enough coins! They have: **{opponent_balance:,}** coins",
                ephemeral=True
            )
            return

        # Take challenger's bet
        remove_coins(interaction.guild.id, interaction.user.id, bet)

        # Create challenge embed
        embed = discord.Embed(
            title="Coinflip Challenge!",
            description=f"{interaction.user.mention} challenges {opponent.mention} to a coinflip!",
            color=discord.Color.gold()
        )
        embed.add_field(name="Bet Amount", value=f"**{bet:,}** coins each", inline=True)
        embed.add_field(name="Total Pot", value=f"**{bet * 2:,}** coins", inline=True)
        embed.add_field(
            name="How it works",
            value="If accepted, the challenger picks Heads or Tails.\nWinner takes all!",
            inline=False
        )
        embed.set_footer(text=f"{opponent.display_name} has 60 seconds to respond")

        view = CoinflipChallengeView(
            interaction.user, opponent, bet, interaction.guild.id
        )

        await interaction.response.send_message(
            content=f"{opponent.mention}",
            embed=embed,
            view=view
        )

        msg = await interaction.original_response()
        view.message = msg


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Coinflip cog to the bot"""
    await bot.add_cog(Coinflip(bot))
