from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .config import load_agent_model_config, load_agent_provider_config
from .game import GameManager
from .schemas import ConfigResponse, StartGameRequest

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
    return ConfigResponse(providerInfo=game_manager.get_provider_info())


@app.get("/api/game/state")
async def state():
    return await game_manager.get_state()


@app.post("/api/game/start")
async def start(request: StartGameRequest):
    return await game_manager.start(request)


@app.post("/api/game/reset")
async def reset():
    return await game_manager.reset()
