"""
Blackjack Game Command
Play blackjack against the dealer with virtual coins

Features:
- Full deck simulation
- Hit, Stand, Double Down
- Dealer hits until 17
- Blackjack pays 1.5x
- Regular win pays 1x
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import random
from typing import List, Tuple

import config
from utils.logger import log_command, logger
from utils.economy_db import get_balance, add_coins, remove_coins, record_gamble


# Card suits and values
SUITS = ['♠️', '♥️', '♦️', '♣️']
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

# Card values
CARD_VALUES = {
    'A': 11, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
    '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10
}


class Card:
    """Represents a playing card"""

    def __init__(self, rank: str, suit: str):
        self.rank = rank
        self.suit = suit
        self.value = CARD_VALUES[rank]

    def __str__(self):
        return f"{self.rank}{self.suit}"

    def display(self) -> str:
        """Display card with formatting"""
        return f"`{self.rank}{self.suit}`"


class Deck:
    """Represents a deck of cards"""

    def __init__(self, num_decks: int = 1):
        self.cards = []
        for _ in range(num_decks):
            for suit in SUITS:
                for rank in RANKS:
                    self.cards.append(Card(rank, suit))
        random.shuffle(self.cards)

    def draw(self) -> Card:
        """Draw a card from the deck"""
        if not self.cards:
            # Reshuffle if deck is empty
            self.__init__()
        return self.cards.pop()


class Hand:
    """Represents a hand of cards"""

    def __init__(self):
        self.cards: List[Card] = []

    def add_card(self, card: Card):
        """Add a card to the hand"""
        self.cards.append(card)

    def get_value(self) -> int:
        """Calculate hand value, handling Aces"""
        value = sum(card.value for card in self.cards)
        aces = sum(1 for card in self.cards if card.rank == 'A')

        # Convert Aces from 11 to 1 if busting
        while value > 21 and aces > 0:
            value -= 10
            aces -= 1

        return value

    def is_blackjack(self) -> bool:
        """Check if hand is a natural blackjack"""
        return len(self.cards) == 2 and self.get_value() == 21

    def is_bust(self) -> bool:
        """Check if hand is bust"""
        return self.get_value() > 21

    def display(self, hide_first: bool = False) -> str:
        """Display the hand"""
        if hide_first and len(self.cards) > 0:
            return f"`??` {' '.join(card.display() for card in self.cards[1:])}"
        return ' '.join(card.display() for card in self.cards)

    def display_value(self, hide_first: bool = False) -> str:
        """Display the hand value"""
        if hide_first:
            return "?"
        return str(self.get_value())


class BlackjackGame:
    """Represents a blackjack game"""

    def __init__(self, player: discord.Member, bet: int):
        self.player = player
        self.bet = bet
        self.deck = Deck(num_decks=2)
        self.player_hand = Hand()
        self.dealer_hand = Hand()
        self.game_over = False
        self.result = None  # "win", "lose", "push", "blackjack"
        self.doubled = False

        # Deal initial cards
        self.player_hand.add_card(self.deck.draw())
        self.dealer_hand.add_card(self.deck.draw())
        self.player_hand.add_card(self.deck.draw())
        self.dealer_hand.add_card(self.deck.draw())

        # Check for natural blackjack
        if self.player_hand.is_blackjack():
            self._dealer_play()
            if self.dealer_hand.is_blackjack():
                self.result = "push"
            else:
                self.result = "blackjack"
            self.game_over = True

    def hit(self) -> bool:
        """Player hits, returns True if still in game"""
        self.player_hand.add_card(self.deck.draw())

        if self.player_hand.is_bust():
            self.result = "lose"
            self.game_over = True
            return False

        return True

    def stand(self):
        """Player stands, dealer plays"""
        self._dealer_play()
        self._determine_winner()
        self.game_over = True

    def double_down(self) -> bool:
        """Player doubles down - one more card then stand"""
        self.doubled = True
        self.bet *= 2
        self.player_hand.add_card(self.deck.draw())

        if self.player_hand.is_bust():
            self.result = "lose"
            self.game_over = True
            return False

        self.stand()
        return True

    def _dealer_play(self):
        """Dealer plays their hand (hits until 17)"""
        while self.dealer_hand.get_value() < 17:
            self.dealer_hand.add_card(self.deck.draw())

    def _determine_winner(self):
        """Determine the winner"""
        player_value = self.player_hand.get_value()
        dealer_value = self.dealer_hand.get_value()

        if self.dealer_hand.is_bust():
            self.result = "win"
        elif player_value > dealer_value:
            self.result = "win"
        elif player_value < dealer_value:
            self.result = "lose"
        else:
            self.result = "push"

    def get_payout(self) -> int:
        """Calculate payout based on result"""
        if self.result == "blackjack":
            return int(self.bet * 1.5)  # Blackjack pays 3:2
        elif self.result == "win":
            return self.bet  # Regular win pays 1:1
        elif self.result == "push":
            return 0  # Push returns bet (handled separately)
        else:
            return -self.bet  # Lose

    def build_embed(self, show_dealer: bool = False) -> discord.Embed:
        """Build the game embed"""
        if self.game_over:
            show_dealer = True

        # Determine embed color based on state
        if not self.game_over:
            color = discord.Color.blue()
        elif self.result == "blackjack":
            color = discord.Color.gold()
        elif self.result == "win":
            color = discord.Color.green()
        elif self.result == "push":
            color = discord.Color.orange()
        else:
            color = discord.Color.red()

        embed = discord.Embed(
            title="Blackjack",
            color=color
        )

        # Dealer's hand
        embed.add_field(
            name=f"Dealer's Hand ({self.dealer_hand.display_value(not show_dealer)})",
            value=self.dealer_hand.display(not show_dealer),
            inline=False
        )

        # Player's hand
        embed.add_field(
            name=f"Your Hand ({self.player_hand.get_value()})",
            value=self.player_hand.display(),
            inline=False
        )

        # Bet info
        bet_text = f"**{self.bet:,}** coins"
        if self.doubled:
            bet_text += " (Doubled!)"
        embed.add_field(name="Bet", value=bet_text, inline=True)

        # Result
        if self.game_over:
            payout = self.get_payout()
            if self.result == "blackjack":
                embed.add_field(name="Result", value="BLACKJACK! You win!", inline=True)
                embed.add_field(name="Winnings", value=f"+{payout:,} coins", inline=True)
            elif self.result == "win":
                embed.add_field(name="Result", value="You win!", inline=True)
                embed.add_field(name="Winnings", value=f"+{payout:,} coins", inline=True)
            elif self.result == "push":
                embed.add_field(name="Result", value="Push! Bet returned.", inline=True)
            else:
                embed.add_field(name="Result", value="Dealer wins!", inline=True)
                embed.add_field(name="Lost", value=f"-{self.bet:,} coins", inline=True)

        embed.set_footer(text=f"Player: {self.player.display_name}")

        return embed


class BlackjackView(View):
    """View for blackjack game controls"""

    def __init__(self, game: BlackjackGame, original_bet: int, guild_id: int, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.game = game
        self.original_bet = original_bet
        self.guild_id = guild_id
        self.message = None

        # Check if double down is possible
        can_double = get_balance(guild_id, game.player.id) >= game.bet

        # Update button states
        if game.game_over:
            self._disable_all()
        else:
            # Disable double if not enough balance
            for item in self.children:
                if isinstance(item, Button) and item.label == "Double Down":
                    item.disabled = not can_double

    def _disable_all(self):
        """Disable all buttons"""
        for item in self.children:
            item.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.game.player.id:
            await interaction.response.send_message(
                "This is not your game!",
                ephemeral=True
            )
            return False
        return True

    async def _end_game(self, interaction: discord.Interaction):
        """Handle end of game payouts"""
        payout = self.game.get_payout()

        if self.game.result == "push":
            # Return the bet
            add_coins(self.guild_id, self.game.player.id, self.game.bet, source="blackjack_push")
        elif payout > 0:
            # Player won - add winnings (bet was already taken, add bet + winnings)
            add_coins(self.guild_id, self.game.player.id, self.game.bet + payout, source="blackjack_win")
            record_gamble(self.guild_id, self.game.player.id, self.original_bet, True, payout)
        else:
            # Player lost - bet was already taken
            record_gamble(self.guild_id, self.game.player.id, self.original_bet, False)

        self._disable_all()
        await interaction.response.edit_message(embed=self.game.build_embed(), view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit_button(self, interaction: discord.Interaction, button: Button):
        """Hit - draw another card"""
        still_playing = self.game.hit()

        if not still_playing:
            await self._end_game(interaction)
        else:
            await interaction.response.edit_message(embed=self.game.build_embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand_button(self, interaction: discord.Interaction, button: Button):
        """Stand - stop drawing cards"""
        self.game.stand()
        await self._end_game(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.success, emoji="💰")
    async def double_button(self, interaction: discord.Interaction, button: Button):
        """Double down - double bet, take one card, then stand"""
        # Take additional bet
        success, _ = remove_coins(self.guild_id, self.game.player.id, self.original_bet)
        if not success:
            await interaction.response.send_message(
                "Not enough coins to double down!",
                ephemeral=True
            )
            return

        self.game.double_down()
        await self._end_game(interaction)

    async def on_timeout(self):
        """Handle timeout - auto-stand"""
        if not self.game.game_over:
            self.game.stand()

            payout = self.game.get_payout()
            if self.game.result == "push":
                add_coins(self.guild_id, self.game.player.id, self.game.bet, source="blackjack_push")
            elif payout > 0:
                add_coins(self.guild_id, self.game.player.id, self.game.bet + payout, source="blackjack_win")
                record_gamble(self.guild_id, self.game.player.id, self.original_bet, True, payout)
            else:
                record_gamble(self.guild_id, self.game.player.id, self.original_bet, False)

            self._disable_all()
            if self.message:
                try:
                    await self.message.edit(
                        content="*Game timed out - Auto-stand*",
                        embed=self.game.build_embed(),
                        view=self
                    )
                except:
                    pass


class Blackjack(commands.Cog):
    """Blackjack game command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="blackjack", description="Play blackjack against the dealer")
    @app_commands.describe(bet="Amount of coins to bet")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        """Play blackjack"""
        log_command(str(interaction.user), interaction.user.id, f"blackjack {bet}", interaction.guild.name)

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

        # Create game
        game = BlackjackGame(interaction.user, bet)
        view = BlackjackView(game, bet, interaction.guild.id)

        # If game is already over (blackjack), handle payout
        if game.game_over:
            payout = game.get_payout()
            if game.result == "push":
                add_coins(interaction.guild.id, interaction.user.id, bet, source="blackjack_push")
            elif payout > 0:
                add_coins(interaction.guild.id, interaction.user.id, bet + payout, source="blackjack_win")
                record_gamble(interaction.guild.id, interaction.user.id, bet, True, payout)
            else:
                record_gamble(interaction.guild.id, interaction.user.id, bet, False)
            view._disable_all()

        await interaction.response.send_message(embed=game.build_embed(), view=view)

        # Store message reference for timeout
        msg = await interaction.original_response()
        view.message = msg


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Blackjack cog to the bot"""
    await bot.add_cog(Blackjack(bot))
