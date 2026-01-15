"""
Daily Quests Command - View and track daily quests

Commands:
- /quests - View your daily quests and progress
- /questkeys - Check how many quest keys you have

Quest progress is tracked automatically and rewards can be claimed
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from typing import Optional

from utils.quests_db import (
    get_daily_quests,
    claim_quest_reward,
    check_all_quests_completed,
    claim_quest_key,
    get_quest_keys,
    get_user_quest_stats,
    get_time_until_reset
)
from utils.economy_db import add_coins
from utils.logger import logger


def create_progress_bar(progress: int, target: int, length: int = 10) -> str:
    """Create a visual progress bar"""
    filled = int((progress / target) * length) if target > 0 else 0
    filled = min(filled, length)
    empty = length - filled

    if progress >= target:
        return f"[{'=' * length}]"
    else:
        return f"[{'=' * filled}{'-' * empty}]"


class QuestClaimButton(Button):
    """Button to claim a quest reward"""

    def __init__(self, quest_id: str, quest_name: str, coins: int, row: int = 0):
        super().__init__(
            label=f"Claim {coins} coins",
            style=discord.ButtonStyle.success,
            custom_id=f"claim_quest_{quest_id}",
            row=row
        )
        self.quest_id = quest_id
        self.quest_name = quest_name
        self.coins = coins

    async def callback(self, interaction: discord.Interaction):
        from utils.quests_db import claim_quest_reward
        from utils.economy_db import add_coins

        success, coins = claim_quest_reward(
            interaction.guild.id,
            interaction.user.id,
            self.quest_id
        )

        if success:
            # Add coins to user's balance
            add_coins(interaction.guild.id, interaction.user.id, coins, source="quest_reward")

            await interaction.response.send_message(
                f"**Quest Complete!** You earned **{coins:,}** coins for completing *{self.quest_name}*!",
                ephemeral=True
            )

            # Refresh the quest view
            view = self.view
            if view:
                view.refresh_quests()
                embed = view.build_embed()
                await interaction.message.edit(embed=embed, view=view)
        else:
            await interaction.response.send_message(
                "This quest reward has already been claimed!",
                ephemeral=True
            )


class ClaimKeyButton(Button):
    """Button to claim the daily quest key"""

    def __init__(self, disabled: bool = False):
        super().__init__(
            label="Claim Quest Key",
            style=discord.ButtonStyle.primary,
            custom_id="claim_quest_key",
            disabled=disabled,
            row=2
        )

    async def callback(self, interaction: discord.Interaction):
        from utils.quests_db import claim_quest_key

        success, total_keys = claim_quest_key(
            interaction.guild.id,
            interaction.user.id
        )

        if success:
            await interaction.response.send_message(
                f"**Quest Key Earned!** You now have **{total_keys}** quest key(s)!\n"
                f"Use `/lootbox` to open a lootbox for rare rewards!",
                ephemeral=True
            )

            # Refresh the view
            view = self.view
            if view:
                view.refresh_quests()
                embed = view.build_embed()
                await interaction.message.edit(embed=embed, view=view)
        else:
            await interaction.response.send_message(
                "You've already claimed today's quest key!",
                ephemeral=True
            )


class QuestsView(View):
    """View for displaying daily quests"""

    def __init__(self, bot: commands.Bot, guild_id: int, user_id: int, user: discord.Member, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.user = user
        self.quests = []

        self.refresh_quests()

    def refresh_quests(self):
        """Refresh quest data and update buttons"""
        self.clear_items()
        self.quests = get_daily_quests(self.guild_id, self.user_id)

        # Add claim buttons for completed but unclaimed quests
        row = 0
        for quest_data in self.quests:
            if quest_data["completed"] and not quest_data["claimed"]:
                btn = QuestClaimButton(
                    quest_data["id"],
                    quest_data["quest"]["name"],
                    quest_data["quest"]["reward_coins"],
                    row=row
                )
                self.add_item(btn)
                row += 1
                if row >= 2:  # Max 2 rows for quest claims
                    break

        # Check if all quests are completed
        all_done, key_claimed = check_all_quests_completed(self.guild_id, self.user_id)

        # Add quest key button if all complete
        if all_done:
            self.add_item(ClaimKeyButton(disabled=key_claimed))

    def build_embed(self) -> discord.Embed:
        """Build the quest embed"""
        stats = get_user_quest_stats(self.guild_id, self.user_id)
        time_left = get_time_until_reset()

        embed = discord.Embed(
            title="Daily Quests",
            description=f"Complete all quests to earn a **Quest Key**!\n\nResets in: **{time_left}**",
            color=discord.Color.gold()
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Display each quest
        completed_count = 0
        for quest_data in self.quests:
            quest = quest_data["quest"]
            progress = quest_data["progress"]
            target = quest["target"]
            completed = quest_data["completed"]
            claimed = quest_data["claimed"]

            if completed:
                completed_count += 1

            # Build progress display
            progress_bar = create_progress_bar(progress, target)
            progress_text = f"{progress}/{target}"

            # Status indicator
            if claimed:
                status = "Claimed"
            elif completed:
                status = "Complete!"
            else:
                status = f"{int((progress/target)*100)}%"

            # Format the quest
            desc = quest["description"].format(target=target)
            reward_text = f"+{quest['reward_coins']} coins"

            embed.add_field(
                name=f"{'[DONE]' if claimed else '[' + status + ']'} {quest['name']}",
                value=f"{desc}\n{progress_bar} {progress_text}\nReward: **{reward_text}**",
                inline=False
            )

        # Summary
        all_done, key_claimed = check_all_quests_completed(self.guild_id, self.user_id)

        if key_claimed:
            key_status = "Quest Key claimed for today!"
        elif all_done:
            key_status = "All quests complete! Claim your Quest Key!"
        else:
            key_status = f"{completed_count}/{len(self.quests)} quests completed"

        embed.add_field(
            name="Quest Key",
            value=f"{key_status}\nYou have: **{stats['quest_keys']}** key(s)",
            inline=False
        )

        # Footer with stats
        embed.set_footer(
            text=f"Total quests completed: {stats['total_quests_completed']} | "
                 f"Lootboxes opened: {stats['total_lootboxes_opened']}"
        )

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to use the buttons"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the person who ran the command can use these buttons!",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """Disable all buttons when the view times out"""
        for item in self.children:
            item.disabled = True


class Quests(commands.Cog):
    """Daily quest commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="quests", description="View your daily quests and progress")
    async def quests(self, interaction: discord.Interaction):
        """View daily quests"""

        logger.info(f"Quests viewed by {interaction.user} in {interaction.guild.name}")

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Create the quest view
        view = QuestsView(
            self.bot,
            interaction.guild.id,
            interaction.user.id,
            interaction.user
        )

        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="questkeys", description="Check how many quest keys you have")
    async def questkeys(self, interaction: discord.Interaction):
        """Check quest key count"""

        logger.info(f"Quest keys checked by {interaction.user} in {interaction.guild.name}")

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        keys = get_quest_keys(interaction.guild.id, interaction.user.id)
        stats = get_user_quest_stats(interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="Quest Keys",
            description=f"You have **{keys}** quest key(s)!",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="How to Use",
            value="Use `/lootbox` to open a lootbox with your keys!",
            inline=False
        )

        embed.add_field(
            name="Stats",
            value=(
                f"**Total Quests Completed:** {stats['total_quests_completed']}\n"
                f"**Lootboxes Opened:** {stats['total_lootboxes_opened']}"
            ),
            inline=False
        )

        embed.set_footer(text="Complete all 3 daily quests to earn a key!")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(Quests(bot))
