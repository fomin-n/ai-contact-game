export type Language = "en" | "ru";

export type Role = "system" | "playerA" | "playerB" | "wordMaster";

export type PlayerRole = "playerA" | "playerB";

export type GameStatus = "idle" | "running" | "finished";

export type HumanRole = "none" | "wordMaster" | "playerA";

export type PendingInputKind = "wordMasterGuess" | "playerMove" | "partnerGuess";

export type AgentModelInfo = {
  wordMasterModel: string;
  playerAModel: string;
  playerBModel: string;
};

export type AgentProviderInfo = {
  wordMasterProvider: string;
  wordMasterDisplayName: string;
  wordMasterHasApiKey: boolean;
  playerAProvider: string;
  playerADisplayName: string;
  playerAHasApiKey: boolean;
  playerBProvider: string;
  playerBDisplayName: string;
  playerBHasApiKey: boolean;
};

export type ProviderInfo = {
  provider: string;
  displayName: string;
  hasApiKey: boolean;
  models: AgentModelInfo;
  providers: AgentProviderInfo;
};

export type RoleModelSelection = {
  provider: string;
  model: string;
};

export type AgentModelSelection = {
  wordMaster: RoleModelSelection;
  playerA: RoleModelSelection;
  playerB: RoleModelSelection;
};

export type ModelOption = {
  id: string;
  displayName: string;
  description?: string | null;
  recommendedFor?: string | null;
  isDefault: boolean;
  isCustom: boolean;
  supportsJsonSchema: boolean;
};

export type ProviderModelCatalog = {
  id: string;
  displayName: string;
  hasApiKey: boolean;
  defaultModel: string;
  models: ModelOption[];
};

export type ConfigResponse = {
  providerInfo: ProviderInfo;
  modelCatalog: ProviderModelCatalog[];
  defaultAgentModelSelection: AgentModelSelection;
};

export type GameMessage = {
  id: string;
  role: Role;
  text: string;
  timestamp: number;
  metadata?: {
    eventType?: string;
    word?: string;
    prefix?: string;
  };
};

export type PendingUserInput = {
  kind: PendingInputKind;
  role: "wordMaster" | "playerA";
  promptText: string;
  placeholderText: string;
  currentPrefix: string;
  clue?: string | null;
  actingPlayer?: PlayerRole | null;
  partner?: PlayerRole | null;
};

export type GameState = {
  status: GameStatus;
  language: Language;
  humanRole: HumanRole;
  secretWord: string;
  currentPrefix: string;
  revealedLength: number;
  usedWords: string[];
  messages: GameMessage[];
  pendingUserInput?: PendingUserInput | null;
  currentTurn: PlayerRole;
  turnNumber: number;
  /** 0 until the secret word is known; then (secretWord length - 1) * 3. */
  maxTurns: number;
  winner?: "players" | "wordMaster";
  finishReason?: string;
  playerAPersonality: string;
  playerBPersonality: string;
  providerInfo: ProviderInfo;
};
