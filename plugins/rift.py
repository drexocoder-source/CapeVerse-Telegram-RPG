from plugins.battle import start_battle


def start_rift(telegram_id: int, floor: int):
    return start_battle(telegram_id, "rift", f"The Rift · Floor {floor}")