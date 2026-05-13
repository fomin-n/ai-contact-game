import type { Language } from "../types/game";

export const rulesCopy = {
  en: {
    title: "Rules",
    intro: "Contact is a word guessing game with one Word Master and two guessing players.",
    steps: [
      "The Word Master secretly chooses a common word and reveals only its first letter.",
      "Players give cryptic clues for other words that start with the current revealed prefix.",
      "The Word Master tries to intercept the clue by guessing that word first.",
      "If the partner understands the clue and both player words match, contact succeeds and the next secret-word letter is revealed.",
      "The players win when they explicitly name the secret word. The Word Master wins if the turn limit is reached."
    ],
    close: "Close"
  },
  ru: {
    title: "Правила",
    intro:
      "«Контакт» — словесная игра, где есть ведущий и игроки, " +
      "отгадывающие слово.",
    steps: [
      "Ведущий загадывает обычное слово и открывает только первую букву.",
      "Игроки дают хитрые подсказки к другим словам, которые начинаются " +
        "с текущего открытого префикса.",
      "Ведущий пытается перехватить подсказку и первым угадать это слово.",
      "Если второй игрок понял подсказку и слова игроков совпали, " +
        "контакт состоялся и открывается следующая буква секретного слова.",
      "Игроки побеждают, если называют секретное слово. Ведущий побеждает, " +
        "если закончились ходы."
    ],
    close: "Закрыть"
  }
} satisfies Record<Language, { title: string; intro: string; steps: string[]; close: string }>;

export const copy = {
  en: {
    title: "AI «Contact» game",
    subtitle: "Whatch LLMs playing «Contact» game",
    language: "Language",
    english: "English",
    russian: "Russian",
    playerA: "Player A",
    playerB: "Player B",
    wordMaster: "Word Master",
    system: "System",
    personalityA: "Player A personality",
    personalityB: "Player B personality",
    gameMode: "Mode",
    modeNone: "Watch AI vs AI",
    modeWordMaster: "Play as Word Master",
    modePlayerA: "Play as Player A",
    start: "Let them play",
    reset: "Reset game",
    secretWord: "Secret word",
    optionalSecretWord: "Secret word",
    optionalSecretWordPlaceholder: "Leave empty for Word Master",
    optionalSecretWordHint: "Optional. If set, Word Master uses this as the hidden word.",
    requiredSecretWordHint: "Required when you play as Word Master.",
    hiddenSecretWordHint: "Hidden when you play as Player A.",
    currentPrefix: "Current prefix",
    turn: "Turn",
    actingPlayer: "Acting player",
    usedWords: "Used words",
    emptyUsedWords: "No used words yet",
    timeline: "Timeline",
    idle: "Ready",
    running: "Running",
    finished: "Finished",
    winner: "Winner",
    players: "Players",
    aiProvider: "AI provider",
    wordMasterModel: "Word Master model",
    playerAModel: "Player A model",
    playerBModel: "Player B model",
    rules: "Rules",
    apiKeyMissing: "One or more AI provider API keys are missing. Set the required key variables and restart the backend.",
    intendedWord: "Intended word",
    intendedWordPlaceholder: "Intended word",
    encryptedClue: "Encrypted clue",
    encryptedCluePlaceholder: "Encrypted clue",
    submit: "Submit",
    submitting: "Submitting..."
  },
  ru: {
    title: "AI «Есть контакт»",
    subtitle: "LLM играют в «Есть контакт»",
    language: "Язык",
    english: "English",
    russian: "Русский",
    playerA: "Игрок A",
    playerB: "Игрок B",
    wordMaster: "Ведущий",
    system: "Система",
    personalityA: "Характер Игрока A",
    personalityB: "Характер Игрока B",
    gameMode: "Режим",
    modeNone: "Смотреть AI vs AI",
    modeWordMaster: "Играть за ведущего",
    modePlayerA: "Играть за Игрока A",
    start: "Начать игру",
    reset: "Сбросить",
    secretWord: "Секретное слово",
    optionalSecretWord: "Секретное слово",
    optionalSecretWordPlaceholder: "Оставьте пустым для ведущего",
    optionalSecretWordHint: "Необязательно. Если задано, ведущий играет с этим словом.",
    requiredSecretWordHint: "Обязательно, если вы играете за ведущего.",
    hiddenSecretWordHint: "Скрыто, когда вы играете за Игрока A.",
    currentPrefix: "Открытый префикс",
    turn: "Ход",
    actingPlayer: "Ходит",
    usedWords: "Использованные слова",
    emptyUsedWords: "Пока нет использованных слов",
    timeline: "Хронология",
    idle: "Готово",
    running: "Игра идет",
    finished: "Завершено",
    winner: "Победитель",
    players: "Игроки",
    aiProvider: "AI-провайдер",
    wordMasterModel: "Модель ведущего",
    playerAModel: "Модель Игрока A",
    playerBModel: "Модель Игрока B",
    rules: "Правила",
    apiKeyMissing:
      "Не задан один или несколько API-ключей AI-провайдеров. " +
      "Укажите нужные переменные и перезапустите сервер.",
    intendedWord: "Задуманное слово",
    intendedWordPlaceholder: "Задуманное слово",
    encryptedClue: "Зашифрованная подсказка",
    encryptedCluePlaceholder: "Зашифрованная подсказка",
    submit: "Отправить",
    submitting: "Отправка..."
  }
} satisfies Record<Language, Record<string, string>>;

export type UiCopy = Record<keyof (typeof copy)["en"], string>;
export type RulesCopy = { title: string; intro: string; steps: string[]; close: string };
