from __future__ import annotations

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from db import (
    get_guild_config,
    create_giveaway,
    get_giveaway,
    get_giveaway_by_message,
    list_due_giveaways,
    list_open_giveaways,
    add_giveaway_entry,
    list_giveaway_entries,
    close_giveaway,
    remove_giveaway_entry,
)
from utils.time_utils import parse_duration
from utils.checks import is_moderator
from utils.guards import module_enabled
from utils.embed_utils import make_embed, Colors


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _timestamp(dt: datetime) -> str:
    return f"<t:{int(dt.timestamp())}:R>"


def _timestamp_full(dt: datetime) -> str:
    return f"<t:{int(dt.timestamp())}:F>"


def _build_embed(giveaway: dict, entries: int, winners: Optional[List[int]] = None) -> discord.Embed:
    prize = giveaway.get("prize") or "prize"
    ended = giveaway.get("ended_at")

    if ended:
        embed = make_embed(title="\U0001f389 giveaway ended", description=f"**{prize}**", color=Colors.NEUTRAL)
    else:
        embed = make_embed(title="\U0001f389 giveaway", description=f"**{prize}**", color=Colors.SPECIAL)

    embed.add_field(name="winners", value=str(giveaway.get("winner_count") or 1), inline=True)
    embed.add_field(name="entries", value=str(entries), inline=True)

    ends_at = giveaway.get("ends_at")
    if ended:
        try:
            embed.add_field(name="ended", value=_timestamp_full(_parse_iso(ended)), inline=True)
        except Exception:
            embed.add_field(name="ended", value="ended", inline=True)
    else:
        try:
            end_time = _parse_iso(ends_at) if ends_at else datetime.now(timezone.utc)
            embed.add_field(name="ends", value=_timestamp(end_time), inline=True)
        except Exception:
            embed.add_field(name="ends", value="soon", inline=True)

    if winners is not None:
        if winners:
            mentions = ", ".join([f"\U0001f3c6 <@{w}>" for w in winners])
            embed.add_field(name="winners", value=mentions, inline=False)
        else:
            embed.add_field(name="winners", value="no valid entries.", inline=False)

    giveaway_id = giveaway.get("id")
    if giveaway_id:
        embed.set_footer(text=f"id: {giveaway_id} \u2022 iroha")
    return embed


class GiveawayJoinView(discord.ui.View):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="join", style=discord.ButtonStyle.success, emoji="\U0001f389", custom_id="giveaway_join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        giveaway = await get_giveaway_by_message(interaction.message.id)
        if not giveaway:
            await interaction.response.send_message("giveaway not found.", ephemeral=True)
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "giveaway_enabled", interaction.user.id):
            await interaction.response.send_message("giveaway module disabled.", ephemeral=True)
            return
        if giveaway.get("ended_at"):
            await interaction.response.send_message("already ended.", ephemeral=True)
            return
        try:
            end_time = _parse_iso(giveaway.get("ends_at"))
        except Exception:
            end_time = datetime.now(timezone.utc)
        if datetime.now(timezone.utc) >= end_time:
            await interaction.response.send_message("already ended.", ephemeral=True)
            return
        added = await add_giveaway_entry(giveaway["id"], interaction.user.id)
        entries = await list_giveaway_entries(giveaway["id"])
        try:
            embed = _build_embed(giveaway, len(entries))
            await interaction.message.edit(embed=embed, view=self)
        except Exception:
            logging.debug("failed to update giveaway embed on join", exc_info=True)
        if added:
            await interaction.response.send_message(
                embed=make_embed(title="joined!", description="\U0001f389 you're in. good luck!", color=Colors.SUCCESS),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message("already joined.", ephemeral=True)

    @discord.ui.button(label="leave", style=discord.ButtonStyle.danger, emoji="\U0001f6aa", custom_id="giveaway_leave")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        giveaway = await get_giveaway_by_message(interaction.message.id)
        if not giveaway:
            await interaction.response.send_message("giveaway not found.", ephemeral=True)
            return
        if giveaway.get("ended_at"):
            await interaction.response.send_message("already ended.", ephemeral=True)
            return
        removed = await remove_giveaway_entry(giveaway["id"], interaction.user.id)
        entries = await list_giveaway_entries(giveaway["id"])
        try:
            embed = _build_embed(giveaway, len(entries))
            await interaction.message.edit(embed=embed, view=self)
        except Exception:
            logging.debug("failed to update giveaway embed on leave", exc_info=True)
        if removed:
            await interaction.response.send_message(
                embed=make_embed(title="left", description="you're out.", color=Colors.NEUTRAL),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message("you weren't in this giveaway.", ephemeral=True)


class GiveawayCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.check_loop.start()

    async def cog_load(self) -> None:
        self.bot.add_view(GiveawayJoinView(self.bot))

    async def cog_unload(self) -> None:
        self.check_loop.cancel()

    @tasks.loop(seconds=30)
    async def check_loop(self) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        due = await list_due_giveaways(now_iso)
        for giveaway in due:
            await self._end_giveaway(giveaway)

    async def _end_giveaway(self, giveaway: dict) -> None:
        guild = self.bot.get_guild(int(giveaway["guild_id"]))
        if not guild:
            await close_giveaway(giveaway["id"], [], datetime.now(timezone.utc).isoformat())
            return
        channel = guild.get_channel(int(giveaway["channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            await close_giveaway(giveaway["id"], [], datetime.now(timezone.utc).isoformat())
            return
        try:
            message = await channel.fetch_message(int(giveaway["message_id"]))
        except Exception:
            message = None
        entries = await list_giveaway_entries(giveaway["id"])
        winners: List[int] = []
        if entries:
            winner_count = int(giveaway.get("winner_count") or 1)
            winners = random.sample(entries, k=min(winner_count, len(entries)))
        ended_at = datetime.now(timezone.utc).isoformat()
        await close_giveaway(giveaway["id"], winners, ended_at)
        giveaway["ended_at"] = ended_at
        embed = _build_embed(giveaway, len(entries), winners)
        if message:
            try:
                await message.edit(embed=embed, view=None)
            except Exception:
                logging.debug("failed to edit giveaway end message", exc_info=True)
        prize = giveaway.get("prize") or "prize"
        if winners:
            mentions = ", ".join([f"<@{w}>" for w in winners])
            win_embed = make_embed(
                title="\U0001f3c6 giveaway ended!",
                description=f"**{prize}**\n\nwinners: {mentions}",
                color=Colors.SPECIAL,
            )
            if guild.icon:
                win_embed.set_thumbnail(url=guild.icon.url)
            await channel.send(embed=win_embed)
        else:
            await channel.send(embed=make_embed(title="giveaway ended", description="no valid entries.", color=Colors.NEUTRAL))

    giveaway_group = app_commands.Group(name="giveaway", description="Giveaway commands")

    @giveaway_group.command(name="create", description="Create a giveaway.")
    async def create(
        self,
        interaction: discord.Interaction,
        duration: str,
        prize: str,
        winners: int,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "giveaway_enabled", interaction.user.id):
            await interaction.response.send_message("giveaway module disabled.", ephemeral=True)
            return
        if not await is_moderator(interaction.user):
            await interaction.response.send_message("no permission.", ephemeral=True)
            return
        try:
            seconds = parse_duration(duration)
        except Exception:
            await interaction.response.send_message("invalid duration.", ephemeral=True)
            return
        if winners <= 0 or winners > 50:
            await interaction.response.send_message("winner count must be 1-50.", ephemeral=True)
            return
        target_channel = channel
        if not target_channel:
            default_channel_id = cfg.get("giveaway_channel_id")
            if default_channel_id:
                target_channel = interaction.guild.get_channel(int(default_channel_id))
        if not isinstance(target_channel, discord.TextChannel):
            target_channel = interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message("no valid channel.", ephemeral=True)
            return
        ends_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        giveaway_data = {
            "prize": prize, "winner_count": winners,
            "ends_at": ends_at.isoformat(), "ended_at": None, "id": None,
        }
        embed = _build_embed(giveaway_data, 0)
        await interaction.response.send_message(
            embed=make_embed(title="created", description=f"giveaway for **{prize}** in {target_channel.mention}", color=Colors.SUCCESS),
            ephemeral=True,
        )
        view = GiveawayJoinView(self.bot)
        message = await target_channel.send(embed=embed, view=view)
        giveaway_id = await create_giveaway(
            interaction.guild.id, target_channel.id, message.id,
            prize, winners, ends_at.isoformat(), interaction.user.id,
        )
        giveaway_data["id"] = giveaway_id
        giveaway_data["guild_id"] = interaction.guild.id
        giveaway_data["channel_id"] = target_channel.id
        giveaway_data["message_id"] = message.id
        embed = _build_embed(giveaway_data, 0)
        try:
            await message.edit(embed=embed, view=view)
        except Exception:
            logging.debug("failed to edit giveaway create message", exc_info=True)

    @giveaway_group.command(name="end", description="End a giveaway early.")
    async def end(self, interaction: discord.Interaction, giveaway_id: int) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "giveaway_enabled", interaction.user.id):
            await interaction.response.send_message("giveaway module disabled.", ephemeral=True)
            return
        if not await is_moderator(interaction.user):
            await interaction.response.send_message("no permission.", ephemeral=True)
            return
        giveaway = await get_giveaway(giveaway_id)
        if not giveaway:
            await interaction.response.send_message("not found.", ephemeral=True)
            return
        if giveaway.get("ended_at"):
            await interaction.response.send_message("already ended.", ephemeral=True)
            return
        await self._end_giveaway(giveaway)
        await interaction.response.send_message(
            embed=make_embed(title="ended", description=f"giveaway #{giveaway_id} ended.", color=Colors.INFO),
            ephemeral=True,
        )

    @giveaway_group.command(name="reroll", description="Reroll winners for a giveaway.")
    async def reroll(self, interaction: discord.Interaction, giveaway_id: int, winners: Optional[int] = None) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "giveaway_enabled", interaction.user.id):
            await interaction.response.send_message("giveaway module disabled.", ephemeral=True)
            return
        if not await is_moderator(interaction.user):
            await interaction.response.send_message("no permission.", ephemeral=True)
            return
        giveaway = await get_giveaway(giveaway_id)
        if not giveaway:
            await interaction.response.send_message("not found.", ephemeral=True)
            return
        if not giveaway.get("ended_at"):
            await interaction.response.send_message("not ended yet. use /giveaway end first.", ephemeral=True)
            return
        entries = await list_giveaway_entries(giveaway_id)
        if not entries:
            await interaction.response.send_message("no entries.", ephemeral=True)
            return
        winner_count = winners if winners is not None else int(giveaway.get("winner_count") or 1)
        if winner_count <= 0:
            await interaction.response.send_message("winner count must be > 0.", ephemeral=True)
            return
        winners_list = random.sample(entries, k=min(winner_count, len(entries)))
        ended_at = datetime.now(timezone.utc).isoformat()
        await close_giveaway(giveaway_id, winners_list, ended_at)
        giveaway["ended_at"] = ended_at
        channel = interaction.guild.get_channel(int(giveaway["channel_id"]))
        if isinstance(channel, discord.TextChannel):
            try:
                message = await channel.fetch_message(int(giveaway["message_id"]))
            except Exception:
                message = None
            embed = _build_embed(giveaway, len(entries), winners_list)
            if message:
                try:
                    await message.edit(embed=embed, view=None)
                except Exception:
                    logging.debug("failed to edit giveaway reroll message", exc_info=True)
            mentions = ", ".join([f"<@{w}>" for w in winners_list])
            await channel.send(embed=make_embed(
                title="\U0001f504 rerolled!",
                description=f"new winners: {mentions}",
                color=Colors.SPECIAL,
            ))
        await interaction.response.send_message(
            embed=make_embed(title="rerolled", description=f"giveaway #{giveaway_id} rerolled.", color=Colors.SUCCESS),
            ephemeral=True,
        )

    @giveaway_group.command(name="list", description="List open giveaways.")
    async def list_open(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "giveaway_enabled", interaction.user.id):
            await interaction.response.send_message("giveaway module disabled.", ephemeral=True)
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        open_giveaways = await list_open_giveaways(now_iso)
        if not open_giveaways:
            await interaction.response.send_message(
                embed=make_embed(title="giveaways", description="none active.", color=Colors.NEUTRAL),
                ephemeral=True,
            )
            return
        lines = []
        for g in open_giveaways[:10]:
            try:
                ends_text = _timestamp(_parse_iso(g["ends_at"]))
            except Exception:
                ends_text = "soon"
            lines.append(f"`#{g['id']}` **{g['prize']}** \u2014 ends {ends_text}")
        await interaction.response.send_message(
            embed=make_embed(title="active giveaways", description="\n".join(lines), color=Colors.SPECIAL),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GiveawayCog(bot))
