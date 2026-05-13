import type { GameState, Language, PlayerRole, ProviderInfo } from "../types/game";
import { DEFAULT_MAX_TURNS } from "../constants/gameConstants";

export const initialProviderInfo: ProviderInfo = {
  provider: "mistral",
  displayName: "Mistral",
  hasApiKey: false,
  models: {
    wordMasterModel: "mistral-small-latest",
    playerAModel: "mistral-small-latest",
    playerBModel: "mistral-small-latest"
  },
  providers: {
    wordMasterProvider: "mistral",
    wordMasterDisplayName: "Mistral",
    wordMasterHasApiKey: false,
    playerAProvider: "mistral",
    playerADisplayName: "Mistral",
    playerAHasApiKey: false,
    playerBProvider: "mistral",
    playerBDisplayName: "Mistral",
    playerBHasApiKey: false
  }
};

export const defaultPersonalities: Record<Language, Record<PlayerRole, string>> = {
  en: {
    playerA: "Playful, metaphor-loving, a little theatrical, but concise.",
    playerB: "Sharp, practical, and good at noticing everyday associations."
  },
  ru: {
    playerA: "Игривый, образный, немного театральный, но краткий.",
    playerB: "Внимательный, практичный, хорошо угадывает бытовые ассоциации."
  }
};

export function createEmptyState(language: Language, providerInfo: ProviderInfo): GameState {
  return {
    status: "idle",
    language,
    humanRole: "none",
    secretWord: "",
    currentPrefix: "",
    revealedLength: 0,
    usedWords: [],
    messages: [],
    pendingUserInput: null,
    currentTurn: "playerA",
    turnNumber: 1,
    maxTurns: DEFAULT_MAX_TURNS,
    playerAPersonality: defaultPersonalities[language].playerA,
    playerBPersonality: defaultPersonalities[language].playerB,
    providerInfo
  };
}
