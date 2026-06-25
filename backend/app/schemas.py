from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["en", "ru"]
Role = Literal["system", "playerA", "playerB", "wordMaster"]
PlayerRole = Literal["playerA", "playerB"]
GameStatus = Literal["idle", "running", "finished"]
HumanRole = Literal["none", "wordMaster", "playerA"]
PendingInputKind = Literal["wordMasterGuess", "playerMove", "partnerGuess"]


@dataclass(frozen=True)
class AgentModelConfig:
    word_master_model: str
    player_a_model: str
    player_b_model: str


class RoleModelSelection(BaseModel):
    provider: str
    model: str


class AgentModelSelection(BaseModel):
    wordMaster: RoleModelSelection
    playerA: RoleModelSelection
    playerB: RoleModelSelection


class AgentProviderInfo(BaseModel):
    wordMasterProvider: str
    wordMasterDisplayName: str
    wordMasterHasApiKey: bool
    playerAProvider: str
    playerADisplayName: str
    playerAHasApiKey: bool
    playerBProvider: str
    playerBDisplayName: str
    playerBHasApiKey: bool


class AgentModelInfo(BaseModel):
    wordMasterModel: str
    playerAModel: str
    playerBModel: str


class ProviderInfo(BaseModel):
    provider: str
    displayName: str
    hasApiKey: bool
    models: AgentModelInfo
    providers: AgentProviderInfo


class ModelOption(BaseModel):
    id: str
    displayName: str
    description: str | None = None
    recommendedFor: str | None = None
    isDefault: bool = False
    isCustom: bool = False
    supportsJsonSchema: bool = True


class ProviderModelCatalog(BaseModel):
    id: str
    displayName: str
    hasApiKey: bool
    defaultModel: str
    models: list[ModelOption]


class GameMessage(BaseModel):
    id: str
    role: Role
    text: str
    timestamp: float
    metadata: dict | None = None


class PendingUserInput(BaseModel):
    kind: PendingInputKind
    role: Literal["wordMaster", "playerA"]
    promptText: str
    placeholderText: str
    currentPrefix: str
    clue: str | None = None
    actingPlayer: PlayerRole | None = None
    partner: PlayerRole | None = None


class GameState(BaseModel):
    status: GameStatus = "idle"
    language: Language = "en"
    humanRole: HumanRole = "none"
    secretWord: str = ""
    currentPrefix: str = ""
    revealedLength: int = 0
    usedWords: list[str] = Field(default_factory=list)
    messages: list[GameMessage] = Field(default_factory=list)
    pendingUserInput: PendingUserInput | None = None
    currentTurn: PlayerRole = "playerA"
    turnNumber: int = 1
    # 0 until the secret word is known; then (len(secretWord) - 1) * 3 —
    # three contact attempts per letter after the already-revealed first one.
    maxTurns: int = 0
    winner: Literal["players", "wordMaster"] | None = None
    finishReason: str | None = None
    playerAPersonality: str = ""
    playerBPersonality: str = ""
    providerInfo: ProviderInfo


class StartGameRequest(BaseModel):
    language: Language
    playerAPersonality: str
    playerBPersonality: str
    humanRole: HumanRole = "none"
    agentModelSelection: AgentModelSelection | None = None
    secretWord: str | None = None


class UserInputRequest(BaseModel):
    kind: PendingInputKind
    guess: str | None = None
    intendedWord: str | None = None
    clue: str | None = None


class ConfigResponse(BaseModel):
    providerInfo: ProviderInfo
    modelCatalog: list[ProviderModelCatalog]
    defaultAgentModelSelection: AgentModelSelection


class SecretWord(BaseModel):
    word: str


class PlayerMove(BaseModel):
    intendedWord: str
    clue: str


class MasterGuess(BaseModel):
    guess: str
    confidence: float = 0


class PartnerGuess(BaseModel):
    guess: str
