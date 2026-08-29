import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database


MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "capeverse")
_client: MongoClient | None = None


def now() -> datetime:
    return datetime.now(timezone.utc)


def get_db() -> Database:
    global _client
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI is not configured")
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=4000)
    try:
        database_name = _client.get_default_database().name
    except Exception:
        database_name = MONGODB_DATABASE
    return _client[database_name or MONGODB_DATABASE]


def collection(name: str) -> Collection:
    return get_db()[name]


def init_db() -> None:
    database = get_db()
    database.users.create_index([("telegram_id", ASCENDING)], unique=True)
    database.heroes.create_index([("hero_key", ASCENDING)], unique=True)
    database.heroes.create_index([("status", ASCENDING), ("rarity", DESCENDING)])
    database.owned_heroes.create_index([("telegram_id", ASCENDING), ("hero_key", ASCENDING)], unique=True)
    database.teams.create_index([("telegram_id", ASCENDING), ("team_number", ASCENDING)], unique=True)
    database.battles.create_index([("telegram_id", ASCENDING), ("status", ASCENDING)])
    database.content_submissions.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    database.moderators.create_index([("telegram_id", ASCENDING)], unique=True)
    database.villains.create_index([("villain_key", ASCENDING)], unique=True)
    database.villains.create_index([("enemy_type", ASCENDING), ("status", ASCENDING)])
    database.events.create_index([("event_key", ASCENDING)], unique=True)
    database.events.create_index([("status", ASCENDING)])
    database.content_wizards.create_index([("telegram_id", ASCENDING)], unique=True)
    database.reward_claims.create_index([("telegram_id", ASCENDING), ("period", ASCENDING)], unique=True)
    database.character_research.create_index([("telegram_id", ASCENDING), ("hero_key", ASCENDING)], unique=True)
    remove_default_seed_content()


def get_or_create_user(telegram_id: int, username: str = "", first_name: str = "") -> dict[str, Any]:
    user, _ = get_or_create_user_with_status(telegram_id, username, first_name)
    return user


def get_or_create_user_with_status(telegram_id: int, username: str = "", first_name: str = "") -> tuple[dict[str, Any], bool]:
    users = collection("users")
    existing = users.find_one({"telegram_id": telegram_id})
    if existing:
        users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"username": username or "", "first_name": first_name or "", "last_seen_at": now()}},
        )
        return users.find_one({"telegram_id": telegram_id}) or existing, False
    users.update_one(
        {"telegram_id": telegram_id},
        {
            "$set": {
                "username": username or "",
                "first_name": first_name or "",
                "last_seen_at": now(),
            },
            "$setOnInsert": {
                "telegram_id": telegram_id,
                "origin": "",
                "passive": "",
                "alignment": "Hero",
                "credits": 500,
                "signal_shards": 2,
                "prism_cores": 0,
                "patrol_intel": 5,
                "rating": 1000,
                "rift_floor": 1,
                "signal_boost": 0,
                "guide_sent": False,
                "xp": 0,
                "level": 1,
                "created_at": now(),
            },
        },
        upsert=True,
    )
    return users.find_one({"telegram_id": telegram_id}) or {}, True


def get_profile(telegram_id: int) -> dict[str, Any] | None:
    return collection("users").find_one({"telegram_id": telegram_id})


def update_player(telegram_id: int, **fields: Any) -> dict[str, Any] | None:
    allowed = {
        "origin",
        "passive",
        "alignment",
        "credits",
        "signal_shards",
        "prism_cores",
        "patrol_intel",
        "rating",
        "rift_floor",
        "signal_boost",
        "guide_sent",
        "xp",
        "level",
    }
    clean = {key: value for key, value in fields.items() if key in allowed}
    if clean:
        clean["last_seen_at"] = now()
        collection("users").update_one({"telegram_id": telegram_id}, {"$set": clean})
    return get_profile(telegram_id)


def inventory_summary(telegram_id: int) -> dict[str, Any]:
    profile = get_profile(telegram_id) or {}
    return {
        "credits": int(profile.get("credits", 0)),
        "signal_shards": int(profile.get("signal_shards", 0)),
        "prism_cores": int(profile.get("prism_cores", 0)),
        "patrol_intel": int(profile.get("patrol_intel", 0)),
        "heroes": collection("owned_heroes").count_documents({"telegram_id": telegram_id}),
        "relics": collection("relic_instances").count_documents({"telegram_id": telegram_id}),
        "research": collection("character_research").count_documents({"telegram_id": telegram_id}),
    }


def claim_timed_reward(telegram_id: int, period: str) -> dict[str, Any]:
    if period not in {"daily", "weekly"}:
        return {"ok": False, "reason": "Unknown reward period."}
    profile = get_profile(telegram_id)
    if not profile:
        return {"ok": False, "reason": "Create your player profile first with /start."}
    current = now()
    interval = timedelta(days=1 if period == "daily" else 7)
    claim_id = f"{telegram_id}:{period}"
    claims = collection("reward_claims")
    claims.update_one(
        {"_id": claim_id},
        {"$setOnInsert": {
            "telegram_id": telegram_id,
            "period": period,
            "next_claim_at": datetime(1970, 1, 1, tzinfo=timezone.utc),
            "streak": 0,
            "last_claim_at": None,
        }},
        upsert=True,
    )
    previous = claims.find_one({"_id": claim_id}) or {}
    locked = claims.find_one_and_update(
        {"_id": claim_id, "next_claim_at": {"$lte": current}},
        {"$set": {"last_claim_at": current, "next_claim_at": current + interval}},
        return_document=ReturnDocument.AFTER,
    )
    if not locked:
        waiting = claims.find_one({"_id": claim_id}) or {}
        return {"ok": False, "reason": "Reward already claimed.", "next_claim_at": waiting.get("next_claim_at")}
    last_claim = previous.get("last_claim_at")
    if last_claim and last_claim.tzinfo is None:
        last_claim = last_claim.replace(tzinfo=timezone.utc)
    streak = int(previous.get("streak", 0)) + 1 if last_claim and current - last_claim <= interval * 2 else 1
    rewards = (
        {"credits": 20 + min(10, streak * 2), "patrol_intel": 1 if streak % 3 == 0 else 0, "signal_shards": 0, "xp": 5}
        if period == "daily"
        else {"credits": 100 + min(40, streak * 10), "patrol_intel": 1, "signal_shards": 1 if streak % 2 == 0 else 0, "xp": 25}
    )
    updated = update_player(
        telegram_id,
        credits=int(profile.get("credits", 0)) + rewards["credits"],
        patrol_intel=int(profile.get("patrol_intel", 0)) + rewards["patrol_intel"],
        signal_shards=int(profile.get("signal_shards", 0)) + rewards["signal_shards"],
    ) or profile
    updated = grant_user_xp(telegram_id, rewards["xp"]) or updated
    claims.update_one({"_id": claim_id}, {"$set": {"streak": streak}})
    record_ledger(telegram_id, "credits", rewards["credits"], f"{period.title()} reward", int(updated.get("credits", 0)))
    return {
        "ok": True,
        "period": period,
        "rewards": rewards,
        "streak": streak,
        "next_claim_at": locked.get("next_claim_at"),
        "profile": updated,
    }


def research_character(telegram_id: int, hero_key: str) -> dict[str, Any]:
    hero = get_hero(hero_key)
    if not hero:
        return {"ok": False, "reason": "Character not found."}
    if not str(hero.get("source", "")).lower().startswith("licensed"):
        return {"ok": False, "reason": "Research Archives are reserved for licensed suit and form catalogs."}
    result = collection("character_research").update_one(
        {"telegram_id": telegram_id, "hero_key": hero_key},
        {
            "$setOnInsert": {
                "telegram_id": telegram_id,
                "hero_key": hero_key,
                "name": hero.get("name", hero_key),
                "status": "researched",
                "discovered_at": now(),
            },
            "$set": {"last_viewed_at": now()},
        },
        upsert=True,
    )
    return {"ok": True, "new": bool(result.upserted_id), "hero": hero}


def is_character_researched(telegram_id: int, hero_key: str) -> bool:
    return collection("character_research").find_one({"telegram_id": telegram_id, "hero_key": hero_key}) is not None


def list_heroes(status: str = "published") -> list[dict[str, Any]]:
    query = {} if status == "all" else {"status": status}
    return list(collection("heroes").find(query).sort([("rarity", DESCENDING), ("name", ASCENDING)]))


def get_hero(hero_key: str) -> dict[str, Any] | None:
    return collection("heroes").find_one({"hero_key": hero_key})


def get_starter_hero(origin: str) -> dict[str, Any] | None:
    return collection("heroes").find_one(
        {
            "status": "published",
            "is_starter": True,
            "starter_origin": {"$regex": f"^{origin}$", "$options": "i"},
        }
    )


def list_owned_heroes(telegram_id: int) -> list[dict[str, Any]]:
    return list(collection("owned_heroes").find({"telegram_id": telegram_id}).sort([("stars", DESCENDING), ("level", DESCENDING), ("name", ASCENDING)]))


def add_hero_to_player(telegram_id: int, hero_key: str) -> dict[str, Any] | None:
    hero = get_hero(hero_key)
    if not hero:
        return None
    owned = collection("owned_heroes")
    owned.update_one(
        {"telegram_id": telegram_id, "hero_key": hero_key},
        {
            "$setOnInsert": {
                "telegram_id": telegram_id,
                "hero_key": hero_key,
                "name": hero["name"],
                "codename": hero["codename"],
                "role": hero["role"],
                "rarity": hero["rarity"],
                "universe": hero["universe"],
                "alignment": hero["alignment"],
                "level": 1,
                "xp": 0,
                "evolved": False,
                "created_at": now(),
            },
            "$inc": {"stars": 1},
        },
        upsert=True,
    )
    return owned.find_one({"telegram_id": telegram_id, "hero_key": hero_key})


def xp_to_next(level: int) -> int:
    return max(100, int(level) * 100)


def grant_user_xp(telegram_id: int, amount: int) -> dict[str, Any] | None:
    profile = get_profile(telegram_id) or {}
    xp = int(profile.get("xp", 0)) + max(0, int(amount))
    level = max(1, int(profile.get("level", 1)))
    while xp >= xp_to_next(level):
        xp -= xp_to_next(level)
        level += 1
    return update_player(telegram_id, xp=xp, level=level)


def grant_character_xp(telegram_id: int, hero_key: str, amount: int) -> dict[str, Any] | None:
    owned = collection("owned_heroes").find_one({"telegram_id": telegram_id, "hero_key": hero_key})
    if not owned:
        return None
    xp = int(owned.get("xp", 0)) + max(0, int(amount))
    level = max(1, int(owned.get("level", 1)))
    while xp >= xp_to_next(level):
        xp -= xp_to_next(level)
        level += 1
    collection("owned_heroes").update_one(
        {"telegram_id": telegram_id, "hero_key": hero_key},
        {"$set": {"xp": xp, "level": level, "updated_at": now()}},
    )
    return collection("owned_heroes").find_one({"telegram_id": telegram_id, "hero_key": hero_key})


def get_owned_hero(telegram_id: int, hero_key: str) -> dict[str, Any] | None:
    return collection("owned_heroes").find_one({"telegram_id": telegram_id, "hero_key": hero_key})


def evolve_character(telegram_id: int, hero_key: str) -> dict[str, Any]:
    owned = get_owned_hero(telegram_id, hero_key)
    if not owned:
        return {"ok": False, "reason": "You do not own this hero."}
    if owned.get("evolved"):
        return {"ok": False, "reason": "This character has already evolved."}
    if int(owned.get("level", 1)) < 10:
        return {"ok": False, "reason": "Reach character level 10 first."}
    if int(owned.get("stars", 0)) < 3:
        return {"ok": False, "reason": "Collect 3 duplicate signals for evolution."}
    collection("owned_heroes").update_one(
        {"telegram_id": telegram_id, "hero_key": hero_key},
        {"$set": {"evolved": True, "updated_at": now()}},
    )
    return {"ok": True, "character": collection("owned_heroes").find_one({"telegram_id": telegram_id, "hero_key": hero_key})}


def update_hero(hero_key: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {
        "name", "codename", "origin_type", "universe", "place", "faction",
        "description", "move_direction", "image_url", "role", "rarity", "alignment", "move_sets",
        "evolution_concepts", "research_concepts", "ai_design_summary",
        "ability_signature", "signature_damage", "ability_utility",
        "utility_damage", "ability_ultimate", "ultimate_damage",
    }
    clean = {key: value for key, value in fields.items() if key in allowed}
    if clean:
        clean["updated_at"] = now()
        collection("heroes").update_one({"hero_key": hero_key}, {"$set": clean})
    return collection("heroes").find_one({"hero_key": hero_key})


def search_players(query: str, limit: int = 10) -> list[dict[str, Any]]:
    value = query.strip()
    if value.lstrip("-").isdigit():
        player = collection("users").find_one({"telegram_id": int(value)})
        return [player] if player else []
    regex = {"$regex": re.escape(value[:80]), "$options": "i"}
    return list(collection("users").find({"$or": [{"first_name": regex}, {"username": regex}]}).limit(limit))


def save_team(telegram_id: int, owned_ids: list[str], team_number: int = 1) -> None:
    collection("teams").update_one(
        {"telegram_id": telegram_id, "team_number": team_number},
        {
            "$set": {
                "telegram_id": telegram_id,
                "team_number": team_number,
                "name": f"Team {team_number}",
                "members": owned_ids[:3],
                "updated_at": now(),
            },
            "$setOnInsert": {"created_at": now()},
        },
        upsert=True,
    )


def get_team(telegram_id: int, team_number: int = 1) -> list[dict[str, Any]]:
    team = collection("teams").find_one({"telegram_id": telegram_id, "team_number": team_number})
    if not team:
        return []
    members = {str(hero["_id"]): hero for hero in list_owned_heroes(telegram_id)}
    return [members[owned_id] for owned_id in team.get("members", []) if owned_id in members]


def record_ledger(telegram_id: int, currency: str, amount: int, reason: str, balance_after: int) -> None:
    collection("ledger").insert_one(
        {
            "telegram_id": telegram_id,
            "currency": currency,
            "amount": amount,
            "reason": reason,
            "balance_after": balance_after,
            "created_at": now(),
        }
    )


def create_battle(
    telegram_id: int,
    mode: str,
    stage: str,
    enemy_hp: int = 100,
    extra: dict[str, Any] | None = None,
) -> str:
    payload = {
        "telegram_id": telegram_id,
        "mode": mode,
        "stage": stage,
        "status": "active",
        "turn": 1,
        "player_hp": 100,
        "enemy_hp": enemy_hp,
        "log": [],
        "created_at": now(),
        "updated_at": now(),
    }
    payload.update(extra or {})
    result = collection("battles").insert_one(
        payload
    )
    return str(result.inserted_id)


def get_battle(telegram_id: int, battle_id: str) -> dict[str, Any] | None:
    from bson import ObjectId

    try:
        return collection("battles").find_one({"_id": ObjectId(battle_id), "telegram_id": telegram_id})
    except Exception:
        return None


def update_battle(battle_id: str, **fields: Any) -> dict[str, Any] | None:
    from bson import ObjectId

    clean = {
        key: value for key, value in fields.items()
        if key in {"status", "turn", "player_hp", "enemy_hp", "log", "cooldowns"}
    }
    clean["updated_at"] = now()
    try:
        collection("battles").update_one({"_id": ObjectId(battle_id)}, {"$set": clean})
        return collection("battles").find_one({"_id": ObjectId(battle_id)})
    except Exception:
        return None


def seed_hero(data: dict[str, Any]) -> None:
    payload = {**data, "created_at": now()}
    collection("heroes").update_one({"hero_key": data["hero_key"]}, {"$setOnInsert": payload}, upsert=True)


def add_submission(kind: str, title: str, payload: dict[str, Any], submitted_by: str) -> str:
    result = collection("content_submissions").insert_one(
        {
            "content_kind": kind,
            "title": title,
            "payload": payload,
            "status": "pending",
            "submitted_by": submitted_by,
            "reviewed_by": "",
            "review_note": "",
            "created_at": now(),
        }
    )
    return str(result.inserted_id)


def list_submissions(status: str = "pending") -> list[dict[str, Any]]:
    return list(collection("content_submissions").find({"status": status}).sort("created_at", DESCENDING))


def get_content_wizard(telegram_id: int) -> dict[str, Any] | None:
    return collection("content_wizards").find_one({"telegram_id": telegram_id})


def save_content_wizard(
    telegram_id: int,
    kind: str,
    step: int,
    payload: dict[str, Any],
    first_name: str = "",
) -> dict[str, Any]:
    collection("content_wizards").update_one(
        {"telegram_id": telegram_id},
        {
            "$set": {
                "telegram_id": telegram_id,
                "kind": kind,
                "step": step,
                "payload": payload,
                "first_name": first_name,
                "updated_at": now(),
            },
            "$setOnInsert": {"created_at": now()},
        },
        upsert=True,
    )
    return get_content_wizard(telegram_id) or {}


def delete_content_wizard(telegram_id: int) -> None:
    collection("content_wizards").delete_one({"telegram_id": telegram_id})


def review_submission(submission_id: str, status: str, reviewer: str, note: str = "") -> None:
    from bson import ObjectId

    collection("content_submissions").update_one(
        {"_id": ObjectId(submission_id)},
        {"$set": {"status": status, "reviewed_by": reviewer, "review_note": note, "reviewed_at": now()}},
    )


def upsert_moderator(telegram_id: int, first_name: str, permissions: list[str]) -> None:
    collection("moderators").update_one(
        {"telegram_id": telegram_id},
        {
            "$set": {"first_name": first_name, "permissions": permissions, "active": True, "updated_at": now()},
            "$setOnInsert": {"telegram_id": telegram_id, "created_at": now()},
        },
        upsert=True,
    )


def list_moderators() -> list[dict[str, Any]]:
    return list(collection("moderators").find({"active": True}).sort("created_at", DESCENDING))


def get_stats() -> dict[str, int]:
    database = get_db()
    return {
        "players": database.users.count_documents({}),
        "heroes": database.heroes.count_documents({"status": "published"}),
        "pending": database.content_submissions.count_documents({"status": "pending"}),
        "battles": database.battles.count_documents({}),
        "moderators": database.moderators.count_documents({"active": True}),
    }


def list_relics(telegram_id: int) -> list[dict[str, Any]]:
    return list(collection("relic_instances").find({"telegram_id": telegram_id}).sort("created_at", DESCENDING))


def grant_relic(telegram_id: int, relic: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "telegram_id": telegram_id,
        "name": relic["name"],
        "slot": relic["slot"],
        "rarity": relic["rarity"],
        "set_name": relic["set_name"],
        "base_stat": relic["base_stat"],
        "substat": relic["substat"],
        "level": 1,
        "equipped_to": "",
        "created_at": now(),
    }
    result = collection("relic_instances").insert_one(payload)
    return {**payload, "_id": result.inserted_id}


def publish_content(kind: str, title: str, payload: dict[str, Any]) -> None:
    collection("content").update_one(
        {"kind": kind, "title": title},
        {
            "$set": {
                "kind": kind,
                "title": title,
                "payload": payload,
                "status": "published",
                "updated_at": now(),
            },
            "$setOnInsert": {"created_at": now()},
        },
        upsert=True,
    )


def publish_villain(data: dict[str, Any]) -> None:
    payload = {
        **data,
        "hp": int(data.get("hp", 100)),
        "attack": int(data.get("attack", 12)),
        "status": "published",
        "updated_at": now(),
    }
    collection("villains").update_one(
        {"villain_key": payload["villain_key"]},
        {"$set": payload, "$setOnInsert": {"created_at": now()}},
        upsert=True,
    )


def list_villains(enemy_type: str | None = None, player_level: int | None = None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"status": "published"}
    if enemy_type:
        query["enemy_type"] = enemy_type
    if player_level is not None:
        query["$and"] = [
            {"$or": [{"min_level": {"$lte": player_level}}, {"min_level": {"$exists": False}}]},
            {"$or": [{"max_level": {"$gte": player_level}}, {"max_level": {"$exists": False}}]},
        ]
    return list(collection("villains").find(query).sort("name", ASCENDING))


def get_villain(villain_key: str) -> dict[str, Any] | None:
    return collection("villains").find_one({"villain_key": villain_key, "status": "published"})


def publish_event(data: dict[str, Any]) -> None:
    collection("events").update_one(
        {"event_key": data["event_key"]},
        {
            "$set": {**data, "status": "published", "updated_at": now()},
            "$setOnInsert": {"created_at": now()},
        },
        upsert=True,
    )


def list_events() -> list[dict[str, Any]]:
    return list(collection("events").find({"status": "published"}).sort("created_at", DESCENDING))


def remove_default_seed_content() -> None:
    default_keys = ["volt_warden", "ash_oracle", "ironbark_sentinel"]
    owned = list(collection("owned_heroes").find({"hero_key": {"$in": default_keys}}, {"_id": 1}))
    owned_ids = [str(item["_id"]) for item in owned]
    collection("heroes").delete_many({"hero_key": {"$in": default_keys}})
    collection("owned_heroes").delete_many({"hero_key": {"$in": default_keys}})
    if owned_ids:
        collection("teams").update_many({}, {"$pull": {"members": {"$in": owned_ids}}})