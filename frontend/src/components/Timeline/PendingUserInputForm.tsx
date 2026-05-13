import { type FormEvent, useEffect, useRef, useState } from "react";
import type { UserInputParams } from "../../api/gameApi";
import type { UiCopy } from "../../i18n/copy";
import type { PendingUserInput } from "../../types/game";

type PendingUserInputFormProps = {
  labels: UiCopy;
  pendingUserInput: PendingUserInput;
  isSubmitting: boolean;
  error: string | null;
  onSubmit: (params: UserInputParams) => void;
};

export function PendingUserInputForm({
  labels,
  pendingUserInput,
  isSubmitting,
  error,
  onSubmit
}: PendingUserInputFormProps) {
  const [guess, setGuess] = useState("");
  const [intendedWord, setIntendedWord] = useState("");
  const [clue, setClue] = useState("");
  const firstInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setGuess("");
    setIntendedWord("");
    setClue("");
    window.requestAnimationFrame(() => firstInputRef.current?.focus());
  }, [pendingUserInput.kind, pendingUserInput.currentPrefix, pendingUserInput.clue]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingUserInput.kind === "playerMove") {
      onSubmit({
        kind: "playerMove",
        intendedWord: intendedWord.trim(),
        clue: clue.trim()
      });
      return;
    }

    onSubmit({
      kind: pendingUserInput.kind,
      guess: guess.trim()
    });
  }

  const roleClass = pendingUserInput.role === "wordMaster" ? "wordMaster" : "playerA";

  return (
    <article className={`message ${roleClass} pending-input`}>
      <div className="message-meta">
        <span>{pendingUserInput.promptText}</span>
      </div>
      <form className="pending-input-form" onSubmit={handleSubmit}>
        {pendingUserInput.kind === "playerMove" ? (
          <>
            <label className="pending-input-field">
              <span>{labels.intendedWord}</span>
              <input
                ref={firstInputRef}
                value={intendedWord}
                onChange={(event) => setIntendedWord(event.target.value)}
                disabled={isSubmitting}
                placeholder={labels.intendedWordPlaceholder}
                autoComplete="off"
              />
            </label>
            <label className="pending-input-field">
              <span>{labels.encryptedClue}</span>
              <textarea
                value={clue}
                onChange={(event) => setClue(event.target.value)}
                disabled={isSubmitting}
                placeholder={labels.encryptedCluePlaceholder}
                rows={3}
              />
            </label>
          </>
        ) : (
          <input
            ref={firstInputRef}
            value={guess}
            onChange={(event) => setGuess(event.target.value)}
            disabled={isSubmitting}
            placeholder={pendingUserInput.placeholderText}
            autoComplete="off"
          />
        )}

        {error && <p className="pending-input-error">{error}</p>}

        <button className="primary" type="submit" disabled={isSubmitting}>
          {isSubmitting ? labels.submitting : labels.submit}
        </button>
      </form>
    </article>
  );
}
