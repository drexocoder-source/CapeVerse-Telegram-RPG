import asyncio
import os

from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from pyrogram.parser.parser import Parser
from pyrogram.types import BotCommand

from database.mongo import init_db
from handlers.admin import register as register_admin
from handlers.player import register


def create_bot() -> Client | None:
    bot_token = os.getenv("BOT_TOKEN", "")
    api_id = os.getenv("API_ID", "")
    api_hash = os.getenv("API_HASH", "")
    if not bot_token or not api_id or not api_hash:
        return None
    if not getattr(Parser.parse, "_capeverse_compat", False):
        original_parse = Parser.parse

        async def parse_compat(parser, text, mode=None):
            if isinstance(mode, str) and mode.lower() == "html":
                mode = ParseMode.HTML
            return await original_parse(parser, text, mode)

        parse_compat._capeverse_compat = True
        Parser.parse = parse_compat
    client = Client(
        "capeverse_bot",
        api_id=int(api_id),
        api_hash=api_hash,
        bot_token=bot_token,
        in_memory=True,
    )
    register_admin(client)
    register(client)
    return client


def run_bot() -> None:
    try:
        init_db()
    except Exception as exc:
        print(f"CapeVerse database setup is incomplete: {exc}")
        return
    client = create_bot()
    if client is None:
        print("CapeVerse bot setup is incomplete. Add BOT_TOKEN, API_ID, and API_HASH.")
        return
    async def serve() -> None:
        await client.start()
        print("CapeVerse Kurigram bot is running.", flush=True)
        async def register_commands() -> None:
            try:
                await client.set_bot_commands([
                    BotCommand("start", "Start or reopen CapeVerse"),
                    BotCommand("main", "Open the main game menu"),
                    BotCommand("inventory", "View wallet, collection and rewards"),
                    BotCommand("profile", "Generate your player dossier"),
                    BotCommand("char", "Search the global character codex"),
                    BotCommand("mychar", "View one of your owned characters"),
                    BotCommand("daily", "Claim the daily signal reward"),
                    BotCommand("weekly", "Claim the weekly signal reward"),
                    BotCommand("guide", "Open the complete guide center"),
                    BotCommand("owner", "Open owner tools"),
                ])
                print("CapeVerse command menu registered.", flush=True)
            except Exception as exc:
                print(f"CapeVerse command menu registration deferred: {exc}", flush=True)

        asyncio.create_task(register_commands())
        await idle()
        await client.stop()

    print("CapeVerse Kurigram bot is starting.", flush=True)
    client.run(serve())


if __name__ == "__main__":
    run_bot()