import { useEffect, useState } from "react";
import { AppHeader } from "./components/AppHeader";
import { AgentModelSettings } from "./components/AgentModelSettings";
import { GameControls } from "./components/GameControls";
import { GameStats } from "./components/GameStats";
import { Notice } from "./components/Notice";
import { RulesDialog } from "./components/RulesDialog";
import { SettingsSidebar } from "./components/SettingsSidebar";
import { Timeline } from "./components/Timeline";
import { UsedWordsPanel } from "./components/UsedWordsPanel";
import { useGameController } from "./hooks/useGameController";
import { copy, rulesCopy } from "./i18n/copy";

const settingsCollapsedStorageKey = "ai-contact-game:settings-collapsed";

function getInitialSettingsCollapsed(): boolean {
  try {
    return window.localStorage.getItem(settingsCollapsedStorageKey) === "true";
  } catch {
    return false;
  }
}

function App() {
  const [isRulesOpen, setIsRulesOpen] = useState(false);
  const [isSettingsCollapsed, setIsSettingsCollapsed] = useState(getInitialSettingsCollapsed);
  const {
    activeProviderInfo,
    agentModelSelection,
    customSecretWord,
    game,
    handleHumanRoleChange,
    handleLanguageChange,
    humanRole,
    isRequesting,
    isRunning,
    isStartDisabled,
    isSubmittingUserInput,
    language,
    modelCatalog,
    playerAPersonality,
    playerBPersonality,
    resetGame,
    setAgentModelSelection,
    setCustomSecretWord,
    setPlayerAPersonality,
    setPlayerBPersonality,
    startGame,
    submitUserInput,
    userInputError,
    uiError
  } = useGameController();
  const visibleLabels = copy[game.language];
  const inputLabels = copy[language];
  const activeRules = rulesCopy[language];
  const statusLabel = visibleLabels[game.status];

  useEffect(() => {
    try {
      window.localStorage.setItem(settingsCollapsedStorageKey, String(isSettingsCollapsed));
    } catch {
      // localStorage is optional for this UI preference.
    }
  }, [isSettingsCollapsed]);

  function handleStartGame() {
    startGame();
    setIsSettingsCollapsed(true);
  }

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

      <section className={`game-board ${isSettingsCollapsed ? "settings-collapsed" : ""}`}>
        <SettingsSidebar
          labels={inputLabels}
          isCollapsed={isSettingsCollapsed}
          onToggle={() => setIsSettingsCollapsed((value) => !value)}
        >
          <GameControls
            labels={inputLabels}
            language={language}
            playerAPersonality={playerAPersonality}
            playerBPersonality={playerBPersonality}
            customSecretWord={customSecretWord}
            humanRole={humanRole}
            isDisabled={isRunning || isRequesting}
            isStartDisabled={isStartDisabled}
            isResetDisabled={isRequesting}
            onLanguageChange={handleLanguageChange}
            onHumanRoleChange={handleHumanRoleChange}
            onPlayerAPersonalityChange={setPlayerAPersonality}
            onPlayerBPersonalityChange={setPlayerBPersonality}
            onCustomSecretWordChange={setCustomSecretWord}
            onStart={handleStartGame}
            onReset={resetGame}
          />

          <AgentModelSettings
            labels={inputLabels}
            catalog={modelCatalog}
            selection={agentModelSelection}
            disabled={isRunning || isRequesting}
            onSelectionChange={setAgentModelSelection}
          />

          {(!activeProviderInfo.hasApiKey || uiError) && (
            <Notice message={uiError || visibleLabels.apiKeyMissing} isError={Boolean(uiError)} />
          )}

          <UsedWordsPanel labels={visibleLabels} usedWords={game.usedWords} />
        </SettingsSidebar>

        <section className="panel timeline-panel main-column">
          <GameStats
            labels={visibleLabels}
            secretWord={game.secretWord}
            currentPrefix={game.currentPrefix}
            turnNumber={game.turnNumber}
          />
          <Timeline
            labels={visibleLabels}
            language={game.language}
            messages={game.messages}
            pendingUserInput={game.pendingUserInput}
            isSubmittingUserInput={isSubmittingUserInput}
            userInputError={userInputError}
            onSubmitUserInput={submitUserInput}
          />
        </section>
      </section>
    </main>
  );
}

export default App;
