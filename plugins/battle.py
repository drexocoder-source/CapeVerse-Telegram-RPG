import random
from copy import deepcopy
from typing import Any

from database.mongo import (
    collection,
    create_battle,
    get_battle,
    get_hero,
    get_profile,
    get_team,
    get_villain,
    grant_character_xp,
    grant_user_xp,
    list_heroes,
    list_villains,
    record_ledger,
    update_battle,
    update_player,
)


def _choose_enemy(
    telegram_id: int,
    mode: str,
    player_level: int,
    enemy_key: str | None = None,
    opponent_telegram_id: int | None = None,
) -> dict[str, Any] | None:
    if enemy_key:
        return get_villain(enemy_key)
    if mode in {"tutorial", "story"}:
        enemies = list_villains("normal", player_level)
        return random.choice(enemies) if enemies else None
    if mode in {"rift", "villain"}:
        enemies = list_villains("villain", player_level)
        return random.choice(enemies) if enemies else None
    if mode == "arena":
        opponent = (
            collection("users").find_one({"telegram_id": opponent_telegram_id, "origin": {"$ne": ""}})
            if opponent_telegram_id
            else collection("users").find_one(
                {"telegram_id": {"$ne": telegram_id}, "origin": {"$ne": ""}},
                sort=[("rating", 1)],
            )
        )
        if not opponent:
            return None
        opponent_team = get_team(int(opponent["telegram_id"]))
        if opponent_team:
            lead_owned = opponent_team[0]
            lead = get_hero(lead_owned["hero_key"])
            if lead:
                lead_level = max(1, int(lead_owned.get("level", 1)))
                return {
                    **lead,
                    "villain_key": f"player_{opponent['telegram_id']}_{lead['hero_key']}",
                    "name": f"{opponent.get('first_name') or opponent.get('username') or 'Challenger'} · {lead['name']}",
                    "enemy_type": "player",
                    "hp": 100 + (lead_level - 1) * 8,
                    "attack": max(8, int(lead.get("signature_damage", 14))),
                    "min_level": lead_level,
                    "nemesis_for": [],
                }
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


def _scale_enemy(enemy: dict[str, Any], player_level: int, randomize_level: bool = False) -> dict[str, Any]:
    scaled = deepcopy(enemy)
    base_level = max(1, int(enemy.get("min_level", 1)))
    max_level = max(base_level, int(enemy.get("max_level", max(base_level, player_level + 2))))
    if randomize_level:
        low = max(base_level, player_level - 2)
        high = min(max_level, player_level + 2)
        effective_level = random.randint(low, max(low, high))
    else:
        effective_level = max(base_level, min(max_level, player_level))
    multiplier = 1.0 + max(0, effective_level - base_level) * 0.08
    scaled["level"] = effective_level
    scaled["hp"] = max(20, round(int(enemy.get("hp", 100)) * multiplier))
    scaled["attack"] = max(1, round(int(enemy.get("attack", 12)) * multiplier))
    scaled_moves = {}
    for category, moves in (enemy.get("move_sets") or {}).items():
        scaled_moves[category] = [
            {**move, "damage": max(0, round(int(move.get("damage", 10)) * multiplier))}
            for move in moves
        ]
    if scaled_moves:
        scaled["move_sets"] = scaled_moves
    return scaled


def _character_moves(character: dict[str, Any], level: int) -> list[dict[str, Any]]:
    move_sets = character.get("move_sets") or {}
    moves: list[dict[str, Any]] = []
    for category in ("normal", "defense", "special"):
        for index, move in enumerate(move_sets.get(category, [])):
            if int(move.get("unlock_level", 1)) <= level:
                moves.append({
                    **move,
                    "category": category,
                    "key": f"{category}_{index + 1}",
                })
    if moves:
        return moves
    return [
        {"key": "signature", "category": "normal", "name": character.get("ability_signature", "Signature Move"), "damage": int(character.get("signature_damage", 24)), "cooldown": 0},
        {"key": "utility", "category": "defense", "name": character.get("ability_utility", "Guard"), "damage": int(character.get("utility_damage", 10)), "cooldown": 1},
        {"key": "ultimate", "category": "special", "name": character.get("ability_ultimate", "Ultimate"), "damage": int(character.get("ultimate_damage", 38)), "cooldown": 2},
    ]


def start_battle(
    telegram_id: int,
    mode: str,
    stage: str,
    enemy_key: str | None = None,
    event_reward: int = 0,
    opponent_telegram_id: int | None = None,
) -> dict[str, Any]:
    team = get_team(telegram_id)
    if not team:
        return {"ok": False, "reason": "Your team has no active hero. The owner must publish and assign your Origin starter first."}
    actor_owned = team[0]
    actor = get_hero(actor_owned["hero_key"])
    if not actor:
        return {"ok": False, "reason": "Your active hero is no longer published."}
    profile = get_profile(telegram_id) or {}
    player_level = max(1, int(profile.get("level", 1)))
    enemy = _choose_enemy(telegram_id, mode, player_level, enemy_key, opponent_telegram_id)
    if not enemy:
        content = "normal enemy" if mode in {"tutorial", "story"} else "villain" if mode == "rift" else "Arena opponent"
        return {"ok": False, "reason": f"No published {content} is available yet."}

    enemy = _scale_enemy(enemy, player_level, randomize_level=mode == "story")
    actor_level = max(1, int(actor_owned.get("level", 1)))
    available_moves = _character_moves(actor, actor_level)
    nemesis_available = actor["hero_key"] in enemy.get("nemesis_for", [])
    if nemesis_available:
        available_moves.append({
            "key": "nemesis",
            "category": "special",
            "name": actor.get("ability_nemesis", "Nemesis Ultimate"),
            "damage": int(actor.get("nemesis_damage", 52)),
            "cooldown": 3,
            "unlock_level": 1,
        })
    enemy_moves = _character_moves(enemy, int(enemy.get("level", 1)))
    enemy_normal = next((move for move in enemy_moves if move["category"] == "normal"), enemy_moves[0])
    enemy_special = next((move for move in enemy_moves if move["category"] == "special"), enemy_moves[-1])
    player_max_hp = 100 + (actor_level - 1) * 8
    battle_id = create_battle(
        telegram_id,
        mode,
        stage,
        int(enemy.get("hp", 100)),
        {
            "enemy_key": enemy.get("villain_key", ""),
            "enemy_name": enemy.get("name", "Unknown Threat"),
            "enemy_attack": int(enemy.get("attack", 12)),
            "enemy_level": int(enemy.get("level", 1)),
            "enemy_move_names": {"signature": enemy_normal["name"], "ultimate": enemy_special["name"]},
            "enemy_move_damage": {"signature": int(enemy_normal["damage"]), "ultimate": int(enemy_special["damage"])},
            "enemy_max_hp": int(enemy.get("hp", 100)),
            "player_max_hp": player_max_hp,
            "player_hp": player_max_hp,
            "actor_hero_key": actor["hero_key"],
            "actor_name": actor["name"],
            "actor_level": actor_level,
            "moves": available_moves,
            "move_names": {move["key"]: move["name"] for move in available_moves},
            "move_damage": {move["key"]: int(move.get("damage", 0)) for move in available_moves},
            "move_meta": {move["key"]: move for move in available_moves},
            "cooldowns": {},
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
        "actor_level": actor_level,
        "player_hp": player_max_hp,
        "moves": available_moves,
        "move_names": {move["key"]: move["name"] for move in available_moves},
        "nemesis_available": nemesis_available,
        "enemy_level": int(enemy.get("level", 1)),
    }


def resolve_action(telegram_id: int, battle_id: str, action: str) -> dict[str, Any] | None:
    battle = get_battle(telegram_id, battle_id)
    if not battle or battle["status"] != "active":
        return None
    if action == "nemesis" and not battle.get("nemesis_available"):
        return None
    if action not in battle.get("move_damage", {}):
        return None
    cooldowns = dict(battle.get("cooldowns", {}))
    if int(cooldowns.get(action, 0)) > 0:
        log = list(battle.get("log", []))
        log.append(f"{battle.get('move_names', {}).get(action, 'Move')} is cooling down → {cooldowns[action]} turn(s)")
        return update_battle(battle_id, log=log[-8:])

    action_damage = int(battle.get("move_damage", {}).get(action, 10))
    enemy_action = "ultimate" if int(battle["turn"]) % 3 == 0 else "signature"
    enemy_base_damage = int(battle.get("enemy_move_damage", {}).get(enemy_action, battle.get("enemy_attack", 12)))
    enemy_damage = random.randint(max(1, enemy_base_damage - 3), enemy_base_damage + 3)
    new_enemy_hp = max(0, int(battle["enemy_hp"]) - action_damage)
    move_meta = battle.get("move_meta", {}).get(action, {})
    is_defense = move_meta.get("category") == "defense"
    new_player_hp = max(0, int(battle["player_hp"]) - (max(1, enemy_damage // 2) if is_defense else enemy_damage))
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
        user_xp = 50 if battle["mode"] == "rift" else 40 if battle["mode"] in {"villain", "event"} else 30
        character_xp = user_xp + 20
        updated_profile = grant_user_xp(telegram_id, user_xp) or {}
        updated_character = grant_character_xp(telegram_id, battle.get("actor_hero_key", ""), character_xp) or {}
        record_ledger(telegram_id, "credits", reward, f"{battle['mode']} battle victory", updates["credits"])
        log.append(f"Reward → +{reward} Cape Credits")
        log.append(
            f"XP → player +{user_xp} (Lv {updated_profile.get('level', 1)}) · "
            f"{battle.get('actor_name', 'hero')} +{character_xp} (Lv {updated_character.get('level', 1)})"
        )
    elif new_player_hp == 0:
        enemy_move = battle.get("enemy_move_names", {}).get(enemy_action, "Enemy attack")
        log.append(f"{enemy_move} countered for {enemy_damage}")
        status = "lost"
        log.append("Defeat → regroup and try again")
    else:
        enemy_move = battle.get("enemy_move_names", {}).get(enemy_action, "Enemy attack")
        log.append(f"{enemy_move} countered for {enemy_damage}")
    for key in list(cooldowns):
        cooldowns[key] = max(0, int(cooldowns[key]) - 1)
    used_cooldown = int(move_meta.get("cooldown", 0))
    if used_cooldown:
        cooldowns[action] = used_cooldown
    return update_battle(
        battle_id,
        enemy_hp=new_enemy_hp,
        player_hp=new_player_hp,
        turn=int(battle["turn"]) + 1,
        status=status,
        log=log[-8:],
        cooldowns=cooldowns,
    )


def simulate_pve() -> dict[str, Any]:
    heroes = list_heroes()
    enemies = list_villains("normal") or list_villains("villain")
    if not heroes:
        return {"ok": False, "reason": "Publish at least one hero before using /test."}
    if not enemies:
        return {"ok": False, "reason": "Publish at least one normal enemy or villain before using /test."}
    hero = heroes[0]
    enemy = enemies[0]
    hero_hp = 100
    enemy_hp = int(enemy.get("hp", 100))
    starting_enemy_hp = enemy_hp
    turns: list[str] = []
    moves = [
        (hero.get("ability_signature", "Signature Move"), int(hero.get("signature_damage", 24))),
        (hero.get("ability_utility", "Utility Move"), int(hero.get("utility_damage", 15))),
        (hero.get("ability_ultimate", "Ultimate"), int(hero.get("ultimate_damage", 38))),
    ]
    for turn in range(1, 11):
        move_name, damage = moves[(turn - 1) % len(moves)]
        enemy_hp = max(0, enemy_hp - damage)
        turns.append(f"{move_name} → {damage} damage · enemy {enemy_hp} HP")
        if enemy_hp == 0:
            break
        use_ultimate = turn % 3 == 0
        incoming = int(enemy.get("ultimate_damage" if use_ultimate else "signature_damage", enemy.get("attack", 12)))
        hero_hp = max(0, hero_hp - incoming)
        enemy_move = enemy.get("ability_ultimate" if use_ultimate else "ability_signature", "Counterattack")
        turns.append(f"{enemy_move} → {incoming} damage · hero {hero_hp} HP")
        if hero_hp == 0:
            break
    return {
        "ok": True,
        "hero": hero["name"],
        "enemy": enemy["name"],
        "hero_hp": 100,
        "enemy_hp": starting_enemy_hp,
        "turns": turns,
        "result": "Hero victory" if enemy_hp == 0 else "Enemy victory" if hero_hp == 0 else "Turn limit reached",
    }