import threading

from app import run_bot
from web import run_web


if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    run_bot()
    web_thread.join()