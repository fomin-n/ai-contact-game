import type { UiCopy } from "../i18n/copy";

type UsedWordsPanelProps = {
  labels: UiCopy;
  usedWords: string[];
};

export function UsedWordsPanel({ labels, usedWords }: UsedWordsPanelProps) {
  return (
    <section className="panel used-words-panel">
      <header>
        <h2>{labels.usedWords}</h2>
        <span>{usedWords.length}</span>
      </header>
      {usedWords.length ? (
        <div className="chips">
          {usedWords.map((word) => (
            <span className="chip" key={word}>
              {word}
            </span>
          ))}
        </div>
      ) : (
        <p className="muted">{labels.emptyUsedWords}</p>
      )}
    </section>
  );
}
