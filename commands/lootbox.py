"""
Lootbox Command - Open lootboxes with quest keys for rewards

Commands:
- /lootbox - Open a lootbox using a quest key

Lootboxes contain random rewards based on rarity tiers
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
from datetime import datetime, timedelta

from utils.quests_db import get_quest_keys, use_quest_key
from utils.economy_db import add_coins
from utils.logger import logger


# ============================================
# LOOTBOX CONFIGURATION
# ============================================

# Reward tiers with their probabilities (must sum to 100)
REWARD_TIERS = {
    "common": {
        "chance": 50,  # 50% chance
        "color": discord.Color.light_grey(),
        "emoji": "",
        "name": "Common"
    },
    "uncommon": {
        "chance": 30,  # 30% chance
        "color": discord.Color.green(),
        "emoji": "",
        "name": "Uncommon"
    },
    "rare": {
        "chance": 15,  # 15% chance
        "color": discord.Color.blue(),
        "emoji": "",
        "name": "Rare"
    },
    "epic": {
        "chance": 4,  # 4% chance
        "color": discord.Color.purple(),
        "emoji": "",
        "name": "Epic"
    },
    "legendary": {
        "chance": 1,  # 1% chance
        "color": discord.Color.gold(),
        "emoji": "",
        "name": "LEGENDARY"
    }
}

# Coin rewards per tier (min, max)
COIN_REWARDS = {
    "common": (500, 1000),
    "uncommon": (1000, 2500),
    "rare": (2500, 5000),
    "epic": (5000, 15000),
    "legendary": (15000, 50000)
}

# Special role rewards (only epic and legendary can get these)
SPECIAL_ROLES = {
    "epic": [
        {"name": "VIP (1 Day)", "color": 0x9B59B6, "duration_hours": 24},
        {"name": "Lucky (1 Day)", "color": 0x2ECC71, "duration_hours": 24},
    ],
    "legendary": [
        {"name": "Jackpot Winner (3 Days)", "color": 0xF1C40F, "duration_hours": 72},
        {"name": "Elite (1 Week)", "color": 0xE74C3C, "duration_hours": 168},
        {"name": "Legendary (1 Week)", "color": 0xFF6B35, "duration_hours": 168},
    ]
}

# Chance for special role instead of just coins (for epic/legendary)
ROLE_CHANCE = {
    "epic": 30,  # 30% chance to get role instead of just coins
    "legendary": 50  # 50% chance to get role
}


def roll_reward_tier() -> str:
    """Roll for a reward tier based on probabilities"""
    roll = random.randint(1, 100)
    cumulative = 0

    for tier, data in REWARD_TIERS.items():
        cumulative += data["chance"]
        if roll <= cumulative:
            return tier

    return "common"  # Fallback


async def create_lootbox_role(guild: discord.Guild, member: discord.Member, role_data: dict) -> discord.Role:
    """Create a temporary role for the lootbox winner"""
    try:
        # Create the role
        role = await guild.create_role(
            name=role_data["name"],
            color=discord.Color(role_data["color"]),
            reason=f"Lootbox reward for {member}"
        )

        # Position the role
        try:
            bot_role = guild.me.top_role
            position = max(1, bot_role.position - 1)
            await role.edit(position=position)
        except:
            pass

        # Assign to member
        await member.add_roles(role)

        # Store for expiration tracking
        try:
            from utils.shop_db import store_custom_role
            expires_at = (datetime.now() + timedelta(hours=role_data["duration_hours"])).isoformat()
            store_custom_role(guild.id, member.id, role.id, expires_at)
        except:
            pass

        return role

    except discord.Forbidden:
        return None
    except Exception as e:
        logger.error(f"Error creating lootbox role: {e}")
        return None


class OpenLootboxButton(Button):
    """Button to confirm opening a lootbox"""

    def __init__(self):
        super().__init__(
            label="Open Lootbox",
            style=discord.ButtonStyle.success,
            emoji=""
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not view:
            return

        # Use a quest key
        success = use_quest_key(interaction.guild.id, interaction.user.id)
        if not success:
            await interaction.response.send_message(
                "You don't have any quest keys! Complete daily quests to earn keys.",
                ephemeral=True
            )
            return

        # Disable the button
        self.disabled = True
        self.label = "Opening..."
        await interaction.response.edit_message(view=view)

        # Create suspense with animated message
        message = interaction.message

        # Opening animation
        animations = [
            "Opening lootbox...",
            "Revealing rewards...",
            "Almost there...",
        ]

        for anim in animations:
            embed = discord.Embed(
                title="Lootbox Opening!",
                description=f"**{anim}**",
                color=discord.Color.gold()
            )
            await message.edit(embed=embed, view=None)
            await asyncio.sleep(1)

        # Roll the reward
        tier = roll_reward_tier()
        tier_data = REWARD_TIERS[tier]

        # Determine reward
        coins_min, coins_max = COIN_REWARDS[tier]
        coins_won = random.randint(coins_min, coins_max)

        # Check for special role
        role_won = None
        if tier in ROLE_CHANCE and random.randint(1, 100) <= ROLE_CHANCE[tier]:
            role_options = SPECIAL_ROLES.get(tier, [])
            if role_options:
                role_data = random.choice(role_options)
                role_won = await create_lootbox_role(
                    interaction.guild,
                    interaction.user,
                    role_data
                )

        # Add coins to balance
        add_coins(interaction.guild.id, interaction.user.id, coins_won, source="lootbox")

        # Build result embed
        embed = discord.Embed(
            title=f"{tier_data['emoji']} {tier_data['name']} Lootbox!",
            color=tier_data["color"]
        )

        # Add dramatic reveal based on tier
        if tier == "legendary":
            embed.description = "**JACKPOT!!!**\n\nYou've hit the legendary reward!"
        elif tier == "epic":
            embed.description = "**WOW!** You got an epic reward!"
        elif tier == "rare":
            embed.description = "Nice! You got a rare reward!"
        elif tier == "uncommon":
            embed.description = "You got an uncommon reward!"
        else:
            embed.description = "You opened the lootbox!"

        # Show rewards
        rewards_text = f"**+{coins_won:,} coins**"
        if role_won:
            duration = role_data["duration_hours"]
            if duration >= 24:
                duration_text = f"{duration // 24} day(s)"
            else:
                duration_text = f"{duration} hours"
            rewards_text += f"\n**+{role_won.mention}** ({duration_text})"

        embed.add_field(
            name="Rewards",
            value=rewards_text,
            inline=False
        )

        # Show remaining keys
        keys_left = get_quest_keys(interaction.guild.id, interaction.user.id)
        embed.set_footer(text=f"Quest keys remaining: {keys_left}")

        await message.edit(embed=embed, view=None)

        logger.info(f"[LOOTBOX] {interaction.user} opened a {tier} lootbox: {coins_won} coins" +
                    (f" + {role_data['name']}" if role_won else ""))


class LootboxView(View):
    """View for lootbox opening"""

    def __init__(self, user_id: int, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.add_item(OpenLootboxButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to use the buttons"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the person who ran the command can use these buttons!",
                ephemeral=True
            )
            return False
        return True


class Lootbox(commands.Cog):
    """Lootbox commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="lootbox", description="Open a lootbox using a quest key")
    async def lootbox(self, interaction: discord.Interaction):
        """Open a lootbox"""

        logger.info(f"Lootbox command used by {interaction.user} in {interaction.guild.name}")

        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server!",
                ephemeral=True
            )
            return

        # Check if user has keys
        keys = get_quest_keys(interaction.guild.id, interaction.user.id)

        if keys <= 0:
            embed = discord.Embed(
                title="No Quest Keys!",
                description=(
                    "You don't have any quest keys!\n\n"
                    "**How to get keys:**\n"
                    "1. Use `/quests` to view daily quests\n"
                    "2. Complete all 3 quests\n"
                    "3. Claim your quest key!\n\n"
                    "Quests reset daily at midnight UTC."
                ),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Show lootbox preview
        embed = discord.Embed(
            title="Lootbox",
            description=f"You have **{keys}** quest key(s)!\n\nClick the button below to open a lootbox!",
            color=discord.Color.gold()
        )

        # Show possible rewards
        embed.add_field(
            name="Possible Rewards",
            value=(
                f" **Common** (50%) - 500-1,000 coins\n"
                f" **Uncommon** (30%) - 1,000-2,500 coins\n"
                f" **Rare** (15%) - 2,500-5,000 coins\n"
                f" **Epic** (4%) - 5,000-15,000 coins + chance for special role!\n"
                f" **LEGENDARY** (1%) - 15,000-50,000 coins + chance for elite role!"
            ),
            inline=False
        )

        view = LootboxView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="lootboxodds", description="View lootbox reward odds")
    async def lootboxodds(self, interaction: discord.Interaction):
        """View lootbox odds"""

        logger.info(f"Lootbox odds viewed by {interaction.user}")

        embed = discord.Embed(
            title="Lootbox Odds & Rewards",
            description="Here's what you can win from lootboxes!",
            color=discord.Color.gold()
        )

        # Common
        embed.add_field(
            name=" Common (50%)",
            value="**500 - 1,000** coins",
            inline=False
        )

        # Uncommon
        embed.add_field(
            name=" Uncommon (30%)",
            value="**1,000 - 2,500** coins",
            inline=False
        )

        # Rare
        embed.add_field(
            name=" Rare (15%)",
            value="**2,500 - 5,000** coins",
            inline=False
        )

        # Epic
        embed.add_field(
            name=" Epic (4%)",
            value=(
                "**5,000 - 15,000** coins\n"
                "**30% chance** for a special role:\n"
                "- VIP (1 Day)\n"
                "- Lucky (1 Day)"
            ),
            inline=False
        )

        # Legendary
        embed.add_field(
            name=" LEGENDARY (1%)",
            value=(
                "**15,000 - 50,000** coins\n"
                "**50% chance** for an elite role:\n"
                "- Jackpot Winner (3 Days)\n"
                "- Elite (1 Week)\n"
                "- Legendary (1 Week)"
            ),
            inline=False
        )

        embed.set_footer(text="Earn quest keys by completing daily quests!")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(Lootbox(bot))
