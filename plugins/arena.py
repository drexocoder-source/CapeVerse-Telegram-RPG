from plugins.battle import start_battle


def start_arena(telegram_id: int):
    return start_battle(telegram_id, "arena", "Sanctioned Bout")