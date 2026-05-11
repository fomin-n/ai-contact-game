import type { ReactNode } from "react";
import { copy } from "../i18n/copy";
import type { GameMessage, Language, PlayerRole, Role } from "../types/game";

export function playerLabel(language: Language, role: PlayerRole): string {
  return role === "playerA" ? copy[language].playerA : copy[language].playerB;
}

export function roleLabel(language: Language, role: Role): string {
  if (role === "playerA" || role === "playerB") return playerLabel(language, role);
  return role === "wordMaster" ? copy[language].wordMaster : copy[language].system;
}

export function renderMessageText(message: GameMessage): ReactNode {
  const word = message.metadata?.word?.trim();
  const shouldHighlight = word && ["playerA", "playerB", "wordMaster"].includes(message.role);
  if (!shouldHighlight) return message.text;

  const text = message.text;
  const lowerText = text.toLocaleLowerCase();
  const lowerWord = word.toLocaleLowerCase();
  const parts: ReactNode[] = [];
  let cursor = 0;
  let matchIndex = lowerText.indexOf(lowerWord);

  while (matchIndex >= 0) {
    if (matchIndex > cursor) {
      parts.push(text.slice(cursor, matchIndex));
    }
    const end = matchIndex + word.length;
    parts.push(
      <strong className="message-word" key={`${message.id}-${matchIndex}`}>
        {text.slice(matchIndex, end)}
      </strong>
    );
    cursor = end;
    matchIndex = lowerText.indexOf(lowerWord, cursor);
  }

  if (cursor < text.length) {
    parts.push(text.slice(cursor));
  }

  return parts.length ? parts : message.text;
}
