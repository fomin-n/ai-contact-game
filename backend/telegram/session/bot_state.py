from enum import Enum


class BotState(str, Enum):
    IDLE = "idle"
    SELECTING_LANGUAGE = "selecting_language"
    SELECTING_ROLE = "selecting_role"
    ENTERING_SECRET = "entering_secret"
    GAME_RUNNING = "game_running"
    WAITING_WM_GUESS = "waiting_wm_guess"
    WAITING_INTENDED_WORD = "waiting_intended_word"
    WAITING_CLUE = "waiting_clue"
    WAITING_PARTNER_GUESS = "waiting_partner_guess"
