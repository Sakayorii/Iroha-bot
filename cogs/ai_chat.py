from __future__ import annotations

import base64
import logging
import re
import time
from typing import Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import MAX_AI_HISTORY, AI_COOLDOWN_SECONDS, OWNER_ID
from db import get_guild_config
from utils.guards import bot_ratio_exceeded, module_enabled
from utils.action_handler import execute_action
from utils.web_tools import fetch_url_text, fetch_github_repo, GITHUB_REPO_PATTERN
from utils.human_send import split_response, send_human

IMAGE_TYPES = ("image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp")
TEXT_EXTENSIONS = (
    ".txt", ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".csv", ".md",
    ".html", ".css", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".sh", ".bat", ".ps1", ".lua", ".rb", ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".php", ".sql", ".r", ".swift",
    ".env", ".gitignore", ".dockerfile", ".log", ".conf", ".properties",
)
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


async def attachment_to_b64(attachment: discord.Attachment) -> Optional[str]:
    try:
        data = await attachment.read()
        return base64.b64encode(data).decode()
    except Exception:
        return None


async def attachment_to_text(attachment: discord.Attachment) -> Optional[str]:
    """Read text-based file attachments. Returns file content as string."""
    name = (attachment.filename or "").lower()

    # text files by extension
    if any(name.endswith(ext) for ext in TEXT_EXTENSIONS):
        try:
            data = await attachment.read()
            return data.decode("utf-8", errors="replace")[:15000]
        except Exception:
            return None

    # PDF
    if name.endswith(".pdf"):
        try:
            data = await attachment.read()
            import io
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(data))
                text = "\n".join(page.extract_text() or "" for page in reader.pages[:30])
                return text[:15000] if text.strip() else None
            except ImportError:
                # fallback: basic text extraction
                raw = data.decode("latin-1", errors="replace")
                import re as _re
                chunks = _re.findall(r"\(([^)]+)\)", raw)
                return "\n".join(chunks)[:15000] if chunks else None
        except Exception:
            return None

    # docx
    if name.endswith(".docx"):
        try:
            data = await attachment.read()
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
                import re as _re
                text = _re.sub(r"<[^>]+>", " ", xml)
                text = _re.sub(r"\s+", " ", text).strip()
                return text[:15000] if text else None
        except Exception:
            return None

    return None


class AICog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.history: Dict[int, Dict[int, List[Dict[str, str]]]] = {}
        self.cooldowns: Dict[int, float] = {}

    def _get_history(self, guild_id: int, user_id: int) -> List[Dict[str, str]]:
        if guild_id not in self.history:
            self.history[guild_id] = {}
        if user_id not in self.history[guild_id]:
            self.history[guild_id][user_id] = []
        return self.history[guild_id][user_id]

    def _cooldown_ok(self, user_id: int) -> bool:
        now = time.time()
        last = self.cooldowns.get(user_id, 0)
        if now - last < AI_COOLDOWN_SECONDS:
            return False
        self.cooldowns[user_id] = now
        return True

    async def _send_chunked(self, send_func, text: str) -> None:
        if len(text) <= 1900:
            await send_func(text)
        else:
            for idx in range(0, len(text), 1900):
                await send_func(text[idx:idx + 1900])

    @app_commands.command(name="ai", description="Chat with Iroha.")
    async def ai(self, interaction: discord.Interaction, prompt: str) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        cfg = await get_guild_config(interaction.guild.id)
        if not module_enabled(cfg, "ai_enabled", interaction.user.id):
            await interaction.response.send_message("AI module is disabled.", ephemeral=True)
            return
        if bot_ratio_exceeded(interaction.guild, cfg, interaction.user.id):
            await interaction.response.send_message("AI is disabled due to bot ratio guard.", ephemeral=True)
            return
        if not self.bot.ai_client.enabled():
            await interaction.response.send_message("AI is not configured.", ephemeral=True)
            return
        if not self._cooldown_ok(interaction.user.id):
            await interaction.response.send_message("Please wait before using AI again.", ephemeral=True)
            return
        history = self._get_history(interaction.guild.id, interaction.user.id)
        history.append({"role": "user", "content": prompt})
        history[:] = history[-MAX_AI_HISTORY:]
        await interaction.response.defer()
        try:
            result = await self.bot.ai_client.generate(history, interaction.user.id)
        except Exception as exc:
            await interaction.followup.send(f"AI error: {exc}")
            return
        history.append({"role": "assistant", "content": result.text})
        history[:] = history[-MAX_AI_HISTORY:]
        await self._send_chunked(interaction.followup.send, result.text)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        if not self.bot.ai_client.enabled():
            return

        cfg = await get_guild_config(message.guild.id)
        is_mentioned = self.bot.user and self.bot.user.mentioned_in(message)
        ai_channel_id = cfg.get("ai_channel_id")
        in_ai_channel = ai_channel_id and message.channel.id == int(ai_channel_id)

        if not is_mentioned and not in_ai_channel:
            return
        if not cfg.get("ai_enabled"):
            return
        if bot_ratio_exceeded(message.guild, cfg):
            return
        if not self._cooldown_ok(message.author.id):
            return

        prompt = message.content
        if is_mentioned and self.bot.user:
            prompt = prompt.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()

        # inject permission tags
        if message.author.id == OWNER_ID:
            prompt = f"[owner] {prompt}"
        elif isinstance(message.author, discord.Member) and message.author.guild_permissions.administrator:
            prompt = f"[admin] {prompt}"

        if not prompt and not message.attachments:
            return

        # ─── Collect attachments (images + files) ─────────────
        images: List[str] = []
        file_context = ""
        for att in message.attachments:
            ct = att.content_type or ""
            if ct in IMAGE_TYPES:
                b64 = await attachment_to_b64(att)
                if b64:
                    images.append(b64)
            else:
                text = await attachment_to_text(att)
                if text:
                    file_context += f"\n[file: {att.filename}]\n{text}\n"

        if not prompt and not images and not file_context:
            prompt = ""
        if not prompt:
            if images:
                prompt = "what's in this image?"
            elif file_context:
                prompt = "analyze this file"
        if not prompt and not images and not file_context:
            return

        # ─── Fetch URL / GitHub content ──────────────────────
        extra_context = file_context
        urls = URL_PATTERN.findall(prompt)
        for url in urls[:2]:
            if GITHUB_REPO_PATTERN.search(url):
                gh_data = await fetch_github_repo(url)
                if gh_data:
                    extra_context += f"\n[github repo data]:\n{gh_data}\n"
            else:
                text = await fetch_url_text(url)
                if text:
                    extra_context += f"\n[content from {url}]:\n{text}\n"

        # ─── Ask Gemini — AI decides everything ────────────
        history = self._get_history(message.guild.id, message.author.id)
        history.append({"role": "user", "content": prompt})
        history[:] = history[-MAX_AI_HISTORY:]

        async with message.channel.typing():
            try:
                result = await self.bot.ai_client.generate(
                    history, message.author.id,
                    images=images or None,
                    extra_context=extra_context,
                )
            except Exception:
                logging.exception("ai generate error")
                return

        # ─── Handle function call (action) ───────────────────
        if result.action:
            try:
                action_result = await execute_action(
                    self.bot, message, result.action, result.action_args
                )
                if action_result:
                    try:
                        reply = await self.bot.ai_client.followup(
                            history, result.action, action_result, message.author.id
                        )
                    except Exception:
                        reply = action_result

                    if reply:
                        history.append({"role": "assistant", "content": reply})
                        history[:] = history[-MAX_AI_HISTORY:]
                        parts = split_response(reply)
                        await send_human(message.channel, parts, reference=message)
            except Exception:
                logging.exception("action execution error")
            return

        # ─── Normal text response (human-like) ───────────────
        if result.text:
            history.append({"role": "assistant", "content": result.text})
            history[:] = history[-MAX_AI_HISTORY:]
            parts = split_response(result.text)
            await send_human(message.channel, parts, reference=message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AICog(bot))
