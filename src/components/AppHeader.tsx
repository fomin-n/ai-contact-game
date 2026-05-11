import type { GameStatus } from "../types/game";

type AppHeaderProps = {
  title: string;
  subtitle: string;
  rulesLabel: string;
  status: GameStatus;
  statusLabel: string;
  isRulesOpen: boolean;
  onOpenRules: () => void;
};

export function AppHeader({
  title,
  subtitle,
  rulesLabel,
  status,
  statusLabel,
  isRulesOpen,
  onOpenRules
}: AppHeaderProps) {
  return (
    <section className="intro">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="intro-actions">
        <button className="rules-button" type="button" aria-haspopup="dialog" aria-expanded={isRulesOpen} onClick={onOpenRules}>
          {rulesLabel}
        </button>
        <span className={`status-pill ${status}`}>{statusLabel}</span>
      </div>
    </section>
  );
}
