from typing import Any

from database.mongo import get_villain, list_events
from plugins.battle import start_battle


def available_events() -> list[dict[str, Any]]:
    return [event for event in list_events() if get_villain(event.get("boss_key", ""))]


def start_event_boss(telegram_id: int, event_key: str) -> dict[str, Any]:
    event = next((item for item in available_events() if item.get("event_key") == event_key), None)
    if not event:
        return {"ok": False, "reason": "This event or its boss is not published."}
    return start_battle(
        telegram_id,
        "event",
        event["title"],
        enemy_key=event["boss_key"],
        event_reward=int(event.get("reward_credits", 200)),
    )