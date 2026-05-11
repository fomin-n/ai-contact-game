import { useEffect, useMemo, useRef, useState } from "react";
import { getConfig, getGameState, resetGame as resetGameApi, startGame as startGameApi } from "./api/gameApi";
import { AppHeader } from "./components/AppHeader";
import { GameControls } from "./components/GameControls";
import { GameStats } from "./components/GameStats";
import { ModelPanel } from "./components/ModelPanel";
import { Notice } from "./components/Notice";
import { RulesDialog } from "./components/RulesDialog";
import { Timeline } from "./components/Timeline";
import { UsedWordsPanel } from "./components/UsedWordsPanel";
import { createEmptyState, defaultPersonalities, DEFAULT_MAX_TURNS, initialProviderInfo } from "./config/defaults";
import { copy, rulesCopy } from "./i18n/copy";
import type { GameState, Language, ProviderInfo } from "./types/game";

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
      <AppHeader
        title={inputLabels.title}
        subtitle={inputLabels.subtitle}
        rulesLabel={inputLabels.rules}
        status={game.status}
        statusLabel={statusLabel}
        isRulesOpen={isRulesOpen}
        onOpenRules={() => setIsRulesOpen(true)}
      />

      {isRulesOpen && <RulesDialog rules={activeRules} onClose={() => setIsRulesOpen(false)} />}

      <section className="game-board">
        <aside className="side-column">
          <GameControls
            labels={inputLabels}
            language={language}
            playerAPersonality={playerAPersonality}
            playerBPersonality={playerBPersonality}
            customSecretWord={customSecretWord}
            isDisabled={isRunning || isRequesting}
            isResetDisabled={isRequesting}
            onLanguageChange={handleLanguageChange}
            onPlayerAPersonalityChange={setPlayerAPersonality}
            onPlayerBPersonalityChange={setPlayerBPersonality}
            onCustomSecretWordChange={setCustomSecretWord}
            onStart={startGame}
            onReset={resetGame}
          />

          <ModelPanel labels={visibleLabels} providerInfo={activeProviderInfo} />

          {(!activeProviderInfo.hasApiKey || uiError) && (
            <Notice message={uiError || visibleLabels.apiKeyMissing} isError={Boolean(uiError)} />
          )}

          <UsedWordsPanel labels={visibleLabels} usedWords={game.usedWords} />
        </aside>

        <section className="panel timeline-panel main-column">
          <GameStats
            labels={visibleLabels}
            secretWord={game.secretWord}
            currentPrefix={game.currentPrefix}
            turnNumber={game.turnNumber}
          />
          <Timeline labels={visibleLabels} language={game.language} messages={game.messages} chatEndRef={chatEndRef} />
        </section>
      </section>
    </main>
  );
}

export default App;
