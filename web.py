import os

from flask import Flask


app = Flask(__name__)


@app.get("/")
def welcome():
    return "CapeVerse\n\nThe signal is live. Open the Telegram bot to begin."


@app.get("/healthz")
def health():
    return "CapeVerse web is online", 200


def run_web() -> None:
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        use_reloader=False,
    )


if __name__ == "__main__":
    run_web()