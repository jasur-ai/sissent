#!/usr/bin/env python3
"""
utils.py - Shared utilities for guid_erbot
Common functions used by bot.py and extra_commands.py
"""

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

# ============ CONFIGURATION ============

# Read admin IDs from environment variable (set in Render dashboard)
_ADMIN_IDS_ENV = os.environ.get("ADMIN_IDS", "8004724563")
ADMIN_IDS = [int(x.strip()) for x in _ADMIN_IDS_ENV.split(",") if x.strip()]

OSBOXES_USER = "osboxes"
OSBOXES_PASS = "osboxes.org"

# ============ MACHINE CONFIG ============
# Supports: 'kal' (Kali Linux) and 'ubuntu' (Ubuntu)
MACHINES = {
    "kal": {
        "name": "Kali Linux",
        "home": "/home/osboxes",
        "data_dir": "/home/osboxes/guid_erbot/data",
        "download_dir": "/home/osboxes/Downloads/guid_erbot",
        "backup_dir": "/home/osboxes/backups",
        "user": "osboxes",
        "pass": "osboxes.org",
    },
    "ubuntu": {
        "name": "Ubuntu",
        "home": "/home/ubuntu",
        "data_dir": "/home/ubuntu/guid_erbot/data",
        "download_dir": "/home/ubuntu/Downloads/guid_erbot",
        "backup_dir": "/home/ubuntu/backups",
        "user": "ubuntu",
        "pass": "ubuntu",
    },
}

_MACHINE_CACHE_FILE = Path(__file__).parent / ".machine"

def get_current_machine():
    """Return current machine key ('kal' or 'ubuntu')."""
    if _MACHINE_CACHE_FILE.exists():
        return _MACHINE_CACHE_FILE.read_text().strip()
    return "kal"

def set_current_machine(key):
    """Set current machine. Returns True if valid."""
    if key not in MACHINES:
        return False
    _MACHINE_CACHE_FILE.write_text(key)
    return True

def get_machine_config(key=None):
    """Get a machine config dict. If key is None, returns current machine."""
    if key is None:
        key = get_current_machine()
    return MACHINES.get(key, MACHINES["kal"])

def machine_path(*parts):
    """Resolve a path relative to the current machine's home directory."""
    cfg = get_machine_config()
    if parts and parts[0].startswith("/home/osboxes"):
        return Path(str(parts[0]).replace("/home/osboxes", cfg["home"], 1))
    return Path(cfg["home"], *parts)

def get_machine_data_dir():
    """Get and ensure the data directory exists for the current machine."""
    cfg = get_machine_config()
    d = Path(cfg["data_dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_machine_download_dir():
    """Get and ensure the download directory exists for the current machine."""
    cfg = get_machine_config()
    d = Path(cfg["download_dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d

DATA_DIR = get_machine_data_dir()
COMMAND_HISTORY_FILE = DATA_DIR / "cmd_history.json"
VNC_PASSWORD_FILE = DATA_DIR / "vnc_pass.txt"
PHONE_NUMBERS_FILE = DATA_DIR / "phone_numbers.json"

# ============ LOGGING ============

# Log level: set LOG_LEVEL env var to DEBUG for verbose output, INFO by default
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
_log_level = getattr(logging, LOG_LEVEL, logging.INFO)

# JSON logs on Render (structured for Render Log Explorer), text locally
_use_json = os.environ.get("JSON_LOGS", "false").lower() in ("true", "1", "yes")

class JsonFormatter(logging.Formatter):
    """Structured JSON formatter for Render Log Explorer."""
    def format(self, record):
        log_entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

# --- Configure Root Logger ---
root_logger = logging.getLogger()
root_logger.setLevel(_log_level)

# Remove default handlers to avoid duplicate output
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# 1) Stream handler: JSON on Render, colored text locally
stream = logging.StreamHandler()
stream.setLevel(_log_level)
if _use_json:
    stream.setFormatter(JsonFormatter())
else:
    stream.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
root_logger.addHandler(stream)

# 2) Rotating file handler (for local debugging, /tmp on Render is ephemeral)
try:
    log_dir = Path("/tmp/guid_erbot")
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        str(log_dir / "bot.log"),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(_log_level)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    root_logger.addHandler(file_handler)
    root_logger.info(f"📁 File logging enabled: {log_dir / 'bot.log'} (max 5MB, 3 backups)")
except (OSError, PermissionError) as e:
    root_logger.warning(f"⚠️  Could not create file logger: {e}")

# Module logger (used by bot.py and extra_commands.py via imports)
logger = logging.getLogger(__name__)

# ============ UTILITY ============

def is_authorized(user_id):
    """Check if user is authorized."""
    return user_id in ADMIN_IDS

def escape_md(text):
    """Escape markdown special characters."""
    if not text:
        return ""
    chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for c in chars:
        text = text.replace(c, f"\\{c}")
    return text

async def reply_long(update: Update, text: str, parse_mode=None):
    """Reply with long text, splitting if necessary."""
    max_len = 4000
    if len(text) <= max_len:
        await update.effective_message.reply_text(text, parse_mode=parse_mode)
    else:
        for i in range(0, len(text), max_len):
            chunk = text[i:i+max_len]
            await update.effective_message.reply_text(chunk, parse_mode=parse_mode)

async def run_shell(cmd: str, timeout=30):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return output if output else "(No output)"
    except subprocess.TimeoutExpired:
        return f"(Command timed out after {timeout}s)"
    except Exception as e:
        return f"(Error: {e})"

def format_bytes(bytes_val):
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"

# ============ COMMAND HISTORY ============

def _get_history_file():
    """Get command history file path for the current machine."""
    return get_machine_data_dir() / "cmd_history.json"

def load_command_history():
    """Load command history from file."""
    path = _get_history_file()
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []

def save_command_history(history):
    """Save command history to file."""
    path = _get_history_file()
    try:
        with open(path, "w") as f:
            json.dump(history[-50:], f)
    except OSError as e:
        logger.error(f"Failed to save command history: {e}")

def add_to_history(cmd, output_preview):
    """Add a command to history."""
    history = load_command_history()
    history.append({
        "time": datetime.now().isoformat(),
        "command": cmd[:100],
        "output_preview": output_preview[:100],
    })
    save_command_history(history)

# ============ PHONE NUMBER STORAGE ============

def _get_phone_file():
    """Get phone numbers file path for the current machine."""
    return get_machine_data_dir() / "phone_numbers.json"

def load_phone_numbers():
    """Load saved phone numbers from file."""
    path = _get_phone_file()
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def save_phone_number(user_id, phone, first_name=""):
    """Save a phone number for a user."""
    numbers = load_phone_numbers()
    numbers[str(user_id)] = {
        "phone": phone,
        "first_name": first_name,
        "saved_at": datetime.now().isoformat(),
    }
    path = _get_phone_file()
    try:
        with open(path, "w") as f:
            json.dump(numbers, f, indent=2)
    except OSError as e:
        logger.error(f"Failed to save phone number: {e}")

def get_phone_number(user_id):
    """Get saved phone number for a user."""
    numbers = load_phone_numbers()
    return numbers.get(str(user_id))
