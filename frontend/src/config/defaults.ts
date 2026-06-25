import type { GameState, Language, PlayerRole, ProviderInfo } from "../types/game";

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
    playerA: "Prefers scientific and technical vocabulary — physics, chemistry, engineering, mathematics.",
    playerB: "Draws from sport, medicine, and art — athletic terms, anatomy, musical and visual arts."
  },
  ru: {
    playerA: "Предпочитает научно-техническую лексику — физика, химия, инженерия, математика.",
    playerB: "Черпает слова из спорта, медицины и искусства — спортивные термины, анатомия, музыка и изобразительное искусство."
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
    // 0 until the secret word is known; the backend computes the real value
    // as (secretWord length - 1) * 3 once the game starts.
    maxTurns: 0,
    playerAPersonality: defaultPersonalities[language].playerA,
    playerBPersonality: defaultPersonalities[language].playerB,
    providerInfo
  };
}
