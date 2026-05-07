from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["en", "ru"]
Role = Literal["system", "playerA", "playerB", "wordMaster"]
PlayerRole = Literal["playerA", "playerB"]
GameStatus = Literal["idle", "running", "finished"]


@dataclass(frozen=True)
class AgentModelConfig:
    word_master_model: str
    player_a_model: str
    player_b_model: str


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


class GameMessage(BaseModel):
    id: str
    role: Role
    text: str
    timestamp: float
    metadata: dict | None = None


class GameState(BaseModel):
    status: GameStatus = "idle"
    language: Language = "en"
    secretWord: str = ""
    currentPrefix: str = ""
    revealedLength: int = 0
    usedWords: list[str] = Field(default_factory=list)
    messages: list[GameMessage] = Field(default_factory=list)
    currentTurn: PlayerRole = "playerA"
    turnNumber: int = 1
    maxTurns: int = 50
    winner: Literal["players", "wordMaster"] | None = None
    finishReason: str | None = None
    playerAPersonality: str = ""
    playerBPersonality: str = ""
    providerInfo: ProviderInfo


class StartGameRequest(BaseModel):
    language: Language
    playerAPersonality: str
    playerBPersonality: str
    maxTurns: int = Field(default=50, ge=1, le=200)


class ConfigResponse(BaseModel):
    providerInfo: ProviderInfo


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
