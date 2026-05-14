from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .config import default_agent_model_selection, load_agent_model_config, load_agent_provider_config
from .game import GameManager
from .model_catalog import build_model_catalog
from .schemas import ConfigResponse, StartGameRequest, UserInputRequest

load_dotenv()

providers = load_agent_provider_config()
models = load_agent_model_config(providers)
game_manager = GameManager(providers, models)

app = FastAPI(title="AI Contact Game API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "providerInfo": game_manager.get_provider_info().model_dump(),
    }


@app.get("/api/config", response_model=ConfigResponse)
async def config() -> ConfigResponse:
    return ConfigResponse(
        providerInfo=game_manager.get_provider_info(),
        modelCatalog=build_model_catalog(),
        defaultAgentModelSelection=default_agent_model_selection(providers, models),
    )


@app.get("/api/game/state")
async def state():
    return await game_manager.get_state()


@app.post("/api/game/start")
async def start(request: StartGameRequest):
    try:
        return await game_manager.start(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/game/reset")
async def reset():
    return await game_manager.reset()


@app.post("/api/game/user-input")
async def user_input(request: UserInputRequest):
    try:
        return await game_manager.submit_user_input(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
