"""
Auto News Command - Automated news feeds from Reddit and RSS

Automatically posts content from Reddit subreddits or RSS feeds
to a designated community feed channel.

Commands:
- /autonews setup - Set up the news channel
- /autonews reddit - Add a subreddit to track
- /autonews rss - Add an RSS feed
- /autonews remove - Remove a feed
- /autonews list - List all feeds
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal

from utils.live_alerts_db import (
    set_news_channel,
    get_news_channel,
    add_feed,
    remove_feed,
    get_feeds
)
from utils.logger import logger


class AutoNews(commands.Cog):
    """Auto news feed commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Create command group
    news_group = app_commands.Group(
        name="autonews",
        description="Manage automated news feeds from Reddit and RSS"
    )

    @news_group.command(name="setup", description="Set up the channel for automated news posts")
    @app_commands.describe(channel="The channel to post news in")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set up the news channel"""

        logger.info(f"Auto news setup by {interaction.user} in {interaction.guild.name}")

        # Set the channel
        set_news_channel(interaction.guild.id, channel.id)

        embed = discord.Embed(
            title="📰 Auto News Setup Complete",
            description=f"Automated news will now be posted in {channel.mention}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Next Steps",
            value=(
                "1. Add a Reddit feed with `/autonews reddit`\n"
                "2. Or add an RSS feed with `/autonews rss`\n"
                "3. Gojo will check for new posts every 10 minutes"
            ),
            inline=False
        )
        embed.add_field(
            name="Popular Gaming Subreddits",
            value=(
                "• `gaming` - General gaming\n"
                "• `pcgaming` - PC gaming news\n"
                "• `Games` - Gaming discussion\n"
                "• `gamernews` - Gaming news\n"
                "• `indiegaming` - Indie games"
            ),
            inline=True
        )
        embed.add_field(
            name="Popular Meme Subreddits",
            value=(
                "• `memes` - General memes\n"
                "• `dankmemes` - Dank memes\n"
                "• `gaming_memes` - Gaming memes\n"
                "• `animemes` - Anime memes"
            ),
            inline=True
        )

        await interaction.response.send_message(embed=embed)

    @news_group.command(name="reddit", description="Add a subreddit to auto-post from")
    @app_commands.describe(
        subreddit="The subreddit name (without r/)",
        filter_type="What type of posts to fetch"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add_reddit(
        self,
        interaction: discord.Interaction,
        subreddit: str,
        filter_type: Literal["hot", "new", "top"] = "hot"
    ):
        """Add a Reddit feed"""

        logger.info(f"Adding Reddit feed r/{subreddit} in {interaction.guild.name}")

        # Check if news channel is set up
        news_channel = get_news_channel(interaction.guild.id)
        if not news_channel:
            await interaction.response.send_message(
                "Please set up a news channel first with `/autonews setup`",
                ephemeral=True
            )
            return

        # Clean up the subreddit name
        subreddit = subreddit.strip().lstrip('r/').lstrip('/')

        # Validate subreddit name (basic check)
        if not subreddit or len(subreddit) > 50 or ' ' in subreddit:
            await interaction.response.send_message(
                "Invalid subreddit name. Please enter just the subreddit name (e.g., `gaming`)",
                ephemeral=True
            )
            return

        # Add the feed
        feed_url = f"{subreddit}/{filter_type}"
        success, message = add_feed(
            interaction.guild.id,
            "reddit",
            feed_url,
            name=f"r/{subreddit}"
        )

        if success:
            embed = discord.Embed(
                title="✅ Reddit Feed Added",
                description=f"Now tracking **r/{subreddit}** ({filter_type} posts)",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Subreddit Link",
                value=f"https://reddit.com/r/{subreddit}",
                inline=False
            )
            embed.set_footer(text="New posts will be checked every 10 minutes")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)

    @news_group.command(name="rss", description="Add an RSS feed to auto-post from")
    @app_commands.describe(
        url="The RSS feed URL",
        name="A friendly name for this feed"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add_rss(
        self,
        interaction: discord.Interaction,
        url: str,
        name: Optional[str] = None
    ):
        """Add an RSS feed"""

        logger.info(f"Adding RSS feed {url} in {interaction.guild.name}")

        # Check if news channel is set up
        news_channel = get_news_channel(interaction.guild.id)
        if not news_channel:
            await interaction.response.send_message(
                "Please set up a news channel first with `/autonews setup`",
                ephemeral=True
            )
            return

        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            await interaction.response.send_message(
                "Please provide a valid URL starting with http:// or https://",
                ephemeral=True
            )
            return

        # Add the feed
        display_name = name or url.split('//')[-1].split('/')[0]  # Extract domain as name
        success, message = add_feed(
            interaction.guild.id,
            "rss",
            url,
            name=display_name
        )

        if success:
            embed = discord.Embed(
                title="✅ RSS Feed Added",
                description=f"Now tracking **{display_name}**",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Feed URL",
                value=url[:100] + "..." if len(url) > 100 else url,
                inline=False
            )
            embed.set_footer(text="New posts will be checked every 10 minutes")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)

    @news_group.command(name="remove", description="Remove a news feed")
    @app_commands.describe(
        feed_type="The type of feed to remove",
        identifier="The subreddit name or RSS URL"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_feed_cmd(
        self,
        interaction: discord.Interaction,
        feed_type: Literal["reddit", "rss"],
        identifier: str
    ):
        """Remove a feed"""

        logger.info(f"Removing {feed_type} feed {identifier} in {interaction.guild.name}")

        # Clean up identifier
        if feed_type == "reddit":
            identifier = identifier.strip().lstrip('r/')
            # Try to match with filter type appended
            feeds = get_feeds(interaction.guild.id)
            for feed in feeds:
                if feed["type"] == "reddit" and feed["url"].startswith(identifier):
                    identifier = feed["url"]
                    break

        success, message = remove_feed(interaction.guild.id, feed_type, identifier)

        if success:
            embed = discord.Embed(
                title="✅ Feed Removed",
                description=message,
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)

    @news_group.command(name="list", description="List all auto news feeds")
    async def list_feeds(self, interaction: discord.Interaction):
        """List all feeds"""

        logger.info(f"Auto news list viewed by {interaction.user} in {interaction.guild.name}")

        feeds = get_feeds(interaction.guild.id)
        news_channel_id = get_news_channel(interaction.guild.id)

        embed = discord.Embed(
            title="📰 Auto News Feeds",
            color=discord.Color.blue()
        )

        # News channel
        if news_channel_id:
            channel = interaction.guild.get_channel(news_channel_id)
            embed.add_field(
                name="News Channel",
                value=channel.mention if channel else "Channel not found",
                inline=False
            )
        else:
            embed.add_field(
                name="News Channel",
                value="Not set up - use `/autonews setup`",
                inline=False
            )

        # Feeds by type
        if feeds:
            reddit_feeds = [f for f in feeds if f["type"] == "reddit"]
            rss_feeds = [f for f in feeds if f["type"] == "rss"]

            if reddit_feeds:
                reddit_list = "\n".join([
                    f"• **{f.get('name', f['url'])}**"
                    for f in reddit_feeds
                ])
                embed.add_field(
                    name="🟠 Reddit Feeds",
                    value=reddit_list,
                    inline=False
                )

            if rss_feeds:
                rss_list = "\n".join([
                    f"• **{f.get('name', f['url'][:40])}**"
                    for f in rss_feeds
                ])
                embed.add_field(
                    name="📡 RSS Feeds",
                    value=rss_list,
                    inline=False
                )
        else:
            embed.add_field(
                name="Feeds",
                value="No feeds configured.\nAdd one with `/autonews reddit` or `/autonews rss`",
                inline=False
            )

        embed.set_footer(text="Gojo checks for new posts every 10 minutes")
        await interaction.response.send_message(embed=embed)

    # Error handlers
    @setup.error
    @add_reddit.error
    @add_rss.error
    @remove_feed_cmd.error
    async def news_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need **Administrator** permission to manage auto news feeds.",
                ephemeral=True
            )
        else:
            logger.error(f"Auto news error: {error}")
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(AutoNews(bot))
