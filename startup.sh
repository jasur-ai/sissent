#!/bin/bash
# ==============================================================
# guid_erbot - Render.com Startup Script
# ==============================================================
# Launched by render.yaml as the Background Worker start command.
# Dependencies are installed by the buildCommand, so no pip here.
# ==============================================================

set -e

cd "$(dirname "$0")"

# Validate BOT_TOKEN (set via Render env vars)
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ ERROR: BOT_TOKEN not set!"
    echo "   Set it in Render Dashboard → Environment Variables"
    exit 1
fi

echo "✅ BOT_TOKEN configured"
echo "🤖 Starting guid_erbot telegram bot..."
echo "📱 Bot: https://t.me/guid_erbot"
echo "🔐 Admin: $ADMIN_IDS"

# Start the main Telegram bot
# Healthcheck server is started internally by bot.py (on a daemon thread)
echo "❤️  Healthcheck server will run inside bot.py (threaded)"
exec python3 bot.py
