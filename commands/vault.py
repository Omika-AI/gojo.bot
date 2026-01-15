"""
Vault System - Shared Economy Banks for Server Communities

Let users create 'Vaults' or 'Clubs' where they can pool coins together
for collective goals and server-wide perks.

Commands:
- /vault create - Create a new vault
- /vault deposit - Deposit coins into a vault
- /vault withdraw - Withdraw coins from vault (leaders only)
- /vault info - View vault information
- /vault members - View vault members
- /vault join - Join a vault
- /vault leave - Leave a vault
- /vault list - List all vaults in the server
- /vault goal - Set a savings goal
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import json
import os
from datetime import datetime

from utils.logger import logger
from utils.economy_db import get_balance, add_coins, remove_coins

# Database paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
VAULT_FILE = os.path.join(DATA_DIR, 'vaults.json')


def load_vault_data() -> dict:
    """Load vault data"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(VAULT_FILE):
        try:
            with open(VAULT_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_vault_data(data: dict):
    """Save vault data"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(VAULT_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_guild_vaults(guild_id: int) -> dict:
    """Get all vaults for a guild"""
    data = load_vault_data()
    return data.get(str(guild_id), {})


def save_guild_vaults(guild_id: int, vaults: dict):
    """Save vaults for a guild"""
    data = load_vault_data()
    data[str(guild_id)] = vaults
    save_vault_data(data)


def get_vault(guild_id: int, vault_name: str) -> Optional[dict]:
    """Get a specific vault"""
    vaults = get_guild_vaults(guild_id)
    return vaults.get(vault_name.lower())


def get_user_vault(guild_id: int, user_id: int) -> Optional[str]:
    """Get the vault a user belongs to"""
    vaults = get_guild_vaults(guild_id)
    for name, vault in vaults.items():
        if user_id in vault.get("members", []) or vault.get("leader") == user_id:
            return name
    return None


class Vault(commands.Cog):
    """Shared economy vault system"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    vault_group = app_commands.Group(
        name="vault",
        description="Manage shared economy vaults"
    )

    @vault_group.command(name="create", description="Create a new vault")
    @app_commands.describe(
        name="Name for your vault (no spaces)",
        description="Description of your vault's purpose",
        public="Whether anyone can join (or invite-only)"
    )
    async def vault_create(
        self,
        interaction: discord.Interaction,
        name: str,
        description: str = "A shared vault",
        public: bool = True
    ):
        """Create a new vault"""
        # Validate name
        name = name.lower().replace(" ", "-")
        if len(name) > 20:
            await interaction.response.send_message(
                "Vault name must be 20 characters or less!",
                ephemeral=True
            )
            return

        # Check if user is already in a vault
        current_vault = get_user_vault(interaction.guild.id, interaction.user.id)
        if current_vault:
            await interaction.response.send_message(
                f"You're already in the **{current_vault}** vault! Leave first with `/vault leave`.",
                ephemeral=True
            )
            return

        vaults = get_guild_vaults(interaction.guild.id)

        # Check if vault exists
        if name in vaults:
            await interaction.response.send_message(
                f"A vault named **{name}** already exists!",
                ephemeral=True
            )
            return

        # Check vault limit (max 10 per server)
        if len(vaults) >= 10:
            await interaction.response.send_message(
                "This server has reached the maximum of 10 vaults!",
                ephemeral=True
            )
            return

        # Create vault
        vaults[name] = {
            "leader": interaction.user.id,
            "description": description,
            "public": public,
            "balance": 0,
            "goal": 0,
            "goal_name": None,
            "members": [],
            "total_deposited": 0,
            "contributions": {},
            "created_at": datetime.utcnow().isoformat()
        }

        save_guild_vaults(interaction.guild.id, vaults)

        embed = discord.Embed(
            title="🏦 Vault Created!",
            description=f"**{name}** is now open for business!",
            color=discord.Color.green()
        )
        embed.add_field(name="Leader", value=interaction.user.mention, inline=True)
        embed.add_field(name="Type", value="Public" if public else "Invite-only", inline=True)
        embed.add_field(name="Description", value=description, inline=False)
        embed.set_footer(text="Members can join with /vault join")

        await interaction.response.send_message(embed=embed)
        logger.info(f"Vault '{name}' created by {interaction.user} in {interaction.guild.name}")

    @vault_group.command(name="deposit", description="Deposit coins into your vault")
    @app_commands.describe(amount="Amount of coins to deposit")
    async def vault_deposit(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 1000000]
    ):
        """Deposit coins into vault"""
        vault_name = get_user_vault(interaction.guild.id, interaction.user.id)
        if not vault_name:
            await interaction.response.send_message(
                "You're not in a vault! Join one with `/vault join` or create with `/vault create`.",
                ephemeral=True
            )
            return

        # Check user balance (using guild-aware economy system)
        balance = get_balance(interaction.guild.id, interaction.user.id)
        if balance < amount:
            await interaction.response.send_message(
                f"You only have **{balance:,}** coins! You can't deposit {amount:,}.",
                ephemeral=True
            )
            return

        vaults = get_guild_vaults(interaction.guild.id)
        vault = vaults[vault_name]

        # Transfer coins (remove from user, add to vault)
        remove_coins(interaction.guild.id, interaction.user.id, amount, "vault_deposit")
        vault["balance"] += amount
        vault["total_deposited"] += amount

        # Track contribution
        user_key = str(interaction.user.id)
        if user_key not in vault["contributions"]:
            vault["contributions"][user_key] = 0
        vault["contributions"][user_key] += amount

        save_guild_vaults(interaction.guild.id, vaults)

        embed = discord.Embed(
            title="💰 Deposit Successful!",
            description=f"You deposited **{amount:,}** coins into **{vault_name}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Vault Balance", value=f"{vault['balance']:,} coins", inline=True)
        embed.add_field(name="Your Total Contribution", value=f"{vault['contributions'][user_key]:,} coins", inline=True)

        # Check goal progress
        if vault.get("goal") and vault["goal"] > 0:
            progress = (vault["balance"] / vault["goal"]) * 100
            goal_bar = "█" * int(progress // 10) + "░" * (10 - int(progress // 10))
            goal_name = vault.get("goal_name", "Goal")
            embed.add_field(
                name=f"🎯 {goal_name}",
                value=f"`{goal_bar}` {progress:.1f}%\n{vault['balance']:,} / {vault['goal']:,}",
                inline=False
            )

            if vault["balance"] >= vault["goal"]:
                embed.add_field(
                    name="🎉 GOAL REACHED!",
                    value="Congratulations! The vault has reached its goal!",
                    inline=False
                )

        await interaction.response.send_message(embed=embed)

    @vault_group.command(name="withdraw", description="Withdraw coins from the vault (Leader only)")
    @app_commands.describe(
        amount="Amount to withdraw",
        reason="Reason for withdrawal"
    )
    async def vault_withdraw(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 1000000],
        reason: str = "No reason provided"
    ):
        """Withdraw from vault (leader only)"""
        vault_name = get_user_vault(interaction.guild.id, interaction.user.id)
        if not vault_name:
            await interaction.response.send_message(
                "You're not in a vault!",
                ephemeral=True
            )
            return

        vaults = get_guild_vaults(interaction.guild.id)
        vault = vaults[vault_name]

        # Check if leader
        if vault["leader"] != interaction.user.id:
            await interaction.response.send_message(
                "Only the vault leader can withdraw coins!",
                ephemeral=True
            )
            return

        # Check vault balance
        if vault["balance"] < amount:
            await interaction.response.send_message(
                f"The vault only has **{vault['balance']:,}** coins!",
                ephemeral=True
            )
            return

        # Withdraw (remove from vault, add to user)
        vault["balance"] -= amount
        add_coins(interaction.guild.id, interaction.user.id, amount, "vault_withdrawal")
        save_guild_vaults(interaction.guild.id, vaults)

        embed = discord.Embed(
            title="💸 Withdrawal Complete",
            description=f"**{amount:,}** coins withdrawn from **{vault_name}**",
            color=discord.Color.orange()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Remaining Balance", value=f"{vault['balance']:,} coins", inline=True)
        embed.set_footer(text="All members can see this withdrawal")

        await interaction.response.send_message(embed=embed)
        logger.info(f"Vault withdrawal: {amount} from {vault_name} by {interaction.user}")

    @vault_group.command(name="info", description="View vault information")
    @app_commands.describe(name="Vault name (leave empty for your vault)")
    async def vault_info(
        self,
        interaction: discord.Interaction,
        name: Optional[str] = None
    ):
        """View vault info"""
        if name:
            vault_name = name.lower()
        else:
            vault_name = get_user_vault(interaction.guild.id, interaction.user.id)
            if not vault_name:
                await interaction.response.send_message(
                    "You're not in a vault! Specify a vault name or join one.",
                    ephemeral=True
                )
                return

        vault = get_vault(interaction.guild.id, vault_name)
        if not vault:
            await interaction.response.send_message(
                f"Vault **{vault_name}** not found!",
                ephemeral=True
            )
            return

        # Get leader info
        leader = interaction.guild.get_member(vault["leader"])
        leader_name = leader.display_name if leader else "Unknown"

        embed = discord.Embed(
            title=f"🏦 {vault_name.title()} Vault",
            description=vault.get("description", "A shared vault"),
            color=discord.Color.gold()
        )

        embed.add_field(name="👑 Leader", value=leader_name, inline=True)
        embed.add_field(name="👥 Members", value=str(len(vault.get("members", [])) + 1), inline=True)
        embed.add_field(name="🔓 Type", value="Public" if vault.get("public") else "Invite-only", inline=True)

        embed.add_field(name="💰 Balance", value=f"{vault['balance']:,} coins", inline=True)
        embed.add_field(name="📊 Total Deposited", value=f"{vault.get('total_deposited', 0):,} coins", inline=True)

        # Goal progress
        if vault.get("goal") and vault["goal"] > 0:
            progress = (vault["balance"] / vault["goal"]) * 100
            goal_bar = "█" * int(progress // 10) + "░" * (10 - int(progress // 10))
            goal_name = vault.get("goal_name", "Savings Goal")
            embed.add_field(
                name=f"🎯 {goal_name}",
                value=f"`{goal_bar}` {progress:.1f}%\n{vault['balance']:,} / {vault['goal']:,} coins",
                inline=False
            )

        # Top contributors
        contributions = vault.get("contributions", {})
        if contributions:
            sorted_contribs = sorted(contributions.items(), key=lambda x: x[1], reverse=True)[:3]
            top_text = []
            medals = ["🥇", "🥈", "🥉"]
            for i, (uid, amount) in enumerate(sorted_contribs):
                member = interaction.guild.get_member(int(uid))
                name = member.display_name if member else "Unknown"
                top_text.append(f"{medals[i]} **{name}**: {amount:,}")

            embed.add_field(
                name="🏆 Top Contributors",
                value="\n".join(top_text),
                inline=False
            )

        # Created date
        if vault.get("created_at"):
            created = datetime.fromisoformat(vault["created_at"])
            embed.set_footer(text=f"Created {created.strftime('%B %d, %Y')}")

        await interaction.response.send_message(embed=embed)

    @vault_group.command(name="join", description="Join a public vault")
    @app_commands.describe(name="Name of the vault to join")
    async def vault_join(
        self,
        interaction: discord.Interaction,
        name: str
    ):
        """Join a vault"""
        # Check if already in a vault
        current = get_user_vault(interaction.guild.id, interaction.user.id)
        if current:
            await interaction.response.send_message(
                f"You're already in **{current}**! Leave first with `/vault leave`.",
                ephemeral=True
            )
            return

        vault_name = name.lower()
        vaults = get_guild_vaults(interaction.guild.id)
        vault = vaults.get(vault_name)

        if not vault:
            await interaction.response.send_message(
                f"Vault **{vault_name}** not found!",
                ephemeral=True
            )
            return

        if not vault.get("public"):
            await interaction.response.send_message(
                "This vault is invite-only!",
                ephemeral=True
            )
            return

        # Add member
        if "members" not in vault:
            vault["members"] = []
        vault["members"].append(interaction.user.id)
        save_guild_vaults(interaction.guild.id, vaults)

        embed = discord.Embed(
            title="🎉 Welcome to the Vault!",
            description=f"You've joined **{vault_name}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Current Balance", value=f"{vault['balance']:,} coins", inline=True)
        embed.add_field(name="Members", value=str(len(vault["members"]) + 1), inline=True)
        embed.set_footer(text="Use /vault deposit to contribute!")

        await interaction.response.send_message(embed=embed)

    @vault_group.command(name="leave", description="Leave your current vault")
    async def vault_leave(self, interaction: discord.Interaction):
        """Leave vault"""
        vault_name = get_user_vault(interaction.guild.id, interaction.user.id)
        if not vault_name:
            await interaction.response.send_message(
                "You're not in a vault!",
                ephemeral=True
            )
            return

        vaults = get_guild_vaults(interaction.guild.id)
        vault = vaults[vault_name]

        # Check if leader
        if vault["leader"] == interaction.user.id:
            # If there are other members, transfer leadership
            if vault.get("members") and len(vault["members"]) > 0:
                new_leader = vault["members"][0]
                vault["leader"] = new_leader
                vault["members"].remove(new_leader)
                new_leader_member = interaction.guild.get_member(new_leader)
                new_leader_name = new_leader_member.display_name if new_leader_member else "Unknown"

                save_guild_vaults(interaction.guild.id, vaults)

                await interaction.response.send_message(
                    f"You've left **{vault_name}**. Leadership transferred to **{new_leader_name}**.",
                    ephemeral=True
                )
            else:
                # Delete the vault if no members
                del vaults[vault_name]
                save_guild_vaults(interaction.guild.id, vaults)

                await interaction.response.send_message(
                    f"You've left and **{vault_name}** has been dissolved (no remaining members).",
                    ephemeral=True
                )
        else:
            vault["members"].remove(interaction.user.id)
            save_guild_vaults(interaction.guild.id, vaults)

            await interaction.response.send_message(
                f"You've left **{vault_name}**.",
                ephemeral=True
            )

    @vault_group.command(name="list", description="List all vaults in this server")
    async def vault_list(self, interaction: discord.Interaction):
        """List all vaults"""
        vaults = get_guild_vaults(interaction.guild.id)

        if not vaults:
            await interaction.response.send_message(
                "No vaults exist in this server yet! Create one with `/vault create`.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🏦 {interaction.guild.name} Vaults",
            description=f"**{len(vaults)}** vault(s) available",
            color=discord.Color.blue()
        )

        for name, vault in sorted(vaults.items(), key=lambda x: x[1]["balance"], reverse=True):
            leader = interaction.guild.get_member(vault["leader"])
            leader_name = leader.display_name if leader else "Unknown"
            member_count = len(vault.get("members", [])) + 1
            status = "🔓" if vault.get("public") else "🔒"

            embed.add_field(
                name=f"{status} {name.title()}",
                value=(
                    f"💰 **{vault['balance']:,}** coins\n"
                    f"👥 {member_count} members | 👑 {leader_name}"
                ),
                inline=True
            )

        embed.set_footer(text="Use /vault join <name> to join a public vault")
        await interaction.response.send_message(embed=embed)

    @vault_group.command(name="goal", description="Set a savings goal for your vault")
    @app_commands.describe(
        amount="Target amount to save",
        name="Name for the goal (e.g., 'Server Nitro')"
    )
    async def vault_goal(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 100, 10000000],
        name: str = "Savings Goal"
    ):
        """Set vault goal"""
        vault_name = get_user_vault(interaction.guild.id, interaction.user.id)
        if not vault_name:
            await interaction.response.send_message(
                "You're not in a vault!",
                ephemeral=True
            )
            return

        vaults = get_guild_vaults(interaction.guild.id)
        vault = vaults[vault_name]

        # Check if leader
        if vault["leader"] != interaction.user.id:
            await interaction.response.send_message(
                "Only the vault leader can set goals!",
                ephemeral=True
            )
            return

        vault["goal"] = amount
        vault["goal_name"] = name
        save_guild_vaults(interaction.guild.id, vaults)

        progress = (vault["balance"] / amount) * 100
        goal_bar = "█" * int(progress // 10) + "░" * (10 - int(progress // 10))

        embed = discord.Embed(
            title="🎯 Goal Set!",
            description=f"**{vault_name}** is now saving for: **{name}**",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Progress",
            value=f"`{goal_bar}` {progress:.1f}%\n{vault['balance']:,} / {amount:,} coins",
            inline=False
        )
        embed.set_footer(text="All members can contribute!")

        await interaction.response.send_message(embed=embed)

    @vault_group.command(name="members", description="View vault members and their contributions")
    async def vault_members(self, interaction: discord.Interaction):
        """View vault members"""
        vault_name = get_user_vault(interaction.guild.id, interaction.user.id)
        if not vault_name:
            await interaction.response.send_message(
                "You're not in a vault!",
                ephemeral=True
            )
            return

        vault = get_vault(interaction.guild.id, vault_name)

        embed = discord.Embed(
            title=f"👥 {vault_name.title()} Members",
            color=discord.Color.blue()
        )

        # Leader
        leader = interaction.guild.get_member(vault["leader"])
        leader_contrib = vault.get("contributions", {}).get(str(vault["leader"]), 0)
        leader_text = f"👑 **{leader.display_name if leader else 'Unknown'}** (Leader)\n"
        leader_text += f"   Contributed: {leader_contrib:,} coins"

        embed.add_field(name="Leader", value=leader_text, inline=False)

        # Members
        if vault.get("members"):
            member_text = []
            for uid in vault["members"]:
                member = interaction.guild.get_member(uid)
                name = member.display_name if member else "Unknown"
                contrib = vault.get("contributions", {}).get(str(uid), 0)
                member_text.append(f"• **{name}** - {contrib:,} coins")

            embed.add_field(
                name=f"Members ({len(vault['members'])})",
                value="\n".join(member_text[:10]),  # Limit to 10
                inline=False
            )
        else:
            embed.add_field(name="Members", value="No other members yet!", inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Add the Vault cog to the bot"""
    await bot.add_cog(Vault(bot))
