"""
Server Configuration System - Module toggling and server settings

Commands:
- /serverconfig modules - Enable/disable bot modules
- /serverconfig view - View current server configuration
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal
import json
import os

from utils.logger import logger

# Database path
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
CONFIG_FILE = os.path.join(DATA_DIR, 'server_config.json')

# Available modules that can be toggled
TOGGLEABLE_MODULES = {
    "gambling": {
        "name": "Gambling",
        "description": "Blackjack, Roulette, Coinflip, etc.",
        "emoji": "🎰",
        "default": True
    },
    "economy": {
        "name": "Economy",
        "description": "Balance, Daily claims, Leaderboard",
        "emoji": "💰",
        "default": True
    },
    "leveling": {
        "name": "Leveling",
        "description": "XP, Ranks, Level-up messages",
        "emoji": "📊",
        "default": True
    },
    "music": {
        "name": "Music",
        "description": "Play, Queue, Volume controls",
        "emoji": "🎵",
        "default": True
    },
    "games": {
        "name": "Games",
        "description": "Trivia, Connect4, TicTacToe, etc.",
        "emoji": "🎮",
        "default": True
    },
    "starboard": {
        "name": "Starboard",
        "description": "Star reactions and hall of fame",
        "emoji": "⭐",
        "default": True
    },
    "welcomes": {
        "name": "Welcome Messages",
        "description": "Welcome/Goodbye cards",
        "emoji": "👋",
        "default": True
    },
    "autothread": {
        "name": "Auto-Threading",
        "description": "Automatic thread creation",
        "emoji": "🧵",
        "default": False
    }
}


def load_config_data() -> dict:
    """Load server configurations"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_config_data(data: dict):
    """Save server configurations"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_server_config(guild_id: int) -> dict:
    """Get configuration for a server"""
    data = load_config_data()
    if str(guild_id) not in data:
        # Initialize with defaults
        data[str(guild_id)] = {
            "modules": {mod: info["default"] for mod, info in TOGGLEABLE_MODULES.items()},
            "settings": {}
        }
        save_config_data(data)
    return data[str(guild_id)]


def save_server_config(guild_id: int, config: dict):
    """Save configuration for a server"""
    data = load_config_data()
    data[str(guild_id)] = config
    save_config_data(data)


def is_module_enabled(guild_id: int, module: str) -> bool:
    """Check if a module is enabled for a server"""
    config = get_server_config(guild_id)
    return config.get("modules", {}).get(module, True)


class ServerConfig(commands.Cog):
    """Server configuration and module management"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    serverconfig_group = app_commands.Group(
        name="serverconfig",
        description="Configure server settings and modules"
    )

    @serverconfig_group.command(name="view", description="View current server configuration")
    @app_commands.default_permissions(administrator=True)
    async def config_view(self, interaction: discord.Interaction):
        """View server configuration"""
        config = get_server_config(interaction.guild.id)

        embed = discord.Embed(
            title=f"⚙️ Server Configuration",
            description=f"Settings for **{interaction.guild.name}**",
            color=discord.Color.blue()
        )

        # Module statuses
        module_status = []
        for mod_id, mod_info in TOGGLEABLE_MODULES.items():
            enabled = config.get("modules", {}).get(mod_id, mod_info["default"])
            status = "✅" if enabled else "❌"
            module_status.append(f"{status} {mod_info['emoji']} **{mod_info['name']}**")

        embed.add_field(
            name="Module Status",
            value="\n".join(module_status),
            inline=False
        )

        embed.add_field(
            name="How to Toggle",
            value="Use `/serverconfig toggle <module>` to enable/disable modules",
            inline=False
        )

        embed.set_footer(text="Only administrators can change these settings")

        await interaction.response.send_message(embed=embed)

    @serverconfig_group.command(name="toggle", description="Enable or disable a module")
    @app_commands.describe(
        module="The module to toggle",
        enabled="Enable or disable the module"
    )
    @app_commands.default_permissions(administrator=True)
    async def config_toggle(
        self,
        interaction: discord.Interaction,
        module: Literal["gambling", "economy", "leveling", "music", "games", "starboard", "welcomes", "autothread"],
        enabled: bool
    ):
        """Toggle a module"""
        config = get_server_config(interaction.guild.id)

        if "modules" not in config:
            config["modules"] = {}

        config["modules"][module] = enabled
        save_server_config(interaction.guild.id, config)

        mod_info = TOGGLEABLE_MODULES[module]
        status = "enabled" if enabled else "disabled"
        emoji = "✅" if enabled else "❌"

        embed = discord.Embed(
            title=f"{emoji} Module {status.title()}",
            description=f"**{mod_info['emoji']} {mod_info['name']}** has been {status}.",
            color=discord.Color.green() if enabled else discord.Color.red()
        )

        if not enabled:
            embed.add_field(
                name="Note",
                value=f"Commands related to {mod_info['name']} will no longer work on this server.",
                inline=False
            )

        await interaction.response.send_message(embed=embed)
        logger.info(f"Module '{module}' {status} in {interaction.guild.name}")

    @serverconfig_group.command(name="reset", description="Reset all settings to defaults")
    @app_commands.default_permissions(administrator=True)
    async def config_reset(self, interaction: discord.Interaction):
        """Reset configuration to defaults"""
        config = {
            "modules": {mod: info["default"] for mod, info in TOGGLEABLE_MODULES.items()},
            "settings": {}
        }
        save_server_config(interaction.guild.id, config)

        await interaction.response.send_message(
            "⚙️ Server configuration has been reset to defaults!",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    """Add the ServerConfig cog to the bot"""
    await bot.add_cog(ServerConfig(bot))
