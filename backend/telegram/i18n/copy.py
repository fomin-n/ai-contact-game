from __future__ import annotations

_COPY: dict[str, dict[str, str]] = {
    "en": {
        "select_language": "Choose a language:",
        "btn_russian": "Русский",
        "btn_english": "English",
        "select_role": "Choose your role:",
        "btn_word_master": "Play as Word Master",
        "btn_player_a": "Play as a Player",
        "enter_secret": "Enter a secret word (single English word, letters only):",
        "thinking": "AI is thinking...",
        "game_started": "Game started!",
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
        "rules": (
            "Contact\n\n"
            "The Word Master chooses a secret word and reveals it letter by letter.\n"
            "Players try to guess it by exchanging encoded clues.\n"
            "If the Word Master intercepts a clue, contact is broken.\n"
            "If players make contact, the next letter is revealed.\n"
            "Players win by guessing the full secret word.\n\n"
            "Commands:\n"
            "/start or /newgame - new game\n"
            "/rules - show these rules\n"
            "/status - current game status\n"
            "/cancel - cancel current game"
        ),
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
        "lang_hint_en": "a-z",
        "lang_hint_ru": "а-я",
        "secret_word_label": "Secret word",
        "used_words_none": "(none)",
        "auth_required_welcome": (
            "Welcome to AI Contact Game \U0001f7e2 (beta).\n\n"
            "Access is currently restricted to invited users.\n\n"
            "Authenticate with:\n"
            "  /login <access_code>\n\n"
            "Contact the administrator if you need a code."
        ),
        "auth_required_brief": "Access required. Use /login <access_code> to authenticate.",
        "login_usage": "Please provide your access code: /login <access_code>",
        "login_success": "Access granted! Use /newgame to start playing.",
        "login_already_authorized": "You are already authorized. Use /newgame to start a game.",
        "login_invalid": "Invalid or already used code. Check the code and try again.",
    },
    "ru": {
        "select_language": "Выберите язык:",
        "btn_russian": "Русский",
        "btn_english": "English",
        "select_role": "Выберите роль:",
        "btn_word_master": "Играть за Ведущего",
        "btn_player_a": "Играть за Игрока",
        "enter_secret": "Введите секретное слово (одно русское слово, только буквы):",
        "thinking": "AI думает...",
        "game_started": "Игра началась!",
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
        "rules": (
            "Есть контакт\n\n"
            "Ведущий загадывает слово и открывает его по одной букве.\n"
            "Игроки пытаются угадать его, обмениваясь зашифрованными подсказками.\n"
            "Если Ведущий перехватывает подсказку, контакт оборван.\n"
            "Если игроки устанавливают контакт, открывается следующая буква.\n"
            "Игроки побеждают, угадав секретное слово целиком.\n\n"
            "Команды:\n"
            "/start или /newgame - новая игра\n"
            "/rules - правила игры\n"
            "/status - текущий статус\n"
            "/cancel - отменить игру"
        ),
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
        "lang_hint_en": "a-z",
        "lang_hint_ru": "а-я",
        "secret_word_label": "Секретное слово",
        "used_words_none": "(нет)",
        "auth_required_welcome": (
            "Добро пожаловать в AI Contact Game \U0001f7e2 (бета).\n\n"
            "Доступ ограничен приглашёнными пользователями.\n\n"
            "Аутентифицируйтесь командой:\n"
            "  /login <код_доступа>\n\n"
            "Обратитесь к администратору, если у вас нет кода."
        ),
        "auth_required_brief": "Доступ закрыт. Используйте /login <код_доступа> для входа.",
        "login_usage": "Укажите код доступа: /login <код_доступа>",
        "login_success": "Доступ разрешён! Используйте /newgame для начала игры.",
        "login_already_authorized": "Вы уже авторизованы. Используйте /newgame для начала игры.",
        "login_invalid": "Неверный или уже использованный код. Проверьте код и попробуйте снова.",
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
