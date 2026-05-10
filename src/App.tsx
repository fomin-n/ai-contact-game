import { useEffect, useMemo, useRef, useState } from "react";
import { getConfig, getGameState, resetGame as resetGameApi, startGame as startGameApi } from "./lib/api";
import type { GameState, Language, PlayerRole, ProviderInfo, Role } from "./lib/gameTypes";

const DEFAULT_MAX_TURNS = 50;

const initialProviderInfo: ProviderInfo = {
  provider: "mistral",
  displayName: "Mistral",
  hasApiKey: false,
  models: {
    wordMasterModel: "mistral-small-latest",
    playerAModel: "mistral-small-latest",
    playerBModel: "mistral-small-latest"
  },
  providers: {
    wordMasterProvider: "mistral",
    wordMasterDisplayName: "Mistral",
    wordMasterHasApiKey: false,
    playerAProvider: "mistral",
    playerADisplayName: "Mistral",
    playerAHasApiKey: false,
    playerBProvider: "mistral",
    playerBDisplayName: "Mistral",
    playerBHasApiKey: false
  }
};

const defaultPersonalities: Record<Language, Record<PlayerRole, string>> = {
  en: {
    playerA: "Playful, metaphor-loving, a little theatrical, but concise.",
    playerB: "Sharp, practical, and good at noticing everyday associations."
  },
  ru: {
    playerA: "Игривый, образный, немного театральный, но краткий.",
    playerB: "Внимательный, практичный, хорошо угадывает бытовые ассоциации."
  }
};

const rulesCopy = {
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
    intro: "«Контакт» — словесная игра, где есть ведущий и игроки, отгадывающие слово.",
    steps: [
      "Ведущий загадывает обычное слово и открывает только первую букву.",
      "Игроки дают хитрые подсказки к другим словам, которые начинаются с текущего открытого префикса.",
      "Ведущий пытается перехватить подсказку и первым угадать это слово.",
      "Если второй игрок понял подсказку и слова игроков совпали, контакт состоялся и открывается следующая буква секретного слова.",
      "Игроки побеждают, если называют секретное слово. Ведущий побеждает, если закончились ходы."
    ],
    close: "Закрыть"
  }
} satisfies Record<Language, { title: string; intro: string; steps: string[]; close: string }>;

const copy = {
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
    start: "Let them play",
    reset: "Reset game",
    secretWord: "Secret word",
    optionalSecretWord: "Secret word",
    optionalSecretWordPlaceholder: "Leave empty for Word Master",
    optionalSecretWordHint: "Optional. If set, Word Master uses this as the hidden word.",
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
    apiKeyMissing: "One or more AI provider API keys are missing. Set the required key variables and restart the backend."
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
    start: "Начать игру",
    reset: "Сбросить",
    secretWord: "Секретное слово",
    optionalSecretWord: "Секретное слово",
    optionalSecretWordPlaceholder: "Оставьте пустым для ведущего",
    optionalSecretWordHint: "Необязательно. Если задано, ведущий играет с этим словом.",
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
    apiKeyMissing: "Не задан один или несколько API-ключей AI-провайдеров. Укажите нужные переменные и перезапустите сервер."
  }
} satisfies Record<Language, Record<string, string>>;

function createEmptyState(language: Language, providerInfo: ProviderInfo): GameState {
  return {
    status: "idle",
    language,
    secretWord: "",
    currentPrefix: "",
    revealedLength: 0,
    usedWords: [],
    messages: [],
    currentTurn: "playerA",
    turnNumber: 1,
    maxTurns: DEFAULT_MAX_TURNS,
    playerAPersonality: defaultPersonalities[language].playerA,
    playerBPersonality: defaultPersonalities[language].playerB,
    providerInfo
  };
}

function playerLabel(language: Language, role: PlayerRole): string {
  return role === "playerA" ? copy[language].playerA : copy[language].playerB;
}

function roleLabel(language: Language, role: Role): string {
  if (role === "playerA" || role === "playerB") return playerLabel(language, role);
  return role === "wordMaster" ? copy[language].wordMaster : copy[language].system;
}

function App() {
  const [language, setLanguage] = useState<Language>("en");
  const [playerAPersonality, setPlayerAPersonality] = useState(defaultPersonalities.en.playerA);
  const [playerBPersonality, setPlayerBPersonality] = useState(defaultPersonalities.en.playerB);
  const [customSecretWord, setCustomSecretWord] = useState("");
  const [providerInfo, setProviderInfo] = useState<ProviderInfo>(initialProviderInfo);
  const [game, setGame] = useState<GameState>(() => createEmptyState("en", initialProviderInfo));
  const [isRequesting, setIsRequesting] = useState(false);
  const [isRulesOpen, setIsRulesOpen] = useState(false);
  const [uiError, setUiError] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const visibleLabels = copy[game.language];
  const inputLabels = copy[language];
  const activeRules = rulesCopy[language];
  const statusLabel = useMemo(() => visibleLabels[game.status], [game.status, visibleLabels]);
  const activeProviderInfo = game.providerInfo ?? providerInfo;

  useEffect(() => {
    let cancelled = false;

    async function loadInitialState() {
      try {
        const [config, state] = await Promise.all([getConfig(), getGameState()]);
        if (cancelled) return;
        setProviderInfo(config.providerInfo);
        setGame(state);
        setLanguage(state.language);
        setPlayerAPersonality(state.playerAPersonality || defaultPersonalities[state.language].playerA);
        setPlayerBPersonality(state.playerBPersonality || defaultPersonalities[state.language].playerB);
      } catch (error) {
        if (!cancelled) {
          setUiError(error instanceof Error ? error.message : String(error));
        }
      }
    }

    loadInitialState();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (game.status !== "running") return;
    let cancelled = false;

    async function refreshState() {
      try {
        const state = await getGameState();
        if (!cancelled) {
          setGame(state);
          setUiError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setUiError(error instanceof Error ? error.message : String(error));
        }
      }
    }

    const interval = window.setInterval(refreshState, 600);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [game.status]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [game.messages.length]);

  function handleLanguageChange(nextLanguage: Language) {
    setLanguage(nextLanguage);
    setPlayerAPersonality(defaultPersonalities[nextLanguage].playerA);
    setPlayerBPersonality(defaultPersonalities[nextLanguage].playerB);
    setCustomSecretWord("");
    if (game.status === "idle") {
      setGame(createEmptyState(nextLanguage, activeProviderInfo));
    }
  }

  async function startGame() {
    setIsRequesting(true);
    setUiError(null);
    try {
      const state = await startGameApi({
        language,
        playerAPersonality,
        playerBPersonality,
        secretWord: customSecretWord.trim() || undefined,
        maxTurns: DEFAULT_MAX_TURNS
      });
      setGame(state);
    } catch (error) {
      setUiError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsRequesting(false);
    }
  }

  async function resetGame() {
    setIsRequesting(true);
    setUiError(null);
    try {
      const state = await resetGameApi();
      setGame(state);
    } catch (error) {
      setUiError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsRequesting(false);
    }
  }

  const isRunning = game.status === "running";

  return (
    <main className="app-shell">
      <section className="intro">
        <div>
          <h1>{inputLabels.title}</h1>
          <p>{inputLabels.subtitle}</p>
        </div>
        <div className="intro-actions">
          <button
            className="rules-button"
            type="button"
            aria-haspopup="dialog"
            aria-expanded={isRulesOpen}
            onClick={() => setIsRulesOpen(true)}
          >
            {inputLabels.rules}
          </button>
          <span className={`status-pill ${game.status}`}>{statusLabel}</span>
        </div>
      </section>

      {isRulesOpen && (
        <div className="rules-backdrop" role="presentation" onClick={() => setIsRulesOpen(false)}>
          <section
            className="rules-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="rules-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <h2 id="rules-title">{activeRules.title}</h2>
              <button type="button" onClick={() => setIsRulesOpen(false)}>
                {activeRules.close}
              </button>
            </header>
            <p>{activeRules.intro}</p>
            <ol>
              {activeRules.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </section>
        </div>
      )}

      <section className="game-board">
        <aside className="side-column">
          <form className="panel controls" onSubmit={(event) => event.preventDefault()}>
            <label className="field">
              <span>{inputLabels.language}</span>
              <select
                value={language}
                onChange={(event) => handleLanguageChange(event.target.value as Language)}
                disabled={isRunning || isRequesting}
              >
                <option value="en">{inputLabels.english}</option>
                <option value="ru">{inputLabels.russian}</option>
              </select>
            </label>

            <label className="field">
              <span>{inputLabels.optionalSecretWord}</span>
              <input
                value={customSecretWord}
                onChange={(event) => setCustomSecretWord(event.target.value)}
                disabled={isRunning || isRequesting}
                placeholder={inputLabels.optionalSecretWordPlaceholder}
                autoComplete="off"
              />
              <small>{inputLabels.optionalSecretWordHint}</small>
            </label>

            <label className="field">
              <span>{inputLabels.personalityA}</span>
              <textarea
                value={playerAPersonality}
                onChange={(event) => setPlayerAPersonality(event.target.value)}
                disabled={isRunning || isRequesting}
                rows={4}
              />
            </label>

            <label className="field">
              <span>{inputLabels.personalityB}</span>
              <textarea
                value={playerBPersonality}
                onChange={(event) => setPlayerBPersonality(event.target.value)}
                disabled={isRunning || isRequesting}
                rows={4}
              />
            </label>

            <div className="button-row">
              <button className="primary" type="button" onClick={startGame} disabled={isRunning || isRequesting}>
                {inputLabels.start}
              </button>
              <button type="button" onClick={resetGame} disabled={isRequesting}>
                {inputLabels.reset}
              </button>
            </div>
          </form>

          <section className="panel model-panel" aria-label="Agent models">
            <div className="model-row">
              <span>{visibleLabels.wordMasterModel}</span>
              <strong>
                {activeProviderInfo.providers.wordMasterDisplayName} / {activeProviderInfo.models.wordMasterModel}
              </strong>
            </div>
            <div className="model-row">
              <span>{visibleLabels.playerAModel}</span>
              <strong>
                {activeProviderInfo.providers.playerADisplayName} / {activeProviderInfo.models.playerAModel}
              </strong>
            </div>
            <div className="model-row">
              <span>{visibleLabels.playerBModel}</span>
              <strong>
                {activeProviderInfo.providers.playerBDisplayName} / {activeProviderInfo.models.playerBModel}
              </strong>
            </div>
          </section>

          {(!activeProviderInfo.hasApiKey || uiError) && (
            <section className={`notice ${uiError ? "error" : ""}`}>
              {uiError || visibleLabels.apiKeyMissing}
            </section>
          )}

          <section className="panel used-words-panel">
            <header>
              <h2>{visibleLabels.usedWords}</h2>
              <span>{game.usedWords.length}</span>
            </header>
            {game.usedWords.length ? (
              <div className="chips">
                {game.usedWords.map((word) => (
                  <span className="chip" key={word}>
                    {word}
                  </span>
                ))}
              </div>
            ) : (
              <p className="muted">{visibleLabels.emptyUsedWords}</p>
            )}
          </section>
        </aside>

        <section className="panel timeline-panel main-column">
          <div className="chat-status" aria-label="Game status">
            <div className="chat-stat secret-chat-stat">
              <span>{visibleLabels.secretWord}</span>
              <strong>{game.secretWord || "..."}</strong>
            </div>
            <div className="chat-stat prefix-chat-stat">
              <span>{visibleLabels.currentPrefix}</span>
              <strong>{game.currentPrefix || "..."}</strong>
            </div>
            <div className="chat-stat turn-chat-stat">
              <span>{visibleLabels.turn}</span>
              <strong>{game.turnNumber}</strong>
            </div>
          </div>
          <header>
            <h2>{visibleLabels.timeline}</h2>
          </header>
          <div className="timeline" aria-live="polite">
            {game.messages.map((message) => (
              <article className={`message ${message.role} ${message.metadata?.eventType ?? ""}`} key={message.id}>
                <div className="message-meta">
                  <span>{roleLabel(game.language, message.role)}</span>
                  <time>{new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>
                </div>
                <p>{message.text}</p>
              </article>
            ))}
            {!game.messages.length && <p className="muted">...</p>}
            <div ref={chatEndRef} />
          </div>
        </section>
      </section>
    </main>
  );
}

export default App;
