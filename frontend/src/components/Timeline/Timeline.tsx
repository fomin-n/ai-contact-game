import { useEffect, useRef } from "react";
import type { UiCopy } from "../../i18n/copy";
import type { GameMessage, Language } from "../../types/game";
import { TimelineMessage } from "./TimelineMessage";

type TimelineProps = {
  labels: UiCopy;
  language: Language;
  messages: GameMessage[];
};

export function Timeline({ labels, language, messages }: TimelineProps) {
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

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
