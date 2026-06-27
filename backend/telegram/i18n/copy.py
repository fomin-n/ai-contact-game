from __future__ import annotations

_COPY: dict[str, dict[str, str]] = {
    "en": {
        "select_language": "Choose a language:",
        "btn_russian": "Русский",
        "btn_english": "English",
        "select_role": "Choose your role:",
        "btn_word_master": "Play as Word Master",
        "btn_player_a": "Play as a Player",
        "btn_ai_vs_ai": "Let LLMs play",
        "enter_secret": "Enter a secret word (single English word, letters only):",
        "thinking": "AI is thinking...",
        "game_started": "Game started!",
        "spectator_game_started": "Spectator mode started! Watching the AIs play. Use /cancel to stop.",
        "daily_game_limit_reached": "You've reached today's limit of {limit} games. Please try again tomorrow.",
        "current_prefix": "Current prefix: {prefix}",
        "wm_guess_prompt": "Your turn, Word Master!\nGuess the encoded word. Prefix: {prefix}",
        "player_move_step1": "Your turn! Enter your intended word (must start with \"{prefix}\"):",
        "player_move_step2": "Now send your encoded clue. Do not include the word \"{word}\" in the clue:",
        "partner_guess_prompt": "Player B's clue: {clue}\n\nGuess the word Player B encoded (must start with \"{prefix}\"):",
        "word_empty": "Word cannot be empty. Try again:",
        "word_too_long": "Word is too long (max 50 characters). Try again:",
        "word_invalid_chars": "Word must contain letters only ({lang_hint}). Try again:",
        "word_wrong_prefix": "Word must start with \"{prefix}\". Try again:",
        "word_already_used": "This word was already used. Try again:",
        "clue_too_long": "Clue is too long (max 500 characters). Try again:",
        "clue_contains_word": "Clue must not include the word \"{word}\". Try again:",
        "clue_empty": "Clue cannot be empty. Try again:",
        "rate_limited": "Please wait a moment before sending again.",
        "game_input_error": "The game did not accept that input: {error}. Try again:",
        "status_no_game": "No active game. Use /newgame to start.",
        "status_template": "Turn: {turn}/{max_turns}\nPrefix: {prefix}\nUsed words: {used_words}",
        "cancel_no_game": "No active game.",
        "cancel_done": "Game cancelled. Use /newgame to start a new game.",
        "game_over_players_win": "Players win! The secret word was: {word}",
        "game_over_wm_wins": "Word Master wins! The secret word was: {word}",
        "game_over_unknown": "Game over. Use /newgame to play again.",
        "game_over_error": "Game stopped due to an error. Use /newgame to try again.",
        "btn_new_game": "New game",
        "private_only": "This bot works in private chats only.",
        "unexpected": "I did not expect a message now. Use /newgame to start a game.",
        "generic_error": "Something went wrong. Use /newgame to start a new game.",
        "role_system": "System",
        "role_player_a": "Player A",
        "role_player_b": "Player B",
        "role_word_master": "Word Master",
        "system_label": "[System]",
        "lang_hint_en": "a-z",
        "lang_hint_ru": "а-я",
        "secret_word_label": "Secret word",
        "used_words_none": "(none)",
        # Render / status message
        "status_game_name": "Contact",
        "status_turn": "Turn",
        "status_prefix": "Prefix",
        "status_used": "Used",
        # Render / pending prompts
        "prompt_clue_label": "Clue",
        "prompt_wm_guess_label": "Guess the encoded word",
        "prompt_player_move_label": "Send an encoded clue for a word starting with",
        "prompt_partner_guess_label": "Guess the word Player B encoded",
        # Render / game over
        "game_over_stats": "Attempts: {turns}/{max_turns}  ·  Words used: {used}",
    },
    "ru": {
        "select_language": "Выберите язык:",
        "btn_russian": "Русский",
        "btn_english": "English",
        "select_role": "Выберите роль:",
        "btn_word_master": "Играть за Ведущего",
        "btn_player_a": "Играть за Игрока",
        "btn_ai_vs_ai": "Пусть LLM играют сами",
        "enter_secret": "Введите секретное слово (одно русское слово, только буквы):",
        "thinking": "AI думает...",
        "game_started": "Игра началась!",
        "spectator_game_started": "Режим наблюдателя запущен! Смотрим, как играют ИИ. /cancel — чтобы остановить.",
        "daily_game_limit_reached": "Вы достигли сегодняшнего лимита в {limit} игр. Попробуйте снова завтра.",
        "current_prefix": "Текущий префикс: {prefix}",
        "wm_guess_prompt": "Ваш ход, Ведущий!\nУгадайте зашифрованное слово. Префикс: {prefix}",
        "player_move_step1": "Ваш ход! Введите задуманное слово (должно начинаться с \"{prefix}\"):",
        "player_move_step2": "Теперь отправьте зашифрованную подсказку. Не включайте слово \"{word}\" в подсказку:",
        "partner_guess_prompt": "Подсказка Игрока B: {clue}\n\nУгадайте слово, которое задумал Игрок B (должно начинаться с \"{prefix}\"):",
        "word_empty": "Слово не может быть пустым. Попробуйте ещё раз:",
        "word_too_long": "Слово слишком длинное (максимум 50 символов). Попробуйте ещё раз:",
        "word_invalid_chars": "Слово должно содержать только буквы ({lang_hint}). Попробуйте ещё раз:",
        "word_wrong_prefix": "Слово должно начинаться с \"{prefix}\". Попробуйте ещё раз:",
        "word_already_used": "Это слово уже использовалось. Попробуйте ещё раз:",
        "clue_too_long": "Подсказка слишком длинная (максимум 500 символов). Попробуйте ещё раз:",
        "clue_contains_word": "Подсказка не должна содержать слово \"{word}\". Попробуйте ещё раз:",
        "clue_empty": "Подсказка не может быть пустой. Попробуйте ещё раз:",
        "rate_limited": "Подождите немного перед следующей отправкой.",
        "game_input_error": "Игра не приняла этот ввод: {error}. Попробуйте ещё раз:",
        "status_no_game": "Нет активной игры. Используйте /newgame для начала.",
        "status_template": "Ход: {turn}/{max_turns}\nПрефикс: {prefix}\nИспользованные слова: {used_words}",
        "cancel_no_game": "Нет активной игры.",
        "cancel_done": "Игра отменена. Используйте /newgame для новой игры.",
        "game_over_players_win": "Игроки победили! Секретное слово: {word}",
        "game_over_wm_wins": "Ведущий победил! Секретное слово: {word}",
        "game_over_unknown": "Игра окончена. Используйте /newgame для новой игры.",
        "game_over_error": "Игра остановлена из-за ошибки. Используйте /newgame для повторной попытки.",
        "btn_new_game": "Новая игра",
        "private_only": "Этот бот работает только в личных чатах.",
        "unexpected": "Я не ожидал сообщения сейчас. Используйте /newgame для начала игры.",
        "generic_error": "Что-то пошло не так. Используйте /newgame для новой игры.",
        "role_system": "Система",
        "role_player_a": "Игрок A",
        "role_player_b": "Игрок B",
        "role_word_master": "Ведущий",
        "system_label": "[Система]",
        "lang_hint_en": "a-z",
        "lang_hint_ru": "а-я",
        "secret_word_label": "Секретное слово",
        "used_words_none": "(нет)",
        # Render / status message
        "status_game_name": "Есть контакт",
        "status_turn": "Ход",
        "status_prefix": "Префикс",
        "status_used": "Слова",
        # Render / pending prompts
        "prompt_clue_label": "Подсказка",
        "prompt_wm_guess_label": "Угадайте зашифрованное слово",
        "prompt_player_move_label": "Отправьте зашифрованную подсказку для слова на",
        "prompt_partner_guess_label": "Угадайте слово Игрока B",
        # Render / game over
        "game_over_stats": "Попыток: {turns}/{max_turns}  ·  Слов использовано: {used}",
    },
}


def get(key: str, lang: str = "en", **kwargs: object) -> str:
    lang = lang if lang in _COPY else "en"
    text = _COPY[lang].get(key) or _COPY["en"].get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


# Bilingual rules message — language-agnostic, always shows Russian then English.
# Sent as HTML directly (not through reply_system / render_system_text).
RULES_HTML: str = (
    "<b>🟢 Есть контакт</b>\n"
    "\n"
    "Ведущий загадывает секретное слово и открывает его по одной букве за ход.\n"
    "Игроки угадывают его, обмениваясь зашифрованными подсказками.\n"
    "\n"
    "🤝 Контакт установлен → открывается следующая буква.\n"
    "✋ Ведущий перехватил подсказку → контакт оборван.\n"
    "🏆 Угадали слово полностью → игроки победили.\n"
    "⌛ Лимит попыток исчерпан → победил Ведущий.\n"
    "\n"
    "<i>Лимит: 3 попытки на каждую букву, кроме первой (она открывается сразу).</i>\n"
    "\n"
    "<b>Команды</b>\n"
    "/start · /newgame — новая игра\n"
    "/rules — правила игры\n"
    "/status — статус игры\n"
    "/cancel — отменить игру\n"
    "\n"
    "--\n"
    "\n"
    "<b>🟢 Contact</b>\n"
    "\n"
    "The Word Master picks a secret word and reveals it one letter per turn.\n"
    "Players try to guess it by exchanging encoded clues.\n"
    "\n"
    "🤝 Players make contact → next letter is revealed.\n"
    "✋ Word Master intercepts a clue → contact is broken.\n"
    "🏆 Players guess the full word → players win.\n"
    "⌛ Attempt limit reached → Word Master wins.\n"
    "\n"
    "<i>Limit: 3 attempts per letter after the first (already revealed).</i>\n"
    "\n"
    "<b>Commands</b>\n"
    "/start · /newgame — new game\n"
    "/rules — show these rules\n"
    "/status — current game status\n"
    "/cancel — cancel current game"
)

RULES_PLAIN: str = (
    "🟢 Есть контакт\n"
    "\n"
    "Ведущий загадывает секретное слово и открывает его по одной букве за ход.\n"
    "Игроки угадывают его, обмениваясь зашифрованными подсказками.\n"
    "\n"
    "🤝 Контакт установлен → открывается следующая буква.\n"
    "✋ Ведущий перехватил подсказку → контакт оборван.\n"
    "🏆 Угадали слово полностью → игроки победили.\n"
    "⌛ Лимит попыток исчерпан → победил Ведущий.\n"
    "\n"
    "Лимит: 3 попытки на каждую букву, кроме первой (она открывается сразу).\n"
    "\n"
    "Команды\n"
    "/start · /newgame — новая игра\n"
    "/rules — правила игры\n"
    "/status — статус игры\n"
    "/cancel — отменить игру\n"
    "\n"
    "--\n"
    "\n"
    "🟢 Contact\n"
    "\n"
    "The Word Master picks a secret word and reveals it one letter per turn.\n"
    "Players try to guess it by exchanging encoded clues.\n"
    "\n"
    "🤝 Players make contact → next letter is revealed.\n"
    "✋ Word Master intercepts a clue → contact is broken.\n"
    "🏆 Players guess the full word → players win.\n"
    "⌛ Attempt limit reached → Word Master wins.\n"
    "\n"
    "Limit: 3 attempts per letter after the first (already revealed).\n"
    "\n"
    "Commands\n"
    "/start · /newgame — new game\n"
    "/rules — show these rules\n"
    "/status — current game status\n"
    "/cancel — cancel current game"
)
