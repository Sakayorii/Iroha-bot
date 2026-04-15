<p align="center">
  <img src="[https://i.imgur.com/placeholder.png](https://i.pinimg.com/originals/a4/d9/67/a4d96725b69443f310f0d089dccdd444.jpg)" width="120" />
</p>

<h1 align="center">Iroha</h1>
<p align="center">
  <b>discord bot that acts like your friend, not your assistant.</b><br>
  ai-powered, talks like a real person, does things when you ask nicely (or not).
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/discord.py-2.3+-5865F2?style=flat-square" />
  <img src="https://img.shields.io/badge/ai-groq%20%2F%20llama-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/license-mit-green?style=flat-square" />
</p>

---

## what is this

iroha is a discord bot with personality. she talks in lowercase, uses slang, occasionally swears, and actually understands what you want.

she's not another boring "how can i help you today?" bot. she's the friend who happens to be an AI.

## features

**ai chat**
- ping her, she responds. natural conversation with memory.
- reads images, PDFs, code files, docx — send any attachment.
- fetches URLs and analyzes GitHub repos on the fly.
- web search when she needs real-time info.
- human-like messaging — types with delays, splits messages naturally.

**action-by-talk**
- "play blue tequila" → joins voice, plays the song.
- "skip" → vote skip (50% threshold) or owner instant skip.
- "tạo giveaway nitro 1h" → creates a giveaway.
- "xóa 50 tin nhắn" → purges messages.
- "timeout thằng kia 10m" → timeouts a user.
- AI decides what's an action vs just chatting. no false triggers.

**music** (yt-dlp + FFmpeg)
- youtube, soundcloud, direct URLs.
- queue, loop, now playing with controls.
- vote skip system — owner bypasses everything.
- auto-leave after 3 min idle.

**image generation**
- "vẽ con mèo" → generates via Pollinations.ai (free, FLUX model).

**leveling & economy**
- XP from messages + voice.
- leaderboard with medals, paginated.
- daily tasks, shop, inventory.
- profile cards (PIL-generated images).

**moderation**
- anti-spam, anti-raid, anti-invite, anti-link, anti-NSFW.
- warnings, blocked words, mass mention detection.
- `/purge` — deletes messages including >14 days old.
- action-by-talk: timeout, kick via natural language.

**giveaway & polls**
- giveaways with join/leave buttons, winner celebration.
- polls with visual vote bars and percentages.

**more**
- welcome/goodbye/boost embeds with avatars.
- ticket system with close button.
- verification with 6-digit codes.
- role menus, reminders, birthdays, events, AFK.
- games: fishing, pokemon, trivia, typing.

**girlfriend mode** (owner only)
- she's different with you. that's all you need to know.

## setup

```bash
# clone
git clone https://github.com/your-repo/iroha-bot.git
cd iroha-bot

# install
pip install -r requirements.txt

# configure
# create .env with:
# DISCORD_TOKEN=your_token
# OWNER_ID=your_discord_id
# AI_API_KEY=your_groq_key (free @ console.groq.com)
# AI_BASE_URL=https://api.groq.com/openai/v1
# AI_MODEL=llama-3.3-70b-versatile
# AI_VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct

# install ffmpeg (for music)
winget install Gyan.FFmpeg  # windows
# or: sudo apt install ffmpeg  # linux

# run
python main.py
```

## tech stack

| what | how |
|------|-----|
| runtime | python 3.12+ |
| discord | discord.py 2.3+ |
| ai chat | groq API (llama 3.3 70B) |
| ai vision | groq (llama 4 scout) |
| image gen | pollinations.ai (FLUX) |
| music | yt-dlp + FFmpeg |
| database | SQLite + aiosqlite |
| profile cards | PIL/Pillow |

## api provider flexibility

iroha uses OpenAI-compatible API format. switch providers by changing `.env`:

```bash
# groq (free)
AI_BASE_URL=https://api.groq.com/openai/v1

# grok (xAI)
AI_BASE_URL=https://api.x.ai/v1

# openai
AI_BASE_URL=https://api.openai.com/v1

# any openai-compatible provider
AI_BASE_URL=https://your-provider.com/v1
```

## structure

```
cogs/           # 20 feature modules
utils/          # ai client, action handler, card drawer, web tools, etc
data/           # sqlite db + cache (gitignored)
main.py         # entry point
config.py       # env loader
db.py           # database layer
```

## credits

built with sleep deprivation and claude code.

---

<p align="center">
  <i>nah ko ns đc. bí mật.</i>
</p>
