import type { GameState, Language, ProviderInfo } from "../types/game";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export type StartGameParams = {
  language: Language;
  playerAPersonality: string;
  playerBPersonality: string;
  secretWord?: string;
  maxTurns?: number;
};

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    }
  });

  if (!response.ok) {
    const detail = await response.text();
    let message = detail;
    try {
      const parsed = JSON.parse(detail) as { detail?: string };
      message = parsed.detail || detail;
    } catch {
      message = detail;
    }
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getConfig(): Promise<{ providerInfo: ProviderInfo }> {
  return requestJson("/api/config");
}

export function getGameState(): Promise<GameState> {
  return requestJson("/api/game/state");
}

export function startGame(params: StartGameParams): Promise<GameState> {
  return requestJson("/api/game/start", {
    method: "POST",
    body: JSON.stringify(params)
  });
}

export function resetGame(): Promise<GameState> {
  return requestJson("/api/game/reset", { method: "POST" });
}
