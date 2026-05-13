import { type UIEvent, useEffect, useRef } from "react";
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
  const shouldStickToBottomRef = useRef(true);

  useEffect(() => {
    if (shouldStickToBottomRef.current || pendingUserInput) {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages.length, pendingUserInput?.kind]);

  function handleTimelineScroll(event: UIEvent<HTMLDivElement>) {
    const element = event.currentTarget;
    const distanceFromBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
    shouldStickToBottomRef.current = distanceFromBottom < 96;
  }

  return (
    <>
      <header>
        <h2>{labels.timeline}</h2>
      </header>
      <div
        className={`timeline${!messages.length && !pendingUserInput ? " timeline-empty" : ""}`}
        aria-live="polite"
        onScroll={handleTimelineScroll}
      >
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
        {!messages.length && <p className="muted">{labels.emptyTimeline}</p>}
        <div ref={chatEndRef} />
      </div>
    </>
  );
}
