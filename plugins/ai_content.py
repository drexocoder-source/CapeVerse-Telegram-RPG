"""OpenRouter-assisted, rights-aware CapeVerse character drafting."""

import json
import os
import urllib.error
import urllib.request
from typing import Any


def _extract_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(cleaned[start:end + 1])
                return value if isinstance(value, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _normalise_moves(value: Any, category: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    moves: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        try:
            damage = max(0, min(1000, int(item.get("damage", 10))))
            unlock_level = max(1, min(50, int(item.get("unlock_level", 1))))
            cooldown = max(0, min(10, int(item.get("cooldown", 0))))
        except (TypeError, ValueError):
            continue
        moves.append({
            "name": str(item["name"])[:80],
            "description": str(item.get("description", ""))[:500],
            "damage": damage,
            "unlock_level": unlock_level,
            "cooldown": cooldown,
            "effect": str(item.get("effect", ""))[:200],
            "category": category,
        })
    return moves


def generate_character_blueprint(
    description: str,
    kind: str = "hero",
    move_direction: str = "",
    character_data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not base_url or not api_key or not description.strip():
        return None
    subject = "hero" if kind == "hero" else "villain or enemy"
    system = (
        "You are a game content designer for CapeVerse. Return ONLY valid JSON. "
        "Create original, rights-safe content: do not copy trademarked names, exact "
        "franchise abilities, logos, costumes, or existing characters. The user may "
        "choose a universe label separately, but your move names and descriptions "
        "must remain original. Make every character mechanically distinctive and make "
        "the moves reflect the story, role, personality, weaknesses, location, and requested "
        "combat style. Create three move categories: normal, defense, special. "
        "Each category must contain one or more moves. The count may be 1, 2, 3, or more; "
        "choose the count naturally for the character and do not force every category to have the same size. "
        "Every move needs name, description, "
        "damage, unlock_level, cooldown, and effect. Defense moves may use damage 0. "
        "For CapeVerse-original characters, suggest original evolution concepts. For licensed "
        "characters, suggest research archive topics such as suit generations or documented "
        "forms; never call licensed suit research an evolution and never invent rights."
    )
    context = character_data or {}
    prompt = (
        f"Analyze this {subject} and make interesting, balanced game data.\n\n"
        f"Character data: {json.dumps(context, ensure_ascii=False)}\n"
        f"Story description: {description}\n"
        f"Requested move direction: {move_direction or 'Use the story and role to decide.'}\n\n"
        "JSON keys: role, rarity, alignment, design_summary, moves "
        "(normal/defense/special arrays), evolution_concepts, research_concepts. "
        "Each evolution/research concept needs name, description, unlock_level, and requirement. "
        "For villains also include hp, attack, min_level, max_level. "
        "Keep unlock levels meaningful: first move level 1, later moves level 4, 8, or 12."
    )
    body = json.dumps({
        "model": os.getenv("OPENROUTER_MODEL", "openrouter/free"),
        "max_completion_tokens": 3000,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload["choices"][0]["message"]["content"]
        result = _extract_json(text)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = ""
        print(f"CapeVerse AI HTTP error {exc.code}: {detail}", flush=True)
        return None
    except Exception as exc:
        print(f"CapeVerse AI error {type(exc).__name__}: {exc}", flush=True)
        return None
    if not result:
        return None
    result["moves"] = {
        category: _normalise_moves(result.get("moves", {}).get(category), category)
        for category in ("normal", "defense", "special")
    }
    if not any(result["moves"].values()):
        return None
    for key in ("evolution_concepts", "research_concepts"):
        values = result.get(key, [])
        result[key] = [
            {
                "name": str(item.get("name", ""))[:80],
                "description": str(item.get("description", ""))[:500],
                "unlock_level": max(1, min(50, int(item.get("unlock_level", 10)))),
                "requirement": str(item.get("requirement", ""))[:200],
            }
            for item in values[:4]
            if isinstance(item, dict) and item.get("name")
        ]
    if kind != "hero":
        try:
            result["hp"] = max(20, min(10000, int(result.get("hp", 150))))
            result["attack"] = max(1, min(1000, int(result.get("attack", 20))))
            result["min_level"] = max(1, min(50, int(result.get("min_level", 1))))
            result["max_level"] = max(result["min_level"], min(100, int(result.get("max_level", 100))))
        except (TypeError, ValueError):
            return None
    return result