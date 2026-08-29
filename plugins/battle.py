import random
from typing import Any

from database.mongo import create_battle, get_battle, get_profile, record_ledger, update_battle, update_player


ENEMIES = {
    "tutorial": ("Null Hound", 78),
    "story": ("Signal Thief", 105),
    "arena": ("Rival Captain", 120),
    "rift": ("The Null Regent", 160),
}


def start_battle(telegram_id: int, mode: str, stage: str) -> dict[str, Any]:
    enemy_name, enemy_hp = ENEMIES.get(mode, ("Unknown Threat", 100))
    battle_id = create_battle(telegram_id, mode, stage, enemy_hp)
    return {"id": battle_id, "enemy_name": enemy_name, "enemy_hp": enemy_hp}


def resolve_action(telegram_id: int, battle_id: str, action: str) -> dict[str, Any] | None:
    battle = get_battle(telegram_id, battle_id)
    if not battle or battle["status"] != "active":
        return None

    action_damage = {"signature": 24, "utility": 15, "ultimate": 38}.get(action, 12)
    if action == "nemesis" and battle["mode"] == "rift":
        action_damage = 52
    enemy_damage = random.randint(7, 16)
    new_enemy_hp = max(0, int(battle["enemy_hp"]) - action_damage)
    new_player_hp = max(0, int(battle["player_hp"]) - (0 if action == "utility" else enemy_damage))
    log = list(battle.get("log", []))
    log.append(f"Turn {battle['turn']} → {action.title()} dealt {action_damage}")
    status = "active"
    if new_enemy_hp == 0:
        status = "won"
        log.append("Victory → threat cleared")
        profile = get_profile(telegram_id) or {}
        reward = 150 if battle["mode"] == "rift" else 100 if battle["mode"] == "arena" else 75
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
    updated = update_battle(
        battle_id,
        enemy_hp=new_enemy_hp,
        player_hp=new_player_hp,
        turn=int(battle["turn"]) + 1,
        status=status,
        log=log[-8:],
    )
    return updated