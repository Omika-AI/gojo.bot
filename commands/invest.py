"""
Community Stock Market Commands - Invest in other members!

Commands:
- /invest @user [shares] - Buy shares in a member
- /sell @user [shares] - Sell shares
- /portfolio - View your investment portfolio
- /stockprice @user - Check a member's stock price
- /stockmarket - View the market overview
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from typing import Optional

from utils.stocks_db import (
    get_stock_price,
    get_member_stock_info,
    buy_shares,
    sell_shares,
    get_portfolio,
    get_top_stocks,
    get_most_invested,
    BASE_STOCK_PRICE,
    MAX_SHARES_PER_PERSON,
    TRANSACTION_FEE_PERCENT
)
from utils.economy_db import get_balance
from utils.logger import logger


class Invest(commands.Cog):
    """Stock market commands for investing in other members"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="invest", description="Buy shares in another member's stock")
    @app_commands.describe(
        member="The member to invest in",
        shares="Number of shares to buy (default: 1)"
    )
    async def invest(self, interaction: discord.Interaction, member: discord.Member, shares: int = 1):
        """Buy shares in another member"""

        logger.info(f"Invest command: {interaction.user} buying {shares} shares of {member}")

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        if member.bot:
            await interaction.response.send_message(
                "You can't invest in bots!",
                ephemeral=True
            )
            return

        if shares <= 0:
            await interaction.response.send_message(
                "You must buy at least 1 share!",
                ephemeral=True
            )
            return

        if shares > MAX_SHARES_PER_PERSON:
            await interaction.response.send_message(
                f"Maximum shares per transaction is {MAX_SHARES_PER_PERSON}!",
                ephemeral=True
            )
            return

        # Get stock info for preview
        stock_info = get_member_stock_info(interaction.guild.id, member.id)
        price = stock_info["current_price"]
        total_cost = price * shares
        fee = int(total_cost * TRANSACTION_FEE_PERCENT / 100)

        # Check balance
        balance = get_balance(interaction.guild.id, interaction.user.id)

        # Attempt purchase
        success, message, cost, new_holding = buy_shares(
            interaction.guild.id,
            interaction.user.id,
            member.id,
            shares
        )

        if success:
            embed = discord.Embed(
                title="Investment Successful!",
                description=message,
                color=discord.Color.green()
            )
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Shares Bought", value=f"{shares}", inline=True)
            embed.add_field(name="Price per Share", value=f"{price:,} coins", inline=True)
            embed.add_field(name="Total Cost", value=f"{cost:,} coins (incl. {fee:,} fee)", inline=True)
            embed.add_field(name="Your Holdings", value=f"{new_holding} shares", inline=True)
            embed.add_field(name="New Balance", value=f"{balance - cost:,} coins", inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Investor: {interaction.user.display_name}")
        else:
            embed = discord.Embed(
                title="Investment Failed",
                description=message,
                color=discord.Color.red()
            )
            embed.add_field(name="Attempted", value=f"{shares} shares of {member.display_name}", inline=False)
            embed.add_field(name="Your Balance", value=f"{balance:,} coins", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="sell", description="Sell shares in another member's stock")
    @app_commands.describe(
        member="The member to sell shares of",
        shares="Number of shares to sell (default: all)"
    )
    async def sell(self, interaction: discord.Interaction, member: discord.Member, shares: Optional[int] = None):
        """Sell shares in another member"""

        logger.info(f"Sell command: {interaction.user} selling shares of {member}")

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Get current holdings to determine shares to sell
        portfolio = get_portfolio(interaction.guild.id, interaction.user.id)
        holding = portfolio["holdings"].get(str(member.id))

        if not holding or holding["shares"] <= 0:
            await interaction.response.send_message(
                f"You don't own any shares of {member.display_name}!",
                ephemeral=True
            )
            return

        # Default to selling all shares
        if shares is None:
            shares = holding["shares"]

        if shares <= 0:
            await interaction.response.send_message(
                "You must sell at least 1 share!",
                ephemeral=True
            )
            return

        # Attempt sale
        success, message, received, profit_loss = sell_shares(
            interaction.guild.id,
            interaction.user.id,
            member.id,
            shares
        )

        if success:
            embed = discord.Embed(
                title="Sale Successful!",
                description=message,
                color=discord.Color.green() if profit_loss >= 0 else discord.Color.red()
            )
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Shares Sold", value=f"{shares}", inline=True)
            embed.add_field(name="Amount Received", value=f"{received:,} coins", inline=True)

            if profit_loss >= 0:
                embed.add_field(name="Profit", value=f"+{profit_loss:,} coins", inline=True)
            else:
                embed.add_field(name="Loss", value=f"{profit_loss:,} coins", inline=True)

            new_balance = get_balance(interaction.guild.id, interaction.user.id)
            embed.add_field(name="New Balance", value=f"{new_balance:,} coins", inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
        else:
            embed = discord.Embed(
                title="Sale Failed",
                description=message,
                color=discord.Color.red()
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="portfolio", description="View your investment portfolio")
    async def portfolio(self, interaction: discord.Interaction):
        """View your investment portfolio"""

        logger.info(f"Portfolio viewed by {interaction.user}")

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        portfolio = get_portfolio(interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="Your Investment Portfolio",
            color=discord.Color.blue()
        )

        if not portfolio["holdings"]:
            embed.description = "You don't own any shares yet!\n\nUse `/invest @member` to start investing!"
            embed.add_field(
                name="How it Works",
                value=(
                    "Member stock prices rise based on activity:\n"
                    "• Messages sent\n"
                    "• XP earned\n"
                    "• Voice chat time\n\n"
                    "Invest in active members to profit!"
                ),
                inline=False
            )
        else:
            embed.description = f"Total Value: **{portfolio['total_value']:,}** coins"

            # Show profit/loss
            pl = portfolio["total_profit_loss"]
            pl_pct = portfolio["profit_loss_percent"]

            if pl >= 0:
                embed.add_field(
                    name="Total Profit/Loss",
                    value=f"+{pl:,} coins (+{pl_pct:.1f}%)",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Total Profit/Loss",
                    value=f"{pl:,} coins ({pl_pct:.1f}%)",
                    inline=False
                )

            # List holdings
            for user_id, holding in list(portfolio["holdings"].items())[:10]:
                member = interaction.guild.get_member(int(user_id))
                name = member.display_name if member else f"User {user_id}"

                pl_str = f"+{holding['profit_loss']:,}" if holding['profit_loss'] >= 0 else f"{holding['profit_loss']:,}"

                embed.add_field(
                    name=f"{name}",
                    value=(
                        f"**{holding['shares']}** shares @ {holding['current_price']:,}\n"
                        f"Value: {holding['current_value']:,} | P/L: {pl_str}"
                    ),
                    inline=True
                )

            if len(portfolio["holdings"]) > 10:
                embed.add_field(
                    name="...",
                    value=f"And {len(portfolio['holdings']) - 10} more holdings",
                    inline=False
                )

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Portfolio of {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stockprice", description="Check a member's stock price and info")
    @app_commands.describe(member="The member to check (default: yourself)")
    async def stockprice(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """Check a member's stock price"""

        logger.info(f"Stock price checked by {interaction.user}")

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        if member is None:
            member = interaction.user

        if member.bot:
            await interaction.response.send_message(
                "Bots don't have stocks!",
                ephemeral=True
            )
            return

        stock_info = get_member_stock_info(interaction.guild.id, member.id)

        embed = discord.Embed(
            title=f"${member.display_name}",
            color=discord.Color.green() if stock_info["price_change"] >= 0 else discord.Color.red()
        )

        # Price info
        price = stock_info["current_price"]
        change = stock_info["price_change"]
        change_pct = stock_info["price_change_percent"]

        if change >= 0:
            change_str = f"+{change:,} (+{change_pct:.1f}%)"
        else:
            change_str = f"{change:,} ({change_pct:.1f}%)"

        embed.add_field(
            name="Current Price",
            value=f"**{price:,}** coins",
            inline=True
        )
        embed.add_field(
            name="Change",
            value=change_str,
            inline=True
        )
        embed.add_field(
            name="Shares Outstanding",
            value=f"{stock_info['shares_outstanding']:,}",
            inline=True
        )

        # Activity today
        activity = stock_info["activity_today"]
        embed.add_field(
            name="Today's Activity",
            value=(
                f"Messages: {activity.get('messages', 0)}\n"
                f"XP Earned: {activity.get('xp_earned', 0)}\n"
                f"Voice Time: {activity.get('voice_minutes', 0)} min"
            ),
            inline=False
        )

        # Price history mini chart
        history = stock_info["price_history"]
        if history:
            prices = [h["price"] for h in history[-5:]] + [price]
            chart = " → ".join([str(p) for p in prices])
            embed.add_field(
                name="Price History",
                value=chart,
                inline=False
            )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Buy shares with /invest @{member.display_name}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stockmarket", description="View the community stock market overview")
    async def stockmarket(self, interaction: discord.Interaction):
        """View stock market overview"""

        logger.info(f"Stock market viewed by {interaction.user}")

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Community Stock Market",
            description="Invest in active members and watch your portfolio grow!",
            color=discord.Color.gold()
        )

        # Top priced stocks
        top_stocks = get_top_stocks(interaction.guild.id, 5)
        if top_stocks:
            top_text = ""
            for i, (user_id, price, shares, change_pct) in enumerate(top_stocks, 1):
                member = interaction.guild.get_member(int(user_id))
                name = member.display_name if member else f"User {user_id}"
                trend = "" if change_pct >= 0 else ""
                top_text += f"**{i}.** {name} - {price:,} coins {trend}\n"

            embed.add_field(
                name="Top Valued Stocks",
                value=top_text,
                inline=False
            )

        # Most invested in
        most_invested = get_most_invested(interaction.guild.id, 5)
        if most_invested:
            invested_text = ""
            for i, (user_id, shares) in enumerate(most_invested, 1):
                member = interaction.guild.get_member(int(user_id))
                name = member.display_name if member else f"User {user_id}"
                invested_text += f"**{i}.** {name} - {shares} shares\n"

            embed.add_field(
                name="Most Popular Stocks",
                value=invested_text,
                inline=False
            )

        # How it works
        embed.add_field(
            name="How It Works",
            value=(
                "**Stock prices rise with activity!**\n"
                "• Each message: +0.5 to price\n"
                "• Each XP earned: +0.1 to price\n"
                "• Each voice minute: +1 to price\n\n"
                f"Transaction fee: {TRANSACTION_FEE_PERCENT}%"
            ),
            inline=False
        )

        embed.add_field(
            name="Commands",
            value=(
                "`/invest @member [shares]` - Buy shares\n"
                "`/sell @member [shares]` - Sell shares\n"
                "`/portfolio` - View your holdings\n"
                "`/stockprice @member` - Check stock info"
            ),
            inline=False
        )

        embed.set_footer(text="Prices reset daily at midnight UTC with decay")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(Invest(bot))
