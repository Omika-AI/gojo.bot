"""
Anti-Scam Protection - Suspicious Link Shield

Protects the server from scam links, phishing attempts, and malicious URLs.
Gojo checks every link posted and takes action on suspicious ones.

Commands:
- /antiscam enable - Enable anti-scam protection
- /antiscam disable - Disable anti-scam protection
- /antiscam settings - View current settings
- /antiscam whitelist - Add/remove whitelisted domains
- /antiscam logs - View recent blocked links
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal
import json
import os
import re
from datetime import datetime
from urllib.parse import urlparse

from utils.logger import logger

# Database path
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
ANTISCAM_FILE = os.path.join(DATA_DIR, 'antiscam.json')

# Known scam domain patterns and keywords
SCAM_PATTERNS = [
    # Discord scam patterns
    r'disc[o0]rd[\-\.]?(?:gift|nitro|app|free)',
    r'dicsord',
    r'discorcl',
    r'discord[\-\.]?(?:giveaway|free)',
    r'steamc[o0]mmunity',
    r'steampowerd',
    r'steam[\-\.]?(?:gift|wallet|free)',
    # Crypto scams
    r'(?:free|claim)[\-\.]?(?:bitcoin|btc|eth|crypto)',
    r'(?:bitcoin|crypto)[\-\.]?(?:giveaway|double)',
    # General phishing patterns
    r'(?:verify|confirm)[\-\.]?(?:account|login)',
    r'(?:account|login)[\-\.]?(?:verify|suspended)',
    r'secure[\-\.]?(?:update|verify)',
    # Gift card scams
    r'(?:free|claim)[\-\.]?(?:gift[\-\.]?card|amazon|visa)',
    # NFT scams
    r'(?:free|claim)[\-\.]?(?:nft|mint|airdrop)',
]

# Known malicious TLDs
SUSPICIOUS_TLDS = ['.xyz', '.tk', '.ml', '.ga', '.cf', '.gq', '.top', '.work', '.click', '.link']

# Common safe domains that should never be flagged
SAFE_DOMAINS = [
    'discord.com', 'discord.gg', 'discordapp.com',
    'youtube.com', 'youtu.be', 'twitch.tv',
    'twitter.com', 'x.com', 'instagram.com', 'facebook.com',
    'github.com', 'gitlab.com', 'reddit.com',
    'google.com', 'docs.google.com', 'drive.google.com',
    'spotify.com', 'soundcloud.com',
    'steam.com', 'steampowered.com', 'steamcommunity.com',
    'amazon.com', 'ebay.com',
    'wikipedia.org', 'wikimedia.org',
    'imgur.com', 'giphy.com', 'tenor.com'
]


def load_antiscam_data() -> dict:
    """Load anti-scam configuration"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(ANTISCAM_FILE):
        try:
            with open(ANTISCAM_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_antiscam_data(data: dict):
    """Save anti-scam configuration"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ANTISCAM_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_guild_config(guild_id: int) -> dict:
    """Get anti-scam config for a guild"""
    data = load_antiscam_data()
    if str(guild_id) not in data:
        data[str(guild_id)] = {
            "enabled": False,
            "action": "delete",  # delete, warn, or log
            "log_channel": None,
            "whitelist": [],
            "blocked_count": 0,
            "recent_blocks": []
        }
        save_antiscam_data(data)
    return data[str(guild_id)]


def save_guild_config(guild_id: int, config: dict):
    """Save anti-scam config for a guild"""
    data = load_antiscam_data()
    data[str(guild_id)] = config
    save_antiscam_data(data)


def extract_urls(text: str) -> list:
    """Extract all URLs from text"""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(url_pattern, text, re.IGNORECASE)


def is_suspicious_url(url: str, whitelist: list) -> tuple[bool, str]:
    """Check if a URL is suspicious. Returns (is_suspicious, reason)"""
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc

        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]

        # Check whitelist
        for safe in whitelist:
            if domain == safe or domain.endswith('.' + safe):
                return False, ""

        # Check safe domains
        for safe in SAFE_DOMAINS:
            if domain == safe or domain.endswith('.' + safe):
                return False, ""

        # Check for scam patterns in the full URL
        full_url = url.lower()
        for pattern in SCAM_PATTERNS:
            if re.search(pattern, full_url):
                return True, f"Matches scam pattern"

        # Check for suspicious TLDs
        for tld in SUSPICIOUS_TLDS:
            if domain.endswith(tld):
                return True, f"Suspicious TLD ({tld})"

        # Check for IP address URLs (often phishing)
        ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        if re.match(ip_pattern, domain):
            return True, "IP address URL"

        # Check for lookalike domains (typosquatting)
        lookalikes = [
            ('discord', ['discrod', 'dlscord', 'disc0rd', 'dizcord', 'discorb']),
            ('steam', ['stearn', 'stearn', 'stean', 'steaim', 'stearn']),
            ('twitter', ['tvvitter', 'twltter', 'twiter']),
            ('paypal', ['paypai', 'paypa1', 'peypal']),
        ]

        for legit, fakes in lookalikes:
            for fake in fakes:
                if fake in domain:
                    return True, f"Lookalike domain (impersonating {legit})"

        # Check for excessive subdomains (common in phishing)
        subdomain_count = domain.count('.')
        if subdomain_count > 3:
            return True, "Excessive subdomains"

        return False, ""

    except Exception:
        return False, ""


class AntiScam(commands.Cog):
    """Anti-scam and phishing protection"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    antiscam_group = app_commands.Group(
        name="antiscam",
        description="Configure anti-scam protection"
    )

    @antiscam_group.command(name="enable", description="Enable anti-scam protection")
    @app_commands.describe(
        action="What to do with suspicious links",
        log_channel="Channel to log blocked links (optional)"
    )
    @app_commands.default_permissions(administrator=True)
    async def antiscam_enable(
        self,
        interaction: discord.Interaction,
        action: Literal["delete", "warn", "log"] = "delete",
        log_channel: Optional[discord.TextChannel] = None
    ):
        """Enable anti-scam"""
        config = get_guild_config(interaction.guild.id)
        config["enabled"] = True
        config["action"] = action
        if log_channel:
            config["log_channel"] = log_channel.id
        save_guild_config(interaction.guild.id, config)

        embed = discord.Embed(
            title="🛡️ Anti-Scam Protection Enabled",
            description="Gojo will now protect this server from suspicious links!",
            color=discord.Color.green()
        )

        action_descriptions = {
            "delete": "Delete the message and warn the user",
            "warn": "Keep the message but warn about the link",
            "log": "Only log the incident (no action)"
        }

        embed.add_field(name="Action", value=action_descriptions[action], inline=False)

        if log_channel:
            embed.add_field(name="Log Channel", value=log_channel.mention, inline=True)

        embed.add_field(
            name="What's Protected",
            value=(
                "• Discord/Steam phishing links\n"
                "• Crypto scam domains\n"
                "• Lookalike/typosquatting domains\n"
                "• IP address links\n"
                "• Known malicious TLDs"
            ),
            inline=False
        )

        embed.set_footer(text="Use /antiscam whitelist to add trusted domains")
        await interaction.response.send_message(embed=embed)
        logger.info(f"Anti-scam enabled in {interaction.guild.name}")

    @antiscam_group.command(name="disable", description="Disable anti-scam protection")
    @app_commands.default_permissions(administrator=True)
    async def antiscam_disable(self, interaction: discord.Interaction):
        """Disable anti-scam"""
        config = get_guild_config(interaction.guild.id)
        config["enabled"] = False
        save_guild_config(interaction.guild.id, config)

        await interaction.response.send_message(
            "🛡️ Anti-scam protection has been disabled.",
            ephemeral=True
        )

    @antiscam_group.command(name="settings", description="View current anti-scam settings")
    @app_commands.default_permissions(administrator=True)
    async def antiscam_settings(self, interaction: discord.Interaction):
        """View settings"""
        config = get_guild_config(interaction.guild.id)

        embed = discord.Embed(
            title="🛡️ Anti-Scam Settings",
            color=discord.Color.blue()
        )

        status = "✅ Enabled" if config["enabled"] else "❌ Disabled"
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Action", value=config.get("action", "delete").title(), inline=True)

        log_channel = None
        if config.get("log_channel"):
            log_channel = self.bot.get_channel(config["log_channel"])
        embed.add_field(
            name="Log Channel",
            value=log_channel.mention if log_channel else "Not set",
            inline=True
        )

        embed.add_field(
            name="Blocked Links",
            value=f"**{config.get('blocked_count', 0):,}** links blocked",
            inline=True
        )

        whitelist = config.get("whitelist", [])
        if whitelist:
            embed.add_field(
                name=f"Whitelisted Domains ({len(whitelist)})",
                value=", ".join(whitelist[:10]) + ("..." if len(whitelist) > 10 else ""),
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @antiscam_group.command(name="whitelist", description="Add or remove whitelisted domains")
    @app_commands.describe(
        action="Add or remove a domain",
        domain="The domain to whitelist (e.g., example.com)"
    )
    @app_commands.default_permissions(administrator=True)
    async def antiscam_whitelist(
        self,
        interaction: discord.Interaction,
        action: Literal["add", "remove", "list"],
        domain: Optional[str] = None
    ):
        """Manage whitelist"""
        config = get_guild_config(interaction.guild.id)

        if "whitelist" not in config:
            config["whitelist"] = []

        if action == "list":
            whitelist = config.get("whitelist", [])
            if not whitelist:
                await interaction.response.send_message(
                    "No domains in whitelist.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🔓 Whitelisted Domains",
                description="\n".join(f"• {d}" for d in whitelist),
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return

        if not domain:
            await interaction.response.send_message(
                "Please provide a domain!",
                ephemeral=True
            )
            return

        # Clean domain
        domain = domain.lower().strip()
        if domain.startswith('http'):
            domain = urlparse(domain).netloc
        if domain.startswith('www.'):
            domain = domain[4:]

        if action == "add":
            if domain in config["whitelist"]:
                await interaction.response.send_message(
                    f"`{domain}` is already whitelisted!",
                    ephemeral=True
                )
                return

            config["whitelist"].append(domain)
            save_guild_config(interaction.guild.id, config)
            await interaction.response.send_message(
                f"✅ Added `{domain}` to whitelist.",
                ephemeral=True
            )

        elif action == "remove":
            if domain not in config["whitelist"]:
                await interaction.response.send_message(
                    f"`{domain}` is not in the whitelist!",
                    ephemeral=True
                )
                return

            config["whitelist"].remove(domain)
            save_guild_config(interaction.guild.id, config)
            await interaction.response.send_message(
                f"✅ Removed `{domain}` from whitelist.",
                ephemeral=True
            )

    @antiscam_group.command(name="logs", description="View recently blocked links")
    @app_commands.default_permissions(administrator=True)
    async def antiscam_logs(self, interaction: discord.Interaction):
        """View blocked link logs"""
        config = get_guild_config(interaction.guild.id)
        recent = config.get("recent_blocks", [])

        if not recent:
            await interaction.response.send_message(
                "No blocked links recorded yet.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🚨 Recently Blocked Links",
            description=f"Last {min(10, len(recent))} blocked links",
            color=discord.Color.red()
        )

        for block in recent[-10:]:
            user_id = block.get("user_id", "Unknown")
            user = interaction.guild.get_member(user_id)
            user_name = user.display_name if user else f"User {user_id}"

            timestamp = block.get("timestamp", "Unknown")
            if timestamp != "Unknown":
                try:
                    dt = datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime("%b %d, %H:%M")
                except:
                    pass

            embed.add_field(
                name=f"{user_name} ({timestamp})",
                value=f"**Reason:** {block.get('reason', 'Unknown')}\n`{block.get('url', 'N/A')[:50]}...`",
                inline=False
            )

        embed.set_footer(text=f"Total blocked: {config.get('blocked_count', 0)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Check messages for suspicious links"""
        # Ignore DMs and bots
        if not message.guild or message.author.bot:
            return

        # Check if anti-scam is enabled
        config = get_guild_config(message.guild.id)
        if not config.get("enabled"):
            return

        # Admins and mods bypass
        if message.author.guild_permissions.administrator or message.author.guild_permissions.manage_messages:
            return

        # Extract URLs
        urls = extract_urls(message.content)
        if not urls:
            return

        whitelist = config.get("whitelist", [])

        for url in urls:
            is_sus, reason = is_suspicious_url(url, whitelist)
            if is_sus:
                # Log the block
                if "recent_blocks" not in config:
                    config["recent_blocks"] = []

                config["recent_blocks"].append({
                    "user_id": message.author.id,
                    "url": url[:100],
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat()
                })

                # Keep only last 100 blocks
                config["recent_blocks"] = config["recent_blocks"][-100:]
                config["blocked_count"] = config.get("blocked_count", 0) + 1
                save_guild_config(message.guild.id, config)

                action = config.get("action", "delete")

                if action == "delete":
                    try:
                        await message.delete()

                        # Warn user
                        warn_embed = discord.Embed(
                            title="🛡️ Suspicious Link Blocked",
                            description=f"{message.author.mention}, your message was removed because it contained a suspicious link.",
                            color=discord.Color.red()
                        )
                        warn_embed.add_field(name="Reason", value=reason, inline=False)
                        warn_embed.set_footer(text="If this was a mistake, contact a moderator.")

                        try:
                            await message.channel.send(embed=warn_embed, delete_after=15)
                        except:
                            pass

                    except discord.Forbidden:
                        logger.warning(f"Missing permissions to delete message in {message.guild.name}")

                elif action == "warn":
                    warn_embed = discord.Embed(
                        title="⚠️ Suspicious Link Detected",
                        description=f"{message.author.mention}, your message contains a potentially dangerous link.",
                        color=discord.Color.orange()
                    )
                    warn_embed.add_field(name="Reason", value=reason, inline=False)
                    try:
                        await message.reply(embed=warn_embed, delete_after=30)
                    except:
                        pass

                # Log to channel
                if config.get("log_channel"):
                    log_channel = self.bot.get_channel(config["log_channel"])
                    if log_channel:
                        log_embed = discord.Embed(
                            title="🚨 Suspicious Link Blocked",
                            color=discord.Color.red(),
                            timestamp=datetime.utcnow()
                        )
                        log_embed.add_field(name="User", value=f"{message.author.mention} ({message.author})", inline=True)
                        log_embed.add_field(name="Channel", value=message.channel.mention, inline=True)
                        log_embed.add_field(name="Reason", value=reason, inline=True)
                        log_embed.add_field(name="URL", value=f"||{url[:100]}...||", inline=False)
                        log_embed.add_field(name="Action", value=action.title(), inline=True)

                        try:
                            await log_channel.send(embed=log_embed)
                        except:
                            pass

                logger.info(f"Blocked suspicious link from {message.author} in {message.guild.name}: {reason}")
                break  # Only handle one suspicious link per message


async def setup(bot: commands.Bot):
    """Add the AntiScam cog to the bot"""
    await bot.add_cog(AntiScam(bot))
