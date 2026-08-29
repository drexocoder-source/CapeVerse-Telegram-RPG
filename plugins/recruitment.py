import random
from typing import Any

from database.mongo import add_hero_to_player, collection, get_profile, list_heroes, record_ledger, update_player


def pull(telegram_id: int) -> dict[str, Any]:
    profile = get_profile(telegram_id)
    if not profile or profile.get("signal_shards", 0) < 1:
        return {"ok": False, "reason": "You need 1 Signal Shard."}
    heroes = list_heroes()
    if not heroes:
        return {"ok": False, "reason": "The Beacon has no published heroes yet."}
    current_boost = int(profile.get("signal_boost", 0))
    if current_boost >= 90:
        guaranteed = [hero for hero in heroes if hero.get("rarity") in {"Epic", "Legendary", "Mythic"}]
        hero = random.choice(guaranteed or heroes)
        next_boost = 0
    else:
        weights = [5 if hero.get("rarity") == "Epic" else 20 for hero in heroes]
        hero = random.choices(heroes, weights=weights, k=1)[0]
        next_boost = min(100, current_boost + 10)
    result = collection("users").update_one(
        {"telegram_id": telegram_id, "signal_shards": {"$gte": 1}},
        {"$inc": {"signal_shards": -1}},
    )
    if result.modified_count != 1:
        return {"ok": False, "reason": "The Beacon could not reserve your Signal Shard. Try again."}
    collection("users").update_one({"telegram_id": telegram_id}, {"$set": {"signal_boost": next_boost}})
    add_hero_to_player(telegram_id, hero["hero_key"])
    current = get_profile(telegram_id)
    record_ledger(telegram_id, "signal_shards", -1, "Recruitment Beacon pull", current.get("signal_shards", 0))
    return {"ok": True, "hero": hero, "balance": current.get("signal_shards", 0), "signal_boost": next_boost}