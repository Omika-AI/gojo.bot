"""
Shop Command - Server shop for spending coins

Users can spend their gambling winnings on:
- XP Boosters (double XP for a time period)
- Custom colored roles (temporary)
- Fun items

Commands:
- /shop - Browse the shop
- /buy - Purchase an item
- /inventory - View your active items
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
from typing import Optional
from datetime import datetime

from utils.shop_db import (
    get_shop_items,
    get_item,
    get_items_by_category,
    purchase_item,
    get_user_purchases,
    get_user_total_spent,
    has_active_xp_boost,
    get_active_item,
    store_custom_role,
    SHOP_ITEMS
)
from utils.economy_db import get_balance, remove_coins
from utils.logger import logger


class ColorModal(Modal, title="Custom Role Setup"):
    """Modal for entering custom role details"""

    role_name = TextInput(
        label="Role Name",
        placeholder="Enter your custom role name...",
        max_length=50,
        required=True
    )

    role_color = TextInput(
        label="Color (Hex Code)",
        placeholder="e.g., #FF5733 or FF5733",
        max_length=7,
        required=True
    )

    def __init__(self, bot, guild_id: int, user_id: int, item_id: str, price: int, duration_hours: int):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.item_id = item_id
        self.price = price
        self.duration_hours = duration_hours

    async def on_submit(self, interaction: discord.Interaction):
        # Parse color
        color_str = self.role_color.value.strip().lstrip('#')
        try:
            color_int = int(color_str, 16)
            if color_int > 0xFFFFFF:
                raise ValueError("Color too large")
            color = discord.Color(color_int)
        except ValueError:
            await interaction.response.send_message(
                "Invalid color! Please use a hex code like `#FF5733` or `FF5733`",
                ephemeral=True
            )
            return

        # Check balance again
        balance = get_balance(self.guild_id, self.user_id)
        if balance < self.price:
            await interaction.response.send_message(
                f"You don't have enough coins! You need **{self.price:,}** but only have **{balance:,}**",
                ephemeral=True
            )
            return

        # Remove coins
        success, new_balance = remove_coins(self.guild_id, self.user_id, self.price)
        if not success:
            await interaction.response.send_message(
                "Failed to process payment. Please try again.",
                ephemeral=True
            )
            return

        try:
            # Create the role
            guild = interaction.guild
            role_name = self.role_name.value.strip()

            # Create role with the custom color
            new_role = await guild.create_role(
                name=role_name,
                color=color,
                reason=f"Custom role purchased by {interaction.user}"
            )

            # Position the role (above @everyone but below mod roles)
            # Try to position it reasonably
            try:
                bot_role = guild.me.top_role
                position = max(1, bot_role.position - 1)
                await new_role.edit(position=position)
            except:
                pass  # Position edit failed, role stays at bottom

            # Assign role to user
            member = guild.get_member(self.user_id)
            if member:
                await member.add_roles(new_role)

            # Record the purchase
            from datetime import timedelta
            expires_at = (datetime.now() + timedelta(hours=self.duration_hours)).isoformat()

            purchase_item(
                self.guild_id,
                self.user_id,
                self.item_id,
                metadata={
                    "role_id": new_role.id,
                    "role_name": role_name,
                    "color": str(color)
                }
            )

            # Store role for expiration tracking
            store_custom_role(self.guild_id, self.user_id, new_role.id, expires_at)

            # Calculate duration display
            days = self.duration_hours // 24
            duration_text = f"{days} day{'s' if days != 1 else ''}" if days > 0 else f"{self.duration_hours} hours"

            embed = discord.Embed(
                title="✅ Custom Role Created!",
                description=f"Your role {new_role.mention} has been created!",
                color=color
            )
            embed.add_field(name="Role Name", value=role_name, inline=True)
            embed.add_field(name="Duration", value=duration_text, inline=True)
            embed.add_field(name="Cost", value=f"{self.price:,} coins", inline=True)
            embed.add_field(name="New Balance", value=f"{new_balance:,} coins", inline=True)
            embed.set_footer(text="Role will be automatically removed when it expires")

            await interaction.response.send_message(embed=embed)
            logger.info(f"[SHOP] {interaction.user} purchased custom role '{role_name}' for {self.price} coins")

        except discord.Forbidden:
            # Refund the coins
            from utils.economy_db import add_coins
            add_coins(self.guild_id, self.user_id, self.price, source="shop_refund")
            await interaction.response.send_message(
                "I don't have permission to create roles. Please contact an admin.",
                ephemeral=True
            )
        except Exception as e:
            # Refund the coins
            from utils.economy_db import add_coins
            add_coins(self.guild_id, self.user_id, self.price, source="shop_refund")
            logger.error(f"Error creating custom role: {e}")
            await interaction.response.send_message(
                "An error occurred while creating your role. Your coins have been refunded.",
                ephemeral=True
            )


class Shop(commands.Cog):
    """Shop commands for spending coins"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def format_price(self, price: int) -> str:
        """Format price with commas"""
        return f"{price:,}"

    def format_duration(self, hours: int) -> str:
        """Format duration in human-readable form"""
        if hours >= 24:
            days = hours // 24
            return f"{days} day{'s' if days != 1 else ''}"
        return f"{hours} hour{'s' if hours != 1 else ''}"

    @app_commands.command(name="shop", description="Browse the server shop")
    async def shop(self, interaction: discord.Interaction):
        """Display the shop"""

        logger.info(f"Shop viewed by {interaction.user} in {interaction.guild.name}")

        # Get user's balance
        balance = get_balance(interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="🛒 Server Shop",
            description=f"Your Balance: **{balance:,}** coins\n\nSpend your hard-earned coins on awesome items!",
            color=discord.Color.gold()
        )

        # XP Boosters
        boosters = get_items_by_category("boosters")
        if boosters:
            booster_text = ""
            for item in boosters:
                can_afford = "✅" if balance >= item.price else "❌"
                booster_text += f"{can_afford} **{item.name}** - {self.format_price(item.price)} coins\n"
                booster_text += f"   {item.description}\n\n"
            embed.add_field(
                name="⚡ XP Boosters",
                value=booster_text,
                inline=False
            )

        # Custom Roles
        roles = get_items_by_category("roles")
        if roles:
            roles_text = ""
            for item in roles:
                can_afford = "✅" if balance >= item.price else "❌"
                roles_text += f"{can_afford} **{item.name}** - {self.format_price(item.price)} coins\n"
                roles_text += f"   {item.description}\n\n"
            embed.add_field(
                name="🎨 Custom Roles",
                value=roles_text,
                inline=False
            )

        # Fun Items
        fun_items = get_items_by_category("fun")
        if fun_items:
            fun_text = ""
            for item in fun_items:
                can_afford = "✅" if balance >= item.price else "❌"
                fun_text += f"{can_afford} **{item.name}** - {self.format_price(item.price)} coins\n"
                fun_text += f"   {item.description}\n\n"
            embed.add_field(
                name="🎉 Fun Items",
                value=fun_text,
                inline=False
            )

        embed.add_field(
            name="How to Buy",
            value="Use `/buy <item>` to purchase an item!\nExample: `/buy xp_boost_2h`",
            inline=False
        )

        embed.set_footer(text="Earn more coins with /claimdaily, gambling, and leveling up!")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Purchase an item from the shop")
    @app_commands.describe(item="The item to purchase")
    @app_commands.choices(item=[
        app_commands.Choice(name="XP Booster (2 Hours) - 2,500 coins", value="xp_boost_2h"),
        app_commands.Choice(name="XP Booster (6 Hours) - 6,000 coins", value="xp_boost_6h"),
        app_commands.Choice(name="XP Booster (24 Hours) - 20,000 coins", value="xp_boost_24h"),
        app_commands.Choice(name="Custom Role (1 Week) - 10,000 coins", value="custom_role_1w"),
        app_commands.Choice(name="Custom Role (1 Month) - 35,000 coins", value="custom_role_1m"),
    ])
    async def buy(self, interaction: discord.Interaction, item: str):
        """Purchase an item"""

        logger.info(f"Buy command used by {interaction.user} for {item} in {interaction.guild.name}")

        # Get the item
        shop_item = get_item(item)
        if not shop_item:
            await interaction.response.send_message(
                "Item not found! Use `/shop` to see available items.",
                ephemeral=True
            )
            return

        # Check balance
        balance = get_balance(interaction.guild.id, interaction.user.id)
        if balance < shop_item.price:
            await interaction.response.send_message(
                f"You don't have enough coins!\n"
                f"**{shop_item.name}** costs **{shop_item.price:,}** coins\n"
                f"Your balance: **{balance:,}** coins\n"
                f"You need **{shop_item.price - balance:,}** more coins!",
                ephemeral=True
            )
            return

        # Handle different item types
        if shop_item.category == "boosters":
            # Check if already has active boost
            has_boost, _ = has_active_xp_boost(interaction.guild.id, interaction.user.id)
            if has_boost:
                await interaction.response.send_message(
                    "You already have an active XP booster! Wait for it to expire before buying another.",
                    ephemeral=True
                )
                return

            # Process purchase
            success, new_balance = remove_coins(interaction.guild.id, interaction.user.id, shop_item.price)
            if not success:
                await interaction.response.send_message(
                    "Failed to process payment. Please try again.",
                    ephemeral=True
                )
                return

            # Record purchase
            purchase_item(interaction.guild.id, interaction.user.id, item)

            embed = discord.Embed(
                title="✅ Purchase Complete!",
                description=f"You bought **{shop_item.name}**!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Effect",
                value="🚀 **Double XP** for all messages and voice activity!",
                inline=False
            )
            embed.add_field(
                name="Duration",
                value=self.format_duration(shop_item.duration_hours),
                inline=True
            )
            embed.add_field(
                name="Cost",
                value=f"{shop_item.price:,} coins",
                inline=True
            )
            embed.add_field(
                name="New Balance",
                value=f"{new_balance:,} coins",
                inline=True
            )
            embed.set_footer(text="Your boost is now active!")

            await interaction.response.send_message(embed=embed)
            logger.info(f"[SHOP] {interaction.user} purchased {item} for {shop_item.price} coins")

        elif shop_item.category == "roles":
            # Check if already has active custom role
            active_role = get_active_item(interaction.guild.id, interaction.user.id, item)
            if active_role:
                await interaction.response.send_message(
                    "You already have an active custom role! Wait for it to expire or it will be replaced.",
                    ephemeral=True
                )
                return

            # Show modal for role customization
            modal = ColorModal(
                self.bot,
                interaction.guild.id,
                interaction.user.id,
                item,
                shop_item.price,
                shop_item.duration_hours
            )
            await interaction.response.send_modal(modal)

        else:
            # Generic purchase for other items
            success, new_balance = remove_coins(interaction.guild.id, interaction.user.id, shop_item.price)
            if not success:
                await interaction.response.send_message(
                    "Failed to process payment. Please try again.",
                    ephemeral=True
                )
                return

            purchase_item(interaction.guild.id, interaction.user.id, item)

            embed = discord.Embed(
                title="✅ Purchase Complete!",
                description=f"You bought **{shop_item.name}**!",
                color=discord.Color.green()
            )
            embed.add_field(name="Cost", value=f"{shop_item.price:,} coins", inline=True)
            embed.add_field(name="New Balance", value=f"{new_balance:,} coins", inline=True)

            await interaction.response.send_message(embed=embed)
            logger.info(f"[SHOP] {interaction.user} purchased {item} for {shop_item.price} coins")

    @app_commands.command(name="inventory", description="View your active shop items")
    async def inventory(self, interaction: discord.Interaction):
        """View active purchases"""

        logger.info(f"Inventory viewed by {interaction.user} in {interaction.guild.name}")

        active_items = get_user_purchases(interaction.guild.id, interaction.user.id, active_only=True)
        total_spent = get_user_total_spent(interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="🎒 Your Inventory",
            description=f"Total coins spent in shop: **{total_spent:,}**",
            color=discord.Color.blue()
        )

        if active_items:
            for purchase in active_items:
                item = get_item(purchase["item_id"])
                if not item:
                    continue

                # Calculate time remaining
                if purchase["expires_at"]:
                    expires = datetime.fromisoformat(purchase["expires_at"])
                    remaining = expires - datetime.now()
                    if remaining.total_seconds() > 0:
                        hours = int(remaining.total_seconds() // 3600)
                        minutes = int((remaining.total_seconds() % 3600) // 60)
                        if hours > 0:
                            time_left = f"{hours}h {minutes}m remaining"
                        else:
                            time_left = f"{minutes}m remaining"
                    else:
                        time_left = "Expired"
                else:
                    time_left = "Permanent"

                # Get metadata for custom roles
                if purchase.get("metadata", {}).get("role_name"):
                    role_info = f"\nRole: {purchase['metadata']['role_name']}"
                else:
                    role_info = ""

                embed.add_field(
                    name=f"✨ {item.name}",
                    value=f"⏱️ {time_left}{role_info}",
                    inline=False
                )
        else:
            embed.add_field(
                name="No Active Items",
                value="You don't have any active items.\nVisit `/shop` to browse!",
                inline=False
            )

        # Show XP boost status
        has_boost, multiplier = has_active_xp_boost(interaction.guild.id, interaction.user.id)
        if has_boost:
            embed.add_field(
                name="🚀 Active Boost",
                value=f"XP Multiplier: **{multiplier}x**",
                inline=False
            )

        embed.set_footer(text="Items expire automatically after their duration")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(Shop(bot))
