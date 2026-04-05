import os
import sys
import subprocess

# ═══════════════════════════════════════════════════════════════════
# ᴀᴜᴛᴏ ɪɴsᴛᴀʟʟ ʀᴇQᴜɪʀᴇᴍᴇɴᴛs
# ═══════════════════════════════════════════════════════════════════
def auto_install_requirements():
    req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    if os.path.exists(req_file):
        print(f"📦 ᴀᴜᴛᴏ ɪɴsᴛᴀʟʟɪɴɢ ʀᴇQᴜɪʀᴇᴍᴇɴᴛs ғʀᴏᴍ {req_file}...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                print("✅ ʀᴇQᴜɪʀᴇᴍᴇɴᴛs ɪɴsᴛᴀʟʟᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ")
            else:
                print(f"⚠️ ɪɴsᴛᴀʟʟ ᴡᴀʀɴɪɴɢ: {result.stderr[:500]}")
        except Exception as e:
            print(f"⚠️ ᴀᴜᴛᴏ ɪɴsᴛᴀʟʟ ᴇʀʀᴏʀ: {e}")
    else:
        print("ℹ️ ɴᴏ requirements.txt ғᴏᴜɴᴅ, sᴋɪᴘᴘɪɴɢ ᴀᴜᴛᴏ ɪɴsᴛᴀʟʟ")

auto_install_requirements()

import zipfile
import shutil
import asyncio
import logging
import time
import signal
import platform
import json
import threading
import traceback
from threading import Thread, Lock
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request
from telegram import ReplyKeyboardMarkup, KeyboardButton, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ═══════════════════════════════════════════════════════════════════
# ᴄᴏɴғɪɢᴜʀᴀᴛɪᴏɴ
# ═══════════════════════════════════════════════════════════════════
TOKEN = os.environ.get('BOT_TOKEN', '8673472964:AAF4Wne-zENnUlXTRgv0L4ql-YelVoe50GE')

PRIMARY_ADMIN_ID = int(os.environ.get('ADMIN_ID_1', '8423357174'))

SUB_ADMINS = []

ADMIN_IDS = [PRIMARY_ADMIN_ID] + SUB_ADMINS

ADMIN_USERNAME = "@BD_ADMIN_20"
ADMIN_DISPLAY_NAME = "💞 ʙᴅ ᴀᴅᴍɪɴ 💞"

BASE_DIR = os.path.join(os.getcwd(), "hosted_projects")
LOGS_DIR = os.path.join(os.getcwd(), "logs")
DATA_FILE = os.path.join(os.getcwd(), "bot_data.json")
PORT = int(os.environ.get('PORT', 8080))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

for dir_path in [BASE_DIR, LOGS_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# ═══════════════════════════════════════════════════════════════════
# ɢʟᴏʙᴀʟ ᴅᴀᴛᴀ
# ═══════════════════════════════════════════════════════════════════
data_lock = Lock()
running_processes = {}
bot_locked = False
auto_restart_mode = True
recovery_enabled = True
user_upload_state = {}
project_owners = {}
recovery_stats = {
    "total_restarts": 0,
    "last_restart": None,
    "crash_count": 0
}

locked_users = {}
blocked_users = {}
force_join_channels = []
all_users = {}

live_logs_tasks = {}
live_logs_status = {}
live_logs_message_ids = {}

# ᴛᴇʀᴍᴜx sʏsᴛᴇᴍ ᴅᴀᴛᴀ
termux_sessions = {}
termux_cwd = {}
termux_processes = {}
all_command_sessions = {}

# ᴀʟʟ ᴘʀᴏᴊᴇᴄᴛ ᴅᴀᴛᴀ - ᴘʀᴏᴊᴇᴄᴛs ʀᴜɴ ᴠɪᴀ ᴛᴇʀᴍᴜx sʏsᴛᴇᴍ
termux_projects = {}

# ═══════════════════════════════════════════════════════════════════
# ᴅᴀᴛᴀ ᴘᴇʀsɪsᴛᴇɴᴄᴇ
# ═══════════════════════════════════════════════════════════════════
def save_data():
    with data_lock:
        data = {
            "project_owners": project_owners,
            "recovery_stats": recovery_stats,
            "locked_users": locked_users,
            "blocked_users": blocked_users,
            "sub_admins": SUB_ADMINS,
            "force_join_channels": force_join_channels,
            "all_users": all_users,
            "termux_projects": termux_projects,
            "timestamp": time.time()
        }
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("✅ ᴅᴀᴛᴀ sᴀᴠᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ")
        except Exception as e:
            logger.error(f"❌ ᴅᴀᴛᴀ sᴀᴠᴇ ᴇʀʀᴏʀ: {e}")

def load_data():
    global project_owners, recovery_stats, locked_users, blocked_users, SUB_ADMINS, force_join_channels, all_users, ADMIN_IDS, termux_projects
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                project_owners = data.get("project_owners", {})
                recovery_stats = data.get("recovery_stats", recovery_stats)
                locked_users = data.get("locked_users", {})
                blocked_users = data.get("blocked_users", {})
                SUB_ADMINS = data.get("sub_admins", [])
                ADMIN_IDS = [PRIMARY_ADMIN_ID] + SUB_ADMINS
                force_join_channels = data.get("force_join_channels", [])
                all_users = data.get("all_users", {})
                termux_projects = data.get("termux_projects", {})
                logger.info("✅ ᴘʀᴇᴠɪᴏᴜs ᴅᴀᴛᴀ ʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ")
        except Exception as e:
            logger.error(f"❌ ᴅᴀᴛᴀ ʟᴏᴀᴅ ᴇʀʀᴏʀ: {e}")

load_data()

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("⚠️ ᴘsᴜᴛɪʟ ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ")

print(f"🤖 ʙᴏᴛ sᴛᴀʀᴛɪɴɢ...")
print(f"👑 ᴏᴡɴᴇʀ ɪᴅ: {PRIMARY_ADMIN_ID}")
print(f"👥 sᴜʙ-ᴀᴅᴍɪɴs: {SUB_ADMINS}")
print(f"📁 ʙᴀsᴇ ᴅɪʀ: {BASE_DIR}")

# ═══════════════════════════════════════════════════════════════════
# ᴘʏᴛʜᴏɴ ʙᴏᴏᴛsᴛʀᴀᴘ - ᴍᴜʟᴛɪᴘʀᴏᴄᴇssɪɴɢ ғɪx ғᴏʀ ʀᴇɴᴅᴇʀ/sᴇʀᴠᴇʀ
# ═══════════════════════════════════════════════════════════════════
BOOTSTRAP_FILE = os.path.join(os.getcwd(), "_py_bootstrap.py")

BOOTSTRAP_CODE = '''\
import sys
import os
import multiprocessing

# ᴀᴜᴛᴏ ғɪx: ᴜsᴇ ғᴏʀᴋ ᴏɴ ʟɪɴᴜx (ʀᴇɴᴅᴇʀ, ᴠᴘs, ʀᴇᴘʟɪᴛ)
if sys.platform != "win32":
    try:
        multiprocessing.set_start_method("fork", force=True)
    except RuntimeError:
        pass

if len(sys.argv) < 2:
    print("Bootstrap: no script provided")
    sys.exit(1)

script_path = sys.argv[1]
sys.argv = sys.argv[1:]

if not os.path.isabs(script_path):
    script_path = os.path.join(os.getcwd(), script_path)

import runpy
runpy.run_path(script_path, run_name="__main__")
'''

def create_bootstrap_file():
    try:
        with open(BOOTSTRAP_FILE, 'w', encoding='utf-8') as f:
            f.write(BOOTSTRAP_CODE)
        logger.info(f"✅ ʙᴏᴏᴛsᴛʀᴀᴘ ғɪʟᴇ ᴄʀᴇᴀᴛᴇᴅ: {BOOTSTRAP_FILE}")
    except Exception as e:
        logger.error(f"❌ ʙᴏᴏᴛsᴛʀᴀᴘ ғɪʟᴇ ᴇʀʀᴏʀ: {e}")

create_bootstrap_file()

def wrap_python_command(command: str, cwd: str) -> str:
    """ᴡʀᴀᴘ ᴘʏᴛʜᴏɴ ᴄᴏᴍᴍᴀɴᴅ ᴡɪᴛʜ ʙᴏᴏᴛsᴛʀᴀᴘ ᴛᴏ ғɪx ᴍᴜʟᴛɪᴘʀᴏᴄᴇssɪɴɢ"""
    cmd = command.strip()
    python_prefixes = ["python3 ", "python "]
    for prefix in python_prefixes:
        if cmd.startswith(prefix):
            rest = cmd[len(prefix):].strip()
            py_bin = prefix.strip()
            # ɪɴᴊᴇᴄᴛ ʙᴏᴏᴛsᴛʀᴀᴘ ʙᴇꜰᴏʀᴇ ᴛʜᴇ ᴛᴀʀɢᴇᴛ sᴄʀɪᴘᴛ
            return f'{py_bin} "{BOOTSTRAP_FILE}" {rest}'
    return command

# ═══════════════════════════════════════════════════════════════════
# ʜᴇʟᴘᴇʀ ғᴜɴᴄᴛɪᴏɴs
# ═══════════════════════════════════════════════════════════════════
def is_admin(user_id):
    return user_id == PRIMARY_ADMIN_ID or user_id in SUB_ADMINS

def is_primary_admin(user_id):
    return user_id == PRIMARY_ADMIN_ID

def get_project_status(p_name):
    if p_name not in running_processes:
        return "offline"
    proc = running_processes[p_name]
    if proc.poll() is None:
        return "online"
    return "crashed"

def get_termux_project_status(p_name):
    if p_name not in termux_processes:
        return "offline"
    proc = termux_processes[p_name]
    if proc.poll() is None:
        return "online"
    return "offline"

def to_small_caps(text):
    if not text:
        return ""
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    small_caps = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ0123456789"
    result = ""
    for char in text:
        if char in normal:
            idx = normal.index(char)
            result += small_caps[idx]
        else:
            result += char
    return result

def escape_markdown(text):
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, '\\' + char)
    return text

def format_username(username):
    if not username:
        return "ɴᴏ ᴜsᴇʀɴᴀᴍᴇ"
    username = username.strip()
    if username.startswith('@'):
        username = username[1:]
    return f"@{username}"

def get_bd_admin_name(index):
    """ɢᴇɴᴇʀᴀᴛᴇ ʙᴅ-ᴀᴅᴍɪɴ ɴᴀᴍᴇ ʙʏ ɪɴᴅᴇx"""
    number_map = {1: "➊", 2: "➋", 3: "➌", 4: "➍", 5: "➎",
                  6: "➏", 7: "➐", 8: "➑", 9: "➒", 10: "➓"}
    num = number_map.get(index, f"({index})")
    return f"ʙᴅ-ᴀᴅᴍɪɴ-{num} ✨"

def get_next_bd_admin_index():
    """ɢᴇᴛ ɴᴇxᴛ ᴀᴠᴀɪʟᴀʙʟᴇ ɪɴᴅᴇx ғᴏʀ ɴᴇᴡ ᴘʀᴏᴊᴇᴄᴛ"""
    used_indices = set()
    number_map_reverse = {"➊": 1, "➋": 2, "➌": 3, "➍": 4, "➎": 5,
                          "➏": 6, "➐": 7, "➑": 8, "➒": 9, "➓": 10}
    for name in termux_projects.keys():
        for sym, idx in number_map_reverse.items():
            if sym in name:
                used_indices.add(idx)
                break
    idx = 1
    while idx in used_indices:
        idx += 1
    return idx

def renumber_termux_projects():
    """ʀᴇɴᴜᴍʙᴇʀ ᴀʟʟ ᴛᴇʀᴍᴜx ᴘʀᴏᴊᴇᴄᴛs ᴀғᴛᴇʀ ᴅᴇʟᴇᴛɪᴏɴ"""
    global termux_projects, termux_processes
    if not termux_projects:
        return

    old_names = list(termux_projects.keys())
    new_projects = {}
    new_processes = {}

    for i, old_name in enumerate(old_names, 1):
        new_name = get_bd_admin_name(i)
        data = termux_projects[old_name]
        data["bd_name"] = new_name
        new_projects[new_name] = data

        if old_name in termux_processes:
            new_processes[new_name] = termux_processes[old_name]
        elif new_name in termux_processes:
            new_processes[new_name] = termux_processes[new_name]

    termux_projects = new_projects
    termux_processes = new_processes
    save_data()
    logger.info(f"✅ ᴛᴇʀᴍᴜx ᴘʀᴏᴊᴇᴄᴛs ʀᴇɴᴜᴍʙᴇʀᴇᴅ: {list(termux_projects.keys())}")

# ═══════════════════════════════════════════════════════════════════
# ʟᴏᴀᴅɪɴɢ ᴀɴɪᴍᴀᴛɪᴏɴs
# ═══════════════════════════════════════════════════════════════════
class Loading:
    @staticmethod
    def executing():
        return [
            "🌺 ᴇxᴇᴄᴜᴛɪɴɢ: [▱▱▱▱▱▱▱▱▱▱] 0%",
            "🌼 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▱▱▱▱▱▱▱▱] 10%",
            "🌻 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▱▱▱▱▱▱▱] 20%",
            "🌸 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▱▱▱▱▱▱] 30%",
            "🌹 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▰▱▱▱▱▱] 40%",
            "🍁 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▰▰▱▱▱▱] 50%",
            "🌿 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▰▰▰▱▱▱] 60%",
            "🌳 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▰▰▰▰▱▱] 70%",
            "🌲 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▰▰▰▰▰▱] 80%",
            "🪷 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▰▰▰▰▰▰] 90%",
            "✅ ᴄᴏᴍᴘʟᴇᴛᴇ: [▰▰▰▰▰▰▰▰▰▰] 100%"
        ]

    @staticmethod
    def uploading():
        return [
            "🗳️ ᴜᴘʟᴏᴀᴅɪɴɢ: [▱▱▱▱▱▱▱▱▱▱] 0%",
            "🗳️ ᴜᴘʟᴏᴀᴅɪɴɢ: [▰▰▱▱▱▱▱▱▱▱] 25%",
            "🗳️ ᴜᴘʟᴏᴀᴅɪɴɢ: [▰▰▰▰▱▱▱▱▱▱] 50%",
            "🗳️ ᴜᴘʟᴏᴀᴅɪɴɢ: [▰▰▰▰▰▰▱▱▱▱] 75%",
            "✅ ᴜᴘʟᴏᴀᴅ ᴄᴏᴍᴘʟᴇᴛᴇ: [▰▰▰▰▰▰▰▰▰▰] 100%"
        ]

    @staticmethod
    def installing():
        return [
            "📦 ɪɴsᴛᴀʟʟɪɴɢ: [▱▱▱▱▱▱▱▱▱▱] 0%",
            "📦 ɪɴsᴛᴀʟʟɪɴɢ: [▰▰▱▱▱▱▱▱▱▱] 20%",
            "📦 ɪɴsᴛᴀʟʟɪɴɢ: [▰▰▰▰▱▱▱▱▱▱] 40%",
            "📦 ɪɴsᴛᴀʟʟɪɴɢ: [▰▰▰▰▰▰▱▱▱▱] 60%",
            "📦 ɪɴsᴛᴀʟʟɪɴɢ: [▰▰▰▰▰▰▰▰▱▱] 80%",
            "✅ ɪɴsᴛᴀʟʟᴇᴅ: [▰▰▰▰▰▰▰▰▰▰] 100%"
        ]

    @staticmethod
    def deleting():
        return [
            "🗑️ ᴅᴇʟᴇᴛɪɴɢ: [▱▱▱▱▱▱▱▱▱▱] 0%",
            "🗑️ ᴅᴇʟᴇᴛɪɴɢ: [▰▰▰▱▱▱▱▱▱▱] 30%",
            "🗑️ ᴅᴇʟᴇᴛɪɴɢ: [▰▰▰▰▰▰▱▱▱▱] 60%",
            "✅ ᴅᴇʟᴇᴛᴇᴅ: [▰▰▰▰▰▰▰▰▰▰] 100%"
        ]

    @staticmethod
    def restarting():
        return [
            "🇧🇩 ʀᴇsᴛᴀʀᴛɪɴɢ: [▱▱▱▱▱▱▱▱▱▱] 0%",
            "🇧🇷 ʀᴇsᴛᴀʀᴛɪɴɢ: [▰▰▱▱▱▱▱▱▱▱] 20%",
            "🇦🇷 ʀᴇsᴛᴀʀᴛɪɴɢ: [▰▰▰▰▱▱▱▱▱▱] 40%",
            "🇦🇨 ʀᴇsᴛᴀʀᴛɪɴɢ: [▰▰▰▰▰▰▱▱▱▱] 60%",
            "🇬🇵 ʀᴇsᴛᴀʀᴛɪɴɢ: [▰▰▰▰▰▰▰▰▱▱] 80%",
            "✅ ʀᴇsᴛᴀʀᴛᴇᴅ: [▰▰▰▰▰▰▰▰▰▰] 100%"
        ]

    @staticmethod
    def recovering():
        return [
            "🔄 ʀᴇᴄᴏᴠᴇʀɪɴɢ: [▱▱▱▱▱▱▱▱▱▱] 0%",
            "🔄 ʀᴇᴄᴏᴠᴇʀɪɴɢ: [▰▰▰▱▱▱▱▱▱▱] 30%",
            "🔄 ʀᴇᴄᴏᴠᴇʀɪɴɢ: [▰▰▰▰▰▰▱▱▱▱] 60%",
            "✅ ʀᴇᴄᴏᴠᴇʀᴇᴅ: [▰▰▰▰▰▰▰▰▰▰] 100%"
        ]

    @staticmethod
    def health_check():
        return [
            "🏩 sʏsᴛᴇᴍ ᴄʜᴇᴄᴋ: [▱▱▱▱▱▱▱▱▱▱] 0%",
            "🏩 sʏsᴛᴇᴍ ᴄʜᴇᴄᴋ: [▰▰▱▱▱▱▱▱▱▱] 25%",
            "🏩 sʏsᴛᴇᴍ ᴄʜᴇᴄᴋ: [▰▰▰▰▱▱▱▱▱▱] 50%",
            "🏩 sʏsᴛᴇᴍ ᴄʜᴇᴄᴋ: [▰▰▰▰▰▰▱▱▱▱] 75%",
            "✅ sʏsᴛᴇᴍ ʀᴇᴀᴅʏ: [▰▰▰▰▰▰▰▰▰▰] 100%"
        ]

    @staticmethod
    def live_logs():
        return [
            "📺 ʟɪᴠᴇ ʟᴏɢs: [▱▱▱▱▱▱▱▱▱▱] 0%",
            "📺 ʟɪᴠᴇ ʟᴏɢs: [▰▰▱▱▱▱▱▱▱▱] 25%",
            "📺 ʟɪᴠᴇ ʟᴏɢs: [▰▰▰▰▱▱▱▱▱▱] 50%",
            "📺 ʟɪᴠᴇ ʟᴏɢs: [▰▰▰▰▰▰▱▱▱▱] 75%",
            "✅ ʟɪᴠᴇ ʟᴏɢs ʀᴇᴀᴅʏ: [▰▰▰▰▰▰▰▰▰▰] 100%"
        ]

# ═══════════════════════════════════════════════════════════════════
# ғʟᴀsᴋ ᴡᴇʙ sᴇʀᴠᴇʀ
# ═══════════════════════════════════════════════════════════════════
app = Flask(__name__)

@app.route('/')
def home():
    try:
        running_count = len([p for p, proc in running_processes.items() if proc.poll() is None])
    except:
        running_count = 0
    return jsonify({
        "status": "online",
        "service": to_small_caps("Apon Premium Hosting v1"),
        "version": "2.0",
        "projects": len(project_owners),
        "running": running_count,
        "recovery": recovery_enabled,
        "auto_restart": auto_restart_mode,
        "uptime": recovery_stats.get("last_restart", to_small_caps("Unknown"))
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()}), 200

@app.route('/api/projects')
def api_projects():
    projects = []
    for name, data in project_owners.items():
        status = get_project_status(name)
        projects.append({
            "name": name,
            "owner": data.get("u_name"),
            "status": status,
            "user_id": data.get("u_id")
        })
    return jsonify(projects)

def run_web():
    try:
        app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True, use_reloader=False)
    except Exception as e:
        logger.error(f"ᴡᴇʙ sᴇʀᴠᴇʀ ᴇʀʀᴏʀ: {e}")

# ═══════════════════════════════════════════════════════════════════
# sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ
# ═══════════════════════════════════════════════════════════════════
async def get_system_health():
    try:
        if PSUTIL_AVAILABLE:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            ram = psutil.virtual_memory()
            ram_used_gb = ram.used / (1024**3)
            ram_total_gb = ram.total / (1024**3)
            ram_percent = ram.percent
            disk = psutil.disk_usage('/')
            disk_used_gb = disk.used / (1024**3)
            disk_total_gb = disk.total / (1024**3)
            disk_percent = disk.percent
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            total_projects = len(project_owners)
            running_count = 0
            for p_name in running_processes:
                try:
                    if running_processes[p_name].poll() is None:
                        running_count += 1
                except:
                    pass
            return {
                "status": "ok",
                "cpu": f"{cpu_percent}%",
                "cpu_cores": cpu_count,
                "ram": f"{ram_percent}%",
                "ram_used": f"{ram_used_gb:.1f}GB",
                "ram_total": f"{ram_total_gb:.1f}GB",
                "disk": f"{disk_percent}%",
                "disk_used": f"{disk_used_gb:.1f}GB",
                "disk_total": f"{disk_total_gb:.1f}GB",
                "uptime": f"{int(uptime//3600)}h {int((uptime%3600)//60)}m",
                "projects": total_projects,
                "running": running_count,
                "recovery_stats": recovery_stats
            }
        else:
            return {
                "status": "basic",
                "platform": platform.system(),
                "machine": platform.machine(),
                "processor": platform.processor() or "unknown",
                "python_version": platform.python_version(),
                "projects": len(project_owners),
                "running": 0
            }
    except Exception as e:
        logger.error(f"sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ ᴇʀʀᴏʀ: {e}")
        return {"status": "error", "error": str(e)}

# ═══════════════════════════════════════════════════════════════════
# ᴍᴀɪɴ ᴋᴇʏʙᴏᴀʀᴅ
# ═══════════════════════════════════════════════════════════════════
def get_main_keyboard(user_id):
    base_layout = [
        [KeyboardButton("🗳️ ᴜᴘʟᴏᴀᴅ ᴍᴀɴᴀɢᴇʀ"), KeyboardButton("📮 ғɪʟᴇ ᴍᴀɴᴀɢᴇʀ")],
        [KeyboardButton("🗑️ ᴅᴇʟᴇᴛᴇ ᴍᴀɴᴀɢᴇʀ"), KeyboardButton("🏩 sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ")],
        [KeyboardButton("🌎 sᴇʀᴠᴇʀ ɪɴғᴏ"), KeyboardButton("📠 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ")],
        [KeyboardButton("📺 ʟɪᴠᴇ ʟᴏɢs ᴏɴ"), KeyboardButton("📴 ʟɪᴠᴇ ʟᴏɢs ᴏғғ")],
        [KeyboardButton("💻 ᴛᴇʀᴍᴜx sʏsᴛᴇᴍ"), KeyboardButton("⌨️ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅ")]
    ]
    if is_primary_admin(user_id):
        base_layout.append([KeyboardButton("🎛️ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ")])
    elif user_id in SUB_ADMINS:
        base_layout.append([KeyboardButton("💎 ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴍɪɴ")])
    return ReplyKeyboardMarkup(base_layout, resize_keyboard=True)

# ═══════════════════════════════════════════════════════════════════
# ᴛᴇʀᴍᴜx sʏsᴛᴇᴍ ᴋᴇʏʙᴏᴀʀᴅ
# ═══════════════════════════════════════════════════════════════════
def get_termux_keyboard():
    layout = [
        [KeyboardButton("📝 ᴋᴏᴍᴀɴᴅ ʟɪᴋʜᴜɴ"), KeyboardButton("📋 ᴀʟʟ ᴘʀᴏᴊᴇᴄᴛ")],
        [KeyboardButton("🟢 ᴋᴏɴsᴏʟ ᴏɴ"), KeyboardButton("🔴 ᴋᴏɴsᴏʟ ᴏғ")],
        [KeyboardButton("🗑️ ᴅɪʟɪᴛ ᴍᴀɴᴇᴊᴀʀ")],
        [KeyboardButton("⬅️ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ")]
    ]
    return ReplyKeyboardMarkup(layout, resize_keyboard=True)

# ═══════════════════════════════════════════════════════════════════
# ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ ᴋᴇʏʙᴏᴀʀᴅ
# ═══════════════════════════════════════════════════════════════════
def get_admin_panel_keyboard(user_id):
    if not is_primary_admin(user_id):
        return ReplyKeyboardMarkup([[KeyboardButton("⬅️ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ")]], resize_keyboard=True)
    layout = [
        [KeyboardButton("🔒 ʟᴏᴄᴋ sʏsᴛᴇᴍ"), KeyboardButton("👤 ʟᴏᴄᴋ ᴜsᴇʀ")],
        [KeyboardButton("🔓 ᴜɴʟᴏᴄᴋ sʏsᴛᴇᴍ"), KeyboardButton("🔓 ᴜɴʟᴏᴄᴋ ᴜsᴇʀ")],
        [KeyboardButton("➕ ᴀᴅᴅ ᴀᴅᴍɪɴ"), KeyboardButton("➖ ʀᴇᴍᴏᴠᴇ ᴀᴅᴍɪɴ")],
        [KeyboardButton("📢 sᴍs ᴀʟʟ"), KeyboardButton("📨 ᴘʀɪᴠᴀᴛᴇ ᴍsɢ")],
        [KeyboardButton("🚫 ʙʟᴏᴄᴋ"), KeyboardButton("✅ ᴜɴʙʟᴏᴄᴋ")],
        [KeyboardButton("➕ ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ"), KeyboardButton("➖ ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ")],
        [KeyboardButton("🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ"), KeyboardButton("🛡️ ʀᴇᴄᴏᴠᴇʀʏ")],
        [KeyboardButton("🎬 ᴘʀᴏᴊᴇᴄᴛ ғɪʟᴇs"), KeyboardButton("📋 ᴀʟʟ ᴘʀᴏᴊᴇᴄᴛs")],
        [KeyboardButton("🪐 ʀᴇsᴛᴀʀᴛ ᴀʟʟ"), KeyboardButton("👥 ᴜsᴇʀs")],
        [KeyboardButton("⬅️ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ")]
    ]
    return ReplyKeyboardMarkup(layout, resize_keyboard=True)

# ═══════════════════════════════════════════════════════════════════
# ʟɪᴠᴇ ʟᴏɢs ғᴜɴᴄᴛɪᴏɴs
# ═══════════════════════════════════════════════════════════════════
async def show_live_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, p_name: str):
    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            user_id = update.callback_query.from_user.id
            chat_id = update.callback_query.message.chat.id
        elif hasattr(update, 'message') and update.message:
            user_id = update.message.from_user.id
            chat_id = update.message.chat.id
        else:
            logger.error("ᴄᴀɴɴᴏᴛ ᴅᴇᴛᴇʀᴍɪɴᴇ ᴜsᴇʀ/ᴄʜᴀᴛ ғʀᴏᴍ ᴜᴘᴅᴀᴛᴇ")
            return

        if user_id in live_logs_tasks:
            try:
                task = live_logs_tasks[user_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            except Exception as e:
                logger.error(f"ᴇʀʀᴏʀ sᴛᴏᴘᴘɪɴɢ ᴘʀᴇᴠɪᴏᴜs ʟɪᴠᴇ ʟᴏɢs: {e}")

        log_file = os.path.join(LOGS_DIR, f"{p_name}.log")

        if not os.path.exists(log_file):
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ ɴᴏ ʟᴏɢ ғɪʟᴇ ғᴏᴜɴᴅ ғᴏʀ {p_name}!\nᴘʟᴇᴀsᴇ ʀᴜɴ ᴛʜᴇ ᴘʀᴏᴊᴇᴄᴛ ғɪʀsᴛ."
            )
            return

        live_logs_status[user_id] = {
            "project": p_name,
            "running": True,
            "chat_id": chat_id,
            "start_time": datetime.now(),
            "message_count": 0
        }

        live_logs_message_ids[user_id] = []

        start_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴\n"
                f"📺 ʟɪᴠᴇ ʟᴏɢs sᴛᴀʀᴛᴇᴅ: {p_name}\n"
                f"🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴\n"
                f"⏱️ sᴛᴀʀᴛᴇᴅ ᴀᴛ: {datetime.now().strftime('%H:%M:%S')}\n"
                f"📝 ɴᴇᴡ ʟᴏɢs ᴡɪʟʟ ᴀᴘᴘᴇᴀʀ ʙᴇʟᴏᴡ...\n"
                f"📴 ᴄʟɪᴄᴋ 'ᴋᴏɴsᴏʟ ᴏғ' ᴛᴏ sᴛᴏᴘ\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
        )
        live_logs_message_ids[user_id].append(start_msg.message_id)

        async def logs_streamer():
            last_pos = 0
            error_count = 0
            rolling_lines = []
            console_msg_id = None
            tick = 0

            while live_logs_status.get(user_id, {}).get("running", False):
                try:
                    if not os.path.exists(log_file):
                        await asyncio.sleep(1)
                        continue

                    current_size = os.path.getsize(log_file)

                    if current_size > last_pos:
                        try:
                            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                                f.seek(last_pos)
                                new_content = f.read()
                            last_pos = current_size

                            new_lines = [l for l in new_content.split('\n') if l.strip()]
                            if new_lines:
                                rolling_lines.extend(new_lines)
                                rolling_lines = rolling_lines[-30:]
                                if user_id in live_logs_status:
                                    live_logs_status[user_id]["message_count"] += len(new_lines)

                        except Exception as e:
                            logger.error(f"ᴇʀʀᴏʀ ʀᴇᴀᴅɪɴɢ ʟᴏɢ ғɪʟᴇ: {e}")

                    tick += 1
                    spinner = ["⣾","⣽","⣻","⢿","⡿","⣟","⣯","⣷"][tick % 8]
                    display_lines = rolling_lines[-20:] if rolling_lines else [to_small_caps("waiting for output...")]
                    log_text = '\n'.join(display_lines)
                    if len(log_text) > 3500:
                        log_text = log_text[-3500:]

                    now_str = datetime.now().strftime('%H:%M:%S')
                    header = (
                        f"🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴\n"
                        f"📺 ʟɪᴠᴇ ʟᴏɢs: {p_name} {spinner}\n"
                        f"🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴\n"
                        f"⏱️ sᴛᴀʀᴛᴇᴅ: {live_logs_status.get(user_id, {}).get('start_time', datetime.now()).strftime('%H:%M:%S') if isinstance(live_logs_status.get(user_id, {}).get('start_time'), datetime) else ''}\n"
                        f"🕐 ʟᴀsᴛ ᴜᴘᴅᴀᴛᴇ: {now_str}\n"
                        f"📴 ᴄʟɪᴄᴋ 'ʟɪᴠᴇ ʟᴏɢs ᴏғғ' ᴛᴏ sᴛᴏᴘ\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    )
                    full_text = header + log_text

                    try:
                        if console_msg_id is None:
                            msg = await context.bot.send_message(
                                chat_id=chat_id,
                                text=full_text
                            )
                            console_msg_id = msg.message_id
                            live_logs_message_ids[user_id].append(console_msg_id)
                        else:
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=chat_id,
                                    message_id=console_msg_id,
                                    text=full_text
                                )
                            except Exception as edit_err:
                                err_str = str(edit_err)
                                if "message is not modified" in err_str:
                                    pass
                                elif "Message to edit not found" in err_str or "message_id_invalid" in err_str:
                                    console_msg_id = None
                                else:
                                    raise
                        error_count = 0
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        error_count += 1
                        logger.error(f"ʟɪᴠᴇ ʟᴏɢs sᴇɴᴅ ᴇʀʀᴏʀ: {e}")
                        if error_count > 15:
                            break
                        await asyncio.sleep(2)
                        continue

                    await asyncio.sleep(1)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"ʟɪᴠᴇ ʟᴏɢs sᴛʀᴇᴀᴍᴇʀ ᴇʀʀᴏʀ: {e}")
                    await asyncio.sleep(2)

            try:
                if user_id in live_logs_status:
                    duration = datetime.now() - live_logs_status[user_id]['start_time']
                    msg_count = live_logs_status[user_id]['message_count']
                else:
                    duration = "?"
                    msg_count = "?"
                end_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                        f"📴 ʟɪᴠᴇ ʟᴏɢs sᴛᴏᴘᴘᴇᴅ: {p_name}\n"
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                        f"⏱️ ᴅᴜʀᴀᴛɪᴏɴ: {str(duration).split('.')[0] if duration != '?' else '?'}\n"
                        f"📝 ᴛᴏᴛᴀʟ ʟɪɴᴇs: {msg_count}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    )
                )
                live_logs_message_ids[user_id].append(end_msg.message_id)
            except Exception as e:
                logger.error(f"ᴇʀʀᴏʀ sᴇɴᴅɪɴɢ ғɪɴᴀʟ ʟɪᴠᴇ ʟᴏɢs ᴍᴇssᴀɢᴇ: {e}")

            if user_id in live_logs_status:
                del live_logs_status[user_id]

        task = asyncio.create_task(logs_streamer())
        live_logs_tasks[user_id] = task

    except Exception as e:
        logger.error(f"sʜᴏᴡ ʟɪᴠᴇ ʟᴏɢs ᴇʀʀᴏʀ: {e}")
        try:
            if 'chat_id' in locals():
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ ᴇʀʀᴏʀ ɪɴ ʟɪᴠᴇ ʟᴏɢs: {str(e)}"
                )
        except:
            pass


async def stop_live_logs(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    stopped = False
    if user_id in live_logs_status:
        live_logs_status[user_id]["running"] = False
        stopped = True
    if user_id in live_logs_tasks:
        try:
            task = live_logs_tasks[user_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del live_logs_tasks[user_id]
        except Exception as e:
            logger.error(f"ᴇʀʀᴏʀ ᴄᴀɴᴄᴇʟɪɴɢ ʟɪᴠᴇ ʟᴏɢs ᴛᴀsᴋ: {e}")
    return stopped

# ═══════════════════════════════════════════════════════════════════
# ᴛᴇʀᴍᴜx ᴋᴏɴsᴏʟ sᴛʀᴇᴀᴍᴇʀ (ʟɪᴠᴇ ᴄᴏɴᴛɪɴᴜᴏᴜs)
# ═══════════════════════════════════════════════════════════════════
async def show_termux_console(user_id: int, chat_id: int, p_name: str, context: ContextTypes.DEFAULT_TYPE):
    """ᴛᴇʀᴍᴜx ᴘʀᴏᴊᴇᴄᴛ ᴋᴏɴsᴏʟ - ʟɪᴠᴇ ᴄᴏɴᴛɪɴᴜᴏᴜs sᴛʀᴇᴀᴍɪɴɢ"""
    try:
        if user_id in live_logs_tasks:
            try:
                task = live_logs_tasks[user_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            except:
                pass

        if user_id in live_logs_status:
            live_logs_status[user_id]["running"] = False

        log_file = os.path.join(LOGS_DIR, f"termux_{p_name}.log")

        if not os.path.exists(log_file):
            open(log_file, 'a').close()

        live_logs_status[user_id] = {
            "project": p_name,
            "running": True,
            "chat_id": chat_id,
            "start_time": datetime.now(),
            "message_count": 0,
            "type": "termux"
        }

        live_logs_message_ids[user_id] = []

        start_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴\n"
                f"🖥️ ᴛᴇʀᴍᴜx ᴋᴏɴsᴏʟ: {p_name}\n"
                f"🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴\n"
                f"⏱️ sᴛᴀʀᴛᴇᴅ: {datetime.now().strftime('%H:%M:%S')}\n"
                f"📝 ʟɪᴠᴇ ᴏᴜᴛᴘᴜᴛ ᴡɪʟʟ ᴀᴘᴘᴇᴀʀ ʜᴇʀᴇ...\n"
                f"🔴 ᴄʟɪᴄᴋ 'ᴋᴏɴsᴏʟ ᴏғ' ᴛᴏ sᴛᴏᴘ\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
        )
        live_logs_message_ids[user_id].append(start_msg.message_id)

        async def termux_streamer():
            last_pos = 0
            error_count = 0
            rolling_lines = []
            console_msg_id = None
            tick = 0

            while live_logs_status.get(user_id, {}).get("running", False):
                try:
                    if not os.path.exists(log_file):
                        await asyncio.sleep(1)
                        continue

                    current_size = os.path.getsize(log_file)

                    if current_size > last_pos:
                        try:
                            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                                f.seek(last_pos)
                                new_content = f.read()
                            last_pos = current_size

                            new_lines = [l for l in new_content.split('\n') if l.strip()]
                            if new_lines:
                                rolling_lines.extend(new_lines)
                                rolling_lines = rolling_lines[-30:]
                                if user_id in live_logs_status:
                                    live_logs_status[user_id]["message_count"] += len(new_lines)

                        except Exception as e:
                            logger.error(f"ᴛᴇʀᴍᴜx ʟᴏɢ ʀᴇᴀᴅ ᴇʀʀᴏʀ: {e}")

                    tick += 1
                    spinner = ["⣾","⣽","⣻","⢿","⡿","⣟","⣯","⣷"][tick % 8]
                    display_lines = rolling_lines[-20:] if rolling_lines else [to_small_caps("waiting for output...")]
                    log_text = '\n'.join(display_lines)
                    if len(log_text) > 3500:
                        log_text = log_text[-3500:]

                    now_str = datetime.now().strftime('%H:%M:%S')
                    header = (
                        f"🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴\n"
                        f"🖥️ ᴛᴇʀᴍᴜx ᴋᴏɴsᴏʟ: {p_name} {spinner}\n"
                        f"🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴\n"
                        f"⏱️ sᴛᴀʀᴛᴇᴅ: {datetime.now().strftime('%H:%M:%S')}\n"
                        f"🕐 ʟᴀsᴛ ᴜᴘᴅᴀᴛᴇ: {now_str}\n"
                        f"🔴 ᴄʟɪᴄᴋ 'ᴋᴏɴsᴏʟ ᴏғ' ᴛᴏ sᴛᴏᴘ\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    )
                    full_text = header + log_text

                    try:
                        if console_msg_id is None:
                            msg = await context.bot.send_message(
                                chat_id=chat_id,
                                text=full_text
                            )
                            console_msg_id = msg.message_id
                            live_logs_message_ids[user_id].append(console_msg_id)
                        else:
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=chat_id,
                                    message_id=console_msg_id,
                                    text=full_text
                                )
                            except Exception as edit_err:
                                err_str = str(edit_err)
                                if "message is not modified" in err_str:
                                    pass
                                elif "Message to edit not found" in err_str or "message_id_invalid" in err_str:
                                    console_msg_id = None
                                else:
                                    raise
                        error_count = 0
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        error_count += 1
                        logger.error(f"ᴛᴇʀᴍᴜx sᴇɴᴅ ᴇʀʀᴏʀ: {e}")
                        if error_count > 15:
                            break
                        await asyncio.sleep(2)
                        continue

                    await asyncio.sleep(1)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"ᴛᴇʀᴍᴜx sᴛʀᴇᴀᴍᴇʀ ᴇʀʀᴏʀ: {e}")
                    await asyncio.sleep(2)

            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                        f"🔴 ᴋᴏɴsᴏʟ sᴛᴏᴘᴘᴇᴅ: {p_name}\n"
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴"
                    )
                )
            except:
                pass

            if user_id in live_logs_status:
                del live_logs_status[user_id]

        task = asyncio.create_task(termux_streamer())
        live_logs_tasks[user_id] = task

    except Exception as e:
        logger.error(f"ᴛᴇʀᴍᴜx ᴄᴏɴsᴏʟᴇ ᴇʀʀᴏʀ: {e}")

# ═══════════════════════════════════════════════════════════════════
# ᴘʀᴏᴊᴇᴄᴛ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ
# ═══════════════════════════════════════════════════════════════════
def restart_project(p_name):
    try:
        if p_name in running_processes:
            try:
                proc = running_processes[p_name]
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except:
                    proc.kill()
                    try:
                        proc.wait(timeout=2)
                    except:
                        pass
                del running_processes[p_name]
            except Exception as e:
                logger.error(f"ᴇʀʀᴏʀ sᴛᴏᴘᴘɪɴɢ ᴇxɪsᴛɪɴɢ ᴘʀᴏᴄᴇss: {e}")

        if p_name not in project_owners:
            logger.error(f"ᴘʀᴏᴊᴇᴄᴛ {p_name} ɴᴏᴛ ғᴏᴜɴᴅ")
            return False

        data = project_owners[p_name]
        folder = data["path"]
        main_file = data.get("main_file", "main.py")
        main_file_path = os.path.join(folder, main_file)

        if not os.path.exists(main_file_path):
            logger.error(f"ᴍᴀɪɴ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ: {main_file_path}")
            return False

        log_file = os.path.join(LOGS_DIR, f"{p_name}.log")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        try:
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"\n\n--- sᴛᴀʀᴛᴇᴅ ᴀᴛ {datetime.now()} ---\n")
                log.flush()

                proc = subprocess.Popen(
                    [sys.executable, BOOTSTRAP_FILE, main_file_path],
                    cwd=folder,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env
                )

            running_processes[p_name] = proc
            project_owners[p_name]["last_run"] = time.time()
            project_owners[p_name]["run_count"] = project_owners[p_name].get("run_count", 0) + 1
            save_data()
            logger.info(f"ᴘʀᴏᴊᴇᴄᴛ {p_name} sᴛᴀʀᴛᴇᴅ ᴡɪᴛʜ ᴘɪᴅ {proc.pid}")
            return True

        except Exception as e:
            logger.error(f"ᴇʀʀᴏʀ sᴛᴀʀᴛɪɴɢ ᴘʀᴏᴄᴇss: {e}")
            return False

    except Exception as e:
        logger.error(f"ʀᴇsᴛᴀʀᴛ ᴇʀʀᴏʀ ғᴏʀ {p_name}: {e}")
        return False


def stop_project(p_name):
    try:
        if p_name not in running_processes:
            return False, "ᴘʀᴏᴊᴇᴄᴛ ɴᴏᴛ ʀᴜɴɴɪɴɢ"
        proc = running_processes[p_name]
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except:
                pass
        del running_processes[p_name]
        return True, "ᴘʀᴏᴊᴇᴄᴛ sᴛᴏᴘᴘᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ"
    except Exception as e:
        logger.error(f"sᴛᴏᴘ ᴇʀʀᴏʀ ғᴏʀ {p_name}: {e}")
        return False, str(e)


def delete_project(p_name):
    try:
        if p_name in running_processes:
            try:
                running_processes[p_name].terminate()
                running_processes[p_name].wait(timeout=3)
            except:
                pass
            del running_processes[p_name]

        for uid, status in list(live_logs_status.items()):
            if status.get("project") == p_name:
                status["running"] = False

        path = os.path.join(BASE_DIR, p_name)
        if os.path.exists(path):
            shutil.rmtree(path)

        if p_name in project_owners:
            del project_owners[p_name]
            save_data()

        return True, "ᴘʀᴏᴊᴇᴄᴛ ᴅᴇʟᴇᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ"

    except Exception as e:
        logger.error(f"ᴅᴇʟᴇᴛᴇ ᴇʀʀᴏʀ ғᴏʀ {p_name}: {e}")
        return False, str(e)

# ═══════════════════════════════════════════════════════════════════
# ᴛᴇʀᴍᴜx sʏsᴛᴇᴍ - ᴋᴏᴍᴀɴᴅ ᴇxᴇᴄᴜᴛᴇ
# ═══════════════════════════════════════════════════════════════════
def run_termux_command(user_id: int, command: str) -> str:
    """ᴛᴇʀᴍᴜx ᴇʀ ᴍᴛᴏ ᴋᴏᴍᴀɴᴅ ᴄʜᴀʟᴀᴏ"""
    try:
        cwd = termux_cwd.get(user_id, os.path.expanduser("~"))

        if not os.path.exists(cwd):
            cwd = os.getcwd()
            termux_cwd[user_id] = cwd

        if command.startswith("cd "):
            new_path = command[3:].strip()
            if new_path == "~":
                new_path = os.path.expanduser("~")
            elif not os.path.isabs(new_path):
                new_path = os.path.join(cwd, new_path)

            new_path = os.path.normpath(new_path)

            if os.path.isdir(new_path):
                termux_cwd[user_id] = new_path
                return f"✅ ᴅɪʀᴇᴄᴛᴏʀʏ ᴄʜᴀɴɢᴇᴅ ᴛᴏ: {new_path}"
            else:
                return f"❌ ᴅɪʀᴇᴄᴛᴏʀʏ ɴᴏᴛ ғᴏᴜɴᴅ: {new_path}"

        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
            env=os.environ.copy()
        )

        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr

        if not output:
            output = "✅ ᴄᴏᴍᴍᴀɴᴅ ᴇxᴇᴄᴜᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ"

        return output[:3500]

    except subprocess.TimeoutExpired:
        return "⏱️ ᴄᴏᴍᴍᴀɴᴅ ᴛɪᴍᴇᴅ ᴏᴜᴛ (30s)"
    except Exception as e:
        return f"❌ ᴇʀʀᴏʀ: {str(e)}"


def start_termux_project(user_id: int, command: str, bd_name: str) -> bool:
    """ᴛᴇʀᴍᴜx ᴛʜᴇᴋᴇ ᴘʀᴏᴊᴇᴄᴛ ʀᴀɴ ᴋᴏʀᴏ"""
    try:
        cwd = termux_cwd.get(user_id, os.getcwd())

        log_file_path = os.path.join(LOGS_DIR, f"termux_{bd_name}.log")

        safe_command = wrap_python_command(command, cwd)

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        with open(log_file_path, 'a', encoding='utf-8') as log:
            log.write(f"\n\n--- sᴛᴀʀᴛᴇᴅ ᴀᴛ {datetime.now()} ---\n")
            log.write(f"ᴄᴏᴍᴍᴀɴᴅ: {command}\n")
            log.write(f"ᴅɪʀᴇᴄᴛᴏʀʏ: {cwd}\n\n")
            log.flush()

            proc = subprocess.Popen(
                safe_command,
                shell=True,
                cwd=cwd,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )

        termux_processes[bd_name] = proc
        termux_projects[bd_name] = {
            "command": command,
            "cwd": cwd,
            "user_id": user_id,
            "started_at": time.time(),
            "pid": proc.pid,
            "bd_name": bd_name
        }
        save_data()
        logger.info(f"ᴛᴇʀᴍᴜx ᴘʀᴏᴊᴇᴄᴛ {bd_name} sᴛᴀʀᴛᴇᴅ (ᴘɪᴅ {proc.pid})")
        return True

    except Exception as e:
        logger.error(f"ᴛᴇʀᴍᴜx sᴛᴀʀᴛ ᴇʀʀᴏʀ: {e}")
        return False


def stop_termux_project(bd_name: str) -> bool:
    """ᴛᴇʀᴍᴜx ᴘʀᴏᴊᴇᴄᴛ sᴛᴏᴘ ᴋᴏʀᴏ"""
    try:
        if bd_name not in termux_processes:
            return False
        proc = termux_processes[bd_name]
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except:
                pass
        del termux_processes[bd_name]
        return True
    except Exception as e:
        logger.error(f"ᴛᴇʀᴍᴜx sᴛᴏᴘ ᴇʀʀᴏʀ: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════
# sᴛᴀʀᴛ ᴄᴏᴍᴍᴀɴᴅ
# ═══════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user = update.effective_user

        if user_id in blocked_users:
            await update.message.reply_text("🚫 ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ʙʟᴏᴄᴋᴇᴅ ғʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ.")
            return

        if force_join_channels and not is_admin(user_id):
            not_joined = []
            for channel in force_join_channels:
                try:
                    member = await context.bot.get_chat_member(channel["channel_id"], user_id)
                    if member.status in ['left', 'kicked']:
                        not_joined.append(channel)
                except:
                    not_joined.append(channel)

            if not_joined:
                keyboard = []
                msg_text = (
                    f"🌺 {escape_markdown(to_small_caps('Welcome to Apon Premium Hosting'))} 🌺\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔒 {escape_markdown(to_small_caps('Please join our channels first:'))}\n\n"
                )
                for i, ch in enumerate(not_joined, 1):
                    msg_text += f"{i}. {escape_markdown(ch['name'])}\n"
                    keyboard.append([InlineKeyboardButton(f"📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ {i}", url=ch["link"])])
                keyboard.append([InlineKeyboardButton("✅ ᴠᴇʀɪғʏ ᴊᴏɪɴ", callback_data="verify_join")])
                await update.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='MarkdownV2')
                return

        if bot_locked and not is_admin(user_id):
            await update.message.reply_text("🔒 sʏsᴛᴇᴍ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ʟᴏᴄᴋᴇᴅ ʙʏ ᴀᴅᴍɪɴ")
            return

        if user_id in locked_users and not is_admin(user_id):
            await update.message.reply_text("🔒 ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɪs ʟᴏᴄᴋᴇᴅ ʙʏ ᴀᴅᴍɪɴ.")
            return

        if user_id not in all_users:
            all_users[user_id] = {
                "name": user.full_name or "Unknown",
                "username": user.username or "no_username",
                "first_seen": time.time()
            }
            save_data()

        user_name = to_small_caps(user.full_name or "Unknown")
        username_raw = user.username if user.username else None
        username_formatted = format_username(username_raw)
        username_display = to_small_caps(username_formatted) if username_raw else "ɴᴏ ᴜsᴇʀɴᴀᴍᴇ"
        user_id_str = str(user_id)

        user_name_escaped = escape_markdown(user_name)
        username_display_escaped = escape_markdown(username_display)

        try:
            photos = await context.bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id
                caption = (
                    f"🌍 {escape_markdown(to_small_caps('Apon Premium Hosting v1'))} 🌸\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💙 {escape_markdown(to_small_caps('Welcome to the Elite Panel'))}\n"
                    f"🔮 {escape_markdown(to_small_caps('Most Powerful Premium Server'))}\n"
                    f"🚀 {escape_markdown(to_small_caps('Support: Telegram Bot, Web App, Games, Tools'))}\n\n"
                    f"👤 {escape_markdown(to_small_caps('Your Info:'))}\n"
                    f"🆔 {escape_markdown(to_small_caps('User ID:'))} {user_id_str}\n"
                    f"📛 {escape_markdown(to_small_caps('Name:'))} {user_name_escaped}\n"
                    f"🔗 {escape_markdown(to_small_caps('Username:'))} {username_display_escaped}\n"
                    f"🇧🇩 {escape_markdown(to_small_caps('Owner:'))} {escape_markdown(to_small_caps(ADMIN_USERNAME))}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )
                await update.message.reply_photo(photo=file_id, caption=caption, reply_markup=get_main_keyboard(user_id), parse_mode='MarkdownV2')
                return
        except Exception as e:
            logger.error(f"ᴘʀᴏғɪʟᴇ ᴘʜᴏᴛᴏ ᴇʀʀᴏʀ: {e}")

        msg = (
            f"🌍 {escape_markdown(to_small_caps('Apon Premium Hosting v1'))} 🌸\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💙 {escape_markdown(to_small_caps('Welcome to the Elite Panel'))}\n"
            f"🔮 {escape_markdown(to_small_caps('Most Powerful Premium Server'))}\n"
            f"🚀 {escape_markdown(to_small_caps('Support: Telegram Bot, Web App, Games, Tools'))}\n\n"
            f"👤 {escape_markdown(to_small_caps('Your Info:'))}\n"
            f"🆔 {escape_markdown(to_small_caps('User ID:'))} {user_id_str}\n"
            f"📛 {escape_markdown(to_small_caps('Name:'))} {user_name_escaped}\n"
            f"🔗 {escape_markdown(to_small_caps('Username:'))} {username_display_escaped}\n"
            f"🇧🇩 {escape_markdown(to_small_caps('Owner:'))} {escape_markdown(to_small_caps(ADMIN_USERNAME))}\n"
            f"━━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(msg, reply_markup=get_main_keyboard(user_id), parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"sᴛᴀʀᴛ ᴄᴏᴍᴍᴀɴᴅ ᴇʀʀᴏʀ: {e}")
        try:
            await update.message.reply_text(
                f"{to_small_caps('Welcome to Apon Premium Hosting v1')}\n"
                f"{to_small_caps('Your ID:')} {user_id}\n"
                f"{to_small_caps('Owner:')} {ADMIN_USERNAME}",
                reply_markup=get_main_keyboard(user_id)
            )
        except:
            pass

# ═══════════════════════════════════════════════════════════════════
# ᴅᴏᴄᴜᴍᴇɴᴛ ʜᴀɴᴅʟᴇʀ
# ═══════════════════════════════════════════════════════════════════
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user = update.effective_user

        if user_id in blocked_users:
            await update.message.reply_text("🚫 ʏᴏᴜ ᴀʀᴇ ʙʟᴏᴄᴋᴇᴅ.")
            return
        if bot_locked and not is_admin(user_id):
            await update.message.reply_text("🔒 sʏsᴛᴇᴍ ɪs ʟᴏᴄᴋᴇᴅ")
            return
        if user_id in locked_users and not is_admin(user_id):
            await update.message.reply_text("🔒 ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɪs ʟᴏᴄᴋᴇᴅ")
            return
        if not update.message.document:
            await update.message.reply_text("❌ ɴᴏ ғɪʟᴇ ғᴏᴜɴᴅ!")
            return

        doc = update.message.document

        if not doc.file_name.endswith('.zip'):
            await update.message.reply_text("❌ ᴏɴʟʏ .ᴢɪᴘ ғɪʟᴇs ᴀʀᴇ ᴀᴄᴄᴇᴘᴛᴇᴅ!")
            return
        if doc.file_size > 20 * 1024 * 1024:
            await update.message.reply_text("❌ ғɪʟᴇ sɪᴢᴇ ᴍᴀxɪᴍᴜᴍ 20ᴍʙ!")
            return

        msg = await update.message.reply_text("🗳️ ᴜᴘʟᴏᴀᴅɪɴɢ: [▱▱▱▱▱▱▱▱▱▱] 0%")

        try:
            frames = Loading.uploading()
            for i, frame in enumerate(frames):
                await asyncio.sleep(0.8)
                try:
                    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=frame)
                except Exception as e:
                    logger.warning(f"ᴜᴘʟᴏᴀᴅ ᴀɴɪᴍᴀᴛɪᴏɴ ᴇʀʀᴏʀ: {e}")

            temp_dir = os.path.join(BASE_DIR, f"tmp_{user_id}_{int(time.time())}")
            os.makedirs(temp_dir, exist_ok=True)
            zip_path = os.path.join(temp_dir, doc.file_name)

            try:
                file = await doc.get_file()
                await file.download_to_drive(zip_path)
            except Exception as e:
                logger.error(f"❌ ғɪʟᴇ ᴅᴏᴡɴʟᴏᴀᴅ ᴇʀʀᴏʀ: {e}")
                await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ ғɪʟᴇ!")
                return

            user_upload_state[user_id] = {
                "path": zip_path,
                "u_name": user.full_name or "Unknown",
                "u_username": user.username or "no_username",
                "original_name": doc.file_name,
                "temp_dir": temp_dir,
                "chat_id": update.effective_chat.id,
                "message_id": msg.message_id
            }

            try:
                user_name = user.full_name or "Unknown"
                username = user.username or "no_username"
                upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                file_size_kb = doc.file_size / 1024
                owner_caption = (
                    f"🚨 <b>NEW FILE UPLOADED</b> 🚨\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>User:</b> {user_name}\n"
                    f"🔗 <b>Username:</b> @{username}\n"
                    f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                    f"📁 <b>File Name:</b> <code>{doc.file_name}</code>\n"
                    f"📊 <b>Size:</b> {file_size_kb:.1f} KB\n"
                    f"⏰ <b>Upload Time:</b> {upload_time}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🤖 <b>Bot:</b> Apon Premium Hosting v1\n"
                    f"✅ <b>Auto-Forwarded to Owner</b>"
                )
                with open(zip_path, 'rb') as f:
                    await context.bot.send_document(chat_id=PRIMARY_ADMIN_ID, document=f, filename=doc.file_name, caption=owner_caption, parse_mode='HTML')
            except Exception as e:
                logger.error(f"❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴀᴜᴛᴏ-ғᴏʀᴡᴀʀᴅ: {e}")

            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id,
                text=(
                    "✅ ᴜᴘʟᴏᴀᴅ ᴄᴏᴍᴘʟᴇᴛᴇ!\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🖋️ {to_small_caps('Now send a project name:')}\n"
                    f"• {to_small_caps('Use English letters or numbers')}\n"
                    f"• {to_small_caps('Use _ (underscore) instead of spaces')}\n"
                    f"• {to_small_caps('Example: my_bot, project123, test_v2')}\n"
                    "━━━━━━━━━━━━━━━━━━━━━"
                )
            )

        except Exception as e:
            logger.error(f"ᴜᴘʟᴏᴀᴅ ᴘʀᴏᴄᴇssɪɴɢ ᴇʀʀᴏʀ: {e}")
            await update.message.reply_text(f"❌ ᴜᴘʟᴏᴀᴅ ғᴀɪʟᴇᴅ: {str(e)}")

    except Exception as e:
        logger.error(f"ᴅᴏᴄᴜᴍᴇɴᴛ ʜᴀɴᴅʟᴇʀ ᴇʀʀᴏʀ: {e}")
        try:
            await update.message.reply_text("❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ, ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.")
        except:
            pass

# ═══════════════════════════════════════════════════════════════════
# ᴛᴇxᴛ ʜᴀɴᴅʟᴇʀ
# ═══════════════════════════════════════════════════════════════════
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text
        global bot_locked, auto_restart_mode, recovery_enabled

        if user_id in blocked_users:
            await update.message.reply_text("🚫 ʏᴏᴜ ᴀʀᴇ ʙʟᴏᴄᴋᴇᴅ.")
            return
        if bot_locked and not is_admin(user_id):
            await update.message.reply_text("🔒 sʏsᴛᴇᴍ ɪs ʟᴏᴄᴋᴇᴅ")
            return
        if user_id in locked_users and not is_admin(user_id):
            await update.message.reply_text("🔒 ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɪs ʟᴏᴄᴋᴇᴅ")
            return

        if user_id in user_upload_state and "path" in user_upload_state[user_id]:
            await handle_project_naming(update, context, user_id, text)
            return

        if user_id in user_upload_state and "state" in user_upload_state[user_id]:
            state_type = user_upload_state[user_id].get("state", "")
            if state_type == "termux_command":
                await handle_termux_command_input(update, context, user_id, text)
                return
            elif state_type == "all_command":
                await handle_all_command_input(update, context, user_id, text)
                return
            elif state_type == "termux_restart_command":
                await handle_termux_restart_command(update, context, user_id, text)
                return
            elif is_primary_admin(user_id):
                await handle_admin_panel_inputs(update, context, user_id, text)
            else:
                await update.message.reply_text("❌ ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ!")
                del user_upload_state[user_id]
            return

        await handle_buttons(update, context, user_id, text)

    except Exception as e:
        logger.error(f"ᴛᴇxᴛ ʜᴀɴᴅʟᴇʀ ᴇʀʀᴏʀ: {e}")

# ═══════════════════════════════════════════════════════════════════
# ᴛᴇʀᴍᴜx ᴄᴏᴍᴍᴀɴᴅ ɪɴᴘᴜᴛ ʜᴀɴᴅʟᴇʀ
# ═══════════════════════════════════════════════════════════════════
async def handle_termux_command_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    """ᴋᴏᴍᴀɴᴅ ʟɪᴋʜᴜɴ ᴇʀ ᴘᴏʀ ᴋᴏᴍᴀɴᴅ ᴇxᴇᴄᴜᴛᴇ"""
    try:
        cwd = termux_cwd.get(user_id, os.getcwd())

        is_run_command = (text.startswith("python ") or text.startswith("python3 ") or
                          text.startswith("node ") or text.startswith("bash ") or
                          text.startswith("sh "))

        if is_run_command:
            next_index = get_next_bd_admin_index()
            bd_name = get_bd_admin_name(next_index)

            msg = await update.message.reply_text(f"🚀 {to_small_caps('Starting project as')} {bd_name}...")

            success = start_termux_project(user_id, text, bd_name)

            if success:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=msg.message_id,
                    text=(
                        f"✅ ᴘʀᴏᴊᴇᴄᴛ sᴛᴀʀᴛᴇᴅ!\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📛 {to_small_caps('Name:')} {bd_name}\n"
                        f"⚡ {to_small_caps('Command:')} {text}\n"
                        f"📁 {to_small_caps('Directory:')} {cwd}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"💡 {to_small_caps('Go to ALL PROJECT to manage it')}"
                    )
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=msg.message_id,
                    text=f"❌ {to_small_caps('Failed to start project!')}"
                )
        else:
            msg = await update.message.reply_text(f"⚙️ {to_small_caps('Executing command...')}")

            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(None, run_termux_command, user_id, text)

            cwd_now = termux_cwd.get(user_id, os.getcwd())

            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id,
                text=f"💻 {to_small_caps('Command:')} {text}\n📁 {cwd_now}\n\n{output[:3500]}"
            )

        if user_id in user_upload_state and user_upload_state[user_id].get("state") == "termux_command":
            del user_upload_state[user_id]

        await update.message.reply_text(
            f"💻 {to_small_caps('Termux System')}\n"
            f"📁 {to_small_caps('Current dir:')} {termux_cwd.get(user_id, os.getcwd())}\n"
            f"{to_small_caps('Send next command or press back')}",
            reply_markup=get_termux_keyboard()
        )

    except Exception as e:
        logger.error(f"ᴛᴇʀᴍᴜx ᴄᴏᴍᴍᴀɴᴅ ɪɴᴘᴜᴛ ᴇʀʀᴏʀ: {e}")
        await update.message.reply_text(f"❌ {to_small_caps('Error:')} {str(e)}")
        if user_id in user_upload_state:
            del user_upload_state[user_id]


async def handle_termux_restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    """ᴀʟʟ ᴘʀᴏᴊᴇᴄᴛ ᴛʜᴇᴋᴇ ᴘʀᴏᴊᴇᴄᴛ ʀᴇsᴛᴀʀᴛ"""
    try:
        bd_name = user_upload_state[user_id].get("bd_name", "")

        if not bd_name:
            await update.message.reply_text("❌ ᴇʀʀᴏʀ: ɴᴏ ᴘʀᴏᴊᴇᴄᴛ sᴇʟᴇᴄᴛᴇᴅ")
            del user_upload_state[user_id]
            return

        stop_termux_project(bd_name)

        old_data = termux_projects.get(bd_name, {})
        cwd = old_data.get("cwd", termux_cwd.get(user_id, os.getcwd()))
        termux_cwd[user_id] = cwd

        success = start_termux_project(user_id, text, bd_name)

        if success:
            await update.message.reply_text(
                f"✅ {bd_name} {to_small_caps('restarted!')}\n"
                f"⚡ {to_small_caps('Command:')} {text}"
            )
        else:
            await update.message.reply_text(f"❌ {to_small_caps('Failed to restart!')} {bd_name}")

        del user_upload_state[user_id]
        await update.message.reply_text(to_small_caps("Termux System"), reply_markup=get_termux_keyboard())

    except Exception as e:
        logger.error(f"ᴛᴇʀᴍᴜx ʀᴇsᴛᴀʀᴛ ᴇʀʀᴏʀ: {e}")
        await update.message.reply_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")
        if user_id in user_upload_state:
            del user_upload_state[user_id]


async def handle_all_command_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    """ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅ ᴇxᴇᴄᴜᴛᴇ"""
    try:
        msg = await update.message.reply_text(f"⚙️ {to_small_caps('Executing...')}")

        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(None, run_termux_command, user_id, text)

        cwd_now = termux_cwd.get(user_id, os.getcwd())

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg.message_id,
            text=f"⌨️ {to_small_caps('Command:')} {text}\n📁 {cwd_now}\n\n{output[:3500]}"
        )

        if user_id in user_upload_state and user_upload_state[user_id].get("state") == "all_command":
            del user_upload_state[user_id]

        await update.message.reply_text(
            f"⌨️ {to_small_caps('All Command')}\n"
            f"📁 {to_small_caps('Current dir:')} {cwd_now}\n"
            f"{to_small_caps('Send next command or press back')}",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("⬅️ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ")]],
                resize_keyboard=True
            )
        )

    except Exception as e:
        logger.error(f"ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅ ᴇʀʀᴏʀ: {e}")
        await update.message.reply_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")
        if user_id in user_upload_state:
            del user_upload_state[user_id]

# ═══════════════════════════════════════════════════════════════════
# ᴘʀᴏᴊᴇᴄᴛ ɴᴀᴍɪɴɢ
# ═══════════════════════════════════════════════════════════════════
async def handle_project_naming(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    try:
        state = user_upload_state[user_id]

        p_name = text.replace(" ", "_").replace("/", "_").replace("\\", "_").replace("..", "_")

        if not p_name or p_name.startswith(".") or p_name.startswith("_"):
            await update.message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ɴᴀᴍᴇ! ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.")
            return
        if len(p_name) > 50:
            await update.message.reply_text("❌ ɴᴀᴍᴇ ᴛᴏᴏ ʟᴏɴɢ! ᴍᴀxɪᴍᴜᴍ 50 ᴄʜᴀʀᴀᴄᴛᴇʀs.")
            return

        extract_path = os.path.join(BASE_DIR, p_name)

        if os.path.exists(extract_path):
            await update.message.reply_text("⚠️ ᴀ ᴘʀᴏᴊᴇᴄᴛ ᴡɪᴛʜ ᴛʜɪs ɴᴀᴍᴇ ᴀʟʀᴇᴀᴅʏ ᴇxɪsᴛs! ᴄʜᴏᴏsᴇ ᴀɴᴏᴛʜᴇʀ ɴᴀᴍᴇ.")
            return

        msg = await update.message.reply_text(Loading.executing()[0])

        try:
            os.makedirs(extract_path, exist_ok=True)
            zip_path = state["path"]

            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
            except Exception as e:
                logger.error(f"ᴢɪᴘ ᴇxᴛʀᴀᴄᴛɪᴏɴ ᴇʀʀᴏʀ: {e}")
                await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ ᴇʀʀᴏʀ ᴇxᴛʀᴀᴄᴛɪɴɢ ᴢɪᴘ ғɪʟᴇ!")
                shutil.rmtree(extract_path, ignore_errors=True)
                return

            entry_points = ["main.py", "bot.py", "app.py", "index.py", "run.py", "start.py"]
            main_file = None

            for ep in entry_points:
                if os.path.exists(os.path.join(extract_path, ep)):
                    main_file = ep
                    break

            if not main_file:
                py_files = [f for f in os.listdir(extract_path) if f.endswith('.py')]
                if py_files:
                    main_file = py_files[0]
                else:
                    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="❌ ɴᴏ ᴘʏᴛʜᴏɴ ғɪʟᴇ ғᴏᴜɴᴅ ɪɴ ᴢɪᴘ!")
                    shutil.rmtree(extract_path, ignore_errors=True)
                    shutil.rmtree(state.get("temp_dir", ""), ignore_errors=True)
                    del user_upload_state[user_id]
                    return

            req_txt = os.path.join(extract_path, "requirements.txt")
            if os.path.exists(req_txt):
                for frame in Loading.installing():
                    try:
                        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=frame)
                    except:
                        pass
                    await asyncio.sleep(1.0)

                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-r", req_txt],
                        capture_output=True, text=True, cwd=extract_path, timeout=120
                    )
                    if result.returncode != 0:
                        logger.warning(f"ʀᴇQᴜɪʀᴇᴍᴇɴᴛs ɪɴsᴛᴀʟʟ ᴡᴀʀɴɪɴɢ: {result.stderr}")
                except Exception as e:
                    logger.error(f"ʀᴇQᴜɪʀᴇᴍᴇɴᴛs ɪɴsᴛᴀʟʟ ғᴀɪʟᴇᴅ: {e}")

            project_owners[p_name] = {
                "u_id": user_id,
                "u_name": state["u_name"],
                "u_username": state.get("u_username", "no_username"),
                "zip": zip_path,
                "original_name": state["original_name"],
                "path": extract_path,
                "main_file": main_file,
                "created_at": time.time(),
                "last_run": None,
                "run_count": 0
            }
            save_data()

            shutil.rmtree(state.get("temp_dir", ""), ignore_errors=True)
            del user_upload_state[user_id]

            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id,
                text=(
                    f"✅ ᴘʀᴏᴊᴇᴄᴛ {p_name} sᴀᴠᴇᴅ!\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📁 {to_small_caps('Entry Point:')} {main_file}\n"
                    f"🚀 {to_small_caps('Go to FILE MANAGER to run')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )
            )

        except Exception as e:
            logger.error(f"ᴘʀᴏᴊᴇᴄᴛ ɴᴀᴍɪɴɢ ᴇʀʀᴏʀ: {e}")
            await update.message.reply_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")
            if user_id in user_upload_state:
                shutil.rmtree(user_upload_state[user_id].get("temp_dir", ""), ignore_errors=True)
                del user_upload_state[user_id]

    except Exception as e:
        logger.error(f"ʜᴀɴᴅʟᴇ ᴘʀᴏᴊᴇᴄᴛ ɴᴀᴍɪɴɢ ᴇʀʀᴏʀ: {e}")
        await update.message.reply_text("❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!")

# ═══════════════════════════════════════════════════════════════════
# ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ ɪɴᴘᴜᴛs
# ═══════════════════════════════════════════════════════════════════
async def handle_admin_panel_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    try:
        state = user_upload_state[user_id]
        input_type = state.get("state")

        if input_type == "lock_user":
            target = text.strip()
            try:
                target_id = int(target)
            except:
                target_id = None
                for uid, data in all_users.items():
                    if data.get("username", "").lower() == target.lower().replace("@", ""):
                        target_id = uid
                        break
            if not target_id:
                await update.message.reply_text(f"❌ {to_small_caps('User not found!')}")
                del user_upload_state[user_id]
                return
            if target_id == PRIMARY_ADMIN_ID:
                await update.message.reply_text(f"⚠️ {to_small_caps('Cannot lock primary admin!')}")
                del user_upload_state[user_id]
                return
            locked_users[target_id] = {"by": user_id, "time": time.time(), "reason": "Locked by admin"}
            save_data()
            await update.message.reply_text(f"🔒 {to_small_caps('User')} {target_id} {to_small_caps('locked successfully!')}")
            del user_upload_state[user_id]

        elif input_type == "unlock_user":
            if not locked_users:
                await update.message.reply_text(f"📭 {to_small_caps('No locked users!')}")
                del user_upload_state[user_id]
                return
            keyboard = []
            for uid, data in locked_users.items():
                user_info = all_users.get(uid, {})
                name = user_info.get("name", "Unknown")
                keyboard.append([InlineKeyboardButton(f"🔓 {name} ({uid})", callback_data=f"unlock_{uid}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_unlock")])
            await update.message.reply_text(f"🔓 {to_small_caps('Select user to unlock:')}", reply_markup=InlineKeyboardMarkup(keyboard))
            del user_upload_state[user_id]

        elif input_type == "add_admin":
            target = text.strip()
            try:
                target_id = int(target)
            except:
                target_id = None
                for uid, data in all_users.items():
                    if data.get("username", "").lower() == target.lower().replace("@", ""):
                        target_id = uid
                        break
            if not target_id:
                await update.message.reply_text(f"❌ {to_small_caps('User not found!')}")
                del user_upload_state[user_id]
                return
            if target_id in SUB_ADMINS:
                await update.message.reply_text(f"⚠️ {to_small_caps('User is already admin!')}")
            else:
                SUB_ADMINS.append(target_id)
                global ADMIN_IDS
                ADMIN_IDS = [PRIMARY_ADMIN_ID] + SUB_ADMINS
                save_data()
                await update.message.reply_text(f"➕ {to_small_caps('Admin added:')} {target_id}")
                try:
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=(
                            f"🎉 {to_small_caps('Congratulations!')}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"✨ {to_small_caps('You have been promoted to ADMIN')}\n"
                            f"🤖 {to_small_caps('Bot: Apon Premium Hosting v1')}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💎 {to_small_caps('New button added: PREMIUM ADMIN')}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━"
                        )
                    )
                except:
                    pass
            del user_upload_state[user_id]

        elif input_type == "remove_admin":
            if not SUB_ADMINS:
                await update.message.reply_text(f"📭 {to_small_caps('No sub-admins!')}")
                del user_upload_state[user_id]
                return
            keyboard = []
            for admin_id in SUB_ADMINS:
                user_info = all_users.get(admin_id, {})
                name = user_info.get("name", "Unknown")
                keyboard.append([InlineKeyboardButton(f"➖ {name} ({admin_id})", callback_data=f"removeadmin_{admin_id}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_removeadmin")])
            await update.message.reply_text(f"➖ {to_small_caps('Select admin to remove:')}", reply_markup=InlineKeyboardMarkup(keyboard))
            del user_upload_state[user_id]

        elif input_type == "sms_all":
            message = text.strip()
            sent_count = 0
            failed_count = 0
            for uid in all_users.keys():
                try:
                    await context.bot.send_message(chat_id=uid, text=f"📢 {to_small_caps('Message from Admin')}\n━━━━━━━━━━━━━━━━━━━━━\n{message}")
                    sent_count += 1
                    await asyncio.sleep(0.1)
                except:
                    failed_count += 1
            await update.message.reply_text(f"📢 {to_small_caps('SMS All Complete')}\n✅ {to_small_caps('Sent:')} {sent_count}\n❌ {to_small_caps('Failed:')} {failed_count}")
            del user_upload_state[user_id]

        elif input_type == "private_msg_user":
            target = text.strip()
            try:
                target_id = int(target)
            except:
                target_id = None
                for uid, data in all_users.items():
                    if data.get("username", "").lower() == target.lower().replace("@", ""):
                        target_id = uid
                        break
            if not target_id:
                await update.message.reply_text(f"❌ {to_small_caps('User not found!')}")
                del user_upload_state[user_id]
                return
            user_upload_state[user_id] = {"state": "private_msg_text", "target_id": target_id, "target_name": all_users.get(target_id, {}).get("name", "Unknown")}
            await update.message.reply_text(f"📨 {to_small_caps('Send your private message to')} {target_id}:")

        elif input_type == "private_msg_text":
            target_id = state.get("target_id")
            message = text.strip()
            try:
                await context.bot.send_message(chat_id=target_id, text=f"📨 {to_small_caps('Private Message from Admin')}\n━━━━━━━━━━━━━━━━━━━━━\n{message}")
                await update.message.reply_text(f"✅ {to_small_caps('Private message sent!')}")
            except:
                await update.message.reply_text(f"❌ {to_small_caps('Failed to send message!')}")
            del user_upload_state[user_id]

        elif input_type == "block_user":
            target = text.strip()
            try:
                target_id = int(target)
            except:
                target_id = None
                for uid, data in all_users.items():
                    if data.get("username", "").lower() == target.lower().replace("@", ""):
                        target_id = uid
                        break
            if not target_id:
                await update.message.reply_text(f"❌ {to_small_caps('User not found!')}")
                del user_upload_state[user_id]
                return
            if target_id == PRIMARY_ADMIN_ID:
                await update.message.reply_text(f"⚠️ {to_small_caps('Cannot block primary admin!')}")
                del user_upload_state[user_id]
                return
            blocked_users[target_id] = {"by": user_id, "time": time.time()}
            save_data()
            await update.message.reply_text(f"🚫 {to_small_caps('User blocked:')} {target_id}")
            del user_upload_state[user_id]

        elif input_type == "add_channel":
            parts = text.split("|")
            if len(parts) < 2:
                await update.message.reply_text(
                    f"❌ {to_small_caps('Invalid format!')}\n"
                    f"{to_small_caps('Use: channel_id|channel_link|channel_name')}"
                )
                del user_upload_state[user_id]
                return
            channel_data = {
                "channel_id": parts[0].strip(),
                "link": parts[1].strip(),
                "name": parts[2].strip() if len(parts) > 2 else "Channel"
            }
            force_join_channels.append(channel_data)
            save_data()
            await update.message.reply_text(f"➕ {to_small_caps('Channel added:')} {channel_data['name']}")
            del user_upload_state[user_id]

    except Exception as e:
        logger.error(f"ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ ɪɴᴘᴜᴛ ᴇʀʀᴏʀ: {e}")
        await update.message.reply_text(f"❌ {to_small_caps('Error:')} {str(e)}")
        if user_id in user_upload_state:
            del user_upload_state[user_id]

# ═══════════════════════════════════════════════════════════════════
# ʙᴜᴛᴛᴏɴ ʜᴀɴᴅʟᴇʀs
# ═══════════════════════════════════════════════════════════════════
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    global bot_locked, auto_restart_mode, recovery_enabled

    try:
        if text == "💎 ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴍɪɴ":
            if user_id not in SUB_ADMINS and user_id != PRIMARY_ADMIN_ID:
                await update.message.reply_text(f"❌ {to_small_caps('Access denied!')}")
                return
            premium_text = (
                f"💎 {escape_markdown(to_small_caps('PREMIUM ADMIN PANEL'))} 💎\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"✨ {escape_markdown(to_small_caps('Welcome to the Elite Admin Zone'))}\n\n"
                f"🌟 {escape_markdown(to_small_caps('Your Privileges:'))}\n"
                f"• {escape_markdown(to_small_caps('Unlimited File Uploads'))}\n"
                f"• {escape_markdown(to_small_caps('Unlimited Project Hosting'))}\n"
                f"• {escape_markdown(to_small_caps('Priority Server Resources'))}\n"
                f"• {escape_markdown(to_small_caps('Advanced Bot Management'))}\n"
                f"• {escape_markdown(to_small_caps('Direct Admin Support'))}\n\n"
                f"🚀 {escape_markdown(to_small_caps('You can run as many files as you want!'))}\n"
                f"🔥 {escape_markdown(to_small_caps('No restrictions, no limits!'))}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 {escape_markdown(to_small_caps('Bot: Apon Premium Hosting v1'))}\n"
                f"👑 {escape_markdown(to_small_caps('Status: ELITE ADMIN'))}"
            )
            await update.message.reply_text(premium_text, parse_mode='MarkdownV2')
            return

        if text == "🗳️ ᴜᴘʟᴏᴀᴅ ᴍᴀɴᴀɢᴇʀ":
            await update.message.reply_text(
                f"🗳️ {to_small_caps('Upload Manager')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{to_small_caps('Send your .zip file containing:')}\n"
                f"• {to_small_caps('main.py / bot.py / app.py (main file)')}\n"
                f"• {to_small_caps('requirements.txt (dependencies - optional)')}\n"
                f"• {to_small_caps('Other files (config, data, etc.)')}\n\n"
                f"{to_small_caps('Tips:')}\n"
                f"• {to_small_caps('Any Telegram bot, web app, or game will work')}\n"
                f"• {to_small_caps('Maximum file size 20MB')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )

        elif text == "📮 ғɪʟᴇ ᴍᴀɴᴀɢᴇʀ":
            user_projects = [p for p, d in project_owners.items() if d.get("u_id") == user_id]
            if not user_projects:
                await update.message.reply_text(f"❌ {to_small_caps('You have no projects! Please upload first.')}")
                return
            keyboard = []
            for p in sorted(user_projects):
                status = get_project_status(p)
                status_emoji = "💚" if status == "online" else "💔" if status == "offline" else "⚠️"
                keyboard.append([InlineKeyboardButton(f"{status_emoji} {p}", callback_data=f"manage_{p}")])
            await update.message.reply_text(
                f"📮 {to_small_caps('Your Projects')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📋 {to_small_caps('Total:')} {len(user_projects)} {to_small_caps('projects')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif text == "🗑️ ᴅᴇʟᴇᴛᴇ ᴍᴀɴᴀɢᴇʀ":
            user_projects = [p for p, d in project_owners.items() if d.get("u_id") == user_id]
            if not user_projects:
                await update.message.reply_text(f"❌ {to_small_caps('You have no projects')}")
                return
            keyboard = [[InlineKeyboardButton(f"🗑️ {p}", callback_data=f"del_{p}")] for p in sorted(user_projects)]
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_delete")])
            await update.message.reply_text(
                f"🗑️ {to_small_caps('Delete Manager')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ {to_small_caps('Data cannot be recovered after deletion!')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif text == "📺 ʟɪᴠᴇ ʟᴏɢs ᴏɴ":
            user_projects = [p for p, d in project_owners.items() if d.get("u_id") == user_id]
            if not user_projects:
                await update.message.reply_text(f"❌ {to_small_caps('You have no projects! Please upload first.')}")
                return
            keyboard = []
            for p in sorted(user_projects):
                status = get_project_status(p)
                status_emoji = "💚" if status == "online" else "💔"
                keyboard.append([InlineKeyboardButton(f"{status_emoji} {p}", callback_data=f"livelogs_{p}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_livelogs")])
            await update.message.reply_text(
                f"📺 {to_small_caps('Live Logs On')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{to_small_caps('Select which project to view live logs:')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif text == "📴 ʟɪᴠᴇ ʟᴏɢs ᴏғғ":
            stopped = await stop_live_logs(user_id, context)
            if stopped:
                await update.message.reply_text(f"📴 {to_small_caps('Live Logs Off')}\n━━━━━━━━━━━━━━━━━━━━━\n✅ {to_small_caps('Live log monitoring stopped')}\n━━━━━━━━━━━━━━━━━━━━━")
            else:
                await update.message.reply_text(f"📴 {to_small_caps('Live Logs Off')}\n━━━━━━━━━━━━━━━━━━━━━\n⚠️ {to_small_caps('No live logs were running')}\n━━━━━━━━━━━━━━━━━━━━━")

        elif text == "💻 ᴛᴇʀᴍᴜx sʏsᴛᴇᴍ":
            cwd = termux_cwd.get(user_id, os.getcwd())
            await update.message.reply_text(
                f"💻 {to_small_caps('Termux System')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 {to_small_caps('Current Directory:')}\n"
                f"{cwd}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📝 {to_small_caps('Komand Likhun')} {to_small_caps('Run any command like Termux')}\n"
                f"📋 {to_small_caps('All Project')} {to_small_caps('View and manage all running projects')}\n"
                f"🟢 {to_small_caps('Konsol On')} {to_small_caps('View live console output (continuous)')}\n"
                f"🔴 {to_small_caps('Konsol Of')} {to_small_caps('Stop console output')}\n"
                f"🗑️ {to_small_caps('Dilit Manejar')} {to_small_caps('Delete a project')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=get_termux_keyboard()
            )

        elif text == "📝 ᴋᴏᴍᴀɴᴅ ʟɪᴋʜᴜɴ":
            cwd = termux_cwd.get(user_id, os.getcwd())
            user_upload_state[user_id] = {"state": "termux_command"}
            await update.message.reply_text(
                f"📝 {to_small_caps('Komand Likhun')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 {to_small_caps('Current Dir:')} {cwd}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 {to_small_caps('Examples:')}\n"
                f"  cd /sdcard/Download/\n"
                f"  ls\n"
                f"  python main.py\n"
                f"  python bot.py\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"✏️ {to_small_caps('Now type your command:')}"
            )

        elif text == "📋 ᴀʟʟ ᴘʀᴏᴊᴇᴄᴛ":
            if not termux_projects:
                await update.message.reply_text(
                    f"📋 {to_small_caps('All Project')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📭 {to_small_caps('No projects running yet.')}\n"
                    f"💡 {to_small_caps('Use Komand Likhun to start a project first.')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )
                return

            keyboard = []
            msg_text = (
                f"📋 {to_small_caps('All Projects')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 {to_small_caps('Total:')} {len(termux_projects)} {to_small_caps('project(s)')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
            )

            for bd_name, data in termux_projects.items():
                status = get_termux_project_status(bd_name)
                status_emoji = "💚" if status == "online" else "💔"
                msg_text += f"{status_emoji} {bd_name} - {to_small_caps(status)}\n"
                keyboard.append([InlineKeyboardButton(f"{status_emoji} {bd_name}", callback_data=f"tmanage_{bd_name}")])

            msg_text += f"━━━━━━━━━━━━━━━━━━━━━"

            await update.message.reply_text(
                msg_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif text == "🟢 ᴋᴏɴsᴏʟ ᴏɴ":
            if not termux_projects:
                await update.message.reply_text(
                    f"🟢 {to_small_caps('Konsol On')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📭 {to_small_caps('No projects available.')}\n"
                    f"💡 {to_small_caps('Start a project first using Komand Likhun.')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )
                return

            keyboard = []
            for bd_name, data in termux_projects.items():
                status = get_termux_project_status(bd_name)
                status_emoji = "💚" if status == "online" else "💔"
                keyboard.append([InlineKeyboardButton(f"{status_emoji} {bd_name}", callback_data=f"tkonsol_{bd_name}")])

            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_tkonsol")])

            await update.message.reply_text(
                f"🟢 {to_small_caps('Konsol On')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{to_small_caps('Select project to view live console:')}\n"
                f"• {to_small_caps('Click project name to start live streaming')}\n"
                f"• {to_small_caps('Console will stream continuously until you press Konsol Of')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif text == "🔴 ᴋᴏɴsᴏʟ ᴏғ":
            stopped = await stop_live_logs(user_id, context)
            if stopped:
                await update.message.reply_text(
                    f"🔴 {to_small_caps('Konsol Of')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ {to_small_caps('Console output stopped')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )
            else:
                await update.message.reply_text(
                    f"🔴 {to_small_caps('Konsol Of')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"⚠️ {to_small_caps('No active console to stop')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )

        elif text == "🗑️ ᴅɪʟɪᴛ ᴍᴀɴᴇᴊᴀʀ":
            if not termux_projects:
                await update.message.reply_text(
                    f"🗑️ {to_small_caps('Dilit Manejar')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📭 {to_small_caps('No projects to delete.')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )
                return

            keyboard = []
            for bd_name in termux_projects:
                keyboard.append([InlineKeyboardButton(f"🗑️ {bd_name}", callback_data=f"tdel_{bd_name}")])

            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_tdel")])

            await update.message.reply_text(
                f"🗑️ {to_small_caps('Dilit Manejar')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ {to_small_caps('Click on a project to delete it:')}\n"
                f"📌 {to_small_caps('Remaining projects will be renumbered automatically')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif text == "⌨️ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅ":
            cwd = termux_cwd.get(user_id, os.getcwd())
            user_upload_state[user_id] = {"state": "all_command"}
            await update.message.reply_text(
                f"⌨️ {to_small_caps('All Command')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 {to_small_caps('Current Dir:')} {cwd}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 {to_small_caps('You can run ANY command here:')}\n"
                f"  pip install package_name\n"
                f"  python script.py\n"
                f"  ls, pwd, cat file.txt\n"
                f"  cd /path/to/folder\n"
                f"  {to_small_caps('Any shell command')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"✏️ {to_small_caps('Type your command now:')}",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⬅️ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ")]], resize_keyboard=True)
            )

        elif text == "🏩 sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ":
            msg = await update.message.reply_text("🏩 sʏsᴛᴇᴍ ᴄʜᴇᴄᴋ: [▱▱▱▱▱▱▱▱▱▱] 0%")
            try:
                for frame in Loading.health_check()[1:]:
                    await asyncio.sleep(0.3)
                    try:
                        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=frame)
                    except:
                        pass

                health_data = await get_system_health()

                if health_data["status"] == "ok":
                    msg_text = (
                        f"🏩 {to_small_caps('System Health')}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🖥️ {to_small_caps('CPU:')} {health_data['cpu']} ({health_data['cpu_cores']} {to_small_caps('cores')})\n"
                        f"🧠 {to_small_caps('RAM:')} {health_data['ram']} ({health_data['ram_used']}/{health_data['ram_total']})\n"
                        f"💾 {to_small_caps('Disk:')} {health_data['disk']} ({health_data['disk_used']}/{health_data['disk_total']})\n"
                        f"⏱️ {to_small_caps('Uptime:')} {health_data['uptime']}\n"
                        f"📮 {to_small_caps('Projects:')} {health_data['projects']}\n"
                        f"💚 {to_small_caps('Running:')} {health_data['running']}\n"
                        f"🛡️ {to_small_caps('Recovery:')} {'ᴏɴ' if recovery_enabled else 'ᴏғғ'}\n"
                        f"🔄 {to_small_caps('Auto-Restart:')} {'ᴏɴ' if auto_restart_mode else 'ᴏғғ'}\n"
                        f"📈 {to_small_caps('Total Restarts:')} {recovery_stats['total_restarts']}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"✅ {to_small_caps('System is Healthy')}"
                    )
                else:
                    msg_text = (
                        f"🏩 {to_small_caps('System Health')}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🖥️ {to_small_caps('Platform:')} {health_data.get('platform', 'unknown')}\n"
                        f"📮 {to_small_caps('Projects:')} {health_data.get('projects', 0)}\n"
                        f"💚 {to_small_caps('Running:')} {health_data.get('running', 0)}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━"
                    )

                await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=msg_text)

            except Exception as e:
                logger.error(f"sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ ᴅɪsᴘʟᴀʏ ᴇʀʀᴏʀ: {e}")
                await update.message.reply_text(f"❌ {to_small_caps('Error loading health data')}")

        elif text == "🌎 sᴇʀᴠᴇʀ ɪɴғᴏ":
            try:
                running_projects = 0
                for p_name in list(running_processes.keys()):
                    try:
                        if running_processes[p_name].poll() is None:
                            running_projects += 1
                    except:
                        pass

                server_info = (
                    f"🌎 {to_small_caps('Server Info')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🚀 {to_small_caps('Port:')} {PORT}\n"
                    f"🛡️ {to_small_caps('Platform:')} {platform.system()} {platform.machine()}\n"
                    f"🐍 {to_small_caps('Python:')} {platform.python_version()}\n"
                )

                if PSUTIL_AVAILABLE:
                    try:
                        cpu_count = psutil.cpu_count()
                        ram = psutil.virtual_memory()
                        ram_total_gb = ram.total / (1024**3)
                        server_info += (
                            f"🖥️ {to_small_caps('CPU Cores:')} {cpu_count}\n"
                            f"🧠 {to_small_caps('Total RAM:')} {ram_total_gb:.1f}GB\n"
                        )
                    except:
                        pass

                server_info += (
                    f"🔄 {to_small_caps('Auto-Restart:')} {'ᴏɴ' if auto_restart_mode else 'ᴏғғ'}\n"
                    f"🛡️ {to_small_caps('Auto-Recovery:')} {'ᴏɴ' if recovery_enabled else 'ᴏғғ'}\n"
                    f"📋 {to_small_caps('Total Projects:')} {len(project_owners)}\n"
                    f"💚 {to_small_caps('Running:')} {running_projects}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )

                await update.message.reply_text(server_info)

            except Exception as e:
                logger.error(f"sᴇʀᴠᴇʀ ɪɴғᴏ ᴇʀʀᴏʀ: {e}")
                await update.message.reply_text(f"🌎 {to_small_caps('Server Info')}\n━━━━━━━━━━━━━━━━━━━━━\n❌ Error")

        elif text == "📠 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ":
            contact_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📠 ᴄᴏɴᴛᴀᴄᴛ ᴏᴡɴᴇʀ", url=f"tg://user?id={PRIMARY_ADMIN_ID}")],
                [InlineKeyboardButton("💬 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")]
            ])
            await update.message.reply_text(
                f"{ADMIN_DISPLAY_NAME}\n"
                f"📠 {to_small_caps('Contact Owner')}\n\n"
                f"🆔 {to_small_caps('Admin ID:')} {PRIMARY_ADMIN_ID}",
                reply_markup=contact_keyboard
            )

        elif text == "🎛️ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ":
            if not is_primary_admin(user_id):
                await update.message.reply_text(f"❌ {to_small_caps('Access denied! Only Owner can access.')}")
                return
            await update.message.reply_text(
                f"🎛️ {to_small_caps('Admin Panel')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔐 {to_small_caps('Welcome to Admin Control Center')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=get_admin_panel_keyboard(user_id)
            )

        elif text == "⬅️ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ":
            if user_id in user_upload_state:
                del user_upload_state[user_id]
            await update.message.reply_text(
                f"⬅️ {to_small_caps('Back to Main Menu')}",
                reply_markup=get_main_keyboard(user_id)
            )

        elif is_primary_admin(user_id):
            await handle_admin_buttons(update, context, user_id, text)

        else:
            await update.message.reply_text(
                f"❌ {to_small_caps('Unknown command! Please select from the menu below.')}",
                reply_markup=get_main_keyboard(user_id)
            )

    except Exception as e:
        logger.error(f"ʙᴜᴛᴛᴏɴ ʜᴀɴᴅʟᴇʀ ᴇʀʀᴏʀ: {e}")
        try:
            await update.message.reply_text(f"❌ {to_small_caps('An error occurred, please try again.')}")
        except:
            pass

# ═══════════════════════════════════════════════════════════════════
# ᴀᴅᴍɪɴ ʙᴜᴛᴛᴏɴs
# ═══════════════════════════════════════════════════════════════════
async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    global bot_locked, auto_restart_mode, recovery_enabled

    try:
        if text == "🔒 ʟᴏᴄᴋ sʏsᴛᴇᴍ":
            bot_locked = True
            await update.message.reply_text(f"🔒 sʏsᴛᴇᴍ ʟᴏᴄᴋᴇᴅ\n━━━━━━━━━━━━━━━━━━━━━\n⚠️ {to_small_caps('All users cannot access the bot now')}")
            await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_admin_panel_keyboard(user_id))

        elif text == "🔓 ᴜɴʟᴏᴄᴋ sʏsᴛᴇᴍ":
            bot_locked = False
            await update.message.reply_text(f"🔓 sʏsᴛᴇᴍ ᴜɴʟᴏᴄᴋᴇᴅ\n━━━━━━━━━━━━━━━━━━━━━\n✅ {to_small_caps('All users can access the bot now')}")
            await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_admin_panel_keyboard(user_id))

        elif text == "👤 ʟᴏᴄᴋ ᴜsᴇʀ":
            user_upload_state[user_id] = {"state": "lock_user"}
            await update.message.reply_text(f"🔒 {to_small_caps('Lock User')}\n━━━━━━━━━━━━━━━━━━━━━\n{to_small_caps('Send user ID or username to lock:')}")

        elif text == "🔓 ᴜɴʟᴏᴄᴋ ᴜsᴇʀ":
            if not locked_users:
                await update.message.reply_text(f"📭 {to_small_caps('No locked users!')}")
                return
            keyboard = []
            for uid, data in locked_users.items():
                user_info = all_users.get(uid, {})
                name = user_info.get("name", "Unknown")
                keyboard.append([InlineKeyboardButton(f"🔓 {name} ({uid})", callback_data=f"unlock_{uid}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_unlock")])
            await update.message.reply_text(f"🔓 {to_small_caps('Click on a user to unlock:')}", reply_markup=InlineKeyboardMarkup(keyboard))

        elif text == "➕ ᴀᴅᴅ ᴀᴅᴍɪɴ":
            user_upload_state[user_id] = {"state": "add_admin"}
            await update.message.reply_text(f"➕ {to_small_caps('Add Admin')}\n━━━━━━━━━━━━━━━━━━━━━\n{to_small_caps('Send user ID or username to make admin:')}\n⚠️ {to_small_caps('They will get Premium Admin button')}")

        elif text == "➖ ʀᴇᴍᴏᴠᴇ ᴀᴅᴍɪɴ":
            if not SUB_ADMINS:
                await update.message.reply_text(f"📭 {to_small_caps('No sub-admins!')}")
                return
            keyboard = []
            for admin_id in SUB_ADMINS:
                user_info = all_users.get(admin_id, {})
                name = user_info.get("name", "Unknown")
                keyboard.append([InlineKeyboardButton(f"➖ {name} ({admin_id})", callback_data=f"removeadmin_{admin_id}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_removeadmin")])
            await update.message.reply_text(f"➖ {to_small_caps('Select admin to remove:')}", reply_markup=InlineKeyboardMarkup(keyboard))

        elif text == "📢 sᴍs ᴀʟʟ":
            user_upload_state[user_id] = {"state": "sms_all"}
            await update.message.reply_text(f"📢 {to_small_caps('SMS All Users')}\n━━━━━━━━━━━━━━━━━━━━━\n{to_small_caps('Send your message to broadcast to all users:')}")

        elif text == "📨 ᴘʀɪᴠᴀᴛᴇ ᴍsɢ":
            user_upload_state[user_id] = {"state": "private_msg_user"}
            await update.message.reply_text(f"📨 {to_small_caps('Private Message')}\n━━━━━━━━━━━━━━━━━━━━━\n{to_small_caps('Send user ID or username to message:')}")

        elif text == "🚫 ʙʟᴏᴄᴋ":
            user_upload_state[user_id] = {"state": "block_user"}
            await update.message.reply_text(f"🚫 {to_small_caps('Block User')}\n━━━━━━━━━━━━━━━━━━━━━\n{to_small_caps('Send user ID or username to block:')}\n⚠️ {to_small_caps('Blocked users cannot use the bot at all')}")

        elif text == "✅ ᴜɴʙʟᴏᴄᴋ":
            if not blocked_users:
                await update.message.reply_text(f"📭 {to_small_caps('No blocked users!')}")
                return
            keyboard = []
            for uid, data in blocked_users.items():
                user_info = all_users.get(uid, {})
                name = user_info.get("name", "Unknown")
                keyboard.append([InlineKeyboardButton(f"✅ {name} ({uid})", callback_data=f"unblock_{uid}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_unblock")])
            await update.message.reply_text(f"✅ {to_small_caps('Select user to unblock:')}", reply_markup=InlineKeyboardMarkup(keyboard))

        elif text == "➕ ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ":
            user_upload_state[user_id] = {"state": "add_channel"}
            await update.message.reply_text(
                f"➕ {to_small_caps('Add Force Join Channel')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{to_small_caps('Format: channel_id|channel_link|channel_name')}\n"
                f"{to_small_caps('Example: -100123456789|https://t.me/channel|My Channel')}"
            )

        elif text == "➖ ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ":
            if not force_join_channels:
                await update.message.reply_text(f"📭 {to_small_caps('No channels added!')}")
                return
            keyboard = []
            for i, ch in enumerate(force_join_channels):
                keyboard.append([InlineKeyboardButton(f"➖ {ch['name']}", callback_data=f"delchannel_{i}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_delchannel")])
            await update.message.reply_text(f"➖ {to_small_caps('Select channel to remove:')}", reply_markup=InlineKeyboardMarkup(keyboard))

        elif text == "🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ":
            auto_restart_mode = not auto_restart_mode
            status = "ᴇɴᴀʙʟᴇᴅ ✅" if auto_restart_mode else "ᴅɪsᴀʙʟᴇᴅ ❌"
            await update.message.reply_text(f"🔄 {to_small_caps('Auto Restart:')} {status}")
            await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_admin_panel_keyboard(user_id))

        elif text == "🛡️ ʀᴇᴄᴏᴠᴇʀʏ":
            recovery_enabled = not recovery_enabled
            status = "ᴇɴᴀʙʟᴇᴅ ✅" if recovery_enabled else "ᴅɪsᴀʙʟᴇᴅ ❌"
            await update.message.reply_text(f"🛡️ {to_small_caps('Recovery:')} {status}")
            await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_admin_panel_keyboard(user_id))

        elif text == "🎬 ᴘʀᴏᴊᴇᴄᴛ ғɪʟᴇs":
            if not project_owners:
                await update.message.reply_text(f"🎬 {to_small_caps('No projects available')}")
                return
            await update.message.reply_text(f"📋 {to_small_caps('Total')} {len(project_owners)} {to_small_caps('projects')}\n{to_small_caps('Sending all files with full information...')}")
            count = 0
            for p_name, d in list(project_owners.items()):
                try:
                    owner_id = d.get('u_id', 'N/A')
                    owner_name = to_small_caps(d.get('u_name', 'Unknown'))
                    main_file = d.get('main_file', 'main.py')
                    cap = (
                        f"🎬 {escape_markdown(to_small_caps('Project:'))} {escape_markdown(p_name)}\n"
                        f"👤 {escape_markdown(to_small_caps('User:'))} {escape_markdown(owner_name)}\n"
                        f"🆔 {escape_markdown(to_small_caps('ID:'))} {owner_id}\n"
                        f"📁 {escape_markdown(to_small_caps('Entry:'))} {escape_markdown(main_file)}"
                    )
                    project_path = d.get('path')
                    zip_path = d.get('zip')
                    file_to_send = None
                    if zip_path and os.path.exists(zip_path):
                        file_to_send = zip_path
                    elif project_path and os.path.exists(project_path):
                        try:
                            tmp_zip = f"/tmp/project_{p_name}.zip"
                            with zipfile.ZipFile(tmp_zip, 'w') as zf:
                                for root, dirs, files in os.walk(project_path):
                                    for file in files:
                                        full_path = os.path.join(root, file)
                                        arcname = os.path.relpath(full_path, project_path)
                                        zf.write(full_path, arcname)
                            file_to_send = tmp_zip
                        except:
                            pass
                    if file_to_send:
                        with open(file_to_send, 'rb') as f:
                            await context.bot.send_document(
                                chat_id=update.effective_chat.id,
                                document=f,
                                filename=f"{p_name}.zip",
                                caption=cap,
                                parse_mode='MarkdownV2'
                            )
                        count += 1
                    else:
                        await update.message.reply_text(f"❌ {to_small_caps('File not found for')} {p_name}")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"ᴇʀʀᴏʀ sᴇɴᴅɪɴɢ ᴘʀᴏᴊᴇᴄᴛ ғɪʟᴇ: {e}")

            await update.message.reply_text(f"✅ {to_small_caps('Sent')} {count}/{len(project_owners)} {to_small_caps('project files')}")

        elif text == "📋 ᴀʟʟ ᴘʀᴏᴊᴇᴄᴛs":
            if not project_owners:
                await update.message.reply_text(f"📭 {to_small_caps('No projects')}")
                return
            msg_text = f"📋 {to_small_caps('All Projects')} ({len(project_owners)})\n━━━━━━━━━━━━━━━━━━━━━\n"
            for p_name, d in project_owners.items():
                status = get_project_status(p_name)
                emoji = "💚" if status == "online" else "💔"
                owner = to_small_caps(d.get('u_name', 'Unknown'))
                msg_text += f"{emoji} {p_name} - {owner}\n"
            msg_text += "━━━━━━━━━━━━━━━━━━━━━"
            await update.message.reply_text(msg_text)

        elif text == "🪐 ʀᴇsᴛᴀʀᴛ ᴀʟʟ":
            if not project_owners:
                await update.message.reply_text(f"📭 {to_small_caps('No projects to restart')}")
                return
            msg = await update.message.reply_text(f"🪐 {to_small_caps('Restarting all projects...')}")
            success_count = 0
            fail_count = 0
            for p_name in list(project_owners.keys()):
                try:
                    if restart_project(p_name):
                        success_count += 1
                    else:
                        fail_count += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    fail_count += 1
                    logger.error(f"ʀᴇsᴛᴀʀᴛ ᴀʟʟ ᴇʀʀᴏʀ ғᴏʀ {p_name}: {e}")
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id,
                text=f"✅ {to_small_caps('Restart All Complete')}\n✅ {to_small_caps('Success:')} {success_count}\n❌ {to_small_caps('Failed:')} {fail_count}"
            )

        elif text == "👥 ᴜsᴇʀs":
            total = len(all_users)
            msg_text = f"👥 {to_small_caps('All Users')} ({total})\n━━━━━━━━━━━━━━━━━━━━━\n"
            count = 0
            for uid, data in list(all_users.items()):
                if count >= 20:
                    msg_text += f"... {to_small_caps('and')} {total - 20} {to_small_caps('more')}\n"
                    break
                name = to_small_caps(data.get('name', 'Unknown'))
                username = data.get('username', 'no_username')
                msg_text += f"👤 {name} | @{username} | {uid}\n"
                count += 1
            msg_text += "━━━━━━━━━━━━━━━━━━━━━"
            await update.message.reply_text(msg_text)

    except Exception as e:
        logger.error(f"ᴀᴅᴍɪɴ ʙᴜᴛᴛᴏɴ ᴇʀʀᴏʀ: {e}")
        try:
            await update.message.reply_text(f"❌ {to_small_caps('Error:')} {str(e)}")
        except:
            pass

# ═══════════════════════════════════════════════════════════════════
# ᴄᴀʟʟʙᴀᴄᴋ ǫᴜᴇʀʏ ʜᴀɴᴅʟᴇʀ
# ═══════════════════════════════════════════════════════════════════
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = query.from_user.id

        chat_id = query.message.chat.id if query.message else None
        message_id = query.message.message_id if query.message else None

        if not chat_id or not message_id:
            logger.error("ɴᴏ ᴄʜᴀᴛ_ɪᴅ ᴏʀ ᴍᴇssᴀɢᴇ_ɪᴅ ɪɴ ᴄᴀʟʟʙᴀᴄᴋ")
            return

        # ᴛᴇʀᴍᴜx ᴘʀᴏᴊᴇᴄᴛ ᴍᴀɴᴀɢᴇ
        if data.startswith("tmanage_"):
            bd_name = data[8:]
            status = get_termux_project_status(bd_name)
            status_text = "💚 ᴏɴʟɪɴᴇ" if status == "online" else "💔 ᴏғғʟɪɴᴇ"
            data_info = termux_projects.get(bd_name, {})
            keyboard = []
            if status == "online":
                keyboard.append([InlineKeyboardButton(f"🛑 {to_small_caps('Stop')}", callback_data=f"tstop_{bd_name}")])
            else:
                keyboard.append([InlineKeyboardButton(f"▶️ {to_small_caps('Restart')}", callback_data=f"trestart_{bd_name}")])
            keyboard.append([InlineKeyboardButton(f"📺 {to_small_caps('Konsol')}", callback_data=f"tkonsol_{bd_name}")])
            keyboard.append([InlineKeyboardButton(f"🗑️ {to_small_caps('Delete')}", callback_data=f"tdel_{bd_name}")])
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"📋 {bd_name}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 {to_small_caps('Status:')} {status_text}\n"
                    f"⚡ {to_small_caps('Command:')} {data_info.get('command', 'N/A')}\n"
                    f"📁 {to_small_caps('Directory:')} {data_info.get('cwd', 'N/A')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💡 {to_small_caps('If offline, click Restart to re-run.')}"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        if data.startswith("tstop_"):
            bd_name = data[6:]
            if stop_termux_project(bd_name):
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🛑 {bd_name} {to_small_caps('stopped!')} 💔")
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"⚠️ {bd_name} {to_small_caps('is not running')}")
            return

        if data.startswith("trestart_"):
            bd_name = data[9:]
            user_upload_state[user_id] = {"state": "termux_restart_command", "bd_name": bd_name}
            old_cmd = termux_projects.get(bd_name, {}).get("command", "python main.py")
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"▶️ {to_small_caps('Restart')} {bd_name}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📝 {to_small_caps('Enter the run command:')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💡 {to_small_caps('Example:')} {old_cmd}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )
            )
            return

        if data.startswith("tkonsol_"):
            bd_name = data[8:]
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🟢 {to_small_caps('Starting live console for')} {bd_name}...\n📺 {to_small_caps('Continuous streaming until Konsol Of is pressed')}")
            await show_termux_console(user_id, chat_id, bd_name, context)
            return

        if data.startswith("tdel_"):
            bd_name = data[5:]
            stop_termux_project(bd_name)
            if bd_name in termux_projects:
                del termux_projects[bd_name]
                save_data()
            log_file = os.path.join(LOGS_DIR, f"termux_{bd_name}.log")
            if os.path.exists(log_file):
                try:
                    os.remove(log_file)
                except:
                    pass
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🗑️ {bd_name} {to_small_caps('deleted!')}\n🔄 {to_small_caps('Renumbering remaining projects...')}")
            renumber_termux_projects()
            new_names = list(termux_projects.keys())
            if new_names:
                names_str = "\n".join([f"• {n}" for n in new_names])
                try:
                    await context.bot.send_message(chat_id=chat_id, text=f"✅ {to_small_caps('Projects renumbered:')}\n{names_str}")
                except:
                    pass
            return

        if data == "cancel_tkonsol":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Console selection cancelled')}")
            return

        if data == "cancel_tdel":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Delete cancelled')}")
            return

        # ᴜɴʟᴏᴄᴋ ᴜsᴇʀ
        if data.startswith("unlock_"):
            target_id = int(data.split("_")[1])
            if target_id in locked_users:
                del locked_users[target_id]
                save_data()
                try:
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=(
                            f"🔓 {to_small_caps('Good News!')}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"✅ {to_small_caps('Your account has been UNLOCKED')}\n"
                            f"🤖 {to_small_caps('You can now use the bot again')}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━"
                        )
                    )
                except Exception as e:
                    logger.warning(f"ᴄᴏᴜʟᴅ ɴᴏᴛ ɴᴏᴛɪғʏ ᴜɴʟᴏᴄᴋᴇᴅ ᴜsᴇʀ: {e}")
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"✅ {to_small_caps('User')} {target_id} {to_small_caps('has been UNLOCKED successfully!')}")
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"⚠️ {to_small_caps('User')} {target_id} {to_small_caps('was not locked!')}")
            return

        if data.startswith("removeadmin_"):
            admin_id = int(data.split("_")[1])
            if admin_id in SUB_ADMINS:
                SUB_ADMINS.remove(admin_id)
                global ADMIN_IDS
                ADMIN_IDS = [PRIMARY_ADMIN_ID] + SUB_ADMINS
                save_data()
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"⚠️ {to_small_caps('Notice')}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"❌ {to_small_caps('Your admin privileges have been revoked')}\n"
                            f"🤖 {to_small_caps('Bot: Apon Premium Hosting v1')}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━"
                        )
                    )
                except:
                    pass
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"➖ {to_small_caps('Admin removed:')} {admin_id}")
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('User is not an admin!')}")
            return

        if data == "cancel_removeadmin":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Remove admin cancelled')}")
            return
        if data == "cancel_delete":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Operation cancelled')}")
            return
        if data == "cancel_livelogs":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Live logs selection cancelled')}")
            return
        if data == "cancel_unlock":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Unlock cancelled')}")
            return
        if data == "cancel_unblock":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Unblock cancelled')}")
            return
        if data == "cancel_delchannel":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Channel removal cancelled')}")
            return

        if data == "verify_join":
            not_joined = []
            for channel in force_join_channels:
                try:
                    member = await context.bot.get_chat_member(channel["channel_id"], user_id)
                    if member.status in ['left', 'kicked']:
                        not_joined.append(channel)
                except:
                    not_joined.append(channel)
            if not_joined:
                await query.answer("❌ Please join all channels first!", show_alert=True)
                return
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"✅ {to_small_caps('Verification successful! You can now use the bot.')}")
            class FakeUpdate:
                def __init__(self, message, user):
                    self.message = message
                    self.effective_user = user
            fake_msg = type('obj', (object,), {'reply_text': update.message.reply_text if update.message else lambda **kwargs: None})()
            fake_update = FakeUpdate(fake_msg, query.from_user)
            await start(fake_update, context)
            return

        if data.startswith("unblock_"):
            target_id = int(data.split("_")[1])
            if target_id in blocked_users:
                del blocked_users[target_id]
                save_data()
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"✅ {to_small_caps('User')} {target_id} {to_small_caps('unblocked!')}")
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('User not found!')}")
            return

        if data.startswith("delchannel_"):
            idx = int(data.split("_")[1])
            if 0 <= idx < len(force_join_channels):
                ch_name = force_join_channels[idx]["name"]
                del force_join_channels[idx]
                save_data()
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🗑️ {to_small_caps('Channel removed:')} {ch_name}")
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Invalid channel!')}")
            return

        if not data.startswith(("run_", "stop_", "del_", "manage_", "logs_", "restart_", "livelogs_")):
            logger.warning(f"ᴜɴᴋɴᴏᴡɴ ᴄᴀʟʟʙᴀᴄᴋ ᴅᴀᴛᴀ: {data}")
            return

        parts = data.split('_', 1)
        if len(parts) != 2:
            logger.error(f"ɪɴᴠᴀʟɪᴅ ᴄᴀʟʟʙᴀᴄᴋ ᴅᴀᴛᴀ ғᴏʀᴍᴀᴛ: {data}")
            return

        action, p_name = parts

        if action == "livelogs":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"📺 {to_small_caps('Starting live logs for')} {p_name}...\n📡 {to_small_caps('Continuous streaming - press Live Logs Off to stop')}")
            class FakeUpdate:
                def __init__(self, callback_query):
                    self.callback_query = callback_query
            fake_update = FakeUpdate(query)
            await show_live_logs(fake_update, context, p_name)
            return

        if action == "run":
            if get_project_status(p_name) == "online":
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"⚠️ {p_name} {to_small_caps('is already running!')}")
                return
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=Loading.executing()[0])
            for frame in Loading.executing()[1:-1]:
                await asyncio.sleep(0.4)
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=frame)
                except:
                    pass
            if restart_project(p_name):
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🚀 {p_name} {to_small_caps('started successfully!')} 💚")
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Failed to start')} {p_name}\n{to_small_caps('Check logs.')}")

        elif action == "stop":
            if p_name not in running_processes:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"⚠️ {p_name} {to_small_caps('is not running')}")
                return
            for i in range(100, -1, -20):
                await asyncio.sleep(0.3)
                bar = "▰" * (i // 10) + "▱" * (10 - (i // 10))
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🛑 {to_small_caps('Stopping:')} [{bar}] {i}%")
                except:
                    pass
            try:
                proc = running_processes[p_name]
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except:
                    proc.kill()
                    try:
                        proc.wait(timeout=2)
                    except:
                        pass
                del running_processes[p_name]
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🛑 {p_name} {to_small_caps('stopped!')} 💔")
            except Exception as e:
                logger.error(f"sᴛᴏᴘ ᴇʀʀᴏʀ: {e}")
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Error stopping:')} {str(e)}")

        elif action == "del":
            for frame in Loading.deleting():
                await asyncio.sleep(0.5)
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=frame)
                except:
                    pass
            success, message = delete_project(p_name)
            if success:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🗑️ {p_name} {to_small_caps('deleted!')}")
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Error deleting:')} {message}")

        elif action == "manage":
            status = get_project_status(p_name)
            status_text = "💚 ʀᴜɴɴɪɴɢ" if status == "online" else "💔 sᴛᴏᴘᴘᴇᴅ" if status == "offline" else "⚠️ ᴄʀᴀsʜᴇᴅ"
            keyboard = [
                [InlineKeyboardButton(f"▶️ {to_small_caps('Run')}", callback_data=f"run_{p_name}"), InlineKeyboardButton(f"🛑 {to_small_caps('Stop')}", callback_data=f"stop_{p_name}")],
                [InlineKeyboardButton(f"🔄 {to_small_caps('Restart')}", callback_data=f"restart_{p_name}"), InlineKeyboardButton(f"📋 {to_small_caps('Logs')}", callback_data=f"logs_{p_name}")],
                [InlineKeyboardButton(f"📺 {to_small_caps('Live Logs')}", callback_data=f"livelogs_{p_name}"), InlineKeyboardButton(f"🗑️ {to_small_caps('Delete')}", callback_data=f"del_{p_name}")]
            ]
            info = project_owners.get(p_name, {})
            last_run = info.get('last_run')
            last_run_str = datetime.fromtimestamp(last_run).strftime('%Y-%m-%d %H:%M') if last_run else to_small_caps('Never')
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"{to_small_caps('Project:')} {p_name}\n"
                    f"{to_small_caps('Status:')} {status_text}\n"
                    f"{to_small_caps('Entry:')} {info.get('main_file', 'main.py')}\n"
                    f"{to_small_caps('Owner:')} {to_small_caps(info.get('u_name', 'Unknown'))}\n"
                    f"{to_small_caps('Last Run:')} {last_run_str}\n"
                    f"{to_small_caps('Run Count:')} {info.get('run_count', 0)}"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif action == "restart":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"🔄 {to_small_caps('Restarting...')}")
            if restart_project(p_name):
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"✅ {p_name} {to_small_caps('restarted!')}")
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {p_name} {to_small_caps('restart failed')}")

        elif action == "logs":
            log_file = os.path.join(LOGS_DIR, f"{p_name}.log")
            if not os.path.exists(log_file):
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=to_small_caps("No log file found"))
                return
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    logs = f.read()
                if len(logs) > 3500:
                    logs = "...[truncated]...\n" + logs[-3500:]
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"📋 {to_small_caps('Logs for')} {p_name}\n```\n{logs}\n```"
                )
            except Exception as e:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('Error reading logs:')} {str(e)}")

    except Exception as e:
        logger.error(f"ᴄᴀʟʟʙᴀᴄᴋ ᴇʀʀᴏʀ: {e}")
        try:
            if 'chat_id' in locals() and 'message_id' in locals():
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('An error occurred!')}")
        except:
            pass

# ═══════════════════════════════════════════════════════════════════
# ʀᴇᴄᴏᴠᴇʀʏ sʏsᴛᴇᴍ
# ═══════════════════════════════════════════════════════════════════
class AdvancedRecovery:
    def __init__(self):
        self.running = True
        self.restart_count = 0
        self.max_restarts = 1000
        self.crash_log = []
        self.last_health_check = time.time()
        self.consecutive_failures = 0

    async def start_monitoring(self, application):
        logger.info("🛡️ ᴀᴅᴠᴀɴᴄᴇᴅ ʀᴇᴄᴏᴠᴇʀʏ sʏsᴛᴇᴍ sᴛᴀʀᴛᴇᴅ")
        while self.running:
            try:
                await self.check_bot_health(application)
                if recovery_enabled:
                    await self.recover_projects()
                await self.memory_cleanup()
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"ʀᴇᴄᴏᴠᴇʀʏ ʟᴏᴏᴘ ᴇʀʀᴏʀ: {e}")
                self.consecutive_failures += 1
                if self.consecutive_failures > 5:
                    logger.critical("ᴛᴏᴏ ᴍᴀɴʏ ғᴀɪʟᴜʀᴇs, ᴡᴀɪᴛɪɴɢ 60s...")
                    await asyncio.sleep(60)
                    self.consecutive_failures = 0
                else:
                    await asyncio.sleep(5)

    async def check_bot_health(self, application):
        try:
            me = await application.bot.get_me()
            self.last_health_check = time.time()
            self.consecutive_failures = 0
            if recovery_stats.get("last_restart") is None:
                recovery_stats["last_restart"] = time.time()
                save_data()
        except Exception as e:
            logger.error(f"ʙᴏᴛ ʜᴇᴀʟᴛʜ ᴄʜᴇᴄᴋ ғᴀɪʟᴇᴅ: {e}")
            self.consecutive_failures += 1
            if self.consecutive_failures >= 3:
                await self.emergency_restart(application)

    async def recover_projects(self):
        for p_name in list(running_processes.keys()):
            try:
                status = get_project_status(p_name)
                if status == "crashed":
                    logger.warning(f"ᴘʀᴏᴊᴇᴄᴛ {p_name} ᴄʀᴀsʜᴇᴅ, ʀᴇᴄᴏᴠᴇʀɪɴɢ...")
                    for attempt in range(3):
                        if restart_project(p_name):
                            recovery_stats["total_restarts"] += 1
                            recovery_stats["last_restart"] = time.time()
                            save_data()
                            logger.info(f"✅ {p_name} ʀᴇᴄᴏᴠᴇʀᴇᴅ (ᴀᴛᴛᴇᴍᴘᴛ {attempt + 1})")
                            break
                        else:
                            logger.error(f"❌ ʀᴇᴄᴏᴠᴇʀʏ ᴀᴛᴛᴇᴍᴘᴛ {attempt + 1} ғᴀɪʟᴇᴅ ғᴏʀ {p_name}")
                            await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"ᴇʀʀᴏʀ ʀᴇᴄᴏᴠᴇʀɪɴɢ {p_name}: {e}")

    async def memory_cleanup(self):
        try:
            if PSUTIL_AVAILABLE:
                mem = psutil.virtual_memory()
                if mem.percent > 90:
                    logger.warning("ʜɪɢʜ ᴍᴇᴍᴏʀʏ ᴅᴇᴛᴇᴄᴛᴇᴅ, ᴄʟᴇᴀɴɪɴɢ ᴜᴘ...")
                    for log_file in os.listdir(LOGS_DIR):
                        file_path = os.path.join(LOGS_DIR, log_file)
                        try:
                            if os.path.getsize(file_path) > 10 * 1024 * 1024:
                                with open(file_path, 'w') as f:
                                    f.write(f"ʟᴏɢ ᴄʟᴇᴀʀᴇᴅ ᴀᴛ {datetime.now()}\n")
                        except:
                            pass
        except Exception as e:
            logger.error(f"ᴍᴇᴍᴏʀʏ ᴄʟᴇᴀɴᴜᴘ ᴇʀʀᴏʀ: {e}")

    async def emergency_restart(self, application):
        if self.restart_count >= self.max_restarts:
            logger.critical("ᴍᴀx ʀᴇsᴛᴀʀᴛs ʀᴇᴀᴄʜᴇᴅ, ɢɪᴠɪɴɢ ᴜᴘ")
            return
        self.restart_count += 1
        logger.critical(f"🚨 ᴇᴍᴇʀɢᴇɴᴄʏ ʀᴇsᴛᴀʀᴛ #{self.restart_count}")
        try:
            await application.stop()
            await asyncio.sleep(3)
            await application.start()
            await application.updater.start_polling(drop_pending_updates=True)
            recovery_stats["total_restarts"] += 1
            recovery_stats["last_restart"] = time.time()
            save_data()
            logger.info("✅ ᴇᴍᴇʀɢᴇɴᴄʏ ʀᴇsᴛᴀʀᴛ sᴜᴄᴄᴇssғᴜʟ")
            self.consecutive_failures = 0
        except Exception as e:
            logger.critical(f"ᴇᴍᴇʀɢᴇɴᴄʏ ʀᴇsᴛᴀʀᴛ ғᴀɪʟᴇᴅ: {e}")

    def stop(self):
        self.running = False


recovery_system = AdvancedRecovery()


def signal_handler(signum, frame):
    logger.info("sʜᴜᴛᴅᴏᴡɴ sɪɢɴᴀʟ ʀᴇᴄᴇɪᴠᴇᴅ, sᴛᴏᴘᴘɪɴɢ ʀᴇᴄᴏᴠᴇʀʏ...")
    recovery_system.stop()
    save_data()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ═══════════════════════════════════════════════════════════════════
# ᴍᴀɪɴ - ᴄᴏᴍᴘᴀᴛɪʙʟᴇ ᴡɪᴛʜ ᴀʟʟ sᴇʀᴠᴇʀs (ʀᴇɴᴅᴇʀ, ʀᴇᴘʟɪᴛ, ᴛᴇʀᴍᴜx, ᴠᴘs)
# ═══════════════════════════════════════════════════════════════════
async def main_async():
    """ᴀsʏɴᴄ ᴍᴀɪɴ - ᴡᴏʀᴋs ᴏɴ ᴀʟʟ ᴘʟᴀᴛғᴏʀᴍs ɪɴᴄʟᴜᴅɪɴɢ ʀᴇɴᴅᴇʀ"""
    web_thread = Thread(target=run_web, daemon=True)
    web_thread.start()
    logger.info("ᴡᴇʙ sᴇʀᴠᴇʀ sᴛᴀʀᴛᴇᴅ")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ZIP, handle_docs))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("🚀 ʙᴏᴛ sᴛᴀʀᴛᴇᴅ ᴡɪᴛʜ ᴀᴅᴠᴀɴᴄᴇᴅ ʀᴇᴄᴏᴠᴇʀʏ sʏsᴛᴇᴍ!")
    logger.info(f"👑 ᴏᴡɴᴇʀ ɪᴅ: {PRIMARY_ADMIN_ID}")
    logger.info(f"👥 sᴜʙ-ᴀᴅᴍɪɴs: {SUB_ADMINS if SUB_ADMINS else 'None'}")

    async with application:
        await application.start()
        asyncio.create_task(recovery_system.start_monitoring(application))
        await application.updater.start_polling(drop_pending_updates=True)

        logger.info("✅ ʙᴏᴛ ɪs ɴᴏᴡ ʀᴜɴɴɪɴɢ. ᴘʀᴇss ᴄᴛʀʟ+ᴄ ᴛᴏ sᴛᴏᴘ.")

        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            pass

        recovery_system.stop()
        await application.updater.stop()
        await application.stop()


def main():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main_async())
    except (KeyboardInterrupt, SystemExit):
        logger.info("ʙᴏᴛ sᴛᴏᴘᴘᴇᴅ")
    except Exception as e:
        logger.critical(f"ᴍᴀɪɴ ᴇʀʀᴏʀ: {e}")
        raise
    finally:
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.close()
        except:
            pass


if __name__ == '__main__':
    main()
