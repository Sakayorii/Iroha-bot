from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

import discord
from discord import app_commands
from discord.ext import commands

from config import DAILY_REWARD, DAILY_TASK_MESSAGES, DAILY_TASK_VOICE_MINUTES, DAILY_TASK_GAMES
from utils.guards import module_enabled
from utils.embed_utils import make_embed, progress_bar, Colors
from db import (
    get_guild_config,
    get_balance,
    update_balance,
    get_daily_tasks,
    upsert_daily_task,
    claim_daily,
    add_user_item,
    get_user_items,
    upsert_user_profile,
    get_user_profile,
)


SHOP_ITEMS: Dict[str, Dict[str, str | int]] = {
    "iroha_frame": {"name": "iroha frame", "price": 500, "type": "frame", "emoji": "\U0001f5bc"},
    "star_title": {"name": "star singer", "price": 300, "type": "title", "emoji": "\u2b50"},
    "fan_title": {"name": "iroha fan", "price": 300, "type": "title", "emoji": "\U0001f496"},
}


def _date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ShopBuyButton(discord.ui.Button):
    def __init__(self, item_id: str, info: dict) -> None:
        super().__init__(
            label=f"{info['name']} — {info['price']} coins",
            style=discord.ButtonStyle.success,
            emoji=info.get("emoji"),
            custom_id=f"shop_buy:{item_id}",
        )
        self.item_id = item_id
        self.info = info

    async def callback(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        price = int(self.info["price"])
        balance, _ = await get_balance(interaction.guild.id, interaction.user.id)
        if balance < price:
            await interaction.response.send_message(
                embed=make_embed(title="nope", description=f"need {price:,} coins, u have {balance:,}.", color=Colors.ERROR),
                ephemeral=True,
            )
            return
        await update_balance(interaction.guild.id, interaction.user.id, -price)
        await add_user_item(interaction.guild.id, interaction.user.id, self.item_id, 1)
        await interaction.response.send_message(
            embed=make_embed(title="purchased!", description=f"{self.info['emoji']} **{self.info['name']}** — -{price:,} coins", color=Colors.SUCCESS),
            ephemeral=True,
        )


class ShopView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=120)
        for item_id, info in SHOP_ITEMS.items():
            self.add_item(ShopBuyButton(item_id, info))


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="balance", description="Check your balance.")
    async def balance(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "economy_enabled", interaction.user.id):
            await interaction.response.send_message("economy disabled.", ephemeral=True)
            return
        target = member or interaction.user
        balance, _ = await get_balance(interaction.guild.id, target.id)
        embed = make_embed(
            title=f"{target.display_name}'s balance",
            description=f"\U0001f4b0 **{balance:,}** coins",
            color=Colors.SPECIAL,
            thumbnail_url=target.display_avatar.url if isinstance(target, discord.Member) else None,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="daily", description="Claim daily rewards if tasks are done.")
    async def daily(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "economy_enabled", interaction.user.id):
            await interaction.response.send_message("economy disabled.", ephemeral=True)
            return
        date = _date_str()
        tasks = await get_daily_tasks(interaction.guild.id, interaction.user.id, date)
        if not tasks:
            await upsert_daily_task(interaction.guild.id, interaction.user.id, date, "messages", DAILY_TASK_MESSAGES, 0, 0)
            await upsert_daily_task(interaction.guild.id, interaction.user.id, date, "voice_minutes", DAILY_TASK_VOICE_MINUTES, 0, 0)
            await upsert_daily_task(interaction.guild.id, interaction.user.id, date, "games", DAILY_TASK_GAMES, 0, 0)
            tasks = await get_daily_tasks(interaction.guild.id, interaction.user.id, date)
        all_done = all(t["progress"] >= t["target"] for t in tasks)
        already_claimed = any(t["claimed"] for t in tasks)
        if already_claimed:
            await interaction.response.send_message(
                embed=make_embed(title="daily", description="already claimed today.", color=Colors.NEUTRAL),
                ephemeral=True,
            )
            return
        if not all_done:
            task_emojis = {"messages": "\U0001f4ac", "voice_minutes": "\U0001f3a4", "games": "\U0001f3ae"}
            lines = []
            for t in tasks:
                emoji = task_emojis.get(t["task_type"], "\u2022")
                done = "\u2705" if t["progress"] >= t["target"] else "\u274c"
                bar = progress_bar(t["progress"], t["target"], 8)
                lines.append(f"{done} {emoji} {t['task_type']}: {bar} ({t['progress']}/{t['target']})")
            embed = make_embed(title="daily tasks", description="\n".join(lines), color=Colors.INFO)
            embed.add_field(name="reward", value=f"\U0001f4b0 {DAILY_REWARD:,} coins (complete all to claim)", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await update_balance(interaction.guild.id, interaction.user.id, DAILY_REWARD)
        await claim_daily(interaction.guild.id, interaction.user.id, date)
        await interaction.response.send_message(
            embed=make_embed(title="daily claimed!", description=f"\U0001f4b0 +{DAILY_REWARD:,} coins", color=Colors.SUCCESS),
            ephemeral=True,
        )

    @app_commands.command(name="shop", description="Show the shop.")
    async def shop(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "economy_enabled", interaction.user.id):
            await interaction.response.send_message("economy disabled.", ephemeral=True)
            return
        lines = []
        for item_id, info in SHOP_ITEMS.items():
            lines.append(f"{info.get('emoji', '')} **{info['name']}** \u2014 {info['price']:,} coins *({info['type']})*")
        embed = make_embed(title="\U0001f6d2 shop", description="\n".join(lines), color=Colors.SPECIAL)
        embed.set_footer(text="click a button to buy \u2022 iroha")
        view = ShopView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="buy", description="Buy an item from the shop.")
    async def buy(self, interaction: discord.Interaction, item_id: str) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "economy_enabled", interaction.user.id):
            await interaction.response.send_message("economy disabled.", ephemeral=True)
            return
        if item_id not in SHOP_ITEMS:
            await interaction.response.send_message(
                embed=make_embed(title="nope", description="item not found.", color=Colors.ERROR),
                ephemeral=True,
            )
            return
        info = SHOP_ITEMS[item_id]
        price = int(info["price"])
        balance, _ = await get_balance(interaction.guild.id, interaction.user.id)
        if balance < price:
            await interaction.response.send_message(
                embed=make_embed(title="broke", description=f"need {price:,}, u have {balance:,}.", color=Colors.ERROR),
                ephemeral=True,
            )
            return
        await update_balance(interaction.guild.id, interaction.user.id, -price)
        await add_user_item(interaction.guild.id, interaction.user.id, item_id, 1)
        await interaction.response.send_message(
            embed=make_embed(title="purchased!", description=f"{info.get('emoji', '')} **{info['name']}**", color=Colors.SUCCESS),
            ephemeral=True,
        )

    @app_commands.command(name="inventory", description="Show your items.")
    async def inventory(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "economy_enabled", interaction.user.id):
            await interaction.response.send_message("economy disabled.", ephemeral=True)
            return
        items = await get_user_items(interaction.guild.id, interaction.user.id)
        if not items:
            await interaction.response.send_message(
                embed=make_embed(title="inventory", description="empty.", color=Colors.NEUTRAL),
                ephemeral=True,
            )
            return
        lines = []
        for i in items:
            info = SHOP_ITEMS.get(i["item_id"], {})
            name = info.get("name", i["item_id"])
            emoji = info.get("emoji", "\u2022")
            lines.append(f"{emoji} **{name}** x{i['count']}")
        embed = make_embed(title="\U0001f392 inventory", description="\n".join(lines), color=Colors.INFO)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="settitle", description="Set a profile title you own.")
    async def settitle(self, interaction: discord.Interaction, item_id: str) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "economy_enabled", interaction.user.id):
            await interaction.response.send_message("economy disabled.", ephemeral=True)
            return
        items = await get_user_items(interaction.guild.id, interaction.user.id)
        owned = {i["item_id"] for i in items}
        if item_id not in owned:
            await interaction.response.send_message("u don't own that.", ephemeral=True)
            return
        item = SHOP_ITEMS.get(item_id)
        if not item or item.get("type") != "title":
            await interaction.response.send_message("not a title.", ephemeral=True)
            return
        current = await get_user_profile(interaction.guild.id, interaction.user.id)
        await upsert_user_profile(interaction.guild.id, interaction.user.id, item["name"], current.get("frame"))
        await interaction.response.send_message(
            embed=make_embed(title="title set", description=f"*{item['name']}*", color=Colors.SUCCESS),
            ephemeral=True,
        )

    @app_commands.command(name="setframe", description="Set a profile frame you own.")
    async def setframe(self, interaction: discord.Interaction, item_id: str) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "economy_enabled", interaction.user.id):
            await interaction.response.send_message("economy disabled.", ephemeral=True)
            return
        items = await get_user_items(interaction.guild.id, interaction.user.id)
        owned = {i["item_id"] for i in items}
        if item_id not in owned:
            await interaction.response.send_message("u don't own that.", ephemeral=True)
            return
        item = SHOP_ITEMS.get(item_id)
        if not item or item.get("type") != "frame":
            await interaction.response.send_message("not a frame.", ephemeral=True)
            return
        current = await get_user_profile(interaction.guild.id, interaction.user.id)
        await upsert_user_profile(interaction.guild.id, interaction.user.id, current.get("title"), item["name"])
        await interaction.response.send_message(
            embed=make_embed(title="frame set", description=f"\U0001f5bc {item['name']}", color=Colors.SUCCESS),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EconomyCog(bot))
