from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from .config import TelegramBotSettings
from .handlers.callbacks import handle_callback
from .handlers.commands import (
    cancel_command,
    newgame_command,
    rules_command,
    start_command,
    status_command,
)
from .handlers.messages import handle_text
from .observability import setup_tracing
from .session.registry import SessionRegistry
from .usage_store import UsageStore


async def _post_init(application: Application) -> None:  # type: ignore[type-arg]
    registry: SessionRegistry = application.bot_data["registry"]
    usage_store: UsageStore = application.bot_data["usage_store"]
    await registry.start()
    await usage_store.load()


async def _post_shutdown(application: Application) -> None:  # type: ignore[type-arg]
    registry: SessionRegistry = application.bot_data["registry"]
    await registry.stop()


def build_application() -> Application:  # type: ignore[type-arg]
    settings = TelegramBotSettings.from_env()
    setup_tracing(settings)

    registry = SessionRegistry(settings)
    usage_store = UsageStore(settings.usage_data_path)

    app = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.bot_data["registry"] = registry
    app.bot_data["settings"] = settings
    app.bot_data["usage_store"] = usage_store

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("newgame", newgame_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app


def main() -> int:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    try:
        app = build_application()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Startup error: {exc}", file=sys.stderr)
        return 2

    app.run_polling(allowed_updates=["message", "callback_query"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
