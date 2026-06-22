"""Access-code management CLI.

Usage (from the project root, with the venv active):

  python -m backend.telegram.auth.cli generate [--count N] [--data-dir PATH]
  python -m backend.telegram.auth.cli revoke <user_id> [--data-dir PATH]
  python -m backend.telegram.auth.cli list-users [--data-dir PATH]

Codes are printed to stdout only. They are never written to the auth store
(only their SHA-256 hashes are stored).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


def _data_path(args_dir: str | None) -> Path:
    if args_dir:
        return Path(args_dir) / "auth.json"
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    raw = os.getenv("AI_CONTACT_TELEGRAM_AUTH_DATA_PATH", "data/auth.json")
    return Path(raw)


async def _cmd_generate(count: int, path: Path) -> None:
    from .codes import generate_code, code_to_hash
    from .store import AuthStore

    store = AuthStore(path)
    await store.load()

    codes = [generate_code() for _ in range(count)]
    hashes = [code_to_hash(c) for c in codes]
    await store.add_codes(hashes)

    print(f"Generated {count} access code(s). Store them safely — they will not be shown again.\n")
    for code in codes:
        print(f"  {code}")
    print()


async def _cmd_revoke(user_id: int, path: Path) -> None:
    from .store import AuthStore

    store = AuthStore(path)
    await store.load()
    removed = await store.revoke_user(user_id)
    if removed:
        print(f"User {user_id} has been revoked.")
    else:
        print(f"User {user_id} was not in the authorized list.")


async def _cmd_list(path: Path) -> None:
    from .store import AuthStore

    store = AuthStore(path)
    await store.load()
    users = await store.list_authorized()
    if not users:
        print("No authorized users.")
        return
    print(f"{'user_id':<15} {'authorized_at'}")
    print("-" * 40)
    for u in sorted(users, key=lambda x: x["authorized_at"]):
        print(f"{u['user_id']:<15} {u['authorized_at']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.telegram.auth.cli",
        description="Manage Telegram bot access codes and authorized users.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate new access codes")
    gen.add_argument("--count", type=int, default=5, help="Number of codes to generate (default: 5)")
    gen.add_argument("--data-dir", default=None, help="Directory containing auth.json")

    rev = sub.add_parser("revoke", help="Revoke a user's authorization")
    rev.add_argument("user_id", type=int, help="Telegram user ID to revoke")
    rev.add_argument("--data-dir", default=None, help="Directory containing auth.json")

    lst = sub.add_parser("list-users", help="List all authorized users")
    lst.add_argument("--data-dir", default=None, help="Directory containing auth.json")

    args = parser.parse_args()
    path = _data_path(getattr(args, "data_dir", None))

    if args.command == "generate":
        asyncio.run(_cmd_generate(args.count, path))
    elif args.command == "revoke":
        asyncio.run(_cmd_revoke(args.user_id, path))
    elif args.command == "list-users":
        asyncio.run(_cmd_list(path))

    return 0


if __name__ == "__main__":
    sys.exit(main())
