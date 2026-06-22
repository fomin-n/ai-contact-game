"""Pure rendering functions: game messages → Telegram HTML.

All user/LLM-generated text is passed through `esc()` before embedding in HTML.
Nothing in this module does I/O or holds state.
"""
from __future__ import annotations

import html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app.schemas import GameMessage, GameState

_ROLE_EMOJI: dict[str, str] = {
    "playerA": "🔵",
    "playerB": "🟢",
    "wordMaster": "🔴",
    "system": "🎮",
}

_ROLE_NAME: dict[str, dict[str, str]] = {
    "en": {
        "playerA": "Player A",
        "playerB": "Player B",
        "wordMaster": "Word Master",
        "system": "Game",
    },
    "ru": {
        "playerA": "Игрок A",
        "playerB": "Игрок B",
        "wordMaster": "Ведущий",
        "system": "Игра",
    },
}

# Emoji for inline system events (non-dialogue, non-prefix).
_EVENT_EMOJI: dict[str, str] = {
    "blocked": "✋",
    "failed-intercept": "🤝",
    "contact-succeeded": "✅",
    "contact-failed": "❌",
    "master-no-guess": "🤷",
    "secret-chosen": "🔒",
}

# Events that carry dialogue content and get their own message.
_DIALOGUE_EVENTS = frozenset({"clue", "master-guess"})

# Events that update the status message (edit in-place).
_STATUS_EVENTS = frozenset({"prefix"})

# Events rendered inline and batched (one system message per burst).
_INLINE_EVENTS = frozenset({
    "blocked", "failed-intercept", "contact-succeeded", "contact-failed",
    "master-no-guess", "secret-chosen", "intended-word", "partner-guess",
})

# Suppressed — game-over is sent separately with an action button.
_SUPPRESS_EVENTS = frozenset({"game-over", "error"})


def esc(text: str) -> str:
    """HTML-escape a string so it cannot inject tags or entities."""
    return html.escape(text, quote=False)


def _role_header(role: str, lang: str) -> str:
    emoji = _ROLE_EMOJI.get(role, "•")
    names = _ROLE_NAME.get(lang) or _ROLE_NAME["en"]
    name = names.get(role, role)
    return f"{emoji} <b>{esc(name)}</b>"


def classify_event(msg: "GameMessage") -> str:
    """Return the rendering category for a message.

    Returns one of: 'dialogue', 'status', 'inline', 'suppress', 'unknown'.
    """
    event_type = (msg.metadata or {}).get("eventType", "")
    if event_type in _DIALOGUE_EVENTS:
        return "dialogue"
    if event_type in _STATUS_EVENTS:
        return "status"
    if event_type in _INLINE_EVENTS:
        return "inline"
    if event_type in _SUPPRESS_EVENTS:
        return "suppress"
    return "inline"  # unknown system events shown compactly


def render_dialogue(msg: "GameMessage", lang: str) -> str:
    """Full dialogue message (clue or WM guess): role header + blockquote."""
    return f"{_role_header(msg.role, lang)}\n<blockquote>{esc(msg.text)}</blockquote>"


def render_inline_event(msg: "GameMessage", lang: str) -> str:  # noqa: ARG001
    """Single compact line for a contact/reveal/system event."""
    event_type = (msg.metadata or {}).get("eventType", "")
    emoji = _EVENT_EMOJI.get(event_type) or _ROLE_EMOJI.get(msg.role, "•")
    return f"{emoji} {esc(msg.text)}"


def render_system_batch(lines: list[str]) -> str:
    """Combine multiple inline event lines into one Telegram message."""
    return "\n".join(lines)


def render_status(snapshot: "GameState", lang: str) -> str:
    """Persistent game status block — sent once and edited in-place."""
    from .i18n import copy as i18n

    turn = f"{snapshot.turnNumber} / {snapshot.maxTurns}"
    lines = [
        f"🎮 <b>{esc(i18n.get('status_game_name', lang))}</b>  ·  "
        f"{esc(i18n.get('status_turn', lang))} {turn}",
        f"{esc(i18n.get('status_prefix', lang))}: <b>{esc(snapshot.currentPrefix)}</b>",
    ]
    if snapshot.usedWords:
        words = snapshot.usedWords[-15:]
        lines.append(
            f"{esc(i18n.get('status_used', lang))}: {', '.join(esc(w) for w in words)}"
        )
    return "\n".join(lines)


def render_prompt_wm_guess(snapshot: "GameState", lang: str) -> str:
    """Input prompt for Word Master to guess the clue word."""
    from .i18n import copy as i18n

    prefix = esc(snapshot.currentPrefix)
    header = f"🔴 <b>{esc(i18n.get('role_word_master', lang))}</b>"
    clue_block = ""
    if snapshot.pendingUserInput and snapshot.pendingUserInput.clue:
        clue_label = esc(i18n.get("prompt_clue_label", lang))
        clue_block = (
            f"\n{clue_label}:\n"
            f"<blockquote>{esc(snapshot.pendingUserInput.clue)}</blockquote>"
        )
    action = esc(i18n.get("prompt_wm_guess_label", lang))
    return f"{header}{clue_block}\n{action} (<b>{prefix}</b>):"


def render_prompt_player_move(snapshot: "GameState", lang: str) -> str:
    """Input prompt for Player A: step 1 — enter the intended word."""
    from .i18n import copy as i18n

    prefix = esc(snapshot.currentPrefix)
    header = f"🔵 <b>{esc(i18n.get('role_player_a', lang))}</b>"
    action = esc(i18n.get("prompt_player_move_label", lang))
    return f"{header}\n{action} <b>{prefix}</b>:"


def render_prompt_partner_guess(snapshot: "GameState", lang: str) -> str:
    """Input prompt for Player A: guess what Player B encoded."""
    from .i18n import copy as i18n

    prefix = esc(snapshot.currentPrefix)
    header = f"🔵 <b>{esc(i18n.get('role_player_a', lang))}</b>"
    clue_block = ""
    if snapshot.pendingUserInput and snapshot.pendingUserInput.clue:
        clue_label = esc(i18n.get("prompt_clue_label", lang))
        clue_block = (
            f"\n{clue_label}:\n"
            f"<blockquote>{esc(snapshot.pendingUserInput.clue)}</blockquote>"
        )
    action = esc(i18n.get("prompt_partner_guess_label", lang))
    return f"{header}{clue_block}\n{action} (<b>{prefix}</b>):"


def render_game_over(snapshot: "GameState", lang: str) -> str:
    """Game-over message with winner, secret word, and stats."""
    from .i18n import copy as i18n

    word = esc(snapshot.secretWord)
    if snapshot.winner == "players":
        header = i18n.get("game_over_players_win", lang, word=word)
    elif snapshot.winner == "wordMaster":
        header = i18n.get("game_over_wm_wins", lang, word=word)
    elif snapshot.finishReason:
        header = i18n.get("game_over_error", lang)
    else:
        header = i18n.get("game_over_unknown", lang)

    stats = i18n.get(
        "game_over_stats", lang,
        turns=snapshot.turnNumber,
        used=len(snapshot.usedWords),
    )
    return f"{header}\n{stats}"
