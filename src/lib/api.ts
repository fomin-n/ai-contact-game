import type { GameState, Language, ProviderInfo } from "./gameTypes";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

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
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getConfig(): Promise<{ providerInfo: ProviderInfo }> {
  return requestJson("/api/config");
}

export function getGameState(): Promise<GameState> {
  return requestJson("/api/game/state");
}

export function startGame(params: {
  language: Language;
  playerAPersonality: string;
  playerBPersonality: string;
  maxTurns?: number;
}): Promise<GameState> {
  return requestJson("/api/game/start", {
    method: "POST",
    body: JSON.stringify(params)
  });
}

export function resetGame(): Promise<GameState> {
  return requestJson("/api/game/reset", { method: "POST" });
}
