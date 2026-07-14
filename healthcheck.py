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
from flask import Flask, jsonify, render_template_string, render_template_string

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



DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>guid_erbot - Diagnostics</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f0f1a;
    color: #e0e0e0;
    min-height: 100vh;
    padding: 20px;
  }
  .container { max-width: 1200px; margin: 0 auto; }
  header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 20px 0; border-bottom: 1px solid #2a2a3e; margin-bottom: 24px;
    flex-wrap: wrap; gap: 12px;
  }
  header h1 {
    font-size: 24px; font-weight: 700;
    background: linear-gradient(135deg, #a29bfe, #6c5ce7);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  .status-badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600;
  }
  .status-badge.ok { background: rgba(0, 255, 136, 0.15); color: #00ff88; }
  .status-badge.error { background: rgba(255, 107, 107, 0.15); color: #ff6b6b; }
  .status-badge.warn { background: rgba(255, 217, 61, 0.15); color: #ffd93d; }
  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .dot.green { background: #00ff88; box-shadow: 0 0 8px #00ff8866; }
  .dot.red { background: #ff6b6b; box-shadow: 0 0 8px #ff6b6b66; }
  .dot.yellow { background: #ffd93d; box-shadow: 0 0 8px #ffd93d66; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
  .card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #2a2a3e;
    border-radius: 16px; padding: 20px;
    transition: transform 0.2s, box-shadow 0.2s;
  }
  .card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
  .card-title {
    font-size: 13px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.5px; color: #8888aa; margin-bottom: 14px;
    display: flex; align-items: center; gap: 8px;
  }
  .card-title .emoji { font-size: 16px; }
  .stat-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 14px; border-bottom: 1px solid #1f1f35; }
  .stat-row:last-child { border-bottom: none; }
  .stat-label { color: #8888aa; }
  .stat-value { color: #e0e0e0; font-weight: 500; font-family: 'SF Mono', 'Fira Code', monospace; }
  .stat-value.green { color: #00ff88; }
  .stat-value.red { color: #ff6b6b; }
  .stat-value.yellow { color: #ffd93d; }
  .bar-container { background: #1f1f35; border-radius: 8px; height: 8px; overflow: hidden; margin: 4px 0 8px; }
  .bar-fill {
    height: 100%; border-radius: 8px;
    transition: width 0.5s ease;
    background: linear-gradient(90deg, #00ff88, #6c5ce7);
  }
  .bar-fill.warn { background: linear-gradient(90deg, #ffd93d, #ff9f43); }
  .bar-fill.danger { background: linear-gradient(90deg, #ff6b6b, #ee5a24); }
  .network-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .network-table th { text-align: left; color: #8888aa; font-weight: 600; padding: 6px 4px; border-bottom: 1px solid #2a2a3e; }
  .network-table td { padding: 6px 4px; border-bottom: 1px solid #1f1f35; font-family: 'SF Mono', monospace; }
  .iface-up { color: #00ff88; }
  .iface-down { color: #ff6b6b; }
  .disk-list { list-style: none; }
  .disk-item { padding: 10px 0; border-bottom: 1px solid #1f1f35; }
  .disk-item:last-child { border-bottom: none; }
  .disk-mount { font-weight: 600; font-size: 13px; color: #a29bfe; }
  .disk-details { display: flex; gap: 16px; font-size: 12px; color: #8888aa; margin: 4px 0; }
  .env-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .env-item { background: #0f0f1a; padding: 8px 12px; border-radius: 8px; font-size: 12px; }
  .env-key { color: #8888aa; }
  .env-val { color: #a29bfe; font-family: 'SF Mono', monospace; display: block; margin-top: 2px; }
  .refresh-bar {
    display: flex; align-items: center; gap: 8px;
    padding: 10px 16px; background: #1a1a2e; border-radius: 10px;
    font-size: 12px; color: #8888aa; margin-bottom: 16px;
  }
  .refresh-spinner { width: 14px; height: 14px; border: 2px solid #2a2a3e; border-top-color: #6c5ce7; border-radius: 50%; animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  footer { text-align: center; padding: 30px 0; font-size: 12px; color: #555; }
  .mt-2 { margin-top: 8px; }
  @media (max-width: 600px) {
    .grid { grid-template-columns: 1fr; }
    .env-grid { grid-template-columns: 1fr; }
    header h1 { font-size: 20px; }
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🖥️ guid_erbot · Diagnostics</h1>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      <span class="status-badge" id="statusBadge">
        <span class="dot" id="statusDot"></span>
        <span id="statusText">Loading...</span>
      </span>
      <span style="font-size:13px;color:#8888aa;" id="timestamp"></span>
    </div>
  </header>

  <div class="refresh-bar">
    <div class="refresh-spinner"></div>
    <span>Auto-refreshes every 30s · </span>
    <a href="/debug" style="color:#6c5ce7;text-decoration:none;font-weight:500;">View Raw JSON</a>
  </div>

  <div class="grid" id="dashboardGrid"></div>
  <footer>guid_erbot · Render Diagnostics</footer>
</div>

<script>
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function pctColor(pct) {
  const n = parseFloat(pct);
  if (isNaN(n)) return '';
  if (n >= 80) return 'danger';
  if (n >= 50) return 'warn';
  return '';
}

function renderDisk(disks) {
  if (!disks || disks.length === 0) return '<div style="color:#888;">No disk data</div>';
  return disks.map(d => {
    const pct = parseInt(d.use_pct);
    const cls = pctColor(pct);
    return `<div class="disk-item">
      <div class="disk-mount">${d.mount}</div>
      <div class="disk-details"><span>💾 ${d.size}</span><span>📀 ${d.used}</span><span>🆓 ${d.avail}</span></div>
      <div class="bar-container"><div class="bar-fill ${cls}" style="width:${pct}%"></div></div>
      <div style="font-size:12px;color:#8888aa;">${d.use_pct} used</div>
    </div>`;
  }).join('');
}

function renderNetwork(ifaces) {
  if (!ifaces || ifaces.length === 0) return '<div style="color:#888;">No network data</div>';
  return `<table class="network-table">
    <tr><th>Interface</th><th>Status</th><th>Address</th></tr>
    ${ifaces.map(i => {
      const cls = i.status === 'UP' ? 'iface-up' : 'iface-down';
      return `<tr><td>${i.name}</td><td class="${cls}">${i.status}</td><td>${i.addresses || '-'}</td></tr>`;
    }).join('')}
  </table>`;
}

function renderProcesses(procs) {
  return Object.entries(procs).map(([name, p]) => {
    const dotClass = p.running ? 'green' : 'red';
    const statusText = p.running ? 'Running' : 'Stopped';
    return `<div class="stat-row">
      <span class="stat-label">${name}</span>
      <span class="stat-value"><span class="dot ${dotClass}"></span> ${statusText} ${p.pid ? '· PID '+p.pid : ''} ${p.memory ? '· '+p.memory : ''}</span>
    </div>`;
  }).join('');
}

function renderEnv(env) {
  if (!env) return '<div style="color:#888;">No env data</div>';
  return `<div class="env-grid">${Object.entries(env).map(([k,v]) => 
    `<div class="env-item"><span class="env-key">${k}</span><span class="env-val">${v || '-'}</span></div>`
  ).join('')}</div>`;
}

function renderBotStats(stats) {
  if (!stats) return '<div style="color:#888;">No stats</div>';
  return Object.entries(stats).map(([k,v]) => {
    const displayKey = k.replace(/_/g, ' ');
    return `<div class="stat-row"><span class="stat-label">${displayKey}</span><span class="stat-value">${esc(v) || '-'}</span></div>`;
  }).join('');
}

function renderUptime(ut) {
  if (!ut) return '<div style="color:#888;">No uptime data</div>';
  return `<div class="stat-row"><span class="stat-label">⏱ Server uptime</span><span class="stat-value green">${ut.server || '-'}</span></div>
    <div class="stat-row"><span class="stat-label">📊 System load</span><span class="stat-value">${ut.system || '-'}</span></div>`;
}

function renderPackages(pkgs) {
  if (!pkgs) return '<div style="color:#888;">No package data</div>';
  const items = [];
  if (pkgs.dpkg) items.push(`<div class="stat-row"><span class="stat-label">📦 dpkg</span><span class="stat-value green">${pkgs.dpkg.toLocaleString()} packages</span></div>`);
  if (pkgs.pip) items.push(`<div class="stat-row"><span class="stat-label">🐍 pip</span><span class="stat-value">${pkgs.pip} packages</span></div>`);
  return items.join('');
}

async function loadDashboard() {
  try {
    const res = await fetch('/debug');
    const d = await res.json();

    const dot = document.getElementById('statusDot');
    const badge = document.getElementById('statusBadge');
    const stxt = document.getElementById('statusText');
    const ts = document.getElementById('timestamp');

    if (d.status === 'ok') {
      dot.className = 'dot green';
      badge.className = 'status-badge ok';
      stxt.textContent = 'All Systems OK';
    } else {
      dot.className = 'dot red';
      badge.className = 'status-badge error';
      stxt.textContent = 'Issues Detected';
    }
    ts.textContent = d.timestamp ? new Date(d.timestamp).toLocaleString() : '';

    const grid = document.getElementById('dashboardGrid');
    grid.innerHTML = `
      <div class="card">
        <div class="card-title"><span class="emoji">⚡</span> Status</div>
        <div class="stat-row"><span class="stat-label">Service</span><span class="stat-value">${d.service}</span></div>
        <div class="stat-row"><span class="stat-label">Status</span><span class="stat-value green">${d.status}</span></div>
        ${renderUptime(d.uptime)}
      </div>
      <div class="card">
        <div class="card-title"><span class="emoji">🧠</span> Processes</div>
        ${d.processes ? renderProcesses(d.processes) : '<div style="color:#888;">No data</div>'}
      </div>
      <div class="card">
        <div class="card-title"><span class="emoji">💾</span> Disk Usage</div>
        ${renderDisk(d.disk)}
      </div>
      <div class="card">
        <div class="card-title"><span class="emoji">🌐</span> Network Interfaces</div>
        ${renderNetwork(d.network)}
      </div>
      <div class="card">
        <div class="card-title"><span class="emoji">📦</span> Packages</div>
        ${renderPackages(d.packages)}
      </div>
      <div class="card">
        <div class="card-title"><span class="emoji">⚙️</span> Environment</div>
        ${renderEnv(d.environment)}
      </div>
      <div class="card">
        <div class="card-title"><span class="emoji">🤖</span> Bot Stats</div>
        ${renderBotStats(d.bot_stats)}
      </div>
      <div class="card">
        <div class="card-title"><span class="emoji">🔗</span> Endpoints</div>
        ${d.endpoints ? Object.entries(d.endpoints).map(([k,v]) => 
          `<div class="stat-row"><span class="stat-label">${k}</span><span class="stat-value" style="font-size:12px;">${v}</span></div>`
        ).join('') : '<div style="color:#888;">No data</div>'}
      </div>
    `;
  } catch (e) {
    document.getElementById('dashboardGrid').innerHTML = 
      `<div class="card"><div class="card-title">❌ Error</div><div style="color:#ff6b6b;">Failed to load diagnostics: ${e.message}</div></div>`;
  }
}

// Initial load
loadDashboard();
// Auto-refresh every 30s
setInterval(loadDashboard, 30000);
</script>
</body>
</html>"""

@app.route("/")
def dashboard():
    """Web dashboard showing all diagnostics."""
    return render_template_string(DASHBOARD_HTML)

@app.route("/dashboard")
def dashboard_redirect():
    return dashboard()

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


# ============ COMMAND RELAY (Local VM Agent Bridge) ============
# The bot on Render stores desktop commands here.
# The local_agent.py script (running on your Kali VM) polls this
# endpoint, executes commands, and posts results back.
# This allows the cloud bot to control your local desktop.

_command_queue = []  # List of pending commands
_result_store = {}   # Dict of completed results

@app.route("/agent/command", methods=["POST", "GET"])
def agent_command():
    """
    POST: Bot enqueues a command for the local agent.
    GET:  Local agent polls for the next command.
    """
    from flask import request
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        cmd_id = str(int(time.time() * 1000)) + "_" + str(len(_command_queue))
        entry = {
            "id": cmd_id,
            "type": data.get("type", "shell"),
            "args": data.get("args", ""),
            "chat_id": data.get("chat_id", ""),
            "status": "pending",
        }
        _command_queue.append(entry)
        return jsonify({"status": "queued", "id": cmd_id})
    
    # GET: return next pending command
    for cmd in _command_queue:
        if cmd["status"] == "pending":
            cmd["status"] = "running"
            return jsonify(cmd)
    return jsonify({"status": "empty"})


@app.route("/agent/result", methods=["POST"])
def agent_result():
    """Local agent posts command results here."""
    from flask import request
    data = request.get_json(silent=True) or {}
    cmd_id = data.get("id", "")
    output = data.get("output", "")
    error = data.get("error", None)
    
    if cmd_id:
        _result_store[cmd_id] = {
            "output": output,
            "error": error,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        # Mark command as completed
        for cmd in _command_queue:
            if cmd["id"] == cmd_id:
                cmd["status"] = "completed"
                break
    return jsonify({"status": "ok"})


@app.route("/agent/result/<cmd_id>")
def agent_get_result(cmd_id):
    """Bot checks if a command result is ready."""
    result = _result_store.get(cmd_id)
    if result:
        return jsonify({"status": "ready", "result": result})
    return jsonify({"status": "pending"})


# File storage for command results (screenshots, uploads)
_RESULT_FILES = {}


@app.route("/agent/upload/<cmd_id>", methods=["POST"])
def agent_upload(cmd_id):
    """Local agent uploads a file (screenshot, etc.) for a completed command."""
    from flask import request
    if "file" not in request.files:
        return jsonify({"status": "error", "error": "No file provided"}), 400
    file = request.files["file"]
    filename = file.filename or f"{cmd_id}.bin"
    file_data = file.read()
    _RESULT_FILES[cmd_id] = {
        "filename": filename,
        "data": file_data,
        "mimetype": file.content_type or "application/octet-stream",
    }
    return jsonify({"status": "ok", "filename": filename, "size": len(file_data)})


@app.route("/agent/download/<cmd_id>")
def agent_download(cmd_id):
    """Bot downloads a file result from a completed command."""
    from flask import send_file
    import io
    file_info = _RESULT_FILES.get(cmd_id)
    if not file_info:
        return jsonify({"status": "error", "error": "File not found"}), 404
    return send_file(
        io.BytesIO(file_info["data"]),
        mimetype=file_info["mimetype"],
        as_attachment=True,
        download_name=file_info["filename"],
    )


@app.route("/agent/has_file/<cmd_id>")
def agent_has_file(cmd_id):
    """Bot checks if a file is ready for download."""
    has_file = cmd_id in _RESULT_FILES
    return jsonify({"status": "ok", "has_file": has_file})


@app.after_request
def add_no_cache(resp):
    """Prevent browsers from caching JSON responses (dashboard refreshes every 30s)."""
    if resp.content_type and 'application/json' in resp.content_type:
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


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
