#!/usr/bin/env python3
"""
guid_erbot - Web Control Panel
===============================
Telegram-like web interface for remote machine control.
Launched via the 🌐 Web Panel button in the Telegram bot.

Usage:
  python3 web_panel.py [port]
  (Default port: 5000)

API endpoints:
  /api/* - JSON API for all bot functions
  /      - Web UI (single-page app)
"""

import asyncio
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from flask import Flask, jsonify, request, send_file, Response, render_template_string

# ============ CONFIG ============
WEB_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
PASSWORD = "osboxes.org"
HOST = "0.0.0.0"

# ============ FLASK APP ============
app = Flask(__name__)


# ============ UTILITY ============

def run_shell(cmd: str, timeout=30):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        output = result.stdout + result.stderr
        return output if output else "(No output)"
    except subprocess.TimeoutExpired:
        return f"(Command timed out after {timeout}s)"
    except Exception as e:
        return f"(Error: {e})"


def check_auth():
    """Check password authentication."""
    pwd = request.args.get("pwd") or request.headers.get("X-Password")
    return pwd == PASSWORD


def require_auth(f):
    """Decorator to require authentication."""
    def wrapper(*args, **kwargs):
        if not check_auth():
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def format_bytes(bytes_val):
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


# ============ API ENDPOINTS ============

@app.route("/api/auth")
def api_auth():
    """Check authentication."""
    return jsonify({"ok": check_auth()})


@app.route("/api/sysinfo")
@require_auth
def api_sysinfo():
    """Get system information."""
    cpu_info = run_shell("lscpu | grep 'Model name\\|CPU(s):' | head -2")
    cpu_usage = run_shell("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
    mem_info = run_shell("free -h | grep -E '^Mem:|^Swap:'")
    disk_info = run_shell("df -h / /home 2>/dev/null | grep -v 'Filesystem'")
    ip_info = run_shell("hostname -I 2>/dev/null | awk '{print $1}'")
    wan_ip = run_shell("curl -s ifconfig.me 2>/dev/null || echo 'Unavailable'")
    uptime = run_shell("uptime -p 2>/dev/null || uptime")
    os_info = run_shell("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'")
    kernel = run_shell("uname -r")
    hostname = platform.node()
    
    # CPU temp
    cpu_temp = ""
    if Path("/sys/class/thermal/thermal_zone0/temp").exists():
        try:
            temp_raw = int(open("/sys/class/thermal/thermal_zone0/temp").read().strip())
            cpu_temp = f"{temp_raw / 1000:.1f}"
        except (ValueError, OSError):
            pass
    
    return jsonify({
        "os": os_info.strip(),
        "kernel": kernel.strip(),
        "hostname": hostname,
        "uptime": uptime.strip(),
        "cpu": cpu_info.strip(),
        "cpu_usage": cpu_usage.strip(),
        "cpu_temp": cpu_temp,
        "memory": mem_info.strip(),
        "disk": disk_info.strip(),
        "ip": ip_info.strip(),
        "wan": wan_ip.strip(),
    })


@app.route("/api/processes")
@require_auth
def api_processes():
    """Get running processes."""
    output = run_shell("ps aux --sort=-%mem | head -40")
    total = run_shell("ps aux | wc -l")
    return jsonify({
        "processes": output,
        "total": total.strip(),
    })


@app.route("/api/memory")
@require_auth
def api_memory():
    """Get memory details."""
    mem = run_shell("free -h")
    details = run_shell("cat /proc/meminfo | head -15")
    top_ram = run_shell("ps aux --sort=-%mem | head -8")
    return jsonify({
        "memory": mem,
        "details": details,
        "top_ram": top_ram,
    })


@app.route("/api/disk")
@require_auth
def api_disk():
    """Get disk usage."""
    output = run_shell("df -h --total 2>/dev/null | grep -E '^/dev|total|Filesystem' | column -t")
    inode = run_shell("df -i --total 2>/dev/null | grep -E '^/dev|total' | column -t")
    return jsonify({
        "disk": output,
        "inodes": inode,
    })


@app.route("/api/ip")
@require_auth
def api_ip():
    """Get IP addresses."""
    local_ip = run_shell("hostname -I 2>/dev/null")
    wan_ip = run_shell("curl -s ifconfig.me 2>/dev/null || echo 'Unavailable'")
    interfaces = run_shell("ip -4 addr show | grep inet | grep -v 127.0.0.1 | awk '{print $2, $NF}'")
    gateway = run_shell("ip route | grep default | awk '{print $3}'")
    return jsonify({
        "local": local_ip.strip(),
        "wan": wan_ip.strip(),
        "interfaces": interfaces.strip(),
        "gateway": gateway.strip(),
    })


@app.route("/api/network")
@require_auth
def api_network():
    """Get full network info."""
    interfaces = run_shell("ip -br addr show | grep -v lo")
    wifi_info = run_shell("iwconfig 2>/dev/null | grep -E 'ESSID|Signal|Mode' || echo 'No WiFi info'")
    connections = run_shell("ss -tunap | head -30")
    dns = run_shell("cat /etc/resolv.conf 2>/dev/null | grep nameserver")
    routing = run_shell("ip route | head -5")
    wan = run_shell("curl -s ifconfig.me 2>/dev/null || echo 'Unavailable'")
    return jsonify({
        "interfaces": interfaces.strip(),
        "wifi": wifi_info.strip(),
        "connections": connections.strip(),
        "dns": dns.strip(),
        "routing": routing.strip(),
        "wan": wan.strip(),
    })


@app.route("/api/uptime")
@require_auth
def api_uptime():
    """Get system uptime."""
    output = run_shell("uptime -p 2>/dev/null; echo '---'; who -b 2>/dev/null | awk '{print $3, $4}'")
    return jsonify({"uptime": output.strip()})


@app.route("/api/services")
@require_auth
def api_services():
    """Get running services."""
    output = run_shell("systemctl list-units --type=service --state=running --no-legend 2>/dev/null | awk '{print $1}' | head -40 || echo 'systemctl not available'")
    count = run_shell("systemctl list-units --type=service --state=running --no-legend 2>/dev/null | wc -l || echo '0'")
    return jsonify({
        "services": output.strip(),
        "count": count.strip(),
    })


@app.route("/api/temperature")
@require_auth
def api_temperature():
    """Get CPU temperatures."""
    temps = run_shell("cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{temp=$1/1000; printf \"%.1f°C\\n\", temp}' || echo 'No sensors'")
    cpu_freq = run_shell("lscpu | grep 'MHz' | head -3 2>/dev/null || echo 'N/A'")
    gpu_temp = run_shell("nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo ''")
    return jsonify({
        "temps": temps.strip(),
        "cpu_freq": cpu_freq.strip(),
        "gpu_temp": gpu_temp.strip(),
    })


@app.route("/api/screenshot")
@require_auth
def api_screenshot():
    """Take a screenshot and return it."""
    screenshot_path = "/tmp/guid_web_screenshot.png"
    methods = [
        ["import", "-window", "root", screenshot_path],
        ["scrot", screenshot_path],
        ["gnome-screenshot", "-f", screenshot_path],
    ]
    for cmd in methods:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, timeout=10, capture_output=True)
                if Path(screenshot_path).exists() and Path(screenshot_path).stat().st_size > 1000:
                    return send_file(screenshot_path, mimetype="image/png")
            except (subprocess.TimeoutExpired, OSError):
                continue
    return jsonify({"error": "Failed to take screenshot"}), 500


@app.route("/api/lock", methods=["POST"])
@require_auth
def api_lock():
    """Lock the screen."""
    if not shutil.which("i3lock"):
        # Try fallback
        if shutil.which("xfce4-screensaver-command"):
            run_shell("xfce4-screensaver-command -l 2>/dev/null")
            return jsonify({"ok": True, "message": "Screen locked (xfce4-screensaver)"})
        return jsonify({"error": "i3lock not installed"}), 400
    
    run_shell("pkill -9 xfce4-screensaver 2>/dev/null; sleep 0.5")
    subprocess.Popen(
        ["i3lock", "-c", "1a1a2e", "--nofork"],
        env={"DISPLAY": ":0", "HOME": os.environ.get("HOME", "/home/osboxes")},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    locked = run_shell("pgrep -x i3lock 2>/dev/null || echo 'not running'")
    if "not running" in locked:
        return jsonify({"error": "i3lock failed to start"}), 500
    return jsonify({"ok": True, "message": "Screen locked with i3lock"})


@app.route("/api/unlock", methods=["POST"])
@require_auth
def api_unlock():
    """Unlock the screen."""
    if not shutil.which("xdotool"):
        return jsonify({"error": "xdotool not installed"}), 400
    
    # Check if locked
    locked_check = run_shell("pgrep -x i3lock 2>/dev/null || echo 'not_locked'")
    if "not_locked" in locked_check:
        return jsonify({"error": "Screen is not locked"}), 400
    
    try:
        subprocess.run(["xdotool", "type", "--delay", "20", "osboxes.org"], timeout=5, env={"DISPLAY": ":0"})
        time.sleep(0.3)
        subprocess.run(["xdotool", "key", "Return"], timeout=3, env={"DISPLAY": ":0"})
        time.sleep(0.5)
        
        still_locked = run_shell("pgrep -x i3lock 2>/dev/null || echo 'unlocked'")
        if "unlocked" in still_locked:
            return jsonify({"ok": True, "message": "Screen unlocked!"})
        else:
            return jsonify({"error": "Password was typed but screen is still locked"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notify", methods=["POST"])
@require_auth
def api_notify():
    """Send a desktop notification."""
    msg = (request.json or {}).get("message", "Hello from Web Panel!")
    try:
        subprocess.run(
            ["notify-send", "📱 Web Panel", msg, "-i", "telegram", "-t", "5000"],
            timeout=5, capture_output=True,
        )
        return jsonify({"ok": True, "message": f"Notification sent: {msg}"})
    except FileNotFoundError:
        run_shell(f'echo "NOTIFY: {msg}" | wall 2>/dev/null')
        return jsonify({"ok": True, "message": "Notification sent (fallback)"})


@app.route("/api/shell", methods=["POST"])
@require_auth
def api_shell():
    """Run a shell command."""
    cmd = (request.json or {}).get("command", "")
    if not cmd:
        return jsonify({"error": "No command provided"}), 400
    
    output = run_shell(cmd, timeout=60)
    return jsonify({
        "ok": True,
        "command": cmd,
        "output": output,
    })


@app.route("/api/sound", methods=["POST", "GET"])
@require_auth
def api_sound():
    """Control volume."""
    action = request.args.get("action", "get")
    
    if action == "get":
        vol = run_shell("amixer get Master 2>/dev/null | grep -o '[0-9]*%' | head -1 || echo 'N/A'")
        mute = run_shell("amixer get Master 2>/dev/null | grep -o '\\[on\\]\\|\\[off\\]' | head -1 || echo ''")
        status = "muted" if 'off' in mute else "active"
        return jsonify({"level": vol.strip(), "status": status})
    
    if action == "up":
        run_shell("amixer set Master 5%+ 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ +5%")
        return jsonify({"ok": True, "message": "Volume up"})
    if action == "down":
        run_shell("amixer set Master 5%- 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ -5%")
        return jsonify({"ok": True, "message": "Volume down"})
    if action == "mute":
        run_shell("amixer set Master mute 2>/dev/null || pactl set-sink-mute @DEFAULT_SINK@ 1")
        return jsonify({"ok": True, "message": "Muted"})
    if action == "unmute":
        run_shell("amixer set Master unmute 2>/dev/null || pactl set-sink-mute @DEFAULT_SINK@ 0")
        return jsonify({"ok": True, "message": "Unmuted"})
    
    return jsonify({"error": f"Unknown action: {action}"}), 400


@app.route("/api/vpn")
@require_auth
def api_vpn():
    """Get VPN status."""
    running = run_shell("pgrep -a 'wg-quick\\|openvpn' 2>/dev/null || echo 'Not running'")
    ip = run_shell("ip addr show tun0 2>/dev/null | grep inet | awk '{print $2}' || echo 'No VPN interface'")
    return jsonify({
        "running": "Not running" not in running,
        "info": running.strip(),
        "ip": ip.strip(),
    })


@app.route("/api/vpn", methods=["POST"])
@require_auth
def api_vpn_control():
    """Control VPN."""
    action = (request.json or {}).get("action", "status")
    password = "osboxes.org"
    
    if action == "stop":
        run_shell(f"echo {password} | sudo -S pkill -f 'wg-quick|openvpn' 2>/dev/null; echo 'done'")
        return jsonify({"ok": True, "message": "VPN disconnected"})
    if action == "restart":
        run_shell(f"echo {password} | sudo -S pkill -f 'wg-quick|openvpn' 2>/dev/null; sleep 2")
        wg_conf = list(Path("/etc/wireguard").glob("*.conf")) if Path("/etc/wireguard").exists() else []
        if wg_conf:
            run_shell(f"echo {password} | sudo -S wg-quick up {wg_conf[0].stem} 2>/dev/null")
            return jsonify({"ok": True, "message": "VPN restart attempted"})
        return jsonify({"error": "No VPN config found"}), 400
    return jsonify({"error": "Unknown action"}), 400


@app.route("/api/socks5")
@require_auth
def api_socks5():
    """Get SOCKS5 proxy status."""
    running = run_shell("pgrep -x microsocks 2>/dev/null || echo 'Not running'")
    ip = run_shell("hostname -I 2>/dev/null | awk '{print $1}'")
    return jsonify({
        "running": "Not running" not in running,
        "ip": ip.strip(),
        "port": 1080,
        "user": "osboxes",
        "password": "osboxes.org",
    })


@app.route("/api/socks5", methods=["POST"])
@require_auth
def api_socks5_control():
    """Control SOCKS5 proxy."""
    action = (request.json or {}).get("action", "status")
    
    if action == "start":
        subprocess.Popen(
            ["microsocks", "-i", "0.0.0.0", "-p", "1080", "-b", "-u", "osboxes", "-P", "osboxes.org"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        return jsonify({"ok": True, "message": "SOCKS5 proxy started on port 1080"})
    if action == "stop":
        run_shell("pkill -x microsocks 2>/dev/null")
        return jsonify({"ok": True, "message": "SOCKS5 proxy stopped"})
    return jsonify({"error": "Unknown action"}), 400


@app.route("/api/vnc")
@require_auth
def api_vnc():
    """Get VNC status."""
    running = run_shell("pgrep -a x11vnc 2>/dev/null || echo 'Not running'")
    port_check = run_shell("ss -tlnp | grep 5900 || echo 'Port 5900 not listening'")
    return jsonify({
        "running": "Not running" not in running,
        "info": running.strip(),
        "port": port_check.strip(),
    })


@app.route("/api/rustdesk")
@require_auth
def api_rustdesk():
    """Get RustDesk info."""
    rustdesk_paths = ["/usr/share/rustdesk/rustdesk", "/usr/bin/rustdesk", "/usr/local/bin/rustdesk"]
    installed = any(Path(p).exists() for p in rustdesk_paths)
    
    info = {}
    if installed:
        id_output = run_shell("rustdesk --get-id 2>/dev/null || cat /etc/rustdesk/id 2>/dev/null || echo 'Not available'")
        status = run_shell("systemctl status rustdesk 2>/dev/null | grep -E 'Active|running' || echo 'Service not running'")
        info["id"] = id_output.strip()
        info["status"] = status.strip()
    
    return jsonify({
        "installed": installed,
        **info,
    })


@app.route("/api/files")
@require_auth
def api_files():
    """List files in a directory."""
    path = request.args.get("path", "/home/osboxes")
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return jsonify({"error": "Path does not exist"}), 400
        if not p.is_dir():
            return jsonify({"error": "Path is not a directory"}), 400
        
        items = []
        for entry in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                stat = entry.stat()
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": stat.st_size,
                    "size_hr": format_bytes(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except (OSError, PermissionError):
                continue
        
        return jsonify({
            "path": str(p),
            "parent": str(p.parent) if str(p) != "/" else None,
            "items": items,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download")
@require_auth
def api_download():
    """Download a file."""
    path = request.args.get("path", "")
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists() or not p.is_file():
            return jsonify({"error": "File not found"}), 404
        if p.stat().st_size > 50 * 1024 * 1024:
            return jsonify({"error": "File too large (max 50MB)"}), 400
        
        return send_file(str(p))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status")
@require_auth
def api_status():
    """Get all status info for dashboard."""
    cpu_usage = run_shell("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
    mem = run_shell("free -h | grep Mem | awk '{print $3 \"/\" $2}'")
    mem_pct = run_shell("free | grep Mem | awk '{printf \"%.0f\", $3/$2 * 100}'")
    disk = run_shell("df -h / | tail -1 | awk '{print $3 \"/\" $2 \" (\" $5 \")\"}'")
    uptime = run_shell("uptime -p 2>/dev/null | sed 's/up //' || uptime")
    processes = run_shell("ps aux | wc -l")
    ip = run_shell("hostname -I 2>/dev/null | awk '{print $1}'")
    
    # Lock status
    locked = run_shell("pgrep -x i3lock 2>/dev/null || echo 'unlocked'")
    is_locked = "unlocked" not in locked.lower()
    
    return jsonify({
        "cpu": cpu_usage.strip(),
        "memory": mem.strip(),
        "memory_pct": mem_pct.strip(),
        "disk": disk.strip(),
        "uptime": uptime.strip(),
        "processes": processes.strip(),
        "ip": ip.strip(),
        "hostname": platform.node(),
        "locked": is_locked,
    })


# ============ WEB UI ============

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>guid_erbot · Web Control</title>
<style>
  :root {
    --bg-primary: #1a1a2e;
    --bg-secondary: #16213e;
    --bg-card: #0f3460;
    --bg-input: #1a1a3e;
    --accent: #2aabee;
    --accent-hover: #1e8fc7;
    --text-primary: #e8e8e8;
    --text-secondary: #8892a4;
    --text-muted: #5a6377;
    --danger: #e74c3c;
    --success: #2ecc71;
    --warning: #f39c12;
    --border: #2a2a4a;
    --sidebar-width: 220px;
    --header-height: 56px;
    --radius: 10px;
    --shadow: 0 2px 12px rgba(0,0,0,0.3);
  }
  
  * { margin: 0; padding: 0; box-sizing: border-box; }
  
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    overflow: hidden;
    height: 100vh;
  }
  
  /* ===== HEADER ===== */
  .header {
    position: fixed;
    top: 0; left: 0; right: 0;
    height: var(--header-height);
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    padding: 0 20px;
    z-index: 100;
    gap: 12px;
  }
  .header .menu-btn {
    display: none;
    background: none;
    border: none;
    color: var(--text-primary);
    font-size: 22px;
    cursor: pointer;
    padding: 4px;
  }
  .header .logo {
    font-size: 18px;
    font-weight: 700;
    color: var(--accent);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .header .logo span { color: var(--text-primary); font-weight: 400; }
  .header .status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-left: auto;
  }
  .header .status-dot.online { background: var(--success); box-shadow: 0 0 8px var(--success); }
  .header .status-dot.offline { background: var(--danger); }
  
  /* ===== SIDEBAR ===== */
  .sidebar {
    position: fixed;
    top: var(--header-height);
    left: 0;
    width: var(--sidebar-width);
    height: calc(100vh - var(--header-height));
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    overflow-y: auto;
    z-index: 90;
    transition: transform 0.3s ease;
  }
  .sidebar .nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 20px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s;
    border-left: 3px solid transparent;
    font-size: 14px;
  }
  .sidebar .nav-item:hover {
    background: rgba(42, 171, 238, 0.08);
    color: var(--text-primary);
  }
  .sidebar .nav-item.active {
    background: rgba(42, 171, 238, 0.12);
    color: var(--accent);
    border-left-color: var(--accent);
  }
  .sidebar .nav-item .icon { font-size: 18px; width: 24px; text-align: center; }
  .sidebar .nav-section {
    padding: 16px 20px 8px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-muted);
    font-weight: 600;
  }
  
  /* ===== MAIN CONTENT ===== */
  .main {
    margin-left: var(--sidebar-width);
    margin-top: var(--header-height);
    height: calc(100vh - var(--header-height));
    overflow-y: auto;
    padding: 20px 24px;
  }
  
  /* ===== BOTTOM NAV (Mobile) ===== */
  .bottom-nav {
    display: none;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border);
    z-index: 100;
    padding: 4px 0 env(safe-area-inset-bottom, 4px);
  }
  .bottom-nav .nav-items {
    display: flex;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .bottom-nav .nav-item {
    flex: 1 0 auto;
    min-width: 60px;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 6px 8px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
    font-size: 10px;
    gap: 2px;
  }
  .bottom-nav .nav-item .icon { font-size: 20px; }
  .bottom-nav .nav-item.active { color: var(--accent); }
  .bottom-nav .nav-item.active .icon { transform: scale(1.1); }
  
  /* ===== PAGES ===== */
  .page { display: none; }
  .page.active { display: block; animation: fadeIn 0.2s ease; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  
  .page-title {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  
  /* ===== CARDS ===== */
  .card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 20px;
    margin-bottom: 16px;
  }
  .card-title {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    margin-bottom: 8px;
    font-weight: 600;
  }
  .card-value {
    font-size: 20px;
    font-weight: 700;
  }
  .card-value.green { color: var(--success); }
  .card-value.yellow { color: var(--warning); }
  .card-value.red { color: var(--danger); }
  .card-value.blue { color: var(--accent); }
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
  }
  
  /* ===== BUTTONS ===== */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s;
    font-family: inherit;
  }
  .btn:active { transform: scale(0.97); }
  .btn-primary { background: var(--accent); color: white; }
  .btn-primary:hover { background: var(--accent-hover); }
  .btn-danger { background: var(--danger); color: white; }
  .btn-danger:hover { background: #c0392b; }
  .btn-success { background: var(--success); color: white; }
  .btn-success:hover { background: #27ae60; }
  .btn-warning { background: var(--warning); color: white; }
  .btn-outline {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-primary);
  }
  .btn-outline:hover { background: rgba(255,255,255,0.05); }
  .btn-sm { padding: 6px 14px; font-size: 12px; }
  .btn-lg { padding: 14px 28px; font-size: 16px; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  
  .btn-group {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin: 8px 0;
  }
  
  /* ===== INPUTS ===== */
  input, textarea, select {
    background: var(--bg-input);
    border: 1px solid var(--border);
    color: var(--text-primary);
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 14px;
    font-family: inherit;
    width: 100%;
    transition: border-color 0.2s;
  }
  input:focus, textarea:focus { outline: none; border-color: var(--accent); }
  textarea { resize: vertical; min-height: 60px; font-family: 'Courier New', monospace; }
  
  .input-group {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
  }
  .input-group input { flex: 1; }
  
  /* ===== TERMINAL ===== */
  .terminal {
    background: #0d0d1a;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.5;
    min-height: 300px;
    max-height: 500px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
    margin-bottom: 12px;
  }
  .terminal .prompt { color: var(--success); }
  .terminal .output { color: var(--text-primary); }
  .terminal .error { color: var(--danger); }
  
  /* ===== CODE BLOCKS ===== */
  .code-block {
    background: #0d0d1a;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 16px;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    line-height: 1.5;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 400px;
    overflow-y: auto;
  }
  
  /* ===== LOGIN SCREEN ===== */
  .login-overlay {
    position: fixed;
    inset: 0;
    background: var(--bg-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 999;
  }
  .login-box {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 40px;
    width: 90%;
    max-width: 360px;
    text-align: center;
  }
  .login-box .logo { font-size: 48px; margin-bottom: 12px; }
  .login-box h2 { margin-bottom: 8px; color: var(--accent); }
  .login-box p { color: var(--text-secondary); font-size: 14px; margin-bottom: 24px; }
  .login-box input { margin-bottom: 12px; text-align: center; }
  .login-box .error { color: var(--danger); font-size: 13px; margin-top: 8px; display: none; }
  
  /* ===== TOAST ===== */
  .toast {
    position: fixed;
    bottom: 80px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-card);
    color: var(--text-primary);
    padding: 12px 24px;
    border-radius: 8px;
    box-shadow: var(--shadow);
    z-index: 200;
    font-size: 14px;
    display: none;
    animation: slideUp 0.3s ease;
  }
  @keyframes slideUp { from { opacity: 0; transform: translateX(-50%) translateY(20px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
  
  /* ===== FILE BROWSER ===== */
  .file-list { list-style: none; }
  .file-list li {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    transition: background 0.15s;
    font-size: 14px;
  }
  .file-list li:hover { background: rgba(255,255,255,0.03); }
  .file-list li .icon { font-size: 18px; width: 24px; }
  .file-list li .name { flex: 1; }
  .file-list li .size { color: var(--text-muted); font-size: 12px; }
  .file-list li .actions { display: flex; gap: 6px; }
  .file-path {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    padding: 8px 12px;
    background: var(--bg-input);
    border-radius: 8px;
    font-size: 13px;
    overflow-x: auto;
    white-space: nowrap;
  }
  .file-path .sep { color: var(--text-muted); }
  
  /* ===== PROGRESS ===== */
  .progress-bar {
    height: 6px;
    background: var(--bg-input);
    border-radius: 3px;
    overflow: hidden;
    margin: 4px 0;
  }
  .progress-bar .fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
  }
  .progress-bar .fill.green { background: var(--success); }
  .progress-bar .fill.yellow { background: var(--warning); }
  .progress-bar .fill.red { background: var(--danger); }
  .progress-bar .fill.blue { background: var(--accent); }
  
  /* ===== SCREENSHOT ===== */
  .screenshot-container {
    position: relative;
    border-radius: var(--radius);
    overflow: hidden;
    border: 1px solid var(--border);
    margin-bottom: 12px;
    max-width: 100%;
  }
  .screenshot-container img {
    width: 100%;
    display: block;
  }
  
  /* ===== RESPONSIVE ===== */
  @media (max-width: 768px) {
    .sidebar { transform: translateX(-100%); }
    .sidebar.open { transform: translateX(0); }
    .main { margin-left: 0; padding: 16px; padding-bottom: 80px; }
    .header .menu-btn { display: block; }
    .bottom-nav { display: block; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .login-box { padding: 24px; }
  }
  
  /* ===== SCROLLBAR ===== */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
  
  /* ===== TABLE ===== */
  .data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .data-table th {
    text-align: left;
    padding: 8px 12px;
    border-bottom: 2px solid var(--border);
    color: var(--text-muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .data-table td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
  }
  .data-table tr:hover td { background: rgba(255,255,255,0.02); }
  
  /* ===== LOCK STATUS ===== */
  .lock-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
  }
  .lock-badge.locked { background: rgba(231, 76, 60, 0.15); color: var(--danger); }
  .lock-badge.unlocked { background: rgba(46, 204, 113, 0.15); color: var(--success); }
  
  .loading { opacity: 0.5; pointer-events: none; }
  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.6s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>

<!-- ========== LOGIN ========== -->
<div class="login-overlay" id="loginOverlay">
  <div class="login-box">
    <div class="logo">🤖</div>
    <h2>guid_erbot</h2>
    <p>Enter password to access the control panel</p>
    <input type="password" id="passwordInput" placeholder="Password" autocomplete="off" onkeydown="if(event.key==='Enter') login()">
    <button class="btn btn-primary btn-lg" style="width:100%" onclick="login()">Unlock</button>
    <div class="error" id="loginError">Wrong password. Try again.</div>
  </div>
</div>

<!-- ========== HEADER ========== -->
<div class="header">
  <button class="menu-btn" onclick="toggleSidebar()">☰</button>
  <div class="logo">🤖 guid_erbot<span> · Web Panel</span></div>
  <div class="status-dot online" id="statusDot" title="Online"></div>
</div>

<!-- ========== SIDEBAR ========== -->
<div class="sidebar" id="sidebar">
  <div class="nav-section">Control</div>
  <div class="nav-item active" data-page="dashboard" onclick="navigate('dashboard')">
    <span class="icon">🏠</span> Dashboard
  </div>
  <div class="nav-item" data-page="terminal" onclick="navigate('terminal')">
    <span class="icon">💻</span> Terminal
  </div>
  <div class="nav-item" data-page="desktop" onclick="navigate('desktop')">
    <span class="icon">🖥️</span> Desktop
  </div>
  <div class="nav-section">System</div>
  <div class="nav-item" data-page="system" onclick="navigate('system')">
    <span class="icon">📊</span> System
  </div>
  <div class="nav-item" data-page="sound" onclick="navigate('sound')">
    <span class="icon">🔊</span> Sound
  </div>
  <div class="nav-item" data-page="network" onclick="navigate('network')">
    <span class="icon">🌐</span> Network
  </div>
  <div class="nav-section">Tools</div>
  <div class="nav-item" data-page="files" onclick="navigate('files')">
    <span class="icon">📁</span> Files
  </div>
</div>

<!-- ========== BOTTOM NAV (Mobile) ========== -->
<div class="bottom-nav" id="bottomNav">
  <div class="nav-items">
    <div class="nav-item active" data-page="dashboard" onclick="navigate('dashboard')">
      <span class="icon">🏠</span> Dashboard
    </div>
    <div class="nav-item" data-page="terminal" onclick="navigate('terminal')">
      <span class="icon">💻</span> Terminal
    </div>
    <div class="nav-item" data-page="desktop" onclick="navigate('desktop')">
      <span class="icon">🖥️</span> Desktop
    </div>
    <div class="nav-item" data-page="system" onclick="navigate('system')">
      <span class="icon">📊</span> System
    </div>
    <div class="nav-item" data-page="network" onclick="navigate('network')">
      <span class="icon">🌐</span> Network
    </div>
  </div>
</div>

<!-- ========== MAIN ========== -->
<div class="main" id="mainContent">

  <!-- ===== PAGE: Dashboard ===== -->
  <div class="page active" id="page-dashboard">
    <div class="page-title">🏠 Dashboard</div>
    <div class="stats-grid" id="dashStats">
      <div class="card"><div class="card-title">CPU Usage</div><div class="card-value blue" id="dashCpu">—</div><div class="progress-bar" style="margin-top:6px"><div class="fill blue" id="dashCpuBar" style="width:0%"></div></div></div>
      <div class="card"><div class="card-title">Memory</div><div class="card-value yellow" id="dashMem">—</div><div class="progress-bar" style="margin-top:6px"><div class="fill yellow" id="dashMemBar" style="width:0%"></div></div></div>
      <div class="card"><div class="card-title">Disk (/)</div><div class="card-value green" id="dashDisk">—</div><div class="progress-bar" style="margin-top:6px"><div class="fill green" id="dashDiskBar" style="width:0%"></div></div></div>
      <div class="card"><div class="card-title">Uptime</div><div class="card-value blue" id="dashUptime">—</div></div>
      <div class="card"><div class="card-title">Processes</div><div class="card-value" id="dashProcs">—</div></div>
      <div class="card"><div class="card-title">IP Address</div><div class="card-value blue" id="dashIp">—</div></div>
      <div class="card"><div class="card-title">Hostname</div><div class="card-value" id="dashHostname">—</div></div>
      <div class="card">
        <div class="card-title">Screen Lock</div>
        <div id="dashLock">
          <span class="lock-badge unlocked" id="dashLockBadge">🔓 Unlocked</span>
        </div>
        <div class="btn-group" style="margin-top:8px">
          <button class="btn btn-danger btn-sm" onclick="apiPost('/api/lock', {}, 'Locking...')">🔒 Lock</button>
          <button class="btn btn-success btn-sm" onclick="apiPost('/api/unlock', {}, 'Unlocking...')">🔓 Unlock</button>
        </div>
      </div>
    </div>
    <div class="btn-group">
      <button class="btn btn-outline btn-sm" onclick="refreshDashboard()">🔄 Refresh</button>
    </div>
  </div>

  <!-- ===== PAGE: Terminal ===== -->
  <div class="page" id="page-terminal">
    <div class="page-title">💻 Terminal</div>
    <div class="card">
      <div class="terminal" id="terminalOutput"><span class="prompt">$ </span><span class="output">Ready. Type a command below.</span></div>
      <div class="input-group">
        <input type="text" id="cmdInput" placeholder="Enter command..." autocomplete="off" onkeydown="if(event.key==='Enter') runCommand()">
        <button class="btn btn-primary" onclick="runCommand()">▶ Run</button>
        <button class="btn btn-outline" onclick="clearTerminal()">✕ Clear</button>
      </div>
    </div>
  </div>

  <!-- ===== PAGE: Desktop ===== -->
  <div class="page" id="page-desktop">
    <div class="page-title">🖥️ Desktop</div>
    <div class="card">
      <div class="card-title">Screenshot</div>
      <div class="screenshot-container" id="screenshotArea">
        <img id="screenshotImg" src="" alt="Screenshot will appear here" style="display:none">
        <div id="screenshotPlaceholder" style="padding:40px;text-align:center;color:var(--text-muted)">📸 Tap "Take Screenshot" to capture</div>
      </div>
      <button class="btn btn-primary" onclick="takeScreenshot()">📸 Take Screenshot</button>
    </div>
    <div class="card">
      <div class="card-title">Lock / Unlock</div>
      <div class="btn-group">
        <button class="btn btn-danger btn-lg" onclick="apiPost('/api/lock', {}, 'Locking...')">🔒 Lock Screen</button>
        <button class="btn btn-success btn-lg" onclick="apiPost('/api/unlock', {}, 'Unlocking...')">🔓 Unlock Screen</button>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Send Notification</div>
      <div class="input-group">
        <input type="text" id="notifyInput" placeholder="Notification message..." onkeydown="if(event.key==='Enter') sendNotify()">
        <button class="btn btn-primary" onclick="sendNotify()">🔔 Send</button>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Type Text</div>
      <div class="input-group">
        <input type="text" id="typeInput" placeholder="Text to type on desktop...">
        <button class="btn btn-primary" onclick="apiPost('/api/shell', {command: 'DISPLAY=:0 xdotool type --delay 50 ' + encodeURIComponent(document.getElementById(\"typeInput\").value)}, 'Typing...')">⌨️ Type</button>
      </div>
    </div>
  </div>

  <!-- ===== PAGE: System ===== -->
  <div class="page" id="page-system">
    <div class="page-title">📊 System</div>
    <div class="card">
      <div class="card-title">System Information</div>
      <div class="code-block" id="sysinfoOutput">Loading...</div>
      <button class="btn btn-outline btn-sm" style="margin-top:8px" onclick="loadSysInfo()">🔄 Refresh</button>
    </div>
    <div class="card">
      <div class="card-title">Memory</div>
      <div class="code-block" id="memoryOutput">Loading...</div>
      <button class="btn btn-outline btn-sm" style="margin-top:8px" onclick="loadMemory()">🔄 Refresh</button>
    </div>
    <div class="card">
      <div class="card-title">Disk Usage</div>
      <div class="code-block" id="diskOutput">Loading...</div>
      <button class="btn btn-outline btn-sm" style="margin-top:8px" onclick="loadDisk()">🔄 Refresh</button>
    </div>
    <div class="card">
      <div class="card-title">Running Processes</div>
      <div class="code-block" id="processesOutput">Loading...</div>
      <button class="btn btn-outline btn-sm" style="margin-top:8px" onclick="loadProcesses()">🔄 Refresh</button>
    </div>
    <div class="card">
      <div class="card-title">Temperature</div>
      <div class="code-block" id="tempOutput">Loading...</div>
      <button class="btn btn-outline btn-sm" style="margin-top:8px" onclick="loadTemperature()">🔄 Refresh</button>
    </div>
  </div>

  <!-- ===== PAGE: Sound ===== -->
  <div class="page" id="page-sound">
    <div class="page-title">🔊 Sound</div>
    <div class="card">
      <div class="card-title">Volume Control</div>
      <div style="text-align:center;padding:20px 0">
        <div style="font-size:64px;margin-bottom:12px" id="soundIcon">🔊</div>
        <div style="font-size:28px;font-weight:700;margin-bottom:4px" id="soundLevel">—</div>
        <div style="font-size:13px;color:var(--text-muted)" id="soundStatus">Loading...</div>
      </div>
      <div class="btn-group" style="justify-content:center">
        <button class="btn btn-outline btn-lg" onclick="soundAction('down')">🔉 −</button>
        <button class="btn btn-outline btn-lg" onclick="soundAction('mute')" id="muteBtn">🔇 Mute</button>
        <button class="btn btn-outline btn-lg" onclick="soundAction('up')">🔊 +</button>
      </div>
      <div style="margin-top:12px;max-width:300px;margin-left:auto;margin-right:auto">
        <input type="range" min="0" max="100" value="50" id="volumeSlider" onchange="setVolume(this.value)" style="width:100%">
      </div>
    </div>
  </div>

  <!-- ===== PAGE: Network ===== -->
  <div class="page" id="page-network">
    <div class="page-title">🌐 Network</div>
    <div class="card">
      <div class="card-title">IP Addresses</div>
      <div class="code-block" id="ipOutput">Loading...</div>
      <button class="btn btn-outline btn-sm" style="margin-top:8px" onclick="loadIP()">🔄 Refresh</button>
    </div>
    <div class="card">
      <div class="card-title">Network Info</div>
      <div class="code-block" id="networkOutput">Loading...</div>
      <button class="btn btn-outline btn-sm" style="margin-top:8px" onclick="loadNetwork()">🔄 Refresh</button>
    </div>
    <div class="card">
      <div class="card-title">VPN</div>
      <div id="vpnStatus">Checking...</div>
      <div class="btn-group" style="margin-top:8px">
        <button class="btn btn-primary btn-sm" onclick="vpnAction('restart')">🔄 Restart VPN</button>
        <button class="btn btn-danger btn-sm" onclick="vpnAction('stop')">⏹️ Stop VPN</button>
      </div>
    </div>
    <div class="card">
      <div class="card-title">SOCKS5 Proxy</div>
      <div id="socks5Status">Checking...</div>
      <div class="btn-group" style="margin-top:8px">
        <button class="btn btn-success btn-sm" onclick="socks5Action('start')">▶️ Start</button>
        <button class="btn btn-danger btn-sm" onclick="socks5Action('stop')">⏹️ Stop</button>
      </div>
    </div>
    <div class="card">
      <div class="card-title">RustDesk</div>
      <div class="code-block" id="rustdeskOutput">Loading...</div>
      <button class="btn btn-outline btn-sm" style="margin-top:8px" onclick="loadRustDesk()">🔄 Refresh</button>
    </div>
  </div>

  <!-- ===== PAGE: Files ===== -->
  <div class="page" id="page-files">
    <div class="page-title">📁 Files</div>
    <div class="card">
      <div class="input-group">
        <input type="text" id="filePath" value="/home/osboxes" onkeydown="if(event.key==='Enter') loadFiles()">
        <button class="btn btn-primary" onclick="loadFiles()">📂 Browse</button>
      </div>
      <div class="file-path" id="fileBreadcrumb"></div>
      <ul class="file-list" id="fileList">
        <li style="color:var(--text-muted);justify-content:center">Enter a path and tap Browse</li>
      </ul>
    </div>
  </div>

</div>

<!-- ========== TOAST ========== -->
<div class="toast" id="toast"></div>

<script>
// ========== CONFIG ==========
const PWD = localStorage.getItem("panel_pwd") || "";

// ========== API HELPERS ==========
function apiUrl(path) {
  const sep = path.includes("?") ? "&" : "?";
  return path + sep + "pwd=" + encodeURIComponent(PWD);
}

async function apiGet(path) {
  const resp = await fetch(apiUrl(path));
  if (resp.status === 401) { localStorage.removeItem("panel_pwd"); location.reload(); }
  return resp.json();
}

async function apiPost(path, data = {}, toastMsg = "") {
  if (toastMsg) showToast(toastMsg);
  const resp = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Password": PWD },
    body: JSON.stringify(data),
  });
  const result = await resp.json();
  if (result.ok || result.message) showToast(result.message || "Done!");
  else if (result.error) showToast("❌ " + result.error);
  return result;
}

async function apiPostRaw(path, data = {}) {
  const resp = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Password": PWD },
    body: JSON.stringify(data),
  });
  return resp.json();
}

// ========== AUTH ==========
async function login() {
  const pwd = document.getElementById("passwordInput").value;
  const resp = await fetch("/api/auth?pwd=" + encodeURIComponent(pwd));
  const data = await resp.json();
  if (data.ok) {
    localStorage.setItem("panel_pwd", pwd);
    document.getElementById("loginOverlay").style.display = "none";
    initApp();
  } else {
    document.getElementById("loginError").style.display = "block";
  }
}

// Check stored password on load
(async function() {
  if (PWD) {
    const resp = await fetch("/api/auth?pwd=" + encodeURIComponent(PWD));
    const data = await resp.json();
    if (data.ok) {
      document.getElementById("loginOverlay").style.display = "none";
      initApp();
    }
  }
})();

// ========== TOAST ==========
let toastTimeout;

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.style.display = "block";
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => t.style.display = "none", 2500);
}

// ========== NAVIGATION ==========
function navigate(page) {
  // Update sidebar
  document.querySelectorAll(".sidebar .nav-item, .bottom-nav .nav-item").forEach(el => {
    el.classList.toggle("active", el.dataset.page === page);
  });
  // Update pages
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.getElementById("page-" + page).classList.add("active");
  // Close sidebar on mobile
  document.getElementById("sidebar").classList.remove("open");
  // Load page content
  if (page === "dashboard") refreshDashboard();
  else if (page === "system") { loadSysInfo(); loadMemory(); loadDisk(); loadProcesses(); loadTemperature(); }
  else if (page === "sound") loadSound();
  else if (page === "network") { loadIP(); loadNetwork(); loadVPN(); loadSocks5(); loadRustDesk(); }
}

function toggleSidebar() {
  document.getElementById("sidebar").classList.toggle("open");
}

// ========== INIT ==========
function initApp() {
  refreshDashboard();
  loadSound();
}

// ========== DASHBOARD ==========
async function refreshDashboard() {
  try {
    const data = await apiGet("/api/status");
    document.getElementById("dashCpu").textContent = data.cpu + "%";
    document.getElementById("dashCpuBar").style.width = data.cpu + "%";
    document.getElementById("dashMem").textContent = data.memory;
    document.getElementById("dashMemBar").style.width = Math.min(parseInt(data.memory_pct) || 0, 100) + "%";
    document.getElementById("dashDisk").textContent = data.disk;
    document.getElementById("dashUptime").textContent = data.uptime;
    document.getElementById("dashProcs").textContent = data.processes;
    document.getElementById("dashIp").textContent = data.ip || "—";
    document.getElementById("dashHostname").textContent = data.hostname;
    
    const badge = document.getElementById("dashLockBadge");
    if (data.locked) {
      badge.className = "lock-badge locked";
      badge.textContent = "🔒 Locked";
    } else {
      badge.className = "lock-badge unlocked";
      badge.textContent = "🔓 Unlocked";
    }
  } catch (e) {
    showToast("❌ Failed to load dashboard");
  }
}

// Auto-refresh dashboard every 10 seconds
setInterval(refreshDashboard, 10000);

// ========== TERMINAL ==========
async function runCommand() {
  const input = document.getElementById("cmdInput");
  const cmd = input.value.trim();
  if (!cmd) return;
  
  const term = document.getElementById("terminalOutput");
  term.innerHTML += '\n<span class="prompt">$ </span><span class="output">' + escapeHtml(cmd) + '</span>\n';
  term.scrollTop = term.scrollHeight;
  input.value = "";
  input.disabled = true;
  
  try {
    const result = await apiPostRaw("/api/shell", { command: cmd });
    if (result.output) {
      const cls = result.output.startsWith("(Error") ? "error" : "output";
      term.innerHTML += '<span class="' + cls + '">' + escapeHtml(result.output) + '</span>\n';
    }
  } catch (e) {
    term.innerHTML += '<span class="error">(Error: ' + e.message + ')</span>\n';
  }
  
  term.scrollTop = term.scrollHeight;
  input.disabled = false;
  input.focus();
}

function clearTerminal() {
  document.getElementById("terminalOutput").innerHTML = '<span class="prompt">$ </span><span class="output">Ready. Type a command below.</span>';
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}

// ========== DESKTOP ==========
async function takeScreenshot() {
  const img = document.getElementById("screenshotImg");
  const placeholder = document.getElementById("screenshotPlaceholder");
  placeholder.style.display = "none";
  img.style.display = "block";
  img.src = apiUrl("/api/screenshot") + "&t=" + Date.now();
  showToast("📸 Screenshot taken!");
}

async function sendNotify() {
  const msg = document.getElementById("notifyInput").value.trim();
  if (!msg) { showToast("❌ Enter a message"); return; }
  await apiPost("/api/notify", { message: msg }, "🔔 Sending notification...");
  document.getElementById("notifyInput").value = "";
}

// ========== SYSTEM ==========
async function loadSysInfo() {
  const data = await apiGet("/api/sysinfo");
  document.getElementById("sysinfoOutput").textContent =
    `OS:       ${data.os}\n` +
    `Kernel:   ${data.kernel}\n` +
    `Hostname: ${data.hostname}\n` +
    `Uptime:   ${data.uptime}\n` +
    `CPU:      ${data.cpu}\n` +
    `CPU Temp: ${data.cpu_temp || "N/A"}\n` +
    `\n--- Memory ---\n${data.memory}\n` +
    `\n--- Disk ---\n${data.disk}`;
}

async function loadMemory() {
  const data = await apiGet("/api/memory");
  document.getElementById("memoryOutput").textContent =
    data.memory + "\n\n--- Top RAM ---\n" + data.top_ram;
}

async function loadDisk() {
  const data = await apiGet("/api/disk");
  document.getElementById("diskOutput").textContent =
    data.disk;
}

async function loadProcesses() {
  const data = await apiGet("/api/processes");
  document.getElementById("processesOutput").textContent =
    `Total: ${data.total}\n\n${data.processes}`;
}

async function loadTemperature() {
  const data = await apiGet("/api/temperature");
  document.getElementById("tempOutput").textContent =
    data.temps + "\n\nCPU Freq:\n" + data.cpu_freq +
    (data.gpu_temp ? "\n\nGPU: " + data.gpu_temp + "°C" : "");
}

// ========== SOUND ==========
async function loadSound() {
  const data = await apiGet("/api/sound");
  document.getElementById("soundLevel").textContent = data.level;
  document.getElementById("soundStatus").textContent = data.status;
  document.getElementById("soundIcon").textContent = data.status === "muted" ? "🔇" : "🔊";
  document.getElementById("muteBtn").textContent = data.status === "muted" ? "🔊 Unmute" : "🔇 Mute";
  document.getElementById("muteBtn").onclick = () => soundAction(data.status === "muted" ? "unmute" : "mute");
  
  const slider = document.getElementById("volumeSlider");
  const val = parseInt(data.level) || 50;
  slider.value = val;
}

async function soundAction(action) {
  await apiGet("/api/sound?action=" + action);
  loadSound();
}

async function setVolume(val) {
  await apiPostRaw("/api/shell", { command: "amixer set Master " + val + "% 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ " + val + "%" });
  loadSound();
}

// ========== NETWORK ==========
async function loadIP() {
  const data = await apiGet("/api/ip");
  document.getElementById("ipOutput").textContent =
    `Local:  ${data.local}\n` +
    `WAN:    ${data.wan}\n` +
    `Gateway: ${data.gateway}\n\nInterfaces:\n${data.interfaces}`;
}

async function loadNetwork() {
  const data = await apiGet("/api/network");
  document.getElementById("networkOutput").textContent =
    `Interfaces:\n${data.interfaces}\n\nWiFi:\n${data.wifi}\n\nDNS:\n${data.dns}\n\nRouting:\n${data.routing}\n\nWAN IP: ${data.wan}`;
}

async function loadVPN() {
  const data = await apiGet("/api/vpn");
  document.getElementById("vpnStatus").innerHTML =
    (data.running ? "✅ <b>Connected</b>" : "❌ <b>Disconnected</b>") +
    "<br><small>" + escapeHtml(data.info) + "</small>";
}

async function vpnAction(action) {
  await apiPost("/api/vpn", { action: action }, "VPN " + action + "...");
  loadVPN();
}

async function loadSocks5() {
  const data = await apiGet("/api/socks5");
  document.getElementById("socks5Status").innerHTML =
    (data.running ? "✅ <b>Running</b> on " + data.ip + ":" + data.port : "❌ <b>Stopped</b>") +
    (data.running ? "<br><small>User: " + data.user + " | Pass: " + data.password + "</small>" : "");
}

async function socks5Action(action) {
  await apiPost("/api/socks5", { action: action }, "SOCKS5 " + action + "...");
  loadSocks5();
}

async function loadRustDesk() {
  const data = await apiGet("/api/rustdesk");
  if (data.installed) {
    document.getElementById("rustdeskOutput").textContent =
      `Installed: ✅\nID: ${data.id || "N/A"}\n\nStatus:\n${data.status || "N/A"}`;
  } else {
    document.getElementById("rustdeskOutput").textContent = "❌ RustDesk is not installed.";
  }
}

// ========== FILES ==========
async function loadFiles() {
  const pathInput = document.getElementById("filePath");
  const path = pathInput.value.trim();
  const list = document.getElementById("fileList");
  const breadcrumb = document.getElementById("fileBreadcrumb");
  
  list.innerHTML = '<li style="justify-content:center"><span class="spinner"></span> Loading...</li>';
  
  const data = await apiGet("/api/files?path=" + encodeURIComponent(path));
  
  if (data.error) {
    list.innerHTML = '<li style="color:var(--danger);justify-content:center">❌ ' + data.error + '</li>';
    return;
  }
  
  // Breadcrumb
  const parts = data.path.split("/").filter(Boolean);
  breadcrumb.innerHTML = '<span class="sep">/</span> ';
  let cumPath = "";
  breadcrumb.innerHTML += '<a href="#" onclick="goToDir(\'/\')" style="color:var(--accent);text-decoration:none">~</a> <span class="sep">/</span> ';
  for (const p of parts) {
    cumPath += "/" + p;
    breadcrumb.innerHTML += '<a href="#" onclick="goToDir(\'' + cumPath + '\')" style="color:var(--accent);text-decoration:none">' + p + '</a> <span class="sep">/</span> ';
  }
  
  // File list
  list.innerHTML = "";
  if (data.parent) {
    const li = document.createElement("li");
    li.innerHTML = '<span class="icon">📂</span><span class="name" style="color:var(--accent)">..</span>';
    li.onclick = () => goToDir(data.parent);
    list.appendChild(li);
  }
  
  for (const item of data.items) {
    const li = document.createElement("li");
    const icon = item.is_dir ? "📁" : "📄";
    li.innerHTML = '<span class="icon">' + icon + '</span><span class="name">' + escapeHtml(item.name) + '</span><span class="size">' + (item.is_dir ? "" : item.size_hr) + '</span>';
    if (item.is_dir) {
      li.onclick = () => goToDir(data.path + "/" + item.name);
    } else {
      const dlBtn = document.createElement("span");
      dlBtn.className = "actions";
      dlBtn.innerHTML = '<button class="btn btn-outline btn-sm" onclick="event.stopPropagation();downloadFile(\'' + data.path + "/" + item.name + '\')">📥 DL</button>';
      li.appendChild(dlBtn);
    }
    list.appendChild(li);
  }
}

function goToDir(path) {
  document.getElementById("filePath").value = path;
  loadFiles();
}

function downloadFile(path) {
  const a = document.createElement("a");
  a.href = apiUrl("/api/download?path=" + encodeURIComponent(path));
  a.download = path.split("/").pop();
  a.click();
  showToast("📥 Downloading " + path.split("/").pop());
}

// ========== KEYBOARD SHORTCUTS ==========
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key === "l") { e.preventDefault(); navigate("dashboard"); }
  if (e.ctrlKey && e.key === "t") { e.preventDefault(); navigate("terminal"); document.getElementById("cmdInput").focus(); }
});

// Re-check sidebar state on resize
window.addEventListener("resize", () => {
  if (window.innerWidth > 768) document.getElementById("sidebar").classList.remove("open");
});
</script>
</body>
</html>"""


@app.route("/")
def index():
    """Serve the web UI."""
    return HTML_TEMPLATE


# ============ MAIN ============

def start_server():
    """Start the Flask web server."""
    print(f"🌐 Web Panel starting on http://{HOST}:{WEB_PORT}")
    print(f"🔐 Password: {PASSWORD}")
    print(f"📱 Access from Telegram browser or any device on the network")
    print(f"   Local:  http://127.0.0.1:{WEB_PORT}")
    print(f"   Remote: http://<your-ip>:{WEB_PORT}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Disable Flask's default logging for cleaner output
    import logging as log
    log.getLogger("werkzeug").setLevel(log.ERROR)
    
    app.run(host=HOST, port=WEB_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    start_server()
