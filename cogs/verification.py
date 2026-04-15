from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import VERIFY_CODE_TTL_MINUTES
from db import get_guild_config, set_verify_code, get_verify_code, delete_verify_code, delete_expired_verify_codes
from utils.guards import module_enabled


def _build_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def _expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=VERIFY_CODE_TTL_MINUTES)).isoformat()


async def _send_code(member: discord.Member, guild_id: int) -> str:
    code = _build_code()
    expires_at = _expires_at()
    await set_verify_code(guild_id, member.id, code, expires_at)
    return code


async def _check_verify_preconditions(
    interaction: discord.Interaction,
) -> Optional[discord.Role]:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return None
    cfg = await get_guild_config(interaction.guild.id)
    if not module_enabled(cfg, "verify_enabled", interaction.user.id):
        await interaction.response.send_message("Verification is disabled.", ephemeral=True)
        return None
    role_id = cfg.get("verify_role_id")
    if not role_id:
        await interaction.response.send_message("Verification is not configured.", ephemeral=True)
        return None
    role = interaction.guild.get_role(int(role_id))
    if role and role in interaction.user.roles:
        await interaction.response.send_message("You are already verified.", ephemeral=True)
        return None
    return role


class VerifyView(discord.ui.View):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.success, emoji="✅", custom_id="verify_start")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        role = await _check_verify_preconditions(interaction)
        if role is None:
            return
        code = await _send_code(interaction.user, interaction.guild.id)
        try:
            await interaction.user.send(
                f"Your verification code is {code}. It expires in {VERIFY_CODE_TTL_MINUTES} minutes. Use /verify in the server."
            )
            await interaction.response.send_message("Code sent in DM. Use /verify to finish.", ephemeral=True)
        except Exception:
            await interaction.response.send_message("I could not DM you. Please enable DMs and press Verify again.", ephemeral=True)


class VerificationCog(commands.Cog):
    _max_attempts: int = 5
    _attempt_window: float = 300.0

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._attempts: dict[tuple[int, int], list[float]] = {}
        self.cleanup_loop.start()

    async def cog_load(self) -> None:
        self.bot.add_view(VerifyView(self.bot))

    async def cog_unload(self) -> None:
        self.cleanup_loop.cancel()

    @tasks.loop(minutes=2)
    async def cleanup_loop(self) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        await delete_expired_verify_codes(now_iso)

    @app_commands.command(name="verify", description="Complete verification with a 6 digit code.")
    async def verify(self, interaction: discord.Interaction, code: str) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        code = code.strip()
        if not code.isdigit() or len(code) != 6:
            await interaction.response.send_message("Code must be 6 digits.", ephemeral=True)
            return
        role = await _check_verify_preconditions(interaction)
        if role is None:
            return
        record = await get_verify_code(interaction.guild.id, interaction.user.id)
        if not record:
            await interaction.response.send_message("No active code. Press Verify to get a new code.", ephemeral=True)
            return
        try:
            expires_at = datetime.fromisoformat(record["expires_at"])
        except Exception:
            expires_at = datetime.now(timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            await delete_verify_code(interaction.guild.id, interaction.user.id)
            await interaction.response.send_message("Your code expired. Press Verify to get a new code.", ephemeral=True)
            return
        key = (interaction.guild.id, interaction.user.id)
        now = time.monotonic()
        history = self._attempts.setdefault(key, [])
        history[:] = [t for t in history if now - t < self._attempt_window]
        if len(history) >= self._max_attempts:
            await interaction.response.send_message(
                "Too many attempts. Please wait a few minutes before trying again.", ephemeral=True
            )
            return
        if record.get("code") != code.strip():
            history.append(now)
            await interaction.response.send_message("Invalid code.", ephemeral=True)
            return
        try:
            if role:
                await interaction.user.add_roles(role, reason="Verification")
        except Exception:
            await interaction.response.send_message("Failed to assign role. Contact a moderator.", ephemeral=True)
            return
        await delete_verify_code(interaction.guild.id, interaction.user.id)
        self._attempts.pop(key, None)
        await interaction.response.send_message("Verification completed. Welcome.", ephemeral=True)

    @app_commands.command(name="verify_resend", description="Send a new verification code.")
    async def verify_resend(self, interaction: discord.Interaction) -> None:
        role = await _check_verify_preconditions(interaction)
        if role is None:
            return
        code = await _send_code(interaction.user, interaction.guild.id)
        try:
            await interaction.user.send(
                f"Your verification code is {code}. It expires in {VERIFY_CODE_TTL_MINUTES} minutes. Use /verify in the server."
            )
            await interaction.response.send_message("Code sent in DM.", ephemeral=True)
        except Exception:
            await interaction.response.send_message("I could not DM you. Please enable DMs and try again.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VerificationCog(bot))
