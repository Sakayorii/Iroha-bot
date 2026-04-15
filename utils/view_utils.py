from __future__ import annotations

from typing import Any, Callable, List, Optional

import discord

from utils.embed_utils import Colors, make_embed, paginate_embed_list


class PaginatorView(discord.ui.View):
    def __init__(
        self,
        items: List[Any],
        per_page: int,
        title: str,
        color: discord.Color,
        formatter_fn: Callable[[int, Any], str],
        author_id: int,
        thumbnail_url: Optional[str] = None,
    ) -> None:
        super().__init__(timeout=120)
        self.items = items
        self.per_page = per_page
        self.title = title
        self.color = color
        self.formatter_fn = formatter_fn
        self.author_id = author_id
        self.thumbnail_url = thumbnail_url
        self.page = 1
        self.total_pages = max(1, (len(items) + per_page - 1) // per_page)
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_btn.disabled = self.page <= 1
        self.next_btn.disabled = self.page >= self.total_pages

    def get_embed(self) -> discord.Embed:
        embed, _ = paginate_embed_list(
            self.items, self.per_page, self.page,
            self.title, self.color, self.formatter_fn,
            self.thumbnail_url,
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("not ur list.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    @discord.ui.button(label="\u25c0", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = max(1, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="\u25b6", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = min(self.total_pages, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


class ConfirmView(discord.ui.View):
    def __init__(self, author_id: int) -> None:
        super().__init__(timeout=30)
        self.author_id = author_id
        self.value: Optional[bool] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("not ur button.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.value = True
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.value = False
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()
