from __future__ import annotations

import random
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import FISH_REWARD, POKEMON_REWARD, DAILY_TASK_MESSAGES, DAILY_TASK_VOICE_MINUTES, DAILY_TASK_GAMES
from db import (
    add_inventory_item,
    add_pokemon,
    update_balance,
    get_guild_config,
    update_daily_progress,
    get_daily_tasks,
    upsert_daily_task,
)
from utils.guards import bot_ratio_exceeded, module_enabled
from utils.embed_utils import make_embed, Colors

FISH_ITEMS = {
    "Tiny Fish": "\U0001f41f",
    "Golden Fish": "\U0001f31f",
    "Old Boot": "\U0001f462",
    "Mystic Koi": "\U0001f420",
    "Iroha Bass": "\U0001f3b8",
}
POKEMON_LIST = ["Pikachu", "Eevee", "Bulbasaur", "Charmander", "Squirtle", "Jigglypuff"]
POKEMON_EMOJIS = {
    "Pikachu": "\u26a1", "Eevee": "\U0001f43e", "Bulbasaur": "\U0001f331",
    "Charmander": "\U0001f525", "Squirtle": "\U0001f4a7", "Jigglypuff": "\U0001f3b5",
}
TRIVIA = [
    ("What command lets you chat with Iroha?", "/ai"),
    ("What does 'ngl' stand for?", "not gonna lie"),
    ("What does 'tbh' mean?", "to be honest"),
]
TYPING_PHRASES = [
    "iroha is typing...",
    "bet u can't type faster than me",
    "ez game ez life",
]


class PlayAgainView(discord.ui.View):
    def __init__(self, game: str, cog: GamesCog, guild_id: int, user_id: int) -> None:
        super().__init__(timeout=30)
        self.game = game
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("not ur game.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="play again", style=discord.ButtonStyle.primary, emoji="\U0001f504")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        button.disabled = True
        await interaction.response.edit_message(view=self)
        if self.game == "fish":
            await self.cog._do_fish(interaction)
        elif self.game == "pokemon":
            await self.cog._do_pokemon(interaction)


class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _ensure_daily_tasks(self, guild_id: int, user_id: int) -> None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tasks = await get_daily_tasks(guild_id, user_id, date)
        if tasks:
            return
        await upsert_daily_task(guild_id, user_id, date, "messages", DAILY_TASK_MESSAGES, 0, 0)
        await upsert_daily_task(guild_id, user_id, date, "voice_minutes", DAILY_TASK_VOICE_MINUTES, 0, 0)
        await upsert_daily_task(guild_id, user_id, date, "games", DAILY_TASK_GAMES, 0, 0)

    async def _module_ok(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "games_enabled", interaction.user.id):
            await interaction.response.send_message("games disabled.", ephemeral=True)
            return False
        if bot_ratio_exceeded(interaction.guild, cfg, interaction.user.id):
            await interaction.response.send_message("games disabled (bot ratio).", ephemeral=True)
            return False
        return True

    async def _do_fish(self, interaction: discord.Interaction) -> None:
        item = random.choice(list(FISH_ITEMS.keys()))
        emoji = FISH_ITEMS[item]
        await add_inventory_item(interaction.guild.id, interaction.user.id, item, 1)
        await update_balance(interaction.guild.id, interaction.user.id, FISH_REWARD)
        await self._ensure_daily_tasks(interaction.guild.id, interaction.user.id)
        await update_daily_progress(interaction.guild.id, interaction.user.id, datetime.now(timezone.utc).strftime("%Y-%m-%d"), "games", 1)
        color = Colors.SPECIAL if item in ("Golden Fish", "Mystic Koi", "Iroha Bass") else Colors.SUCCESS
        embed = make_embed(
            title=f"{emoji} caught!",
            description=f"**{item}**\n+{FISH_REWARD} coins",
            color=color,
        )
        view = PlayAgainView("fish", self, interaction.guild.id, interaction.user.id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def _do_pokemon(self, interaction: discord.Interaction) -> None:
        poke = random.choice(POKEMON_LIST)
        emoji = POKEMON_EMOJIS.get(poke, "\U0001f4a0")
        await add_pokemon(interaction.guild.id, interaction.user.id, poke, 1)
        await update_balance(interaction.guild.id, interaction.user.id, POKEMON_REWARD)
        await self._ensure_daily_tasks(interaction.guild.id, interaction.user.id)
        await update_daily_progress(interaction.guild.id, interaction.user.id, datetime.now(timezone.utc).strftime("%Y-%m-%d"), "games", 1)
        embed = make_embed(
            title=f"{emoji} wild {poke} appeared!",
            description=f"caught **{poke}**!\n+{POKEMON_REWARD} coins",
            color=Colors.SPECIAL,
        )
        view = PlayAgainView("pokemon", self, interaction.guild.id, interaction.user.id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="fish", description="Go fishing.")
    @app_commands.checks.cooldown(1, 15.0)
    async def fish(self, interaction: discord.Interaction) -> None:
        if not await self._module_ok(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await self._do_fish(interaction)

    @app_commands.command(name="pokemon", description="Catch a random Pokémon.")
    @app_commands.checks.cooldown(1, 15.0)
    async def pokemon(self, interaction: discord.Interaction) -> None:
        if not await self._module_ok(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        await self._do_pokemon(interaction)

    @app_commands.command(name="quiz", description="Answer a trivia question.")
    async def quiz(self, interaction: discord.Interaction) -> None:
        if not await self._module_ok(interaction):
            return
        question, answer = random.choice(TRIVIA)
        embed = make_embed(
            title="\U0001f9e0 trivia",
            description=f"**{question}**\n\nyou have 15 seconds.",
            color=Colors.INFO,
        )
        await interaction.response.send_message(embed=embed)

        def check(msg: discord.Message) -> bool:
            return msg.author == interaction.user and msg.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", timeout=15.0, check=check)
        except Exception:
            await interaction.followup.send(
                embed=make_embed(title="\u23f0 time's up!", description=f"answer: **{answer}**", color=Colors.NEUTRAL)
            )
            return
        if msg.content.strip().lower() == answer.lower():
            await update_balance(interaction.guild.id, interaction.user.id, 50)
            await interaction.followup.send(
                embed=make_embed(title="\u2705 correct!", description="+50 coins", color=Colors.SUCCESS)
            )
        else:
            await interaction.followup.send(
                embed=make_embed(title="\u274c wrong!", description=f"answer: **{answer}**", color=Colors.ERROR)
            )

    @app_commands.command(name="typing", description="Typing speed mini-game.")
    async def typing(self, interaction: discord.Interaction) -> None:
        if not await self._module_ok(interaction):
            return
        phrase = random.choice(TYPING_PHRASES)
        embed = make_embed(
            title="\u2328 typing game",
            description=f"type this within 20s:\n\n`{phrase}`",
            color=Colors.INFO,
        )
        await interaction.response.send_message(embed=embed)

        def check(msg: discord.Message) -> bool:
            return msg.author == interaction.user and msg.channel == interaction.channel and msg.content.strip() == phrase

        try:
            await self.bot.wait_for("message", timeout=20.0, check=check)
        except Exception:
            await interaction.followup.send(
                embed=make_embed(title="\u274c too slow!", description="better luck next time.", color=Colors.ERROR)
            )
            return
        await update_balance(interaction.guild.id, interaction.user.id, 40)
        await interaction.followup.send(
            embed=make_embed(title="\u2705 nice typing!", description="+40 coins", color=Colors.SUCCESS)
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GamesCog(bot))
