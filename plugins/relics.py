import random
from typing import Any

from database.mongo import get_profile, grant_relic, record_ledger, update_player


RELICS = [
    {"name": "Signal Lens", "slot": "Focus", "rarity": "Rare", "set_name": "Gridwalker", "base_stat": "Attack +8%", "substat": "Speed +3"},
    {"name": "Ashbound Thread", "slot": "Charm", "rarity": "Rare", "set_name": "Last Ember", "base_stat": "Health +10%", "substat": "Resistance +4"},
    {"name": "Rootplate", "slot": "Armor", "rarity": "Epic", "set_name": "Old Growth", "base_stat": "Defense +12%", "substat": "Guard +5"},
]


def craft_relic(telegram_id: int) -> dict[str, Any]:
    profile = get_profile(telegram_id)
    if not profile or int(profile.get("credits", 0)) < 100:
        return {"ok": False, "reason": "You need 100 Cape Credits."}
    new_balance = int(profile.get("credits", 0)) - 100
    update_player(telegram_id, credits=new_balance)
    relic = grant_relic(telegram_id, random.choice(RELICS))
    record_ledger(telegram_id, "credits", -100, "Relic forge", new_balance)
    return {"ok": True, "relic": relic, "balance": new_balance}