"""Pure rendering functions: game messages → Telegram HTML.

All user/LLM-generated text is passed through `esc()` before embedding in HTML.
Nothing in this module does I/O or holds state.

Visual language (two main tiers for player speech, plus system):
  - Player/WM speech (clue, WM guess, or revealed word/guess in contact):
    bold role header with emoji and "(LLM)" suffix when AI-controlled, followed
    by the utterance in a <blockquote>.  All three event types share this
    format via _player_block / _dialogue_block.
  - System events (contact result, prefix reveal, errors): single italic line
    with an emoji, no label, no blockquote.
  - System instructions/menus: no label, plain or italic text.
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

_LLM_SUFFIX: dict[str, str] = {"en": " (LLM)", "ru": " (LLM)"}

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

# Events rendered inline — each gets its own message.
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


def _is_llm_role(role: str, human_role: str) -> bool:
    """Return True when the given role is played by an LLM (not a human)."""
    return human_role in ("", "none") or role != human_role


def _actor_name(role: str, lang: str, *, is_llm: bool = True) -> str:
    """Return the display name for a role, with or without the (LLM) suffix."""
    names = _ROLE_NAME.get(lang) or _ROLE_NAME["en"]
    name = names.get(role, role)
    return name + (_LLM_SUFFIX.get(lang, " (LLM)") if is_llm else "")


def _role_header(role: str, lang: str, *, is_llm: bool = True) -> str:
    emoji = _ROLE_EMOJI.get(role, "•")
    return f"{emoji} <b>{esc(_actor_name(role, lang, is_llm=is_llm))}</b>"


def _player_block(role: str, actor: str, text: str) -> str:
    """Shared builder for all player/WM speech: emoji + bold actor + blockquote."""
    emoji = _ROLE_EMOJI.get(role, "•")
    return f"{emoji} <b>{esc(actor)}</b>\n<blockquote>{esc(text)}</blockquote>"


def _dialogue_block(role: str, text: str, lang: str, *, is_llm: bool = True) -> str:
    return _player_block(role, _actor_name(role, lang, is_llm=is_llm), text)


def render_system_text(text: str, lang: str) -> str:  # noqa: ARG001
    """Render a system/instructional string without a role label.

    `text` is treated as plain text and HTML-escaped wholesale — callers must
    not pre-embed HTML tags in it (the i18n copy strings never do).
    """
    return f"<i>{esc(text)}</i>"


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


def render_dialogue(msg: "GameMessage", lang: str, human_role: str = "none") -> str:
    """Full dialogue message (clue or WM guess): role header + blockquote.

    Roles played by an LLM receive a "(LLM)" suffix. The human's own role does not.
    """
    is_llm = _is_llm_role(msg.role, human_role)
    return _dialogue_block(msg.role, msg.text, lang, is_llm=is_llm)


def render_inline_event(
    msg: "GameMessage",
    lang: str,
    human_role: str = "none",
    display_name: str = "",
) -> str:
    """Render a contact-resolution or outcome event.

    Revealed words (intended-word, partner-guess) use the same blockquote
    format as all other player speech so the feed looks consistent.  The
    human player's word shows their display name (or "You" / "Вы").

    Pure system outcomes (contact-succeeded, contact-failed, …) stay as a
    single italic line with an emoji — no role label, no blockquote.
    """
    event_type = (msg.metadata or {}).get("eventType", "")

    if event_type in ("intended-word", "partner-guess"):
        if not _is_llm_role(msg.role, human_role):
            actor = display_name or ("Вы" if lang == "ru" else "You")
        else:
            actor = _actor_name(msg.role, lang, is_llm=True)
        return _player_block(msg.role, actor, msg.text)

    emoji = _EVENT_EMOJI.get(event_type) or _ROLE_EMOJI.get(msg.role, "•")
    return f"<i>{emoji} {esc(msg.text)}</i>"


def is_human_origin(msg: "GameMessage", human_role: str) -> bool:
    """Return True when this message echoes the human player's own submitted dialogue.

    Only dialogue messages (clue, master-guess) should be suppressed — the human
    already sees them as their own Telegram message.  Contact-resolution events
    (intended-word, partner-guess) are intentionally NOT suppressed so the game
    can display the human's word with a proper role label.
    """
    if human_role in ("", "none"):
        return False
    event_type = (msg.metadata or {}).get("eventType", "")
    return msg.role == human_role and event_type in _DIALOGUE_EVENTS


def render_prefix_revealed(prefix: str, lang: str) -> str:
    """Compact inline line showing the newly revealed prefix after contact."""
    label = i18n.get("status_prefix", lang)
    return f"<i>🔤 {esc(label)}: <b>{esc(prefix)}</b></i>"


def render_status(snapshot: "GameState", lang: str) -> str:
    """Persistent game status block — sent once and edited in-place."""
    # maxTurns is 0 only in the brief window before the secret word (and
    # therefore the attempt limit) is known.
    turn = f"{snapshot.turnNumber} / {snapshot.maxTurns}" if snapshot.maxTurns > 0 else f"{snapshot.turnNumber}"
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
    """Render a received clue: actual speaker's header when known, else a generic label.

    The actor is always an LLM in prompt contexts (human can never be the other player).
    """
    if actor:
        header = _role_header(actor, lang, is_llm=True)
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
    parts.append(f"{action} (<code>{prefix}</code>):")
    return "\n\n".join(parts)


def render_prompt_player_move(snapshot: "GameState", lang: str) -> str:
    """Input prompt for Player A: step 1 — enter the intended word."""
    prefix = esc(snapshot.currentPrefix)
    action = esc(i18n.get("prompt_player_move_label", lang))
    return f"{action} (<code>{prefix}</code>):"


def render_prompt_partner_guess(snapshot: "GameState", lang: str) -> str:
    """Input prompt for Player A: guess what Player B encoded."""
    prefix = esc(snapshot.currentPrefix)
    parts = []
    pending = snapshot.pendingUserInput
    if pending and pending.clue:
        parts.append(_clue_block(pending.actingPlayer, pending.clue, lang))
    action = esc(i18n.get("prompt_partner_guess_label", lang))
    parts.append(f"{action} (<code>{prefix}</code>):")
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
        max_turns=snapshot.maxTurns,
        used=len(snapshot.usedWords),
    )
    return f"<b>{header}</b>\n<i>{stats}</i>"
