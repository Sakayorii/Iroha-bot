from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


IROHA_CODE_URL = "https://github.com/yukkisensei/Teto"
DISCORD_URL = "https://discord.gg/35P2xNnemF"


class LinksCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="links", description="Show official links.")
    async def links(self, interaction: discord.Interaction) -> None:
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Source Code", url=IROHA_CODE_URL))
        view.add_item(discord.ui.Button(label="Discord Server", url=DISCORD_URL))
        embed = discord.Embed(
            title="Iroha Links",
            description="useful links.",
            color=discord.Color.purple(),
        )
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LinksCog(bot))
