from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from db import (
    create_role_menu,
    add_role_menu_item,
    list_all_role_menus,
    list_role_menu_items,
    get_guild_config,
    update_guild_config,
)
from utils.checks import is_moderator
from utils.guards import module_enabled


class RoleSelect(discord.ui.Select):
    def __init__(self, message_id: int, options: list[discord.SelectOption], min_values: int, max_values: int) -> None:
        super().__init__(
            placeholder="Choose roles...",
            min_values=min_values,
            max_values=max_values,
            options=options,
            custom_id=f"role_menu:{message_id}",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        selected_ids = {int(v) for v in self.values}
        for option in self.options:
            role_id = int(option.value)
            role = interaction.guild.get_role(role_id)
            if not role:
                continue
            if role_id in selected_ids:
                await interaction.user.add_roles(role, reason="Role menu selection")
            else:
                await interaction.user.remove_roles(role, reason="Role menu selection")
        await interaction.response.send_message("Roles updated.", ephemeral=True)


class RoleMenuView(discord.ui.View):
    def __init__(self, message_id: int, options: list[discord.SelectOption], min_values: int, max_values: int) -> None:
        super().__init__(timeout=None)
        self.add_item(RoleSelect(message_id, options, min_values, max_values))


class RolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        menus = await list_all_role_menus()
        for menu in menus:
            items = await list_role_menu_items(menu["message_id"])
            options = []
            for item in items:
                options.append(
                    discord.SelectOption(
                        label=item.get("label") or f"Role {item['role_id']}",
                        value=str(item["role_id"]),
                        emoji=item.get("emoji") or None,
                    )
                )
            view = RoleMenuView(menu["message_id"], options, menu["min_values"], menu["max_values"])
            self.bot.add_view(view)

    @app_commands.command(name="rolemenu", description="Create a role menu.")
    async def rolemenu(
        self,
        interaction: discord.Interaction,
        title: str,
        roles: str,
        min_values: int = 0,
        max_values: int = 1,
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "roles_enabled", interaction.user.id):
            await interaction.response.send_message("Roles module is disabled.", ephemeral=True)
            return
        if not await is_moderator(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        role_ids = []
        for part in roles.split(","):
            part = part.strip().strip("<@&>").strip()
            if part.isdigit():
                role_ids.append(int(part))
        if not role_ids:
            await interaction.response.send_message("No valid roles provided.", ephemeral=True)
            return
        options = []
        for role_id in role_ids:
            role = interaction.guild.get_role(role_id)
            if role:
                options.append(discord.SelectOption(label=role.name, value=str(role.id)))
        if not options:
            await interaction.response.send_message("No valid roles found.", ephemeral=True)
            return
        min_values = max(0, min(min_values, len(options)))
        max_values = max(min_values if min_values > 0 else 1, min(max_values, len(options)))
        view = RoleMenuView(0, options, min_values, max_values)
        embed = discord.Embed(title=title, description="Select your roles below.")
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()
        view = RoleMenuView(message.id, options, min_values, max_values)
        await message.edit(view=view)
        await create_role_menu(interaction.guild.id, message.id, interaction.channel_id, title, min_values, max_values)
        for opt in options:
            await add_role_menu_item(message.id, int(opt.value), opt.label, opt.emoji)
        self.bot.add_view(view)

    @app_commands.command(name="autorole", description="Set an auto-role for new members.")
    async def autorole(self, interaction: discord.Interaction, role: discord.Role | None = None) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "roles_enabled", interaction.user.id):
            await interaction.response.send_message("Roles module is disabled.", ephemeral=True)
            return
        if not await is_moderator(interaction.user):
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        await update_guild_config(interaction.guild.id, auto_role_id=role.id if role else None)
        await interaction.response.send_message("Auto-role updated.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RolesCog(bot))
