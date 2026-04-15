from __future__ import annotations

from typing import Dict

MESSAGES: Dict[str, Dict[str, str]] = {
    "en": {
        "setup_done": "Setup complete.",
        "setup_channels_done": "Channels updated.",
        "setup_language_done": "Language updated.",
        "no_permission": "You do not have permission to use this command.",
        "module_disabled": "This module is disabled in this server.",
        "cooldown": "Please slow down and try again in a few seconds.",
        "ai_not_configured": "AI is not configured. Ask the admin to add an API key.",
        "music_not_connected": "I'm not connected to a voice channel.",
        "queue_empty": "The queue is empty.",
        "invalid_duration": "Invalid duration format.",
        "poll_created": "Poll created.",
        "ticket_created": "Ticket created.",
        "ticket_closed": "Ticket closed.",
        "role_menu_created": "Role menu created.",
    },
}


def t(locale: str, key: str, **kwargs: str) -> str:
    lang = MESSAGES.get(locale) or MESSAGES["en"]
    text = lang.get(key) or MESSAGES["en"].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
