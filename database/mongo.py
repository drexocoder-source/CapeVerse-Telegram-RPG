import json
import os
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
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
    database_name = MongoClient(MONGODB_URI).get_default_database().name if "/" in MONGODB_URI.rsplit("/", 1)[-1] else MONGODB_DATABASE
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
    seed_content()


def get_or_create_user(telegram_id: int, username: str = "", first_name: str = "") -> dict[str, Any]:
    users = collection("users")
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
                "credits": 500,
                "signal_shards": 2,
                "prism_cores": 0,
                "patrol_intel": 5,
                "rating": 1000,
                "rift_floor": 1,
                "guide_sent": False,
                "created_at": now(),
            },
        },
        upsert=True,
    )
    return users.find_one({"telegram_id": telegram_id}) or {}


def get_profile(telegram_id: int) -> dict[str, Any] | None:
    return collection("users").find_one({"telegram_id": telegram_id})


def update_player(telegram_id: int, **fields: Any) -> dict[str, Any] | None:
    allowed = {
        "origin",
        "passive",
        "credits",
        "signal_shards",
        "prism_cores",
        "patrol_intel",
        "rating",
        "rift_floor",
        "guide_sent",
    }
    clean = {key: value for key, value in fields.items() if key in allowed}
    if clean:
        clean["last_seen_at"] = now()
        collection("users").update_one({"telegram_id": telegram_id}, {"$set": clean})
    return get_profile(telegram_id)


def list_heroes(status: str = "published") -> list[dict[str, Any]]:
    query = {} if status == "all" else {"status": status}
    return list(collection("heroes").find(query).sort([("rarity", DESCENDING), ("name", ASCENDING)]))


def get_hero(hero_key: str) -> dict[str, Any] | None:
    return collection("heroes").find_one({"hero_key": hero_key})


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


def create_battle(telegram_id: int, mode: str, stage: str, enemy_hp: int = 100) -> str:
    result = collection("battles").insert_one(
        {
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

    clean = {key: value for key, value in fields.items() if key in {"status", "turn", "player_hp", "enemy_hp", "log"}}
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


def review_submission(submission_id: str, status: str, reviewer: str, note: str = "") -> None:
    from bson import ObjectId

    collection("content_submissions").update_one(
        {"_id": ObjectId(submission_id)},
        {"$set": {"status": status, "reviewed_by": reviewer, "review_note": note, "reviewed_at": now()}},
    )


def upsert_moderator(telegram_id: int, username: str, permissions: list[str]) -> None:
    collection("moderators").update_one(
        {"telegram_id": telegram_id},
        {
            "$set": {"username": username, "permissions": permissions, "active": True, "updated_at": now()},
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


def seed_content() -> None:
    heroes = [
        {
            "hero_key": "volt_warden",
            "name": "Volt Warden",
            "codename": "The Living Circuit",
            "source": "Capeverse Original",
            "rights_status": "approved",
            "universe": "Capeverse Originals",
            "faction": "Independent",
            "role": "Controller",
            "rarity": "Epic",
            "alignment": "Hero",
            "description": "A city-grid guardian who turns broken signals into protective force.",
            "ability_signature": "Arc Mark → shocks one enemy and lowers speed.",
            "ability_utility": "Grid Step → shields the weakest ally.",
            "ability_ultimate": "Overload Protocol → damages all enemies and stuns the leader.",
            "status": "published",
        },
        {
            "hero_key": "ash_oracle",
            "name": "Ash Oracle",
            "codename": "Keeper of the Last Ember",
            "source": "Original Indian-Inspired",
            "rights_status": "approved",
            "universe": "Bhoomi-1",
            "faction": "Hollow Choir",
            "role": "Support",
            "rarity": "Rare",
            "alignment": "Vigilante",
            "description": "A memory-reader who protects a neighborhood with firelight and foresight.",
            "ability_signature": "Cinder Thread → heals one ally over two turns.",
            "ability_utility": "Read the Smoke → reveals the next enemy action.",
            "ability_ultimate": "Ember Reversal → restores team health and clears one debuff.",
            "status": "published",
        },
        {
            "hero_key": "ironbark_sentinel",
            "name": "Ironbark Sentinel",
            "codename": "The Rooted Shield",
            "source": "Capeverse Original",
            "rights_status": "approved",
            "universe": "Earth-Prime",
            "faction": "Independent",
            "role": "Defender",
            "rarity": "Rare",
            "alignment": "Hero",
            "description": "A patient protector whose living armor grows stronger under pressure.",
            "ability_signature": "Rootline → taunts an enemy and gains guard.",
            "ability_utility": "Bastion Pulse → grants armor to the team.",
            "ability_ultimate": "Old Growth → restores guard and counters the next hit.",
            "status": "published",
        },
    ]
    for hero in heroes:
        seed_hero(hero)