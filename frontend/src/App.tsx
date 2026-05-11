import { useState } from "react";
import { AppHeader } from "./components/AppHeader";
import { GameControls } from "./components/GameControls";
import { GameStats } from "./components/GameStats";
import { ModelPanel } from "./components/ModelPanel";
import { Notice } from "./components/Notice";
import { RulesDialog } from "./components/RulesDialog";
import { Timeline } from "./components/Timeline";
import { UsedWordsPanel } from "./components/UsedWordsPanel";
import { useGameController } from "./hooks/useGameController";
import { copy, rulesCopy } from "./i18n/copy";

function App() {
  const [isRulesOpen, setIsRulesOpen] = useState(false);
  const {
    activeProviderInfo,
    customSecretWord,
    game,
    handleLanguageChange,
    isRequesting,
    isRunning,
    language,
    playerAPersonality,
    playerBPersonality,
    resetGame,
    setCustomSecretWord,
    setPlayerAPersonality,
    setPlayerBPersonality,
    startGame,
    uiError
  } = useGameController();
  const visibleLabels = copy[game.language];
  const inputLabels = copy[language];
  const activeRules = rulesCopy[language];
  const statusLabel = visibleLabels[game.status];

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
          <Timeline labels={visibleLabels} language={game.language} messages={game.messages} />
        </section>
      </section>
    </main>
  );
}

export default App;
