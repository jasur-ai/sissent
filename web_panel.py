#!/usr/bin/env python3
"""
guid_erbot — Sleek Web Dashboard
=================================
Modern dark-themed control panel for remote system monitoring & management.
All-in-one: system stats, process manager, terminal, file browser, controls.

Run:  python3 web_panel.py
Visit: http://localhost:5000
Login: osboxes.org
"""

import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import threading
import zipfile
import io
import base64
from datetime import datetime
from pathlib import Path
from functools import wraps
from flask import Flask, jsonify, request, send_file, render_template_string

app = Flask(__name__)

PASSWORD = os.environ.get("WEB_PASSWORD", "osboxes.org")
PORT = int(os.environ.get("PORT", 5000))

# ==============================================================
# UTILITY
# ==============================================================

def run_shell(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip() or "(empty)"
    except subprocess.TimeoutExpired:
        return "(timeout)"
    except Exception as e:
        return f"(error: {e})"

def format_bytes(b):
    for unit in ['B','KB','MB','GB','TB']:
        if b < 1024: return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"

def check_auth():
    auth = request.headers.get("X-Password", request.args.get("pwd", ""))
    return auth == PASSWORD

def require_auth(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not check_auth():
            return jsonify({"error": "unauthorized"}), 401
        return f(*a, **kw)
    return wrapper

# ==============================================================
# API ENDPOINTS
# ==============================================================

@app.route("/api/auth")
def api_auth():
    return jsonify({"ok": check_auth()})

@app.route("/api/sysinfo")
@require_auth
def api_sysinfo():
    cpu = run_shell("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
    cpu_model = run_shell("lscpu | grep 'Model name' | cut -d: -f2 | xargs")
    mem = run_shell("free -h | grep Mem | awk '{print $3\"/\"$2}'")
    mem_pct = run_shell("free | grep Mem | awk '{printf \"%.0f\", $3/$2 * 100}'")
    disk = run_shell("df -h / | tail -1 | awk '{print $3\"/\"$2\" (\"$5\")\"}'")
    disk_pct = run_shell("df / | tail -1 | awk '{print $5+0}'")
    uptime = run_shell("uptime -p | sed 's/up //'")
    hostname = platform.node()
    os_info = run_shell("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'")
    kernel = run_shell("uname -r")
    processes = run_shell("ps aux | wc -l")
    return jsonify({
        "cpu": cpu, "cpu_model": cpu_model, "mem": mem, "mem_pct": mem_pct,
        "disk": disk, "disk_pct": disk_pct, "uptime": uptime,
        "hostname": hostname, "os": os_info, "kernel": kernel, "processes": processes
    })

@app.route("/api/cpu")
@require_auth
def api_cpu():
    info = run_shell("lscpu | grep -E 'Model name|CPU\\(s\\)|MHz|Thread|Core' | head -6")
    usage = run_shell("top -bn1 | grep 'Cpu(s)'")
    load = run_shell("cat /proc/loadavg")
    temps = run_shell("cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{t=$1/1000; printf \"%.1f°C \", t}' || echo 'N/A'")
    freq = run_shell("lscpu | grep 'MHz' | head -1 | awk '{print $3}'")
    return jsonify({"info": info, "usage": usage, "load": load, "temps": temps, "freq": freq})

@app.route("/api/memory")
@require_auth
def api_memory():
    mem = run_shell("free -h | grep -E '^Mem:|^Swap:'")
    details = run_shell("cat /proc/meminfo | grep -E 'MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree|Cached|Buffers'")
    top = run_shell("ps aux --sort=-%mem | head -8 | awk 'NR>1{printf \"%s %s %s%%\\n\", $11, $4, $4}'")
    return jsonify({"mem": mem, "details": details, "top": top})

@app.route("/api/disk")
@require_auth
def api_disk():
    df = run_shell("df -h | grep -E '^/dev|tmpfs' | column -t")
    inodes = run_shell("df -i 2>/dev/null | grep -E '^/dev' | column -t")
    mounts = run_shell("mount | grep '^/dev' | awk '{print $1, $3, $5}'")
    return jsonify({"df": df, "inodes": inodes, "mounts": mounts})

@app.route("/api/network")
@require_auth
def api_network():
    interfaces = run_shell("ip -br addr | grep -v lo")
    wifi = run_shell("iwconfig 2>/dev/null | grep -E 'ESSID|Signal' || echo 'No WiFi'")
    dns = run_shell("cat /etc/resolv.conf 2>/dev/null | grep nameserver | head -3 || echo 'N/A'")
    routing = run_shell("ip route | head -5")
    wan = run_shell("curl -s ifconfig.me 2>/dev/null || echo 'Unavailable'")
    ports = run_shell("ss -tlnp 2>/dev/null | tail -15 || netstat -tlnp 2>/dev/null | tail -15")
    return jsonify({"interfaces": interfaces, "wifi": wifi, "dns": dns, "routing": routing, "wan": wan, "ports": ports})

@app.route("/api/processes")
@require_auth
def api_processes():
    procs = run_shell("ps aux --sort=-%mem | head -25 | awk 'NR==1{print \"USER PID %CPU %MEM VSZ RSS CMD\"} NR>1{printf \"%s %s %s%% %s%% %s %s\\n\", $1,$2,$3,$4,$5,$11}'")
    total = run_shell("ps aux | wc -l")
    thread_count = run_shell("ps aux | wc -l; ps -eLf | wc -l")
    return jsonify({"procs": procs, "total": total, "threads": thread_count})

@app.route("/api/services")
@require_auth
def api_services():
    running = run_shell("systemctl list-units --type=service --state=running --no-legend 2>/dev/null | awk '{print $1}' | head -30 || echo 'N/A'")
    failed = run_shell("systemctl list-units --type=service --state=failed --no-legend 2>/dev/null | awk '{print $1}' | head -10 || echo 'None'")
    count = run_shell("systemctl list-units --type=service --state=running --no-legend 2>/dev/null | wc -l")
    return jsonify({"running": running, "failed": failed, "count": count})

@app.route("/api/temperature")
@require_auth
def api_temperature():
    temps = run_shell("cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | awk '{printf \"%.1f°C\\n\", $1/1000}' || echo 'No sensors'")
    gpu = run_shell("nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null | head -1 || echo 'No NVIDIA GPU'")
    cpu_freq = run_shell("lscpu | grep 'MHz' | head -1 | awk '{print $3}'")
    return jsonify({"temps": temps, "gpu": gpu, "cpu_freq": cpu_freq})

@app.route("/api/uptime")
@require_auth
def api_uptime():
    uptime = run_shell("uptime -p | sed 's/up //'")
    boot = run_shell("who -b | awk '{print $3, $4}'")
    users = run_shell("who | awk '{print $1}' | sort -u | tr '\\n' ' '")
    return jsonify({"uptime": uptime, "boot": boot, "users": users})

@app.route("/api/screenshot")
@require_auth
def api_screenshot():
    path = "/tmp/guid_screenshot.png"
    methods = [["import","-window","root",path],["scrot",path],["gnome-screenshot","-f",path]]
    for cmd in methods:
        if shutil.which(cmd[0]):
            subprocess.run(cmd, timeout=10, capture_output=True)
            if Path(path).exists() and Path(path).stat().st_size > 1000:
                with open(path, "rb") as f:
                    data = base64.b64encode(f.read()).decode()
                os.remove(path)
                return jsonify({"ok": True, "image": data})
    return jsonify({"ok": False, "error": "No screenshot tool available"})

@app.route("/api/lock", methods=["POST"])
@require_auth
def api_lock():
    subprocess.Popen(["i3lock","-c","1a1a2e","--nofork"], env={"DISPLAY":":0"})
    time.sleep(1)
    locked = run_shell("pgrep -x i3lock || echo 'no'")
    return jsonify({"ok": "no" not in locked})

@app.route("/api/unlock", methods=["POST"])
@require_auth
def api_unlock():
    if not shutil.which("xdotool"):
        return jsonify({"ok": False, "error": "xdotool not installed"})
    locked = run_shell("pgrep -x i3lock || echo 'no'")
    if "no" in locked:
        return jsonify({"ok": False, "error": "not locked"})
    subprocess.run(["xdotool","type","--delay","20","osboxes.org"], timeout=5, env={"DISPLAY":":0"})
    time.sleep(0.3)
    subprocess.run(["xdotool","key","Return"], timeout=3, env={"DISPLAY":":0"})
    time.sleep(0.5)
    still = run_shell("pgrep -x i3lock || echo 'unlocked'")
    return jsonify({"ok": "unlocked" in still})

@app.route("/api/notify", methods=["POST"])
@require_auth
def api_notify():
    msg = (request.json or {}).get("message", "Hello from dashboard!")
    try:
        subprocess.run(["notify-send","📱 Dashboard",msg,"-t","5000"], timeout=5)
    except:
        run_shell(f'echo "NOTIFY: {msg}" | wall 2>/dev/null')
    return jsonify({"ok": True})

@app.route("/api/shell", methods=["POST"])
@require_auth
def api_shell():
    cmd = (request.json or {}).get("command", "")
    if not cmd:
        return jsonify({"ok": False, "error": "empty command"})
    output = run_shell(cmd, timeout=60)
    return jsonify({"ok": True, "output": output})

@app.route("/api/sound", methods=["GET", "POST"])
@require_auth
def api_sound():
    if request.method == "POST":
        action = (request.json or {}).get("action", "get")
        if action == "up": run_shell("amixer set Master 5%+ 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ +5%")
        elif action == "down": run_shell("amixer set Master 5%- 2>/dev/null || pactl set-sink-volume @DEFAULT_SINK@ -5%")
        elif action == "mute": run_shell("amixer set Master mute 2>/dev/null || pactl set-sink-mute @DEFAULT_SINK@ 1")
        elif action == "unmute": run_shell("amixer set Master unmute 2>/dev/null || pactl set-sink-mute @DEFAULT_SINK@ 0")
        return jsonify({"ok": True})
    vol = run_shell("amixer get Master 2>/dev/null | grep -o '[0-9]*%' | head -1 || echo 'N/A'")
    mute = run_shell("amixer get Master 2>/dev/null | grep -o '\\[on\\]\\|\\[off\\]' | head -1 || echo ''")
    return jsonify({"vol": vol, "muted": "off" in mute})

@app.route("/api/vnc", methods=["GET"])
@require_auth
def api_vnc():
    running = run_shell("pgrep -a x11vnc 2>/dev/null || echo 'Not running'")
    port = run_shell("ss -tlnp | grep 5900 || echo 'Not listening'")
    return jsonify({"running": "x11vnc" in running, "detail": running, "port": port})

@app.route("/api/vnc", methods=["POST"])
@require_auth
def api_vnc_control():
    action = (request.json or {}).get("action", "status")
    if action == "start":
        if not shutil.which("x11vnc"):
            return jsonify({"ok": False, "error": "x11vnc not installed"})
        run_shell("x11vnc -display :0 -forever -shared -rfbport 5900 -auth guess -o /tmp/x11vnc.log 2>/dev/null & echo started")
        time.sleep(1)
        return jsonify({"ok": True})
    elif action == "stop":
        run_shell("pkill x11vnc 2>/dev/null")
        return jsonify({"ok": True})
    return jsonify({"ok": False})

@app.route("/api/rustdesk")
@require_auth
def api_rustdesk():
    id_info = run_shell("rustdesk --get-id 2>/dev/null || cat /etc/rustdesk/id 2>/dev/null || echo 'Not installed'")
    status = run_shell("systemctl status rustdesk 2>/dev/null | grep Active || echo 'N/A'")
    return jsonify({"id": id_info, "status": status})

@app.route("/api/files", methods=["GET"])
@require_auth
def api_files():
    path = request.args.get("path", "/home/osboxes")
    if not Path(path).exists():
        return jsonify({"error": "path not found", "path": path}), 404
    items = []
    try:
        for entry in sorted(Path(path).iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                stat = entry.stat()
                items.append({
                    "name": entry.name, "is_dir": entry.is_dir(),
                    "size": stat.st_size, "size_hr": format_bytes(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            except: pass
    except PermissionError:
        return jsonify({"error": "permission denied", "path": path}), 403
    return jsonify({"path": path, "parent": str(Path(path).parent), "items": items})

@app.route("/api/download", methods=["GET"])
@require_auth
def api_download():
    path = request.args.get("path", "")
    if not Path(path).exists():
        return jsonify({"error": "not found"}), 404
    p = Path(path)
    if p.is_dir():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in p.rglob("*"):
                try: z.write(f, f.relative_to(p))
                except: pass
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=f"{p.name}.zip")
    return send_file(str(p), as_attachment=True)

@app.route("/api/status")
@require_auth
def api_status():
    locked = run_shell("pgrep -x i3lock || echo 'no'")
    vnc = run_shell("pgrep x11vnc || echo 'no'")
    vpn = run_shell("pgrep -f 'wg-quick|openvpn' | grep -v grep || echo 'no'")
    return jsonify({
        "locked": "no" not in locked, "vnc_running": "no" not in vnc,
        "vpn_running": "no" not in vpn
    })

# ==============================================================
# SLEEK DASHBOARD UI
# ==============================================================

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>guid_erbot Dashboard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

  :root {
    --bg: #0a0a0f;
    --surface: #13131a;
    --surface2: #1a1a24;
    --surface3: #22222e;
    --border: #2a2a3a;
    --text: #e8e8f0;
    --text2: #8888a0;
    --accent: #6c5ce7;
    --accent2: #a29bfe;
    --green: #00b894;
    --red: #e17055;
    --yellow: #fdcb6e;
    --blue: #0984e3;
    --radius: 12px;
    --shadow: 0 4px 24px rgba(0,0,0,0.4);
    font-family: 'Inter', -apple-system, sans-serif;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg); color: var(--text); min-height: 100vh;
    display: flex; flex-direction: column;
  }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: var(--surface); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  /* Login Overlay */
  #login-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.85);
    backdrop-filter: blur(12px); display: flex; align-items: center;
    justify-content: center; z-index: 1000; flex-direction: column; gap: 20px;
  }
  #login-overlay.hidden { display: none; }
  #login-overlay h1 { font-size: 2em; font-weight: 800; background: linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  #login-overlay p { color: var(--text2); font-size: 0.95em; }
  .login-box {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 40px; width: 340px;
    box-shadow: var(--shadow); text-align: center;
  }
  .login-box input {
    width: 100%; padding: 14px 16px; background: var(--surface2);
    border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); font-size: 1em; margin: 16px 0;
    transition: border-color 0.2s;
  }
  .login-box input:focus { outline: none; border-color: var(--accent); }
  .login-box button {
    width: 100%; padding: 14px; background: linear-gradient(135deg,var(--accent),var(--accent2));
    border: none; border-radius: 8px; color: white; font-size: 1em;
    font-weight: 600; cursor: pointer; transition: transform 0.15s, box-shadow 0.15s;
  }
  .login-box button:hover { transform: translateY(-1px); box-shadow: 0 4px 20px rgba(108,92,231,0.4); }
  .login-error { color: var(--red); font-size: 0.85em; margin-top: 10px; }

  /* Header */
  header {
    padding: 20px 24px; background: var(--surface);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    position: sticky; top: 0; z-index: 100;
  }
  header h1 { font-size: 1.2em; font-weight: 700; display: flex; align-items: center; gap: 10px; }
  header h1 span { background: linear-gradient(135deg,var(--accent),var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  header .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); display: inline-block; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }
  header .nav { display: flex; gap: 4px; }
  header .nav button {
    background: none; border: none; color: var(--text2); padding: 8px 14px;
    border-radius: 8px; cursor: pointer; font-size: 0.85em; font-weight: 500;
    transition: all 0.15s;
  }
  header .nav button:hover { background: var(--surface2); color: var(--text); }
  header .nav button.active { background: var(--surface3); color: var(--accent2); }

  /* Main Content */
  .main { flex: 1; padding: 24px; max-width: 1400px; margin: 0 auto; width: 100%; }
  .page { display: none; }
  .page.active { display: block; animation: fadeIn 0.3s; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

  /* Grid */
  .grid { display: grid; gap: 16px; }
  .grid-2 { grid-template-columns: 1fr 1fr; }
  .grid-3 { grid-template-columns: 1fr 1fr 1fr; }
  .grid-4 { grid-template-columns: 1fr 1fr 1fr 1fr; }
  @media(max-width:900px){ .grid-2,.grid-3,.grid-4 { grid-template-columns: 1fr; } }
  @media(min-width:901px)and(max-width:1200px){ .grid-3,.grid-4 { grid-template-columns: 1fr 1fr; } }

  /* Cards */
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow);
    transition: border-color 0.2s, transform 0.15s;
  }
  .card:hover { border-color: var(--surface3); }
  .card-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 14px; font-size: 0.85em; color: var(--text2); font-weight: 500;
    text-transform: uppercase; letter-spacing: 0.5px;
  }
  .card-value { font-size: 2em; font-weight: 700; line-height: 1.2; }
  .card-value.small { font-size: 1.2em; }
  .card-label { font-size: 0.8em; color: var(--text2); margin-top: 4px; }
  .card pre {
    background: var(--surface2); padding: 12px; border-radius: 8px;
    font-size: 0.8em; overflow-x: auto; white-space: pre-wrap;
    word-break: break-all; max-height: 300px; overflow-y: auto; color: var(--text2);
  }
  .card pre.data { color: var(--text); font-family: 'JetBrains Mono', monospace; }

  /* Progress Bars */
  .progress-bar {
    height: 8px; background: var(--surface2); border-radius: 4px;
    overflow: hidden; margin: 8px 0;
  }
  .progress-fill {
    height: 100%; border-radius: 4px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    transition: width 0.5s ease;
  }
  .progress-fill.green { background: linear-gradient(90deg, var(--green), #00cec9); }
  .progress-fill.yellow { background: linear-gradient(90deg, var(--yellow), #f39c12); }
  .progress-fill.red { background: linear-gradient(90deg, var(--red), #d63031); }

  /* Stats Row */
  .stat-row { display: flex; justify-content: space-between; margin: 4px 0; font-size: 0.9em; }
  .stat-row .label { color: var(--text2); }
  .stat-row .value { color: var(--text); font-weight: 500; }

  /* Buttons */
  .btn {
    padding: 10px 18px; border: none; border-radius: 8px; cursor: pointer;
    font-size: 0.85em; font-weight: 600; transition: all 0.15s;
    display: inline-flex; align-items: center; gap: 6px;
  }
  .btn-primary { background: linear-gradient(135deg,var(--accent),var(--accent2)); color: white; }
  .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 4px 16px rgba(108,92,231,0.3); }
  .btn-green { background: var(--green); color: white; }
  .btn-green:hover { transform: translateY(-1px); }
  .btn-red { background: var(--red); color: white; }
  .btn-red:hover { transform: translateY(-1px); }
  .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text); }
  .btn-outline:hover { background: var(--surface2); }
  .btn-sm { padding: 6px 12px; font-size: 0.78em; }
  .btn-group { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }

  /* Shell Terminal */
  .terminal {
    background: #000; border: 1px solid var(--border); border-radius: var(--radius);
    font-family: 'JetBrains Mono', monospace; font-size: 0.85em; overflow: hidden;
  }
  .terminal-bar {
    padding: 10px 14px; background: var(--surface2);
    display: flex; align-items: center; gap: 8px; border-bottom: 1px solid var(--border);
  }
  .terminal-dot { width: 10px; height: 10px; border-radius: 50%; }
  .terminal-dot.red { background: #ff5f57; }
  .terminal-dot.yellow { background: #ffbd2e; }
  .terminal-dot.green { background: #28c840; }
  .terminal-output {
    padding: 14px; min-height: 260px; max-height: 400px; overflow-y: auto;
    color: #00ff88; line-height: 1.5;
  }
  .terminal-input-row {
    display: flex; border-top: 1px solid var(--border);
  }
  .terminal-input-row input {
    flex: 1; padding: 12px 14px; background: #000; border: none;
    color: #00ff88; font-family: inherit; font-size: 0.9em;
  }
  .terminal-input-row input:focus { outline: none; }
  .terminal-input-row button {
    padding: 12px 20px; background: var(--surface2); border: none;
    border-left: 1px solid var(--border); color: var(--text); cursor: pointer;
    font-weight: 600; transition: background 0.15s;
  }
  .terminal-input-row button:hover { background: var(--surface3); }

  /* File Browser */
  .file-list { width: 100%; border-collapse: collapse; font-size: 0.85em; }
  .file-list th { text-align: left; padding: 8px 12px; color: var(--text2); font-weight: 500; border-bottom: 1px solid var(--border); }
  .file-list td { padding: 8px 12px; border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.1s; }
  .file-list tr:hover td { background: var(--surface2); }
  .file-list .folder { color: var(--accent2); }
  .file-list .file { color: var(--text); }
  .file-path { padding: 10px 0; color: var(--text2); font-size: 0.85em; display: flex; align-items: center; gap: 8px; }
  .file-path span { color: var(--accent2); }

  /* Logout */
  .logout-btn {
    position: fixed; bottom: 20px; right: 20px; z-index: 50;
    padding: 10px 16px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; color: var(--text2); cursor: pointer; font-size: 0.8em;
    transition: all 0.15s; backdrop-filter: blur(8px);
  }
  .logout-btn:hover { color: var(--red); border-color: var(--red); }

  /* Loading */
  .loading { color: var(--text2); font-size: 0.85em; display: flex; align-items: center; gap: 8px; }
  .spinner { width: 16px; height: 16px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.6s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Alerts / Toasts */
  .toast {
    position: fixed; top: 20px; right: 20px; z-index: 2000;
    padding: 14px 20px; background: var(--surface); border: 1px solid var(--green);
    border-radius: var(--radius); color: var(--text); font-size: 0.9em;
    box-shadow: var(--shadow); animation: slideIn 0.3s;
    max-width: 360px;
  }
  .toast.error { border-color: var(--red); }
  @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

  .badge {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 0.75em; font-weight: 600;
  }
  .badge-green { background: rgba(0,184,148,0.15); color: var(--green); }
  .badge-red { background: rgba(225,112,85,0.15); color: var(--red); }
  .badge-yellow { background: rgba(253,203,110,0.15); color: var(--yellow); }

  /* Image preview */
  .img-preview { max-width: 100%; border-radius: 8px; cursor: pointer; transition: transform 0.2s; }
  .img-preview:hover { transform: scale(1.02); }
</style>
</head>
<body>

<!-- Login -->
<div id="login-overlay">
  <div class="login-box">
    <h1 style="background:linear-gradient(135deg,#6c5ce7,#a29bfe);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:1.6em;font-weight:800;margin-bottom:4px;">guid_erbot</h1>
    <p style="color:#8888a0;font-size:0.85em;margin-bottom:8px;">Remote System Dashboard</p>
    <input type="password" id="pwd-input" placeholder="Enter password" onkeydown="if(event.key==='Enter')login()">
    <button onclick="login()">Unlock Dashboard</button>
    <div id="login-err" class="login-error"></div>
  </div>
</div>

<!-- Header -->
<header>
  <h1><span class="status-dot"></span> <span>guid_erbot</span> <span style="font-weight:400;color:#8888a0;font-size:0.75em;">v2.0</span></h1>
  <div class="nav" id="nav">
    <button class="active" data-page="overview">📊 Overview</button>
    <button data-page="system">💻 System</button>
    <button data-page="network">🌐 Network</button>
    <button data-page="processes">📋 Processes</button>
    <button data-page="terminal">⌨️ Terminal</button>
    <button data-page="files">📁 Files</button>
    <button data-page="controls">🎮 Controls</button>
  </div>
</header>

<div class="main">

  <!-- ===== PAGE: Overview ===== -->
  <div class="page active" id="page-overview">
    <div class="grid grid-4" id="overview-stats"></div>
    <div style="margin-top:16px">
      <div class="grid grid-2">
        <div class="card">
          <div class="card-header">📊 CPU Usage</div>
          <div class="card-value" id="ov-cpu">—</div>
          <div class="progress-bar"><div class="progress-fill" id="ov-cpu-bar" style="width:0%"></div></div>
          <div class="stat-row"><span class="label">Model</span><span class="value" id="ov-cpu-model">—</span></div>
          <div class="stat-row"><span class="label">Load</span><span class="value" id="ov-load">—</span></div>
          <div class="stat-row"><span class="label">Temp</span><span class="value" id="ov-temp">—</span></div>
        </div>
        <div class="card">
          <div class="card-header">🧠 Memory</div>
          <div class="card-value" id="ov-mem">—</div>
          <div class="progress-bar"><div class="progress-fill green" id="ov-mem-bar" style="width:0%"></div></div>
          <div class="stat-row"><span class="label">Total / Used</span><span class="value" id="ov-mem-detail">—</span></div>
          <div style="margin-top:10px;" id="ov-mem-top"></div>
        </div>
        <div class="card">
          <div class="card-header">💾 Disk</div>
          <div class="card-value" id="ov-disk">—</div>
          <div class="progress-bar"><div class="progress-fill yellow" id="ov-disk-bar" style="width:0%"></div></div>
          <div class="stat-row"><span class="label">Mount</span><span class="value">/</span></div>
          <pre id="ov-disk-mounts" style="margin-top:8px;">—</pre>
        </div>
        <div class="card">
          <div class="card-header">⏱️ System</div>
          <div class="card-value" id="ov-uptime" style="font-size:1.3em;">—</div>
          <div class="stat-row" style="margin-top:12px;"><span class="label">Hostname</span><span class="value" id="ov-host">—</span></div>
          <div class="stat-row"><span class="label">IP</span><span class="value" id="ov-ip">—</span></div>
          <div class="stat-row"><span class="label">OS</span><span class="value" id="ov-os">—</span></div>
          <div class="stat-row"><span class="label">Kernel</span><span class="value" id="ov-kernel">—</span></div>
          <div class="stat-row"><span class="label">Processes</span><span class="value" id="ov-procs">—</span></div>
        </div>
      </div>
    </div>
  </div>

  <!-- ===== PAGE: System ===== -->
  <div class="page" id="page-system">
    <div class="grid grid-2">
      <div class="card">
        <div class="card-header">🔧 CPU Info</div>
        <pre class="data" id="sys-cpu">Loading...</pre>
      </div>
      <div class="card">
        <div class="card-header">🌡️ Temperatures</div>
        <pre class="data" id="sys-temp">Loading...</pre>
        <div class="btn-group"><button class="btn btn-outline btn-sm" onclick="loadSystem()">🔄 Refresh</button></div>
      </div>
      <div class="card">
        <div class="card-header">📊 Memory</div>
        <pre class="data" id="sys-mem">Loading...</pre>
      </div>
      <div class="card">
        <div class="card-header">💾 Disk</div>
        <pre class="data" id="sys-disk">Loading...</pre>
      </div>
      <div class="card">
        <div class="card-header">⚙️ Services</div>
        <div class="stat-row"><span class="label">Running</span><span class="value" id="sys-svc-count">—</span></div>
        <pre class="data" id="sys-services" style="margin-top:8px;">Loading...</pre>
      </div>
      <div class="card">
        <div class="card-header">📸 Screenshot</div>
        <div id="sys-shot-area"><p style="color:var(--text2);font-size:0.9em;">Click to capture the current desktop screen.</p></div>
        <div class="btn-group"><button class="btn btn-primary btn-sm" onclick="takeScreenshot()">📸 Take Screenshot</button></div>
      </div>
    </div>
  </div>

  <!-- ===== PAGE: Network ===== -->
  <div class="page" id="page-network">
    <div class="grid grid-2">
      <div class="card">
        <div class="card-header">📡 Interfaces</div>
        <pre class="data" id="net-interfaces">Loading...</pre>
      </div>
      <div class="card">
        <div class="card-header">📶 WiFi</div>
        <pre class="data" id="net-wifi">Loading...</pre>
      </div>
      <div class="card">
        <div class="card-header">🌍 Routing</div>
        <pre class="data" id="net-routing">Loading...</pre>
      </div>
      <div class="card">
        <div class="card-header">🔓 Open Ports</div>
        <pre class="data" id="net-ports">Loading...</pre>
        <div class="btn-group"><button class="btn btn-outline btn-sm" onclick="loadNetwork()">🔄 Refresh</button></div>
      </div>
    </div>
    <div class="card" style="margin-top:16px;">
      <div class="card-header">🌐 Network Details</div>
      <div class="grid grid-3" id="net-details"></div>
    </div>
  </div>

  <!-- ===== PAGE: Processes ===== -->
  <div class="page" id="page-processes">
    <div class="card">
      <div class="card-header">
        <span>📋 Running Processes</span>
        <div class="btn-group" style="margin:0">
          <span id="proc-count" style="color:var(--text2);font-size:0.85em;"></span>
          <button class="btn btn-outline btn-sm" onclick="loadProcesses()">🔄 Refresh</button>
        </div>
      </div>
      <pre class="data" id="proc-list" style="max-height:500px;">Loading...</pre>
    </div>
  </div>

  <!-- ===== PAGE: Terminal ===== -->
  <div class="page" id="page-terminal">
    <div class="card">
      <div class="card-header">⌨️ Remote Terminal</div>
      <div class="terminal">
        <div class="terminal-bar">
          <span class="terminal-dot red"></span><span class="terminal-dot yellow"></span><span class="terminal-dot green"></span>
          <span style="margin-left:8px;color:#8888a0;font-size:0.8em;">root@guid_erbot — bash</span>
        </div>
        <div class="terminal-output" id="term-output">
          <span style="color:#888;">Welcome to guid_erbot remote terminal</span><br>
          <span style="color:#888;">Type a command and press Enter...</span><br><br>
        </div>
        <div class="terminal-input-row">
          <span style="padding:12px 0 12px 14px;color:#00ff88;font-size:0.9em;">$</span>
          <input type="text" id="term-input" placeholder="type command..." autocomplete="off" onkeydown="if(event.key==='Enter')runCommand()">
          <button onclick="runCommand()">⏎ Run</button>
        </div>
      </div>
    </div>
  </div>

  <!-- ===== PAGE: Files ===== -->
  <div class="page" id="page-files">
    <div class="card">
      <div class="card-header">
        <span>📁 File Browser</span>
        <div style="display:flex;gap:8px;">
          <input type="text" id="file-path-input" value="/home/osboxes" style="flex:1;padding:6px 10px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:0.85em;">
          <button class="btn btn-outline btn-sm" onclick="browseFiles()">📂 Browse</button>
        </div>
      </div>
      <div class="file-path" id="file-breadcrumb"><span>📁</span><span id="file-current-path">/home/osboxes</span></div>
      <table class="file-list" id="file-table"><tbody id="file-tbody"></tbody></table>
    </div>
  </div>

  <!-- ===== PAGE: Controls ===== -->
  <div class="page" id="page-controls">
    <div class="grid grid-2">
      <div class="card">
        <div class="card-header">🔒 Screen Lock</div>
        <div style="display:flex;align-items:center;gap:12px;">
          <span style="font-size:1.2em;" id="ctrl-lock-status">🔓 Unlocked</span>
          <span class="badge badge-green" id="ctrl-lock-badge">Active</span>
        </div>
        <div class="btn-group">
          <button class="btn btn-primary btn-sm" onclick="lock()">🔒 Lock</button>
          <button class="btn btn-green btn-sm" onclick="unlock()">🔓 Unlock</button>
        </div>
      </div>
      <div class="card">
        <div class="card-header">🔊 Sound</div>
        <div style="display:flex;align-items:center;gap:12px;">
          <span style="font-size:1.5em;" id="ctrl-vol-icon">🔊</span>
          <span id="ctrl-vol">—</span>
          <span class="badge badge-green" id="ctrl-mute-badge">Active</span>
        </div>
        <div class="btn-group">
          <button class="btn btn-outline btn-sm" onclick="sound('down')">🔉 Down</button>
          <button class="btn btn-outline btn-sm" onclick="sound('mute')">🔇 Mute</button>
          <button class="btn btn-outline btn-sm" onclick="sound('up')">🔊 Up</button>
          <button class="btn btn-outline btn-sm" onclick="sound('unmute')">🔊 Unmute</button>
        </div>
      </div>
      <div class="card">
        <div class="card-header">🖥️ VNC Server</div>
        <div id="ctrl-vnc-status">Checking...</div>
        <div class="btn-group">
          <button class="btn btn-primary btn-sm" onclick="vnc('start')">▶ Start</button>
          <button class="btn btn-red btn-sm" onclick="vnc('stop')">⏹ Stop</button>
        </div>
      </div>
      <div class="card">
        <div class="card-header">🔐 VPN</div>
        <div id="ctrl-vpn-status">Checking...</div>
        <div class="btn-group">
          <button class="btn btn-primary btn-sm" onclick="vpnStop()">⏹ Disconnect</button>
        </div>
      </div>
      <div class="card">
        <div class="card-header">🧦 SOCKS5 Proxy</div>
        <div id="ctrl-socks5-status">Checking...</div>
        <div class="btn-group">
          <button class="btn btn-primary btn-sm" onclick="socks5('start')">▶ Start</button>
          <button class="btn btn-red btn-sm" onclick="socks5('stop')">⏹ Stop</button>
        </div>
      </div>
      <div class="card">
        <div class="card-header">🔔 Notification</div>
        <div style="display:flex;gap:8px;">
          <input type="text" id="notif-msg" value="Hello from dashboard!" style="flex:1;padding:10px;background:var(--surface2);border:1px solid var(--border);border-radius:8px;color:var(--text);">
          <button class="btn btn-primary btn-sm" onclick="sendNotif()">Send</button>
        </div>
      </div>
    </div>
  </div>

</div>

<button class="logout-btn" onclick="logout()">🔒 Lock Dashboard</button>

<script>
// ===== AUTH =====
const PWD = sessionStorage.getItem('dash_pwd') || '';

function login() {
  const pwd = document.getElementById('pwd-input').value;
  fetch('/api/auth?pwd='+encodeURIComponent(pwd)).then(r=>r.json()).then(d=>{
    if(d.ok) { sessionStorage.setItem('dash_pwd',pwd); document.getElementById('login-overlay').classList.add('hidden'); init(); }
    else document.getElementById('login-err').textContent='❌ Wrong password';
  });
}
function logout() { sessionStorage.removeItem('dash_pwd'); document.getElementById('login-overlay').classList.remove('hidden'); }
if(PWD) { fetch('/api/auth?pwd='+encodeURIComponent(PWD)).then(r=>r.json()).then(d=>{ if(d.ok){document.getElementById('login-overlay').classList.add('hidden');init();} }); }

function headers() { return {'X-Password': sessionStorage.getItem('dash_pwd')||''}; }
function api(url) { return fetch(url,{headers:headers()}).then(r=>r.json()); }
function apiPost(url,body) { return fetch(url,{method:'POST',headers:{...headers(),'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()); }

function toast(msg,isError) {
  const t=document.createElement('div'); t.className='toast'+(isError?' error':''); t.textContent=msg;
  document.body.appendChild(t); setTimeout(()=>t.remove(),3000);
}

// ===== NAVIGATION =====
document.querySelectorAll('#nav button').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('#nav button').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('page-'+btn.dataset.page).classList.add('active');
  });
});

// ===== OVERVIEW =====
async function loadOverview() {
  const d = await api('/api/sysinfo');
  document.getElementById('ov-cpu').textContent = d.cpu+'%';
  document.getElementById('ov-cpu-bar').style.width = Math.min(parseFloat(d.cpu)||0,100)+'%';
  document.getElementById('ov-cpu-model').textContent = d.cpu_model||'—';
  document.getElementById('ov-mem').textContent = d.mem||'—';
  document.getElementById('ov-mem-bar').style.width = Math.min(parseFloat(d.mem_pct)||0,100)+'%';
  document.getElementById('ov-mem-detail').textContent = d.mem||'—';
  document.getElementById('ov-disk').textContent = d.disk||'—';
  document.getElementById('ov-disk-bar').style.width = Math.min(parseFloat(d.disk_pct)||0,100)+'%';
  document.getElementById('ov-uptime').textContent = d.uptime||'—';
  document.getElementById('ov-host').textContent = d.hostname||'—';
  // Load IP from network endpoint
  api('/api/network').then(n=>{
    const ifaces = (n.interfaces||'').split('\\n').filter(l=>l.trim());
    const firstIp = ifaces.length>0 ? ifaces[0].split(/\\s+/)[1]||'—' : '—';
    document.getElementById('ov-ip').textContent = firstIp;
  });
  document.getElementById('ov-os').textContent = (d.os||'—').substring(0,40);
  document.getElementById('ov-kernel').textContent = d.kernel||'—';
  document.getElementById('ov-procs').textContent = d.processes||'—';

  // Load additional data
  const cpuD = await api('/api/cpu');
  document.getElementById('ov-load').textContent = cpuD.load||'—';
  document.getElementById('ov-temp').textContent = cpuD.temps||'—';

  const memD = await api('/api/memory');
  document.getElementById('ov-mem-top').innerHTML = '<pre style="font-size:0.78em;color:#8888a0;margin-top:6px;">'+(memD.top||'—')+'</pre>';
}

// ===== SYSTEM =====
async function loadSystem() {
  const c = await api('/api/cpu');
  document.getElementById('sys-cpu').textContent = c.info+'\n\nUsage: '+c.usage+'\nLoad: '+c.load+'\nTemp: '+c.temps+'\nFreq: '+c.freq+' MHz';
  const t = await api('/api/temperature');
  document.getElementById('sys-temp').textContent = 'Sensors:\n'+t.temps+'\n\nGPU: '+t.gpu+'\n\nCPU Freq: '+t.cpu_freq+' MHz';
  const m = await api('/api/memory');
  document.getElementById('sys-mem').textContent = m.mem+'\n\nDetails:\n'+m.details+'\n\nTop RAM:\n'+m.top;
  const d = await api('/api/disk');
  document.getElementById('sys-disk').textContent = d.df+'\n\nInodes:\n'+d.inodes;
  const svc = await api('/api/services');
  document.getElementById('sys-svc-count').textContent = svc.count+' running';
  document.getElementById('sys-services').textContent = svc.running+'\n\nFailed:\n'+svc.failed;
}
function takeScreenshot() {
  document.getElementById('sys-shot-area').innerHTML = '<div class="loading"><div class="spinner"></div>Capturing...</div>';
  api('/api/screenshot').then(d=>{
    if(d.ok) document.getElementById('sys-shot-area').innerHTML = '<img src="data:image/png;base64,'+d.image+'" class="img-preview" onclick="window.open(this.src)">';
    else document.getElementById('sys-shot-area').innerHTML = '<p style="color:var(--red);">❌ '+d.error+'</p>';
  });
}

// ===== NETWORK =====
async function loadNetwork() {
  const n = await api('/api/network');
  document.getElementById('net-interfaces').textContent = n.interfaces||'—';
  document.getElementById('net-wifi').textContent = n.wifi||'—';
  document.getElementById('net-routing').textContent = n.routing||'—';
  document.getElementById('net-ports').textContent = n.ports||'—';
  document.getElementById('net-details').innerHTML = `
    <div class="card"><div class="card-header">🌍 WAN IP</div><div class="card-value small">${n.wan||'—'}</div></div>
    <div class="card"><div class="card-header">📡 DNS</div><div class="card-value small"><pre style="font-size:0.8em;">${n.dns||'—'}</pre></div></div>
    <div class="card"><div class="card-header">🔓 Ports</div><div class="card-value small" style="font-size:0.9em;">Listening services</div></div>
  `;
}

// ===== PROCESSES =====
async function loadProcesses() {
  const p = await api('/api/processes');
  document.getElementById('proc-list').textContent = p.procs||'No data';
  document.getElementById('proc-count').textContent = 'Total: '+p.total+' processes';
}

// ===== TERMINAL =====
function runCommand() {
  const input = document.getElementById('term-input');
  const cmd = input.value.trim();
  if(!cmd) return;
  const out = document.getElementById('term-output');
  // Echo command
  const promptSpan = document.createElement('span');
  promptSpan.style.cssText = 'color:#a29bfe;';
  promptSpan.textContent = '$ ';
  const cmdSpan = document.createElement('span');
  cmdSpan.style.cssText = 'color:#fff;';
  cmdSpan.textContent = cmd;
  out.appendChild(promptSpan);
  out.appendChild(cmdSpan);
  out.appendChild(document.createElement('br'));
  // Loading indicator
  const loadSpan = document.createElement('div');
  loadSpan.className = 'term-loading';
  loadSpan.style.cssText = 'color:#888;';
  loadSpan.textContent = '⏳ Running...';
  out.appendChild(loadSpan);
  out.scrollTop = out.scrollHeight;
  input.value = '';
  apiPost('/api/shell',{command: cmd}).then(d=>{
    out.innerHTML = out.innerHTML.replace('<span style="color:#888;">⏳ Running...</span><br>','');
    const output = (d.output||'No output').replace(/</g,'&lt;').replace(/\\n/g,'<br>');
    out.innerHTML += '<span style="color:#00ff88;">'+output+'</span><br><br>';
    out.scrollTop = out.scrollHeight;
  }).catch(()=>{
    out.innerHTML = out.innerHTML.replace('<span style="color:#888;">⏳ Running...</span><br>','');
    out.innerHTML += '<span style="color:#e17055;">Error running command</span><br><br>';
  });
}

// ===== FILES =====
async function browseFiles(path) {
  if(!path) path = document.getElementById('file-path-input').value;
  const d = await api('/api/files?path='+encodeURIComponent(path)+'&pwd='+encodeURIComponent(sessionStorage.getItem('dash_pwd')||''));
  if(d.error) { toast('❌ '+d.error, true); return; }
  document.getElementById('file-current-path').textContent = d.path;
  document.getElementById('file-path-input').value = d.path;
  let html = '<tr><th>Name</th><th>Size</th><th>Modified</th></tr>';
  if(d.parent && d.parent !== d.path) {
    html += '<tr onclick="browseFiles(\\''+d.parent.replace(/'/g,"\\'")+'\\')"><td class="folder">📂 <strong>..</strong> (parent)</td><td>—</td><td>—</td></tr>';
  }
  d.items.forEach(item => {
    const icon = item.is_dir ? '📂' : '📄';
    const name = item.name.replace(/</g,'&lt;');
    const click = item.is_dir ? 'onclick="browseFiles(\\''+(d.path+'/'+item.name).replace(/'/g,"\\'")+'\\')"' : 'onclick="downloadFile(\\''+(d.path+'/'+item.name).replace(/'/g,"\\'")+'\\')"';
    html += '<tr '+click+'><td class="'+(item.is_dir?'folder':'file')+'">'+icon+' '+name+'</td><td>'+(item.is_dir?'—':item.size_hr)+'</td><td>'+(item.modified||'').substring(0,10)+'</td></tr>';
  });
  document.getElementById('file-tbody').innerHTML = html;
}
function downloadFile(path) {
  window.open('/api/download?path='+encodeURIComponent(path)+'&pwd='+encodeURIComponent(sessionStorage.getItem('dash_pwd')||''), '_blank');
}

// ===== CONTROLS =====
async function lock() { const d=await apiPost('/api/lock'); toast(d.ok?'🔒 Screen locked':'❌ Lock failed',!d.ok); loadStatus(); }
async function unlock() { const d=await apiPost('/api/unlock'); toast(d.ok?'🔓 Screen unlocked':'❌ '+(d.error||'Failed'),!d.ok); loadStatus(); }
async function sound(a) { await apiPost('/api/sound',{action:a}); toast('🔊 Sound: '+a); loadSound(); }
async function sendNotif() {
  const msg=document.getElementById('notif-msg').value;
  await apiPost('/api/notify',{message:msg}); toast('🔔 Notification sent');
}
async function vnc(a) {
  const d=await apiPost('/api/vnc',{action:a});
  toast(d.ok?(a==='start'?'▶ VNC started':'⏹ VNC stopped'):'❌ '+(d.error||'Failed'),!d.ok);
  loadStatus();
}
async function vpnStop() {
  const d=await apiPost('/api/vpn',{action:'stop'});
  toast(d.ok?'⏹ VPN disconnected':'❌ Failed',!d.ok);
  loadStatus();
}
async function socks5(a) {
  const d=await apiPost('/api/socks5',{action:a});
  toast(d.ok?(a==='start'?'▶ SOCKS5 started on :1080':'⏹ SOCKS5 stopped'):'❌ Failed',!d.ok);
  loadSocks5();
}
async function loadSocks5() {
  const s=await api('/api/socks5');
  document.getElementById('ctrl-socks5-status').textContent = s.running?'✅ Running on :1080':'❌ Stopped';
}

async function loadStatus() {
  const s = await api('/api/status');
  document.getElementById('ctrl-lock-status').textContent = s.locked?'🔒 Locked':'🔓 Unlocked';
  document.getElementById('ctrl-lock-badge').className = 'badge '+(s.locked?'badge-red':'badge-green');
  document.getElementById('ctrl-lock-badge').textContent = s.locked?'Locked':'Active';
  document.getElementById('ctrl-vnc-status').textContent = s.vnc_running?'✅ Running':'❌ Stopped';
  // Load VPN status
  const v = await api('/api/vpn');
  document.getElementById('ctrl-vpn-status').textContent = v.running?'✅ Connected ('+(v.interface||'')+')':'❌ Disconnected';
  // Load SOCKS5 status
  loadSocks5();
}
async function loadSound() {
  const s = await api('/api/sound');
  document.getElementById('ctrl-vol').textContent = s.vol||'—';
  document.getElementById('ctrl-vol-icon').textContent = s.muted?'🔇':'🔊';
  document.getElementById('ctrl-mute-badge').className = 'badge '+(s.muted?'badge-red':'badge-green');
  document.getElementById('ctrl-mute-badge').textContent = s.muted?'Muted':'Active';
}

// ===== INIT =====
function init() {
  loadOverview(); loadSystem(); loadNetwork(); loadProcesses(); loadStatus(); loadSound(); browseFiles();
  // Auto-refresh overview every 5 seconds
  setInterval(loadOverview, 5000);
  setInterval(loadStatus, 10000);
}
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/vpn", methods=["GET"])
@require_auth
def api_vpn_dash():
    running = run_shell("pgrep -f 'wg-quick|openvpn' 2>/dev/null | grep -v grep || echo 'no'")
    interface = run_shell("ip addr show tun0 2>/dev/null | grep inet | awk '{print $2}' || echo 'No VPN interface'")
    return jsonify({"running": "no" not in running, "interface": interface})

@app.route("/api/vpn", methods=["POST"])
@require_auth
def api_vpn_ctrl():
    action = (request.json or {}).get("action", "status")
    if action == "stop":
        run_shell("pkill -f 'wg-quick|openvpn' 2>/dev/null; ip link delete tun0 2>/dev/null; echo done")
        return jsonify({"ok": True})
    elif action == "status":
        running = run_shell("pgrep -f 'wg-quick|openvpn' 2>/dev/null | grep -v grep || echo 'no'")
        return jsonify({"running": "no" not in running})
    return jsonify({"ok": False})

@app.route("/api/socks5", methods=["GET"])
@require_auth
def api_socks5_dash():
    running = run_shell("pgrep -x microsocks 2>/dev/null || echo 'no'")
    port = run_shell("ss -tlnp | grep 1080 || echo 'Not listening'")
    return jsonify({"running": "no" not in running, "port": port})

@app.route("/api/socks5", methods=["POST"])
@require_auth
def api_socks5_ctrl():
    action = (request.json or {}).get("action", "status")
    if action == "start":
        subprocess.Popen(["microsocks","-i","0.0.0.0","-p","1080"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        return jsonify({"ok": True})
    elif action == "stop":
        run_shell("pkill -x microsocks 2>/dev/null")
        return jsonify({"ok": True})
    return jsonify({"ok": False})

@app.route("/api/<path:fallback>")
def fallback_api():
    return jsonify({"error": "Not found"}), 404

# ==============================================================
# STARTUP
# ==============================================================

def start_server():
    print(f"🚀 guid_erbot Dashboard running on http://0.0.0.0:{PORT}")
    print(f"🔐 Password: {PASSWORD}")
    app.run(host="0.0.0.0", port=PORT, debug=False)

if __name__ == "__main__":
    start_server()
