"""Run the fakenodo blueprint as a standalone Flask service.

Usage:
    python -m app.modules.fakenodo.run

This file creates a minimal Flask app, registers only the `fakenodo` blueprint and runs
on the port defined by the environment variable `FAKENODO_PORT` (default 5001).
"""

import os

from flask import Flask

from app.modules.fakenodo import fakenodo_bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(fakenodo_bp)
    return app


def main():
    port = int(os.environ.get("FAKENODO_PORT", "5001"))
    host = os.environ.get("FAKENODO_HOST", "0.0.0.0")
    app = create_app()
    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    main()
