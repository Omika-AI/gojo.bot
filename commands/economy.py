"""
Economy Commands
Basic economy management commands for the virtual currency system

Commands:
- /balance - Check your coin balance
- /claimdaily - Claim daily coins (streak bonus)
- /givecoins - Give coins to a user (Admin only)
- /leaderboard - View the richest users
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from typing import Optional

import config
from utils.logger import log_command, logger
from utils.economy_db import (
    get_balance,
    add_coins,
    claim_daily,
    get_user_stats,
    get_leaderboard,
    DAILY_BASE_AMOUNT,
    DAILY_STREAK_BONUS,
    MAX_STREAK_BONUS
)
from utils.achievements_data import (
    update_user_stat as update_achievement_stat,
    check_and_complete_achievements
)


# =============================================================================
# GIVE COINS VIEW (Admin)
# =============================================================================

class GiveCoinsView(View):
    """View for admins to give coins to users"""

    def __init__(self, admin: discord.Member, target: discord.Member, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.admin = admin
        self.target = target
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.admin.id:
            await interaction.response.send_message(
                "Only the admin who ran the command can use these buttons!",
                ephemeral=True
            )
            return False
        return True

    async def _give_coins(self, interaction: discord.Interaction, amount: int):
        """Give coins to the target user"""
        new_balance = add_coins(
            interaction.guild.id,
            self.target.id,
            amount,
            source=f"admin_gift_by_{self.admin.id}"
        )

        embed = discord.Embed(
            title="Coins Given",
            description=f"Gave **{amount:,}** coins to {self.target.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="New Balance", value=f"{new_balance:,} coins", inline=True)
        embed.add_field(name="Given by", value=self.admin.mention, inline=True)

        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="10 Coins", style=discord.ButtonStyle.secondary)
    async def give_10(self, interaction: discord.Interaction, button: Button):
        await self._give_coins(interaction, 10)

    @discord.ui.button(label="50 Coins", style=discord.ButtonStyle.secondary)
    async def give_50(self, interaction: discord.Interaction, button: Button):
        await self._give_coins(interaction, 50)

    @discord.ui.button(label="100 Coins", style=discord.ButtonStyle.primary)
    async def give_100(self, interaction: discord.Interaction, button: Button):
        await self._give_coins(interaction, 100)

    @discord.ui.button(label="1000 Coins", style=discord.ButtonStyle.primary)
    async def give_1000(self, interaction: discord.Interaction, button: Button):
        await self._give_coins(interaction, 1000)

    @discord.ui.button(label="Custom Amount", style=discord.ButtonStyle.success, emoji="✏️")
    async def give_custom(self, interaction: discord.Interaction, button: Button):
        """Open modal for custom amount"""
        modal = CustomAmountModal(self.admin, self.target)
        await interaction.response.send_modal(modal)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="Cancelled",
            description="Coin gift cancelled.",
            color=discord.Color.grey()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


class CustomAmountModal(Modal):
    """Modal for entering a custom coin amount"""

    def __init__(self, admin: discord.Member, target: discord.Member):
        super().__init__(title="Give Custom Amount")
        self.admin = admin
        self.target = target

        self.amount_input = TextInput(
            label="Amount of Coins",
            placeholder="Enter a number (e.g., 500)",
            required=True,
            min_length=1,
            max_length=10
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value)
            if amount <= 0:
                await interaction.response.send_message(
                    "Amount must be a positive number!",
                    ephemeral=True
                )
                return

            if amount > 1000000:
                await interaction.response.send_message(
                    "Maximum amount is 1,000,000 coins!",
                    ephemeral=True
                )
                return

            new_balance = add_coins(
                interaction.guild.id,
                self.target.id,
                amount,
                source=f"admin_gift_by_{self.admin.id}"
            )

            embed = discord.Embed(
                title="Coins Given",
                description=f"Gave **{amount:,}** coins to {self.target.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="New Balance", value=f"{new_balance:,} coins", inline=True)
            embed.add_field(name="Given by", value=self.admin.mention, inline=True)

            await interaction.response.send_message(embed=embed)

        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number!",
                ephemeral=True
            )


# =============================================================================
# ECONOMY COG
# =============================================================================

class Economy(commands.Cog):
    """Economy commands for virtual currency"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Check your coin balance")
    @app_commands.describe(user="User to check balance for (optional)")
    async def balance(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Check coin balance"""
        log_command(str(interaction.user), interaction.user.id, "balance", interaction.guild.name)

        target = user or interaction.user
        balance = get_balance(interaction.guild.id, target.id)
        stats = get_user_stats(interaction.guild.id, target.id)

        embed = discord.Embed(
            title=f"Balance: {target.display_name}",
            color=discord.Color.gold()
        )

        if target.avatar:
            embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="Coins", value=f"**{balance:,}**", inline=True)
        embed.add_field(name="Daily Streak", value=f"{stats['daily_streak']} days", inline=True)
        embed.add_field(name="Total Earned", value=f"{stats['total_earned']:,}", inline=True)

        # Gambling stats
        net_gambling = stats['total_won'] - stats['total_lost']
        gambling_emoji = "📈" if net_gambling >= 0 else "📉"
        embed.add_field(
            name=f"{gambling_emoji} Gambling Profit",
            value=f"{net_gambling:+,} coins",
            inline=True
        )
        embed.add_field(name="Total Gambled", value=f"{stats['total_gambled']:,}", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="claimdaily", description="Claim your daily coins")
    async def claimdaily(self, interaction: discord.Interaction):
        """Claim daily coins with streak bonus"""
        log_command(str(interaction.user), interaction.user.id, "claimdaily", interaction.guild.name)

        success, amount, streak, message = claim_daily(interaction.guild.id, interaction.user.id)

        if not success:
            embed = discord.Embed(
                title="Daily Already Claimed",
                description=message,
                color=discord.Color.red()
            )
            embed.add_field(name="Current Streak", value=f"{streak} days", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Calculate streak bonus for display
        streak_bonus = min(streak * DAILY_STREAK_BONUS, MAX_STREAK_BONUS)

        # Track achievement progress for daily streak
        try:
            update_achievement_stat(interaction.user.id, "max_daily_streak", value=streak)
            check_and_complete_achievements(interaction.user.id)
        except:
            pass

        embed = discord.Embed(
            title="Daily Coins Claimed!",
            description=f"You received **{amount:,}** coins!",
            color=discord.Color.green()
        )

        embed.add_field(name="Base Amount", value=f"{DAILY_BASE_AMOUNT} coins", inline=True)
        embed.add_field(name="Streak Bonus", value=f"+{streak_bonus} coins", inline=True)
        embed.add_field(name="Current Streak", value=f"{streak} days", inline=True)

        new_balance = get_balance(interaction.guild.id, interaction.user.id)
        embed.add_field(name="New Balance", value=f"{new_balance:,} coins", inline=False)

        # Streak milestone messages
        if streak == 7:
            embed.add_field(name="Milestone!", value="1 week streak! Keep it up!", inline=False)
        elif streak == 30:
            embed.add_field(name="Milestone!", value="1 month streak! Amazing dedication!", inline=False)
        elif streak == 50:
            embed.add_field(name="Milestone!", value="50 day streak! Maximum bonus reached!", inline=False)

        embed.set_footer(text="Claim again in 20 hours to keep your streak!")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="givecoins", description="Give coins to a user (Owner only)")
    @app_commands.describe(user="The user to give coins to")
    async def givecoins(self, interaction: discord.Interaction, user: discord.Member):
        """Owner command to give coins to a user"""
        log_command(str(interaction.user), interaction.user.id, f"givecoins {user}", interaction.guild.name)

        # Only allow specific user IDs to use this command
        allowed_users = [324070041601441813, 259024292329684994]
        if interaction.user.id not in allowed_users:
            await interaction.response.send_message(
                "You don't have permission to use this command!",
                ephemeral=True
            )
            return

        # Can't give coins to bots
        if user.bot:
            await interaction.response.send_message(
                "You can't give coins to bots!",
                ephemeral=True
            )
            return

        current_balance = get_balance(interaction.guild.id, user.id)

        embed = discord.Embed(
            title=f"Give Coins to {user.display_name}",
            description="Select an amount to give or enter a custom amount.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Current Balance", value=f"{current_balance:,} coins", inline=True)

        if user.avatar:
            embed.set_thumbnail(url=user.display_avatar.url)

        view = GiveCoinsView(interaction.user, user)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="leaderboard", description="View the richest users globally")
    async def leaderboard(self, interaction: discord.Interaction):
        """Show the global wealth leaderboard"""
        log_command(str(interaction.user), interaction.user.id, "leaderboard", interaction.guild.name)

        top_users = get_leaderboard(interaction.guild.id, limit=10)

        embed = discord.Embed(
            title="Global Coin Leaderboard",
            description="Top 10 richest users across all servers",
            color=discord.Color.gold()
        )

        if not top_users:
            embed.description = "No users have earned coins yet!"
            await interaction.response.send_message(embed=embed)
            return

        # Build leaderboard text
        leaderboard_text = ""
        medals = ["🥇", "🥈", "🥉"]

        for i, (user_id, balance) in enumerate(top_users):
            # Get user mention or fallback to ID
            try:
                user = await self.bot.fetch_user(int(user_id))
                user_display = user.mention
            except:
                user_display = f"<@{user_id}>"

            # Add medal for top 3
            position = medals[i] if i < 3 else f"`{i+1}.`"
            leaderboard_text += f"{position} {user_display} - **{balance:,}** coins\n"

        embed.add_field(name="Rankings", value=leaderboard_text, inline=False)

        # Show user's position if not in top 10
        user_balance = get_balance(interaction.guild.id, interaction.user.id)
        user_in_top = any(uid == str(interaction.user.id) for uid, _ in top_users)

        if not user_in_top:
            embed.add_field(
                name="Your Balance",
                value=f"{interaction.user.mention} - **{user_balance:,}** coins",
                inline=False
            )

        await interaction.response.send_message(embed=embed)


# Required setup function
async def setup(bot: commands.Bot):
    """Add the Economy cog to the bot"""
    await bot.add_cog(Economy(bot))
