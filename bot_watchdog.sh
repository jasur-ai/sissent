#!/bin/bash
# Watchdog for guid_erbot - restarts if dead
BOT_DIR="/home/osboxes/guid_erbot"
BOT_LOG="/tmp/b_watchdog.log"

# Check if bot is running
if ! pgrep -f "python3.*bot.py" | grep -v grep | grep -v watchdog > /dev/null 2>&1; then
    echo "$(date): Bot not running, restarting..." >> "$BOT_LOG"
    cd "$BOT_DIR"
    export BOT_TOKEN="8968630982:AAHDe_lE1fRTYCjzeXxAWlbIUCaAWmo_WD8"
    export ADMIN_IDS="8004724563"
    nohup python3 -u bot.py > /tmp/b_bot.log 2>&1 &
    echo "$(date): Restarted with PID $!" >> "$BOT_LOG"
fi
