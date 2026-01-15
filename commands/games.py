"""
Advanced Games System - Interactive Discord games

Commands:
- /trivia - Start a trivia game
- /minesweeper - Generate a minesweeper game
- /connect4 - Start a Connect 4 game
- /tictactoe - Start a Tic Tac Toe game
- /rps - Play Rock Paper Scissors
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
from typing import Optional, Literal, List
import random
import asyncio
import aiohttp

from utils.logger import logger


# ============================================
# TRIVIA GAME
# ============================================

class TriviaView(View):
    """View for trivia answers"""

    def __init__(self, correct_answer: str, all_answers: List[str], timeout_seconds: int = 30):
        super().__init__(timeout=timeout_seconds)
        self.correct_answer = correct_answer
        self.answered_users = {}  # user_id -> is_correct
        self.message = None

        # Create buttons for each answer
        for i, answer in enumerate(all_answers):
            button = Button(
                style=discord.ButtonStyle.secondary,
                label=answer[:80],
                custom_id=f"trivia_{i}"
            )
            button.callback = self.create_callback(answer)
            self.add_item(button)

    def create_callback(self, answer: str):
        """Create a callback for answer buttons"""
        async def callback(interaction: discord.Interaction):
            if interaction.user.id in self.answered_users:
                await interaction.response.send_message(
                    "You already answered!",
                    ephemeral=True
                )
                return

            is_correct = answer == self.correct_answer
            self.answered_users[interaction.user.id] = is_correct

            if is_correct:
                await interaction.response.send_message(
                    "✅ Correct!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Wrong! The answer was: **{self.correct_answer}**",
                    ephemeral=True
                )

        return callback

    async def on_timeout(self):
        """When trivia times out"""
        if self.message:
            # Disable all buttons and show answer
            for item in self.children:
                item.disabled = True
                if isinstance(item, Button):
                    if item.label == self.correct_answer:
                        item.style = discord.ButtonStyle.success

            embed = self.message.embeds[0] if self.message.embeds else None
            if embed:
                correct_count = sum(1 for v in self.answered_users.values() if v)
                embed.add_field(
                    name="Results",
                    value=f"✅ {correct_count} correct | ❌ {len(self.answered_users) - correct_count} wrong",
                    inline=False
                )
                embed.color = discord.Color.orange()

            try:
                await self.message.edit(embed=embed, view=self)
            except:
                pass


# ============================================
# CONNECT 4 GAME
# ============================================

class Connect4Game:
    """Connect 4 game logic"""

    def __init__(self, player1: discord.Member, player2: discord.Member):
        self.board = [[0 for _ in range(7)] for _ in range(6)]  # 6 rows, 7 columns
        self.player1 = player1
        self.player2 = player2
        self.current_player = 1
        self.winner = None
        self.game_over = False

    def get_current_member(self) -> discord.Member:
        return self.player1 if self.current_player == 1 else self.player2

    def drop_piece(self, column: int) -> bool:
        """Drop a piece in the column. Returns True if successful."""
        if column < 0 or column > 6:
            return False

        # Find lowest empty row
        for row in range(5, -1, -1):
            if self.board[row][column] == 0:
                self.board[row][column] = self.current_player
                self.check_winner(row, column)
                if not self.game_over:
                    self.current_player = 2 if self.current_player == 1 else 1
                return True

        return False  # Column is full

    def check_winner(self, row: int, col: int):
        """Check if the last move was a winning move"""
        player = self.board[row][col]

        # Check all directions
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]

        for dr, dc in directions:
            count = 1

            # Check forward
            r, c = row + dr, col + dc
            while 0 <= r < 6 and 0 <= c < 7 and self.board[r][c] == player:
                count += 1
                r += dr
                c += dc

            # Check backward
            r, c = row - dr, col - dc
            while 0 <= r < 6 and 0 <= c < 7 and self.board[r][c] == player:
                count += 1
                r -= dr
                c -= dc

            if count >= 4:
                self.winner = player
                self.game_over = True
                return

        # Check for tie
        if all(self.board[0][c] != 0 for c in range(7)):
            self.game_over = True

    def render_board(self) -> str:
        """Render the board as a string"""
        emojis = {0: "⚫", 1: "🔴", 2: "🟡"}
        lines = []

        for row in self.board:
            lines.append(" ".join(emojis[cell] for cell in row))

        lines.append("1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣")

        return "\n".join(lines)


class Connect4View(View):
    """View for Connect 4 game"""

    def __init__(self, game: Connect4Game):
        super().__init__(timeout=300)
        self.game = game
        self.message = None

        # Add column buttons
        for i in range(7):
            button = Button(
                style=discord.ButtonStyle.secondary,
                label=str(i + 1),
                custom_id=f"c4_{i}"
            )
            button.callback = self.create_callback(i)
            self.add_item(button)

    def create_callback(self, column: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user not in [self.game.player1, self.game.player2]:
                await interaction.response.send_message(
                    "You're not part of this game!",
                    ephemeral=True
                )
                return

            if interaction.user != self.game.get_current_member():
                await interaction.response.send_message(
                    "It's not your turn!",
                    ephemeral=True
                )
                return

            if not self.game.drop_piece(column):
                await interaction.response.send_message(
                    "That column is full!",
                    ephemeral=True
                )
                return

            # Update the board
            embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
            embed.description = self.game.render_board()

            if self.game.game_over:
                if self.game.winner:
                    winner = self.game.player1 if self.game.winner == 1 else self.game.player2
                    embed.title = f"🎉 {winner.display_name} wins!"
                    embed.color = discord.Color.gold()
                else:
                    embed.title = "🤝 It's a tie!"
                    embed.color = discord.Color.orange()

                # Disable all buttons
                for item in self.children:
                    item.disabled = True
            else:
                current = self.game.get_current_member()
                embed.title = f"Connect 4 - {current.display_name}'s turn"
                emoji = "🔴" if self.game.current_player == 1 else "🟡"
                embed.set_footer(text=f"{emoji} {current.display_name}")

            await interaction.response.edit_message(embed=embed, view=self)

        return callback


# ============================================
# TIC TAC TOE
# ============================================

class TicTacToeGame:
    """Tic Tac Toe game logic"""

    def __init__(self, player1: discord.Member, player2: discord.Member):
        self.board = [0] * 9
        self.player1 = player1
        self.player2 = player2
        self.current_player = 1
        self.winner = None
        self.game_over = False

    def get_current_member(self) -> discord.Member:
        return self.player1 if self.current_player == 1 else self.player2

    def make_move(self, position: int) -> bool:
        if self.board[position] != 0:
            return False

        self.board[position] = self.current_player
        self.check_winner()

        if not self.game_over:
            self.current_player = 2 if self.current_player == 1 else 1

        return True

    def check_winner(self):
        # Winning combinations
        wins = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Columns
            [0, 4, 8], [2, 4, 6]  # Diagonals
        ]

        for combo in wins:
            if self.board[combo[0]] == self.board[combo[1]] == self.board[combo[2]] != 0:
                self.winner = self.board[combo[0]]
                self.game_over = True
                return

        if 0 not in self.board:
            self.game_over = True


class TicTacToeView(View):
    """View for Tic Tac Toe"""

    def __init__(self, game: TicTacToeGame):
        super().__init__(timeout=300)
        self.game = game

        for i in range(9):
            button = Button(
                style=discord.ButtonStyle.secondary,
                label="⬜",
                custom_id=f"ttt_{i}",
                row=i // 3
            )
            button.callback = self.create_callback(i)
            self.add_item(button)

    def create_callback(self, position: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user not in [self.game.player1, self.game.player2]:
                await interaction.response.send_message("You're not part of this game!", ephemeral=True)
                return

            if interaction.user != self.game.get_current_member():
                await interaction.response.send_message("It's not your turn!", ephemeral=True)
                return

            if not self.game.make_move(position):
                await interaction.response.send_message("That spot is taken!", ephemeral=True)
                return

            # Update button
            symbols = {0: "⬜", 1: "❌", 2: "⭕"}
            self.children[position].label = symbols[self.game.board[position]]
            self.children[position].disabled = True

            if self.game.current_player == 1:
                self.children[position].style = discord.ButtonStyle.danger
            else:
                self.children[position].style = discord.ButtonStyle.primary

            embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()

            if self.game.game_over:
                if self.game.winner:
                    winner = self.game.player1 if self.game.winner == 1 else self.game.player2
                    embed.title = f"🎉 {winner.display_name} wins!"
                    embed.color = discord.Color.gold()
                else:
                    embed.title = "🤝 It's a tie!"
                    embed.color = discord.Color.orange()

                for item in self.children:
                    item.disabled = True
            else:
                current = self.game.get_current_member()
                symbol = "❌" if self.game.current_player == 1 else "⭕"
                embed.title = f"Tic Tac Toe - {current.display_name}'s turn ({symbol})"

            await interaction.response.edit_message(embed=embed, view=self)

        return callback


# ============================================
# ROCK PAPER SCISSORS
# ============================================

class RPSView(View):
    """View for Rock Paper Scissors"""

    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__(timeout=60)
        self.player1 = player1
        self.player2 = player2
        self.choices = {}
        self.message = None

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.secondary)
    async def rock(self, interaction: discord.Interaction, button: Button):
        await self.make_choice(interaction, "rock")

    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.secondary)
    async def paper(self, interaction: discord.Interaction, button: Button):
        await self.make_choice(interaction, "paper")

    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.secondary)
    async def scissors(self, interaction: discord.Interaction, button: Button):
        await self.make_choice(interaction, "scissors")

    async def make_choice(self, interaction: discord.Interaction, choice: str):
        if interaction.user not in [self.player1, self.player2]:
            await interaction.response.send_message("You're not part of this game!", ephemeral=True)
            return

        if interaction.user.id in self.choices:
            await interaction.response.send_message("You already chose!", ephemeral=True)
            return

        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(f"You chose **{choice}**!", ephemeral=True)

        # Check if both players have chosen
        if len(self.choices) == 2:
            await self.end_game()

    async def end_game(self):
        if not self.message:
            return

        c1 = self.choices[self.player1.id]
        c2 = self.choices[self.player2.id]

        # Determine winner
        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

        if c1 == c2:
            result = "🤝 It's a tie!"
            color = discord.Color.orange()
        elif (c1 == "rock" and c2 == "scissors") or \
             (c1 == "paper" and c2 == "rock") or \
             (c1 == "scissors" and c2 == "paper"):
            result = f"🎉 {self.player1.display_name} wins!"
            color = discord.Color.green()
        else:
            result = f"🎉 {self.player2.display_name} wins!"
            color = discord.Color.green()

        embed = discord.Embed(
            title=result,
            description=(
                f"{self.player1.display_name}: {emojis[c1]} {c1}\n"
                f"{self.player2.display_name}: {emojis[c2]} {c2}"
            ),
            color=color
        )

        for item in self.children:
            item.disabled = True

        await self.message.edit(embed=embed, view=self)


# ============================================
# COG
# ============================================

class Games(commands.Cog):
    """Fun games for Discord"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="trivia", description="Start a trivia game")
    @app_commands.describe(
        category="Trivia category",
        difficulty="Question difficulty"
    )
    async def trivia(
        self,
        interaction: discord.Interaction,
        category: Optional[Literal[
            "General Knowledge", "Science", "History", "Geography",
            "Entertainment", "Sports", "Art", "Animals", "Vehicles", "Computers"
        ]] = None,
        difficulty: Optional[Literal["easy", "medium", "hard"]] = None
    ):
        """Start a trivia game"""
        await interaction.response.defer()

        # Map categories to Open Trivia DB IDs
        category_map = {
            "General Knowledge": 9,
            "Science": 17,
            "History": 23,
            "Geography": 22,
            "Entertainment": 11,
            "Sports": 21,
            "Art": 25,
            "Animals": 27,
            "Vehicles": 28,
            "Computers": 18
        }

        # Build API URL
        url = "https://opentdb.com/api.php?amount=1&type=multiple"
        if category:
            url += f"&category={category_map[category]}"
        if difficulty:
            url += f"&difficulty={difficulty}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()

            if data["response_code"] != 0 or not data["results"]:
                await interaction.followup.send("Couldn't fetch a trivia question. Try again!")
                return

            question_data = data["results"][0]

            # Decode HTML entities
            import html
            question = html.unescape(question_data["question"])
            correct = html.unescape(question_data["correct_answer"])
            incorrect = [html.unescape(a) for a in question_data["incorrect_answers"]]

            # Shuffle answers
            all_answers = [correct] + incorrect
            random.shuffle(all_answers)

            # Create embed
            embed = discord.Embed(
                title="🎯 Trivia Time!",
                description=question,
                color=discord.Color.blue()
            )
            embed.add_field(name="Category", value=question_data["category"], inline=True)
            embed.add_field(name="Difficulty", value=question_data["difficulty"].capitalize(), inline=True)
            embed.set_footer(text="You have 30 seconds to answer!")

            view = TriviaView(correct, all_answers)
            msg = await interaction.followup.send(embed=embed, view=view)
            view.message = msg

        except Exception as e:
            logger.error(f"Trivia error: {e}")
            await interaction.followup.send("Error fetching trivia question!")

    @app_commands.command(name="minesweeper", description="Generate a minesweeper game")
    @app_commands.describe(
        size="Board size",
        mines="Number of mines"
    )
    async def minesweeper(
        self,
        interaction: discord.Interaction,
        size: Optional[Literal["small", "medium", "large"]] = "medium",
        mines: Optional[int] = None
    ):
        """Generate a minesweeper board"""
        sizes = {
            "small": (5, 5, 4),
            "medium": (8, 8, 10),
            "large": (10, 10, 15)
        }

        rows, cols, default_mines = sizes[size]
        mine_count = mines if mines else default_mines
        mine_count = min(mine_count, rows * cols - 1)

        # Create empty board
        board = [[0 for _ in range(cols)] for _ in range(rows)]

        # Place mines
        mine_positions = random.sample(range(rows * cols), mine_count)
        for pos in mine_positions:
            r, c = pos // cols, pos % cols
            board[r][c] = -1

        # Calculate numbers
        for r in range(rows):
            for c in range(cols):
                if board[r][c] == -1:
                    continue

                count = 0
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols and board[nr][nc] == -1:
                            count += 1
                board[r][c] = count

        # Convert to spoiler text
        emojis = {
            -1: "💥",
            0: "⬜",
            1: "1️⃣",
            2: "2️⃣",
            3: "3️⃣",
            4: "4️⃣",
            5: "5️⃣",
            6: "6️⃣",
            7: "7️⃣",
            8: "8️⃣"
        }

        lines = []
        for row in board:
            line = " ".join(f"||{emojis[cell]}||" for cell in row)
            lines.append(line)

        board_text = "\n".join(lines)

        embed = discord.Embed(
            title="💣 Minesweeper",
            description=board_text,
            color=discord.Color.dark_grey()
        )
        embed.set_footer(text=f"Size: {rows}x{cols} | Mines: {mine_count}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="connect4", description="Start a Connect 4 game")
    @app_commands.describe(opponent="The person to play against")
    async def connect4(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member
    ):
        """Start a Connect 4 game"""
        if opponent.bot:
            await interaction.response.send_message("You can't play against a bot!", ephemeral=True)
            return

        if opponent == interaction.user:
            await interaction.response.send_message("You can't play against yourself!", ephemeral=True)
            return

        game = Connect4Game(interaction.user, opponent)
        view = Connect4View(game)

        embed = discord.Embed(
            title=f"Connect 4 - {interaction.user.display_name}'s turn",
            description=game.render_board(),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"🔴 {interaction.user.display_name}")

        await interaction.response.send_message(
            f"{opponent.mention}, you've been challenged to Connect 4!",
            embed=embed,
            view=view
        )

    @app_commands.command(name="tictactoe", description="Start a Tic Tac Toe game")
    @app_commands.describe(opponent="The person to play against")
    async def tictactoe(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member
    ):
        """Start a Tic Tac Toe game"""
        if opponent.bot:
            await interaction.response.send_message("You can't play against a bot!", ephemeral=True)
            return

        if opponent == interaction.user:
            await interaction.response.send_message("You can't play against yourself!", ephemeral=True)
            return

        game = TicTacToeGame(interaction.user, opponent)
        view = TicTacToeView(game)

        embed = discord.Embed(
            title=f"Tic Tac Toe - {interaction.user.display_name}'s turn (❌)",
            description=f"{interaction.user.mention} vs {opponent.mention}",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(
            f"{opponent.mention}, you've been challenged to Tic Tac Toe!",
            embed=embed,
            view=view
        )

    @app_commands.command(name="rps", description="Play Rock Paper Scissors")
    @app_commands.describe(opponent="The person to play against")
    async def rps(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member
    ):
        """Play Rock Paper Scissors"""
        if opponent.bot:
            await interaction.response.send_message("You can't play against a bot!", ephemeral=True)
            return

        if opponent == interaction.user:
            await interaction.response.send_message("You can't play against yourself!", ephemeral=True)
            return

        view = RPSView(interaction.user, opponent)

        embed = discord.Embed(
            title="✂️ Rock Paper Scissors",
            description=f"{interaction.user.mention} vs {opponent.mention}\n\nBoth players choose your move!",
            color=discord.Color.blue()
        )
        embed.set_footer(text="You have 60 seconds to choose")

        msg = await interaction.response.send_message(
            f"{opponent.mention}, you've been challenged!",
            embed=embed,
            view=view
        )
        view.message = await interaction.original_response()

    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="Your question for the 8-ball")
    async def eightball(self, interaction: discord.Interaction, question: str):
        """Magic 8-ball"""
        responses = [
            # Positive
            "It is certain.", "It is decidedly so.", "Without a doubt.",
            "Yes, definitely.", "You may rely on it.", "As I see it, yes.",
            "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
            # Neutral
            "Reply hazy, try again.", "Ask again later.",
            "Better not tell you now.", "Cannot predict now.",
            "Concentrate and ask again.",
            # Negative
            "Don't count on it.", "My reply is no.", "My sources say no.",
            "Outlook not so good.", "Very doubtful."
        ]

        response = random.choice(responses)

        embed = discord.Embed(
            title="🎱 Magic 8-Ball",
            color=discord.Color.purple()
        )
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=f"**{response}**", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roll", description="Roll dice")
    @app_commands.describe(dice="Dice notation (e.g., 2d6, d20, 3d8+5)")
    async def roll(self, interaction: discord.Interaction, dice: str = "1d6"):
        """Roll dice"""
        import re

        # Parse dice notation
        match = re.match(r"(\d*)d(\d+)([+-]\d+)?", dice.lower())
        if not match:
            await interaction.response.send_message(
                "Invalid dice format! Use notation like: d6, 2d6, 3d8+5",
                ephemeral=True
            )
            return

        count = int(match.group(1)) if match.group(1) else 1
        sides = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0

        if count > 100 or sides > 1000:
            await interaction.response.send_message("Too many dice or sides!", ephemeral=True)
            return

        # Roll dice
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + modifier

        # Format result
        roll_str = ", ".join(str(r) for r in rolls)
        if modifier:
            result = f"[{roll_str}] {'+' if modifier > 0 else ''}{modifier} = **{total}**"
        else:
            result = f"[{roll_str}] = **{total}**"

        embed = discord.Embed(
            title="🎲 Dice Roll",
            description=f"Rolling **{dice}**\n{result}",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="coinflip", description="Flip a coin")
    async def coinflip(self, interaction: discord.Interaction):
        """Flip a coin"""
        result = random.choice(["Heads", "Tails"])
        emoji = "🪙"

        embed = discord.Embed(
            title=f"{emoji} Coin Flip",
            description=f"**{result}!**",
            color=discord.Color.gold()
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Add the Games cog to the bot"""
    await bot.add_cog(Games(bot))
