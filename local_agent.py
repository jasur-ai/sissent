#!/usr/bin/env python3
"""
local_agent.py - Desktop command executor for guid_erbot
==========================================================
Runs on your local Kali Linux VM. Polls the Render healthcheck
server for pending desktop commands, executes them locally,
and posts results back.

Usage:
    python3 local_agent.py

The agent connects OUT to Render (no open ports needed on your VM).
Allows the cloud bot (on Render) to control your local desktop.
"""

import json
import os
import subprocess
import sys
import time
import shutil
from pathlib import Path

# ============ CONFIGURATION ============

# The Render healthcheck server URL (change this to your actual URL)
RENDER_URL = os.environ.get("RENDER_URL", "https://sissent-1.onrender.com")

# How often to poll for new commands (seconds)
POLL_INTERVAL = 2

# ============ COMMAND EXECUTORS ============
# Each function takes no args and returns (output_string, error_string_or_None)


def cmd_screenshot():
    """Take a screenshot of the desktop."""
    path = "/tmp/guid_agent_screenshot.png"
    methods = [
        ["import", "-window", "root", path],
        ["scrot", path],
        ["gnome-screenshot", "-f", path],
    ]
    for cmd in methods:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, timeout=10, capture_output=True)
                if Path(path).exists() and Path(path).stat().st_size > 1000:
                    # Upload the screenshot to Render
                    _upload_file(path)
                    return f"Screenshot uploaded: {os.path.getsize(path)} bytes", None
            except Exception:
                continue
    return None, "No screenshot tool found (install imagemagick or scrot)"


def cmd_shell(command):
    """Execute a shell command."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=60
        )
        output = result.stdout + result.stderr
        return output if output else "(No output)", None
    except subprocess.TimeoutExpired:
        return None, "Command timed out after 60s"
    except Exception as e:
        return None, str(e)


def cmd_lock():
    """Lock the screen using i3lock."""
    if not shutil.which("i3lock"):
        return None, "i3lock not installed. Run: sudo apt install i3lock"
    try:
        subprocess.Popen(
            ["i3lock", "-c", "1a1a2e", "--nofork"],
            env={**os.environ, "DISPLAY": ":0"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        locked = subprocess.run(["pgrep", "-x", "i3lock"], capture_output=True, text=True)
        if locked.returncode == 0:
            return "Screen locked! Use /unlock to type password.", None
        return None, "i3lock failed to start"
    except Exception as e:
        return None, str(e)


def cmd_unlock():
    """Unlock screen by typing password for i3lock."""
    password = os.environ.get("OSBOXES_PASS", "osboxes.org")
    if not shutil.which("xdotool"):
        return None, "xdotool not installed"
    try:
        subprocess.run(["xdotool", "type", "--delay", "20", password], timeout=5, env={"DISPLAY": ":0"})
        time.sleep(0.3)
        subprocess.run(["xdotool", "key", "Return"], timeout=3, env={"DISPLAY": ":0"})
        time.sleep(0.5)
        locked = subprocess.run(["pgrep", "-x", "i3lock"], capture_output=True, text=True)
        if locked.returncode != 0:
            return "Screen unlocked!", None
        return None, "Failed to unlock - wrong password?"
    except Exception as e:
        return None, str(e)


def cmd_notify(message):
    """Show a desktop notification."""
    try:
        subprocess.run(
            ["notify-send", "📱 Telegram", message, "-i", "telegram", "-t", "5000"],
            timeout=5, capture_output=True,
        )
        return f"Notification shown: {message[:50]}", None
    except FileNotFoundError:
        try:
            subprocess.run(f'echo "NOTIFY: {message}" | wall', shell=True, timeout=3)
            return f"Notification sent (wall): {message[:50]}", None
        except Exception as e:
            return None, str(e)
    except Exception as e:
        return None, str(e)


def cmd_browser(url):
    """Open a URL in the default browser."""
    browsers = ["xdg-open", "firefox", "chromium", "google-chrome", "sensible-browser"]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    for browser in browsers:
        bpath = shutil.which(browser)
        if bpath:
            try:
                subprocess.Popen([bpath, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"Opened {url} in {browser}", None
            except Exception:
                continue
    return None, "No browser found"


def cmd_type(text):
    """Type text using xdotool."""
    if not shutil.which("xdotool"):
        return None, "xdotool not installed"
    try:
        subprocess.run(["xdotool", "type", "--delay", "50", text], timeout=10, capture_output=True, env={"DISPLAY": ":0"})
        return f"Typed: {text[:50]}", None
    except Exception as e:
        return None, str(e)


def cmd_key(key):
    """Press a keyboard key."""
    if not shutil.which("xdotool"):
        return None, "xdotool not installed"
    try:
        subprocess.run(["xdotool", "key", key], timeout=5, capture_output=True, env={"DISPLAY": ":0"})
        return f"Pressed key: {key}", None
    except Exception as e:
        return None, str(e)


def cmd_click(button="left"):
    """Click mouse button."""
    if not shutil.which("xdotool"):
        return None, "xdotool not installed"
    try:
        subprocess.run(["xdotool", "click", button], timeout=5, capture_output=True, env={"DISPLAY": ":0"})
        return f"Clicked {button}", None
    except Exception as e:
        return None, str(e)


def cmd_scroll(direction="down", clicks="3"):
    """Scroll mouse wheel."""
    if not shutil.which("xdotool"):
        return None, "xdotool not installed"
    btn = "4" if direction == "up" else "5"
    try:
        for _ in range(int(clicks)):
            subprocess.run(["xdotool", "click", btn], timeout=3, capture_output=True, env={"DISPLAY": ":0"})
        return f"Scrolled {direction} {clicks} times", None
    except Exception as e:
        return None, str(e)


def cmd_sound(action):
    """Control sound volume."""
    try:
        if action == "up":
            subprocess.run(["amixer", "set", "Master", "5%+"], timeout=3, capture_output=True)
            return "Volume up", None
        elif action == "down":
            subprocess.run(["amixer", "set", "Master", "5%-"], timeout=3, capture_output=True)
            return "Volume down", None
        elif action in ("mute", "toggle"):
            subprocess.run(["amixer", "set", "Master", "toggle"], timeout=3, capture_output=True)
            return "Volume toggled", None
        elif action == "get":
            r = subprocess.run(["amixer", "get", "Master"], timeout=3, capture_output=True, text=True)
            return r.stdout[:500], None
        return None, f"Unknown sound action: {action}"
    except Exception as e:
        return None, str(e)


def cmd_media(folder):
    """Open a media folder in file manager."""
    folders = {
        "music": str(Path.home() / "Music"),
        "downloads": str(Path.home() / "Downloads"),
        "videos": str(Path.home() / "Videos"),
        "images": str(Path.home() / "Pictures"),
        "documents": str(Path.home() / "Documents"),
        "home": str(Path.home()),
    }
    target = folders.get(folder, folder)
    try:
        subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened {folder}", None
    except Exception as e:
        return None, str(e)


# ============ FILE UPLOAD HELPER ============

def _upload_file(filepath):
    """Upload a file to the Render healthcheck server."""
    import urllib.request
    import os
    try:
        cmd_id = os.environ.get("_LAST_CMD_ID", "")
        if not cmd_id:
            return
        with open(filepath, "rb") as f:
            file_data = f.read()
        boundary = "----WebKitFormBoundary" + os.urandom(16).hex()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(filepath)}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            f"{RENDER_URL}/agent/upload/{cmd_id}",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        print(f"📤 Uploaded {os.path.basename(filepath)} ({len(file_data)} bytes)")
    except Exception as e:
        print(f"⚠️ Upload failed: {e}")

def execute_command(cmd_type, args_str):
    """Execute a command and return (output, error)."""
    handlers = {
        "screenshot": lambda: cmd_screenshot(),
        "lock": lambda: cmd_lock(),
        "unlock": lambda: cmd_unlock(),
        "notify": lambda: cmd_notify(args_str),
        "browser": lambda: cmd_browser(args_str),
        "type": lambda: cmd_type(args_str),
        "key": lambda: cmd_key(args_str),
        "click": lambda: cmd_click(args_str or "left"),
        "scroll": lambda: cmd_scroll(*args_str.split() if args_str else ("down", "3")),
        "sound": lambda: cmd_sound(args_str or "get"),
        "media": lambda: cmd_media(args_str or "home"),
        "shell": lambda: cmd_shell(args_str),
    }
    handler = handlers.get(cmd_type)
    if handler:
        return handler()
    return None, f"Unknown command type: {cmd_type}"


# ============ MAIN LOOP ============

def poll_commands():
    """Main loop: poll Render for commands, execute, post results."""
    import urllib.request
    import urllib.error

    print(f"🤖 guid_erbot Local Agent")
    print(f"{'='*40}")
    print(f"🔗 Render URL: {RENDER_URL}")
    print(f"🔄 Polling every {POLL_INTERVAL}s")
    print(f"📋 Ready to execute desktop commands")
    print(f"{'='*40}")
    print()

    while True:
        try:
            # Poll for next command
            req = urllib.request.Request(f"{RENDER_URL}/agent/command")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            if data.get("status") == "empty":
                time.sleep(POLL_INTERVAL)
                continue

            cmd_id = data.get("id", "")
            cmd_type = data.get("type", "shell")
            cmd_args = data.get("args", "")
            print(f"⚡ Executing [{cmd_id}]: {cmd_type} {cmd_args[:50]}")

            # Set cmd_id so _upload_file can find it
            os.environ["_LAST_CMD_ID"] = cmd_id

            # Execute locally
            output, error = execute_command(cmd_type, cmd_args)

            # Post result back
            result = {"id": cmd_id, "output": output or "", "error": error}
            req = urllib.request.Request(
                f"{RENDER_URL}/agent/result",
                data=json.dumps(result).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()

            status = "✅" if not error else "❌"
            print(f"{status} Completed [{cmd_id}]: {output[:80] if output else error}")

        except urllib.error.HTTPError as e:
            # 404 means the /agent endpoints aren't deployed yet - wait
            if e.code == 404:
                print(f"⏳ Waiting for Render deploy... ({e.code})")
                time.sleep(5)
            else:
                print(f"⚠️ HTTP Error: {e.code} {e.reason}")
                time.sleep(POLL_INTERVAL)
        except urllib.error.URLError as e:
            print(f"⚠️ Connection error: {e.reason}")
            time.sleep(5)
        except json.JSONDecodeError:
            print("⚠️ Invalid JSON response, retrying...")
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        poll_commands()
    except KeyboardInterrupt:
        print("\n👋 Agent stopped.")
