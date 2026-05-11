import type { RefObject } from "react";
import type { UiCopy } from "../i18n/copy";
import type { GameMessage, Language } from "../types/game";
import { TimelineMessage } from "./TimelineMessage";

type TimelineProps = {
  labels: UiCopy;
  language: Language;
  messages: GameMessage[];
  chatEndRef: RefObject<HTMLDivElement | null>;
};

export function Timeline({ labels, language, messages, chatEndRef }: TimelineProps) {
  return (
    <>
      <header>
        <h2>{labels.timeline}</h2>
      </header>
      <div className="timeline" aria-live="polite">
        {messages.map((message) => (
          <TimelineMessage language={language} message={message} key={message.id} />
        ))}
        {!messages.length && <p className="muted">...</p>}
        <div ref={chatEndRef} />
      </div>
    </>
  );
}
