"""
Human-like message sending: split AI response into multiple messages with typing delays.
"""
from __future__ import annotations

import asyncio
import random
import logging
from typing import List

import discord


def split_response(text: str) -> List[str]:
    """Split AI response by [s] delimiter. Strips empty parts."""
    if "[s]" not in text:
        return [text.strip()] if text.strip() else []
    parts = [p.strip() for p in text.split("[s]")]
    return [p for p in parts if p]


def calc_delay(text: str) -> float:
    """Calculate typing delay based on message length. Feels like actually typing."""
    length = len(text)
    if length <= 5:
        return random.uniform(1.0, 1.8)
    if length <= 20:
        return random.uniform(1.8, 3.0)
    if length <= 60:
        return random.uniform(2.5, 4.5)
    if length <= 150:
        return random.uniform(3.5, 5.5)
    return random.uniform(4.5, 7.0)


async def _send_with_retry(coro, retries: int = 3):
    """Retry on 503/5xx Discord errors."""
    for attempt in range(retries):
        try:
            return await coro
        except discord.DiscordServerError:
            if attempt < retries - 1:
                await asyncio.sleep(1 + attempt)
            else:
                logging.warning("discord 5xx after retries, skipping message")
        except Exception:
            logging.exception("send error")
            break


async def send_human(
    channel: discord.TextChannel | discord.Thread,
    parts: List[str],
    reference: discord.Message | None = None,
) -> None:
    """Send multiple messages with typing delays, like a human chatting."""
    for i, text in enumerate(parts):
        if not text:
            continue

        chunks = []
        while text:
            if len(text) <= 1900:
                chunks.append(text)
                break
            cut = text[:1900].rfind("\n")
            if cut < 100:
                cut = 1900
            chunks.append(text[:cut])
            text = text[cut:].lstrip()

        for j, chunk in enumerate(chunks):
            delay = calc_delay(chunk)
            try:
                async with channel.typing():
                    await asyncio.sleep(delay)
            except Exception:
                await asyncio.sleep(delay)

            if i == 0 and j == 0 and reference:
                await _send_with_retry(reference.reply(chunk, mention_author=False))
            else:
                await _send_with_retry(channel.send(chunk))
