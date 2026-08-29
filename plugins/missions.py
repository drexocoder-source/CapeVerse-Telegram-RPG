from typing import Any

from database.mongo import get_profile, grant_user_xp, record_ledger, update_player


def claim_patrol(telegram_id: int) -> dict[str, Any]:
    profile = get_profile(telegram_id)
    if not profile or profile.get("patrol_intel", 0) < 1:
        return {"ok": False, "reason": "No Patrol Intel remains."}
    update_player(
        telegram_id,
        patrol_intel=profile.get("patrol_intel", 0) - 1,
        credits=profile.get("credits", 0) + 120,
    )
    record_ledger(telegram_id, "credits", 120, "Patrol reward", profile.get("credits", 0) + 120)
    updated = grant_user_xp(telegram_id, 15) or {}
    return {"ok": True, "credits": 120, "xp": 15, "level": updated.get("level", 1)}


def complete_case(telegram_id: int, alignment: str) -> dict[str, Any]:
    profile = get_profile(telegram_id)
    if not profile or profile.get("patrol_intel", 0) < 1:
        return {"ok": False, "reason": "You need 1 Patrol Intel."}
    reward = 90 if alignment == "Hero" else 110
    update_player(
        telegram_id,
        alignment=alignment,
        patrol_intel=int(profile.get("patrol_intel", 0)) - 1,
        credits=int(profile.get("credits", 0)) + reward,
    )
    record_ledger(telegram_id, "credits", reward, f"Case File choice: {alignment}", int(profile.get("credits", 0)) + reward)
    updated = grant_user_xp(telegram_id, 20) or {}
    return {"ok": True, "alignment": alignment, "credits": reward, "xp": 20, "level": updated.get("level", 1)}