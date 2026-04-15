from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from db import get_guild_config, update_guild_config
from utils.i18n import t
from utils.checks import is_moderator
from cogs.verification import VerifyView


PRESETS = {
    "small": {
        "ai_enabled": 0,
        "music_enabled": 0,
        "games_enabled": 0,
        "leveling_enabled": 1,
        "economy_enabled": 1,
        "tickets_enabled": 1,
        "roles_enabled": 1,
        "verify_enabled": 1,
        "giveaway_enabled": 1,
        "reminders_enabled": 1,
        "polls_enabled": 1,
        "logging_enabled": 1,
        "welcome_enabled": 1,
        "goodbye_enabled": 1,
        "boost_enabled": 1,
    },
    "medium": {
        "ai_enabled": 1,
        "music_enabled": 1,
        "games_enabled": 1,
        "leveling_enabled": 1,
        "economy_enabled": 1,
        "tickets_enabled": 1,
        "roles_enabled": 1,
        "verify_enabled": 1,
        "giveaway_enabled": 1,
        "reminders_enabled": 1,
        "polls_enabled": 1,
        "logging_enabled": 1,
        "welcome_enabled": 1,
        "goodbye_enabled": 1,
        "boost_enabled": 1,
    },
    "gaming": {
        "ai_enabled": 1,
        "music_enabled": 1,
        "games_enabled": 1,
        "leveling_enabled": 1,
        "economy_enabled": 1,
        "tickets_enabled": 1,
        "roles_enabled": 1,
        "verify_enabled": 1,
        "giveaway_enabled": 1,
        "reminders_enabled": 1,
        "polls_enabled": 1,
        "logging_enabled": 1,
        "welcome_enabled": 1,
        "goodbye_enabled": 1,
        "boost_enabled": 1,
    },
    "fanclub": {
        "ai_enabled": 1,
        "music_enabled": 1,
        "games_enabled": 1,
        "leveling_enabled": 1,
        "economy_enabled": 1,
        "tickets_enabled": 1,
        "roles_enabled": 1,
        "verify_enabled": 1,
        "giveaway_enabled": 1,
        "reminders_enabled": 1,
        "polls_enabled": 1,
        "logging_enabled": 1,
        "welcome_enabled": 1,
        "goodbye_enabled": 1,
        "boost_enabled": 1,
    },
}


class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _parse_channel_id(self, raw: str | None) -> int | None:
        if not raw:
            return None
        token = raw.strip()
        if token.startswith("<") and token.endswith(">"):
            token = "".join(ch for ch in token[1:-1] if ch.isdigit())
        if not token.isdigit():
            return None
        return int(token)

    async def _resolve_text_channel(self, guild: discord.Guild, raw: str | None) -> discord.TextChannel | None:
        channel_id = self._parse_channel_id(raw)
        if channel_id is None:
            return None
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        try:
            fetched = await guild.fetch_channel(channel_id)
        except Exception:
            return None
        if isinstance(fetched, discord.TextChannel):
            return fetched
        return None

    setup_group = app_commands.Group(name="setup", description="Server setup")

    @setup_group.command(name="preset", description="Apply a quick setup preset.")
    @app_commands.describe(preset="Choose a preset")
    @app_commands.choices(
        preset=[
            app_commands.Choice(name="Small Server", value="small"),
            app_commands.Choice(name="Medium Server", value="medium"),
            app_commands.Choice(name="Gaming Community", value="gaming"),
            app_commands.Choice(name="Fanclub", value="fanclub"),
        ]
    )
    async def preset(self, interaction: discord.Interaction, preset: app_commands.Choice[str]) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        locale = cfg.get("locale") or "en"
        if not await is_moderator(interaction.user):
            await interaction.response.send_message(t(locale, "no_permission"), ephemeral=True)
            return
        updates = PRESETS.get(preset.value, {})
        if not cfg.get("log_channel_id"):
            updates["log_channel_id"] = interaction.channel_id
        if not cfg.get("welcome_channel_id"):
            updates["welcome_channel_id"] = interaction.channel_id
        if not cfg.get("goodbye_channel_id"):
            updates["goodbye_channel_id"] = interaction.channel_id
        await update_guild_config(interaction.guild.id, **updates)
        await interaction.response.send_message(t(locale, "setup_done"), ephemeral=True)

    @setup_group.command(name="channels", description="Set log/welcome/goodbye/AI/music channels.")
    @app_commands.describe(
        log_channel="Log channel",
        welcome_channel="Welcome channel",
        goodbye_channel="Goodbye channel",
        ai_channel="AI channel",
        music_channel="Music channel",
        log_channel_id="Log channel ID",
        welcome_channel_id="Welcome channel ID",
        goodbye_channel_id="Goodbye channel ID",
        ai_channel_id="AI channel ID",
        music_channel_id="Music channel ID",
    )
    async def channels(
        self,
        interaction: discord.Interaction,
        log_channel: discord.TextChannel | None = None,
        welcome_channel: discord.TextChannel | None = None,
        goodbye_channel: discord.TextChannel | None = None,
        ai_channel: discord.TextChannel | None = None,
        music_channel: discord.TextChannel | None = None,
        log_channel_id: str | None = None,
        welcome_channel_id: str | None = None,
        goodbye_channel_id: str | None = None,
        ai_channel_id: str | None = None,
        music_channel_id: str | None = None,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        locale = cfg.get("locale") or "en"
        if not await is_moderator(interaction.user):
            await interaction.response.send_message(t(locale, "no_permission"), ephemeral=True)
            return
        resolved_log_channel = log_channel or await self._resolve_text_channel(interaction.guild, log_channel_id)
        resolved_welcome_channel = welcome_channel or await self._resolve_text_channel(interaction.guild, welcome_channel_id)
        resolved_goodbye_channel = goodbye_channel or await self._resolve_text_channel(interaction.guild, goodbye_channel_id)
        resolved_ai_channel = ai_channel or await self._resolve_text_channel(interaction.guild, ai_channel_id)
        resolved_music_channel = music_channel or await self._resolve_text_channel(interaction.guild, music_channel_id)
        invalid_fields: list[str] = []
        if log_channel_id and log_channel is None and resolved_log_channel is None:
            invalid_fields.append("log_channel_id")
        if welcome_channel_id and welcome_channel is None and resolved_welcome_channel is None:
            invalid_fields.append("welcome_channel_id")
        if goodbye_channel_id and goodbye_channel is None and resolved_goodbye_channel is None:
            invalid_fields.append("goodbye_channel_id")
        if ai_channel_id and ai_channel is None and resolved_ai_channel is None:
            invalid_fields.append("ai_channel_id")
        if music_channel_id and music_channel is None and resolved_music_channel is None:
            invalid_fields.append("music_channel_id")
        if invalid_fields:
            details = ", ".join(invalid_fields)
            await interaction.response.send_message(
                f"Invalid channel ID in: {details}. Use a valid text channel ID or channel mention.",
                ephemeral=True,
            )
            return
        updates = {}
        if resolved_log_channel:
            updates["log_channel_id"] = resolved_log_channel.id
        if resolved_welcome_channel:
            updates["welcome_channel_id"] = resolved_welcome_channel.id
        if resolved_goodbye_channel:
            updates["goodbye_channel_id"] = resolved_goodbye_channel.id
        if resolved_ai_channel:
            updates["ai_channel_id"] = resolved_ai_channel.id
        if resolved_music_channel:
            updates["music_channel_id"] = resolved_music_channel.id
        if updates:
            await update_guild_config(interaction.guild.id, **updates)
        await interaction.response.send_message(t(locale, "setup_channels_done"), ephemeral=True)

    @setup_group.command(name="verify", description="Set up the verification channel and role.")
    @app_commands.describe(
        role="Role to grant after verification",
        channel="Verification channel",
        message="Custom verification message",
    )
    async def verify(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        channel: discord.TextChannel | None = None,
        message: str | None = None,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        locale = cfg.get("locale") or "en"
        if not await is_moderator(interaction.user):
            await interaction.response.send_message(t(locale, "no_permission"), ephemeral=True)
            return
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message("Invalid channel.", ephemeral=True)
            return
        text = message or "Press Verify to start. You will receive a 6 digit code in DM and complete with /verify."
        embed = discord.Embed(title="Verification", description=text, color=discord.Color.red())
        view = VerifyView(self.bot)
        msg = await target_channel.send(embed=embed, view=view)
        await update_guild_config(
            interaction.guild.id,
            verify_channel_id=target_channel.id,
            verify_role_id=role.id,
            verify_message_id=msg.id,
            verify_enabled=1,
        )
        await interaction.response.send_message("Verification setup complete.", ephemeral=True)

    @setup_group.command(name="giveaway", description="Set the default giveaway channel.")
    @app_commands.describe(channel="Giveaway channel")
    async def giveaway(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        locale = cfg.get("locale") or "en"
        if not await is_moderator(interaction.user):
            await interaction.response.send_message(t(locale, "no_permission"), ephemeral=True)
            return
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message("Invalid channel.", ephemeral=True)
            return
        await update_guild_config(interaction.guild.id, giveaway_channel_id=target_channel.id)
        await interaction.response.send_message("Giveaway channel updated.", ephemeral=True)

    @setup_group.command(name="language", description="Set the server language.")
    @app_commands.choices(
        language=[
            app_commands.Choice(name="English", value="en"),
        ]
    )
    async def language(self, interaction: discord.Interaction, language: app_commands.Choice[str]) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not await is_moderator(interaction.user):
            await interaction.response.send_message(t("en", "no_permission"), ephemeral=True)
            return
        await update_guild_config(interaction.guild.id, locale=language.value)
        await interaction.response.send_message(t(language.value, "setup_language_done"), ephemeral=True)

    @setup_group.command(name="summary", description="Show current setup summary.")
    async def summary(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        embed = discord.Embed(title="Setup Summary", color=discord.Color.red())
        embed.add_field(name="Locale", value=cfg.get("locale") or "en", inline=True)
        embed.add_field(name="AI", value="On" if cfg.get("ai_enabled") else "Off", inline=True)
        embed.add_field(name="Music", value="On" if cfg.get("music_enabled") else "Off", inline=True)
        embed.add_field(name="Games", value="On" if cfg.get("games_enabled") else "Off", inline=True)
        embed.add_field(name="Leveling", value="On" if cfg.get("leveling_enabled") else "Off", inline=True)
        embed.add_field(name="Economy", value="On" if cfg.get("economy_enabled") else "Off", inline=True)
        embed.add_field(name="Tickets", value="On" if cfg.get("tickets_enabled") else "Off", inline=True)
        embed.add_field(name="Roles", value="On" if cfg.get("roles_enabled") else "Off", inline=True)
        embed.add_field(name="Verification", value="On" if cfg.get("verify_enabled") else "Off", inline=True)
        embed.add_field(name="Giveaway", value="On" if cfg.get("giveaway_enabled") else "Off", inline=True)
        embed.add_field(name="Reminders", value="On" if cfg.get("reminders_enabled") else "Off", inline=True)
        embed.add_field(name="Polls", value="On" if cfg.get("polls_enabled") else "Off", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @setup_group.command(name="modrole", description="Set the moderator role.")
    async def modrole(self, interaction: discord.Interaction, role: discord.Role | None = None) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        locale = cfg.get("locale") or "en"
        if not await is_moderator(interaction.user):
            await interaction.response.send_message(t(locale, "no_permission"), ephemeral=True)
            return
        await update_guild_config(interaction.guild.id, mod_role_id=role.id if role else None)
        await interaction.response.send_message("Moderator role updated.", ephemeral=True)

    @setup_group.command(name="toggle", description="Enable or disable a module.")
    @app_commands.choices(
        module=[
            app_commands.Choice(name="AI", value="ai_enabled"),
            app_commands.Choice(name="Music", value="music_enabled"),
            app_commands.Choice(name="Games", value="games_enabled"),
            app_commands.Choice(name="Leveling", value="leveling_enabled"),
            app_commands.Choice(name="Economy", value="economy_enabled"),
            app_commands.Choice(name="Tickets", value="tickets_enabled"),
            app_commands.Choice(name="Roles", value="roles_enabled"),
            app_commands.Choice(name="Verification", value="verify_enabled"),
            app_commands.Choice(name="Giveaway", value="giveaway_enabled"),
            app_commands.Choice(name="Reminders", value="reminders_enabled"),
            app_commands.Choice(name="Polls", value="polls_enabled"),
            app_commands.Choice(name="Logging", value="logging_enabled"),
            app_commands.Choice(name="Welcome", value="welcome_enabled"),
            app_commands.Choice(name="Goodbye", value="goodbye_enabled"),
            app_commands.Choice(name="Boost", value="boost_enabled"),
            app_commands.Choice(name="Anti-Spam", value="anti_spam_enabled"),
            app_commands.Choice(name="Anti-Raid", value="anti_raid_enabled"),
            app_commands.Choice(name="Anti-Invite", value="anti_invite_enabled"),
            app_commands.Choice(name="Anti-Link", value="anti_link_enabled"),
            app_commands.Choice(name="Anti-NSFW", value="anti_nsfw_enabled"),
        ]
    )
    async def toggle(self, interaction: discord.Interaction, module: app_commands.Choice[str], enabled: bool) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        locale = cfg.get("locale") or "en"
        if not await is_moderator(interaction.user):
            await interaction.response.send_message(t(locale, "no_permission"), ephemeral=True)
            return
        await update_guild_config(interaction.guild.id, **{module.value: 1 if enabled else 0})
        await interaction.response.send_message(f"{module.name} set to {enabled}.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetupCog(bot))
