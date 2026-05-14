import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getConfig,
  getGameState,
  resetGame as resetGameApi,
  startGame as startGameApi,
  submitUserInput as submitUserInputApi,
  type StartGameParams,
  type UserInputParams
} from "../api/gameApi";
import { DEFAULT_MAX_TURNS, POLLING_INTERVAL_MS } from "../constants/gameConstants";
import { createEmptyState, defaultPersonalities, initialProviderInfo } from "../config/defaults";
import type {
  AgentModelSelection,
  GameState,
  HumanRole,
  Language,
  ProviderInfo,
  ProviderModelCatalog,
  RoleModelSelection
} from "../types/game";

const configQueryKey = ["config"] as const;
const gameStateQueryKey = ["gameState"] as const;
const modelSelectionStorageKey = "ai-contact-game:model-selection";

function getErrorMessage(error: unknown): string | null {
  if (!error) return null;
  return error instanceof Error ? error.message : String(error);
}

function providerFor(catalog: ProviderModelCatalog[], providerId: string): ProviderModelCatalog | undefined {
  return catalog.find((provider) => provider.id === providerId);
}

function firstAvailableProvider(catalog: ProviderModelCatalog[]): ProviderModelCatalog | undefined {
  return catalog.find((provider) => provider.hasApiKey) ?? catalog[0];
}

function modelForProvider(provider: ProviderModelCatalog, modelId: string): string {
  if (provider.models.some((model) => model.id === modelId)) return modelId;
  return provider.defaultModel || provider.models[0]?.id || modelId;
}

function sanitizeRoleSelection(
  selection: RoleModelSelection | undefined,
  fallback: RoleModelSelection,
  catalog: ProviderModelCatalog[]
): RoleModelSelection {
  const provider = providerFor(catalog, selection?.provider ?? "") ?? providerFor(catalog, fallback.provider) ?? firstAvailableProvider(catalog);
  if (!provider) return fallback;
  return {
    provider: provider.id,
    model: modelForProvider(provider, selection?.model || fallback.model || provider.defaultModel)
  };
}

function sanitizeAgentModelSelection(
  selection: AgentModelSelection | undefined,
  fallback: AgentModelSelection,
  catalog: ProviderModelCatalog[]
): AgentModelSelection {
  return {
    wordMaster: sanitizeRoleSelection(selection?.wordMaster, fallback.wordMaster, catalog),
    playerA: sanitizeRoleSelection(selection?.playerA, fallback.playerA, catalog),
    playerB: sanitizeRoleSelection(selection?.playerB, fallback.playerB, catalog)
  };
}

function readStoredModelSelection(): { selection?: AgentModelSelection } | null {
  try {
    const raw = window.localStorage.getItem(modelSelectionStorageKey);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

type UseGameControllerResult = {
  activeProviderInfo: ProviderInfo;
  agentModelSelection: AgentModelSelection;
  customSecretWord: string;
  game: GameState;
  handleLanguageChange: (language: Language) => void;
  handleHumanRoleChange: (role: HumanRole) => void;
  isRequesting: boolean;
  isRunning: boolean;
  isStartDisabled: boolean;
  isSubmittingUserInput: boolean;
  language: Language;
  humanRole: HumanRole;
  modelCatalog: ProviderModelCatalog[];
  playerAPersonality: string;
  playerBPersonality: string;
  resetGame: () => void;
  setCustomSecretWord: (value: string) => void;
  setAgentModelSelection: (value: AgentModelSelection) => void;
  setPlayerAPersonality: (value: string) => void;
  setPlayerBPersonality: (value: string) => void;
  startGame: () => void;
  submitUserInput: (params: UserInputParams) => void;
  userInputError: string | null;
  uiError: string | null;
};

export function useGameController(): UseGameControllerResult {
  const queryClient = useQueryClient();
  const initialSyncDone = useRef(false);
  const modelSelectionSyncDone = useRef(false);
  const [language, setLanguage] = useState<Language>("en");
  const [humanRole, setHumanRole] = useState<HumanRole>("none");
  const [playerAPersonality, setPlayerAPersonality] = useState(defaultPersonalities.en.playerA);
  const [playerBPersonality, setPlayerBPersonality] = useState(defaultPersonalities.en.playerB);
  const [customSecretWord, setCustomSecretWord] = useState("");
  const [agentModelSelection, setAgentModelSelection] = useState<AgentModelSelection>({
    wordMaster: { provider: initialProviderInfo.providers.wordMasterProvider, model: initialProviderInfo.models.wordMasterModel },
    playerA: { provider: initialProviderInfo.providers.playerAProvider, model: initialProviderInfo.models.playerAModel },
    playerB: { provider: initialProviderInfo.providers.playerBProvider, model: initialProviderInfo.models.playerBModel }
  });
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [userInputError, setUserInputError] = useState<string | null>(null);

  const configQuery = useQuery({
    queryKey: configQueryKey,
    queryFn: getConfig
  });

  const gameStateQuery = useQuery({
    queryKey: gameStateQueryKey,
    queryFn: getGameState,
    refetchInterval: (query) => {
      const state = query.state.data;
      return state?.status === "running" ? POLLING_INTERVAL_MS : false;
    }
  });

  const configProviderInfo = configQuery.data?.providerInfo ?? initialProviderInfo;
  const modelCatalog = configQuery.data?.modelCatalog ?? [];
  const defaultAgentModelSelection =
    configQuery.data?.defaultAgentModelSelection ?? agentModelSelection;
  const serverGame = gameStateQuery.data;
  const activeProviderInfo = serverGame?.providerInfo ?? configProviderInfo;

  const game = useMemo(() => {
    if (!serverGame) {
      return createEmptyState(language, activeProviderInfo);
    }

    const shouldUseSelectedLanguage =
      serverGame.status === "idle" &&
      serverGame.messages.length === 0 &&
      serverGame.usedWords.length === 0 &&
      language !== serverGame.language;

    return shouldUseSelectedLanguage ? createEmptyState(language, activeProviderInfo) : serverGame;
  }, [activeProviderInfo, language, serverGame]);

  const startGameMutation = useMutation({
    mutationFn: (params: StartGameParams) => startGameApi(params),
    onMutate: () => {
      setMutationError(null);
    },
    onSuccess: (state) => {
      queryClient.setQueryData(gameStateQueryKey, state);
      setMutationError(null);
    },
    onError: (error) => {
      setMutationError(getErrorMessage(error));
    }
  });

  const resetGameMutation = useMutation({
    mutationFn: resetGameApi,
    onMutate: () => {
      setMutationError(null);
    },
    onSuccess: (state) => {
      queryClient.setQueryData(gameStateQueryKey, state);
      setMutationError(null);
    },
    onError: (error) => {
      setMutationError(getErrorMessage(error));
    }
  });

  const userInputMutation = useMutation({
    mutationFn: (params: UserInputParams) => submitUserInputApi(params),
    onMutate: () => {
      setUserInputError(null);
    },
    onSuccess: (state) => {
      queryClient.setQueryData(gameStateQueryKey, state);
      setUserInputError(null);
      void queryClient.invalidateQueries({ queryKey: gameStateQueryKey });
    },
    onError: (error) => {
      setUserInputError(getErrorMessage(error));
    }
  });

  useEffect(() => {
    const state = gameStateQuery.data;
    if (!state || initialSyncDone.current) return;

    initialSyncDone.current = true;
    setLanguage(state.language);
    setHumanRole(state.humanRole);
    setPlayerAPersonality(state.playerAPersonality || defaultPersonalities[state.language].playerA);
    setPlayerBPersonality(state.playerBPersonality || defaultPersonalities[state.language].playerB);
  }, [gameStateQuery.data]);

  useEffect(() => {
    if (!configQuery.data || modelSelectionSyncDone.current) return;

    const stored = readStoredModelSelection();
    const sanitized = sanitizeAgentModelSelection(
      stored?.selection,
      configQuery.data.defaultAgentModelSelection,
      configQuery.data.modelCatalog
    );
    setAgentModelSelection(sanitized);
    modelSelectionSyncDone.current = true;
  }, [configQuery.data]);

  useEffect(() => {
    if (!modelSelectionSyncDone.current) return;
    try {
      window.localStorage.setItem(
        modelSelectionStorageKey,
        JSON.stringify({ selection: agentModelSelection })
      );
    } catch {
      // localStorage is optional for this UI preference.
    }
  }, [agentModelSelection]);

  function handleLanguageChange(nextLanguage: Language) {
    setLanguage(nextLanguage);
    setPlayerAPersonality(defaultPersonalities[nextLanguage].playerA);
    setPlayerBPersonality(defaultPersonalities[nextLanguage].playerB);
    setCustomSecretWord("");

    if (game.status === "idle") {
      queryClient.setQueryData(gameStateQueryKey, createEmptyState(nextLanguage, activeProviderInfo));
    }
  }

  function handleHumanRoleChange(nextHumanRole: HumanRole) {
    setHumanRole(nextHumanRole);
    setMutationError(null);
    setUserInputError(null);
    if (nextHumanRole === "playerA") {
      setCustomSecretWord("");
    }
  }

  function handleAgentModelSelectionChange(nextSelection: AgentModelSelection) {
    setAgentModelSelection(sanitizeAgentModelSelection(nextSelection, defaultAgentModelSelection, modelCatalog));
  }

  function startGame() {
    startGameMutation.mutate({
      language,
      playerAPersonality,
      playerBPersonality,
      humanRole,
      agentModelSelection,
      secretWord: humanRole === "playerA" ? undefined : customSecretWord.trim() || undefined,
      maxTurns: DEFAULT_MAX_TURNS
    });
  }

  function resetGame() {
    resetGameMutation.mutate();
  }

  function submitUserInput(params: UserInputParams) {
    userInputMutation.mutate(params);
  }

  const queryError = getErrorMessage(configQuery.error) ?? getErrorMessage(gameStateQuery.error);
  const uiError = mutationError ?? queryError;
  const isRequesting = startGameMutation.isPending || resetGameMutation.isPending;
  const isRunning = game.status === "running";
  const isStartDisabled =
    isRunning ||
    isRequesting ||
    (humanRole === "wordMaster" && customSecretWord.trim().length === 0);

  return {
    activeProviderInfo,
    agentModelSelection,
    customSecretWord,
    game,
    handleLanguageChange,
    handleHumanRoleChange,
    isRequesting,
    isRunning,
    isStartDisabled,
    isSubmittingUserInput: userInputMutation.isPending,
    language,
    humanRole,
    modelCatalog,
    playerAPersonality,
    playerBPersonality,
    resetGame,
    setAgentModelSelection: handleAgentModelSelectionChange,
    setCustomSecretWord,
    setPlayerAPersonality,
    setPlayerBPersonality,
    startGame,
    submitUserInput,
    userInputError,
    uiError
  };
}
