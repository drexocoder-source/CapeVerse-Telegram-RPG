from plugins.battle import start_battle


def start_arena(telegram_id: int, opponent_telegram_id: int | None = None):
    return start_battle(
        telegram_id,
        "arena",
        "Direct Challenge" if opponent_telegram_id else "Sanctioned Bout",
        opponent_telegram_id=opponent_telegram_id,
    )