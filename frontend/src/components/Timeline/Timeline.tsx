import { useEffect, useRef } from "react";
import type { UiCopy } from "../../i18n/copy";
import type { GameMessage, Language, PendingUserInput as PendingUserInputType } from "../../types/game";
import type { UserInputParams } from "../../api/gameApi";
import { PendingUserInputForm } from "./PendingUserInputForm";
import { TimelineMessage } from "./TimelineMessage";

type TimelineProps = {
  labels: UiCopy;
  language: Language;
  messages: GameMessage[];
  pendingUserInput?: PendingUserInputType | null;
  isSubmittingUserInput: boolean;
  userInputError: string | null;
  onSubmitUserInput: (params: UserInputParams) => void;
};

export function Timeline({
  labels,
  language,
  messages,
  pendingUserInput,
  isSubmittingUserInput,
  userInputError,
  onSubmitUserInput
}: TimelineProps) {
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, pendingUserInput?.kind]);

  return (
    <>
      <header>
        <h2>{labels.timeline}</h2>
      </header>
      <div className="timeline" aria-live="polite">
        {messages.map((message) => (
          <TimelineMessage language={language} message={message} key={message.id} />
        ))}
        {pendingUserInput && (
          <PendingUserInputForm
            labels={labels}
            pendingUserInput={pendingUserInput}
            isSubmitting={isSubmittingUserInput}
            error={userInputError}
            onSubmit={onSubmitUserInput}
          />
        )}
        {!messages.length && <p className="muted">...</p>}
        <div ref={chatEndRef} />
      </div>
    </>
  );
}
