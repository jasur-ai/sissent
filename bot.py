#!/usr/bin/env python3
"""
guid_erbot - Telegram Bot for Kali Linux Remote Control
=======================================================
Securely control your Kali Linux VM from your phone via Telegram.

Commands:
  /start       - Show welcome message and available commands
  /shell <cmd> - Execute a shell command on the machine
  /screenshot  - Take a screenshot of the desktop
  /sysinfo     - Show system information (CPU, RAM, disk, network)
  /ps          - List running processes
  /upload <path> - Upload a file from the machine to Telegram
  /download    - Download a file (send the file in reply)
  /web <url>   - Open a URL in the machine's browser
  /type <text> - Type text on the machine (using xdotool)
  /key <key>   - Press a keyboard key (Enter, Escape, etc.)
  /cmdhistory  - Show command execution history
  /lock        - Lock the screen
  /notify <msg> - Show a desktop notification
  /wifi        - Show WiFi/network info
  /vnc         - Start/Stop VNC server on the machine
  /rustdesk    - Show RustDesk connection info
  /whoami      - Show your Telegram ID (for setup)
  /reboot      - Reboot the machine (confirmation required)
  /shutdown    - Shutdown the machine (confirmation required)
  /help        - Show detailed help

Author: guid_erbot
"""

import asyncio
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
import json
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

# Import 60+ extra command handlers
from extra_commands import (
    packages_command,
    update_system,
    gpu_temp_handler,
    speed_test,
    open_music,
    open_media,
    open_images,
    open_youtube,
    open_steam,
    podcast_command,
    open_home,
    open_downloads,
    open_documents,
    open_screenshots,
    open_videos,
    backup_command,
    empty_trash,
    share_folder,
    restart_network,
    firewall_status,
    ssh_keys,
    secure_delete,
    port_scan,
    keychain_command,
    python_shell,
    docker_status,
    open_vscode,
    git_status,
    build_project,
    run_tests,
    roll_dice,
    flip_coin,
    fortune_cookie,
    eight_ball,
    matrix_effect,
    cat_facts,
    screen_res,
    brightness_command,
    night_mode,
    theme_command,
    about_command,
    clear_temp,
    power_off,
    calculator_command,
    notes_command,
    calendar_command,
    open_camera,
    EXTRA_CMD_MAP,
    EXTRA_BUTTON_COMMANDS,
)

# Import shared utilities
from utils import (
    ADMIN_IDS,
    OSBOXES_USER,
    OSBOXES_PASS,
    DATA_DIR,
    COMMAND_HISTORY_FILE,
    VNC_PASSWORD_FILE,
    PHONE_NUMBERS_FILE,
    logger,
    is_authorized,
    escape_md,
    reply_long,
    run_shell,
    format_bytes,
    load_command_history,
    save_command_history,
    add_to_history,
    load_phone_numbers,
    save_phone_number,
    get_phone_number,
)


# ============ CONFIGURATION ============

# IMPORTANT: Get your token from environment variable
# Generate token from @BotFather on Telegram
# Usage: export BOT_TOKEN="your_token_here" && python3 bot.py
# Try environment variable, then fallback to .env file, then hardcoded (not recommended)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    # Try loading from .env file
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("BOT_TOKEN="):
                    BOT_TOKEN = line.split("=", 1)[1].strip().strip("\"'").strip()
                    break

if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN not found!")
    print("   Option 1: export BOT_TOKEN='your_token_here' && python3 bot.py")
    print("   Option 2: echo 'BOT_TOKEN=your_token_here' > .env")
    sys.exit(1)

# ============ OSBOXES VM LOGIN CREDENTIALS ============
# Used by /unlock and /login commands
# Values imported from utils.py: ADMIN_IDS, OSBOXES_USER, OSBOXES_PASS

# ============ SETUP ============

# Logging setup imported from utils.py (logger, logging.basicConfig)

# Data directories and file paths imported from utils.py:
#   DATA_DIR, COMMAND_HISTORY_FILE, VNC_PASSWORD_FILE, PHONE_NUMBERS_FILE

# ============ UTILITY FUNCTIONS (imported from utils.py) ============



# ============ PHONE NUMBER STORAGE (imported from utils.py) ============









# ============ REPLY KEYBOARD (Buttons Below Chat) ============

def build_reply_keyboard():
    """Expanded 90+ button keyboard organized by sorted categories."""
    keyboard = [
        # 🚀 Power Tools
        ["💻 Open Terminal", "🌍 Open Firefox", "📸 Screenshot"],
        ["🎬 Record Screen", "⏹️ Stop Record", "🔪 Kill Top CPU"],
        ["🧹 Clear Cache", "🔐 VPN Toggle", "🧦 SOCKS5"],

        # 💻 System
        ["💻 Shell Command", "⚙️ Services", "🪟 Open Apps"],
        ["🌡️ CPU Temp", "📋 Clipboard", "📦 Packages"],
        ["🧑‍💻 Who's Online", "🔧 Fix Network", "🔄 Update System"],

        # 📊 Monitoring
        ["📋 Processes", "📊 System Info", "🌡️ GPU Info"],
        ["🌐 LAN IP", "📡 WiFi", "📡 Speed Test"],
        ["👤 Whoami", "⏱️ Uptime", "📜 History"],

        # 🖥️ Desktop
        ["🔒 Lock", "🔓 Unlock", "🔑 GPG Keys"],
        ["🔔 Notify", "⌨️ Type Text", "🔘 Press Key"],

        # 📊 Dashboard
        ["📊 Dashboard"],

        # 🔊 Sound & Media
        ["🔊 Vol Up", "🔊 Vol Down", "🔇 Mute"],
        ["🎵 Music", "🎬 Media", "🖼️ Images"],
        ["📺 YouTube", "🎮 Steam", "🎧 Podcasts"],

        # 🖱️ Mouse
        ["🖱️ Mouse", "🖱️ Left Click", "🖱️ Right Click"],
        ["📜 Scroll Up", "📜 Scroll Down", "📍 Mouse Pos"],

        # 📁 Files
        ["📁 Home", "📂 Downloads", "📄 Documents"],
        ["🖼️ Screenshots", "🎬 Videos", "📤 Upload"],
        ["📥 Download", "💾 Backup", "🗑️ Empty Trash"],

        # 🌐 Remote & Network
        ["🌐 Web VNC", "🖥️ VNC Start", "🖥️ VNC Status"],
        ["🖥️ VNC Stop", "🔄 RustDesk", "🌍 Open URL"],
        ["🖧 Share Folder", "🔄 Restart Network", "📡 Speed Test"],

        # 🛡️ Security
        ["🛡️ Firewall", "🔐 SSH Keys", "🔐 Login Info"],
        ["🧹 Secure Delete", "🔍 Port Scan", "🔑 Keychain"],

        # 🛠️ Developer
        ["🐍 Python", "🐳 Docker", "📝 VS Code"],
        ["🐙 Git Status", "🛠️ Build", "🧪 Run Tests"],
        ["🧮 Calculator", "📝 Notes", "📅 Calendar"],

        # 🎮 Fun
        ["🎲 Roll Dice", "🪙 Flip Coin", "🔮 Fortune"],
        ["🎱 8-Ball", "👾 Matrix", "🐱 Cat Facts"],

        # ⚡ Control
        ["⏹️ Shutdown", "📖 Help", "🔄 Reboot"],
        ["🌐 Web Panel", "📞 Share Phone", "🔍 About"],
        ["🔌 Power Off", "💻 Lock Now", "🧹 Clear Temp"],

        # ⚙️ Display
        ["🖥️ Screen Res", "💡 Brightness", "🌙 Night Mode"],
        ["🎨 Theme", "📷 Camera", "📞 Share Phone"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Map button text to command handler
BUTTON_COMMANDS = {
    "💻 Open Terminal": "term",
    "🌍 Open Firefox": "firefox",
    "📸 Screenshot": "screenshot",
    "🎬 Record Screen": "record",
    "⏹️ Stop Record": "stop_record",
    "🔪 Kill Top CPU": "killcpu",
    "🧹 Clear Cache": "clearcache",
    "🔐 VPN Toggle": "vpn",
    "🧦 SOCKS5": "socks5",
    "🌡️ CPU Temp": "temp",
    "🔑 GPG Keys": "gpg",
    "🔒 Lock": "lock",
    "🔓 Unlock": "unlock",
    "🔊 Vol Up": "sound up",
    "🔊 Vol Down": "sound down",
    "🔇 Mute": "sound mute",
    "🌐 Web VNC": "webvnc",
    "🖥️ VNC Status": "vnc",
    "📊 System Info": "sysinfo",
    "🧠 Memory": "memory",
    "📖 Help": "help",
    "🔄 Reboot": "reboot",
    # === Backward compat: old button labels ===
    "📋 Processes": "ps",
    "📊 Sysinfo": "sysinfo",
    "👤 Whoami": "whoami",
    "📜 Down": "scroll down",
    "📜 Up": "scroll up",
    "🖱️ Right": "click right",
    "🖱️ Left": "click left",
    "🔄 RustDesk": "rustdesk",
    "📱 Share #": "phone",
    "🔔 Notify": "notify",
    "💻 Shell": "shell",
    "💾 Disk": "disk",
    "🌐 IP": "ip",
    "📡 WiFi": "wifi",
    "⏹️ Shutdown": "shutdown",
    "📜 History": "cmdhistory",
    "⏱️ Uptime": "uptime",
    "📱 Share Phone": "phone",
    "📞 Share Phone": "phone",
    "🖱️ Mouse": "mouse",
    "🌐 Web Panel": "webpanel",
    "📊 Dashboard": "dashboard",
    # ===== EXTRA COMMANDS (60+) =====
    # 💻 System
    "💻 Shell Command": "shell",
    "⚙️ Services": "services",
    "🪟 Open Apps": "apps",
    "🌡️ CPU Temp": "temp",
    "📋 Clipboard": "clipboard",
    "📦 Packages": "packages",
    "🧑‍💻 Who's Online": "whoson",
    "🔧 Fix Network": "fixnet",
    "🔄 Update System": "updatesys",
    # 📊 Monitoring
    "🌡️ GPU Info": "gputemp",
    "🌐 LAN IP": "ip",
    "📡 Speed Test": "speedtest",
    # 🖥️ Desktop
    "⌨️ Type Text": "type",
    "🔘 Press Key": "key",
    "🔐 Login Info": "login",
    # 🔊 Sound & Media
    "🎵 Music": "music",
    "🎬 Media": "media",
    "🖼️ Images": "images",
    "📺 YouTube": "youtube",
    "🎮 Steam": "steam",
    "🎧 Podcasts": "podcast",
    # 🖱️ Mouse
    "🖱️ Left Click": "click left",
    "🖱️ Right Click": "click right",
    "📜 Scroll Up": "scroll up",
    "📜 Scroll Down": "scroll down",
    "📍 Mouse Pos": "mpos",
    # 📁 Files
    "📁 Home": "home",
    "📂 Downloads": "downloads",
    "📄 Documents": "docs",
    "🖼️ Screenshots": "screenshots",
    "🎬 Videos": "videos",
    "📤 Upload": "upload",
    "📥 Download": "download_prompt",
    "💾 Backup": "backup",
    "🗑️ Empty Trash": "emptytrash",
    # 🌐 Remote
    "🖥️ VNC Start": "vnc start",
    "🖥️ VNC Stop": "vnc stop",
    "🌍 Open URL": "web",
    "🖧 Share Folder": "share",
    "🔄 Restart Network": "restartnet",
    # 🛡️ Security
    "🛡️ Firewall": "firewall",
    "🔐 SSH Keys": "sshkeys",
    "🧹 Secure Delete": "shred",
    "🔍 Port Scan": "portscan",
    "🔑 Keychain": "keychain",
    # 🛠️ Developer
    "🐍 Python": "python",
    "🐳 Docker": "docker",
    "📝 VS Code": "vscode",
    "🐙 Git Status": "git",
    "🛠️ Build": "build",
    "🧪 Run Tests": "tests",
    "🧮 Calculator": "calc",
    "📝 Notes": "notes",
    "📅 Calendar": "calendar",
    # 🎮 Fun
    "🎲 Roll Dice": "dice",
    "🪙 Flip Coin": "coin",
    "🔮 Fortune": "fortune",
    "🎱 8-Ball": "8ball",
    "👾 Matrix": "matrix",
    "🐱 Cat Facts": "catfacts",
    # ⚡ Control
    "🔍 About": "about",
    "🔌 Power Off": "poweroff",
    "💻 Lock Now": "lock",
    "🧹 Clear Temp": "cleartemp",
    # ⚙️ Display
    "🖥️ Screen Res": "screenres",
    "💡 Brightness": "brightness",
    "🌙 Night Mode": "nightmode",
    "🎨 Theme": "theme",
    "📷 Camera": "camera",
}

# ============ COMMAND HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with buttons when /start is issued."""
    user_id = update.effective_user.id
    # Check if this is a callback query (menu refresh) or new /start command
    is_callback = update.callback_query is not None
    welcome = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 *guid_erbot* · Remote Control\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *Operator:* `{user_id}`  │  📡 *Status:* `Online`\n"
        f"🖥️ *System:* `{platform.node()}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 Use the buttons below or tap *📖 Category Menu* to browse.\n"
        f"💡 Tip: You can also type commands like `/shell whoami` or `/screenshot`"
    )
    # Build the persistent reply keyboard (below chat)
    reply_kb = build_reply_keyboard()
    # Also keep inline menu for browsing
    inline_kb = [
        [InlineKeyboardButton("📖 Category Menu", callback_data="menu_main")],
    ]
    if is_callback:
        await update.callback_query.edit_message_text(
            welcome, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_kb)
        )
    else:
        await update.effective_message.reply_text(
            welcome, parse_mode="Markdown",
            reply_markup=reply_kb  # Show the persistent keyboard below chat!
        )

# ============ BUTTON TEXT HANDLER ============

async def button_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle taps on the reply keyboard buttons (below chat)."""
    if not is_authorized(update.effective_user.id):
        return
    text = update.message.text
    if text not in BUTTON_COMMANDS:
        return  # Not a button tap, ignore
    cmd = BUTTON_COMMANDS[text]
    # Handle special prompt commands (need user to type something)
    if cmd == "shell_prompt":
        await update.effective_message.reply_text(
            "💻 *Run a Shell Command*\n\n"
            "Type: `/shell <command>`\n"
            "Example: `/shell whoami`",
            parse_mode="Markdown"
        )
        return
    if cmd == "notify_prompt":
        await update.effective_message.reply_text(
            "🔔 *Send a Notification*\n\n"
            "Type: `/notify <message>`\n"
            "Example: `/notify Hello from phone!`",
            parse_mode="Markdown"
        )
        return
    if cmd == "download_prompt":
        await update.effective_message.reply_text(
            "📥 *Download a File to the VM*\n\n"
            "Just send me a file or photo in this chat\n"
            "and I'll save it to the VM!\n\n"
            "📁 Saved to: `/home/osboxes/Downloads/guid_erbot/`\n\n"
            "💡 You can also reply to a message with `/upload <path>`\n"
            "to send files FROM the VM TO Telegram.",
            parse_mode="Markdown"
        )
        return
    # Map command name to handler function
    cmd_map = {
        "term": open_terminal,
        "firefox": open_firefox,
        "screenshot": screenshot_command,
        "record": record_screen,
        "stop_record": stop_record,
        "killcpu": kill_top_cpu,
        "clearcache": clear_cache,
        "fixnet": fix_network,
        "temp": cpu_temp_handler,
        "clipboard": clipboard_handler,
        "whoson": whos_online,
        "lock": lock_command,
        "unlock": unlock_command,
        "sysinfo": sysinfo_command,
        "memory": memory_command,
        "disk": disk_command,
        "ip": ip_command,
        "wifi": wifi_command,
        "webvnc": webvnc_command,
        "vnc": vnc_command,
        "rustdesk": rustdesk_command,
        "phone": phone_command,
        "help": help_command,
        "reboot": reboot_command,
        "shutdown": shutdown_command,
        "uptime": uptime_command,
        "sound": sound_command,
        "click": click_command,
        "scroll": scroll_command,
        "vpn": vpn_command,
        "socks5": socks5_command,
        "gpg": gpg_command,
        "ps": ps_command,
        "whoami": whoami_command,
        "notify": notify_command,
        "shell": shell_command,
        "cmdhistory": cmdhistory_command,
        "webpanel": webpanel_command,
        "dashboard": dashboard_command,
        # ===== EXTRA COMMANDS (60+) =====
        "packages": packages_command,
        "updatesys": update_system,
        "gputemp": gpu_temp_handler,
        "speedtest": speed_test,
        "music": open_music,
        "media": open_media,
        "images": open_images,
        "youtube": open_youtube,
        "steam": open_steam,
        "podcast": podcast_command,
        "home": open_home,
        "downloads": open_downloads,
        "docs": open_documents,
        "screenshots": open_screenshots,
        "videos": open_videos,
        "backup": backup_command,
        "emptytrash": empty_trash,
        "share": share_folder,
        "restartnet": restart_network,
        "firewall": firewall_status,
        "sshkeys": ssh_keys,
        "shred": secure_delete,
        "portscan": port_scan,
        "keychain": keychain_command,
        "python": python_shell,
        "docker": docker_status,
        "vscode": open_vscode,
        "git": git_status,
        "build": build_project,
        "tests": run_tests,
        "dice": roll_dice,
        "coin": flip_coin,
        "fortune": fortune_cookie,
        "8ball": eight_ball,
        "matrix": matrix_effect,
        "catfacts": cat_facts,
        "screenres": screen_res,
        "brightness": brightness_command,
        "nightmode": night_mode,
        "theme": theme_command,
        "about": about_command,
        "services": services_command,
        "apps": apps_command,
        "type": type_command,
        "key": key_command,
        "login": login_command,
        "web": web_command,
        "mpos": mouse_command,
        "cleartemp": clear_temp,
        "poweroff": power_off,
        "calc": calculator_command,
        "notes": notes_command,
        "calendar": calendar_command,
        "camera": open_camera,
        "mpos": mouse_command,
        "upload": upload_command,
    }
    handler = cmd_map.get(cmd)
    if handler:
        # Set context.args if needed (for commands like "sound up", "click left")
        parts = cmd.split()
        if len(parts) > 1:
            context.args = parts[1:]
        else:
            context.args = []
        await handler(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send detailed help when /help is issued."""
    user_id = update.effective_user.id
    # Check if this was triggered from a callback or direct command
    is_callback = update.callback_query is not None
    help_text = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📖 *guid_erbot · Command Reference*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 `{user_id}` │ 📡 Online\n\n"
        "▸ *Quick Start*\n"
        "  Tap the *📖 Category Menu* button or just press any button below.\n\n"
        "▸ *Direct Commands*\n"
        "  `/shell <cmd>` — Execute any command\n"
        "  `/screenshot` — Capture desktop\n"
        "  `/sysinfo` — System overview\n"
        "  `/lock` / `/unlock` — Lock/unlock screen\n"
        "  `/webvnc` — Desktop in browser\n"
        "  `/upload <path>` — Send file from VM\n"
        "  `/sound get` — Volume status\n"
        "  `/speedtest` — Network speed test\n"
        "  `/docker` — Docker containers status\n"
        "  `/packages` — Package manager counts\n"
        "  `/git` — Git repositories status\n"
        "  `/notes` — Quick notes manager\n"
        "  `/calc <expr>` — Inline calculator\n"
        "  `/calendar` — Show calendar\n"
        "  `/backup` — Create config backup\n"
        "  `/emptytrash` — Empty trash folder\n"
        "  `/about` — Bot information\n"
        "  `/cleartemp` — Clear temp files\n"
        "  `/music` — Open music player\n"
        "  `/media` — Open media player\n"
        "  `/youtube` — Open YouTube\n"
        "  `/steam` — Open Steam\n"
        "  `/dice` — Roll a dice\n"
        "  `/coin` — Flip a coin\n"
        "  `/fortune` — Fortune cookie\n"
        "  `/help` — Show this message\n\n"
        "💡 Buttons cover everything — no need to remember commands!"
    )
    kb = [
        [InlineKeyboardButton("« Back to Menu", callback_data="menu_main")],
    ]
    reply_markup = InlineKeyboardMarkup(kb)
    if is_callback:
        await update.callback_query.edit_message_text(help_text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.effective_message.reply_text(help_text, parse_mode="Markdown", reply_markup=reply_markup)

async def shell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute a shell command."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized. You are not allowed to control this machine.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "Usage: `/shell <command>`\n"
            "Example: `/shell whoami`",
            parse_mode="Markdown"
        )
        return

    command = " ".join(context.args)
    status_msg = await update.effective_message.reply_text(f"⚡ Executing: `{command[:50]}`...", parse_mode="Markdown")

    try:
        output = await run_shell(command, timeout=60)
        add_to_history(command, output[:200])

        if len(output) > 3900:
            output = output[:3900] + "\n\n...(truncated)"

        await status_msg.edit_text(
            f"✅ *Command:* `{escape_md(command[:100])}`\n\n```\n{output[:3900]}```",
            parse_mode="Markdown"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")

async def screenshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Take a screenshot of the desktop."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    status_msg = await update.effective_message.reply_text("📸 Taking screenshot...")

    screenshot_path = "/tmp/guid_screenshot.png"

    # Try multiple methods
    methods = [
        ["import", "-window", "root", screenshot_path],
        ["scrot", screenshot_path],
        ["gnome-screenshot", "-f", screenshot_path],
    ]

    success = False
    for cmd in methods:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, timeout=10, capture_output=True)
                if Path(screenshot_path).exists() and Path(screenshot_path).stat().st_size > 1000:
                    success = True
                    break
            except (subprocess.TimeoutExpired, OSError):
                continue

    if success:
        await status_msg.delete()
        with open(screenshot_path, "rb") as f:
            await update.effective_message.reply_photo(
                photo=f,
                caption=f"📸 Screenshot taken at {datetime.now().strftime('%H:%M:%S')}",
            )
        os.remove(screenshot_path)
    else:
        await status_msg.edit_text(
            "❌ Failed to take screenshot.\n"
            "Make sure a desktop environment is running and you have "
            "`import` (imagemagick) or `scrot` installed."
        )

async def sysinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system information."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    status_msg = await update.effective_message.reply_text("🔍 Gathering system info...")

    try:
        # CPU info
        cpu_info = await run_shell("lscpu | grep 'Model name\\|CPU(s):' | head -2")
        cpu_usage = await run_shell("top -bn1 | grep 'Cpu(s)' | awk '{print $2 \"%\"}'")
        cpu_temp = ""
        if Path("/sys/class/thermal/thermal_zone0/temp").exists():
            try:
                temp_raw = int(open("/sys/class/thermal/thermal_zone0/temp").read().strip())
                cpu_temp = f"\n🔥 CPU Temp: {temp_raw / 1000:.1f}°C"
            except (ValueError, OSError):
                pass

        # Memory info
        mem_info = await run_shell("free -h | grep -E '^Mem:|^Swap:'")

        # Disk info
        disk_info = await run_shell("df -h / /home 2>/dev/null | grep -v 'Filesystem'")

        # Network info
        ip_info = await run_shell("hostname -I 2>/dev/null | awk '{print $1}'")
        wan_ip = await run_shell("curl -s ifconfig.me 2>/dev/null || echo 'Unavailable'")
        net_info = await run_shell("ip -4 addr show | grep inet | grep -v 127.0.0.1 | awk '{print $2, $NF}'")

        # Uptime
        uptime = await run_shell("uptime -p 2>/dev/null || uptime")

        # OS info
        os_info = await run_shell("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'")
        kernel = await run_shell("uname -r")

        # GPU
        gpu_info = await run_shell("lspci | grep -i 'vga\\|3d' | head -1 | cut -d: -f3-")
        if not gpu_info:
            gpu_info = "N/A"

        info_text = (
            f"🖥️ *System Information*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"*OS:* {os_info.strip()}\n"
            f"*Kernel:* {kernel.strip()}\n"
            f"*Hostname:* {platform.node()}\n"
            f"*Uptime:* {uptime.strip()}\n\n"
            f"*CPU:* {cpu_info.strip()}\n"
            f"*Usage:* {cpu_usage.strip()}{cpu_temp}\n"
            f"*GPU:* {gpu_info.strip()}\n\n"
            f"*Memory:*\n{escape_md(mem_info.strip())}\n\n"
            f"*Disk:*\n{escape_md(disk_info.strip())}\n\n"
            f"*Network:*\n{escape_md(net_info.strip())}\n"
            f"*IP:* {ip_info.strip()}\n"
            f"*WAN:* {wan_ip.strip()}\n\n"
            f"📍 _Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
        )

        await status_msg.delete()
        await update.effective_message.reply_text(info_text, parse_mode="Markdown")

    except Exception as e:
        await status_msg.edit_text(f"❌ Error gathering system info: {e}")

async def ps_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show running processes."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    output = await run_shell("ps aux --sort=-%mem | head -35")
    total = await run_shell("ps aux | wc -l")
    text = f"📊 *Running Processes* (Total: {total.strip()})\n"
    text += f"━━━━━━━━━━━━━━━━━━\n```\n{output[:3900]}```"
    await update.effective_message.reply_text(text[:4000], parse_mode="Markdown")

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upload a file from the machine."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: `/upload <path>`\nExample: `/upload /etc/passwd`", parse_mode="Markdown")
        return

    filepath = " ".join(context.args)
    path = Path(filepath).expanduser().resolve()

    if not path.exists():
        await update.effective_message.reply_text(f"❌ File not found: `{escape_md(filepath)}`", parse_mode="Markdown")
        return

    if path.is_dir():
        # Zip directory first
        zip_path = f"/tmp/guid_upload_{int(time.time())}.zip"
        try:
            subprocess.run(["zip", "-r", zip_path, str(path)], timeout=30, capture_output=True)
            with open(zip_path, "rb") as f:
                await update.effective_message.reply_document(
                    document=f,
                    filename=f"{path.name}.zip",
                    caption=f"📁 Directory: `{escape_md(filepath)}`",
                    parse_mode="Markdown",
                )
            os.remove(zip_path)
        except Exception as e:
            await update.effective_message.reply_text(f"❌ Failed to zip: {e}")
        return

    # File size check
    size = path.stat().st_size
    if size > 50 * 1024 * 1024:  # 50MB limit
        await update.effective_message.reply_text(f"❌ File too large ({format_bytes(size)}). Max 50MB.")
        return

    try:
        with open(path, "rb") as f:
            await update.effective_message.reply_document(
                document=f,
                filename=path.name,
                caption=f"📄 `{escape_md(filepath)}` ({format_bytes(size)})",
                parse_mode="Markdown",
            )
    except Exception as e:
        await update.effective_message.reply_text(f"❌ Upload failed: {e}")

async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle downloaded files from Telegram."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    if not update.message.document and not update.message.photo:
        return

    # Restrict downloads to home directory for safety
    save_dir = Path("/home/osboxes/Downloads/guid_erbot")
    save_dir.mkdir(parents=True, exist_ok=True)

    await update.effective_message.reply_text("📥 Downloading file...")

    doc = update.message.document
    if doc:
        file = await context.bot.get_file(doc.file_id)
        file_size = format_bytes(doc.file_size) if doc.file_size else "Unknown"
        save_path = save_dir / doc.file_name
        await file.download_to_drive(save_path)
        await update.effective_message.reply_text(
            f"✅ Downloaded `{escape_md(doc.file_name)}` ({file_size})\n"
            f"📁 Saved to: `{save_path}`",
            parse_mode="Markdown"
        )
    elif update.message.photo:
        # Get the largest photo
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        save_path = save_dir / f"photo_{int(time.time())}.jpg"
        await file.download_to_drive(save_path)
        await update.effective_message.reply_text(
            f"✅ Photo saved to `{save_path}`",
            parse_mode="Markdown"
        )

async def web_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open a URL in the machine's browser."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: `/web <url>`\nExample: `/web https://google.com`", parse_mode="Markdown")
        return

    url = " ".join(context.args)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    browsers = ["xdg-open", "firefox", "chromium", "google-chrome", "sensible-browser"]
    success = False
    for browser in browsers:
        browser_path = shutil.which(browser)
        if browser_path:
            try:
                subprocess.Popen([browser_path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                success = True
                break
            except OSError:
                continue

    if success:
        await update.effective_message.reply_text(f"🌐 Opened `{escape_md(url)}` in browser", parse_mode="Markdown")
    else:
        await update.effective_message.reply_text("❌ No browser found. Install firefox or chromium.")

async def type_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Type text on the machine using xdotool."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: `/type <text>`\nExample: `/type Hello World`", parse_mode="Markdown")
        return

    text = " ".join(context.args)
    try:
        subprocess.run(
            ["xdotool", "type", "--delay", "50", text],
            timeout=10,
            capture_output=True,
            env={"DISPLAY": ":0"},
        )
        await update.effective_message.reply_text(f"⌨️ Typed: `{escape_md(text[:50])}`", parse_mode="Markdown")
    except FileNotFoundError:
        await update.effective_message.reply_text("❌ xdotool not installed. Install with: `sudo apt install xdotool`")
    except Exception as e:
        await update.effective_message.reply_text(f"❌ Failed to type: {e}")

async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Press a keyboard key using xdotool."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "Usage: `/key <key>`\n"
            "Example: `/key Enter`\n"
            "Keys: Enter, Tab, Escape, BackSpace, Delete, Return, "
            "Up, Down, Left, Right, F1-F12, Ctrl+c, Alt+Tab, etc.",
            parse_mode="Markdown"
        )
        return

    key = " ".join(context.args)
    try:
        subprocess.run(["xdotool", "key", key], timeout=5, capture_output=True, env={"DISPLAY": ":0"})
        await update.effective_message.reply_text(f"🔘 Pressed key: `{escape_md(key)}`", parse_mode="Markdown")
    except FileNotFoundError:
        await update.effective_message.reply_text("❌ xdotool not installed.")
    except Exception as e:
        await update.effective_message.reply_text(f"❌ Failed to press key: {e}")

async def cmdhistory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show command execution history."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    history = load_command_history()
    if not history:
        await update.effective_message.reply_text("📜 No command history yet.")
        return

    lines = []
    for i, entry in enumerate(reversed(history[-20:]), 1):
        lines.append(
            f"{i}. [{entry['time'][:19]}] `{escape_md(entry['command'])}`\n"
            f"   ↳ {escape_md(entry['output_preview'])}"
        )

    text = "📜 *Command History*\n━━━━━━━━━━━━━\n\n" + "\n\n".join(lines)
    await reply_long(update, text, parse_mode="Markdown")

async def lock_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show screen lock status (locked/unlocked) with lock/unlock buttons."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    is_callback = update.callback_query is not None

    # Check lock state
    locked = await run_shell("pgrep -x i3lock 2>/dev/null || pgrep -x xfce4-screensaver 2>/dev/null || echo 'unlocked'")
    is_locked = "unlocked" not in locked.lower()

    if is_locked:
        status_text = "🔒 *LOCKED*"
        status_emoji = "🔒"
        detail = "Screen is currently locked with i3lock."
    else:
        status_text = "🔓 *UNLOCKED*"
        status_emoji = "🔓"
        detail = "Screen is accessible — no lock active."

    text = (
        f"🔐 *Screen Lock Status*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{status_text}\n"
        f"{detail}\n"
    )

    # Check if xdotool is available for unlock
    if not shutil.which("i3lock"):
        text += "\n⚠️ i3lock not installed. Run: `sudo apt install i3lock`"

    if is_locked:
        kb = [
            [InlineKeyboardButton("🔓 Unlock Now", callback_data="cmd_unlock")],
        ]
    else:
        kb = [
            [InlineKeyboardButton("🔒 Lock Screen", callback_data="cmd_lock")],
        ]
    kb.append([InlineKeyboardButton("🔄 Refresh", callback_data="cmd_lock_status")])
    kb.append([InlineKeyboardButton("« Back to Desktop", callback_data="menu_desktop")])

    reply_markup = InlineKeyboardMarkup(kb)
    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def lock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lock the screen using i3lock (proper full-screen lock)."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    if not shutil.which("i3lock"):
        # Fallback: try xfce4-screensaver
        if shutil.which("xfce4-screensaver-command"):
            await run_shell("xfce4-screensaver-command -l 2>/dev/null")
            await update.effective_message.reply_text("🔒 Lock attempted (xfce4-screensaver). It may not show properly.")
            return
        await update.effective_message.reply_text("❌ No lock screen tool found. Run: `sudo apt install i3lock`", parse_mode="Markdown")
        return

    status_msg = await update.effective_message.reply_text("🔒 Locking screen...")

    try:
        # Kill xfce4-screensaver first (it conflicts with i3lock)
        await run_shell("pkill -9 xfce4-screensaver 2>/dev/null; sleep 0.5; echo 'killed'")

        # Run i3lock in background - it shows a black screen
        # Type password + Enter to unlock (i3lock uses PAM auth)
        subprocess.Popen(
            ["i3lock", "-c", "1a1a2e", "--nofork"],  # Dark purple-blue color
            env={"DISPLAY": ":0", "HOME": os.environ.get("HOME", "/home/osboxes")},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Note: env only sets DISPLAY+HOME for i3lock to work even without X session env.
        # i3lock only needs DISPLAY to know which screen to lock.

        await asyncio.sleep(1)

        # Check if i3lock is running
        locked = await run_shell("pgrep -x i3lock 2>/dev/null || echo 'not running'")

        if "not running" in locked:
            await status_msg.edit_text(
                "❌ i3lock failed to start. Trying fallback...\n"
                "Try manually: `i3lock -c 000000`",
                parse_mode="Markdown"
            )
            # Fallback: dm-tool
            await run_shell("dm-tool lock 2>/dev/null")
            return

        await status_msg.edit_text(
            "🔒 *Screen Locked!* 🔒\n"
            "━━━━━━━━━━━━━━━━\n"
            "Screen is now locked with i3lock.\n\n"
            "🔓 *To unlock:*\n"
            "Tap the *🔓 Unlock* button below and I'll\n"
            "type the password and press Enter for you!\n\n"
            "💡 The screen shows a dark background now.\n"
            "Typing + Enter = unlocks automatically via i3lock.",
            parse_mode="Markdown"
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ Failed to lock: {e}")

async def notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show a desktop notification on the machine."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: `/notify <message>`\nExample: `/notify Hello from phone!`", parse_mode="Markdown")
        return

    msg = " ".join(context.args)
    try:
        subprocess.run(
            ["notify-send", "📱 Telegram", msg, "-i", "telegram", "-t", "5000"],
            timeout=5,
            capture_output=True,
        )
        await update.effective_message.reply_text(f"🔔 Notification shown: `{escape_md(msg[:50])}`", parse_mode="Markdown")
    except FileNotFoundError:
        # Try alternative methods
        await run_shell(f'echo "NOTIFY: {msg}" | wall 2>/dev/null')
        await update.effective_message.reply_text(f"🔔 Sent notification (fallback): `{escape_md(msg[:50])}`", parse_mode="Markdown")

async def wifi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show network information."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    interfaces = await run_shell("ip -br addr show | grep -v lo")
    wifi_info = await run_shell("iwconfig 2>/dev/null | grep -E 'ESSID|Signal|Mode' || echo 'No WiFi info'")
    connections = await run_shell("ss -tunap | head -30")
    dns = await run_shell("cat /etc/resolv.conf 2>/dev/null | grep nameserver")
    routing = await run_shell("ip route | head -5")
    wan = await run_shell("curl -s ifconfig.me 2>/dev/null || echo 'Unavailable'")

    text = (
        "🌐 *Network Information*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"*Interfaces:*\n```\n{interfaces.strip()}```\n\n"
        f"*WiFi:*\n```\n{wifi_info.strip()}```\n\n"
        f"*Routing:*\n```\n{routing.strip()}```\n\n"
        f"*DNS:*\n```\n{dns.strip()}```\n\n"
        f"*Public IP:* `{wan.strip()}`\n\n"
        f"*Active Connections (top 20):*\n```\n{connections.strip()}```"
    )
    await reply_long(update, text, parse_mode="Markdown")

async def vnc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Control VNC server."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    action = context.args[0].lower() if context.args else "status"

    if action == "start":
        await update.effective_message.reply_text("🔄 Starting VNC server...")
        # Check if x11vnc is installed
        if not shutil.which("x11vnc"):
            await update.effective_message.reply_text(
                "❌ x11vnc not installed.\n"
                "Install: `sudo apt install x11vnc`",
                parse_mode="Markdown"
            )
            return

        # Generate a random password if not exists
        if not VNC_PASSWORD_FILE.exists():
            passwd = subprocess.run(
                ["openssl", "rand", "-hex", "4"],
                capture_output=True, text=True
            ).stdout.strip()
            VNC_PASSWORD_FILE.write_text(passwd)
        else:
            passwd = VNC_PASSWORD_FILE.read_text().strip()

        output = await run_shell(
            f"x11vnc -display :0 -forever -shared -rfbauth ~/.vnc/passwd "
            f"-rfbport 5900 -auth guess -o /tmp/x11vnc.log 2>/dev/null & "
            f"echo 'VNC server started on port 5900'"
        )
        await update.effective_message.reply_text(
            f"✅ VNC server started!\n"
            f"📡 Port: 5900\n"
            f"🔐 Password: `{passwd}`\n"
            f"📱 Use a VNC client app (RealVNC, bVNC) to connect.\n\n"
            f"*Note:* You may need to forward port 5900 or use a VPN.",
            parse_mode="Markdown"
        )

    elif action == "stop":
        await run_shell("pkill x11vnc 2>/dev/null; echo 'VNC stopped'")
        await update.effective_message.reply_text("⏹️ VNC server stopped.")

    elif action == "status":
        running = await run_shell("pgrep -a x11vnc 2>/dev/null || echo 'Not running'")
        port_check = await run_shell("ss -tlnp | grep 5900 || echo 'Port 5900 not listening'")
        if "x11vnc" in running:
            await update.effective_message.reply_text(
                f"✅ *VNC Status:* Running\n```\n{escape_md(running)}```\n```\n{escape_md(port_check)}```",
                parse_mode="Markdown"
            )
        else:
            await update.effective_message.reply_text("❌ VNC server is not running. Use `/vnc start` to start.", parse_mode="Markdown")

    elif action == "password":
        new_pass = " ".join(context.args[1:])
        if new_pass:
            VNC_PASSWORD_FILE.write_text(new_pass)
            await update.effective_message.reply_text(f"🔐 VNC password changed to: `{new_pass}`", parse_mode="Markdown")
        else:
            current = VNC_PASSWORD_FILE.read_text().strip() if VNC_PASSWORD_FILE.exists() else "Not set"
            await update.effective_message.reply_text(f"🔐 Current VNC password: `{current}`", parse_mode="Markdown")

    else:
        await update.effective_message.reply_text(
            "Usage: `/vnc <action>`\n"
            "Actions: `start`, `stop`, `status`, `password <new>`",
            parse_mode="Markdown"
        )

async def webvnc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start/stop web VNC for browser-based remote desktop via noVNC."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    # Handle stop action
    if context.args and context.args[0].lower() == "stop":
        await run_shell("pkill x11vnc 2>/dev/null; pkill websockify 2>/dev/null")
        await update.effective_message.reply_text("⏹️ Web VNC stopped (x11vnc + noVNC).")
        return

    status_msg = await update.effective_message.reply_text("🔄 Starting web VNC...")

    # Check x11vnc is installed
    if not shutil.which("x11vnc"):
        await status_msg.edit_text("❌ x11vnc not installed. Run: `sudo apt install x11vnc`", parse_mode="Markdown")
        return

    # Check noVNC files exist
    novnc_dir = Path("/usr/share/novnc")
    if not novnc_dir.exists():
        await status_msg.edit_text("❌ noVNC not installed. Run: `sudo apt install novnc`", parse_mode="Markdown")
        return

    try:
        # Kill any existing instances
        await run_shell("pkill x11vnc 2>/dev/null; pkill websockify 2>/dev/null")
        await asyncio.sleep(0.5)

        # Step 1: Start x11vnc on port 5900
        await run_shell(
            "x11vnc -display :0 -forever -shared -rfbauth ~/.vnc/passwd "
            "-rfbport 5900 -auth guess -o /tmp/x11vnc.log 2>/dev/null & "
            "echo 'VNC started'"
        )
        await asyncio.sleep(1)

        # Step 2: Start websockify (noVNC proxy) on port 6080
        await run_shell(
            "websockify -D --web=/usr/share/novnc 6080 localhost:5900 2>/dev/null "
            "&& echo 'noVNC proxy started'"
        )
        await asyncio.sleep(1)

        # Step 3: Get the VM's IP address
        vm_ip = await run_shell("hostname -I 2>/dev/null | awk '{print $1}'")
        vm_ip = vm_ip.strip()
        if not vm_ip:
            vm_ip = "10.0.2.15"  # fallback

        web_url = f"http://{vm_ip}:6080/vnc.html"

        # Get VNC password from stored file or use default
        vnc_pass = OSBOXES_PASS
        if VNC_PASSWORD_FILE.exists():
            vnc_pass = VNC_PASSWORD_FILE.read_text().strip()

        # Create inline button to open in browser
        kb = [
            [InlineKeyboardButton("🖥️ Open Desktop in Browser", url=web_url)],
        ]

        await status_msg.edit_text(
            f"✅ *Web VNC Ready!*\n"
            f"━━━━━━━━━━━━━━━━\n\n"
            f"🔗 Tap the button below to open your desktop\n"
            f"in Telegram's built-in browser!\n\n"
            f"🔐 *Password:* `{vnc_pass}`\n\n"
            f"⚠️ *Note:* If the link doesn't work, your VM might be\n"
            f"in NAT mode. Set network to *Bridged* in your VM settings.\n"
            f"\n"
            f"🔗 `{web_url}`\n"
            f"📌 `/webvnc stop` - Stop web VNC",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ Failed to start web VNC: {e}")

async def rustdesk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show RustDesk connection information."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    # Check if RustDesk is installed (check multiple paths)
    rustdesk_paths = ["/usr/share/rustdesk/rustdesk", "/usr/bin/rustdesk", "/usr/local/bin/rustdesk"]
    rustdesk_found = any(Path(p).exists() for p in rustdesk_paths)
    rustdesk_bin = next((p for p in rustdesk_paths if Path(p).exists()), None)

    if not rustdesk_found:
        kb = [
            [
                InlineKeyboardButton("📥 Download RustDesk", url="https://github.com/rustdesk/rustdesk/releases"),
            ]
        ]
        await update.effective_message.reply_text(
            "❌ RustDesk is not installed.\n\n"
            "Install with:\n"
            "```bash\n"
            "wget https://github.com/rustdesk/rustdesk/releases/download/1.3.8/rustdesk-1.3.8-x86_64.deb\n"
            "sudo dpkg -i rustdesk-1.3.8.deb\n"
            "sudo apt install -f\n"
            "```\n\n"
            "Or click below to download:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # Get RustDesk ID
    id_output = await run_shell("rustdesk --get-id 2>/dev/null || cat /etc/rustdesk/id 2>/dev/null || echo 'Not available'")
    status_output = await run_shell("systemctl status rustdesk 2>/dev/null | grep -E 'Active|running' || echo 'Service not running'")
    config_output = await run_shell("cat ~/.config/rustdesk/RustDesk2.toml 2>/dev/null | grep -E 'password|relay-server' || echo 'No config found'")

    text = (
        "🖥️ *RustDesk Remote Desktop*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"*Connection Info:*\n"
        f"```\n{escape_md(id_output.strip())}```\n\n"
        f"*Service Status:*\n"
        f"```\n{escape_md(status_output.strip())}```\n\n"
        f"*To connect:*\n"
        "1. Install RustDesk on your phone (Google Play Store)\n"
        "2. Enter the ID above\n"
        "3. Enter the password you set in RustDesk settings\n\n"
        "💡 *Tip:* Set a permanent password in RustDesk Settings → Security → Set password"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def whoami_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the user their Telegram ID."""
    user = update.effective_user
    text = (
        f"👤 *Your Info*\n"
        f"━━━━━━━━━━━\n\n"
        f"*Name:* {user.full_name}\n"
        f"*Username:* @{user.username if user.username else 'N/A'}\n"
        f"*User ID:* `{user.id}`\n\n"
        f"*Authorized:* {'✅ Yes' if user.id in ADMIN_IDS else '❌ No'}\n\n"
        f"To add your ID, update `ADMIN_IDS` in the bot config."
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def reboot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reboot the machine with confirmation."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, reboot", callback_data="confirm_reboot"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_reboot"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(
        "⚠️ *WARNING:* Are you sure you want to reboot this machine?\n"
        "The bot will go offline until the system boots back up.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def shutdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shutdown the machine with confirmation."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, shutdown", callback_data="confirm_shutdown"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_shutdown"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_message.reply_text(
        "⚠️ *WARNING:* Are you sure you want to shutdown this machine?\n"
        "The bot will stop and the machine will power off.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# ============ MENU SYSTEM ============

async def build_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all menu callbacks and command buttons."""
    query = update.callback_query
    await query.answer()
    if not is_authorized(query.from_user.id):
        await query.edit_message_text("⛔ Unauthorized.")
        return
    data = query.data
    # ===== CONFIRMATION HANDLERS =====
    if data == "confirm_reboot":
        await query.edit_message_text("🔄 Rebooting now... Goodbye!")
        asyncio.create_task(run_shell("sudo reboot 2>/dev/null || reboot 2>/dev/null || systemctl reboot -i 2>/dev/null || shutdown -r now"))
        return
    elif data == "cancel_reboot":
        await query.edit_message_text("✅ Reboot cancelled.")
        return
    elif data == "confirm_shutdown":
        await query.edit_message_text("⏹️ Shutting down now... Goodbye!")
        asyncio.create_task(run_shell("sudo poweroff 2>/dev/null || poweroff 2>/dev/null || systemctl poweroff -i 2>/dev/null || shutdown -h now"))
        return
    elif data == "cancel_shutdown":
        await query.edit_message_text("✅ Shutdown cancelled.")
        return

    # ===== MAIN MENU =====
    if data == "menu_main":
        await start(update, context)
        return

    # ===== CATEGORY MENUS =====
    back_btn = InlineKeyboardButton("« Back to Menu", callback_data="menu_main")
    if data == "menu_system":
        text = (
            "💻 *System Commands*\n"
            "━━━━━━━━━━━━━━━\n"
            "_Explore system info, processes, services, and performance metrics._"
        )
        kb = [
            [InlineKeyboardButton("🔧 Shell Command", callback_data="cmd_shell")],
            [InlineKeyboardButton("📊 System Info", callback_data="cmd_sysinfo")],
            [InlineKeyboardButton("📋 Processes", callback_data="cmd_ps")],
            [InlineKeyboardButton("⏱️ Uptime", callback_data="cmd_uptime")],
            [InlineKeyboardButton("⚙️ Services", callback_data="cmd_services")],
            [InlineKeyboardButton("🪟 Open Apps", callback_data="cmd_apps")],
            [InlineKeyboardButton("🌡️ Temperatures", callback_data="cmd_temp")],
            [InlineKeyboardButton("📦 Packages", callback_data="cmd_packages")],
            [InlineKeyboardButton("🔄 Update System", callback_data="cmd_updatesys")],
            [InlineKeyboardButton("📋 Clipboard", callback_data="cmd_clipboard")],
            [back_btn],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_resources":
        text = (
            "📊 *Resource Commands*\n"
            "━━━━━━━━━━━━━━━━━\n"
            "_Check memory, disk, network, and IP addresses._"
        )
        kb = [
            [InlineKeyboardButton("🧠 Memory", callback_data="cmd_memory")],
            [InlineKeyboardButton("💾 Disk Usage", callback_data="cmd_disk")],
            [InlineKeyboardButton("🌐 IP Addresses", callback_data="cmd_ip")],
            [InlineKeyboardButton("📡 Network Info", callback_data="cmd_wifi")],
            [back_btn],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_desktop":
        text = (
            "🖥️ *Desktop Commands*\n"
            "━━━━━━━━━━━━━━━━\n"
            "_Capture screens, lock/unlock, notify, and type text._"
        )
        kb = [
            [InlineKeyboardButton("📸 Screenshot", callback_data="cmd_screenshot")],
            [InlineKeyboardButton("🔐 Lock Status", callback_data="cmd_lock_status")],
            [InlineKeyboardButton("🔐 Login Info", callback_data="cmd_login")],
            [InlineKeyboardButton("🔔 Send Notification", callback_data="cmd_notify")],
            [InlineKeyboardButton("⌨️ Type Text", callback_data="cmd_type")],
            [InlineKeyboardButton("🔘 Press Key", callback_data="cmd_key")],
            [back_btn],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_mouse":
        text = (
            "🖱️ *Mouse Commands*\n"
            "━━━━━━━━━━━━━━\n"
            "_View position, click, scroll, and navigate the desktop._"
        )
        kb = [
            [InlineKeyboardButton("📍 Show Position", callback_data="cmd_mouse_pos")],
            [
                InlineKeyboardButton("🖱️ Left Click", callback_data="cmd_click_left"),
                InlineKeyboardButton("🖱️ Right Click", callback_data="cmd_click_right"),
            ],
            [
                InlineKeyboardButton("📜 Scroll Up", callback_data="cmd_scroll_up"),
                InlineKeyboardButton("📜 Scroll Down", callback_data="cmd_scroll_down"),
            ],
            [back_btn],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_sound":
        text = (
            "🔊 *Sound Commands*\n"
            "━━━━━━━━━━━━━\n"
            "_Adjust volume, mute/unmute, and check audio levels._"
        )
        kb = [
            [InlineKeyboardButton("🔊 Get Volume", callback_data="cmd_sound_get")],
            [
                InlineKeyboardButton("🔊 Up", callback_data="cmd_sound_up"),
                InlineKeyboardButton("🔉 Down", callback_data="cmd_sound_down"),
            ],
            [
                InlineKeyboardButton("🔇 Mute", callback_data="cmd_sound_mute"),
                InlineKeyboardButton("🔊 Unmute", callback_data="cmd_sound_unmute"),
            ],
            [back_btn],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_files":
        text = (
            "📁 *Files & Storage*\n"
            "━━━━━━━━━━━━━━━━\n"
            "_Browse, upload, download, and manage files._"
        )
        kb = [
            [InlineKeyboardButton("📁 Home", callback_data="cmd_home"),
             InlineKeyboardButton("📂 Downloads", callback_data="cmd_downloads"),
             InlineKeyboardButton("📄 Documents", callback_data="cmd_docs")],
            [InlineKeyboardButton("🖼️ Screenshots", callback_data="cmd_screenshots"),
             InlineKeyboardButton("🎬 Videos", callback_data="cmd_videos")],
            [InlineKeyboardButton("📤 Upload", callback_data="cmd_upload"),
             InlineKeyboardButton("📥 Download", callback_data="cmd_download"),
             InlineKeyboardButton("💾 Backup", callback_data="cmd_backup")],
            [InlineKeyboardButton("🗑️ Empty Trash", callback_data="cmd_emptytrash"),
             InlineKeyboardButton("🧹 Clear Temp", callback_data="cmd_cleartemp")],
            [back_btn],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_remote":
        text = (
            "🌐 *Remote Access Commands*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "_Web VNC, VNC server, RustDesk, and browser access._"
        )
        kb = [
            [InlineKeyboardButton("🌐 Web VNC (Browser)", callback_data="cmd_webvnc")],
            [InlineKeyboardButton("🖥️ VNC Server", callback_data="cmd_vnc_status")],
            [InlineKeyboardButton("🔄 RustDesk Info", callback_data="cmd_rustdesk")],
            [InlineKeyboardButton("🌍 Open URL", callback_data="cmd_web")],
            [back_btn],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_control":
        text = (
            "⚡ *Control Commands*\n"
            "━━━━━━━━━━━━━━━\n"
            "_Reboot, shutdown, history, and account info._"
        )
        kb = [
            [
                InlineKeyboardButton("🔄 Reboot", callback_data="cmd_reboot"),
                InlineKeyboardButton("⏹️ Shutdown", callback_data="cmd_shutdown"),
            ],
            [InlineKeyboardButton("📜 Command History", callback_data="cmd_cmdhistory")],
            [InlineKeyboardButton("👤 Who Am I", callback_data="cmd_whoami")],
            [back_btn],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_help":
        await help_command(update, context)
        return

    elif data == "menu_extra":
        text = (
            "🌟 *Extra Tools*\n"
            "━━━━━━━━━━━━━\n"
            "_Fun, utilities, developer tools, and more._"
        )
        kb = [
            [InlineKeyboardButton("🎲 Roll Dice", callback_data="cmd_dice"),
             InlineKeyboardButton("🪙 Flip Coin", callback_data="cmd_coin"),
             InlineKeyboardButton("🔮 Fortune", callback_data="cmd_fortune")],
            [InlineKeyboardButton("🎱 8-Ball", callback_data="cmd_8ball"),
             InlineKeyboardButton("👾 Matrix", callback_data="cmd_matrix"),
             InlineKeyboardButton("🐱 Cat Facts", callback_data="cmd_catfacts")],
            [InlineKeyboardButton("🧮 Calculator", callback_data="cmd_calc"),
             InlineKeyboardButton("📝 Notes", callback_data="cmd_notes"),
             InlineKeyboardButton("📅 Calendar", callback_data="cmd_calendar")],
            [InlineKeyboardButton("🖥️ Screen Res", callback_data="cmd_screenres"),
             InlineKeyboardButton("🎨 Theme", callback_data="cmd_theme"),
             InlineKeyboardButton("📷 Camera", callback_data="cmd_camera")],
            [InlineKeyboardButton("💡 Brightness", callback_data="cmd_brightness"),
             InlineKeyboardButton("🌙 Night Mode", callback_data="cmd_nightmode")],
            [InlineKeyboardButton("🔍 About", callback_data="cmd_about"),
             InlineKeyboardButton("« Back to Menu", callback_data="menu_main")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_dev":
        text = (
            "🛠️ *Developer Tools*\n"
            "━━━━━━━━━━━━━━━\n"
            "_Coding, building, testing, and containers._"
        )
        kb = [
            [InlineKeyboardButton("🐍 Python", callback_data="cmd_python"),
             InlineKeyboardButton("🐳 Docker", callback_data="cmd_docker"),
             InlineKeyboardButton("📝 VS Code", callback_data="cmd_vscode")],
            [InlineKeyboardButton("🐙 Git Status", callback_data="cmd_git"),
             InlineKeyboardButton("🛠️ Build", callback_data="cmd_build"),
             InlineKeyboardButton("🧪 Run Tests", callback_data="cmd_tests")],
            [InlineKeyboardButton("📦 Packages", callback_data="cmd_packages"),
             InlineKeyboardButton("🔄 Update", callback_data="cmd_updatesys")],
            [InlineKeyboardButton("« Back to Menu", callback_data="menu_main")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_files":
        text = (
            "📁 *Files & Storage*\n"
            "━━━━━━━━━━━━━━━━\n"
            "_Browse, upload, download, and manage files._"
        )
        kb = [
            [InlineKeyboardButton("📁 Home", callback_data="cmd_home"),
             InlineKeyboardButton("📂 Downloads", callback_data="cmd_downloads"),
             InlineKeyboardButton("📄 Documents", callback_data="cmd_docs")],
            [InlineKeyboardButton("🖼️ Screenshots", callback_data="cmd_screenshots"),
             InlineKeyboardButton("🎬 Videos", callback_data="cmd_videos")],
            [InlineKeyboardButton("📤 Upload", callback_data="cmd_upload"),
             InlineKeyboardButton("📥 Download", callback_data="cmd_download"),
             InlineKeyboardButton("💾 Backup", callback_data="cmd_backup")],
            [InlineKeyboardButton("🗑️ Empty Trash", callback_data="cmd_emptytrash"),
             InlineKeyboardButton("🧹 Clear Temp", callback_data="cmd_cleartemp")],
            [InlineKeyboardButton("« Back to Menu", callback_data="menu_main")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_fun":
        text = (
            "🎮 *Fun & Games*\n"
            "━━━━━━━━━━━━\n"
            "_Take a break with these fun commands._"
        )
        kb = [
            [InlineKeyboardButton("🎲 Roll Dice", callback_data="cmd_dice"),
             InlineKeyboardButton("🪙 Flip Coin", callback_data="cmd_coin"),
             InlineKeyboardButton("🔮 Fortune", callback_data="cmd_fortune")],
            [InlineKeyboardButton("🎱 8-Ball", callback_data="cmd_8ball"),
             InlineKeyboardButton("👾 Matrix", callback_data="cmd_matrix"),
             InlineKeyboardButton("🐱 Cat Facts", callback_data="cmd_catfacts")],
            [InlineKeyboardButton("🎵 Music", callback_data="cmd_music"),
             InlineKeyboardButton("🎬 Media", callback_data="cmd_media"),
             InlineKeyboardButton("📺 YouTube", callback_data="cmd_youtube")],
            [InlineKeyboardButton("🎮 Steam", callback_data="cmd_steam"),
             InlineKeyboardButton("🎧 Podcasts", callback_data="cmd_podcast"),
             InlineKeyboardButton("🖼️ Images", callback_data="cmd_images")],
            [InlineKeyboardButton("« Back to Menu", callback_data="menu_main")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_media":
        text = (
            "🎵 *Media & Entertainment*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "_Music, videos, images, and streaming._"
        )
        kb = [
            [InlineKeyboardButton("🎵 Music Player", callback_data="cmd_music"),
             InlineKeyboardButton("🎬 Media Player", callback_data="cmd_media"),
             InlineKeyboardButton("🖼️ Image Viewer", callback_data="cmd_images")],
            [InlineKeyboardButton("📺 YouTube", callback_data="cmd_youtube"),
             InlineKeyboardButton("🎮 Steam", callback_data="cmd_steam"),
             InlineKeyboardButton("🎧 Podcasts", callback_data="cmd_podcast")],
            [InlineKeyboardButton("📷 Camera", callback_data="cmd_camera"),
             InlineKeyboardButton("🎬 Videos Folder", callback_data="cmd_videos")],
            [InlineKeyboardButton("« Back to Menu", callback_data="menu_main")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    elif data == "menu_security":
        text = (
            "🛡️ *Security & Privacy*\n"
            "━━━━━━━━━━━━━━━━━\n"
            "_Firewall, encryption, keys, and secure operations._"
        )
        kb = [
            [InlineKeyboardButton("🛡️ Firewall", callback_data="cmd_firewall"),
             InlineKeyboardButton("🔐 SSH Keys", callback_data="cmd_sshkeys"),
             InlineKeyboardButton("🔑 Keychain", callback_data="cmd_keychain")],
            [InlineKeyboardButton("🔐 Login Info", callback_data="cmd_login"),
             InlineKeyboardButton("🧹 Secure Delete", callback_data="cmd_shred"),
             InlineKeyboardButton("🔍 Port Scan", callback_data="cmd_portscan")],
            [InlineKeyboardButton("🔐 VPN Toggle", callback_data="cmd_vpn"),
             InlineKeyboardButton("🧦 SOCKS5", callback_data="cmd_socks5")],
            [InlineKeyboardButton("« Back to Menu", callback_data="menu_main")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    # ===== COMMAND ACTIONS =====
    # These execute commands directly and reply with a new message
    cmd_actions = {
        "cmd_sysinfo": ("📊 System Info", sysinfo_command),
        "cmd_ps": ("📋 Processes", ps_command),
        "cmd_uptime": ("⏱️ Uptime", uptime_command),
        "cmd_services": ("⚙️ Services", services_command),
        "cmd_apps": ("🪟 Open Apps", apps_command),
        "cmd_temp": ("🌡️ Temps", temp_command),
        "cmd_memory": ("🧠 Memory", memory_command),
        "cmd_disk": ("💾 Disk", disk_command),
        "cmd_ip": ("🌐 IPs", ip_command),
        "cmd_wifi": ("📡 Network", wifi_command),
        "cmd_screenshot": ("📸 Screenshot", screenshot_command),
        "cmd_lock": ("🔒 Lock", lock_command),
        "cmd_unlock": ("🔓 Unlock", unlock_command),
        "cmd_lock_status": ("🔐 Lock Status", lock_status_command),
        "cmd_login": ("🔐 Login", login_command),
        "cmd_cmdhistory": ("📜 History", cmdhistory_command),
        "cmd_whoami": ("👤 Who Am I", whoami_command),
        "cmd_phone": ("📱 Phone", phone_command),
        "cmd_rustdesk": ("🔄 RustDesk", rustdesk_command),
        "cmd_vnc_status": ("🖥️ VNC", vnc_command),
        "cmd_webvnc": ("🌐 Web VNC", webvnc_command),
    }
    # Extra command callbacks (from extra_commands)
    extra_cmd_actions = {
        "cmd_packages": ("📦 Packages", packages_command),
        "cmd_updatesys": ("🔄 Update", update_system),
        "cmd_gputemp": ("🌡️ GPU", gpu_temp_handler),
        "cmd_speedtest": ("📡 Speed", speed_test),
        "cmd_music": ("🎵 Music", open_music),
        "cmd_media": ("🎬 Media", open_media),
        "cmd_images": ("🖼️ Images", open_images),
        "cmd_youtube": ("📺 YouTube", open_youtube),
        "cmd_steam": ("🎮 Steam", open_steam),
        "cmd_podcast": ("🎧 Podcast", podcast_command),
        "cmd_home": ("📁 Home", open_home),
        "cmd_downloads": ("📂 Downloads", open_downloads),
        "cmd_docs": ("📄 Documents", open_documents),
        "cmd_screenshots": ("🖼️ Screenshots", open_screenshots),
        "cmd_videos": ("🎬 Videos", open_videos),
        "cmd_backup": ("💾 Backup", backup_command),
        "cmd_emptytrash": ("🗑️ Empty", empty_trash),
        "cmd_share": ("🖧 Share", share_folder),
        "cmd_restartnet": ("🔄 Network", restart_network),
        "cmd_firewall": ("🛡️ Firewall", firewall_status),
        "cmd_sshkeys": ("🔐 SSH Keys", ssh_keys),
        "cmd_shred": ("🧹 Secure Delete", secure_delete),
        "cmd_portscan": ("🔍 Port Scan", port_scan),
        "cmd_keychain": ("🔑 Keychain", keychain_command),
        "cmd_python": ("🐍 Python", python_shell),
        "cmd_docker": ("🐳 Docker", docker_status),
        "cmd_vscode": ("📝 VS Code", open_vscode),
        "cmd_git": ("🐙 Git", git_status),
        "cmd_build": ("🛠️ Build", build_project),
        "cmd_tests": ("🧪 Tests", run_tests),
        "cmd_dice": ("🎲 Dice", roll_dice),
        "cmd_coin": ("🪙 Coin", flip_coin),
        "cmd_fortune": ("🔮 Fortune", fortune_cookie),
        "cmd_8ball": ("🎱 8-Ball", eight_ball),
        "cmd_matrix": ("👾 Matrix", matrix_effect),
        "cmd_catfacts": ("🐱 Cat Facts", cat_facts),
        "cmd_screenres": ("🖥️ Screen", screen_res),
        "cmd_brightness": ("💡 Brightness", brightness_command),
        "cmd_nightmode": ("🌙 Night", night_mode),
        "cmd_theme": ("🎨 Theme", theme_command),
        "cmd_about": ("🔍 About", about_command),
        "cmd_cleartemp": ("🧹 Clear Temp", clear_temp),
        "cmd_poweroff": ("🔌 Power", power_off),
        "cmd_calc": ("🧮 Calc", calculator_command),
        "cmd_notes": ("📝 Notes", notes_command),
        "cmd_calendar": ("📅 Calendar", calendar_command),
        "cmd_camera": ("📷 Camera", open_camera),
    }
    if data in extra_cmd_actions:
        name, handler = extra_cmd_actions[data]
        await query.edit_message_text(f"⚡ Running `{name}`...", parse_mode="Markdown")
        await handler(update, context)
        return
    if data in cmd_actions:
        name, handler = cmd_actions[data]
        await query.edit_message_text(f"⚡ Running `{name}`...", parse_mode="Markdown")
        await handler(update, context)
        return
    # ===== WEB PANEL CALLBACKS =====
    if data == "cmd_webpanel_stop":
        await query.edit_message_text("⏹️ Stopping web panel...")
        context.args = ["stop"]
        await webpanel_command(update, context)
        return

    # Mouse command actions (need special handling)
    if data == "cmd_mouse_pos":
        await query.edit_message_text("📍 Getting mouse position...")
        await mouse_command(update, context)
        return
    elif data == "cmd_click_left":
        await query.edit_message_text("🖱️ Left clicking...")
        context.args = ["left"]
        await click_command(update, context)
        return
    elif data == "cmd_click_right":
        await query.edit_message_text("🖱️ Right clicking...")
        context.args = ["right"]
        await click_command(update, context)
        return
    elif data == "cmd_scroll_up":
        await query.edit_message_text("📜 Scrolling up...")
        context.args = ["up", "5"]
        await scroll_command(update, context)
        return
    elif data == "cmd_scroll_down":
        await query.edit_message_text("📜 Scrolling down...")
        context.args = ["down", "5"]
        await scroll_command(update, context)
        return
    elif data == "cmd_sound_get":
        await query.edit_message_text("🔊 Getting volume...")
        context.args = ["get"]
        await sound_command(update, context)
        return
    elif data == "cmd_sound_up":
        await query.edit_message_text("🔊 Volume up...")
        context.args = ["up"]
        await sound_command(update, context)
        return
    elif data == "cmd_sound_down":
        await query.edit_message_text("🔉 Volume down...")
        context.args = ["down"]
        await sound_command(update, context)
        return
    elif data == "cmd_sound_mute":
        await query.edit_message_text("🔇 Muting...")
        context.args = ["mute"]
        await sound_command(update, context)
        return
    elif data == "cmd_sound_unmute":
        await query.edit_message_text("🔊 Unmuting...")
        context.args = ["unmute"]
        await sound_command(update, context)
        return

    # ===== SOCKS5 CALLBACKS =====
    if data == "socks5_main":
        await socks5_command(update, context)
        return
    if data == "socks5_stop":
        await query.edit_message_text("⏹️ Stopping SOCKS5 proxy...")
        await run_shell("pkill -x microsocks 2>/dev/null; echo 'done'")
        await asyncio.sleep(1)
        await socks5_command(update, context)
        return
    if data == "socks5_restart":
        await query.edit_message_text("🔄 Restarting SOCKS5 proxy...")
        await run_shell("pkill -x microsocks 2>/dev/null; sleep 1; echo 'done'")
        subprocess.Popen(["microsocks", "-i", "0.0.0.0", "-p", "1080", "-b", "-u", OSBOXES_USER, "-P", OSBOXES_PASS],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(1)
        await socks5_command(update, context)
        return

    # ===== DASHBOARD CALLBACKS =====
    if data == "cmd_dashboard":
        await dashboard_command(update, context)
        return
    if data == "cmd_dash_lock":
        await query.edit_message_text("🔒 Locking screen...")
        await lock_command(update, context)
        return
    if data == "cmd_dash_unlock":
        await query.edit_message_text("🔓 Unlocking screen...")
        await unlock_command(update, context)
        return
    if data == "cmd_dash_screenshot":
        await query.edit_message_text("📷 Taking screenshot...")
        await screenshot_command(update, context)
        return
    if data == "cmd_dash_volup":
        await query.edit_message_text("🔊 Volume up...")
        context.args = ["up"]
        await sound_command(update, context)
        return
    if data == "cmd_dash_voldown":
        await query.edit_message_text("🔉 Volume down...")
        context.args = ["down"]
        await sound_command(update, context)
        return
    if data == "cmd_dash_mute":
        await query.edit_message_text("🔇 Toggling mute...")
        context.args = ["toggle"]
        await sound_command(update, context)
        return

    # ===== VPN CALLBACKS =====
    if data == "vpn_cancel":
        await query.edit_message_text("✅ VPN cancelled.", parse_mode="Markdown")
        return

    if data == "vpn_stop":
        await query.edit_message_text("⏹️ Disconnecting VPN...")
        await run_shell(
            f"echo {OSBOXES_PASS} | sudo -S pkill -f 'wg-quick|openvpn' 2>/dev/null; "
            f"echo {OSBOXES_PASS} | sudo -S ip link delete tun0 2>/dev/null; "
            f"echo 'done'"
        )
        await asyncio.sleep(1)
        await vpn_command(update, context)
        return

    if data == "vpn_restart":
        await query.edit_message_text("🔄 Reconnecting VPN...")
        await run_shell(
            f"echo {OSBOXES_PASS} | sudo -S pkill -f 'wg-quick|openvpn' 2>/dev/null; "
            f"sleep 2; echo 'done'"
        )
        # Try to restart with available configs
        wg_conf = list(Path("/etc/wireguard").glob("*.conf")) if Path("/etc/wireguard").exists() else []
        ovpn_conf = list(Path("/etc/openvpn/client").glob("*.conf")) if Path("/etc/openvpn/client").exists() else []
        ovpn_ovpn = list(Path("/etc/openvpn/client").glob("*.ovpn")) if Path("/etc/openvpn/client").exists() else []
        if not ovpn_conf and not ovpn_ovpn:
            ovpn_conf = list(Path("/etc/openvpn").glob("*.conf")) if Path("/etc/openvpn").exists() else []
            ovpn_ovpn = list(Path("/etc/openvpn").glob("*.ovpn")) if Path("/etc/openvpn").exists() else []
        ovpn_conf = ovpn_conf + ovpn_ovpn
        if wg_conf:
            await run_shell(f"echo {OSBOXES_PASS} | sudo -S wg-quick up {wg_conf[0].stem} 2>/dev/null; echo 'done'")
        elif ovpn_conf and shutil.which("openvpn"):
            subprocess.Popen(["sudo", "-S", "openvpn", "--config", str(ovpn_conf[0]), "--daemon"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).communicate(input=f"{OSBOXES_PASS}\n".encode())
        await asyncio.sleep(2)
        await vpn_command(update, context)
        return

    if data.startswith("vpn_start_"):
        conf_path = data[10:]  # Remove "vpn_start_" prefix
        await query.edit_message_text(f"🔐 Connecting to `{Path(conf_path).name}`...", parse_mode="Markdown")
        if conf_path.startswith("/etc/wireguard/"):
            # WireGuard
            name = Path(conf_path).stem
            result = await run_shell(
                f"echo {OSBOXES_PASS} | sudo -S wg-quick up {name} 2>&1; echo 'done'"
            )
        else:
            # OpenVPN
            subprocess.Popen(
                ["sudo", "-S", "openvpn", "--config", conf_path, "--daemon", "--log", "/tmp/openvpn.log"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ).communicate(input=f"{OSBOXES_PASS}\n".encode())
            await asyncio.sleep(3)
            result = await run_shell("cat /tmp/openvpn.log 2>/dev/null | tail -3 || echo 'started'")
        await asyncio.sleep(2)
        # Show updated status
        await vpn_command(update, context)
        return

    # ===== GPG CALLBACKS =====
    if data == "gpg_main":
        await gpg_command(update, context)
        return
    if data == "gpg_list":
        await gpg_list_keys(update, context)
        return
    if data == "gpg_gen":
        await gpg_generate_key(update, context)
        return
    if data == "gpg_gen_do":
        await gpg_gen_do(update, context)
        return
    if data == "gpg_export":
        await gpg_export_prompt(update, context)
        return
    if data == "gpg_close":
        await query.edit_message_text("✅ Closed GPG Manager.")
        return
    if data.startswith("gpg_export_do_"):
        await gpg_export_do(update, context)
        return
    if data == "gpg_delete":
        await gpg_delete_prompt(update, context)
        return
    if data.startswith("gpg_del_"):
        if data.startswith("gpg_del_conf_"):
            await gpg_delete_do(update, context)
        else:
            await gpg_delete_confirm(update, context)
        return

    # Commands that need user input (prompt the user to type)
    if data == "cmd_shell":
        await query.edit_message_text(
            "💻 *Run a Shell Command*\n\n"
            "Type your command after `/shell`\n"
            "Example: `/shell whoami`",
            parse_mode="Markdown"
        )
        return
    elif data == "cmd_notify":
        await query.edit_message_text(
            "🔔 *Send a Notification*\n\n"
            "Type your message after `/notify`\n"
            "Example: `/notify Hello from phone!`",
            parse_mode="Markdown"
        )
        return
    elif data == "cmd_type":
        await query.edit_message_text(
            "⌨️ *Type on Keyboard*\n\n"
            "Type your text after `/type`\n"
            "Example: `/type Hello World`",
            parse_mode="Markdown"
        )
        return
    elif data == "cmd_key":
        await query.edit_message_text(
            "🔘 *Press a Key*\n\n"
            "Type your key after `/key`\n"
            "Example: `/key Enter`\n"
            "Available: `Enter`, `Tab`, `Escape`, `F5`, etc.",
            parse_mode="Markdown"
        )
        return
    elif data == "cmd_web":
        await query.edit_message_text(
            "🌍 *Open a URL*\n\n"
            "Type the URL after `/web`\n"
            "Example: `/web https://google.com`",
            parse_mode="Markdown"
        )
        return
    elif data == "cmd_upload":
        await query.edit_message_text(
            "📤 *Upload a File*\n\n"
            "Type the file path after `/upload`\n"
            "Example: `/upload /etc/passwd`",
            parse_mode="Markdown"
        )
        return
    elif data == "cmd_download":
        await query.edit_message_text(
            "📥 *Download a File*\n\n"
            "Send a file or photo in this chat\n"
            "and it will be saved to your VM!",
            parse_mode="Markdown"
        )
        return
    elif data == "cmd_reboot":
        await query.edit_message_text(
            "⚠️ *Are you sure?*\n"
            "This will reboot the machine!\n"
            "The bot will go offline until reboot completes."
        )
        # Send confirmation buttons
        kb = [
            [
                InlineKeyboardButton("✅ Yes, reboot", callback_data="confirm_reboot"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_reboot"),
            ]
        ]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="🔄 *Confirm Reboot:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return
    elif data == "cmd_shutdown":
        await query.edit_message_text(
            "⚠️ *Are you sure?*\n"
            "This will shutdown the machine!\n"
            "The bot will stop and the machine will power off."
        )
        kb = [
            [
                InlineKeyboardButton("✅ Yes, shutdown", callback_data="confirm_shutdown"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_shutdown"),
            ]
        ]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="⏹️ *Confirm Shutdown:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

# ============ NEW COMMAND HANDLERS ============

# ============ PHONE NUMBER COMMANDS ============

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming contact sharing (phone number)."""
    if not is_authorized(update.effective_user.id):
        return

    contact = update.message.contact
    if not contact:
        return

    user_id = update.effective_user.id
    phone = contact.phone_number
    first_name = contact.first_name or ""

    # Save the phone number
    save_phone_number(user_id, phone, first_name)

    # Remove the keyboard after sharing
    await update.effective_message.reply_text(
        f"✅ *Phone Number Saved!* 🎉\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 *Number:* `{phone}`\n"
        f"👤 *Name:* {first_name}\n"
        f"🆔 *Telegram ID:* `{user_id}`\n\n"
        f"You can now use the main menu again by tapping /start",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )


async def phone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request user's phone number via Telegram's built-in contact sharing."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    user_id = update.effective_user.id

    # Check if we already have their number
    existing = get_phone_number(user_id)

    # Show contact sharing button
    kb = [[KeyboardButton("📱 Share My Phone Number 💯", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)

    msg = (
        "📱 *Share Your Phone Number*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Tap the button below to share your phone number!\n\n"
        "🔒 *100% safe:* Telegram handles this securely and\n"
        "only shares it with this bot.\n"
        "💡 Just tap the button → done! \n\n"
        "_Send /start anytime to go back._"
    )

    if existing:
        msg = (
            f"📱 *You already shared:* `{existing['phone']}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Tap below to share a *new* number,\n"
            f"or send /start to go back.\n\n"
            f"🔒 _Your number is stored securely._"
        )

    # Handle both callback (from menu button) and direct /phone command
    is_callback = update.callback_query is not None
    if is_callback:
        await update.callback_query.edit_message_text(
            "📱 Tap the button that just appeared below 👇",
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=msg,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)















async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show a rich system dashboard with live stats and action buttons inside Telegram."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    
    is_callback = update.callback_query is not None
    
    # Gather all system info
    cpu_usage = await run_shell("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
    cpu_usage = cpu_usage.strip() or "0"
    
    mem_info = await run_shell("free -h | grep Mem | awk '{print $3 "/" $2}'")
    mem_pct = await run_shell("free | grep Mem | awk '{printf \"%.0f\", $3/$2 * 100}'")
    mem_pct = mem_pct.strip() or "0"
    
    disk_info = await run_shell("""df -h / | tail -1 | awk '{print $3\"/\"$2\" (\"$5\")\"}'""")
    disk_pct = await run_shell("df / | tail -1 | awk '{print $5+0}'")
    disk_pct = disk_pct.strip() or "0"
    
    uptime = await run_shell("uptime -p 2>/dev/null | sed 's/up //' || uptime")
    processes = await run_shell("ps aux | wc -l")
    ip = await run_shell("hostname -I 2>/dev/null | awk '{print $1}'")
    hostname = platform.node()
    
    # Check lock status
    locked_check = await run_shell("pgrep -x i3lock 2>/dev/null || echo 'unlocked'")
    is_locked = "unlocked" not in locked_check.lower()
    
    # Sound status
    vol = await run_shell("amixer get Master 2>/dev/null | grep -o '[0-9]*%' | head -1 || echo 'N/A'")
    mute_check = await run_shell("amixer get Master 2>/dev/null | grep -o '\\[on\\]|\\[off\\]' | head -1 || echo ''")
    is_muted = 'off' in mute_check
    
    # Build progress bars
    try:
        cpu_blocks = int(float(cpu_usage)) // 5
    except ValueError:
        cpu_blocks = 0
    cpu_bar_str = "█" * min(cpu_blocks, 20) + "░" * max(20 - min(cpu_blocks, 20), 0)
    
    try:
        mem_blocks = int(mem_pct) // 5
    except ValueError:
        mem_blocks = 0
    mem_bar_str = "█" * min(mem_blocks, 20) + "░" * max(20 - min(mem_blocks, 20), 0)
    
    try:
        disk_blocks = int(disk_pct) // 5
    except ValueError:
        disk_blocks = 0
    disk_bar_str = "█" * min(disk_blocks, 20) + "░" * max(20 - min(disk_blocks, 20), 0)
    
    lock_icon = "🔒" if is_locked else "🔓"
    lock_status = "LOCKED" if is_locked else "Unlocked"
    
    sound_icon = "🔇" if is_muted else "🔊"
    sound_status = "Muted" if is_muted else f"{vol.strip()}"
    
    text = (
        "\U0001f4ca *System Dashboard*\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\n"
        f"\U0001f4bb *CPU:*      {cpu_usage}%\n"
        f"`{cpu_bar_str}`\n"
        f"\U0001f9e0 *Memory:*   {mem_info}\n"
        f"`{mem_bar_str}`\n"
        f"\U0001f4be *Disk:*     {disk_info}\n"
        f"`{disk_bar_str}`\n"
        "\n"
        f"\u23f1 *Uptime:*    {uptime.strip()}\n"
        f"\U0001f310 *IP:*        `{ip.strip()}`\n"
        f"\U0001f4ca *Processes:* {processes.strip()}\n"
        f"\U0001f5a5 *Hostname:* {hostname}\n"
        "\n"
        f"{lock_icon} *Screen:* {lock_status}   {sound_icon} *Sound:* {sound_status}\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    )

    kb = [
        # Row 1: Screen control
        [
            InlineKeyboardButton("🔒 Lock", callback_data="cmd_dash_lock"),
            InlineKeyboardButton("🔓 Unlock", callback_data="cmd_dash_unlock"),
            InlineKeyboardButton("📷 Screenshot", callback_data="cmd_dash_screenshot"),
        ],
        # Row 2: Sound control
        [
            InlineKeyboardButton("🔉 Vol Down", callback_data="cmd_dash_voldown"),
            InlineKeyboardButton("🔇 Mute", callback_data="cmd_dash_mute"),
            InlineKeyboardButton("🔊 Vol Up", callback_data="cmd_dash_volup"),
        ],
        # Row 3: Actions
        [
            InlineKeyboardButton("📊 Sysinfo", callback_data="cmd_sysinfo"),
            InlineKeyboardButton("📋 Processes", callback_data="cmd_ps"),
        ],
        # Row 4: Refresh & Back
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="cmd_dashboard"),
            InlineKeyboardButton("« Menu", callback_data="menu_main"),
        ],
    ]
    
    reply_markup = InlineKeyboardMarkup(kb)
    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def webpanel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start/stop web control panel and show access info."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    is_callback = update.callback_query is not None

    existing = await run_shell("pgrep -f 'python3.*web_panel.py' | grep -v grep || echo 'not_running'")
    is_running = "not_running" not in existing

    if context.args and context.args[0].lower() == "stop":
        await run_shell("pkill -f 'python3.*web_panel.py' 2>/dev/null; sleep 1; echo 'stopped'")
        text = "⏹ *Web Panel Stopped*\n━━━━━━━━━━━━━━━\nThe web control panel has been shut down."
        if is_callback:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown")
        else:
            await update.effective_message.reply_text(text, parse_mode="Markdown")
        return

    if not is_running:
        script_dir = Path(__file__).parent
        web_panel_path = script_dir / "web_panel.py"
        if not web_panel_path.exists():
            text = "❌ Web panel script not found at `web_panel.py` in the bot directory."
            if is_callback:
                await update.callback_query.edit_message_text(text, parse_mode="Markdown")
            else:
                await update.effective_message.reply_text(text, parse_mode="Markdown")
            return

        subprocess.Popen(
            ["python3", str(web_panel_path)],
            cwd=str(script_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(2)
        port_check = await run_shell("ss -tlnp | grep 5000 || echo 'not_listening'")
        is_running = "not_listening" not in port_check

    vm_ip = await run_shell("hostname -I 2>/dev/null | awk '{print $1}'")
    vm_ip = vm_ip.strip()
    if not vm_ip:
        vm_ip = "10.0.2.15"

    web_url = f"http://{vm_ip}:5000"
    password = "osboxes.org"

    if is_running:
        text = ("🌐 *Web Panel is Running* ✅\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Tap the button below to open the control panel!\n"
                "It works in Telegram's built-in browser too!\n\n"
                "🔐 *Password:* `{password}`\n\n"
                "🔗 `{web_url}`\n\n"
                "*Features:* Dashboard, Terminal, Desktop control,\n"
                "System monitor, Sound, Network, File browser, and more!\n\n"
                "📌 `/webpanel stop` - Stop the web panel")
        kb = [
            [InlineKeyboardButton("🌐 Open Web Panel", url=web_url)],
            [InlineKeyboardButton("⏹ Stop Web Panel", callback_data="cmd_webpanel_stop"),
             InlineKeyboardButton("« Back", callback_data="menu_main")],
        ]
    else:
        text = ("🌐 *Web Panel*\n"
                "━━━━━━━━━━━━━━\n"
                "❌ Failed to start the web panel.\n"
                "Port 5000 may be in use or the script had an error.")
        kb = [[InlineKeyboardButton("« Back", callback_data="menu_main")]]

    reply_markup = InlineKeyboardMarkup(kb)
    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
async def unlock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unlock the screen by typing password for i3lock."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    if not shutil.which("xdotool"):
        await update.effective_message.reply_text("❌ xdotool not installed. Run: `sudo apt install xdotool`", parse_mode="Markdown")
        return

    # Check if screen is actually locked
    locked_check = await run_shell("pgrep -x i3lock 2>/dev/null || pgrep -x xfce4-screensaver 2>/dev/null || echo 'not_locked'")
    if "not_locked" in locked_check:
        await update.effective_message.reply_text(
            "⚠️ Screen doesn't appear to be locked.\n"
            "Use *🔒 Lock* first, then *🔓 Unlock*.",
            parse_mode="Markdown"
        )
        return

    await update.effective_message.reply_text("🔓 Unlocking screen (typing password for i3lock)...")

    try:
        # i3lock captures ALL keyboard input directly via PAM.
        # No need to click - just type password + Enter
        # i3lock receives keystrokes and authenticates automatically

        # Step 1: Small delay to let user see the message
        await asyncio.sleep(0.5)

        # Step 2: Type password directly (i3lock captures this)
        subprocess.run(["xdotool", "type", "--delay", "20", OSBOXES_PASS], timeout=5, env={"DISPLAY": ":0"})
        await asyncio.sleep(0.3)

        # Step 3: Press Enter - i3lock authenticates and unlocks
        subprocess.run(["xdotool", "key", "Return"], timeout=3, env={"DISPLAY": ":0"})

        await asyncio.sleep(0.5)

        # Check if unlocked
        still_locked = await run_shell("pgrep -x i3lock 2>/dev/null || echo 'unlocked'")

        if "unlocked" in still_locked:
            await update.effective_message.reply_text(
                "🔓 *Screen Unlocked!* ✅\n"
                "━━━━━━━━━━━━━━━━━\n"
                "Desktop is now accessible. 🎉",
                parse_mode="Markdown"
            )
        else:
            await update.effective_message.reply_text(
                "⚠️ Password was typed but screen is still locked.\n"
                "The password might be incorrect.\n"
                "Try `/login` to check the stored password.",
                parse_mode="Markdown"
            )

    except Exception as e:
        await update.effective_message.reply_text(f"❌ Failed to unlock: {e}")

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show stored login credentials for the VM."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    text = (
        "🔐 *OSBoxes VM Login Credentials*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Username:* `{OSBOXES_USER}`\n"
        f"*Password:* `{OSBOXES_PASS}`\n\n"
        "📌 *Commands:*\n"
        "`/lock` - Lock the screen\n"
        "`/unlock` - Auto-type password to unlock\n"
        "`/login` - Show this info again"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system uptime."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    output = await run_shell("uptime -p 2>/dev/null; echo '---'; uptime 2>/dev/null; echo '---'; who -b 2>/dev/null | awk '{print \"Boot time: \"$3\" \"$4}'")
    await update.effective_message.reply_text(f"⏱️ *System Uptime*\n```\n{output.strip()}```", parse_mode="Markdown")

async def ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show IP addresses."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    local_ip = await run_shell("hostname -I 2>/dev/null")
    wan_ip = await run_shell("curl -s ifconfig.me 2>/dev/null || echo 'Unavailable'")
    interfaces = await run_shell("ip -4 addr show | grep inet | grep -v 127.0.0.1 | awk '{print \"  • \"$2, $NF}'")
    gateway = await run_shell("ip route | grep default | awk '{print \"  • \"$3}'")

    text = (
        "🌐 *IP Addresses*\n"
        "━━━━━━━━━━━━━━\n\n"
        f"*Local IPs:*\n{escape_md(interfaces.strip())}\n\n"
        f"*Gateway:*\n{escape_md(gateway.strip())}\n\n"
        f"*Public IP:* `{wan_ip.strip()}`"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show disk usage."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    output = await run_shell("df -h --total 2>/dev/null | grep -E '^/dev|total|Filesystem' | column -t")
    inode = await run_shell("df -i --total 2>/dev/null | grep -E '^/dev|total' | column -t")

    text = (
        "💾 *Disk Usage*\n"
        "━━━━━━━━━━━━\n\n"
        f"```\n{output.strip()}```\n\n"
        f"*Inodes:*\n```\n{inode.strip()}```"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed memory usage."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    mem = await run_shell("free -h | grep -E '^Mem:|^Swap:|^total'")
    details = await run_shell("cat /proc/meminfo | grep -E 'MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree|Cached|Buffers' | head -10")
    top_ram = await run_shell("ps aux --sort=-%mem | head -6 | awk '{print \"  • \"$4\"% \"$11}'")

    text = (
        "🧠 *Memory Usage*\n"
        "━━━━━━━━━━━━━\n\n"
        f"```\n{mem.strip()}```\n\n"
        f"*Details:*\n```\n{details.strip()}```\n\n"
        f"*Top RAM processes:*\n{escape_md(top_ram.strip())}"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def temp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show CPU and system temperatures."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    temps = await run_shell("cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{temp=$1/1000; printf \"  • %.1f°C\\n\", temp}' || echo 'No thermal sensors'")
    cpu_freq = await run_shell("lscpu | grep 'MHz' | head -3 2>/dev/null || echo 'N/A'")
    gpu_temp = await run_shell("nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo 'No NVIDIA GPU'")
    hdd_temp = ""
    # Try to get HDD temp
    for disk in ['sda', 'nvme0', 'mmcblk0']:
        t = await run_shell(f"hddtemp /dev/{disk} 2>/dev/null | awk -F: '{{print \"  • \"$NF}}' || smartctl -A /dev/{disk} 2>/dev/null | grep Temp | awk '{{print \"  • \"$10\"°C\"}}' || echo ''")
        if t.strip():
            hdd_temp += f"\n*Disk {disk}:* {t.strip()}"

    text = (
        "🌡️ *Temperatures*\n"
        "━━━━━━━━━━━━━\n\n"
        f"*CPU Zones:*\n{escape_md(temps.strip())}\n\n"
        f"*CPU Frequency:*\n```\n{cpu_freq.strip()}```"
    )
    if gpu_temp.strip() and 'No NVIDIA' not in gpu_temp:
        text += f"\n*GPU Temp:* {gpu_temp.strip()}°C"
    if hdd_temp:
        text += f"\n{hdd_temp}"

    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def services_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show running system services."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    output = await run_shell("systemctl list-units --type=service --state=running --no-legend 2>/dev/null | awk '{print \"  • \"$1}' | head -30 || echo 'systemctl not available'")
    count = await run_shell("systemctl list-units --type=service --state=running --no-legend 2>/dev/null | wc -l || echo '0'")

    text = (
        f"⚙️ *Running Services* (Total: {count.strip()})\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"```\n{output.strip()}```"
    )
    await update.effective_message.reply_text(text[:4000], parse_mode="Markdown")

async def apps_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show open windows/applications."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    windows = await run_shell("wmctrl -l 2>/dev/null | awk '{print \"  • \"$NF}' | head -20 || echo 'wmctrl not installed'")
    processes = await run_shell("ps aux --sort=-%cpu | head -10 | awk 'NR>1 {print \"  • (\"$3\"% cpu) \"$11}'")

    if 'wmctrl not installed' in windows:
        windows = await run_shell("DISPLAY=:0 xdotool getactivewindow getwindowname 2>/dev/null || echo 'No active window info'")
        windows = f"  • Active window: {windows.strip()}"

    text = (
        "🪟 *Open Windows & Top Apps*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Windows:*\n{escape_md(windows.strip())}\n\n"
        f"*Top CPU Processes:*\n{escape_md(processes.strip())}"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def mouse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Control mouse: move to position or show location."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    if not context.args:
        # Show current mouse position
        pos = await run_shell("DISPLAY=:0 xdotool getmouselocation 2>/dev/null | awk '{print \"X: \"$1\", Y: \"$2}' || echo 'N/A'")
        await update.effective_message.reply_text(
            f"🖱️ *Mouse Position*\n```\n{escape_md(pos.strip())}```\n\n"
            "Usage: `/mouse <x> <y>`\n"
            "Example: `/mouse 500 400`",
            parse_mode="Markdown"
        )
        return

    if len(context.args) >= 2:
        try:
            x, y = int(context.args[0]), int(context.args[1])
            subprocess.run(["xdotool", "mousemove", str(x), str(y)], timeout=5, env={"DISPLAY": ":0"})
            await update.effective_message.reply_text(f"🖱️ Mouse moved to ({x}, {y})")
        except ValueError:
            await update.effective_message.reply_text("❌ Invalid coordinates. Use: `/mouse <x> <y>`", parse_mode="Markdown")
        except Exception as e:
            await update.effective_message.reply_text(f"❌ Error: {e}")

async def click_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simulate mouse click."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    button = context.args[0].lower() if context.args else "left"

    btn_map = {
        "left": "1",
        "middle": "2",
        "right": "3",
        "double": "1 1",
    }

    btn = btn_map.get(button, "1")
    try:
        subprocess.run(["xdotool", "click"] + btn.split(), timeout=5, env={"DISPLAY": ":0"})
        await update.effective_message.reply_text(f"🖱️ Clicked: `{button}`", parse_mode="Markdown")
    except Exception as e:
        await update.effective_message.reply_text(f"❌ Click failed: {e}")

async def scroll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scroll mouse wheel."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    direction = context.args[0].lower() if context.args else "down"
    amount = int(context.args[1]) if len(context.args) > 1 else 5

    if direction in ["up", "down"]:
        try:
            clicks = amount if direction == "down" else -amount
            subprocess.run(["xdotool", "click", "--repeat", str(abs(amount)), "--delay", "100",
                          "5" if direction == "down" else "4"], timeout=10, env={"DISPLAY": ":0"})
            await update.effective_message.reply_text(f"📜 Scrolled {direction} {amount} steps")
        except Exception as e:
            await update.effective_message.reply_text(f"❌ Scroll failed: {e}")
    else:
        await update.effective_message.reply_text("Usage: `/scroll <up|down> [amount]`\nExample: `/scroll down 10`", parse_mode="Markdown")

async def sound_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Control system volume."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    action = context.args[0].lower() if context.args else "get"

    if action == "get" or action == "status":
        vol = await run_shell("amixer get Master 2>/dev/null | grep -o '[0-9]*%' | head -1 || pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | grep -o '[0-9]*%' | head -1 || echo 'N/A'")
        mute = await run_shell(r"amixer get Master 2>/dev/null | grep -o '\[on\]\|\[off\]' | head -1 || echo ''")
        status = "🔇 Muted" if 'off' in mute else "🔊 Active"
        await update.effective_message.reply_text(
            f"🔊 *Volume Control*\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"*Level:* {vol.strip()}\n"
            f"*Status:* {status}\n\n"
            "*Usage:* `/sound <action> [value]`\n"
            "Actions: `up`, `down`, `set 50`, `mute`, `unmute`, `toggle`",
            parse_mode="Markdown"
        )
    elif action == "up":
        await run_shell("amixer set Master 5%+ 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ +5%")
        await update.effective_message.reply_text("🔊 Volume increased")
    elif action == "down":
        await run_shell("amixer set Master 5%- 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ -5%")
        await update.effective_message.reply_text("🔉 Volume decreased")
    elif action == "set" and len(context.args) > 1:
        value = context.args[1]
        await run_shell(f"amixer set Master {value}% 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ {value}%")
        await update.effective_message.reply_text(f"🔊 Volume set to {value}%")
    elif action == "mute":
        await run_shell("amixer set Master mute 2>/dev/null || pactl set-sink-mute @DEFAULT_SINK@ 1")
        await update.effective_message.reply_text("🔇 Muted")
    elif action == "unmute":
        await run_shell("amixer set Master unmute 2>/dev/null || pactl set-sink-mute @DEFAULT_SINK@ 0")
        await update.effective_message.reply_text("🔊 Unmuted")
    elif action == "toggle":
        await run_shell("amixer set Master toggle 2>/dev/null || pactl set-sink-mute @DEFAULT_SINK@ toggle")
        await update.effective_message.reply_text("🔊 Toggled mute")
    else:
        await update.effective_message.reply_text(
            "Usage: `/sound <action>`\n"
            "Actions: `get`, `up`, `down`, `set 50`, `mute`, `unmute`, `toggle`",
            parse_mode="Markdown"
        )

# ============ ADVANCED POWER USER COMMANDS ============

async def open_terminal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open a terminal window on the desktop."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    terminals = ["xfce4-terminal", "gnome-terminal", "lxterminal", "xterm", "konsole"]
    for term in terminals:
        if shutil.which(term):
            subprocess.Popen([term], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await update.effective_message.reply_text(f"💻 Opened `{term}` ✓", parse_mode="Markdown")
            return
    await update.effective_message.reply_text("❌ No terminal found. Install: `sudo apt install xfce4-terminal`", parse_mode="Markdown")

async def open_firefox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open Firefox browser."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    browsers = ["firefox", "chromium", "google-chrome"]
    for b in browsers:
        if shutil.which(b):
            subprocess.Popen([b], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await update.effective_message.reply_text(f"🌍 Opened `{b}` ✓", parse_mode="Markdown")
            return
    await update.effective_message.reply_text("❌ No browser found.")

async def record_screen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start screen recording with ffmpeg."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    if not shutil.which("ffmpeg"):
        await update.effective_message.reply_text("❌ ffmpeg not installed. Run: `sudo apt install ffmpeg`", parse_mode="Markdown")
        return
    # Check if already recording
    running = await run_shell("pgrep -a ffmpeg 2>/dev/null | grep -i screen | head -3 || echo 'none'")
    if "ffmpeg" in running:
        await update.effective_message.reply_text("🎬 Already recording! Tap *⏹️ Stop Record* to stop.", parse_mode="Markdown")
        return
    out_path = f"/home/osboxes/Videos/screen_{int(time.time())}.mp4"
    subprocess.Popen([
        "ffmpeg", "-y", "-f", "x11grab", "-s", "1920x1080", "-i", ":0.0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", out_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(0.5)
    await update.effective_message.reply_text(
        f"🎬 *Recording started!*\n"
        f"📹 Saving to: `{out_path}`\n"
        f"⏹️ Tap *⏹️ Stop Record* to stop.",
        parse_mode="Markdown"
    )

async def stop_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop screen recording."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    await run_shell("pkill -INT ffmpeg 2>/dev/null; sleep 1; echo 'stopped'")
    await update.effective_message.reply_text("⏹️ Recording stopped. Check `/home/osboxes/Videos/` for the file.", parse_mode="Markdown")

async def kill_top_cpu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kill the process using the most CPU."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    # Find the top CPU process (skip first line header)
    info = await run_shell(
        "ps aux --sort=-%cpu | head -2 | tail -1 | awk '{print \"PID: \" $2 \" | CPU: \" $3 \"% | MEM: \" $4 \"% | CMD: \" $11}'"
    )
    killed = await run_shell(
        "ps aux --sort=-%cpu | awk 'NR==2{print $2}' | xargs -r kill -9 2>/dev/null; echo 'killed'"
    )
    await update.effective_message.reply_text(
        f"🔪 *Killed Top CPU Process*\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"`{info.strip()}`\n\n"
        f"✅ Process terminated.",
        parse_mode="Markdown"
    )

async def clear_cache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear RAM cache and free up memory."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    ram = await run_shell("free -h | grep Mem | awk '{print \"Used: \"$3\" Free: \"$4}'")
    await run_shell(
        f"sync; echo {OSBOXES_PASS} | sudo -S sh -c 'echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null; "
        f"sync; echo done"
    )
    ram2 = await run_shell("free -h | grep Mem | awk '{print \"Used: \"$3\" Free: \"$4}'")
    await update.effective_message.reply_text(
        f"🧹 *Cache Cleared!*\n"
        f"━━━━━━━━━━━━━\n"
        f"*Before:* `{escape_md(ram.strip())}`\n"
        f"*After:* `{escape_md(ram2.strip())}`",
        parse_mode="Markdown"
    )

async def fix_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart network services."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    msg = await update.effective_message.reply_text("🔄 Restarting network...")
    await run_shell(
        "systemctl restart NetworkManager 2>/dev/null || "
        "service network-manager restart 2>/dev/null || "
        "nmcli networking off 2>/dev/null; nmcli networking on 2>/dev/null; "
        "echo done"
    )
    ip = await run_shell("hostname -I | awk '{print $1}'")
    await msg.edit_text(
        f"✅ *Network Restarted!*\n"
        f"📡 IP: `{ip.strip()}`",
        parse_mode="Markdown"
    )

async def cpu_temp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show CPU temperature."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    temps = await run_shell("cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{temp=$1/1000; printf \"  • %.1f°C\\n\", temp}' || echo 'No sensors'")
    cpu_freq = await run_shell("lscpu | grep 'MHz' | head -1 | awk '{print $3}'")
    await update.effective_message.reply_text(
        f"🌡️ *CPU Temperature*\n"
        f"━━━━━━━━━━━━━━\n```\n{temps.strip()}```\n\n"
        f"⚡ *Frequency:* {cpu_freq.strip()} MHz",
        parse_mode="Markdown"
    )

async def clipboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get clipboard content from the desktop."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    content = await run_shell("xclip -o -selection clipboard 2>/dev/null || xclip -o 2>/dev/null || echo '(Clipboard empty)'")
    await update.effective_message.reply_text(
        f"📋 *Clipboard Content*\n"
        f"━━━━━━━━━━━━━━\n```\n{content.strip()[:1500]}```",
        parse_mode="Markdown"
    )

async def whos_online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show who is logged into the system."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    users = await run_shell("w -h | awk '{print \"  • \"$1\" from \"$3\" since \"$4}'")
    await update.effective_message.reply_text(
        f"👥 *Logged In Users*\n"
        f"━━━━━━━━━━━━━\n"
        f"{escape_md(users.strip()) if users.strip() else '  • (none)'}",
        parse_mode="Markdown"
    )


# ============ GPG / PGP KEY MANAGEMENT ============

async def gpg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GPG key management — list, generate, export, delete keys."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    if not shutil.which("gpg"):
        await update.effective_message.reply_text("❌ GPG not installed. Run: `sudo apt install gnupg`", parse_mode="Markdown")
        return

    is_callback = update.callback_query is not None

    # Get key count
    key_list = await run_shell("gpg --list-keys --keyid-format LONG 2>/dev/null | grep '^pub' | wc -l")
    try:
        total_keys = int(key_list.strip())
    except ValueError:
        total_keys = 0

    text = (
        "🔑 *GPG Key Manager*\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"🗝️ *Keys in keyring:* `{total_keys}`\n"
        f"\n"
        f"🔹 *List Keys* — view all keys with IDs\n"
        f"🔹 *Generate Pair* — create a new keypair\n"
        f"🔹 *Export Key* — get a public key\n"
        f"🔹 *Delete Key* — remove a key from keyring\n"
    )

    kb = [
        [InlineKeyboardButton("📋 List All Keys", callback_data="gpg_list")],
        [InlineKeyboardButton("➕ Generate New Keypair", callback_data="gpg_gen")],
    ]
    if total_keys > 0:
        kb.append([InlineKeyboardButton("📤 Export Public Key", callback_data="gpg_export")])
        kb.append([InlineKeyboardButton("🗑️ Delete a Key", callback_data="gpg_delete")])
    kb.append([InlineKeyboardButton("❌ Close", callback_data="gpg_close")])

    reply_markup = InlineKeyboardMarkup(kb)
    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def gpg_list_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all GPG keys with details."""
    output = await run_shell("gpg --list-keys --keyid-format LONG 2>/dev/null")
    secret = await run_shell("gpg --list-secret-keys --keyid-format LONG 2>/dev/null | grep '^sec' | awk '{print $2}'")
    if "No public key" in output or not output.strip():
        text = "📋 *GPG Keys*\n━━━━━━━━━━━\n\n🔴 No keys in the keyring.\n\nUse *➕ Generate* to create one!"
    else:
        text = f"📋 *GPG Keys*\n━━━━━━━━━━━\n\n```\n{escape_md(output.strip())}```"
        if secret.strip():
            text += f"\n🔐 *Secret keys:*\n`{escape_md(secret.strip())}`"

    kb = [[InlineKeyboardButton("« Back to GPG Menu", callback_data="gpg_main")]]
    is_callback = update.callback_query is not None
    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def gpg_generate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a new GPG keypair."""
    # Prompt for name/email via inline
    text = (
        "➕ *Generate New GPG Keypair*\n\n"
        "This will create a 4096-bit RSA keypair.\n"
        "\n"
        "_No passphrase will be set (for automation)._\n"
        "\n"
        "Continue?"
    )
    kb = [
        [InlineKeyboardButton("✅ Yes, generate with defaults", callback_data="gpg_gen_do")],
        [InlineKeyboardButton("❌ Cancel", callback_data="gpg_main")],
    ]
    is_callback = update.callback_query is not None
    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def gpg_gen_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute GPG key generation."""
    await update.callback_query.edit_message_text("🔑 Generating 4096-bit RSA keypair... (this may take a minute)")

    # Create batch config for unattended key generation
    batch_config = f"""Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: guid_erbot Auto Key
Name-Email: admin@guid-erbot.local
Expire-Date: 2y
%no-protection
%commit
"""
    with open("/tmp/gpg_batch.conf", "w") as f:
        f.write(batch_config)

    result = await run_shell("gpg --batch --gen-key /tmp/gpg_batch.conf 2>&1")
    os.remove("/tmp/gpg_batch.conf")

    # Get the new key ID
    new_key = await run_shell("gpg --list-keys --keyid-format LONG 2>/dev/null | grep '^pub' | tail -1 | awk '{print $2}' | cut -d'/' -f2")
    key_id = new_key.strip()[:16]

    if key_id:
        text = (
            "✅ *Keypair Generated!* 🎉\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 *Key ID:* `{key_id}`\n"
            f"🔐 *Type:* RSA 4096-bit\n"
            f"📅 *Expires:* 2 years\n"
            f"👤 *Name:* guid_erbot Auto Key\n"
            f"📧 *Email:* admin@guid-erbot.local\n\n"
            f"📤 Use *📤 Export* to copy the public key!"
        )
    else:
        text = f"❌ Key generation may have failed. Output:\n```\n{escape_md(result[-500:])}```"

    kb = [[InlineKeyboardButton("« Back to GPG Menu", callback_data="gpg_main")]]
    await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def gpg_export_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of keys to export."""
    keys_output = await run_shell("gpg --list-keys --keyid-format LONG 2>/dev/null | grep -E '^pub|^uid'")
    if "No public key" in keys_output or not keys_output.strip():
        kb = [[InlineKeyboardButton("« Back", callback_data="gpg_main")]]
        await update.callback_query.edit_message_text(
            "📤 *Export Key*\n\n🔴 No keys to export.",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # Parse key IDs and UIDs
    lines = keys_output.strip().split("\n")
    buttons = []
    current_key = None
    for line in lines:
        if line.startswith("pub "):
            parts = line.split()
            if len(parts) >= 2:
                key_full = parts[1]
                key_id = key_full.split("/")[-1][:16]
                current_key = key_id
        elif line.startswith("uid ") and current_key:
            uid = line[4:].strip()[:30]
            buttons.append([InlineKeyboardButton(f"📤 {key_id} — {uid}", callback_data=f"gpg_export_do_{key_id}")])

    buttons.append([InlineKeyboardButton("« Back", callback_data="gpg_main")])
    text = "📤 *Export Public Key*\n\nTap a key to export:"
    await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))


async def gpg_export_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export a specific public key."""
    key_id = update.callback_query.data[14:]  # Remove "gpg_export_do_"
    pubkey = await run_shell(f"gpg --armor --export {key_id} 2>/dev/null || echo 'Key not found'")

    # Send as a code block for copying
    if len(pubkey) > 3900:
        # Too long for message, send as file
        with open("/tmp/gpg_export.asc", "w") as f:
            f.write(pubkey)
        with open("/tmp/gpg_export.asc", "rb") as f:
            await update.callback_query.edit_message_text(
                f"📤 *Exported Key* `{key_id}`\n\n📎 Key is too long — sent as file below.",
                parse_mode="Markdown"
            )
            await context.bot.send_document(
                chat_id=update.callback_query.message.chat_id,
                document=f, filename=f"{key_id}.asc",
                caption=f"🔑 Public key: `{key_id}`", parse_mode="Markdown"
            )
        os.remove("/tmp/gpg_export.asc")
    else:
        text = f"📤 *Exported Key:* `{key_id}`\n```\n{pubkey}```"
        kb = [[InlineKeyboardButton("« Back", callback_data="gpg_main")]]
        await update.callback_query.edit_message_text(text[:4000], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def gpg_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of keys to delete."""
    keys_output = await run_shell("gpg --list-keys --keyid-format LONG 2>/dev/null | grep -E '^pub|^uid'")
    if "No public key" in keys_output or not keys_output.strip():
        kb = [[InlineKeyboardButton("« Back", callback_data="gpg_main")]]
        await update.callback_query.edit_message_text(
            "🗑️ *Delete Key*\n\n🔴 No keys to delete.",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    lines = keys_output.strip().split("\n")
    buttons = []
    current_key = None
    for line in lines:
        if line.startswith("pub "):
            parts = line.split()
            if len(parts) >= 2:
                key_full = parts[1]
                key_id = key_full.split("/")[-1][:16]
                current_key = key_id
        elif line.startswith("uid ") and current_key:
            uid = line[4:].strip()[:30]
            buttons.append([InlineKeyboardButton(f"🗑️ {key_id} — {uid}", callback_data=f"gpg_del_{key_id}")])

    buttons.append([InlineKeyboardButton("« Back", callback_data="gpg_main")])
    text = "🗑️ *Delete a Key*\n\n⚠️ Tap a key to delete it (with confirmation):"
    await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))


async def gpg_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm deletion of a key."""
    key_id = update.callback_query.data[8:]  # Remove "gpg_del_"
    text = (
        f"⚠️ *Are you sure?*\n\n"
        f"This will permanently delete key `{key_id}`\n"
        f"from the GPG keyring.\n\n"
        f"*This cannot be undone unless you have a backup!*"
    )
    kb = [
        [InlineKeyboardButton("✅ Yes, delete it", callback_data=f"gpg_del_conf_{key_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="gpg_main")],
    ]
    await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def gpg_delete_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute key deletion."""
    key_id = update.callback_query.data[13:]  # Remove "gpg_del_conf_"
    await update.callback_query.edit_message_text(f"🗑️ Deleting key `{key_id}`...", parse_mode="Markdown")

    # Delete secret key first if exists, then public key
    result = await run_shell(
        f"gpg --batch --yes --delete-secret-keys {key_id} 2>/dev/null; "
        f"gpg --batch --yes --delete-key {key_id} 2>/dev/null; "
        f"echo 'done'"
    )

    # Check if deleted
    check = await run_shell(f"gpg --list-keys --keyid-format LONG 2>/dev/null | grep {key_id} || echo 'deleted'")
    if "deleted" in check:
        text = f"✅ Key `{key_id}` has been deleted."
    else:
        text = f"⚠️ Key `{key_id}` may still exist. Try manual deletion."

    kb = [[InlineKeyboardButton("« Back to GPG Menu", callback_data="gpg_main")]]
    await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


# ============ SOCKS5 PROXY COMMAND ============

async def socks5_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle SOCKS5 proxy via microsocks (lightweight)."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    is_callback = update.callback_query is not None
    microsocks_path = shutil.which("microsocks")
    if not microsocks_path:
        text = (
            "❌ *microsocks not installed.*\n\n"
            "Install: `sudo apt install microsocks`\n\n"
            "_A lightweight SOCKS5 proxy that runs with minimal overhead._"
        )
        kb = [[InlineKeyboardButton("« Back to Menu", callback_data="menu_main")]]
        if is_callback:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    # Check if already running
    proxy_running = await run_shell("pgrep -x microsocks 2>/dev/null || echo 'stopped'")
    is_running = "microsocks" in proxy_running.lower()

    # Get port info
    port_check = await run_shell("ss -tlnp 2>/dev/null | grep 1080 || echo 'Not listening'")

    if is_running:
        # Show status + stop/restart buttons
        kb = [
            [InlineKeyboardButton("⏹️ Stop Proxy", callback_data="socks5_stop")],
            [InlineKeyboardButton("🔄 Restart", callback_data="socks5_restart")],
            [InlineKeyboardButton("❌ Close", callback_data="menu_main")],
        ]
        vm_hostname = await run_shell("hostname -I 2>/dev/null | awk '{print $1}'")
        wan_ip = await run_shell("curl -s ifconfig.me 2>/dev/null || echo '?'")
        text = (
            f"🧦 *SOCKS5 Proxy — RUNNING* ✅\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📡 *Status:* Active\n"
            f"🔌 *Port:* `1080`\n"
            f"🌐 *Public IP:* `{wan_ip.strip()}`\n"
            f"👤 *Auth:* `{OSBOXES_USER}` / `{OSBOXES_PASS}`\n"
            f"\n"
            f"```\nHost: {vm_hostname.strip()}\nPort: 1080\nUser: {OSBOXES_USER}\nPass: {OSBOXES_PASS}\n```\n"
            f"```\nHost: {vm_hostname.strip()}\nPort: 1080\nUser: {OSBOXES_USER}\nPass: {OSBOXES_PASS}\n```\n"
            f"\n💡 Tap ⏹️ *Stop Proxy* to turn it off."
        )
    else:
        # Show start button
        kb = [
            [InlineKeyboardButton("▶️ Start SOCKS5 Proxy", callback_data="socks5_restart")],
            [InlineKeyboardButton("❌ Close", callback_data="menu_main")],
        ]
        text = (
            f"🧦 *SOCKS5 Proxy — STOPPED* ⏹️\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📡 *Status:* Inactive\n"
            f"🔌 *Port:* `1080`\n"
            f"\n"
            f"Tap ▶️ *Start* to launch a lightweight SOCKS5 proxy\n"
            f"using `microsocks`. No VPN needed!\n"
            f"\n"
            f"🔐 *Auth:* `{OSBOXES_USER}` / `{OSBOXES_PASS}`\n"
            f"⚡ *Fast, low-overhead, single-purpose.*"
        )

    reply_markup = InlineKeyboardMarkup(kb)
    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


# ============ VPN COMMAND ============

async def vpn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle VPN connection — WireGuard or OpenVPN."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return

    is_callback = update.callback_query is not None

    # Detect available VPN configs
    wg_conf = list(Path("/etc/wireguard").glob("*.conf")) if Path("/etc/wireguard").exists() else []
    ovpn_conf = list(Path("/etc/openvpn/client").glob("*.conf")) if Path("/etc/openvpn/client").exists() else []
    ovpn_ovpn = list(Path("/etc/openvpn/client").glob("*.ovpn")) if Path("/etc/openvpn/client").exists() else []
    if not ovpn_conf and not ovpn_ovpn:
        ovpn_conf = list(Path("/etc/openvpn").glob("*.conf")) if Path("/etc/openvpn").exists() else []
        ovpn_ovpn = list(Path("/etc/openvpn").glob("*.ovpn")) if Path("/etc/openvpn").exists() else []

    # Check if any VPN tunnel is active
    tun_check = await run_shell("ip link show tun0 2>/dev/null | grep -q 'UP' && echo 'up' || echo 'down'")
    vpn_active = "up" in tun_check

    # Check for running VPN processes
    wg_running = "up" in await run_shell("wg show 2>/dev/null | grep -q interface && echo 'up' || echo 'down'")

    total_confs = len(wg_conf) + len(ovpn_conf)

    # If VPN is active, show kill/stop button
    if vpn_active:
        kb = [
            [InlineKeyboardButton("⏹️ Disconnect VPN", callback_data="vpn_stop")],
            [InlineKeyboardButton("🔄 Reconnect", callback_data="vpn_restart")],
        ]
        wan_ip = await run_shell("curl -s ifconfig.me 2>/dev/null || echo '?'")
        text = (
            f"🔐 *VPN Status*\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"✅ *VPN is CONNECTED*\n"
            f"🌐 *Public IP:* `{wan_ip.strip()}`\n"
            f"\n"
        )
        if wg_running:
            wg_info = await run_shell("wg show 2>/dev/null | head -10")
            text += f"*WireGuard:*\n```\n{escape_md(wg_info.strip())}```\n\n"
        if total_confs > 0:
            text += f"📁 *Configs available:* {total_confs}"
        text += "\n\n💡 Tap *⏹️ Disconnect* to stop the VPN."

        reply_markup = InlineKeyboardMarkup(kb)
        if is_callback:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
        return

    # VPN is NOT active — check for configs to connect
    if total_confs > 0:
        # Build list of configs to tap
        buttons = []
        row = []
        for i, conf in enumerate(wg_conf + ovpn_conf + ovpn_ovpn):
            name = conf.stem[:12]
            row.append(InlineKeyboardButton(f"▶️ {name}", callback_data=f"vpn_start_{conf}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        text = (
            "🔐 *VPN Disconnected*\n"
            f"━━━━━━━━━━━━━━━━\n\n"
            f"📁 *Available configs:*\n"
        )
        for conf in wg_conf:
            text += f"  • 🔵 `{conf.name}` (WireGuard)\n"
        for conf in ovpn_conf + ovpn_ovpn:
            text += f"  • 🟠 `{conf.name}` (OpenVPN)\n"
        text += "\n👇 Tap a config to connect:"

        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="vpn_cancel")])
        kb = InlineKeyboardMarkup(buttons)
        if is_callback:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        else:
            await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    # No configs found — show setup guide
    text = (
        "🔐 *VPN — No Configs Found*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "No WireGuard or OpenVPN configs detected.\n\n"
        "*To get started:*\n\n"
        "📥 *WireGuard:*\n"
        "1. Get a .conf file from your VPN provider\n"
        "2. Upload it as: `/etc/wireguard/wg0.conf`\n"
        "3. Run: `sudo wg-quick up wg0`\n\n"
        "📥 *OpenVPN:*\n"
        "1. Get a .ovpn file from your VPN provider\n"
        "2. Upload it as: `/etc/openvpn/client/config.ovpn`\n"
        "3. Run: `sudo openvpn /etc/openvpn/client/config.ovpn`\n\n"
        "💡 You can upload config files via the folder\n"
        "using the /upload command or SCP."
    )
    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(text, parse_mode="Markdown")


# ============ ERROR HANDLER ============

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")

# ============ MAIN ============

def main():
    """Start the bot."""
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers - Sorted by category
    # 💻 System
    app.add_handler(CommandHandler("shell", shell_command))
    app.add_handler(CommandHandler("sysinfo", sysinfo_command))
    app.add_handler(CommandHandler("ps", ps_command))
    app.add_handler(CommandHandler("uptime", uptime_command))
    app.add_handler(CommandHandler("services", services_command))
    app.add_handler(CommandHandler("apps", apps_command))
    app.add_handler(CommandHandler("temp", temp_command))
    # 📊 Resources
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("disk", disk_command))
    app.add_handler(CommandHandler("ip", ip_command))
    app.add_handler(CommandHandler("wifi", wifi_command))
    # 🖥️ Desktop
    app.add_handler(CommandHandler("screenshot", screenshot_command))
    app.add_handler(CommandHandler("lock", lock_command))
    app.add_handler(CommandHandler("unlock", unlock_command))
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(CommandHandler("notify", notify_command))
    app.add_handler(CommandHandler("type", type_command))
    app.add_handler(CommandHandler("key", key_command))
    # 🖱️ Mouse
    app.add_handler(CommandHandler("mouse", mouse_command))
    app.add_handler(CommandHandler("click", click_command))
    app.add_handler(CommandHandler("scroll", scroll_command))
    # 🔊 Sound
    app.add_handler(CommandHandler("sound", sound_command))
    # 📁 Files
    app.add_handler(CommandHandler("upload", upload_command))
    # 🌐 Remote & Web
    app.add_handler(CommandHandler("web", web_command))
    app.add_handler(CommandHandler("vnc", vnc_command))
    app.add_handler(CommandHandler("webvnc", webvnc_command))
    app.add_handler(CommandHandler("rustdesk", rustdesk_command))

    # 📡 Extra Commands (direct slash commands)
    app.add_handler(CommandHandler("speedtest", speed_test))
    app.add_handler(CommandHandler("docker", docker_status))
    app.add_handler(CommandHandler("packages", packages_command))
    app.add_handler(CommandHandler("git", git_status))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("calc", calculator_command))
    app.add_handler(CommandHandler("calendar", calendar_command))
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("emptytrash", empty_trash))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("cleartemp", clear_temp))
    # 🎵 Media & Fun
    app.add_handler(CommandHandler("music", open_music))
    app.add_handler(CommandHandler("media", open_media))
    app.add_handler(CommandHandler("youtube", open_youtube))
    app.add_handler(CommandHandler("steam", open_steam))
    app.add_handler(CommandHandler("dice", roll_dice))
    app.add_handler(CommandHandler("coin", flip_coin))
    app.add_handler(CommandHandler("fortune", fortune_cookie))
    # ⚡ Control
    app.add_handler(CommandHandler("reboot", reboot_command))
    app.add_handler(CommandHandler("shutdown", shutdown_command))
    app.add_handler(CommandHandler("cmdhistory", cmdhistory_command))
    app.add_handler(CommandHandler("webpanel", webpanel_command))
    app.add_handler(CommandHandler("whoami", whoami_command))
    # 📖 Help
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("phone", phone_command))
    app.add_handler(CommandHandler("vpn", vpn_command))
    app.add_handler(CommandHandler("socks5", socks5_command))
    app.add_handler(CommandHandler("gpg", gpg_command))

    # Button text handler (for reply keyboard taps below chat)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_text_handler))

    # Contact handler (for phone number sharing)
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))

    # Download handler (for file uploads from phone)
    app.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO,
        download_handler
    ))

    # Callback handler for inline keyboards (menu system)
    app.add_handler(CallbackQueryHandler(build_menu))

    # Error handler
    app.add_error_handler(error_handler)

    logger.info("🤖 guid_erbot starting...")
    print("🤖 guid_erbot is running! Press Ctrl+C to stop.")
    print(f"📱 Bot: https://t.me/guid_erbot")
    print(f"🔐 Authorized User IDs: {ADMIN_IDS}")

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
