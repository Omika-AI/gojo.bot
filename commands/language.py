"""
Language Configuration - Set server language for bot responses

Commands:
- /language set - Set the server language
- /language list - List available languages
- /language current - View current language setting
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal

from utils.server_config_db import set_server_language, get_server_language
from utils.i18n import (
    get_supported_languages,
    is_supported,
    t,
    SUPPORTED_LANGUAGES
)
from utils.logger import logger


class Language(commands.Cog):
    """Language configuration commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    language_group = app_commands.Group(
        name="language",
        description="Configure server language"
    )

    @language_group.command(name="set", description="Set the server language")
    @app_commands.describe(language="The language to use")
    @app_commands.default_permissions(administrator=True)
    async def language_set(
        self,
        interaction: discord.Interaction,
        language: Literal["en", "da", "de", "es", "fr", "pt", "nl", "it", "pl", "ru", "ja", "ko", "zh"]
    ):
        """Set the server language"""
        if not is_supported(language):
            await interaction.response.send_message(
                t("config.language_unsupported", interaction.guild.id),
                ephemeral=True
            )
            return

        success, message = set_server_language(interaction.guild.id, language)

        if success:
            lang_name = SUPPORTED_LANGUAGES.get(language, language)

            embed = discord.Embed(
                title="Language Updated",
                description=t("config.language_set", interaction.guild.id, language=lang_name),
                color=discord.Color.green()
            )
            embed.add_field(name="Language Code", value=f"`{language}`", inline=True)
            embed.add_field(name="Language Name", value=lang_name, inline=True)
            embed.set_footer(text="Bot messages will now appear in this language where supported.")

            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Language set to '{language}' in {interaction.guild.name}")
        else:
            await interaction.response.send_message(message, ephemeral=True)

    @language_group.command(name="list", description="List all available languages")
    async def language_list(self, interaction: discord.Interaction):
        """List available languages"""
        languages = get_supported_languages()

        embed = discord.Embed(
            title="Available Languages",
            description="Use `/language set <code>` to change the server language.",
            color=discord.Color.blue()
        )

        # Group languages
        lang_list = []
        for code, name in languages.items():
            current = get_server_language(interaction.guild.id)
            marker = " (current)" if code == current else ""
            lang_list.append(f"`{code}` - {name}{marker}")

        embed.add_field(
            name="Languages",
            value="\n".join(lang_list),
            inline=False
        )

        embed.set_footer(text="More languages coming soon!")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @language_group.command(name="current", description="View the current server language")
    async def language_current(self, interaction: discord.Interaction):
        """View current language"""
        current = get_server_language(interaction.guild.id)
        lang_name = SUPPORTED_LANGUAGES.get(current, current)

        embed = discord.Embed(
            title="Current Language",
            color=discord.Color.blue()
        )
        embed.add_field(name="Language Code", value=f"`{current}`", inline=True)
        embed.add_field(name="Language Name", value=lang_name, inline=True)
        embed.set_footer(text="Use /language set to change this")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @language_group.command(name="preview", description="Preview how bot messages look in a language")
    @app_commands.describe(language="Language to preview")
    async def language_preview(
        self,
        interaction: discord.Interaction,
        language: Literal["en", "da", "de", "es", "fr", "pt", "nl", "it", "pl", "ru", "ja", "ko", "zh"]
    ):
        """Preview translations"""
        if not is_supported(language):
            await interaction.response.send_message("Language not supported!", ephemeral=True)
            return

        lang_name = SUPPORTED_LANGUAGES.get(language, language)

        embed = discord.Embed(
            title=f"Preview: {lang_name}",
            color=discord.Color.blue()
        )

        # Show sample translations
        samples = [
            ("common.yes", "Yes/No"),
            ("common.success", "Success message"),
            ("welcome.message", "Welcome message"),
            ("economy.balance", "Balance label"),
            ("leveling.level_up", "Level up"),
            ("games.you_win", "Win message"),
        ]

        for key, description in samples:
            translated = t(key, lang=language, server="Server", user="User")
            embed.add_field(name=description, value=translated, inline=True)

        embed.set_footer(text="Note: Not all messages may be translated yet")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Add the Language cog to the bot"""
    await bot.add_cog(Language(bot))
