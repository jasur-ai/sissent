#!/usr/bin/env python3
"""
healthcheck.py - Lightweight Flask server for Render/Uptime Runner
===============================================================
Keeps the bot alive on Render's free tier by providing an HTTP endpoint
that UptimeRobot / Kaffeine can ping every 10-15 minutes.

Run alongside the bot:
    python3 healthcheck.py &

Or deploy as a separate Web Service on Render.
"""

import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
@app.route("/health")
def health():
    """Healthcheck endpoint for Uptime Robot / Kaffeine."""
    return jsonify({
        "status": "ok",
        "service": "guid_erbot",
        "uptime_runner": True
    })

@app.route("/ping")
def ping():
    """Simple ping endpoint."""
    return "pong"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"❤️  Healthcheck server running on port {port}")
    print(f"   → http://localhost:{port}/health")
    print(f"   → Configure UptimeRobot to ping this URL every 10 min")
    app.run(host="0.0.0.0", port=port)
