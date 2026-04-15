from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import TICKET_CATEGORY_NAME
from db import create_ticket, close_ticket, get_guild_config
from utils.checks import is_moderator
from utils.guards import module_enabled
from utils.embed_utils import make_embed, Colors
from utils.view_utils import ConfirmView


class TicketCloseView(discord.ui.View):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="close ticket", style=discord.ButtonStyle.danger, emoji="\U0001f512", custom_id="ticket_close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        topic = getattr(interaction.channel, "topic", "") or ""
        is_opener = str(interaction.user.id) in topic
        is_mod = await is_moderator(interaction.user)
        if not is_opener and not is_mod:
            await interaction.response.send_message("no permission.", ephemeral=True)
            return

        confirm = ConfirmView(interaction.user.id)
        await interaction.response.send_message(
            embed=make_embed(title="close ticket?", description="this will delete the channel.", color=Colors.ERROR),
            view=confirm, ephemeral=True,
        )
        await confirm.wait()
        if not confirm.value:
            return
        await close_ticket(interaction.channel_id)
        try:
            await interaction.channel.send(embed=make_embed(title="ticket closed", description=f"closed by {interaction.user.mention}", color=Colors.NEUTRAL))
            await interaction.channel.delete()
        except Exception:
            logging.exception("failed to delete ticket channel %s", interaction.channel_id)


class TicketModal(discord.ui.Modal, title="support ticket"):
    issue = discord.ui.TextInput(label="describe your issue", style=discord.TextStyle.paragraph, max_length=1000)

    def __init__(self, bot: commands.Bot, interaction: discord.Interaction) -> None:
        super().__init__()
        self.bot = bot
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if not guild:
            return
        cfg = await get_guild_config(guild.id)
        if not module_enabled(cfg, "tickets_enabled", interaction.user.id):
            await interaction.response.send_message("tickets disabled.", ephemeral=True)
            return
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)
        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}".lower(),
            category=category,
            topic=f"ticket by {interaction.user.id}",
        )
        await channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        mod_role_id = cfg.get("mod_role_id")
        if mod_role_id:
            role = guild.get_role(int(mod_role_id))
            if role:
                await channel.set_permissions(role, read_messages=True, send_messages=True)
        await create_ticket(guild.id, channel.id, interaction.user.id)

        ticket_embed = make_embed(
            title="\U0001f3ab new ticket",
            description=f"**issue:** {self.issue.value}",
            color=Colors.INFO,
            thumbnail_url=interaction.user.display_avatar.url,
        )
        ticket_embed.add_field(name="opened by", value=interaction.user.mention, inline=True)
        ticket_embed.add_field(name="status", value="\U0001f7e2 open", inline=True)
        view = TicketCloseView(self.bot)
        await channel.send(embed=ticket_embed, view=view)
        await interaction.response.send_message(
            embed=make_embed(title="ticket created", description=f"your ticket: {channel.mention}", color=Colors.SUCCESS),
            ephemeral=True,
        )


class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(TicketCloseView(self.bot))

    @app_commands.command(name="ticket", description="Open a support ticket.")
    async def ticket(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "tickets_enabled", interaction.user.id):
            await interaction.response.send_message("tickets disabled.", ephemeral=True)
            return
        modal = TicketModal(self.bot, interaction)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="ticket_close", description="Close the current ticket.")
    async def ticket_close(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not await is_moderator(interaction.user):
            await interaction.response.send_message("no permission.", ephemeral=True)
            return
        await close_ticket(interaction.channel_id)
        await interaction.response.send_message(
            embed=make_embed(title="ticket closed", description="closing...", color=Colors.NEUTRAL),
            ephemeral=True,
        )
        try:
            await interaction.channel.delete()
        except Exception:
            logging.exception("failed to delete ticket channel %s", interaction.channel_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketsCog(bot))
