"""
Server Milestones - Track server history and achievements

Commands:
- /milestones - View server milestones and records
- /milestones leaderboard - View record holders
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime

from utils.logger import logger

# Database path
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
MILESTONES_FILE = os.path.join(DATA_DIR, 'milestones.json')


def load_milestones() -> dict:
    """Load milestones data"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(MILESTONES_FILE):
        try:
            with open(MILESTONES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_milestones(data: dict):
    """Save milestones data"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MILESTONES_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_guild_milestones(guild_id: int) -> dict:
    """Get milestones for a guild"""
    data = load_milestones()
    if str(guild_id) not in data:
        data[str(guild_id)] = {
            "records": {},
            "firsts": {},
            "stats": {
                "total_messages": 0,
                "total_songs_played": 0,
                "total_coins_gambled": 0,
                "total_giveaways": 0,
                "total_tickets": 0
            }
        }
        save_milestones(data)
    return data[str(guild_id)]


def save_guild_milestones(guild_id: int, milestones: dict):
    """Save milestones for a guild"""
    data = load_milestones()
    data[str(guild_id)] = milestones
    save_milestones(data)


def update_record(guild_id: int, record_type: str, user_id: int, username: str, value: int, details: str = None):
    """Update a server record if the new value beats the old one"""
    milestones = get_guild_milestones(guild_id)

    current = milestones.get("records", {}).get(record_type, {}).get("value", 0)

    if value > current:
        milestones["records"][record_type] = {
            "user_id": user_id,
            "username": username,
            "value": value,
            "details": details,
            "date": datetime.utcnow().isoformat()
        }
        save_guild_milestones(guild_id, milestones)
        return True
    return False


def record_first(guild_id: int, first_type: str, user_id: int, username: str):
    """Record a server first (only if not already recorded)"""
    milestones = get_guild_milestones(guild_id)

    if first_type not in milestones.get("firsts", {}):
        if "firsts" not in milestones:
            milestones["firsts"] = {}
        milestones["firsts"][first_type] = {
            "user_id": user_id,
            "username": username,
            "date": datetime.utcnow().isoformat()
        }
        save_guild_milestones(guild_id, milestones)
        return True
    return False


def increment_stat(guild_id: int, stat: str, amount: int = 1):
    """Increment a server statistic"""
    milestones = get_guild_milestones(guild_id)
    if "stats" not in milestones:
        milestones["stats"] = {}
    milestones["stats"][stat] = milestones["stats"].get(stat, 0) + amount
    save_guild_milestones(guild_id, milestones)


class Milestones(commands.Cog):
    """Server milestones and history tracking"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="milestones", description="View server milestones and records")
    async def milestones(self, interaction: discord.Interaction):
        """Display server milestones"""
        milestones = get_guild_milestones(interaction.guild.id)

        embed = discord.Embed(
            title=f"🏆 {interaction.guild.name} Milestones",
            description="Server records and historical firsts",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        # Server Firsts
        firsts = milestones.get("firsts", {})
        if firsts:
            firsts_text = []
            first_labels = {
                "level_100": "🎯 First to Level 100",
                "level_50": "📈 First to Level 50",
                "millionaire": "💎 First Millionaire (1M coins)",
                "all_achievements": "🏅 First to Complete All Achievements",
                "1000_messages": "💬 First 1,000 Messages",
                "100_voice_hours": "🎤 First 100 Voice Hours"
            }

            for first_type, data in firsts.items():
                label = first_labels.get(first_type, first_type.replace("_", " ").title())
                date = datetime.fromisoformat(data["date"]).strftime("%b %d, %Y")
                firsts_text.append(f"{label}\n└ **{data['username']}** ({date})")

            embed.add_field(
                name="🥇 Server Firsts",
                value="\n".join(firsts_text[:5]) if firsts_text else "No firsts recorded yet!",
                inline=False
            )
        else:
            embed.add_field(
                name="🥇 Server Firsts",
                value="No firsts recorded yet! Be the first to reach a milestone!",
                inline=False
            )

        # Server Records
        records = milestones.get("records", {})
        if records:
            records_text = []
            record_labels = {
                "biggest_blackjack_win": "🃏 Biggest Blackjack Win",
                "biggest_roulette_win": "🎰 Biggest Roulette Win",
                "highest_level": "📊 Highest Level",
                "most_coins": "💰 Most Coins (Peak)",
                "longest_streak": "🔥 Longest Daily Streak",
                "most_rep": "⭐ Most Reputation Points"
            }

            for record_type, data in records.items():
                label = record_labels.get(record_type, record_type.replace("_", " ").title())
                records_text.append(
                    f"{label}\n└ **{data['username']}**: {data['value']:,}"
                )

            embed.add_field(
                name="🏅 Server Records",
                value="\n".join(records_text[:5]) if records_text else "No records set yet!",
                inline=False
            )
        else:
            embed.add_field(
                name="🏅 Server Records",
                value="No records set yet! Start playing to set records!",
                inline=False
            )

        # Server Statistics
        stats = milestones.get("stats", {})
        stats_text = []

        stat_labels = {
            "total_messages": ("💬", "Messages Sent"),
            "total_songs_played": ("🎵", "Songs Played"),
            "total_coins_gambled": ("🎰", "Coins Gambled"),
            "total_giveaways": ("🎉", "Giveaways Held"),
            "total_tickets": ("🎫", "Tickets Resolved")
        }

        for stat_key, (emoji, label) in stat_labels.items():
            value = stats.get(stat_key, 0)
            if value > 0:
                stats_text.append(f"{emoji} **{label}:** {value:,}")

        if stats_text:
            embed.add_field(
                name="📊 All-Time Statistics",
                value="\n".join(stats_text),
                inline=False
            )

        # Server age
        created_at = interaction.guild.created_at
        age = datetime.utcnow() - created_at.replace(tzinfo=None)
        years = age.days // 365
        months = (age.days % 365) // 30
        days = age.days % 30

        age_str = ""
        if years > 0:
            age_str += f"{years}y "
        if months > 0:
            age_str += f"{months}m "
        age_str += f"{days}d"

        embed.add_field(
            name="📅 Server Age",
            value=f"Created: {created_at.strftime('%B %d, %Y')}\nAge: **{age_str}**",
            inline=True
        )

        embed.add_field(
            name="👥 Member Count",
            value=f"**{interaction.guild.member_count:,}** members",
            inline=True
        )

        embed.set_footer(text="Milestones are tracked automatically as you use the bot!")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverhistory", description="View detailed server history timeline")
    async def server_history(self, interaction: discord.Interaction):
        """View server history"""
        milestones = get_guild_milestones(interaction.guild.id)

        # Collect all events with dates
        events = []

        for first_type, data in milestones.get("firsts", {}).items():
            events.append({
                "date": datetime.fromisoformat(data["date"]),
                "type": "first",
                "name": first_type.replace("_", " ").title(),
                "user": data["username"]
            })

        for record_type, data in milestones.get("records", {}).items():
            events.append({
                "date": datetime.fromisoformat(data["date"]),
                "type": "record",
                "name": record_type.replace("_", " ").title(),
                "user": data["username"],
                "value": data["value"]
            })

        # Sort by date
        events.sort(key=lambda x: x["date"], reverse=True)

        embed = discord.Embed(
            title=f"📜 {interaction.guild.name} History",
            description="Timeline of server achievements",
            color=discord.Color.blue()
        )

        if events:
            timeline = []
            for event in events[:10]:
                date_str = event["date"].strftime("%b %d, %Y")
                if event["type"] == "first":
                    timeline.append(f"🥇 **{date_str}** - {event['user']} achieved {event['name']}")
                else:
                    timeline.append(f"🏆 **{date_str}** - {event['user']} set {event['name']} record ({event['value']:,})")

            embed.add_field(
                name="Recent Events",
                value="\n".join(timeline),
                inline=False
            )
        else:
            embed.add_field(
                name="No History Yet",
                value="Start using the bot to create server history!",
                inline=False
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Add the Milestones cog to the bot"""
    await bot.add_cog(Milestones(bot))
