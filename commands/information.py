"""
/information Command
Displays bot information, features, and available commands
Shows only commands the user has permission to use

IMPORTANT: Update this file when adding new commands!
Last updated: 2026-01-08
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from typing import List, Dict

import config
from utils.logger import log_command, logger


# =============================================================================
# COMMAND REGISTRY - UPDATE THIS WHEN ADDING NEW COMMANDS
# =============================================================================
# Each command entry contains:
# - name: The command name (e.g., "/ping")
# - description: What the command does
# - usage: Example usage
# - category: Which category it belongs to
# - permission: Required permission (None = everyone, or discord permission name)
#
# Categories: "general", "moderation", "admin", "fun"
# =============================================================================

COMMANDS_REGISTRY = [
    # General Commands (Everyone can use)
    {
        "name": "/ping",
        "description": "Check if the bot is online and responsive",
        "usage": "/ping",
        "category": "general",
        "permission": None
    },
    {
        "name": "/help",
        "description": "Shows a quick list of all commands",
        "usage": "/help",
        "category": "general",
        "permission": None
    },
    {
        "name": "/information",
        "description": "Detailed bot info and command guide (this command)",
        "usage": "/information",
        "category": "general",
        "permission": None
    },
    {
        "name": "/dq",
        "description": "Get a random inspirational quote from movies, anime, and famous people",
        "usage": "/dq",
        "category": "fun",
        "permission": None
    },
    {
        "name": "/67",
        "description": "Unleash maximum cringe upon the server",
        "usage": "/67",
        "category": "fun",
        "permission": None
    },
    {
        "name": "/start",
        "description": "Getting started guide for new users with interactive buttons",
        "usage": "/start",
        "category": "general",
        "permission": None
    },
    {
        "name": "/invitegojo",
        "description": "Get the link to add Gojo to your server",
        "usage": "/invitegojo",
        "category": "general",
        "permission": None
    },

    # Games Commands (Everyone can use)
    {
        "name": "/trivia",
        "description": "Start a trivia game with various categories",
        "usage": "/trivia category:general difficulty:medium",
        "category": "games",
        "permission": None
    },
    {
        "name": "/minesweeper",
        "description": "Generate a minesweeper game board",
        "usage": "/minesweeper size:medium mines:10",
        "category": "games",
        "permission": None
    },
    {
        "name": "/connect4",
        "description": "Start a Connect 4 game against another player",
        "usage": "/connect4 opponent:@user",
        "category": "games",
        "permission": None
    },
    {
        "name": "/tictactoe",
        "description": "Start a Tic Tac Toe game against another player",
        "usage": "/tictactoe opponent:@user",
        "category": "games",
        "permission": None
    },
    {
        "name": "/rps",
        "description": "Play Rock Paper Scissors against the bot or a player",
        "usage": "/rps choice:rock OR /rps opponent:@user",
        "category": "games",
        "permission": None
    },
    {
        "name": "/8ball",
        "description": "Ask the magic 8-ball a question",
        "usage": "/8ball question:Will I win?",
        "category": "games",
        "permission": None
    },
    {
        "name": "/roll",
        "description": "Roll dice with custom notation",
        "usage": "/roll dice:2d6 OR /roll dice:1d20+5",
        "category": "games",
        "permission": None
    },

    # Profile Commands (Everyone can use)
    {
        "name": "/profile",
        "description": "View your graphical profile card with stats and badges",
        "usage": "/profile OR /profile user:@someone",
        "category": "profile",
        "permission": None
    },
    {
        "name": "/profilecolor",
        "description": "Change your profile card accent color",
        "usage": "/profilecolor color:#FF5733 OR /profilecolor preset:ocean",
        "category": "profile",
        "permission": None
    },
    {
        "name": "/profilepresets",
        "description": "View available profile color presets",
        "usage": "/profilepresets",
        "category": "profile",
        "permission": None
    },

    # Reminder Commands (Everyone can use)
    {
        "name": "/remind",
        "description": "Set a personal reminder (DMs you when time is up)",
        "usage": "/remind time:1h message:Check the oven",
        "category": "reminders",
        "permission": None
    },
    {
        "name": "/reminders",
        "description": "View all your active reminders",
        "usage": "/reminders",
        "category": "reminders",
        "permission": None
    },
    {
        "name": "/reminder delete",
        "description": "Delete a specific reminder by ID",
        "usage": "/reminder delete reminder_id:123",
        "category": "reminders",
        "permission": None
    },
    {
        "name": "/reminder clear",
        "description": "Clear all your reminders",
        "usage": "/reminder clear",
        "category": "reminders",
        "permission": None
    },
    {
        "name": "/reminder info",
        "description": "View details of a specific reminder",
        "usage": "/reminder info reminder_id:123",
        "category": "reminders",
        "permission": None
    },

    # Voice Channel Commands (Everyone can use)
    {
        "name": "/tempvc panel",
        "description": "Open control panel for your temporary voice channel",
        "usage": "/tempvc panel",
        "category": "voicechannel",
        "permission": None
    },
    {
        "name": "/vcsignal",
        "description": "Send a private signal to invite a friend to your voice channel",
        "usage": "/vcsignal user:@friend message:Join me!",
        "category": "voicechannel",
        "permission": None
    },
    {
        "name": "/vclink",
        "description": "Get a shareable info embed for your current voice channel",
        "usage": "/vclink",
        "category": "voicechannel",
        "permission": None
    },

    # Economy Commands (Everyone can use)
    {
        "name": "/balance",
        "description": "Check your coin balance and gambling stats",
        "usage": "/balance or /balance @user",
        "category": "economy",
        "permission": None
    },
    {
        "name": "/claimdaily",
        "description": "Claim daily coins (streak bonus increases rewards)",
        "usage": "/claimdaily",
        "category": "economy",
        "permission": None
    },
    {
        "name": "/leaderboard",
        "description": "View the top 10 richest users",
        "usage": "/leaderboard",
        "category": "economy",
        "permission": None
    },

    # Gambling Commands (Everyone can use)
    {
        "name": "/bj",
        "description": "Play blackjack against the dealer (1x-1.5x payout)",
        "usage": "/bj bet:100",
        "category": "gambling",
        "permission": None
    },
    {
        "name": "/roulette",
        "description": "Bet on red/black, odd/even, or ranges (2x-3x payout)",
        "usage": "/roulette bet:100 bet_type:red",
        "category": "gambling",
        "permission": None
    },
    {
        "name": "/roulettenumber",
        "description": "Bet on one or more numbers (36x for 1, 18x for 2, etc.)",
        "usage": "/roulettenumber bet:100 numbers:7 OR numbers:7, 17, 23 OR numbers:1-6",
        "category": "gambling",
        "permission": None
    },
    {
        "name": "/roulettetable",
        "description": "View the roulette betting table with all numbers and payouts",
        "usage": "/roulettetable",
        "category": "gambling",
        "permission": None
    },
    {
        "name": "/coinflip",
        "description": "Challenge someone to a coinflip duel for coins",
        "usage": "/coinflip opponent:@user bet:100",
        "category": "gambling",
        "permission": None
    },
    {
        "name": "/guessnumber",
        "description": "Guess 1-50 for 500x payout! (2% chance)",
        "usage": "/guessnumber bet:50 guess:25",
        "category": "gambling",
        "permission": None
    },

    # Music Commands (Everyone can use)
    {
        "name": "/play",
        "description": "Play a song immediately (or next if something is playing)",
        "usage": "/play query:song name OR /play query:<soundcloud link>",
        "category": "music",
        "permission": None
    },
    {
        "name": "/addsong",
        "description": "Add a song to the queue",
        "usage": "/addsong query:song name OR /addsong query:<soundcloud link>",
        "category": "music",
        "permission": None
    },
    {
        "name": "/playlist",
        "description": "Play a SoundCloud playlist or album",
        "usage": "/playlist url:<soundcloud playlist/album link>",
        "category": "music",
        "permission": None
    },
    {
        "name": "/pause",
        "description": "Pause the currently playing song",
        "usage": "/pause",
        "category": "music",
        "permission": None
    },
    {
        "name": "/resume",
        "description": "Resume a paused song",
        "usage": "/resume",
        "category": "music",
        "permission": None
    },
    {
        "name": "/skip",
        "description": "Skip to the next song in queue",
        "usage": "/skip",
        "category": "music",
        "permission": None
    },
    {
        "name": "/stop",
        "description": "Stop music and leave the voice channel",
        "usage": "/stop",
        "category": "music",
        "permission": None
    },
    {
        "name": "/queue",
        "description": "View the music queue with remove buttons",
        "usage": "/queue",
        "category": "music",
        "permission": None
    },
    {
        "name": "/nowplaying",
        "description": "Show current song with Lyrics button (Genius integration)",
        "usage": "/nowplaying",
        "category": "music",
        "permission": None
    },
    {
        "name": "/volume",
        "description": "Adjust the music volume (0-100)",
        "usage": "/volume 50",
        "category": "music",
        "permission": None
    },
    {
        "name": "/shuffle",
        "description": "Shuffle the songs in the queue",
        "usage": "/shuffle",
        "category": "music",
        "permission": None
    },
    {
        "name": "/clearqueue",
        "description": "Clear all songs from the queue (Mods only)",
        "usage": "/clearqueue",
        "category": "music",
        "permission": "manage_messages"
    },
    {
        "name": "/audiostatus",
        "description": "Check current audio optimization settings for your server",
        "usage": "/audiostatus",
        "category": "music",
        "permission": None
    },
    {
        "name": "/karaokelist",
        "description": "View all available karaoke songs",
        "usage": "/karaokelist",
        "category": "karaoke",
        "permission": None
    },
    {
        "name": "/karaokesolo",
        "description": "Start a solo karaoke performance with spotlight and countdown",
        "usage": "/karaokesolo singer:@user",
        "category": "karaoke",
        "permission": None
    },
    {
        "name": "/karaokeduet",
        "description": "Start a duet with two singers taking alternating lines",
        "usage": "/karaokeduet singer1:@user1 singer2:@user2",
        "category": "karaoke",
        "permission": None
    },
    {
        "name": "/karaoke",
        "description": "Shows karaoke mode options (redirects to solo/duet)",
        "usage": "/karaoke",
        "category": "karaoke",
        "permission": None
    },

    # Achievement Commands (Everyone can use)
    {
        "name": "/achievements",
        "description": "View your unlocked achievements and progress",
        "usage": "/achievements or /achievements @user",
        "category": "achievements",
        "permission": None
    },
    {
        "name": "/achievementstats",
        "description": "View detailed progress toward all achievements with progress bars",
        "usage": "/achievementstats or /achievementstats user:@someone",
        "category": "achievements",
        "permission": None
    },

    # Leveling Commands (Everyone can use)
    {
        "name": "/rank",
        "description": "View your level and XP with a beautiful graphical rank card",
        "usage": "/rank or /rank @user",
        "category": "leveling",
        "permission": None
    },
    {
        "name": "/xpleaderboard",
        "description": "View the server's XP leaderboard sorted by total XP",
        "usage": "/xpleaderboard or /xpleaderboard page:2",
        "category": "leveling",
        "permission": None
    },
    {
        "name": "/levels",
        "description": "View XP requirements for each level and milestone rewards",
        "usage": "/levels",
        "category": "leveling",
        "permission": None
    },

    # Reputation Commands (Everyone can use)
    {
        "name": "/rep",
        "description": "Give a reputation point to a helpful member (1 per day)",
        "usage": "/rep @user",
        "category": "reputation",
        "permission": None
    },
    {
        "name": "/repcheck",
        "description": "Check reputation points for yourself or another user",
        "usage": "/repcheck or /repcheck @user",
        "category": "reputation",
        "permission": None
    },
    {
        "name": "/repleaderboard",
        "description": "View the most reputable members in the server",
        "usage": "/repleaderboard or /repleaderboard page:2",
        "category": "reputation",
        "permission": None
    },

    # Shop Commands (Everyone can use)
    {
        "name": "/shop",
        "description": "Browse the server shop for XP boosters, custom roles, and more",
        "usage": "/shop",
        "category": "shop",
        "permission": None
    },
    {
        "name": "/buy",
        "description": "Purchase an item from the shop",
        "usage": "/buy item:xp_boost_2h",
        "category": "shop",
        "permission": None
    },
    {
        "name": "/inventory",
        "description": "View your active shop items and purchases",
        "usage": "/inventory",
        "category": "shop",
        "permission": None
    },

    # Daily Quest Commands (Everyone can use)
    {
        "name": "/quests",
        "description": "View your daily quests and progress",
        "usage": "/quests",
        "category": "quests",
        "permission": None
    },
    {
        "name": "/questkeys",
        "description": "Check how many quest keys you have",
        "usage": "/questkeys",
        "category": "quests",
        "permission": None
    },
    {
        "name": "/lootbox",
        "description": "Open a lootbox using a quest key for rewards",
        "usage": "/lootbox",
        "category": "quests",
        "permission": None
    },
    {
        "name": "/lootboxodds",
        "description": "View lootbox reward odds and possible prizes",
        "usage": "/lootboxodds",
        "category": "quests",
        "permission": None
    },

    # Stock Market Commands (Everyone can use)
    {
        "name": "/invest",
        "description": "Buy shares in another member's stock",
        "usage": "/invest @user shares:10",
        "category": "stocks",
        "permission": None
    },
    {
        "name": "/sell",
        "description": "Sell shares you own in another member",
        "usage": "/sell @user shares:5",
        "category": "stocks",
        "permission": None
    },
    {
        "name": "/portfolio",
        "description": "View your investment portfolio and holdings",
        "usage": "/portfolio",
        "category": "stocks",
        "permission": None
    },
    {
        "name": "/stockprice",
        "description": "Check a member's current stock price and info",
        "usage": "/stockprice @user",
        "category": "stocks",
        "permission": None
    },
    {
        "name": "/stockmarket",
        "description": "View the community stock market overview",
        "usage": "/stockmarket",
        "category": "stocks",
        "permission": None
    },

    # Moderation Commands (Require specific permissions)
    {
        "name": "/moderationpanel",
        "description": "Interactive panel with all moderation tools (kick, ban, timeout, warn, clear messages)",
        "usage": "/moderationpanel @user",
        "category": "moderation",
        "permission": "moderate_members"
    },
    {
        "name": "/timeout",
        "description": "Temporarily mute a user for a specified time",
        "usage": "/timeout @user 10 Being disruptive",
        "category": "moderation",
        "permission": "moderate_members"
    },
    {
        "name": "/warning",
        "description": "Issue a warning to a user (Minor/Medium/Serious)",
        "usage": "/warning @user Medium Breaking rules",
        "category": "moderation",
        "permission": "manage_messages"
    },
    {
        "name": "/modtalk",
        "description": "Send a message as the bot in any channel",
        "usage": "/modtalk",
        "category": "moderation",
        "permission": "manage_messages"
    },
    {
        "name": "/moderationlogs",
        "description": "View all moderation actions with filters",
        "usage": "/moderationlogs or /moderationlogs @user",
        "category": "moderation",
        "permission": "manage_messages"
    },
    {
        "name": "/modstats",
        "description": "View moderation statistics and top moderators",
        "usage": "/modstats",
        "category": "moderation",
        "permission": "manage_messages"
    },
    {
        "name": "/userhistory",
        "description": "View a user's moderation history",
        "usage": "/userhistory @user",
        "category": "moderation",
        "permission": "manage_messages"
    },
    {
        "name": "/modactivity",
        "description": "View a moderator's action history",
        "usage": "/modactivity or /modactivity @moderator",
        "category": "moderation",
        "permission": "manage_messages"
    },

    # Admin Commands (Require administrator)
    {
        "name": "/adminprofile",
        "description": "View detailed member profile with warnings and server stats (3 pages)",
        "usage": "/adminprofile @user",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/webhook",
        "description": "Create and send webhook messages with embeds",
        "usage": "/webhook",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/webhookedit",
        "description": "Edit an existing webhook message",
        "usage": "/webhookedit <message_link>",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/givecoins",
        "description": "Give coins to a user (preset amounts or custom)",
        "usage": "/givecoins @user",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/ultraoptimizemusic",
        "description": "Toggle ultra audio quality mode for maximum music quality",
        "usage": "/ultraoptimizemusic or /ultraoptimizemusic enable:True",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/backfill",
        "description": "Sync all historical data: messages, gambling wins, balance, and daily streaks to achievements",
        "usage": "/backfill or /backfill skip_messages:True (economy only)",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/syncstats",
        "description": "Sync economy data (gambling, balance, streaks) to achievement stats",
        "usage": "/syncstats or /syncstats user:@someone",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/setup",
        "description": "Interactive setup wizard to configure all bot features",
        "usage": "/setup",
        "category": "admin",
        "permission": "administrator"
    },
    {
        "name": "/dashboard",
        "description": "View server configuration status and quick overview",
        "usage": "/dashboard",
        "category": "admin",
        "permission": "manage_guild"
    },
    {
        "name": "/tempvc setup",
        "description": "Set up Join-to-Create voice channels for the server",
        "usage": "/tempvc setup channel:#join-vc category:#temp-vcs",
        "category": "voicechannel",
        "permission": "administrator"
    },
    {
        "name": "/tempvc disable",
        "description": "Disable the Join-to-Create voice channel system",
        "usage": "/tempvc disable",
        "category": "voicechannel",
        "permission": "administrator"
    },

    # Live Alerts Commands (Require administrator)
    {
        "name": "/livealerts setup",
        "description": "Set up the channel for live stream alerts",
        "usage": "/livealerts setup channel:#alerts",
        "category": "livealerts",
        "permission": "administrator"
    },
    {
        "name": "/livealerts add",
        "description": "Add a Twitch or YouTube streamer to track",
        "usage": "/livealerts add platform:twitch username:ninja",
        "category": "livealerts",
        "permission": "administrator"
    },
    {
        "name": "/livealerts remove",
        "description": "Remove a streamer from tracking",
        "usage": "/livealerts remove platform:twitch username:ninja",
        "category": "livealerts",
        "permission": "administrator"
    },
    {
        "name": "/livealerts list",
        "description": "List all tracked streamers and configuration",
        "usage": "/livealerts list",
        "category": "livealerts",
        "permission": None
    },
    {
        "name": "/livealerts role",
        "description": "Set a role to ping when someone goes live",
        "usage": "/livealerts role @StreamNotify",
        "category": "livealerts",
        "permission": "administrator"
    },

    # Auto News Commands (Require administrator)
    {
        "name": "/autonews setup",
        "description": "Set up the channel for automated news posts",
        "usage": "/autonews setup channel:#community-feed",
        "category": "autonews",
        "permission": "administrator"
    },
    {
        "name": "/autonews reddit",
        "description": "Add a subreddit to auto-post from",
        "usage": "/autonews reddit subreddit:gaming filter_type:hot",
        "category": "autonews",
        "permission": "administrator"
    },
    {
        "name": "/autonews rss",
        "description": "Add an RSS feed to auto-post from",
        "usage": "/autonews rss url:https://example.com/feed.xml",
        "category": "autonews",
        "permission": "administrator"
    },
    {
        "name": "/autonews remove",
        "description": "Remove a feed from tracking",
        "usage": "/autonews remove feed_type:reddit identifier:gaming",
        "category": "autonews",
        "permission": "administrator"
    },
    {
        "name": "/autonews list",
        "description": "List all configured news feeds",
        "usage": "/autonews list",
        "category": "autonews",
        "permission": None
    },

    # Support/Ticket Commands (Require administrator)
    {
        "name": "/ticket setup",
        "description": "Set up the ticket system with staff role and log channel",
        "usage": "/ticket setup staff_role:@Staff log_channel:#ticket-logs category:Tickets",
        "category": "support",
        "permission": "administrator"
    },
    {
        "name": "/ticket panel",
        "description": "Send a new ticket panel embed with Open Ticket button",
        "usage": "/ticket panel",
        "category": "support",
        "permission": "administrator"
    },
    {
        "name": "/ticket add",
        "description": "Add a user to the current ticket channel",
        "usage": "/ticket add user:@someone",
        "category": "support",
        "permission": None  # Staff or ticket owner can use
    },
    {
        "name": "/ticket remove",
        "description": "Remove a user from the current ticket channel",
        "usage": "/ticket remove user:@someone",
        "category": "support",
        "permission": "manage_messages"  # Staff only
    },

    # Giveaway Commands (Require manage_guild)
    {
        "name": "/giveaway start",
        "description": "Start a new giveaway with prize and duration",
        "usage": "/giveaway start prize:Steam Key duration:1d winners:1",
        "category": "giveaways",
        "permission": "manage_guild"
    },
    {
        "name": "/giveaway end",
        "description": "End a giveaway early and pick winners",
        "usage": "/giveaway end message_link:<message link>",
        "category": "giveaways",
        "permission": "manage_guild"
    },
    {
        "name": "/giveaway reroll",
        "description": "Reroll winners for a giveaway",
        "usage": "/giveaway reroll message_link:<message link> count:1",
        "category": "giveaways",
        "permission": "manage_guild"
    },
    {
        "name": "/giveaway list",
        "description": "List all active giveaways in the server",
        "usage": "/giveaway list",
        "category": "giveaways",
        "permission": "manage_guild"
    },
    {
        "name": "/giveaway delete",
        "description": "Delete a giveaway",
        "usage": "/giveaway delete message_link:<message link>",
        "category": "giveaways",
        "permission": "manage_guild"
    },

    # Poll Commands (Require manage_messages)
    {
        "name": "/poll create",
        "description": "Create a new poll with multiple options",
        "usage": "/poll create question:Favorite color? options:Red | Blue | Green duration:1h",
        "category": "polls",
        "permission": "manage_messages"
    },
    {
        "name": "/poll end",
        "description": "End a poll early and show results",
        "usage": "/poll end message_link:<message link>",
        "category": "polls",
        "permission": "manage_messages"
    },
    {
        "name": "/poll results",
        "description": "View current results of a poll",
        "usage": "/poll results message_link:<message link>",
        "category": "polls",
        "permission": None
    },
    {
        "name": "/poll delete",
        "description": "Delete a poll",
        "usage": "/poll delete message_link:<message link>",
        "category": "polls",
        "permission": "manage_messages"
    },

    # Reaction Role Commands (Require administrator)
    {
        "name": "/reactionrole create",
        "description": "Create a new reaction role panel with buttons/dropdowns",
        "usage": "/reactionrole create title:Roles description:Pick your roles type:buttons",
        "category": "reactionroles",
        "permission": "administrator"
    },
    {
        "name": "/reactionrole addrole",
        "description": "Add a role to a reaction role panel",
        "usage": "/reactionrole addrole message_link:<link> role:@Role label:Click me",
        "category": "reactionroles",
        "permission": "administrator"
    },
    {
        "name": "/reactionrole removerole",
        "description": "Remove a role from a panel",
        "usage": "/reactionrole removerole message_link:<link> role:@Role",
        "category": "reactionroles",
        "permission": "administrator"
    },
    {
        "name": "/reactionrole delete",
        "description": "Delete a reaction role panel",
        "usage": "/reactionrole delete message_link:<link>",
        "category": "reactionroles",
        "permission": "administrator"
    },
    {
        "name": "/reactionrole list",
        "description": "List all reaction role panels in the server",
        "usage": "/reactionrole list",
        "category": "reactionroles",
        "permission": "administrator"
    },
    {
        "name": "/reactionrole mode",
        "description": "Change panel mode (single/multiple selection)",
        "usage": "/reactionrole mode message_link:<link> mode:single",
        "category": "reactionroles",
        "permission": "administrator"
    },

    # Custom Command Commands (Require administrator)
    {
        "name": "/customcmd create",
        "description": "Create a custom command with trigger and response",
        "usage": "/customcmd create trigger:hello response:Hello there!",
        "category": "customcommands",
        "permission": "administrator"
    },
    {
        "name": "/customcmd delete",
        "description": "Delete a custom command",
        "usage": "/customcmd delete trigger:hello",
        "category": "customcommands",
        "permission": "administrator"
    },
    {
        "name": "/customcmd edit",
        "description": "Edit an existing custom command",
        "usage": "/customcmd edit trigger:hello new_response:Hi there!",
        "category": "customcommands",
        "permission": "administrator"
    },
    {
        "name": "/customcmd list",
        "description": "List all custom commands",
        "usage": "/customcmd list",
        "category": "customcommands",
        "permission": "administrator"
    },
    {
        "name": "/customcmd info",
        "description": "View details of a custom command",
        "usage": "/customcmd info trigger:hello",
        "category": "customcommands",
        "permission": "administrator"
    },
    {
        "name": "/customcmd prefix",
        "description": "Set the trigger prefix for custom commands",
        "usage": "/customcmd prefix prefix:!",
        "category": "customcommands",
        "permission": "administrator"
    },

    # Welcome Commands (Require administrator)
    {
        "name": "/welcome enable",
        "description": "Enable or disable welcome messages",
        "usage": "/welcome enable enabled:True",
        "category": "welcome",
        "permission": "administrator"
    },
    {
        "name": "/welcome channel",
        "description": "Set the channel for welcome messages",
        "usage": "/welcome channel channel:#welcome",
        "category": "welcome",
        "permission": "administrator"
    },
    {
        "name": "/welcome message",
        "description": "Set the welcome message text",
        "usage": "/welcome message message:Welcome {user} to {server}!",
        "category": "welcome",
        "permission": "administrator"
    },
    {
        "name": "/welcome image",
        "description": "Enable or disable welcome card images",
        "usage": "/welcome image enabled:True",
        "category": "welcome",
        "permission": "administrator"
    },
    {
        "name": "/welcome background",
        "description": "Set custom background for welcome cards",
        "usage": "/welcome background url:<image url>",
        "category": "welcome",
        "permission": "administrator"
    },
    {
        "name": "/welcome dm",
        "description": "Configure DM welcome messages",
        "usage": "/welcome dm enabled:True message:Welcome to our server!",
        "category": "welcome",
        "permission": "administrator"
    },
    {
        "name": "/welcome test",
        "description": "Test the welcome card with yourself",
        "usage": "/welcome test",
        "category": "welcome",
        "permission": "administrator"
    },
    {
        "name": "/welcome status",
        "description": "View current welcome configuration",
        "usage": "/welcome status",
        "category": "welcome",
        "permission": "administrator"
    },

    # Goodbye Commands (Require administrator)
    {
        "name": "/goodbye enable",
        "description": "Enable or disable goodbye messages",
        "usage": "/goodbye enable enabled:True",
        "category": "goodbye",
        "permission": "administrator"
    },
    {
        "name": "/goodbye channel",
        "description": "Set the channel for goodbye messages",
        "usage": "/goodbye channel channel:#goodbye",
        "category": "goodbye",
        "permission": "administrator"
    },
    {
        "name": "/goodbye message",
        "description": "Set the goodbye message text",
        "usage": "/goodbye message message:Goodbye {user}!",
        "category": "goodbye",
        "permission": "administrator"
    },
    {
        "name": "/goodbye image",
        "description": "Enable or disable goodbye card images",
        "usage": "/goodbye image enabled:True",
        "category": "goodbye",
        "permission": "administrator"
    },
    {
        "name": "/goodbye test",
        "description": "Test the goodbye card with yourself",
        "usage": "/goodbye test",
        "category": "goodbye",
        "permission": "administrator"
    },

    # Autorole Commands (Require administrator)
    {
        "name": "/autorole enable",
        "description": "Enable or disable auto roles on join",
        "usage": "/autorole enable enabled:True",
        "category": "autorole",
        "permission": "administrator"
    },
    {
        "name": "/autorole add",
        "description": "Add a role to auto-assign on join",
        "usage": "/autorole add role:@Member",
        "category": "autorole",
        "permission": "administrator"
    },
    {
        "name": "/autorole remove",
        "description": "Remove a role from auto-assign",
        "usage": "/autorole remove role:@Member",
        "category": "autorole",
        "permission": "administrator"
    },
    {
        "name": "/autorole list",
        "description": "List all auto-assign roles",
        "usage": "/autorole list",
        "category": "autorole",
        "permission": "administrator"
    },
    {
        "name": "/autorole clear",
        "description": "Remove all auto-assign roles",
        "usage": "/autorole clear",
        "category": "autorole",
        "permission": "administrator"
    },

    # Language Commands (Require administrator)
    {
        "name": "/language set",
        "description": "Set the server language for bot responses",
        "usage": "/language set language:da",
        "category": "language",
        "permission": "administrator"
    },
    {
        "name": "/language list",
        "description": "List all available languages",
        "usage": "/language list",
        "category": "language",
        "permission": None
    },
    {
        "name": "/language current",
        "description": "View the current server language",
        "usage": "/language current",
        "category": "language",
        "permission": None
    },
    {
        "name": "/language preview",
        "description": "Preview how bot messages look in a language",
        "usage": "/language preview language:da",
        "category": "language",
        "permission": None
    },

    # Owner Commands (Server Owner only)
    {
        "name": "/clearlogs",
        "description": "Clear all moderation logs (Server Owner only)",
        "usage": "/clearlogs",
        "category": "owner",
        "permission": "administrator"  # We check for owner in the command itself
    },
    {
        "name": "/setuplogs",
        "description": "Set up event logging channel (Server Owner only)",
        "usage": "/setuplogs #log-channel",
        "category": "owner",
        "permission": "administrator"
    },
    {
        "name": "/editlogs",
        "description": "Change the event logging channel (Server Owner only)",
        "usage": "/editlogs #new-log-channel",
        "category": "owner",
        "permission": "administrator"
    },
    {
        "name": "/searchlogs",
        "description": "Search event logs with text, user, or category filters (Server Owner only)",
        "usage": "/searchlogs search_text:badword OR /searchlogs user:@someone category:messages",
        "category": "owner",
        "permission": "administrator"
    },
    {
        "name": "/logstats",
        "description": "View event logging statistics (Server Owner only)",
        "usage": "/logstats",
        "category": "owner",
        "permission": "administrator"
    },
    {
        "name": "/clearmessages",
        "description": "Bulk delete messages from a channel (Server Owner only)",
        "usage": "/clearmessages amount:50 OR /clearmessages amount:20 user:@someone channel:#general",
        "category": "owner",
        "permission": "administrator"
    },

    # Additional Profile Commands (Everyone can use)
    {
        "name": "/profilemotto",
        "description": "Set your profile motto (short tagline, max 50 chars)",
        "usage": "/profilemotto motto:Living my best life",
        "category": "profile",
        "permission": None
    },
    {
        "name": "/profilebanner",
        "description": "View, buy, or equip profile banners",
        "usage": "/profilebanner action:view OR /profilebanner action:buy banner:sunset",
        "category": "profile",
        "permission": None
    },
    {
        "name": "/profilebadges",
        "description": "View your earned profile badges",
        "usage": "/profilebadges OR /profilebadges user:@someone",
        "category": "profile",
        "permission": None
    },
    {
        "name": "/profilefeature",
        "description": "Choose badges to feature on your profile (up to 3)",
        "usage": "/profilefeature badges:chatterbox, rich, level_10",
        "category": "profile",
        "permission": None
    },
    {
        "name": "/profilecard",
        "description": "View a text-based profile overview with all customizations",
        "usage": "/profilecard OR /profilecard user:@someone",
        "category": "profile",
        "permission": None
    },

    # Vault Commands (Everyone can use)
    {
        "name": "/vault create",
        "description": "Create a shared economy vault/club",
        "usage": "/vault create name:savings description:Our savings vault public:true",
        "category": "vault",
        "permission": None
    },
    {
        "name": "/vault deposit",
        "description": "Deposit coins into your vault",
        "usage": "/vault deposit amount:500",
        "category": "vault",
        "permission": None
    },
    {
        "name": "/vault withdraw",
        "description": "Withdraw coins from vault (leader only)",
        "usage": "/vault withdraw amount:500 reason:Server event prize",
        "category": "vault",
        "permission": None
    },
    {
        "name": "/vault info",
        "description": "View vault information and progress",
        "usage": "/vault info OR /vault info name:myvault",
        "category": "vault",
        "permission": None
    },
    {
        "name": "/vault join",
        "description": "Join a public vault",
        "usage": "/vault join name:savings",
        "category": "vault",
        "permission": None
    },
    {
        "name": "/vault leave",
        "description": "Leave your current vault",
        "usage": "/vault leave",
        "category": "vault",
        "permission": None
    },
    {
        "name": "/vault list",
        "description": "List all vaults in the server",
        "usage": "/vault list",
        "category": "vault",
        "permission": None
    },
    {
        "name": "/vault goal",
        "description": "Set a savings goal for your vault (leader only)",
        "usage": "/vault goal amount:10000 name:Server Nitro",
        "category": "vault",
        "permission": None
    },
    {
        "name": "/vault members",
        "description": "View vault members and their contributions",
        "usage": "/vault members",
        "category": "vault",
        "permission": None
    },

    # Starboard Commands (Require administrator)
    {
        "name": "/starboard setup",
        "description": "Set up the starboard hall of fame channel",
        "usage": "/starboard setup channel:#starboard",
        "category": "starboard",
        "permission": "administrator"
    },
    {
        "name": "/starboard threshold",
        "description": "Set minimum stars required (1-25)",
        "usage": "/starboard threshold stars:3",
        "category": "starboard",
        "permission": "administrator"
    },
    {
        "name": "/starboard emoji",
        "description": "Set the starboard reaction emoji",
        "usage": "/starboard emoji emoji:star",
        "category": "starboard",
        "permission": "administrator"
    },
    {
        "name": "/starboard selfstar",
        "description": "Allow or disallow self-starring",
        "usage": "/starboard selfstar allowed:false",
        "category": "starboard",
        "permission": "administrator"
    },
    {
        "name": "/starboard disable",
        "description": "Disable the starboard",
        "usage": "/starboard disable",
        "category": "starboard",
        "permission": "administrator"
    },
    {
        "name": "/starboard stats",
        "description": "View starboard statistics",
        "usage": "/starboard stats",
        "category": "starboard",
        "permission": None
    },

    # Server Config Commands (Require administrator)
    {
        "name": "/serverconfig view",
        "description": "View current server module configuration",
        "usage": "/serverconfig view",
        "category": "serverconfig",
        "permission": "administrator"
    },
    {
        "name": "/serverconfig toggle",
        "description": "Enable or disable a bot module",
        "usage": "/serverconfig toggle module:gambling enabled:false",
        "category": "serverconfig",
        "permission": "administrator"
    },
    {
        "name": "/serverconfig reset",
        "description": "Reset all settings to defaults",
        "usage": "/serverconfig reset",
        "category": "serverconfig",
        "permission": "administrator"
    },

    # Auto-Thread Commands (Require administrator)
    {
        "name": "/autothread setup",
        "description": "Enable auto-threading for a channel",
        "usage": "/autothread setup channel:#discussions thread_name:Discussion by {user}",
        "category": "autothread",
        "permission": "administrator"
    },
    {
        "name": "/autothread disable",
        "description": "Disable auto-threading for a channel",
        "usage": "/autothread disable channel:#discussions",
        "category": "autothread",
        "permission": "administrator"
    },
    {
        "name": "/autothread list",
        "description": "List channels with auto-threading enabled",
        "usage": "/autothread list",
        "category": "autothread",
        "permission": "administrator"
    },

    # Anti-Scam Commands (Require administrator)
    {
        "name": "/antiscam enable",
        "description": "Enable anti-scam link protection",
        "usage": "/antiscam enable action:delete log_channel:#mod-logs",
        "category": "antiscam",
        "permission": "administrator"
    },
    {
        "name": "/antiscam disable",
        "description": "Disable anti-scam protection",
        "usage": "/antiscam disable",
        "category": "antiscam",
        "permission": "administrator"
    },
    {
        "name": "/antiscam settings",
        "description": "View current anti-scam settings",
        "usage": "/antiscam settings",
        "category": "antiscam",
        "permission": "administrator"
    },
    {
        "name": "/antiscam whitelist",
        "description": "Add/remove/list whitelisted domains",
        "usage": "/antiscam whitelist action:add domain:mysite.com",
        "category": "antiscam",
        "permission": "administrator"
    },
    {
        "name": "/antiscam logs",
        "description": "View recently blocked suspicious links",
        "usage": "/antiscam logs",
        "category": "antiscam",
        "permission": "administrator"
    },

    # Milestones Commands (Everyone can use)
    {
        "name": "/milestones",
        "description": "View server milestones, records, and firsts",
        "usage": "/milestones",
        "category": "milestones",
        "permission": None
    },
    {
        "name": "/serverhistory",
        "description": "View detailed server history timeline",
        "usage": "/serverhistory",
        "category": "milestones",
        "permission": None
    },

    # System Commands (Owner only)
    {
        "name": "/system health",
        "description": "View bot health and performance metrics (Owner only)",
        "usage": "/system health",
        "category": "system",
        "permission": "administrator"
    },
    {
        "name": "/system errors",
        "description": "View recent error logs (Owner only)",
        "usage": "/system errors",
        "category": "system",
        "permission": "administrator"
    },
    {
        "name": "/system servers",
        "description": "View server statistics breakdown (Owner only)",
        "usage": "/system servers",
        "category": "system",
        "permission": "administrator"
    },
    {
        "name": "/system clear",
        "description": "Clear the error log (Owner only)",
        "usage": "/system clear",
        "category": "system",
        "permission": "administrator"
    },

    # Server Reports Commands (Require administrator)
    {
        "name": "/serverreports setup",
        "description": "Set up automated weekly/daily server reports",
        "usage": "/serverreports setup channel:#admin frequency:weekly day:0 hour:9",
        "category": "serverreports",
        "permission": "administrator"
    },
    {
        "name": "/serverreports disable",
        "description": "Disable automated server reports",
        "usage": "/serverreports disable",
        "category": "serverreports",
        "permission": "administrator"
    },
    {
        "name": "/serverreports now",
        "description": "Generate a server report immediately",
        "usage": "/serverreports now",
        "category": "serverreports",
        "permission": "administrator"
    },
    {
        "name": "/serverreports settings",
        "description": "View current report settings",
        "usage": "/serverreports settings",
        "category": "serverreports",
        "permission": "administrator"
    },
]

# Category display info
CATEGORY_INFO = {
    "general": {
        "name": "General Commands",
        "emoji": "📌",
        "description": "Basic commands everyone can use"
    },
    "fun": {
        "name": "Fun Commands",
        "emoji": "🎮",
        "description": "Entertainment and fun features"
    },
    "economy": {
        "name": "Economy Commands",
        "emoji": "💰",
        "description": "Virtual currency and daily rewards"
    },
    "gambling": {
        "name": "Gambling Commands",
        "emoji": "🎰",
        "description": "Casino games with virtual coins"
    },
    "music": {
        "name": "Music Commands",
        "emoji": "🔊",
        "description": "Play music from SoundCloud in voice channels"
    },
    "karaoke": {
        "name": "Karaoke Commands",
        "emoji": "🎤",
        "description": "Sing along with synced lyrics and spotlight features"
    },
    "achievements": {
        "name": "Achievement Commands",
        "emoji": "🏆",
        "description": "Track progress and unlock achievements"
    },
    "leveling": {
        "name": "Leveling Commands",
        "emoji": "📊",
        "description": "XP, levels, and rank cards"
    },
    "reputation": {
        "name": "Reputation Commands",
        "emoji": "⭐",
        "description": "Social recognition for helpful members"
    },
    "shop": {
        "name": "Shop Commands",
        "emoji": "🛒",
        "description": "Spend coins on XP boosters and custom roles"
    },
    "quests": {
        "name": "Daily Quest Commands",
        "emoji": "",
        "description": "Complete daily quests for keys and lootbox rewards"
    },
    "stocks": {
        "name": "Stock Market Commands",
        "emoji": "",
        "description": "Invest in other members and profit from their activity"
    },
    "voicechannel": {
        "name": "Voice Channel Commands",
        "emoji": "🔊",
        "description": "Temporary voice channels and VC tools"
    },
    "moderation": {
        "name": "Moderation Commands",
        "emoji": "🛡️",
        "description": "Tools for server moderators"
    },
    "support": {
        "name": "Support Ticket Commands",
        "emoji": "🎫",
        "description": "Ticket system for user support"
    },
    "admin": {
        "name": "Admin Commands",
        "emoji": "👑",
        "description": "Powerful tools for administrators"
    },
    "livealerts": {
        "name": "Live Alert Commands",
        "emoji": "📺",
        "description": "Stream notifications for Twitch and YouTube"
    },
    "autonews": {
        "name": "Auto News Commands",
        "emoji": "📰",
        "description": "Automated news from Reddit and RSS feeds"
    },
    "owner": {
        "name": "Owner Commands",
        "emoji": "🔐",
        "description": "Exclusive commands for the server owner"
    },
    "games": {
        "name": "Games Commands",
        "emoji": "🎮",
        "description": "Fun multiplayer and solo games"
    },
    "profile": {
        "name": "Profile Commands",
        "emoji": "🎨",
        "description": "Customize and view your profile card"
    },
    "reminders": {
        "name": "Reminder Commands",
        "emoji": "⏰",
        "description": "Set personal reminders that DM you"
    },
    "giveaways": {
        "name": "Giveaway Commands",
        "emoji": "🎉",
        "description": "Create and manage server giveaways"
    },
    "polls": {
        "name": "Poll Commands",
        "emoji": "📊",
        "description": "Create interactive polls with voting"
    },
    "reactionroles": {
        "name": "Reaction Role Commands",
        "emoji": "🏷️",
        "description": "Self-assign roles with buttons/dropdowns"
    },
    "customcommands": {
        "name": "Custom Command Commands",
        "emoji": "⚡",
        "description": "Create custom keyword responses"
    },
    "welcome": {
        "name": "Welcome Commands",
        "emoji": "👋",
        "description": "Configure welcome messages and cards"
    },
    "goodbye": {
        "name": "Goodbye Commands",
        "emoji": "👋",
        "description": "Configure goodbye messages and cards"
    },
    "autorole": {
        "name": "Auto Role Commands",
        "emoji": "🎭",
        "description": "Auto-assign roles to new members"
    },
    "language": {
        "name": "Language Commands",
        "emoji": "🌍",
        "description": "Set server language for bot responses"
    },
    "vault": {
        "name": "Vault Commands",
        "emoji": "🏦",
        "description": "Shared economy vaults for pooling coins together"
    },
    "starboard": {
        "name": "Starboard Commands",
        "emoji": "⭐",
        "description": "Hall of fame for starred messages"
    },
    "serverconfig": {
        "name": "Server Config Commands",
        "emoji": "⚙️",
        "description": "Module toggling and server settings"
    },
    "autothread": {
        "name": "Auto-Thread Commands",
        "emoji": "🧵",
        "description": "Automatic thread creation for channels"
    },
    "antiscam": {
        "name": "Anti-Scam Commands",
        "emoji": "🛡️",
        "description": "Protection against suspicious links"
    },
    "milestones": {
        "name": "Milestone Commands",
        "emoji": "🏆",
        "description": "Server records and historical firsts"
    },
    "system": {
        "name": "System Commands",
        "emoji": "🖥️",
        "description": "Bot health monitoring (Owner only)"
    },
    "serverreports": {
        "name": "Server Report Commands",
        "emoji": "📊",
        "description": "Automated weekly server health reports"
    }
}


def user_has_permission(user: discord.Member, permission: str) -> bool:
    """Check if a user has a specific permission"""
    if permission is None:
        return True
    return getattr(user.guild_permissions, permission, False)


def get_user_commands(user: discord.Member) -> Dict[str, List[Dict]]:
    """Get all commands the user has access to, organized by category"""
    accessible = {}

    for cmd in COMMANDS_REGISTRY:
        if user_has_permission(user, cmd["permission"]):
            category = cmd["category"]
            if category not in accessible:
                accessible[category] = []
            accessible[category].append(cmd)

    return accessible


class InformationView(View):
    """View with buttons to navigate between information pages"""

    def __init__(self, bot: commands.Bot, user: discord.Member, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user = user
        self.current_page = 1
        self.accessible_commands = get_user_commands(user)

        # Define category groups to reduce page count
        # Each group combines related categories into one page
        self.category_groups = [
            # Everyone categories
            {
                "name": "General & Fun",
                "emoji": "🎮",
                "color": discord.Color.blue(),
                "categories": ["general", "fun", "games"]
            },
            {
                "name": "Profile & Social",
                "emoji": "🎨",
                "color": discord.Color.from_rgb(233, 30, 99),
                "categories": ["profile", "reminders", "reputation", "milestones"]
            },
            {
                "name": "Economy & Gambling",
                "emoji": "💰",
                "color": discord.Color.gold(),
                "categories": ["economy", "gambling", "shop", "quests", "stocks", "vault"]
            },
            {
                "name": "Music & Entertainment",
                "emoji": "🎵",
                "color": discord.Color.green(),
                "categories": ["music", "karaoke"]
            },
            {
                "name": "Leveling & Achievements",
                "emoji": "📊",
                "color": discord.Color.from_rgb(88, 101, 242),
                "categories": ["leveling", "achievements"]
            },
            {
                "name": "Voice Channels",
                "emoji": "🔊",
                "color": discord.Color.from_rgb(87, 242, 135),
                "categories": ["voicechannel"]
            },
            # Admin categories
            {
                "name": "Giveaways & Polls",
                "emoji": "🎉",
                "color": discord.Color.from_rgb(255, 152, 0),
                "categories": ["giveaways", "polls"]
            },
            {
                "name": "Roles & Custom Commands",
                "emoji": "🏷️",
                "color": discord.Color.purple(),
                "categories": ["reactionroles", "customcommands"]
            },
            {
                "name": "Member Management",
                "emoji": "👋",
                "color": discord.Color.from_rgb(76, 175, 80),
                "categories": ["welcome", "goodbye", "autorole"]
            },
            {
                "name": "Starboard & Threads",
                "emoji": "⭐",
                "color": discord.Color.gold(),
                "categories": ["starboard", "autothread"]
            },
            {
                "name": "Server Config & Reports",
                "emoji": "⚙️",
                "color": discord.Color.from_rgb(96, 125, 139),
                "categories": ["serverconfig", "serverreports", "antiscam"]
            },
            {
                "name": "Language & Localization",
                "emoji": "🌍",
                "color": discord.Color.teal(),
                "categories": ["language"]
            },
            {
                "name": "Moderation",
                "emoji": "🛡️",
                "color": discord.Color.orange(),
                "categories": ["moderation"]
            },
            {
                "name": "Admin & Tickets",
                "emoji": "👑",
                "color": discord.Color.red(),
                "categories": ["admin", "support"]
            },
            {
                "name": "Feeds & Alerts",
                "emoji": "📺",
                "color": discord.Color.from_rgb(255, 69, 0),
                "categories": ["livealerts", "autonews"]
            },
            {
                "name": "Owner & System",
                "emoji": "🔐",
                "color": discord.Color.dark_red(),
                "categories": ["owner", "system"]
            },
        ]

        # Filter groups to only include those with accessible commands
        self.accessible_groups = []
        for group in self.category_groups:
            # Check if user has access to any category in this group
            has_access = any(cat in self.accessible_commands for cat in group["categories"])
            if has_access:
                self.accessible_groups.append(group)

        # +3 for About, Features, and Credits pages
        self.total_pages = 3 + len(self.accessible_groups)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to use the buttons"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "Only the person who ran the command can use these buttons!",
                ephemeral=True
            )
            return False
        return True

    def get_page_embed(self) -> discord.Embed:
        """Get the embed for the current page"""
        if self.current_page == 1:
            return self._build_about_embed()
        elif self.current_page == 2:
            return self._build_features_embed()
        elif self.current_page == self.total_pages:
            # Last page is Credits
            return self._build_credits_embed()
        else:
            # Pages 3 to (total-1) are command category groups
            group_index = self.current_page - 3
            if 0 <= group_index < len(self.accessible_groups):
                group = self.accessible_groups[group_index]
                return self._build_group_embed(group)
            return self._build_about_embed()

    def _build_about_embed(self) -> discord.Embed:
        """Build the about/introduction embed (Page 1)"""
        embed = discord.Embed(
            title=f"📖 About {config.BOT_NAME}",
            description=f"**Page 1/{self.total_pages}** - Introduction",
            color=discord.Color.blue()
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Bot introduction
        embed.add_field(
            name="🤖 What is Gojo?",
            value=(
                f"**{config.BOT_NAME}** is a powerful Discord bot designed to help "
                "manage your server with moderation tools, fun commands, and useful utilities.\n\n"
                "Named after the strongest sorcerer from Jujutsu Kaisen, this bot aims to be "
                "the strongest helper in your server!"
            ),
            inline=False
        )

        # Quick stats
        total_commands = len(COMMANDS_REGISTRY)
        user_accessible = sum(len(cmds) for cmds in self.accessible_commands.values())

        embed.add_field(
            name="📊 Quick Stats",
            value=(
                f"**Bot Version:** {config.BOT_VERSION}\n"
                f"**Total Commands:** {total_commands}\n"
                f"**Your Accessible Commands:** {user_accessible}\n"
                f"**Servers:** {len(self.bot.guilds)}"
            ),
            inline=True
        )

        # Your access level
        perms = self.user.guild_permissions
        if perms.administrator:
            access_level = "👑 Administrator"
            access_desc = "You have full access to all commands!"
        elif perms.manage_messages or perms.moderate_members:
            access_level = "🛡️ Moderator"
            access_desc = "You have access to moderation commands"
        else:
            access_level = "👤 Member"
            access_desc = "You have access to general commands"

        embed.add_field(
            name="🔑 Your Access Level",
            value=f"**{access_level}**\n{access_desc}",
            inline=True
        )

        embed.add_field(
            name="📚 Navigation",
            value=(
                "Use the **dropdown menu** below to jump to any section:\n"
                "• **Features** - Overview of bot capabilities\n"
                "• **Command Categories** - Detailed command lists\n"
                "• **Credits** - Acknowledgments"
            ),
            inline=False
        )

        embed.set_footer(text=f"Requested by {self.user} • Use dropdown to navigate")

        return embed

    def _build_features_embed(self) -> discord.Embed:
        """Build the features overview embed (Page 2) - Shows only public features"""
        embed = discord.Embed(
            title=f"✨ {config.BOT_NAME} Features",
            description=f"**Page 2/{self.total_pages}** - Features Overview",
            color=discord.Color.gold()
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Music Features (Everyone)
        embed.add_field(
            name="🔊 Music System",
            value=(
                "• **SoundCloud Integration** - Search and play from SoundCloud\n"
                "• **Search & Play** - Search for any song by name\n"
                "• **Direct Links** - Paste SoundCloud URLs directly\n"
                "• **Queue System** - Queue up multiple songs with remove buttons\n"
                "• **Playback Controls** - Pause, resume, skip, shuffle\n"
                "• **Volume Control** - Adjust volume as needed\n"
                "• **Lyrics** - View song lyrics via Genius integration\n"
                "• **Audio Optimization** - Smooth playback with Opus codec support"
            ),
            inline=False
        )

        # Karaoke Features (Everyone)
        embed.add_field(
            name="🎤 Karaoke System",
            value=(
                "• **Solo Mode** - Spotlight on a single singer with countdown\n"
                "• **Duet Mode** - Two singers with alternating lyric lines\n"
                "• **5-Second Countdown** - Get ready before the music starts\n"
                "• **Singer Spotlight** - Announces who's singing\n"
                "• **Synced Lyrics** - Real-time lyrics display while singing\n"
                "• **Song Library** - Browse available karaoke songs"
            ),
            inline=False
        )

        # Economy System (Everyone)
        embed.add_field(
            name="💰 Economy System",
            value=(
                "• **Virtual Coins** - Earn free coins (not purchasable with real money)\n"
                "• **Daily Claims** - Claim coins daily with streak bonuses\n"
                "• **Leaderboard** - Compete for the top spot\n"
                "• **Balance Tracking** - View your coins and gambling stats"
            ),
            inline=False
        )

        # Gambling System (Everyone)
        embed.add_field(
            name="🎰 Gambling Games",
            value=(
                "• **Blackjack** - Classic card game vs dealer (1x-1.5x payout)\n"
                "• **Roulette** - Bet on colors, numbers, or ranges (2x-36x payout)\n"
                "• **Multi-Number Roulette** - Bet on multiple numbers at once!\n"
                "• **Roulette Table** - View the visual betting table\n"
                "• **Coinflip Duel** - Challenge other players for coins\n"
                "• **Guess the Number** - High risk game with 500x payout!"
            ),
            inline=False
        )

        # Achievement Features (Everyone)
        embed.add_field(
            name="🏆 Achievement System",
            value=(
                "• **10 Unique Achievements** - Unlock achievements as you use the bot\n"
                "• **Progress Tracking** - View your progress toward each achievement\n"
                "• **Chat God** - Send 10,000 messages\n"
                "• **Voice Veteran** - Spend 50 hours in voice channels\n"
                "• **High Roller** - Win 50,000 coins from gambling\n"
                "• **Wealthy Elite** - Have 100,000 coins at once\n"
                "• **And More!** - Music, karaoke, daily streaks achievements"
            ),
            inline=False
        )

        # Leveling System (Everyone)
        embed.add_field(
            name="📊 Leveling System",
            value=(
                "• **Earn XP** - Get XP for messages (15-25 XP) and voice chat (10 XP/min)\n"
                "• **Level Up** - Progress through levels with increasing XP requirements\n"
                "• **Rank Cards** - Beautiful graphical rank cards with your avatar & stats\n"
                "• **XP Leaderboard** - Compete for the top spot in your server\n"
                "• **Milestone Rewards** - Earn bonus coins at levels 5, 10, 20, 50, 100!\n"
                "• **Level 10: 5,000 coins** - Plus other milestone bonuses"
            ),
            inline=False
        )

        # Reputation System (Everyone)
        embed.add_field(
            name="⭐ Reputation System",
            value=(
                "• **Give Rep** - Recognize helpful members with `/rep @user`\n"
                "• **Daily Limit** - One rep point per day to prevent spam\n"
                "• **Rep Leaderboard** - See who the most helpful members are\n"
                "• **Check Rep** - View anyone's reputation stats\n"
                "• **Social Recognition** - Build your server's community lore"
            ),
            inline=False
        )

        # Shop System (Everyone)
        embed.add_field(
            name="🛒 Server Shop",
            value=(
                "• **XP Boosters** - Double XP for 2h, 6h, or 24h\n"
                "• **Custom Roles** - Buy a custom colored role for 1 week or 1 month\n"
                "• **Browse & Buy** - Use `/shop` to see items, `/buy` to purchase\n"
                "• **Inventory** - Track your active items with `/inventory`\n"
                "• **Auto-Expiry** - Temporary items are automatically removed when expired"
            ),
            inline=False
        )

        # Daily Quests (Everyone)
        embed.add_field(
            name=" Daily Quest System",
            value=(
                "• **3 Daily Quests** - New quests every day at midnight UTC\n"
                "• **Quest Variety** - Gambling, music, chat, voice, and social quests\n"
                "• **Quest Keys** - Complete all 3 quests to earn a Quest Key\n"
                "• **Lootboxes** - Open lootboxes for coins and rare roles!\n"
                "• **Legendary Rewards** - Up to 50,000 coins and exclusive roles"
            ),
            inline=False
        )

        # Stock Market (Everyone)
        embed.add_field(
            name=" Community Stock Market",
            value=(
                "• **Invest in Members** - Buy shares in active server members\n"
                "• **Dynamic Prices** - Prices rise with messages, XP, and voice time\n"
                "• **Buy & Sell** - Use `/invest` and `/sell` to trade\n"
                "• **Portfolio Tracking** - View your holdings with `/portfolio`\n"
                "• **Profit from Activity** - Invest in active members and sell high!"
            ),
            inline=False
        )

        # Voice Channel Features (Everyone)
        embed.add_field(
            name="🔊 Voice Channel Tools",
            value=(
                "• **Join-to-Create** - Join a channel to get your own private VC\n"
                "• **VC Controls** - Rename, lock, set limits, kick/ban users\n"
                "• **Auto-Transfer** - Ownership transfers when owner leaves\n"
                "• **VC Signal** - Send private invites to friends with `/vcsignal`\n"
                "• **Auto-Delete** - Empty channels are automatically cleaned up"
            ),
            inline=False
        )

        # Games System (Everyone)
        embed.add_field(
            name="🎮 Games System",
            value=(
                "• **Trivia** - Test your knowledge with multiple categories\n"
                "• **Minesweeper** - Classic puzzle game in Discord\n"
                "• **Connect 4** - Challenge friends to a strategy game\n"
                "• **Tic Tac Toe** - Classic X's and O's\n"
                "• **Rock Paper Scissors** - Quick duels vs bot or players\n"
                "• **8-Ball** - Ask the magic 8-ball anything\n"
                "• **Dice Rolling** - Roll any combination of dice"
            ),
            inline=False
        )

        # Profile Cards (Everyone)
        embed.add_field(
            name="🎨 Profile Cards",
            value=(
                "• **Graphical Cards** - Beautiful profile cards with your stats\n"
                "• **Custom Colors** - Choose your accent color or use presets\n"
                "• **Stats Display** - Shows level, XP, coins, reputation\n"
                "• **Achievement Badges** - Display your earned badges"
            ),
            inline=False
        )

        # Reminders (Everyone)
        embed.add_field(
            name="⏰ Personal Reminders",
            value=(
                "• **DM Reminders** - Get reminded via DM when time is up\n"
                "• **Flexible Timing** - 1h, 30m, 1d, 1w, or combinations\n"
                "• **Repeating Reminders** - Daily or weekly repeat options\n"
                "• **Manage Reminders** - View, delete, or clear all reminders"
            ),
            inline=False
        )

        # Fun Features (Everyone)
        embed.add_field(
            name="🎭 Fun & Entertainment",
            value=(
                "• **Daily Quotes** - Inspirational quotes from movies, anime & famous people\n"
                "• **67 Command** - Unleash maximum cringe"
            ),
            inline=False
        )

        # Onboarding (Everyone)
        embed.add_field(
            name="🚀 Easy Onboarding",
            value=(
                "• **Interactive Start** - Use `/start` to learn all features\n"
                "• **Setup Wizard** - Admins use `/setup` for easy configuration\n"
                "• **Dashboard** - Quick overview with `/dashboard`\n"
                "• **Welcome Message** - Auto-welcome when bot joins a server"
            ),
            inline=False
        )

        # Staff-only features below
        perms = self.user.guild_permissions
        is_staff = perms.manage_messages or perms.moderate_members or perms.administrator

        # Ticket System (Staff)
        if is_staff:
            embed.add_field(
                name="🎫 Support Ticket System",
                value=(
                    "• **Button-Based Tickets** - Users click to open private support channels\n"
                    "• **Category Selection** - Support, Report, Appeal, or Other\n"
                    "• **Claim System** - Staff can claim tickets to handle them\n"
                    "• **Lock/Unlock** - Temporarily prevent user from typing\n"
                    "• **Transcripts** - Save ticket conversations to log channel\n"
                    "• **Safe Close** - Close with reopen option, delete confirmation"
                ),
                inline=False
            )

            embed.add_field(
                name="📺 Live Stream Alerts",
                value=(
                    "• **Twitch & YouTube** - Get alerts when streamers go live\n"
                    "• **Auto-Detection** - Bot checks every 5 minutes for new streams\n"
                    "• **Custom Channel** - Set which channel receives alerts\n"
                    "• **Role Pings** - Optionally ping a role when someone goes live\n"
                    "• **Rich Embeds** - Beautiful alerts with streamer info and links"
                ),
                inline=False
            )

            embed.add_field(
                name="📰 Auto News Feeds",
                value=(
                    "• **Reddit Integration** - Auto-post from any subreddit\n"
                    "• **RSS Support** - Subscribe to any RSS feed\n"
                    "• **Filter Options** - Choose hot, new, or top posts\n"
                    "• **Automatic Posts** - Bot fetches new content every 10 minutes\n"
                    "• **Rich Formatting** - Posts include titles, links, and thumbnails"
                ),
                inline=False
            )

            embed.add_field(
                name="🎉 Giveaways & Polls",
                value=(
                    "• **Button Giveaways** - One-click entry with live count\n"
                    "• **Timed Duration** - Auto-end after specified time\n"
                    "• **Multiple Winners** - Pick 1 or more winners\n"
                    "• **Role Requirements** - Require a role to enter\n"
                    "• **Reroll Winners** - Pick new winners anytime\n"
                    "• **Interactive Polls** - Button voting with live results"
                ),
                inline=False
            )

            embed.add_field(
                name="🏷️ Reaction Roles",
                value=(
                    "• **Button Panels** - Click to get/remove roles\n"
                    "• **Dropdown Menus** - Select roles from a dropdown\n"
                    "• **Single/Multi Mode** - Allow one or multiple roles\n"
                    "• **Custom Labels** - Set button text and descriptions\n"
                    "• **Emoji Support** - Add emojis to buttons"
                ),
                inline=False
            )

            embed.add_field(
                name="⚡ Custom Commands",
                value=(
                    "• **Keyword Triggers** - Auto-respond to specific words\n"
                    "• **Custom Prefix** - Set your own trigger prefix\n"
                    "• **Embed Responses** - Rich formatted responses\n"
                    "• **Variables** - Use {user}, {server}, {channel} placeholders"
                ),
                inline=False
            )

            embed.add_field(
                name="👋 Welcome & Goodbye Cards",
                value=(
                    "• **Visual Cards** - Beautiful image welcome/goodbye cards\n"
                    "• **Custom Backgrounds** - Set your own background image\n"
                    "• **DM Welcomes** - Optional DM message to new members\n"
                    "• **Auto Roles** - Automatically assign roles on join\n"
                    "• **Custom Messages** - Use {user}, {server}, {count} variables"
                ),
                inline=False
            )

            embed.add_field(
                name="🌍 Multilingual Support",
                value=(
                    "• **13 Languages** - EN, DA, DE, ES, FR, PT, NL, IT, PL, RU, JA, KO, ZH\n"
                    "• **Per-Server Language** - Each server picks their language\n"
                    "• **Preview Mode** - See translations before switching\n"
                    "• **Fallback System** - English fallback for missing translations"
                ),
                inline=False
            )

            embed.add_field(
                name="📝 Deep Logging",
                value=(
                    "• **Message Tracking** - Edits, deletions with content\n"
                    "• **Member Events** - Joins, leaves, bans, unbans\n"
                    "• **Role/Nick Changes** - Track all member updates\n"
                    "• **Voice Activity** - Join, leave, move, mute/deafen\n"
                    "• **Channel Updates** - Create, delete, modify channels"
                ),
                inline=False
            )

        # Coming Soon
        embed.add_field(
            name="🚀 Coming Soon",
            value=(
                "• AI Chat Features (OpenRouter integration)\n"
                "• Auto-moderation (word filters, spam protection)\n"
                "• Social media alerts (Twitter, Instagram)\n"
                "• And more!"
            ),
            inline=False
        )

        # Note about more features for staff
        if is_staff:
            embed.add_field(
                name="🔒 Staff Features",
                value="*You have access to additional commands. Browse the category pages to see moderation, admin, and owner tools.*",
                inline=False
            )

        embed.set_footer(text=f"Requested by {self.user} • Use buttons to navigate")

        return embed

    def _build_group_embed(self, group: dict) -> discord.Embed:
        """Build a command group embed (multiple categories combined)"""
        embed = discord.Embed(
            title=f"{group['emoji']} {group['name']}",
            description=f"**Page {self.current_page}/{self.total_pages}**",
            color=group['color']
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        total_commands = 0
        field_count = 0

        # Add commands from each category in the group
        for category in group['categories']:
            if category not in self.accessible_commands:
                continue

            commands_list = self.accessible_commands[category]
            if not commands_list:
                continue

            cat_info = CATEGORY_INFO.get(category, {"name": category.title(), "emoji": "📁"})

            # Format commands compactly - group them to avoid hitting 25 field limit
            # Show command name and brief description
            cmd_lines = []
            for cmd in commands_list:
                # Truncate description if too long
                desc = cmd['description']
                if len(desc) > 50:
                    desc = desc[:47] + "..."
                cmd_lines.append(f"**{cmd['name']}** - {desc}")

            # Split into chunks if too many commands (max ~1024 chars per field value)
            chunk_size = 6  # commands per field
            for i in range(0, len(cmd_lines), chunk_size):
                chunk = cmd_lines[i:i + chunk_size]
                field_name = f"{cat_info['emoji']} {cat_info['name']}" if i == 0 else f"{cat_info['name']} (cont.)"

                if field_count < 24:  # Leave room for footer info
                    embed.add_field(
                        name=field_name,
                        value="\n".join(chunk),
                        inline=False
                    )
                    field_count += 1

            total_commands += len(commands_list)

        # Show command count
        embed.set_footer(
            text=f"{total_commands} command(s) • Requested by {self.user} • Use buttons to navigate"
        )

        return embed

    def _build_category_embed(self, category: str) -> discord.Embed:
        """Build a command category embed (single category - legacy)"""
        cat_info = CATEGORY_INFO.get(category, {
            "name": category.title(),
            "emoji": "📁",
            "description": "Commands"
        })

        commands_list = self.accessible_commands.get(category, [])

        embed = discord.Embed(
            title=f"{cat_info['emoji']} {cat_info['name']}",
            description=f"**Page {self.current_page}/{self.total_pages}** - {cat_info['description']}",
            color=self._get_category_color(category)
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # List commands in this category
        for cmd in commands_list:
            # Add permission indicator
            if cmd["permission"]:
                perm_text = f"\n🔒 *Requires: {cmd['permission'].replace('_', ' ').title()}*"
            else:
                perm_text = ""

            embed.add_field(
                name=f"**{cmd['name']}**",
                value=f"{cmd['description']}\n📝 `{cmd['usage']}`{perm_text}",
                inline=False
            )

        # Show command count
        embed.set_footer(
            text=f"{len(commands_list)} command(s) • Requested by {self.user} • Use buttons to navigate"
        )

        return embed

    def _get_category_color(self, category: str) -> discord.Color:
        """Get the color for a category"""
        colors = {
            "general": discord.Color.blue(),
            "fun": discord.Color.gold(),
            "games": discord.Color.from_rgb(114, 137, 218),  # Discord blurple for games
            "profile": discord.Color.from_rgb(233, 30, 99),  # Pink for profile
            "reminders": discord.Color.from_rgb(0, 188, 212),  # Cyan for reminders
            "economy": discord.Color.from_rgb(255, 215, 0),  # Gold
            "gambling": discord.Color.purple(),
            "music": discord.Color.green(),
            "karaoke": discord.Color.magenta(),
            "achievements": discord.Color.from_rgb(255, 165, 0),  # Orange/Gold
            "leveling": discord.Color.from_rgb(88, 101, 242),  # Discord Blurple
            "reputation": discord.Color.gold(),  # Gold for reputation
            "shop": discord.Color.teal(),  # Teal for shop
            "quests": discord.Color.from_rgb(255, 193, 7),  # Amber for quests
            "stocks": discord.Color.from_rgb(0, 200, 83),  # Green for stocks
            "voicechannel": discord.Color.from_rgb(87, 242, 135),  # Discord green for VC
            "polls": discord.Color.from_rgb(63, 81, 181),  # Indigo for polls
            "giveaways": discord.Color.from_rgb(255, 152, 0),  # Orange for giveaways
            "reactionroles": discord.Color.from_rgb(156, 39, 176),  # Purple for reaction roles
            "customcommands": discord.Color.from_rgb(255, 235, 59),  # Yellow for custom commands
            "welcome": discord.Color.from_rgb(76, 175, 80),  # Green for welcome
            "goodbye": discord.Color.from_rgb(121, 85, 72),  # Brown for goodbye
            "autorole": discord.Color.from_rgb(103, 58, 183),  # Deep purple for autorole
            "language": discord.Color.from_rgb(0, 150, 136),  # Teal for language
            "moderation": discord.Color.orange(),
            "support": discord.Color.from_rgb(96, 125, 139),  # Blue grey for support
            "admin": discord.Color.red(),
            "livealerts": discord.Color.purple(),  # Purple for live alerts (Twitch)
            "autonews": discord.Color.from_rgb(255, 69, 0),  # Reddit orange
            "owner": discord.Color.dark_red()
        }
        return colors.get(category, discord.Color.blurple())

    def _build_credits_embed(self) -> discord.Embed:
        """Build the credits embed (Last Page)"""
        embed = discord.Embed(
            title="Credits",
            description=f"**Page {self.total_pages}/{self.total_pages}** - The Team Behind {config.BOT_NAME}",
            color=discord.Color.purple()
        )

        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        # Developer
        embed.add_field(
            name="Developer",
            value=(
                "**Fengus**\n"
                "Lead developer responsible for building and maintaining "
                f"all of {config.BOT_NAME}'s features and functionality."
            ),
            inline=False
        )

        # Owner/Overseer
        embed.add_field(
            name="Owner & Overseer",
            value=(
                "**Frederik \"NaCly\"**\n"
                "Owner of **Omika AI** and project overseer.\n"
                f"{config.BOT_NAME} is developed under the Omika AI umbrella."
            ),
            inline=False
        )

        # Project Info
        embed.add_field(
            name="About the Project",
            value=(
                f"**{config.BOT_NAME}** is a project developed under **Omika AI**.\n\n"
                "Named after the strongest sorcerer from Jujutsu Kaisen, "
                "this bot aims to provide powerful moderation, logging, "
                "and entertainment features for Discord servers."
            ),
            inline=False
        )

        # Special Thanks
        embed.add_field(
            name="Special Thanks",
            value=(
                "Thank you to everyone who uses and supports this bot!\n"
                "Your feedback helps make it better every day."
            ),
            inline=False
        )

        embed.set_footer(text=f"Requested by {self.user} • {config.BOT_NAME} v{config.BOT_VERSION}")

        return embed

    def update_buttons(self):
        """Update the dropdown menu with all available pages"""
        self.clear_items()

        # Build dropdown options
        options = [
            discord.SelectOption(
                label="About",
                description="Introduction and bot info",
                value="1",
                emoji="📖",
                default=(self.current_page == 1)
            ),
            discord.SelectOption(
                label="Features",
                description="Overview of bot features",
                value="2",
                emoji="✨",
                default=(self.current_page == 2)
            )
        ]

        # Add category group pages
        for i, group in enumerate(self.accessible_groups):
            page_num = i + 3
            options.append(
                discord.SelectOption(
                    label=group["name"],
                    description=f"{len([c for c in group['categories'] if c in self.accessible_commands])} categories",
                    value=str(page_num),
                    emoji=group["emoji"],
                    default=(self.current_page == page_num)
                )
            )

        # Add credits page
        options.append(
            discord.SelectOption(
                label="Credits",
                description="Credits and acknowledgments",
                value=str(self.total_pages),
                emoji="💝",
                default=(self.current_page == self.total_pages)
            )
        )

        # Create the select menu
        select = discord.ui.Select(
            placeholder=f"Page {self.current_page}/{self.total_pages} - Select a page...",
            options=options,
            custom_id="page_select"
        )
        select.callback = self.on_page_select
        self.add_item(select)

    async def on_page_select(self, interaction: discord.Interaction):
        """Handle page selection from dropdown"""
        selected_page = int(interaction.data["values"][0])
        self.current_page = selected_page
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    async def on_timeout(self):
        """Disable all buttons when the view times out"""
        for item in self.children:
            item.disabled = True


class Information(commands.Cog):
    """Cog for the information command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="information", description="Learn about the bot and see available commands")
    async def information(self, interaction: discord.Interaction):
        """
        Slash command that displays bot information and available commands
        Usage: /information
        Shows only commands the user has permission to use
        """
        # Log that someone used this command
        guild_name = interaction.guild.name if interaction.guild else None
        log_command(
            user=str(interaction.user),
            user_id=interaction.user.id,
            command="information",
            guild=guild_name
        )

        # Check if in a server (needed for permission checking)
        if not interaction.guild:
            await interaction.response.send_message(
                "This command works best in a server! Some features may be limited in DMs.",
                ephemeral=True
            )
            return

        try:
            # Create the paginated view
            view = InformationView(self.bot, interaction.user)
            view.update_buttons()

            # Send the first page
            embed = view.get_page_embed()
            await interaction.response.send_message(embed=embed, view=view)

            logger.info(f"Information command used by {interaction.user}")

        except Exception as e:
            logger.error(f"Failed to show information: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong while loading information.",
                ephemeral=True
            )


# Required setup function - Discord.py calls this to load the cog
async def setup(bot: commands.Bot):
    """Add the Information cog to the bot"""
    await bot.add_cog(Information(bot))
