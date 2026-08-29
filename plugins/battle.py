import random
from typing import Any

from database.mongo import (
    collection,
    create_battle,
    get_battle,
    get_hero,
    get_profile,
    get_team,
    get_villain,
    list_villains,
    record_ledger,
    update_battle,
    update_player,
)


def _choose_enemy(telegram_id: int, mode: str, enemy_key: str | None = None) -> dict[str, Any] | None:
    if enemy_key:
        return get_villain(enemy_key)
    if mode in {"tutorial", "story"}:
        enemies = list_villains("normal")
        return random.choice(enemies) if enemies else None
    if mode in {"rift", "villain"}:
        enemies = list_villains("villain")
        return random.choice(enemies) if enemies else None
    if mode == "arena":
        opponent = collection("users").find_one(
            {"telegram_id": {"$ne": telegram_id}, "origin": {"$ne": ""}},
            sort=[("rating", 1)],
        )
        if not opponent:
            return None
        return {
            "villain_key": f"player_{opponent['telegram_id']}",
            "name": opponent.get("first_name") or opponent.get("username") or "Arena Challenger",
            "enemy_type": "player",
            "hp": 120,
            "attack": 14,
            "ability_signature": "Counter Signal",
            "ability_ultimate": "Final Push",
            "nemesis_for": [],
        }
    return None


def start_battle(
    telegram_id: int,
    mode: str,
    stage: str,
    enemy_key: str | None = None,
    event_reward: int = 0,
) -> dict[str, Any]:
    team = get_team(telegram_id)
    if not team:
        return {"ok": False, "reason": "Your team has no active hero. The owner must publish and assign your Origin starter first."}
    actor_owned = team[0]
    actor = get_hero(actor_owned["hero_key"])
    if not actor:
        return {"ok": False, "reason": "Your active hero is no longer published."}
    enemy = _choose_enemy(telegram_id, mode, enemy_key)
    if not enemy:
        content = "normal enemy" if mode in {"tutorial", "story"} else "villain" if mode == "rift" else "Arena opponent"
        return {"ok": False, "reason": f"No published {content} is available yet."}

    nemesis_available = actor["hero_key"] in enemy.get("nemesis_for", [])
    battle_id = create_battle(
        telegram_id,
        mode,
        stage,
        int(enemy.get("hp", 100)),
        {
            "enemy_key": enemy.get("villain_key", ""),
            "enemy_name": enemy.get("name", "Unknown Threat"),
            "enemy_attack": int(enemy.get("attack", 12)),
            "actor_hero_key": actor["hero_key"],
            "actor_name": actor["name"],
            "move_names": {
                "signature": actor.get("ability_signature", "Signature Move"),
                "utility": actor.get("ability_utility", "Utility Move"),
                "ultimate": actor.get("ability_ultimate", "Ultimate"),
                "nemesis": actor.get("ability_nemesis", "Nemesis Ultimate"),
            },
            "move_damage": {
                "signature": int(actor.get("signature_damage", 24)),
                "utility": int(actor.get("utility_damage", 15)),
                "ultimate": int(actor.get("ultimate_damage", 38)),
                "nemesis": int(actor.get("nemesis_damage", 52)),
            },
            "nemesis_available": nemesis_available,
            "event_reward": int(event_reward),
        },
    )
    return {
        "ok": True,
        "id": battle_id,
        "enemy_name": enemy["name"],
        "enemy_hp": int(enemy.get("hp", 100)),
        "actor_name": actor["name"],
        "move_names": {
            "signature": actor.get("ability_signature", "Signature Move"),
            "utility": actor.get("ability_utility", "Utility Move"),
            "ultimate": actor.get("ability_ultimate", "Ultimate"),
        },
        "nemesis_available": nemesis_available,
    }


def resolve_action(telegram_id: int, battle_id: str, action: str) -> dict[str, Any] | None:
    battle = get_battle(telegram_id, battle_id)
    if not battle or battle["status"] != "active":
        return None
    if action == "nemesis" and not battle.get("nemesis_available"):
        return None

    action_damage = int(battle.get("move_damage", {}).get(action, 10))
    enemy_damage = random.randint(max(4, int(battle.get("enemy_attack", 12)) - 4), int(battle.get("enemy_attack", 12)) + 3)
    new_enemy_hp = max(0, int(battle["enemy_hp"]) - action_damage)
    new_player_hp = max(0, int(battle["player_hp"]) - (max(2, enemy_damage // 2) if action == "utility" else enemy_damage))
    move_name = battle.get("move_names", {}).get(action, action.title())
    log = list(battle.get("log", []))
    log.append(f"Turn {battle['turn']} → {move_name} dealt {action_damage}")
    status = "active"
    if new_enemy_hp == 0:
        status = "won"
        log.append("Victory → threat cleared")
        profile = get_profile(telegram_id) or {}
        reward = int(battle.get("event_reward", 0)) or (150 if battle["mode"] == "rift" else 100 if battle["mode"] == "arena" else 75)
        updates = {"credits": int(profile.get("credits", 0)) + reward}
        if battle["mode"] == "arena":
            updates["rating"] = int(profile.get("rating", 1000)) + 10
        if battle["mode"] == "rift":
            updates["rift_floor"] = int(profile.get("rift_floor", 1)) + 1
        update_player(telegram_id, **updates)
        record_ledger(telegram_id, "credits", reward, f"{battle['mode']} battle victory", updates["credits"])
        log.append(f"Reward → +{reward} Cape Credits")
    elif new_player_hp == 0:
        status = "lost"
        log.append("Defeat → regroup and try again")
    return update_battle(
        battle_id,
        enemy_hp=new_enemy_hp,
        player_hp=new_player_hp,
        turn=int(battle["turn"]) + 1,
        status=status,
        log=log[-8:],
    )