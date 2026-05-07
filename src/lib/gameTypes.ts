export type Language = "en" | "ru";

export type Role = "system" | "playerA" | "playerB" | "wordMaster";

export type PlayerRole = "playerA" | "playerB";

export type GameStatus = "idle" | "running" | "finished";

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

export type GameState = {
  status: GameStatus;
  language: Language;
  secretWord: string;
  currentPrefix: string;
  revealedLength: number;
  usedWords: string[];
  messages: GameMessage[];
  currentTurn: PlayerRole;
  turnNumber: number;
  maxTurns: number;
  winner?: "players" | "wordMaster";
  finishReason?: string;
  playerAPersonality: string;
  playerBPersonality: string;
  providerInfo: ProviderInfo;
};
