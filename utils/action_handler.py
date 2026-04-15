"""
Action executor: handles function calls from AI.
No wavelink — uses new yt-dlp music cog.
"""
from __future__ import annotations

import io
import random
import logging
from typing import Optional

import discord
from discord.ext import commands

from config import OWNER_ID
from utils.embed_utils import make_embed, Colors


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


NO_VOICE = [
    "m có ở voice đéo đâu mà bắt t mở?",
    "vào voice trc đi r tính, t ko mở cho ng vắng mặt",
    "ủa m ở đâu v? vào voice đi đã",
    "lmao m ko ở voice mà kêu t play? vào đi",
    "nah, m chưa vào voice. vào r ns chuyện",
]

NO_PERM = [
    "m ko có quyền lm cái này đâu bro, hỏi admin đi",
    "nah m ko đủ quyền, đừng cố",
    "lmao nice try nhưng m ko có role để lm cái đó",
    "permission denied. m tưởng m là ai?",
]

OWNER_ONLY = [
    "cái này chỉ owner mới dc lm thui",
    "nah, reserved cho boss, m ko phải",
]


class VoiceControlView(discord.ui.View):
    def __init__(self, cog, guild_id: int) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="pause", emoji="\u23f8", style=discord.ButtonStyle.secondary)
    async def pause_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc:
            return
        if vc.is_paused():
            self.cog.resume(self.guild_id, vc)
            button.emoji = "\u23f8"
            button.label = "pause"
        else:
            self.cog.pause(self.guild_id, vc)
            button.emoji = "\u25b6"
            button.label = "resume"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="skip", emoji="\u23ed", style=discord.ButtonStyle.primary)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc:
            return
        if is_owner(interaction.user.id):
            self.cog.skip(self.guild_id, vc)
            await interaction.response.send_message(embed=make_embed(description="\u23ed owner skip.", color=Colors.INFO))
            return
        if self.guild_id not in self.cog.skip_votes:
            self.cog.skip_votes[self.guild_id] = set()
        self.cog.skip_votes[self.guild_id].add(interaction.user.id)
        total = self.cog._voice_member_count(vc)
        needed = max(1, (total + 1) // 2)
        votes = len(self.cog.skip_votes[self.guild_id])
        if votes >= needed:
            self.cog.skip(self.guild_id, vc)
            await interaction.response.send_message(embed=make_embed(description=f"\u23ed skipped ({votes}/{total})", color=Colors.INFO))
        else:
            await interaction.response.send_message(embed=make_embed(description=f"\u23ed vote: {votes}/{needed}", color=Colors.NEUTRAL), ephemeral=True)

    @discord.ui.button(label="stop", emoji="\u23f9", style=discord.ButtonStyle.danger)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not is_owner(interaction.user.id):
            await interaction.response.send_message(random.choice(OWNER_ONLY), ephemeral=True)
            return
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc:
            self.cog.stop(self.guild_id, vc)
        await interaction.response.send_message(embed=make_embed(description="\u23f9 stopped.", color=Colors.ERROR))

    @discord.ui.button(label="leave", emoji="\U0001f44b", style=discord.ButtonStyle.danger)
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not is_owner(interaction.user.id):
            await interaction.response.send_message(random.choice(OWNER_ONLY), ephemeral=True)
            return
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc:
            self.cog.stop(self.guild_id, vc)
            await vc.disconnect()
        await interaction.response.send_message(embed=make_embed(description="\U0001f44b bye.", color=Colors.NEUTRAL))
        self.stop()


async def execute_action(
    bot: commands.Bot,
    message: discord.Message,
    action: str,
    args: dict,
) -> str:
    member = message.author
    guild = message.guild
    if not guild or not isinstance(member, discord.Member):
        return "error: no guild"

    music_cog = bot.get_cog("MusicCog")
    vc = guild.voice_client

    # ── Music: play ──
    if action == "play_music":
        query = args.get("query", "")
        if not member.voice or not member.voice.channel:
            await message.reply(random.choice(NO_VOICE), mention_author=False)
            return ""
        if not vc:
            vc = await member.voice.channel.connect(self_deaf=True)
        if music_cog:
            track = await music_cog.play(guild.id, vc, query)
            if track:
                return f"đã bật '{track.title}'"
            return f"ko tìm thấy '{query}'"
        return "music cog ko có"

    # ── Music: controls ──
    if action in ("skip_music", "pause_music", "resume_music", "stop_music", "leave_voice"):
        if not member.voice or not member.voice.channel:
            await message.reply(random.choice(NO_VOICE), mention_author=False)
            return ""
        if not vc:
            return "t ko ở voice nào cả"
        if not music_cog:
            return "music cog ko có"

        if action == "skip_music":
            if is_owner(member.id):
                music_cog.skip(guild.id, vc)
                return "đã skip, owner quyền tối cao"
            total = music_cog._voice_member_count(vc)
            needed = max(1, (total + 1) // 2)
            return f"skip cần vote >50% ({needed}/{total} ng). bảo user dùng menu"

        if action == "pause_music":
            music_cog.pause(guild.id, vc)
            return "đã pause"

        if action == "resume_music":
            music_cog.resume(guild.id, vc)
            return "đã resume"

        if action == "stop_music":
            if not is_owner(member.id):
                await message.reply(random.choice(OWNER_ONLY), mention_author=False)
                return ""
            music_cog.stop(guild.id, vc)
            return "đã stop và clear queue"

        if action == "leave_voice":
            if not is_owner(member.id):
                await message.reply(random.choice(OWNER_ONLY), mention_author=False)
                return ""
            music_cog.stop(guild.id, vc)
            await vc.disconnect()
            return "đã rời voice"

    # ── Music: queue/menu ──
    if action == "show_queue":
        if not music_cog:
            return "ko có queue"
        items = music_cog.get_queue_list(guild.id)
        current = music_cog.get_current(guild.id)
        if not items and not current:
            return "queue trống"
        lines = []
        if current:
            lines.append(f"đang phát: {current.title}")
        for i, t in enumerate(items[:8]):
            lines.append(f"{i+1}. {t.title}")
        return "queue:\n" + "\n".join(lines)

    if action == "show_music_menu":
        if not music_cog or not vc:
            return "ko ở voice"
        view = VoiceControlView(music_cog, guild.id)
        current = music_cog.get_current(guild.id)
        title = current.title if current else "nothing"
        embed = make_embed(title=f"\U0001f3b5 {title}", description="bấm nút để điều khiển", color=Colors.SPECIAL)
        await message.reply(embed=embed, view=view, mention_author=False)
        return ""

    # ── Image gen ──
    if action == "generate_image":
        prompt = args.get("prompt", "")
        if not prompt:
            return "ko có prompt để gen ảnh"
        img_data = await bot.ai_client.generate_image(prompt)
        if img_data:
            file = discord.File(io.BytesIO(img_data), filename="iroha_gen.png")
            await message.reply(file=file, mention_author=False)
            return ""
        return "gen ảnh thất bại, thử lại đi"

    # ── Web search ──
    if action == "web_search":
        query = args.get("query", "")
        if not query:
            return "ko có gì để search"
        result = await bot.ai_client.search_web(query, [{"role": "user", "content": query}])
        if result:
            await message.reply(result, mention_author=False)
            return ""
        return "search ko ra gì"

    # ── Admin tools (owner + server admin only) ──
    is_admin = is_owner(member.id) or (isinstance(member, discord.Member) and member.guild_permissions.administrator)

    if action == "create_giveaway":
        if not is_admin:
            await message.reply(random.choice(NO_PERM), mention_author=False)
            return ""
        prize = args.get("prize", "")
        duration = args.get("duration", "")
        winners = args.get("winners", 1)
        if not prize or not duration:
            return "thiếu info, hỏi lại user prize + duration"
        from utils.time_utils import parse_duration
        from db import create_giveaway, get_guild_config
        from datetime import datetime, timezone, timedelta
        try:
            seconds = parse_duration(duration)
        except Exception:
            return f"duration '{duration}' ko hợp lệ"
        ends_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        cfg = await get_guild_config(guild.id)
        channel = message.channel
        giveaway_cog = bot.get_cog("GiveawayCog")
        if giveaway_cog:
            from cogs.giveaway import GiveawayJoinView, _build_embed
            giveaway_data = {"prize": prize, "winner_count": winners, "ends_at": ends_at.isoformat(), "ended_at": None, "id": None}
            embed = _build_embed(giveaway_data, 0)
            view = GiveawayJoinView(bot)
            msg = await channel.send(embed=embed, view=view)
            giveaway_id = await create_giveaway(guild.id, channel.id, msg.id, prize, winners, ends_at.isoformat(), member.id)
            giveaway_data["id"] = giveaway_id
            embed = _build_embed(giveaway_data, 0)
            await msg.edit(embed=embed, view=view)
            return f"đã tạo giveaway '{prize}', {winners} winner, kết thúc trong {duration}"
        return "giveaway cog ko có"

    if action == "purge_messages":
        if not is_admin:
            await message.reply(random.choice(NO_PERM), mention_author=False)
            return ""
        amount = args.get("amount", 10)
        if amount < 1 or amount > 500:
            return "purge 1-500 thôi"
        from datetime import datetime, timezone, timedelta
        channel = message.channel
        deleted = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        recent, old = [], []
        async for msg in channel.history(limit=amount + 1):  # +1 for trigger message
            if msg.id == message.id:
                continue
            if msg.created_at > cutoff:
                recent.append(msg)
            else:
                old.append(msg)
        if recent:
            try:
                for i in range(0, len(recent), 100):
                    await channel.delete_messages(recent[i:i+100])
                    deleted += len(recent[i:i+100])
            except Exception:
                for m in recent:
                    try:
                        await m.delete()
                        deleted += 1
                    except Exception:
                        pass
        for m in old:
            try:
                await m.delete()
                deleted += 1
            except Exception:
                pass
        return f"đã xóa {deleted} tin nhắn"

    if action == "timeout_user":
        if not is_admin:
            await message.reply(random.choice(NO_PERM), mention_author=False)
            return ""
        user_str = args.get("user", "")
        duration = args.get("duration", "5m")
        reason = args.get("reason", "no reason")
        from utils.time_utils import parse_duration
        from datetime import timedelta
        try:
            seconds = parse_duration(duration)
        except Exception:
            return f"duration '{duration}' ko hợp lệ"
        # find member
        target = None
        for m in guild.members:
            if user_str.lower() in m.name.lower() or user_str.lower() in m.display_name.lower() or f"<@{m.id}>" in user_str or f"<@!{m.id}>" in user_str:
                target = m
                break
        if not target:
            return f"ko tìm thấy user '{user_str}'"
        try:
            await target.timeout(timedelta(seconds=seconds), reason=reason)
            return f"đã timeout {target.display_name} {duration} — lý do: {reason}"
        except Exception as e:
            return f"timeout fail: {e}"

    if action == "kick_user":
        if not is_admin:
            await message.reply(random.choice(NO_PERM), mention_author=False)
            return ""
        user_str = args.get("user", "")
        reason = args.get("reason", "no reason")
        target = None
        for m in guild.members:
            if user_str.lower() in m.name.lower() or user_str.lower() in m.display_name.lower() or f"<@{m.id}>" in user_str:
                target = m
                break
        if not target:
            return f"ko tìm thấy user '{user_str}'"
        try:
            await target.kick(reason=reason)
            return f"đã kick {target.display_name} — lý do: {reason}"
        except Exception as e:
            return f"kick fail: {e}"

    if action == "create_channel":
        if not is_admin:
            await message.reply(random.choice(NO_PERM), mention_author=False)
            return ""
        name = args.get("name", "")
        cat_name = args.get("category", "")
        if not name:
            return "thiếu tên kênh"
        category = None
        if cat_name:
            category = discord.utils.get(guild.categories, name=cat_name)
            if not category:
                try:
                    category = await guild.create_category(cat_name)
                except Exception:
                    pass
        try:
            ch = await guild.create_text_channel(name=name, category=category)
            return f"đã tạo kênh {ch.mention}"
        except Exception as e:
            return f"tạo kênh fail: {e}"

    if action == "delete_channel":
        if not is_admin:
            await message.reply(random.choice(NO_PERM), mention_author=False)
            return ""
        ch_name = args.get("channel", "current")
        if ch_name == "current":
            target_ch = message.channel
        else:
            target_ch = discord.utils.get(guild.text_channels, name=ch_name.lower().replace(" ", "-"))
        if not target_ch:
            return f"ko tìm thấy kênh '{ch_name}'"
        try:
            name = target_ch.name
            await target_ch.delete()
            return f"đã xóa kênh #{name}"
        except Exception as e:
            return f"xóa kênh fail: {e}"

    return f"action '{action}' ko hỗ trợ"
