#!/usr/bin/env python3
"""
utils.py - Shared utilities for guid_erbot
Common functions used by bot.py and extra_commands.py
"""

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

# ============ CONFIGURATION ============

# Read admin IDs from environment variable (set in Render dashboard)
_ADMIN_IDS_ENV = os.environ.get("ADMIN_IDS", "8004724563")
ADMIN_IDS = [int(x.strip()) for x in _ADMIN_IDS_ENV.split(",") if x.strip()]

OSBOXES_USER = "osboxes"
OSBOXES_PASS = "osboxes.org"

DATA_DIR = Path("/home/osboxes/guid_erbot/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

COMMAND_HISTORY_FILE = DATA_DIR / "cmd_history.json"
VNC_PASSWORD_FILE = DATA_DIR / "vnc_pass.txt"
PHONE_NUMBERS_FILE = DATA_DIR / "phone_numbers.json"

# ============ LOGGING ============

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
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

def load_command_history():
    """Load command history from file."""
    if COMMAND_HISTORY_FILE.exists():
        try:
            with open(COMMAND_HISTORY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    return []

def save_command_history(history):
    """Save command history to file."""
    try:
        with open(COMMAND_HISTORY_FILE, "w") as f:
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

def load_phone_numbers():
    """Load saved phone numbers from file."""
    if PHONE_NUMBERS_FILE.exists():
        try:
            with open(PHONE_NUMBERS_FILE) as f:
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
    try:
        with open(PHONE_NUMBERS_FILE, "w") as f:
            json.dump(numbers, f, indent=2)
    except OSError as e:
        logger.error(f"Failed to save phone number: {e}")

def get_phone_number(user_id):
    """Get saved phone number for a user."""
    numbers = load_phone_numbers()
    return numbers.get(str(user_id))
