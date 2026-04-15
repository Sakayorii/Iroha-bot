from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List

import discord
from discord import app_commands
from discord.ext import commands, tasks

from db import (
    create_poll,
    get_poll,
    vote_poll,
    get_poll_counts,
    list_due_polls,
    list_open_polls,
    delete_poll,
    get_guild_config,
)
from utils.guards import module_enabled
from utils.embed_utils import make_embed, progress_bar, Colors


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_options(raw: str) -> List[str]:
    return [opt.strip() for opt in raw.split("|") if opt.strip()]


class PollButton(discord.ui.Button):
    def __init__(self, poll_id: int, index: int, label: str) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=f"poll:{poll_id}:{index}")
        self.poll_id = poll_id
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        poll = await get_poll(self.poll_id)
        if not poll:
            await interaction.response.send_message("poll not found.", ephemeral=True)
            return
        await vote_poll(self.poll_id, interaction.user.id, self.index)
        options = json.loads(poll["options_json"])
        counts = await get_poll_counts(self.poll_id, len(options))
        embed = render_poll_embed(poll["question"], options, counts, poll["anonymous"])
        try:
            await interaction.message.edit(embed=embed, view=self.view)
        except Exception:
            logging.debug("failed to edit poll message", exc_info=True)
        opt_name = options[self.index] if self.index < len(options) else "?"
        await interaction.response.send_message(
            embed=make_embed(title="voted!", description=f"you voted for **{opt_name}**", color=Colors.SUCCESS),
            ephemeral=True,
        )


class PollView(discord.ui.View):
    def __init__(self, poll_id: int, options: List[str]) -> None:
        super().__init__(timeout=None)
        for idx, opt in enumerate(options):
            self.add_item(PollButton(poll_id, idx, opt))


def render_poll_embed(
    question: str, options: List[str], counts: List[int], anonymous: int, closed: bool = False,
) -> discord.Embed:
    total = sum(counts)
    color = Colors.NEUTRAL if closed else Colors.INFO
    title = f"\U0001f4ca {question}" if not closed else f"\U0001f4ca {question} [closed]"
    embed = make_embed(title=title, color=color)

    max_count = max(counts) if counts else 0
    lines = []
    for idx, opt in enumerate(options):
        count = counts[idx] if idx < len(counts) else 0
        bar = progress_bar(count, total, 12) if total > 0 else progress_bar(0, 1, 12)
        winner = " \U0001f3c6" if closed and count == max_count and count > 0 else ""
        lines.append(f"**{idx + 1}. {opt}**{winner}\n{bar} \u2014 {count} votes")
    embed.description = "\n\n".join(lines) if lines else "no options."

    footer = "anonymous poll" if anonymous else "poll"
    if closed:
        footer = f"poll closed \u2022 total: {total} votes"
    embed.set_footer(text=f"{footer} \u2022 iroha")
    return embed


class PollsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.poll_loop.start()

    async def cog_load(self) -> None:
        polls = await list_open_polls(_utcnow())
        for poll in polls:
            options = json.loads(poll["options_json"])
            view = PollView(poll["id"], options)
            self.bot.add_view(view)

    async def cog_unload(self) -> None:
        self.poll_loop.cancel()

    @tasks.loop(seconds=30)
    async def poll_loop(self) -> None:
        due = await list_due_polls(_utcnow())
        for poll in due:
            channel = self.bot.get_channel(int(poll["channel_id"]))
            if not isinstance(channel, discord.TextChannel):
                await delete_poll(poll["id"])
                continue
            try:
                message = await channel.fetch_message(int(poll["message_id"]))
            except Exception:
                await delete_poll(poll["id"])
                continue
            options = json.loads(poll["options_json"])
            counts = await get_poll_counts(poll["id"], len(options))
            embed = render_poll_embed(poll["question"], options, counts, poll["anonymous"], closed=True)
            await message.edit(embed=embed, view=None)
            await delete_poll(poll["id"])

    @app_commands.command(name="poll", description="Create a poll.")
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        options: str,
        duration_minutes: int | None = None,
        anonymous: bool = False,
    ) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "polls_enabled", interaction.user.id):
            await interaction.response.send_message("polls disabled.", ephemeral=True)
            return
        opts = _parse_options(options)
        if len(opts) < 2:
            await interaction.response.send_message("need at least 2 options, separated by `|`.", ephemeral=True)
            return
        if len(opts) > 5:
            await interaction.response.send_message("max 5 options.", ephemeral=True)
            return
        ends_at = None
        if duration_minutes and duration_minutes > 0:
            ends_at = (datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)).isoformat()
        embed = render_poll_embed(question, opts, [0] * len(opts), 1 if anonymous else 0)
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        poll_id = await create_poll(
            interaction.guild.id, interaction.channel_id, message.id,
            question, json.dumps(opts), 1 if anonymous else 0,
            ends_at, interaction.user.id,
        )
        view = PollView(poll_id, opts)
        await message.edit(view=view)
        self.bot.add_view(view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollsCog(bot))
