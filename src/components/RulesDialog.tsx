import type { RulesCopy } from "../i18n/copy";

type RulesDialogProps = {
  rules: RulesCopy;
  onClose: () => void;
};

export function RulesDialog({ rules, onClose }: RulesDialogProps) {
  return (
    <div className="rules-backdrop" role="presentation" onClick={onClose}>
      <section
        className="rules-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="rules-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <h2 id="rules-title">{rules.title}</h2>
          <button type="button" onClick={onClose}>
            {rules.close}
          </button>
        </header>
        <p>{rules.intro}</p>
        <ol>
          {rules.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>
    </div>
  );
}
