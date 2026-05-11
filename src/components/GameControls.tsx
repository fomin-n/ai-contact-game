import type { UiCopy } from "../i18n/copy";
import type { Language } from "../types/game";

type GameControlsProps = {
  labels: UiCopy;
  language: Language;
  playerAPersonality: string;
  playerBPersonality: string;
  customSecretWord: string;
  isDisabled: boolean;
  isResetDisabled: boolean;
  onLanguageChange: (language: Language) => void;
  onPlayerAPersonalityChange: (value: string) => void;
  onPlayerBPersonalityChange: (value: string) => void;
  onCustomSecretWordChange: (value: string) => void;
  onStart: () => void;
  onReset: () => void;
};

export function GameControls({
  labels,
  language,
  playerAPersonality,
  playerBPersonality,
  customSecretWord,
  isDisabled,
  isResetDisabled,
  onLanguageChange,
  onPlayerAPersonalityChange,
  onPlayerBPersonalityChange,
  onCustomSecretWordChange,
  onStart,
  onReset
}: GameControlsProps) {
  return (
    <form className="panel controls" onSubmit={(event) => event.preventDefault()}>
      <label className="field">
        <span>{labels.language}</span>
        <select value={language} onChange={(event) => onLanguageChange(event.target.value as Language)} disabled={isDisabled}>
          <option value="en">{labels.english}</option>
          <option value="ru">{labels.russian}</option>
        </select>
      </label>

      <label className="field">
        <span>{labels.optionalSecretWord}</span>
        <input
          value={customSecretWord}
          onChange={(event) => onCustomSecretWordChange(event.target.value)}
          disabled={isDisabled}
          placeholder={labels.optionalSecretWordPlaceholder}
          autoComplete="off"
        />
        <small>{labels.optionalSecretWordHint}</small>
      </label>

      <label className="field">
        <span>{labels.personalityA}</span>
        <textarea
          value={playerAPersonality}
          onChange={(event) => onPlayerAPersonalityChange(event.target.value)}
          disabled={isDisabled}
          rows={4}
        />
      </label>

      <label className="field">
        <span>{labels.personalityB}</span>
        <textarea
          value={playerBPersonality}
          onChange={(event) => onPlayerBPersonalityChange(event.target.value)}
          disabled={isDisabled}
          rows={4}
        />
      </label>

      <div className="button-row">
        <button className="primary" type="button" onClick={onStart} disabled={isDisabled}>
          {labels.start}
        </button>
        <button type="button" onClick={onReset} disabled={isResetDisabled}>
          {labels.reset}
        </button>
      </div>
    </form>
  );
}
