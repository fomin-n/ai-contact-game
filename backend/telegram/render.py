"""Pure rendering functions: game messages → Telegram HTML.

All user/LLM-generated text is passed through `esc()` before embedding in HTML.
Nothing in this module does I/O or holds state.

Visual language (three tiers, kept visually distinct on purpose):
  - System (instructions, errors, menus): italic "[System]"/"[Система]" label
    on its own line, plain (non-bold) body below. Lightest weight.
  - Dialogue (an actual clue or guess spoken by a player/Word Master): bold
    role header with emoji, followed by the utterance in a <blockquote>.
  - Outcome (contact made/broken, reveals): single italic line with an emoji,
    no label — compact, no blockquote, sits between the two above in weight.
Persistent status (turn/prefix/used words) is sent once and edited in place.
"""
from __future__ import annotations

import html
from typing import TYPE_CHECKING

from .i18n import copy as i18n

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


TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def esc(text: str) -> str:
    """HTML-escape a string so it cannot inject tags or entities."""
    return html.escape(text, quote=False)


def truncate_plain(text: str, limit: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> str:
    """Truncate plain (non-HTML) text to fit Telegram's message length limit.

    Safe to call on already-rendered HTML strings too, but only when they are
    about to be sent as plain-text fallback — truncating mid-tag would produce
    invalid markup, so callers must not pass truncated output back through a
    parse_mode=HTML send.
    """
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _role_header(role: str, lang: str) -> str:
    emoji = _ROLE_EMOJI.get(role, "•")
    names = _ROLE_NAME.get(lang) or _ROLE_NAME["en"]
    name = names.get(role, role)
    return f"{emoji} <b>{esc(name)}</b>"


def _system_label(lang: str) -> str:
    return f"<i>{esc(i18n.get('system_label', lang))}</i>"


def _dialogue_block(role: str, text: str, lang: str) -> str:
    return f"{_role_header(role, lang)}\n<blockquote>{esc(text)}</blockquote>"


def render_system_text(text: str, lang: str) -> str:
    """Wrap a fully-composed system/instructional string with the [System] label.

    `text` is treated as plain text and HTML-escaped wholesale — callers must
    not pre-embed HTML tags in it (the i18n copy strings never do).
    """
    return f"{_system_label(lang)}\n{esc(text)}"


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
    return _dialogue_block(msg.role, msg.text, lang)


def render_inline_event(msg: "GameMessage", lang: str) -> str:  # noqa: ARG001
    """Single compact, lightweight line for a contact/reveal outcome."""
    event_type = (msg.metadata or {}).get("eventType", "")
    emoji = _EVENT_EMOJI.get(event_type) or _ROLE_EMOJI.get(msg.role, "•")
    return f"<i>{emoji} {esc(msg.text)}</i>"


def is_human_origin(msg: "GameMessage", human_role: str) -> bool:
    """Return True when this message echoes the human player's own submitted input.

    The game appends a GameMessage for every move regardless of whether it came
    from an LLM or from human input. Human-originated messages always carry the
    same role as humanRole, so the role match is the only check needed.
    """
    return human_role not in ("", "none") and msg.role == human_role


def render_system_batch(lines: list[str]) -> str:
    """Combine multiple inline event lines into one Telegram message."""
    return "\n".join(lines)


def render_status(snapshot: "GameState", lang: str) -> str:
    """Persistent game status block — sent once and edited in-place."""
    turn = f"{snapshot.turnNumber} / {snapshot.maxTurns}"
    lines = [
        f"🎮 <b>{esc(i18n.get('status_game_name', lang))}</b>  ·  "
        f"{esc(i18n.get('status_turn', lang))} {turn}",
        f"{esc(i18n.get('status_prefix', lang))}: <b>{esc(snapshot.currentPrefix)}</b>",
    ]
    if snapshot.usedWords:
        words = snapshot.usedWords[-15:]
        lines.append(
            f"<i>{esc(i18n.get('status_used', lang))}: "
            f"{', '.join(esc(w) for w in words)}</i>"
        )
    return "\n".join(lines)


def _clue_block(actor: str | None, clue: str, lang: str) -> str:
    """Render a received clue: actual speaker's header when known, else a generic label."""
    if actor:
        header = _role_header(actor, lang)
    else:
        header = f"📨 <b>{esc(i18n.get('prompt_clue_label', lang))}</b>"
    return f"{header}\n<blockquote>{esc(clue)}</blockquote>"


def render_prompt_wm_guess(snapshot: "GameState", lang: str) -> str:
    """Input prompt for Word Master to guess the clue word."""
    prefix = esc(snapshot.currentPrefix)
    parts = []
    pending = snapshot.pendingUserInput
    if pending and pending.clue:
        parts.append(_clue_block(pending.actingPlayer, pending.clue, lang))
    action = esc(i18n.get("prompt_wm_guess_label", lang))
    parts.append(f"{_system_label(lang)}\n{action} (<code>{prefix}</code>):")
    return "\n\n".join(parts)


def render_prompt_player_move(snapshot: "GameState", lang: str) -> str:
    """Input prompt for Player A: step 1 — enter the intended word."""
    prefix = esc(snapshot.currentPrefix)
    action = esc(i18n.get("prompt_player_move_label", lang))
    return f"{_system_label(lang)}\n{action} (<code>{prefix}</code>):"


def render_prompt_partner_guess(snapshot: "GameState", lang: str) -> str:
    """Input prompt for Player A: guess what Player B encoded."""
    prefix = esc(snapshot.currentPrefix)
    parts = []
    pending = snapshot.pendingUserInput
    if pending and pending.clue:
        parts.append(_clue_block(pending.actingPlayer, pending.clue, lang))
    action = esc(i18n.get("prompt_partner_guess_label", lang))
    parts.append(f"{_system_label(lang)}\n{action} (<code>{prefix}</code>):")
    return "\n\n".join(parts)


def render_game_over(snapshot: "GameState", lang: str) -> str:
    """Game-over message with winner, secret word, and stats."""
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
    return f"<b>{header}</b>\n<i>{stats}</i>"
