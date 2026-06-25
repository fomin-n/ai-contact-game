import type { UiCopy } from "../../i18n/copy";

type GameStatsProps = {
  labels: UiCopy;
  secretWord: string;
  currentPrefix: string;
  turnNumber: number;
  maxTurns: number;
};

export function GameStats({ labels, secretWord, currentPrefix, turnNumber, maxTurns }: GameStatsProps) {
  // maxTurns is 0 until the secret word is known (briefly, while the Word
  // Master is choosing it) — show just the turn number until then.
  const turnDisplay = maxTurns > 0 ? `${turnNumber} / ${maxTurns}` : `${turnNumber}`;
  return (
    <div className="chat-status" aria-label="Game status">
      <div className="chat-stat secret-chat-stat">
        <span>{labels.secretWord}</span>
        <strong>{secretWord || "..."}</strong>
      </div>
      <div className="chat-stat prefix-chat-stat">
        <span>{labels.currentPrefix}</span>
        <strong>{currentPrefix || "..."}</strong>
      </div>
      <div className="chat-stat turn-chat-stat">
        <span>{labels.turn}</span>
        <strong>{turnDisplay}</strong>
      </div>
    </div>
  );
}
