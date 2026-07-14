#!/bin/bash
set -e

# guid_erbot - Installation Script
# Run with: bash install.sh
# This script will install dependencies and set up the bot

echo "==========================================="
echo "  guid_erbot - Kali Linux Remote Control"
echo "==========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}This script needs to install packages.${NC}"
    echo -e "${YELLOW}Re-running with sudo...${NC}"
    exec sudo bash "$0" "$@"
    exit 1
fi

echo "📦 Installing dependencies..."
apt-get update -qq
apt-get install -y -qq \
    x11vnc \
    imagemagick \
    xdotool \
    libnotify-bin \
    python3-pip \
    2>&1 | tail -3

echo ""
echo "📥 Installing RustDesk..."
if [ -f /tmp/rustdesk.deb ]; then
    dpkg -i /tmp/rustdesk.deb 2>&1 | tail -3 || true
    apt-get install -f -y -qq 2>&1 | tail -3
    echo -e "${GREEN}✅ RustDesk installed!${NC}"
else
    echo -e "${YELLOW}⚠️ Downloading RustDesk...${NC}"
    wget -q https://github.com/rustdesk/rustdesk/releases/download/1.3.8/rustdesk-1.3.8-x86_64.deb -O /tmp/rustdesk.deb
    dpkg -i /tmp/rustdesk.deb 2>&1 | tail -3 || true
    apt-get install -f -y -qq 2>&1 | tail -3
    echo -e "${GREEN}✅ RustDesk installed!${NC}"
fi

echo ""
echo "🐍 Installing python-telegram-bot..."
pip3 install python-telegram-bot --break-system-packages -q 2>&1 | tail -3

echo ""
echo "🔧 Setting up systemd service..."
cat > /etc/systemd/system/guid-erbot.service << 'EOF'
[Unit]
Description=guid_erbot - Telegram Bot for Kali Remote Control
After=network.target graphical-session.target

[Service]
Type=simple
User=osboxes
WorkingDirectory=/home/osboxes/guid_erbot
ExecStart=/usr/bin/python3 /home/osboxes/guid_erbot/bot.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable guid-erbot.service 2>&1 | tail -2

echo ""
echo "==========================================="
echo -e "${GREEN}✅ Installation Complete!${NC}"
echo "==========================================="
echo ""
echo "📋 Next steps:"
echo "  1. Start the bot:  sudo systemctl start guid-erbot"
echo "  2. Check status:   sudo systemctl status guid-erbot"
echo "  3. View logs:      sudo journalctl -u guid-erbot -f"
echo ""
echo "📱 Open Telegram and find @guid_erbot"
echo "   Send /start to see all commands"
echo ""
echo "🖥️ For RustDesk:"
echo "   Set a permanent password in RustDesk GUI"
echo "   Settings → Security → Set password"
echo ""
echo "🔐 For VNC:"
echo "   From Telegram, send: /vnc start"
echo ""
