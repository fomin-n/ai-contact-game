import type { UiCopy } from "../../i18n/copy";
import type { HumanRole } from "../../types/game";
import "./ModeSegmentedControl.css";

type ModeSegmentedControlProps = {
  labels: UiCopy;
  value: HumanRole;
  disabled: boolean;
  onChange: (value: HumanRole) => void;
};

const modes: HumanRole[] = ["none", "wordMaster", "playerA"];

function modeLabel(labels: UiCopy, mode: HumanRole): string {
  if (mode === "wordMaster") return labels.modeWordMaster;
  if (mode === "playerA") return labels.modePlayerA;
  return labels.modeNone;
}

export function ModeSegmentedControl({ labels, value, disabled, onChange }: ModeSegmentedControlProps) {
  return (
    <fieldset className="mode-segmented-field">
      <legend>{labels.gameMode}</legend>
      <div className="mode-segmented-control" role="radiogroup" aria-label={labels.gameMode}>
        {modes.map((mode) => (
          <label className="mode-segment" data-active={value === mode} key={mode}>
            <input
              type="radio"
              name="game-mode"
              value={mode}
              checked={value === mode}
              disabled={disabled}
              onChange={() => onChange(mode)}
            />
            <span>{modeLabel(labels, mode)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
