#!/usr/bin/env python3
"""
extra_commands.py - 60+ extra command handlers for guid_erbot
Expands the bot with fun, utility, and developer tools.
"""

import asyncio
import json
import logging
import os
import platform
import random
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils import is_authorized, run_shell, escape_md, reply_long, get_machine_config, get_machine_data_dir, get_machine_download_dir

logger = logging.getLogger(__name__)

# ============ SYSTEM ============

async def packages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List installed packages count and recent ones."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    total = await run_shell("dpkg -l 2>/dev/null | wc -l || echo 'N/A'")
    recent = await run_shell("grep ' install ' /var/log/dpkg.log 2>/dev/null | tail -10 | awk '{print $4}' || echo 'No log'")
    upgradable = await run_shell("apt list --upgradable 2>/dev/null | grep -c upgradable || echo '0'")
    text = (
        "📦 *Package Manager*\\n━━━━━━━━━━━━━━\\n\\n"
        f"*Total:* {total.strip()}\\n"
        f"*Upgradable:* {upgradable.strip()}\\n\\n"
        f"*Recently installed:*\\n```\\n{recent.strip()[:1500]}```"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def update_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run apt update to refresh package lists."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    msg = await update.effective_message.reply_text("🔄 Updating package lists...")
    output = await run_shell("apt update 2>&1 | tail -5", timeout=60)
    await msg.edit_text(
        f"🔄 *Update Complete*\\n```\\n{escape_md(output.strip()[:1500])}```\\n\\n"
        f"ℹ️ Run `/shell apt upgrade -y` to upgrade packages.",
        parse_mode="Markdown"
    )

async def gpu_temp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show GPU temperature and info."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    gpu_info = await run_shell("lspci | grep -i 'vga\\|3d' | head -1 | cut -d: -f3-")
    nvidia = await run_shell("nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo 'No NVIDIA GPU'")
    amd = await run_shell("cat /sys/class/drm/card*/device/hwmon/hwmon*/temp1_input 2>/dev/null | awk '{temp=$1/1000; printf \"  • AMD GPU: %.1f°C\\n\", temp}' || echo ''")
    text = (
        "🌡️ *GPU Information*\\n━━━━━━━━━━━━━━\\n\\n"
        f"*GPU:* {gpu_info.strip()}\\n\\n"
        f"*NVIDIA:*\\n```\\n{nvidia.strip()}```\\n{amd.strip()}"
    )
    await update.effective_message.reply_text(text.strip(), parse_mode="Markdown")

# ============ NETWORK ============

async def speed_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run a quick network speed test."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    msg = await update.effective_message.reply_text("📡 Running speed test... (this may take a moment)")
    if shutil.which("speedtest-cli"):
        result = await run_shell("speedtest-cli --simple 2>/dev/null || speedtest-cli 2>/dev/null | head -20", timeout=60)
    else:
        # Fallback: test ping and download speed with curl
        ping = await run_shell("ping -c 3 8.8.8.8 2>/dev/null | tail -1 | awk '{print $4}' || echo 'Unreachable'")
        download = await run_shell("curl -s -o /dev/null -w '%{speed_download}' https://speedtest.tele2.net/1MB.zip 2>/dev/null; echo ''")
        result = f"Ping: {ping.strip()}\\nDownload: {download.strip()} B/s"
    await msg.edit_text(
        f"📡 *Speed Test Results*\\n```\\n{escape_md(result.strip()[:1500])}```",
        parse_mode="Markdown"
    )

# ============ MEDIA & ENTERTAINMENT ============

async def open_app(app_name, app_cmd):
    """Helper to open an application."""
    if shutil.which(app_cmd):
        subprocess.Popen([app_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    return False

async def open_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    apps = [("rhythmbox", "rhythmbox"), ("audacious", "audacious"), ("vlc", "vlc")]
    for name, cmd in apps:
        if await open_app(name, cmd):
            await update.effective_message.reply_text(f"🎵 Opened `{name}` ✓", parse_mode="Markdown")
            return
    # Fallback: open music folder
    cfg = get_machine_config()
    subprocess.Popen(["xdg-open", f"{cfg['home']}/Music"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await update.effective_message.reply_text("🎵 Opened Music folder", parse_mode="Markdown")

async def open_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    if await open_app("VLC", "vlc"): 
        await update.effective_message.reply_text("🎬 Opened VLC media player ✓", parse_mode="Markdown")
        return
    cfg = get_machine_config()
    subprocess.Popen(["xdg-open", f"{cfg['home']}/Videos"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await update.effective_message.reply_text("🎬 Opened Videos folder", parse_mode="Markdown")

async def open_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    apps = [("Eye of GNOME", "eog"), ("GIMP", "gimp"), ("shotwell", "shotwell")]
    for name, cmd in apps:
        if await open_app(name, cmd):
            await update.effective_message.reply_text(f"🖼️ Opened `{name}` ✓", parse_mode="Markdown")
            return
    cfg = get_machine_config()
    subprocess.Popen(["xdg-open", f"{cfg['home']}/Pictures"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await update.effective_message.reply_text("🖼️ Opened Pictures folder", parse_mode="Markdown")

async def open_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    browsers = ["firefox", "chromium", "google-chrome", "xdg-open"]
    for b in browsers:
        if shutil.which(b):
            subprocess.Popen([b, "https://youtube.com"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await update.effective_message.reply_text("📺 Opened YouTube in browser ✓", parse_mode="Markdown")
            return
    await update.effective_message.reply_text("❌ No browser found.")

async def open_steam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    if shutil.which("steam"):
        subprocess.Popen(["steam"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await update.effective_message.reply_text("🎮 Opening Steam...", parse_mode="Markdown")
    else:
        await update.effective_message.reply_text("❌ Steam not installed. Run: `sudo apt install steam`", parse_mode="Markdown")

async def podcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    apps = [("Spotify", "spotify"), ("rhythmbox", "rhythmbox"), ("vlc", "vlc")]
    for name, cmd in apps:
        if await open_app(name, cmd):
            await update.effective_message.reply_text(f"🎧 Opened `{name}` ✓", parse_mode="Markdown")
            return
    await update.effective_message.reply_text("🎧 Open Spotify or install: `sudo snap install spotify`", parse_mode="Markdown")

# ============ FILES & FOLDERS ============

async def open_folder(folder_path, label, emoji):
    """Helper to open a folder in file manager."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    path = Path(folder_path).expanduser()
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await update.effective_message.reply_text(f"{emoji} Opened {label} folder ✓", parse_mode="Markdown")

async def open_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_machine_config()
    await open_folder(f"{cfg['home']}", "Home", "📁")

async def open_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_machine_config()
    await open_folder(f"{cfg['home']}/Downloads", "Downloads", "📂")

async def open_documents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_machine_config()
    await open_folder(f"{cfg['home']}/Documents", "Documents", "📄")

async def open_screenshots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_machine_config()
    await open_folder(f"{cfg['home']}/Pictures", "Screenshots", "🖼️")

async def open_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_machine_config()
    await open_folder(f"{cfg['home']}/Videos", "Videos", "🎬")

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a quick backup of important configs."""
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    msg = await update.effective_message.reply_text("💾 Creating backup...")
    cfg = get_machine_config()
    backup_dir = Path(f"{cfg['backup_dir']}/backup_{int(time.time())}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    home = cfg['home']
    await run_shell(f"cp -r {home}/.ssh {backup_dir}/ 2>/dev/null; "
                    f"cp -r {home}/.config {backup_dir}/ 2>/dev/null; "
                    f"cp {home}/.bashrc {backup_dir}/ 2>/dev/null; "
                    f"echo done")
    size = await run_shell(f"du -sh {backup_dir} | awk '{{print \\$1}}'")
    await msg.edit_text(
        f"💾 *Backup Created!*\\n📁 `{backup_dir}`\\n📦 Size: {size.strip()}",
        parse_mode="Markdown"
    )

async def empty_trash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    size = await run_shell("du -sh ~/.local/share/Trash 2>/dev/null | awk '{print $1}' || echo '0B'")
    await run_shell("rm -rf ~/.local/share/Trash/* 2>/dev/null; rm -rf ~/.local/share/Trash/.Trash-* 2>/dev/null; echo done")
    await update.effective_message.reply_text(f"🗑️ *Trash emptied!* (was {size.strip()})", parse_mode="Markdown")

# ============ NETWORK & REMOTE ============

async def share_folder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    ip = await run_shell("hostname -I 2>/dev/null | awk '{print $1}'")
    user = "osboxes"
    text = (
        "🖧 *Share Files via Network*\\n━━━━━━━━━━━━━━━\\n\\n"
        f"*From another computer:*\\n"
        f"```\\nsmb:\\\\\\\\{ip.strip()}\\\\shared\\nssh://{user}@{ip.strip()}/home/{user}```\\n\\n"
        f"*Or run:*\\n"
        "```\\npython3 -m http.server 8000```\\n"
        f"Then visit: `http://{ip.strip()}:8000`\\n\\n"
        f"*Install SMB:* `sudo apt install samba`"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def restart_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    msg = await update.effective_message.reply_text("🔄 Restarting network services...")
    await run_shell("systemctl restart NetworkManager 2>/dev/null || "
                    "service network-manager restart 2>/dev/null || "
                    "nmcli networking off 2>/dev/null; nmcli networking on 2>/dev/null; echo done")
    ip = await run_shell("hostname -I | awk '{print $1}'")
    await msg.edit_text(f"✅ *Network Restarted!*\\n📡 IP: `{ip.strip()}`", parse_mode="Markdown")

async def firewall_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    ufw = await run_shell("ufw status 2>/dev/null || echo 'UFW not installed'")
    iptables = await run_shell("iptables -L -n --line-numbers 2>/dev/null | head -30 || echo 'No iptables'")
    text = (
        "🛡️ *Firewall Status*\\n━━━━━━━━━━━━━\\n\\n"
        f"*UFW:*\\n```\\n{ufw.strip()[:500]}```\\n\\n"
        f"*IPTables (top 30):*\\n```\\n{iptables.strip()[:1500]}```"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def ssh_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    keys = await run_shell("ls -la ~/.ssh/ 2>/dev/null | grep -E 'id_|authorized|config' || echo 'No SSH keys found'")
    pub = await run_shell("cat ~/.ssh/id_*.pub 2>/dev/null || echo 'No public key'")
    text = (
        "🔐 *SSH Keys*\\n━━━━━━━━━━\\n\\n"
        f"*Key files:*\\n```\\n{keys.strip()[:1000]}```\\n\\n"
        f"*Public key:*\\n```\\n{pub.strip()[:1000]}```"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def secure_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "🧹 *Secure Delete*\\n━━━━━━━━━━━\\n\\n"
            "Permanently shred a file (cannot be recovered).\\n\\n"
            "Usage: `/shred <filepath>`\\n"
            "Example: `/shred ~/secret.txt`",
            parse_mode="Markdown"
        )
        return
    path = " ".join(context.args)
    if shutil.which("shred"):
        await run_shell(f"shred -vuz {path} 2>&1 || echo 'Failed'", timeout=30)
        await update.effective_message.reply_text(f"🧹 *Securely deleted:* `{escape_md(path)}`", parse_mode="Markdown")
    else:
        await run_shell(f"rm -rf {path} 2>/dev/null; echo done")
        await update.effective_message.reply_text(f"🧹 *Deleted:* `{escape_md(path)}` (install `shred` for secure deletion)", parse_mode="Markdown")

async def port_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    listening = await run_shell("ss -tlnp 2>/dev/null | tail -20 || netstat -tlnp 2>/dev/null | tail -20 || echo 'N/A'")
    text = (
        "🔍 *Open Ports (Listening)*\\n━━━━━━━━━━━━━━━━━\\n```\\n"
        f"{escape_md(listening.strip()[:2000])}```"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def keychain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    gnome = await run_shell("echo osboxes.org | sudo -S secret-tool search --all '' 2>/dev/null | head -20 || echo 'No secret-tool'")
    ssh_agent = await run_shell("ssh-add -l 2>/dev/null || echo 'No SSH keys loaded'")
    text = (
        "🔑 *Keychain & Credentials*\\n━━━━━━━━━━━━━━━━\\n\\n"
        f"*SSH Agent:*\\n```\\n{ssh_agent.strip()[:500]}```\\n\\n"
        f"*GNOME Keyring:*\\n```\\n{gnome.strip()[:1000]}```"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

# ============ DEVELOPER TOOLS ============

async def python_shell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    if not context.args:
        # Just open Python REPL
        if shutil.which("xfce4-terminal"):
            subprocess.Popen(["xfce4-terminal", "-e", "python3"], stdout=subprocess.DEVNULL)
            await update.effective_message.reply_text("🐍 Opened Python REPL ✓", parse_mode="Markdown")
        else:
            ver = await run_shell("python3 --version")
            await update.effective_message.reply_text(
                f"🐍 *Python*\\n{ver.strip()}\\n\\n"
                f"Usage: `/python <code>`\\n"
                f"Example: `/python print(\\\"hi\\\")`",
                parse_mode="Markdown"
            )
        return
    code = " ".join(context.args)
    result = await run_shell(f"python3 -c '{code}' 2>&1 || echo 'Error'", timeout=10)
    await update.effective_message.reply_text(
        f"🐍 *Python Result*\\n`$ {escape_md(code)}`\\n```\\n{escape_md(result.strip()[:1500])}```",
        parse_mode="Markdown"
    )

async def docker_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    if not shutil.which("docker"):
        await update.effective_message.reply_text("❌ Docker not installed. Run: `sudo apt install docker.io`", parse_mode="Markdown")
        return
    info = await run_shell("docker info --format '{{.Containers}} containers | {{.Images}} images' 2>/dev/null || echo 'N/A'")
    running = await run_shell("docker ps --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}' 2>/dev/null | head -20 || echo 'No running containers'")
    text = (
        "🐳 *Docker Status*\\n━━━━━━━━━━━\\n\\n"
        f"*Info:* {info.strip()}\\n\\n"
        f"*Running containers:*\\n```\\n{running.strip()[:1500]}```"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def open_vscode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    apps = [("code", "code"), ("codium", "codium"), ("atom", "atom"), ("subl", "subl")]
    for name, cmd in apps:
        if shutil.which(cmd):
            subprocess.Popen([cmd, "."], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await update.effective_message.reply_text(f"📝 Opened `{name}` ✓", parse_mode="Markdown")
            return
    await update.effective_message.reply_text("❌ No code editor found. Install: `sudo snap install code --classic`", parse_mode="Markdown")

async def git_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    if not shutil.which("git"):
        await update.effective_message.reply_text("❌ Git not installed. Run: `sudo apt install git`", parse_mode="Markdown")
        return
    # Check common directories
    cfg = get_machine_config()
    home = cfg['home']
    dirs = [home, f"{home}/guid_erbot", f"{home}/Documents", f"{home}/projects"]
    results = []
    for d in dirs:
        path = Path(d)
        if path.exists():
            git_info = await run_shell(f"cd {d} && git status --short 2>/dev/null | head -10 || echo 'Not a repo'")
            if "Not a repo" not in git_info and "fatal" not in git_info:
                branch = await run_shell(f"cd {d} && git branch --show-current 2>/dev/null")
                results.append(f"📁 `{d}` (`{branch.strip()}`):\\n```\\n{git_info.strip()[:500]}```")
    if results:
        text = "🐙 *Git Status*\\n━━━━━━━━━━\\n\\n" + "\\n\\n".join(results)
    else:
        text = "🐙 *Git Status*\\n━━━━━━━━━━\\n\\nNo git repositories found in common directories."
    await update.effective_message.reply_text(text[:4000], parse_mode="Markdown")

async def build_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    # Detect project type and build
    cfg = get_machine_config()
    home = cfg['home']
    dirs = [home, f"{home}/guid_erbot"]
    built = False
    for d in dirs:
        path = Path(d)
        if (path / "Makefile").exists():
            result = await run_shell(f"cd {d} && make 2>&1 | tail -10", timeout=60)
            await update.effective_message.reply_text(f"🛠️ *Build Output*\\n```\\n{escape_md(result.strip()[:1500])}```", parse_mode="Markdown")
            built = True
            break
        elif (path / "package.json").exists():
            result = await run_shell(f"cd {d} && npm run build 2>&1 | tail -10", timeout=60)
            await update.effective_message.reply_text(f"🛠️ *Build Output*\\n```\\n{escape_md(result.strip()[:1500])}```", parse_mode="Markdown")
            built = True
            break
    if not built:
        await update.effective_message.reply_text("🛠️ No buildable project found. Navigate to a project directory first.", parse_mode="Markdown")

async def run_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    cfg = get_machine_config()
    home = cfg['home']
    dirs = [home, f"{home}/guid_erbot"]
    tested = False
    for d in dirs:
        path = Path(d)
        if (path / "Makefile").exists():
            result = await run_shell(f"cd {d} && make test 2>&1 | tail -10", timeout=60)
            if result.strip():
                await update.effective_message.reply_text(f"🧪 *Test Results*\\n```\\n{escape_md(result.strip()[:1500])}```", parse_mode="Markdown")
                tested = True
                break
    if not tested:
        cfg = get_machine_config()
        result = await run_shell(f"cd {cfg['home']}/guid_erbot && python3 -m pytest 2>&1 | tail -20 || python3 -m unittest discover 2>&1 | tail -20 || echo 'No tests found'", timeout=30)
        await update.effective_message.reply_text(f"🧪 *Test Results*\\n```\\n{escape_md(result.strip()[:1500])}```", parse_mode="Markdown")

# ============ FUN ============

async def roll_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    dice = random.randint(1, 6)
    emojis = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
    await update.effective_message.reply_text(f"🎲 *Dice Roll:* {emojis[dice-1]} `{dice}`", parse_mode="Markdown")

async def flip_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    result = random.choice(["Heads", "Tails"])
    emoji = "🪙" if result == "Heads" else "🪙"
    await update.effective_message.reply_text(f"{emoji} *Coin Flip:* **{result}**", parse_mode="Markdown")

async def fortune_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    fortunes = [
        "A beautiful day begins with a beautiful mindset.",
        "Good news will come to you from an unexpected place.",
        "Adventure is worthwhile in itself.",
        "Your hard work will soon pay off.",
        "A surprise is waiting for you around the corner.",
        "The best time to plant a tree was 20 years ago. The second best time is now.",
        "You will soon embark on an exciting new journey.",
        "An old friend will bring you joy this week.",
        "Trust your instincts — they are guiding you right.",
        "Something lost will soon be found.",
        "The stars are aligning in your favor.",
        "A small kindness will lead to a big reward.",
        "Your creativity is about to shine brightly.",
        "Change is coming, and it will be wonderful.",
        "You have the power to make someone's day — use it!",
    ]
    await update.effective_message.reply_text(f"🔮 *Fortune Cookie* 🥠\\n\\n_{random.choice(fortunes)}_", parse_mode="Markdown")

async def eight_ball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    answers = [
        "🎱 Yes, definitely!",
        "🎱 It is certain.",
        "🎱 Without a doubt.",
        "🎱 Most likely.",
        "🎱 Outlook good.",
        "🎱 Reply hazy, try again.",
        "🎱 Ask again later.",
        "🎱 Better not tell you now.",
        "🎱 Don't count on it.",
        "🎱 My sources say no.",
        "🎱 Outlook not so good.",
        "🎱 Very doubtful.",
    ]
    await update.effective_message.reply_text(f"🎱 *Magic 8-Ball*\\n\\n{random.choice(answers)}", parse_mode="Markdown")

async def matrix_effect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    if shutil.which("cmatrix"):
        if shutil.which("xfce4-terminal"):
            subprocess.Popen(["xfce4-terminal", "-e", "cmatrix"], stdout=subprocess.DEVNULL)
            await update.effective_message.reply_text("👾 Matrix rain started in terminal! 🌧️", parse_mode="Markdown")
        else:
            await update.effective_message.reply_text("👾 Install xfce4-terminal to see the Matrix!", parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(
            "👾 *Matrix Effect*\\n\\n"
            "Install cmatrix for the classic Matrix rain effect:\\n"
            "```bash\\nsudo apt install cmatrix\\ncmatrix```",
            parse_mode="Markdown"
        )

async def cat_facts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id): return
    facts = [
        "Cats sleep about 70% of their lives.",
        "A cat's nose print is as unique as a human's fingerprint.",
        "Cats can rotate their ears 180 degrees.",
        "Adult cats have 30 teeth.",
        "Cats can jump up to 6 times their body length.",
        "A group of cats is called a clowder.",
        "Cats spend 30-50% of their day grooming themselves.",
        "The world's richest cat had a net worth of $13 million.",
        "Cats can make over 100 different vocal sounds.",
        "A cat's brain is 90% similar to a human's brain.",
        "The oldest known pet cat existed 9,500 years ago.",
        "Cats walk like camels and giraffes (both right feet, then both left).",
    ]
    await update.effective_message.reply_text(f"🐱 *Cat Fact* 🐱\\n\\n{random.choice(facts)}", parse_mode="Markdown")

# ============ DISPLAY & THEME ============

async def screen_res(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    res = await run_shell("xdpyinfo 2>/dev/null | grep dimensions | awk '{print $2}' || xrandr 2>/dev/null | grep '*' | awk '{print $1}' || echo 'N/A'")
    displays = await run_shell("xrandr --listmonitors 2>/dev/null | head -10 || echo 'No xrandr'")
    text = (
        "🖥️ *Display Info*\\n━━━━━━━━━━━\\n\\n"
        f"*Resolution:* {res.strip()}\\n\\n"
        f"*Monitors:*\\n```\\n{displays.strip()[:500]}```"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def brightness_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    if context.args:
        try:
            val = min(100, max(0, int(context.args[0])))
            await run_shell(f"xrandr --output $(xrandr | grep ' connected' | head -1 | awk '{{print $1}}') --brightness {val/100.0} 2>/dev/null || "
                           f"echo {val} | sudo tee /sys/class/backlight/*/brightness 2>/dev/null || echo 'Cannot adjust brightness'")
            await update.effective_message.reply_text(f"💡 Brightness set to {val}%", parse_mode="Markdown")
        except ValueError:
            await update.effective_message.reply_text("Usage: `/brightness <0-100>`", parse_mode="Markdown")
    else:
        current = await run_shell("xrandr --verbose 2>/dev/null | grep -m1 Brightness | awk '{print $2}' || echo 'N/A'")
        await update.effective_message.reply_text(
            f"💡 *Brightness*\\nCurrent: {current.strip()}\\n\\nUsage: `/brightness <0-100>`",
            parse_mode="Markdown"
        )

async def night_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    if shutil.which("redshift"):
        running = await run_shell("pgrep redshift || echo 'not running'")
        if "not running" in running:
            subprocess.Popen(["redshift", "-O", "3500"], stdout=subprocess.DEVNULL)
            await update.effective_message.reply_text("🌙 Night mode activated!", parse_mode="Markdown")
        else:
            await run_shell("pkill redshift 2>/dev/null; redshift -x 2>/dev/null")
            await update.effective_message.reply_text("☀️ Night mode deactivated!", parse_mode="Markdown")
    else:
        await update.effective_message.reply_text("🌙 Install redshift: `sudo apt install redshift`", parse_mode="Markdown")

async def theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    de = await run_shell("echo $XDG_CURRENT_DESKTOP 2>/dev/null || echo 'Unknown'")
    gtk = await run_shell("gsettings get org.gnome.desktop.interface gtk-theme 2>/dev/null || echo 'N/A'")
    icon = await run_shell("gsettings get org.gnome.desktop.interface icon-theme 2>/dev/null || echo 'N/A'")
    font = await run_shell("gsettings get org.gnome.desktop.interface font-name 2>/dev/null || echo 'N/A'")
    text = (
        "🎨 *Desktop Theme*\\n━━━━━━━━━━━\\n\\n"
        f"*Desktop:* {de.strip()}\\n"
        f"*GTK Theme:* {gtk.strip()}\\n"
        f"*Icons:* {icon.strip()}\\n"
        f"*Font:* {font.strip()}"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

# ============ MISC ============

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    uptime = await run_shell("uptime -p 2>/dev/null | sed 's/up //' || uptime")
    ver = await run_shell("python3 --version 2>/dev/null")
    text = (
        "🔍 *About guid_erbot*\\n━━━━━━━━━━━━━\\n\\n"
        "🤖 *guid_erbot* - Telegram Remote Control for Kali Linux\\n"
        "📡 Control your VM entirely from your phone!\\n\\n"
        f"*Host:* {platform.node()}\\n"
        f"*OS:* {platform.system()} {platform.release()}\\n"
        f"*Python:* {ver.strip()}\\n"
        f"*Uptime:* {uptime.strip()}\\n"
        f"*Buttons:* 90+ sorted commands\\n\\n"
        "💡 Use the keyboard below or type /help for commands!"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def clear_temp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    size = await run_shell("du -sh /tmp 2>/dev/null | awk '{print $1}' || echo 'N/A'")
    await run_shell("rm -rf /tmp/* 2>/dev/null; echo done")
    await update.effective_message.reply_text(f"🧹 *Temp files cleared!* (was {size.strip()})", parse_mode="Markdown")

async def power_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    kb = [
        [InlineKeyboardButton("✅ Yes, power off", callback_data="confirm_shutdown"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel_shutdown")]
    ]
    await update.effective_message.reply_text(
        "⚠️ *Are you sure?* The machine will power off!",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
    )



async def calculator_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "🧮 *Calculator*\\n\\nUsage: `/calc <expression>`\\n"
            "Example: `/calc 2 + 2 * 5`\\n"
            "Example: `/calc sqrt(144)`",
            parse_mode="Markdown"
        )
        return
    expr = " ".join(context.args)
    result = await run_shell(f"python3 -c 'import math; print(eval(\\\"{expr}\\\"))' 2>&1 || echo 'Error'", timeout=5)
    await update.effective_message.reply_text(
        f"🧮 *Calculator*\\n`{escape_md(expr)}`\\n━━━━━━━━━\\n**=** `{result.strip()}`",
        parse_mode="Markdown"
    )

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    notes_file = get_machine_data_dir() / "quick_notes.json"
    if not context.args:
        # Show notes
        if notes_file.exists():
            notes = json.loads(notes_file.read_text())
            text_lines = []
            for i, note in enumerate(reversed(notes[-10:]), 1):
                text_lines.append(f"{i}. {escape_md(note['text'][:80])} _{note['time'][:16]}_")
            text = "📝 *Quick Notes*\\n━━━━━━━━━━\\n\\n" + "\\n".join(text_lines) if text_lines else "📝 *No notes yet*"
        else:
            text = "📝 *No notes yet*\\n\\nUsage: `/note <text>` to add one!"
        await update.effective_message.reply_text(text, parse_mode="Markdown")
    else:
        # Save a note
        note_text = " ".join(context.args)
        notes = json.loads(notes_file.read_text()) if notes_file.exists() else []
        notes.append({"text": note_text, "time": datetime.now().isoformat()})
        notes_file.write_text(json.dumps(notes[-50:]))
        await update.effective_message.reply_text(f"📝 Note saved: _{escape_md(note_text[:80])}_", parse_mode="Markdown")

async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    cal = await run_shell("cal 2>/dev/null || echo 'No calendar'")
    date = datetime.now().strftime("%A, %B %d, %Y")
    time_now = datetime.now().strftime("%H:%M:%S")
    text = (
        f"📅 *Calendar* • {date}\\n"
        f"⏰ *Time:* {time_now}\\n"
        f"━━━━━━━━━━━━\\n```\\n{cal.strip()[:1500]}```"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")

async def open_camera(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return
    apps = [("cheese", "cheese"), ("guvcview", "guvcview"), ("fswebcam", "fswebcam")]
    for name, cmd in apps:
        if shutil.which(cmd):
            subprocess.Popen([cmd], stdout=subprocess.DEVNULL)
            await update.effective_message.reply_text(f"📷 Opened `{name}` ✓", parse_mode="Markdown")
            return
    # Last resort: capture a single frame
    if shutil.which("fswebcam"):
        await run_shell("fswebcam /tmp/webcam.jpg 2>/dev/null")
        if Path("/tmp/webcam.jpg").exists():
            with open("/tmp/webcam.jpg", "rb") as f:
                await update.effective_message.reply_photo(photo=f, caption="📷 Webcam snapshot")
            Path("/tmp/webcam.jpg").unlink()
            return
    await update.effective_message.reply_text("❌ No webcam app found. Install: `sudo apt install cheese`", parse_mode="Markdown")

# ============ EXPORT ============

# Map of button label -> command string
EXTRA_BUTTON_COMMANDS = {
    "💻 Shell Command": "shell",
    "⚙️ Services": "services",
    "🪟 Open Apps": "apps",
    "🌡️ CPU Temp": "temp",
    "📋 Clipboard": "clipboard",
    "🔧 Fix Network": "fixnet",
    "📦 Packages": "packages",
    "🧑‍💻 Who's Online": "whoson",
    "🔄 Update System": "updatesys",
    "🌡️ GPU Info": "gputemp",
    "📡 Speed Test": "speedtest",
    "⌨️ Type Text": "type",
    "🔘 Press Key": "key",
    "🎵 Music": "music",
    "🎬 Media": "media",
    "🖼️ Images": "images",
    "📺 YouTube": "youtube",
    "🎮 Steam": "steam",
    "🎧 Podcasts": "podcast",
    "🖱️ Left Click": "click left",
    "🖱️ Right Click": "click right",
    "📜 Scroll Up": "scroll up",
    "📜 Scroll Down": "scroll down",
    "📍 Mouse Pos": "mpos",
    "📁 Home": "home",
    "📂 Downloads": "downloads",
    "📄 Documents": "docs",
    "🖼️ Screenshots": "screenshots",
    "🎬 Videos": "videos",
    "📤 Upload": "upload",
    "📥 Download": "download",
    "💾 Backup": "backup",
    "🗑️ Empty Trash": "emptytrash",
    "🖥️ VNC Start": "vncstart",
    "🖥️ VNC Stop": "vncstop",
    "🖥️ VNC Status": "vnc",
    "🌍 Open URL": "web",
    "🖧 Share Folder": "share",
    "🔄 Restart Network": "restartnet",
    "🛡️ Firewall": "firewall",
    "🔐 SSH Keys": "sshkeys",
    "🧹 Secure Delete": "shred",
    "🔍 Port Scan": "portscan",
    "🔑 Keychain": "keychain",
    "🐍 Python": "python",
    "🐳 Docker": "docker",
    "📝 VS Code": "vscode",
    "🐙 Git Status": "git",
    "🛠️ Build": "build",
    "🧪 Run Tests": "tests",
    "🎲 Roll Dice": "dice",
    "🪙 Flip Coin": "coin",
    "🔮 Fortune": "fortune",
    "🎱 8-Ball": "8ball",
    "👾 Matrix": "matrix",
    "🐱 Cat Facts": "catfacts",
    "⚙️ Brightness": "brightness",
    "🌙 Night Mode": "nightmode",
    "🖥️ Screen Res": "screenres",
    "🎨 Theme": "theme",
    "🔍 About": "about",
    "🧹 Clear Temp": "cleartemp",
    "🔌 Power Off": "poweroff",
    "💻 Lock Now": "lock",
    "🧮 Calculator": "calc",
    "📝 Notes": "notes",
    "📅 Calendar": "calendar",
    "📷 Camera": "camera",
}

# Map command name to handler function
EXTRA_CMD_MAP = {
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
    "cleartemp": clear_temp,
    "poweroff": power_off,
    "calc": calculator_command,
    "notes": notes_command,
    "calendar": calendar_command,
    "camera": open_camera,
}
