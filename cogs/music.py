"""
Music cog — yt-dlp + FFmpeg. No Lavalink needed.
"""
from __future__ import annotations

import asyncio
import logging
import random
from collections import deque
from dataclasses import dataclass
from typing import Optional, Dict, Deque

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

from config import OWNER_ID
from db import get_guild_config
from utils.guards import bot_ratio_exceeded, module_enabled
from utils.embed_utils import make_embed, progress_bar, format_duration, Colors

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


@dataclass
class Track:
    title: str
    url: str
    stream_url: str
    duration: int  # seconds
    thumbnail: Optional[str] = None
    author: Optional[str] = None


async def search_track(query: str) -> Optional[Track]:
    """Search for a track using yt-dlp. Runs in thread pool."""
    def _search():
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
            if not info:
                return None
            if "entries" in info:
                entries = list(info["entries"])
                if not entries:
                    return None
                info = entries[0]
            return Track(
                title=info.get("title", "unknown"),
                url=info.get("webpage_url", ""),
                stream_url=info.get("url", ""),
                duration=info.get("duration", 0) or 0,
                thumbnail=info.get("thumbnail"),
                author=info.get("uploader", info.get("channel", "")),
            )

    try:
        return await asyncio.to_thread(_search)
    except Exception:
        logging.exception("yt-dlp search error")
        return None


IDLE_TIMEOUT = 180  # 3 minutes


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.queues: Dict[int, Deque[Track]] = {}
        self.current_track: Dict[int, Optional[Track]] = {}
        self.loop_enabled: Dict[int, bool] = {}
        self._idle_tasks: Dict[int, asyncio.Task] = {}
        self.skip_votes: Dict[int, set] = {}

    def _get_queue(self, guild_id: int) -> Deque[Track]:
        if guild_id not in self.queues:
            self.queues[guild_id] = deque()
        return self.queues[guild_id]

    def _voice_member_count(self, vc: discord.VoiceClient) -> int:
        if not vc or not vc.channel:
            return 0
        return sum(1 for m in vc.channel.members if not m.bot)

    def _cancel_idle(self, guild_id: int) -> None:
        task = self._idle_tasks.pop(guild_id, None)
        if task and not task.done():
            task.cancel()

    def _start_idle_timer(self, guild_id: int, vc: discord.VoiceClient) -> None:
        self._cancel_idle(guild_id)

        async def _idle_disconnect():
            await asyncio.sleep(IDLE_TIMEOUT)
            if not vc.is_playing() and not vc.is_paused() and vc.is_connected():
                self.current_track[guild_id] = None
                self._get_queue(guild_id).clear()
                await vc.disconnect()
                logging.info(f"idle disconnect guild {guild_id} after {IDLE_TIMEOUT}s")

        self._idle_tasks[guild_id] = self.bot.loop.create_task(_idle_disconnect())

    async def _play_next(self, guild_id: int, vc: discord.VoiceClient) -> None:
        """Play the next track in queue."""
        queue = self._get_queue(guild_id)

        # loop current track
        if self.loop_enabled.get(guild_id) and self.current_track.get(guild_id):
            track = self.current_track[guild_id]
        elif queue:
            track = queue.popleft()
        else:
            self.current_track[guild_id] = None
            # start idle timer — leave after 3 min
            self._start_idle_timer(guild_id, vc)
            return

        self.current_track[guild_id] = track
        self.skip_votes.pop(guild_id, None)
        self._cancel_idle(guild_id)

        # re-fetch stream URL (they expire)
        fresh = await search_track(track.url or track.title)
        if fresh:
            track.stream_url = fresh.stream_url

        def after_play(error):
            if error:
                logging.error(f"playback error: {error}")
            asyncio.run_coroutine_threadsafe(
                self._play_next(guild_id, vc), self.bot.loop
            )

        try:
            source = discord.FFmpegPCMAudio(track.stream_url, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=0.5)
            vc.play(source, after=after_play)
        except Exception:
            logging.exception("ffmpeg play error")
            self.current_track[guild_id] = None

    async def play(self, guild_id: int, vc: discord.VoiceClient, query: str) -> Optional[Track]:
        """Search, queue, and play. Returns the track or None."""
        track = await search_track(query)
        if not track:
            return None
        queue = self._get_queue(guild_id)
        if len(queue) >= 100:
            return None
        if vc.is_playing() or vc.is_paused():
            queue.append(track)
        else:
            self.current_track[guild_id] = track
            queue.append(track)
            await self._play_next(guild_id, vc)
        return track

    def skip(self, guild_id: int, vc: discord.VoiceClient) -> None:
        self.loop_enabled[guild_id] = False  # disable loop on skip
        if vc.is_playing() or vc.is_paused():
            vc.stop()  # triggers after_play → plays next

    def pause(self, guild_id: int, vc: discord.VoiceClient) -> None:
        if vc.is_playing():
            vc.pause()

    def resume(self, guild_id: int, vc: discord.VoiceClient) -> None:
        if vc.is_paused():
            vc.resume()

    def stop(self, guild_id: int, vc: discord.VoiceClient) -> None:
        self._get_queue(guild_id).clear()
        self.current_track[guild_id] = None
        self.loop_enabled[guild_id] = False
        if vc.is_playing() or vc.is_paused():
            vc.stop()

    def get_queue_list(self, guild_id: int) -> list[Track]:
        return list(self._get_queue(guild_id))

    def get_current(self, guild_id: int) -> Optional[Track]:
        return self.current_track.get(guild_id)

    # ─── Slash commands ───────────────────────────────────────

    @app_commands.command(name="play", description="Play a song.")
    async def play_cmd(self, interaction: discord.Interaction, query: str) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("vào voice trước đi.", ephemeral=True)
            return
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect(self_deaf=True)
        track = await self.play(interaction.guild.id, vc, query)
        if track:
            embed = make_embed(
                title=f"\U0001f3b5 {track.title}",
                description=f"by {track.author or 'unknown'} \u2022 {format_duration(track.duration * 1000)}",
                color=Colors.SUCCESS,
            )
            if track.thumbnail:
                embed.set_thumbnail(url=track.thumbnail)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(embed=make_embed(description="ko tìm thấy bài.", color=Colors.ERROR))

    @app_commands.command(name="skip", description="Skip the current song.")
    async def skip_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            await interaction.response.send_message("ko ở voice.", ephemeral=True)
            return
        self.skip(interaction.guild.id, vc)
        await interaction.response.send_message(embed=make_embed(description="\u23ed skipped.", color=Colors.INFO), ephemeral=True)

    @app_commands.command(name="pause", description="Pause playback.")
    async def pause_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("ko ở voice.", ephemeral=True)
            return
        self.pause(interaction.guild.id, vc)
        await interaction.response.send_message(embed=make_embed(description="\u23f8 paused.", color=Colors.NEUTRAL), ephemeral=True)

    @app_commands.command(name="resume", description="Resume playback.")
    async def resume_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("ko ở voice.", ephemeral=True)
            return
        self.resume(interaction.guild.id, vc)
        await interaction.response.send_message(embed=make_embed(description="\u25b6 resumed.", color=Colors.SUCCESS), ephemeral=True)

    @app_commands.command(name="stop", description="Stop playback and clear queue.")
    async def stop_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("ko ở voice.", ephemeral=True)
            return
        self.stop(interaction.guild.id, vc)
        await interaction.response.send_message(embed=make_embed(description="\u23f9 stopped.", color=Colors.ERROR), ephemeral=True)

    @app_commands.command(name="leave", description="Disconnect from voice.")
    async def leave_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("ko ở voice.", ephemeral=True)
            return
        self.stop(interaction.guild.id, vc)
        await vc.disconnect()
        await interaction.response.send_message(embed=make_embed(description="\U0001f44b bye.", color=Colors.NEUTRAL), ephemeral=True)

    @app_commands.command(name="queue", description="Show the queue.")
    async def queue_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        items = self.get_queue_list(interaction.guild.id)
        current = self.get_current(interaction.guild.id)
        if not items and not current:
            await interaction.response.send_message(embed=make_embed(description="queue trống.", color=Colors.NEUTRAL), ephemeral=True)
            return
        from utils.view_utils import PaginatorView

        def fmt(idx, track):
            return f"`{idx + 1}.` {track.title} \u2014 {format_duration(track.duration * 1000)}"

        now_text = f"**now:** {current.title}\n\n" if current else ""
        view = PaginatorView(items=items, per_page=10, title="queue", color=Colors.INFO, formatter_fn=fmt, author_id=interaction.user.id)
        embed = view.get_embed()
        if now_text:
            embed.description = now_text + (embed.description or "")
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="nowplaying", description="Show current song.")
    async def nowplaying_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        current = self.get_current(interaction.guild.id)
        if not current:
            await interaction.response.send_message("nothing playing.", ephemeral=True)
            return
        loop_on = self.loop_enabled.get(interaction.guild.id, False)
        embed = make_embed(
            title=current.title,
            description=f"by **{current.author or 'unknown'}**",
            color=Colors.SPECIAL,
        )
        embed.add_field(name="duration", value=format_duration(current.duration * 1000), inline=True)
        embed.add_field(name="queue", value=str(len(self._get_queue(interaction.guild.id))), inline=True)
        embed.add_field(name="loop", value="on" if loop_on else "off", inline=True)
        if current.thumbnail:
            embed.set_thumbnail(url=current.thumbnail)
        view = NowPlayingView(self, interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="loop", description="Toggle loop mode.")
    async def loop_cmd(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            return
        enabled = not self.loop_enabled.get(interaction.guild.id, False)
        self.loop_enabled[interaction.guild.id] = enabled
        color = Colors.SUCCESS if enabled else Colors.NEUTRAL
        await interaction.response.send_message(
            embed=make_embed(description=f"\U0001f501 loop {'on' if enabled else 'off'}", color=color),
            ephemeral=True,
        )


class NowPlayingView(discord.ui.View):
    def __init__(self, cog: MusicCog, guild_id: int) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(emoji="\u23f8", style=discord.ButtonStyle.secondary)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc:
            return
        if vc.is_paused():
            self.cog.resume(self.guild_id, vc)
            button.emoji = "\u23f8"
        else:
            self.cog.pause(self.guild_id, vc)
            button.emoji = "\u25b6"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="\u23ed", style=discord.ButtonStyle.primary)
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc:
            return
        if interaction.user.id == OWNER_ID:
            self.cog.skip(self.guild_id, vc)
            await interaction.response.send_message(embed=make_embed(description="\u23ed owner skip.", color=Colors.INFO))
            return
        # vote skip
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

    @discord.ui.button(emoji="\u23f9", style=discord.ButtonStyle.danger)
    async def stop_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("chỉ owner mới dc stop.", ephemeral=True)
            return
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc:
            self.cog.stop(self.guild_id, vc)
        await interaction.response.send_message(embed=make_embed(description="\u23f9 stopped.", color=Colors.ERROR))

    @discord.ui.button(emoji="\U0001f501", style=discord.ButtonStyle.secondary)
    async def loop_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        enabled = not self.cog.loop_enabled.get(self.guild_id, False)
        self.cog.loop_enabled[self.guild_id] = enabled
        button.style = discord.ButtonStyle.success if enabled else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot))
