from typing import Any

from database.mongo import get_profile, record_ledger, update_player


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
    return {"ok": True, "credits": 120}