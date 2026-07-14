#!/usr/bin/env python3
"""
healthcheck.py - Diagnostic server for Render + UptimeRobot
===============================================================
Keeps the bot alive on Render's free tier AND provides rich
runtime diagnostics so you can debug without SSH access.

Run alongside the bot:
    python3 healthcheck.py &

Diagnostic endpoints:
  GET /health     — UptimeRobot keep-alive (JSON)
  GET /ping       — Simple ping (returns "pong")
  GET /debug      — Full diagnostic info (processes, disk, network, packages, uptime)
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from flask import Flask, jsonify

app = Flask(__name__)

# Track when this server started
START_TIME = time.time()


def get_uptime():
    """Return human-readable uptime string."""
    elapsed = time.time() - START_TIME
    days, rem = divmod(elapsed, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    if days:
        return f"{int(days)}d {int(hours)}h {int(mins)}m"
    elif hours:
        return f"{int(hours)}h {int(mins)}m {int(secs)}s"
    else:
        return f"{int(mins)}m {int(secs)}s"


def check_process(name):
    """Check if a process is running by name. Returns (bool, pid_or_error)."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().splitlines()
            return True, pids[0]
        return False, None
    except Exception as e:
        return False, str(e)


def get_proc_memory(pid):
    """Get memory usage (RSS) for a PID in MB. Returns string or 'N/A'."""
    try:
        result = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0 and result.stdout.strip():
            rss_kb = int(result.stdout.strip())
            return f"{rss_kb // 1024} MB"
    except (ValueError, subprocess.TimeoutExpired, OSError):
        pass
    return "N/A"


def get_system_load():
    """Get system load averages."""
    try:
        result = subprocess.run(
            ["uptime"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            # Extract load averages from the end of the line
            parts = result.stdout.strip().split("load average:")
            if len(parts) > 1:
                return parts[1].strip()
    except Exception:
        pass
    return "N/A"


def get_disk_usage():
    """Get disk usage for all mounts. Returns list of dicts."""
    try:
        result = subprocess.run(
            ["df", "-h", "-x", "tmpfs", "-x", "devtmpfs", "-x", "squashfs"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            if len(lines) < 2:
                return []
            mounts = []
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 6:
                    mounts.append({
                        "filesystem": parts[0],
                        "size": parts[1],
                        "used": parts[2],
                        "avail": parts[3],
                        "use_pct": parts[4],
                        "mount": parts[5],
                    })
            return mounts
    except Exception:
        pass
    return []


def get_network_interfaces():
    """Get network interfaces and their IPs. Returns list of dicts."""
    try:
        result = subprocess.run(
            ["ip", "-br", "addr"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            interfaces = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    iface = {"name": parts[0], "status": parts[1]}
                    if len(parts) >= 3:
                        iface["addresses"] = parts[2]
                    if len(parts) >= 4:
                        iface["extra"] = " ".join(parts[3:])
                    interfaces.append(iface)
            return interfaces
    except Exception:
        pass
    return []


def get_package_count():
    """Count installed packages via dpkg or pip."""
    try:
        # Try dpkg (Debian/Ubuntu)
        result = subprocess.run(
            ["dpkg", "--list"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            count = sum(1 for line in result.stdout.splitlines() if line.startswith("ii"))
            return {"dpkg": count, "pip": None}
    except Exception:
        pass
    # Fallback: try pip list
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=columns"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.splitlines() if l.strip() and not l.startswith("Package")]
            return {"dpkg": None, "pip": len(lines)}
    except Exception:
        pass
    return None


def get_bot_stats():
    """Get stats about the bot's data directory."""
    stats = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    try:
        if os.path.isdir(data_dir):
            files = os.listdir(data_dir)
            stats["data_dir"] = data_dir
            stats["data_files"] = files
            for f in files:
                fp = os.path.join(data_dir, f)
                if os.path.isfile(fp):
                    try:
                        size = os.path.getsize(fp)
                        stats[f"{f}_size"] = f"{size:,} bytes"
                    except OSError:
                        pass
        else:
            stats["data_dir"] = "directory not created yet"
    except Exception as e:
        stats["data_dir_error"] = str(e)
    
    # Check bot.py in the same directory
    bot_py = os.path.join(script_dir, "bot.py")
    try:
        if os.path.isfile(bot_py):
            stats["bot_py_size"] = f"{os.path.getsize(bot_py):,} bytes"
            with open(bot_py) as f:
                stats["bot_py_lines"] = sum(1 for _ in f)
    except Exception:
        pass
    
    return stats


@app.route("/health")
def health():
    """Healthcheck endpoint for UptimeRobot / Kaffeine."""
    bot_running, bot_pid = check_process("bot.py")
    return jsonify({
        "status": "ok",
        "service": "guid_erbot",
        "uptime_runner": True,
        "bot_running": bot_running,
        "server_uptime": get_uptime(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/ping")
def ping():
    """Simple ping endpoint (returns plain text)."""
    return "pong"


@app.route("/debug")
def debug():
    """Full diagnostic info — your browser-based SSH replacement."""
    bot_running, bot_pid = check_process("bot.py")
    health_running, health_pid = check_process("healthcheck.py")

    info = {
        "service": "guid_erbot",
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": {
            "server": get_uptime(),
            "system": get_system_load(),
        },
        "processes": {
            "bot": {
                "running": bot_running,
                "pid": bot_pid,
                "memory": get_proc_memory(bot_pid) if bot_pid else "N/A",
            },
            "healthcheck": {
                "running": health_running,
                "pid": health_pid,
                "memory": get_proc_memory(health_pid) if health_pid else "N/A",
            },
        },
        "environment": {
            "render": os.environ.get("RENDER", "false"),
            "python_version": os.environ.get("PYTHON_VERSION", "unknown"),
            "port": os.environ.get("PORT", "8080"),
            "hostname": os.uname().nodename,
            "kernel": os.uname().release,
            "architecture": os.uname().machine,
        },
        "disk": get_disk_usage(),
        "network": get_network_interfaces(),
        "packages": get_package_count(),
        "bot_stats": get_bot_stats(),
        "endpoints": {
            "/health": "UptimeRobot keep-alive",
            "/ping": "Simple ping",
            "/debug": "Full diagnostics (this page)",
        },
    }
    return jsonify(info)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"{'='*50}")
    print(f"❤️  guid_erbot Diagnostic Server")
    print(f"{'='*50}")
    print(f"📡 Port:     {port}")
    print(f"🔗 Health:   https://YOUR-APP.onrender.com/health")
    print(f"🔍 Debug:    https://YOUR-APP.onrender.com/debug")
    print(f"📌 UptimeRobot: https://YOUR-APP.onrender.com/health (every 10 min)")
    print(f"{'='*50}")
    app.run(host="0.0.0.0", port=port)
