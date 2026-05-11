import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getConfig,
  getGameState,
  resetGame as resetGameApi,
  startGame as startGameApi,
  type StartGameParams
} from "../api/gameApi";
import { DEFAULT_MAX_TURNS, POLLING_INTERVAL_MS } from "../constants/gameConstants";
import { createEmptyState, defaultPersonalities, initialProviderInfo } from "../config/defaults";
import type { GameState, Language, ProviderInfo } from "../types/game";

const configQueryKey = ["config"] as const;
const gameStateQueryKey = ["gameState"] as const;

function getErrorMessage(error: unknown): string | null {
  if (!error) return null;
  return error instanceof Error ? error.message : String(error);
}

type UseGameControllerResult = {
  activeProviderInfo: ProviderInfo;
  customSecretWord: string;
  game: GameState;
  handleLanguageChange: (language: Language) => void;
  isRequesting: boolean;
  isRunning: boolean;
  language: Language;
  playerAPersonality: string;
  playerBPersonality: string;
  resetGame: () => void;
  setCustomSecretWord: (value: string) => void;
  setPlayerAPersonality: (value: string) => void;
  setPlayerBPersonality: (value: string) => void;
  startGame: () => void;
  uiError: string | null;
};

export function useGameController(): UseGameControllerResult {
  const queryClient = useQueryClient();
  const initialSyncDone = useRef(false);
  const [language, setLanguage] = useState<Language>("en");
  const [playerAPersonality, setPlayerAPersonality] = useState(defaultPersonalities.en.playerA);
  const [playerBPersonality, setPlayerBPersonality] = useState(defaultPersonalities.en.playerB);
  const [customSecretWord, setCustomSecretWord] = useState("");
  const [mutationError, setMutationError] = useState<string | null>(null);

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

  useEffect(() => {
    const state = gameStateQuery.data;
    if (!state || initialSyncDone.current) return;

    initialSyncDone.current = true;
    setLanguage(state.language);
    setPlayerAPersonality(state.playerAPersonality || defaultPersonalities[state.language].playerA);
    setPlayerBPersonality(state.playerBPersonality || defaultPersonalities[state.language].playerB);
  }, [gameStateQuery.data]);

  function handleLanguageChange(nextLanguage: Language) {
    setLanguage(nextLanguage);
    setPlayerAPersonality(defaultPersonalities[nextLanguage].playerA);
    setPlayerBPersonality(defaultPersonalities[nextLanguage].playerB);
    setCustomSecretWord("");

    if (game.status === "idle") {
      queryClient.setQueryData(gameStateQueryKey, createEmptyState(nextLanguage, activeProviderInfo));
    }
  }

  function startGame() {
    startGameMutation.mutate({
      language,
      playerAPersonality,
      playerBPersonality,
      secretWord: customSecretWord.trim() || undefined,
      maxTurns: DEFAULT_MAX_TURNS
    });
  }

  function resetGame() {
    resetGameMutation.mutate();
  }

  const queryError = getErrorMessage(configQuery.error) ?? getErrorMessage(gameStateQuery.error);
  const uiError = mutationError ?? queryError;
  const isRequesting = startGameMutation.isPending || resetGameMutation.isPending;
  const isRunning = game.status === "running";

  return {
    activeProviderInfo,
    customSecretWord,
    game,
    handleLanguageChange,
    isRequesting,
    isRunning,
    language,
    playerAPersonality,
    playerBPersonality,
    resetGame,
    setCustomSecretWord,
    setPlayerAPersonality,
    setPlayerBPersonality,
    startGame,
    uiError
  };
}
