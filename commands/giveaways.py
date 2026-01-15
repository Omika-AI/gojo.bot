"""
Giveaways & Polls System - Interactive timed events

Commands:
- /giveaway start - Start a new giveaway
- /giveaway end - End a giveaway early
- /giveaway reroll - Reroll giveaway winners
- /giveaway list - List active giveaways
- /giveaway delete - Delete a giveaway

- /poll create - Create a new poll
- /poll end - End a poll early
- /poll results - View poll results
- /poll delete - Delete a poll
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Button
from typing import Optional, Literal
from datetime import datetime, timedelta
import re

from utils.giveaways_db import (
    create_giveaway,
    enter_giveaway,
    leave_giveaway,
    end_giveaway,
    reroll_giveaway,
    get_giveaway,
    get_active_giveaways,
    delete_giveaway,
    create_poll,
    vote_poll,
    end_poll,
    get_poll,
    get_active_polls,
    delete_poll
)
from utils.logger import logger


# ============================================
# VIEW COMPONENTS - GIVEAWAY
# ============================================

class GiveawayButton(Button):
    """Button to enter a giveaway"""

    def __init__(self, entry_count: int = 0):
        super().__init__(
            style=discord.ButtonStyle.green,
            label=f"Enter ({entry_count})",
            emoji="🎉",
            custom_id="giveaway_enter"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle button click"""
        giveaway = get_giveaway(interaction.guild.id, interaction.message.id)

        if not giveaway:
            await interaction.response.send_message(
                "This giveaway no longer exists!",
                ephemeral=True
            )
            return

        if giveaway["ended"]:
            await interaction.response.send_message(
                "This giveaway has ended!",
                ephemeral=True
            )
            return

        # Check required role
        if giveaway.get("required_role_id"):
            role = interaction.guild.get_role(giveaway["required_role_id"])
            if role and role not in interaction.user.roles:
                await interaction.response.send_message(
                    f"You need the {role.name} role to enter this giveaway!",
                    ephemeral=True
                )
                return

        # Check if already entered
        if interaction.user.id in giveaway["entries"]:
            # Leave the giveaway
            success, message = leave_giveaway(
                interaction.guild.id,
                interaction.message.id,
                interaction.user.id
            )
            emoji = "👋"
        else:
            # Enter the giveaway
            success, message = enter_giveaway(
                interaction.guild.id,
                interaction.message.id,
                interaction.user.id
            )
            emoji = "🎉"

        # Update button count
        updated = get_giveaway(interaction.guild.id, interaction.message.id)
        if updated:
            view = GiveawayView(len(updated["entries"]))
            embed = interaction.message.embeds[0] if interaction.message.embeds else None
            if embed:
                # Update entries field
                for i, field in enumerate(embed.fields):
                    if field.name == "Entries":
                        embed.set_field_at(i, name="Entries", value=str(len(updated["entries"])), inline=True)
                        break

            await interaction.message.edit(embed=embed, view=view)

        await interaction.response.send_message(f"{emoji} {message}", ephemeral=True)


class GiveawayView(View):
    """View for giveaway messages"""

    def __init__(self, entry_count: int = 0):
        super().__init__(timeout=None)
        self.add_item(GiveawayButton(entry_count))


# ============================================
# VIEW COMPONENTS - POLL
# ============================================

class PollButton(Button):
    """Button to vote in a poll"""

    def __init__(self, option_index: int, label: str, emoji: str, vote_count: int):
        self.option_index = option_index
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=f"{label} ({vote_count})",
            emoji=emoji if emoji else None,
            custom_id=f"poll_vote_{option_index}"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle vote"""
        poll = get_poll(interaction.guild.id, interaction.message.id)

        if not poll:
            await interaction.response.send_message(
                "This poll no longer exists!",
                ephemeral=True
            )
            return

        if poll["ended"]:
            await interaction.response.send_message(
                "This poll has ended!",
                ephemeral=True
            )
            return

        # Cast vote
        success, message = vote_poll(
            interaction.guild.id,
            interaction.message.id,
            interaction.user.id,
            self.option_index
        )

        if success:
            # Update the view
            updated_poll = get_poll(interaction.guild.id, interaction.message.id)
            if updated_poll:
                view = PollView(updated_poll)

                # Update embed
                embed = interaction.message.embeds[0] if interaction.message.embeds else None
                if embed:
                    embed = create_poll_embed(updated_poll)

                await interaction.message.edit(embed=embed, view=view)

        await interaction.response.send_message(f"📊 {message}", ephemeral=True)


class PollView(View):
    """View for poll messages"""

    def __init__(self, poll: dict):
        super().__init__(timeout=None)

        for i, option in enumerate(poll["options"][:25]):
            self.add_item(PollButton(
                option_index=i,
                label=option["label"],
                emoji=option.get("emoji", ""),
                vote_count=len(option["votes"])
            ))


def create_poll_embed(poll: dict) -> discord.Embed:
    """Create an embed showing poll results"""
    total_votes = sum(len(opt["votes"]) for opt in poll["options"])

    embed = discord.Embed(
        title="📊 " + poll["question"],
        color=discord.Color.blue()
    )

    results = []
    for opt in poll["options"]:
        votes = len(opt["votes"])
        percentage = (votes / total_votes * 100) if total_votes > 0 else 0

        # Create progress bar
        bar_length = 10
        filled = int(bar_length * percentage / 100)
        bar = "▓" * filled + "░" * (bar_length - filled)

        emoji = opt.get("emoji", "")
        results.append(f"{emoji} **{opt['label']}**\n{bar} {percentage:.1f}% ({votes})")

    embed.description = "\n\n".join(results)
    embed.set_footer(text=f"Total votes: {total_votes}")

    if poll.get("ends_at"):
        embed.add_field(
            name="Ends",
            value=f"<t:{int(datetime.fromisoformat(poll['ends_at']).timestamp())}:R>",
            inline=True
        )

    return embed


# ============================================
# COG
# ============================================

class Giveaways(commands.Cog):
    """Giveaways and polls system"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_endings.start()

    def cog_unload(self):
        self.check_endings.cancel()

    async def cog_load(self):
        """Register persistent views"""
        for guild in self.bot.guilds:
            # Restore giveaway views
            for giveaway in get_active_giveaways(guild.id):
                view = GiveawayView(len(giveaway["entries"]))
                self.bot.add_view(view, message_id=giveaway["message_id"])

            # Restore poll views
            for poll in get_active_polls(guild.id):
                view = PollView(poll)
                self.bot.add_view(view, message_id=poll["message_id"])

    @tasks.loop(seconds=30)
    async def check_endings(self):
        """Check for giveaways/polls that need to end"""
        now = datetime.utcnow()

        for guild in self.bot.guilds:
            # Check giveaways
            for giveaway in get_active_giveaways(guild.id):
                ends_at = datetime.fromisoformat(giveaway["ends_at"])
                if now >= ends_at:
                    await self.auto_end_giveaway(guild, giveaway)

            # Check polls
            for poll in get_active_polls(guild.id):
                if poll.get("ends_at"):
                    ends_at = datetime.fromisoformat(poll["ends_at"])
                    if now >= ends_at:
                        await self.auto_end_poll(guild, poll)

    @check_endings.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    async def auto_end_giveaway(self, guild: discord.Guild, giveaway: dict):
        """Automatically end a giveaway"""
        success, winners, message = end_giveaway(guild.id, giveaway["message_id"])

        if not success:
            return

        try:
            channel = guild.get_channel(giveaway["channel_id"])
            if not channel:
                return

            msg = await channel.fetch_message(giveaway["message_id"])

            # Update embed
            embed = discord.Embed(
                title="🎉 Giveaway Ended!",
                description=f"**Prize:** {giveaway['prize']}",
                color=discord.Color.orange()
            )

            if winners:
                winner_mentions = [f"<@{w}>" for w in winners]
                embed.add_field(
                    name="Winners",
                    value="\n".join(winner_mentions),
                    inline=False
                )

                # Send winner announcement
                await channel.send(
                    f"🎊 Congratulations {', '.join(winner_mentions)}! "
                    f"You won **{giveaway['prize']}**!",
                    reference=msg
                )
            else:
                embed.add_field(name="Winners", value="No entries!", inline=False)

            embed.add_field(name="Entries", value=str(len(giveaway["entries"])), inline=True)

            # Disable button
            view = View()
            view.add_item(Button(
                style=discord.ButtonStyle.secondary,
                label=f"Ended ({len(giveaway['entries'])} entries)",
                emoji="🎉",
                disabled=True
            ))

            await msg.edit(embed=embed, view=view)
            logger.info(f"Giveaway ended in {guild.name}: {giveaway['prize']}")

        except Exception as e:
            logger.error(f"Error ending giveaway: {e}")

    async def auto_end_poll(self, guild: discord.Guild, poll: dict):
        """Automatically end a poll"""
        success, updated_poll, message = end_poll(guild.id, poll["message_id"])

        if not success:
            return

        try:
            channel = guild.get_channel(poll["channel_id"])
            if not channel:
                return

            msg = await channel.fetch_message(poll["message_id"])

            # Create final results embed
            embed = create_poll_embed(updated_poll)
            embed.title = "📊 Poll Ended: " + poll["question"]
            embed.color = discord.Color.orange()

            # Find winner
            max_votes = 0
            winners = []
            for opt in updated_poll["options"]:
                votes = len(opt["votes"])
                if votes > max_votes:
                    max_votes = votes
                    winners = [opt["label"]]
                elif votes == max_votes and votes > 0:
                    winners.append(opt["label"])

            if winners:
                embed.add_field(
                    name="Winner(s)",
                    value=", ".join(winners),
                    inline=False
                )

            # Disable buttons
            view = View()
            for opt in poll["options"][:25]:
                view.add_item(Button(
                    style=discord.ButtonStyle.secondary,
                    label=f"{opt['label']} ({len(opt['votes'])})",
                    emoji=opt.get("emoji") if opt.get("emoji") else None,
                    disabled=True
                ))

            await msg.edit(embed=embed, view=view)
            logger.info(f"Poll ended in {guild.name}: {poll['question']}")

        except Exception as e:
            logger.error(f"Error ending poll: {e}")

    # ============================================
    # GIVEAWAY COMMANDS
    # ============================================

    giveaway_group = app_commands.Group(
        name="giveaway",
        description="Create and manage giveaways"
    )

    @giveaway_group.command(name="start", description="Start a new giveaway")
    @app_commands.describe(
        prize="What you're giving away",
        duration="Duration (e.g., 1h, 30m, 1d, 1w)",
        winners="Number of winners (default: 1)",
        required_role="Role required to enter (optional)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway_start(
        self,
        interaction: discord.Interaction,
        prize: str,
        duration: str,
        winners: Optional[int] = 1,
        required_role: Optional[discord.Role] = None
    ):
        """Start a new giveaway"""
        # Parse duration
        duration_match = re.match(r"(\d+)([mhdw])", duration.lower())
        if not duration_match:
            await interaction.response.send_message(
                "Invalid duration! Use format like: 1h, 30m, 1d, 1w",
                ephemeral=True
            )
            return

        amount = int(duration_match.group(1))
        unit = duration_match.group(2)

        if unit == "m":
            delta = timedelta(minutes=amount)
        elif unit == "h":
            delta = timedelta(hours=amount)
        elif unit == "d":
            delta = timedelta(days=amount)
        elif unit == "w":
            delta = timedelta(weeks=amount)
        else:
            delta = timedelta(hours=1)

        ends_at = datetime.utcnow() + delta

        # Create embed
        embed = discord.Embed(
            title="🎉 GIVEAWAY!",
            description=f"**Prize:** {prize}",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Ends",
            value=f"<t:{int(ends_at.timestamp())}:R>",
            inline=True
        )
        embed.add_field(name="Winners", value=str(winners), inline=True)
        embed.add_field(name="Entries", value="0", inline=True)

        if required_role:
            embed.add_field(
                name="Required Role",
                value=required_role.mention,
                inline=False
            )

        embed.set_footer(text=f"Hosted by {interaction.user.display_name}")

        # Send message
        await interaction.response.defer()
        view = GiveawayView(0)
        msg = await interaction.channel.send(embed=embed, view=view)

        # Save to database
        success, giveaway_id, message = create_giveaway(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=msg.id,
            prize=prize,
            winners_count=winners,
            host_id=interaction.user.id,
            ends_at=ends_at.isoformat(),
            required_role_id=required_role.id if required_role else None
        )

        self.bot.add_view(view, message_id=msg.id)

        await interaction.followup.send(
            f"Giveaway started! ID: `{giveaway_id}`",
            ephemeral=True
        )
        logger.info(f"Giveaway started in {interaction.guild.name}: {prize}")

    @giveaway_group.command(name="end", description="End a giveaway early")
    @app_commands.describe(message_id="The message ID of the giveaway")
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway_end(self, interaction: discord.Interaction, message_id: str):
        """End a giveaway early"""
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
            return

        giveaway = get_giveaway(interaction.guild.id, msg_id)
        if not giveaway:
            await interaction.response.send_message("Giveaway not found!", ephemeral=True)
            return

        await interaction.response.defer()
        await self.auto_end_giveaway(interaction.guild, giveaway)
        await interaction.followup.send("Giveaway ended!", ephemeral=True)

    @giveaway_group.command(name="reroll", description="Reroll giveaway winners")
    @app_commands.describe(
        message_id="The message ID of the giveaway",
        count="Number of new winners to pick (default: 1)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway_reroll(
        self,
        interaction: discord.Interaction,
        message_id: str,
        count: Optional[int] = 1
    ):
        """Reroll winners"""
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
            return

        success, new_winners, message = reroll_giveaway(interaction.guild.id, msg_id, count)

        if success:
            giveaway = get_giveaway(interaction.guild.id, msg_id)
            winner_mentions = [f"<@{w}>" for w in new_winners]

            # Announce new winners
            try:
                channel = interaction.guild.get_channel(giveaway["channel_id"])
                await channel.send(
                    f"🎲 Reroll! New winner(s): {', '.join(winner_mentions)}\n"
                    f"Prize: **{giveaway['prize']}**"
                )
            except:
                pass

            await interaction.response.send_message(
                f"Rerolled! New winners: {', '.join(winner_mentions)}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @giveaway_group.command(name="list", description="List active giveaways")
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway_list(self, interaction: discord.Interaction):
        """List active giveaways"""
        giveaways = get_active_giveaways(interaction.guild.id)

        if not giveaways:
            await interaction.response.send_message(
                "No active giveaways!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Active Giveaways",
            color=discord.Color.green()
        )

        for g in giveaways[:10]:
            ends_at = datetime.fromisoformat(g["ends_at"])
            embed.add_field(
                name=g["prize"],
                value=(
                    f"Entries: {len(g['entries'])} | Winners: {g['winners_count']}\n"
                    f"Ends: <t:{int(ends_at.timestamp())}:R>\n"
                    f"Message ID: `{g['message_id']}`"
                ),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @giveaway_group.command(name="delete", description="Delete a giveaway")
    @app_commands.describe(message_id="The message ID of the giveaway")
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway_delete(self, interaction: discord.Interaction, message_id: str):
        """Delete a giveaway"""
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
            return

        giveaway = get_giveaway(interaction.guild.id, msg_id)
        success, message = delete_giveaway(interaction.guild.id, msg_id)

        if success:
            # Try to delete the message
            try:
                channel = interaction.guild.get_channel(giveaway["channel_id"])
                msg = await channel.fetch_message(msg_id)
                await msg.delete()
            except:
                pass

            await interaction.response.send_message("Giveaway deleted!", ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    # ============================================
    # POLL COMMANDS
    # ============================================

    poll_group = app_commands.Group(
        name="poll",
        description="Create and manage polls"
    )

    @poll_group.command(name="create", description="Create a new poll")
    @app_commands.describe(
        question="The poll question",
        options="Options separated by | (e.g., Yes | No | Maybe)",
        duration="Optional duration (e.g., 1h, 30m, 1d)",
        multiple="Allow multiple votes"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def poll_create(
        self,
        interaction: discord.Interaction,
        question: str,
        options: str,
        duration: Optional[str] = None,
        multiple: Optional[bool] = False
    ):
        """Create a new poll"""
        # Parse options
        option_list = [opt.strip() for opt in options.split("|")]

        if len(option_list) < 2:
            await interaction.response.send_message(
                "You need at least 2 options! Separate them with |",
                ephemeral=True
            )
            return

        if len(option_list) > 25:
            await interaction.response.send_message(
                "Maximum 25 options allowed!",
                ephemeral=True
            )
            return

        # Parse duration if provided
        ends_at = None
        if duration:
            duration_match = re.match(r"(\d+)([mhdw])", duration.lower())
            if duration_match:
                amount = int(duration_match.group(1))
                unit = duration_match.group(2)

                if unit == "m":
                    delta = timedelta(minutes=amount)
                elif unit == "h":
                    delta = timedelta(hours=amount)
                elif unit == "d":
                    delta = timedelta(days=amount)
                elif unit == "w":
                    delta = timedelta(weeks=amount)
                else:
                    delta = timedelta(hours=1)

                ends_at = (datetime.utcnow() + delta).isoformat()

        # Build poll options
        poll_options = []
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i, opt in enumerate(option_list):
            poll_options.append({
                "label": opt,
                "emoji": emojis[i] if i < len(emojis) else "",
                "votes": []
            })

        # Create temporary poll data for embed
        temp_poll = {
            "question": question,
            "options": poll_options,
            "ends_at": ends_at,
            "ended": False
        }

        # Create embed and view
        embed = create_poll_embed(temp_poll)
        embed.set_footer(text=f"Created by {interaction.user.display_name} | Multiple votes: {'Yes' if multiple else 'No'}")

        await interaction.response.defer()
        view = PollView(temp_poll)
        msg = await interaction.channel.send(embed=embed, view=view)

        # Save to database
        success, poll_id, message = create_poll(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=msg.id,
            question=question,
            options=poll_options,
            host_id=interaction.user.id,
            ends_at=ends_at,
            multiple_votes=multiple
        )

        self.bot.add_view(view, message_id=msg.id)

        await interaction.followup.send(
            f"Poll created! ID: `{poll_id}`",
            ephemeral=True
        )
        logger.info(f"Poll created in {interaction.guild.name}: {question}")

    @poll_group.command(name="end", description="End a poll early")
    @app_commands.describe(message_id="The message ID of the poll")
    @app_commands.default_permissions(manage_messages=True)
    async def poll_end(self, interaction: discord.Interaction, message_id: str):
        """End a poll early"""
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
            return

        poll = get_poll(interaction.guild.id, msg_id)
        if not poll:
            await interaction.response.send_message("Poll not found!", ephemeral=True)
            return

        await interaction.response.defer()
        await self.auto_end_poll(interaction.guild, poll)
        await interaction.followup.send("Poll ended!", ephemeral=True)

    @poll_group.command(name="results", description="View poll results")
    @app_commands.describe(message_id="The message ID of the poll")
    async def poll_results(self, interaction: discord.Interaction, message_id: str):
        """View poll results"""
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
            return

        poll = get_poll(interaction.guild.id, msg_id)
        if not poll:
            await interaction.response.send_message("Poll not found!", ephemeral=True)
            return

        embed = create_poll_embed(poll)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @poll_group.command(name="delete", description="Delete a poll")
    @app_commands.describe(message_id="The message ID of the poll")
    @app_commands.default_permissions(manage_messages=True)
    async def poll_delete(self, interaction: discord.Interaction, message_id: str):
        """Delete a poll"""
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
            return

        poll = get_poll(interaction.guild.id, msg_id)
        success, message = delete_poll(interaction.guild.id, msg_id)

        if success:
            try:
                channel = interaction.guild.get_channel(poll["channel_id"])
                msg = await channel.fetch_message(msg_id)
                await msg.delete()
            except:
                pass

            await interaction.response.send_message("Poll deleted!", ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    """Add the Giveaways cog to the bot"""
    await bot.add_cog(Giveaways(bot))
