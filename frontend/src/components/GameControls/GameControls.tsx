import type { UiCopy } from "../../i18n/copy";
import type { HumanRole, Language } from "../../types/game";
import { ModeSegmentedControl } from "../ModeSegmentedControl";

type GameControlsProps = {
  labels: UiCopy;
  language: Language;
  playerAPersonality: string;
  playerBPersonality: string;
  customSecretWord: string;
  humanRole: HumanRole;
  isDisabled: boolean;
  isStartDisabled: boolean;
  isResetDisabled: boolean;
  onLanguageChange: (language: Language) => void;
  onHumanRoleChange: (role: HumanRole) => void;
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
  humanRole,
  isDisabled,
  isStartDisabled,
  isResetDisabled,
  onLanguageChange,
  onHumanRoleChange,
  onPlayerAPersonalityChange,
  onPlayerBPersonalityChange,
  onCustomSecretWordChange,
  onStart,
  onReset
}: GameControlsProps) {
  return (
    <form className="panel controls" onSubmit={(event) => event.preventDefault()}>
      <fieldset className="lang-switch-field">
        <legend>{labels.language}</legend>
        <div className="lang-switch">
          {(["en", "ru"] as Language[]).map((lang) => (
            <label className="lang-option" data-active={language === lang} key={lang}>
              <input
                type="radio"
                name="language"
                value={lang}
                checked={language === lang}
                disabled={isDisabled}
                onChange={() => onLanguageChange(lang)}
              />
              <span>{lang === "en" ? labels.english : labels.russian}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <ModeSegmentedControl
        labels={labels}
        value={humanRole}
        disabled={isDisabled}
        onChange={onHumanRoleChange}
      />

      <label className="field">
        <span>{labels.optionalSecretWord}</span>
        <input
          value={customSecretWord}
          onChange={(event) => onCustomSecretWordChange(event.target.value)}
          disabled={isDisabled || humanRole === "playerA"}
          placeholder={labels.optionalSecretWordPlaceholder}
          autoComplete="off"
          required={humanRole === "wordMaster"}
        />
        <small>
          {humanRole === "wordMaster"
            ? labels.requiredSecretWordHint
            : humanRole === "playerA"
              ? labels.hiddenSecretWordHint
              : labels.optionalSecretWordHint}
        </small>
      </label>

      <label className="field">
        <span>{labels.personalityA}</span>
        <textarea
          value={playerAPersonality}
          onChange={(event) => onPlayerAPersonalityChange(event.target.value)}
          disabled={isDisabled}
        />
      </label>

      <label className="field">
        <span>{labels.personalityB}</span>
        <textarea
          value={playerBPersonality}
          onChange={(event) => onPlayerBPersonalityChange(event.target.value)}
          disabled={isDisabled}
        />
      </label>

      <div className="button-row">
        <button className="primary" type="button" onClick={onStart} disabled={isStartDisabled}>
          {labels.start}
        </button>
        <button type="button" onClick={onReset} disabled={isResetDisabled}>
          {labels.reset}
        </button>
      </div>
    </form>
  );
}
