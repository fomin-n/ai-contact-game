import { roleLabel, renderMessageText } from "../utils/gameUi";
import type { GameMessage, Language } from "../types/game";

type TimelineMessageProps = {
  language: Language;
  message: GameMessage;
};

export function TimelineMessage({ language, message }: TimelineMessageProps) {
  return (
    <article className={`message ${message.role} ${message.metadata?.eventType ?? ""}`}>
      <div className="message-meta">
        <span>{roleLabel(language, message.role)}</span>
        <time>{new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>
      </div>
      <p>{renderMessageText(message)}</p>
    </article>
  );
}
