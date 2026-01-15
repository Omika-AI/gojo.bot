"""
Vault System - Shared Economy Banks for Server Communities

Let users create 'Vaults' or 'Clubs' where they can pool coins together
for collective goals and server-wide perks.

Single command /vault opens a panel with all vault actions as buttons.
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
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


# =============================================================================
# MODALS
# =============================================================================

class CreateVaultModal(Modal, title="Create a New Vault"):
    """Modal for creating a vault"""

    vault_name = TextInput(
        label="Vault Name",
        placeholder="e.g., savings-club (no spaces, max 20 chars)",
        max_length=20,
        required=True
    )

    description = TextInput(
        label="Description",
        placeholder="What is this vault for?",
        default="A shared vault",
        max_length=100,
        required=False
    )

    public = TextInput(
        label="Public? (yes/no)",
        placeholder="yes = anyone can join, no = invite only",
        default="yes",
        max_length=3,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        name = self.vault_name.value.lower().replace(" ", "-")
        is_public = self.public.value.lower() in ["yes", "y", "true", "1"]
        desc = self.description.value or "A shared vault"

        # Check if user is already in a vault
        current_vault = get_user_vault(interaction.guild.id, interaction.user.id)
        if current_vault:
            await interaction.response.send_message(
                f"You're already in the **{current_vault}** vault! Leave first.",
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

        # Check vault limit
        if len(vaults) >= 10:
            await interaction.response.send_message(
                "This server has reached the maximum of 10 vaults!",
                ephemeral=True
            )
            return

        # Create vault
        vaults[name] = {
            "leader": interaction.user.id,
            "description": desc,
            "public": is_public,
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
        embed.add_field(name="Type", value="Public" if is_public else "Invite-only", inline=True)
        embed.add_field(name="Description", value=desc, inline=False)

        await interaction.response.send_message(embed=embed)
        logger.info(f"Vault '{name}' created by {interaction.user} in {interaction.guild.name}")


class DepositModal(Modal, title="Deposit Coins"):
    """Modal for depositing coins"""

    vault_name = TextInput(
        label="Vault Name",
        placeholder="Enter the vault name",
        required=True
    )

    amount = TextInput(
        label="Amount",
        placeholder="How many coins to deposit?",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        vault_name = self.vault_name.value.lower()

        try:
            amount = int(self.amount.value.replace(",", ""))
            if amount <= 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid positive number!",
                ephemeral=True
            )
            return

        vaults = get_guild_vaults(interaction.guild.id)

        if vault_name not in vaults:
            await interaction.response.send_message(
                f"Vault **{vault_name}** not found!",
                ephemeral=True
            )
            return

        # Check user balance
        balance = get_balance(interaction.guild.id, interaction.user.id)
        if balance < amount:
            await interaction.response.send_message(
                f"You only have **{balance:,}** coins!",
                ephemeral=True
            )
            return

        vault_data = vaults[vault_name]

        # Transfer coins
        remove_coins(interaction.guild.id, interaction.user.id, amount)
        vault_data["balance"] += amount
        vault_data["total_deposited"] += amount

        # Track contribution
        user_key = str(interaction.user.id)
        if user_key not in vault_data["contributions"]:
            vault_data["contributions"][user_key] = 0
        vault_data["contributions"][user_key] += amount

        save_guild_vaults(interaction.guild.id, vaults)

        embed = discord.Embed(
            title="💰 Deposit Successful!",
            description=f"You deposited **{amount:,}** coins into **{vault_name}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Vault Balance", value=f"{vault_data['balance']:,} coins", inline=True)
        embed.add_field(name="Your Contribution", value=f"{vault_data['contributions'][user_key]:,} coins", inline=True)

        # Goal progress
        if vault_data.get("goal") and vault_data["goal"] > 0:
            progress = (vault_data["balance"] / vault_data["goal"]) * 100
            goal_bar = "█" * int(progress // 10) + "░" * (10 - int(progress // 10))
            goal_name = vault_data.get("goal_name", "Goal")
            embed.add_field(
                name=f"🎯 {goal_name}",
                value=f"`{goal_bar}` {progress:.1f}%\n{vault_data['balance']:,} / {vault_data['goal']:,}",
                inline=False
            )

        await interaction.response.send_message(embed=embed)


class JoinVaultModal(Modal, title="Join a Vault"):
    """Modal for joining a vault"""

    vault_name = TextInput(
        label="Vault Name",
        placeholder="Enter the vault name to join",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Check if already in a vault
        current = get_user_vault(interaction.guild.id, interaction.user.id)
        if current:
            await interaction.response.send_message(
                f"You're already in **{current}**! Leave first.",
                ephemeral=True
            )
            return

        vault_name = self.vault_name.value.lower()
        vaults = get_guild_vaults(interaction.guild.id)
        vault_data = vaults.get(vault_name)

        if not vault_data:
            await interaction.response.send_message(
                f"Vault **{vault_name}** not found!",
                ephemeral=True
            )
            return

        if not vault_data.get("public"):
            await interaction.response.send_message(
                "This vault is invite-only!",
                ephemeral=True
            )
            return

        # Add member
        if "members" not in vault_data:
            vault_data["members"] = []
        vault_data["members"].append(interaction.user.id)
        save_guild_vaults(interaction.guild.id, vaults)

        embed = discord.Embed(
            title="🎉 Welcome to the Vault!",
            description=f"You've joined **{vault_name}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Balance", value=f"{vault_data['balance']:,} coins", inline=True)
        embed.add_field(name="Members", value=str(len(vault_data["members"]) + 1), inline=True)

        await interaction.response.send_message(embed=embed)


class WithdrawModal(Modal, title="Withdraw Coins"):
    """Modal for withdrawing coins (leader only)"""

    amount = TextInput(
        label="Amount",
        placeholder="How many coins to withdraw?",
        required=True
    )

    reason = TextInput(
        label="Reason",
        placeholder="Why are you withdrawing?",
        default="No reason provided",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        vault_name = get_user_vault(interaction.guild.id, interaction.user.id)
        if not vault_name:
            await interaction.response.send_message(
                "You're not in a vault!",
                ephemeral=True
            )
            return

        vaults = get_guild_vaults(interaction.guild.id)
        vault = vaults[vault_name]

        if vault["leader"] != interaction.user.id:
            await interaction.response.send_message(
                "Only the vault leader can withdraw!",
                ephemeral=True
            )
            return

        try:
            amount = int(self.amount.value.replace(",", ""))
            if amount <= 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid positive number!",
                ephemeral=True
            )
            return

        if vault["balance"] < amount:
            await interaction.response.send_message(
                f"The vault only has **{vault['balance']:,}** coins!",
                ephemeral=True
            )
            return

        # Withdraw
        vault["balance"] -= amount
        add_coins(interaction.guild.id, interaction.user.id, amount, "vault_withdrawal")
        save_guild_vaults(interaction.guild.id, vaults)

        embed = discord.Embed(
            title="💸 Withdrawal Complete",
            description=f"**{amount:,}** coins withdrawn from **{vault_name}**",
            color=discord.Color.orange()
        )
        embed.add_field(name="Reason", value=self.reason.value or "No reason provided", inline=False)
        embed.add_field(name="Remaining", value=f"{vault['balance']:,} coins", inline=True)

        await interaction.response.send_message(embed=embed)


class SetGoalModal(Modal, title="Set Savings Goal"):
    """Modal for setting a vault goal (leader only)"""

    amount = TextInput(
        label="Goal Amount",
        placeholder="Target amount to save (e.g., 10000)",
        required=True
    )

    goal_name = TextInput(
        label="Goal Name",
        placeholder="What are you saving for?",
        default="Savings Goal",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        vault_name = get_user_vault(interaction.guild.id, interaction.user.id)
        if not vault_name:
            await interaction.response.send_message(
                "You're not in a vault!",
                ephemeral=True
            )
            return

        vaults = get_guild_vaults(interaction.guild.id)
        vault = vaults[vault_name]

        if vault["leader"] != interaction.user.id:
            await interaction.response.send_message(
                "Only the vault leader can set goals!",
                ephemeral=True
            )
            return

        try:
            amount = int(self.amount.value.replace(",", ""))
            if amount < 100:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number (minimum 100)!",
                ephemeral=True
            )
            return

        vault["goal"] = amount
        vault["goal_name"] = self.goal_name.value or "Savings Goal"
        save_guild_vaults(interaction.guild.id, vaults)

        progress = (vault["balance"] / amount) * 100
        goal_bar = "█" * int(progress // 10) + "░" * (10 - int(progress // 10))

        embed = discord.Embed(
            title="🎯 Goal Set!",
            description=f"**{vault_name}** is now saving for: **{vault['goal_name']}**",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Progress",
            value=f"`{goal_bar}` {progress:.1f}%\n{vault['balance']:,} / {amount:,} coins",
            inline=False
        )

        await interaction.response.send_message(embed=embed)


# =============================================================================
# MAIN VAULT PANEL VIEW
# =============================================================================

class VaultPanelView(View):
    """Main vault panel with all actions"""

    def __init__(self, user_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.guild_id = guild_id
        self.user_vault = get_user_vault(guild_id, user_id)

        # Check if user is a vault leader
        self.is_leader = False
        if self.user_vault:
            vault = get_vault(guild_id, self.user_vault)
            if vault and vault.get("leader") == user_id:
                self.is_leader = True

        # Add leader-only buttons if applicable
        if self.is_leader:
            withdraw_btn = Button(label="Withdraw", style=discord.ButtonStyle.danger, emoji="💸", row=2)
            withdraw_btn.callback = self.withdraw_callback
            self.add_item(withdraw_btn)

            goal_btn = Button(label="Set Goal", style=discord.ButtonStyle.primary, emoji="🎯", row=2)
            goal_btn.callback = self.set_goal_callback
            self.add_item(goal_btn)

            members_btn = Button(label="Members", style=discord.ButtonStyle.secondary, emoji="👥", row=2)
            members_btn.callback = self.members_callback
            self.add_item(members_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This panel isn't for you! Use `/vault` to open your own.",
                ephemeral=True
            )
            return False
        return True

    # Leader-only callbacks
    async def withdraw_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(WithdrawModal())

    async def set_goal_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SetGoalModal())

    async def members_callback(self, interaction: discord.Interaction):
        vault_name = get_user_vault(interaction.guild.id, interaction.user.id)
        if not vault_name:
            await interaction.response.send_message("You're not in a vault!", ephemeral=True)
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
                value="\n".join(member_text[:10]),
                inline=False
            )
        else:
            embed.add_field(name="Members", value="No other members yet!", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Row 0: Main actions
    @discord.ui.button(label="Create Vault", style=discord.ButtonStyle.success, emoji="🏦", row=0)
    async def create_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CreateVaultModal())

    @discord.ui.button(label="My Vault", style=discord.ButtonStyle.primary, emoji="📊", row=0)
    async def my_vault_button(self, interaction: discord.Interaction, button: Button):
        vault_name = get_user_vault(interaction.guild.id, interaction.user.id)
        if not vault_name:
            await interaction.response.send_message(
                "You're not in a vault! Use **Create Vault** or **Join Vault** to get started.",
                ephemeral=True
            )
            return

        vault = get_vault(interaction.guild.id, vault_name)

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

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Deposit", style=discord.ButtonStyle.success, emoji="💰", row=0)
    async def deposit_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(DepositModal())

    @discord.ui.button(label="Vault List", style=discord.ButtonStyle.secondary, emoji="📋", row=0)
    async def list_button(self, interaction: discord.Interaction, button: Button):
        vaults = get_guild_vaults(interaction.guild.id)

        if not vaults:
            await interaction.response.send_message(
                "No vaults exist in this server yet! Click **Create Vault** to make one.",
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

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Row 1: Join/Leave
    @discord.ui.button(label="Join Vault", style=discord.ButtonStyle.primary, emoji="🚪", row=1)
    async def join_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(JoinVaultModal())

    @discord.ui.button(label="Leave Vault", style=discord.ButtonStyle.danger, emoji="🚶", row=1)
    async def leave_button(self, interaction: discord.Interaction, button: Button):
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


# =============================================================================
# COG
# =============================================================================

class Vault(commands.Cog):
    """Shared economy vault system"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="vault", description="Open the vault management panel")
    async def vault(self, interaction: discord.Interaction):
        """Open the vault panel with all actions"""
        user_vault = get_user_vault(interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="🏦 Vault Management",
            description="Manage shared economy vaults for your server community.",
            color=discord.Color.gold()
        )

        if user_vault:
            vault_data = get_vault(interaction.guild.id, user_vault)
            is_leader = vault_data and vault_data.get("leader") == interaction.user.id
            role = "👑 Leader" if is_leader else "👥 Member"
            embed.add_field(
                name="Your Vault",
                value=f"**{user_vault.title()}** ({role})\n💰 Balance: {vault_data['balance']:,} coins",
                inline=False
            )
            if is_leader:
                embed.add_field(
                    name="Leader Actions",
                    value="As the leader, you can Withdraw, Set Goal, and view Members.",
                    inline=False
                )
        else:
            embed.add_field(
                name="No Vault",
                value="You're not in a vault. Create one or join an existing vault!",
                inline=False
            )

        embed.set_footer(text="Click a button below to manage vaults")

        view = VaultPanelView(interaction.user.id, interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    """Add the Vault cog to the bot"""
    await bot.add_cog(Vault(bot))
