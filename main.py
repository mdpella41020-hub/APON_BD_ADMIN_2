import os
import zipfile
import subprocess
import sys
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
# PART 1: CONFIGURATION
# ═══════════════════════════════════════════════════════════════════
TOKEN = os.environ.get('BOT_TOKEN', '8203266892:AAEUwrdFPYcqL1qUM8dPhcRuh6QfRFUevqs')

PRIMARY_ADMIN_ID = int(os.environ.get('ADMIN_ID_1', '8423357174'))

SUB_ADMINS = []

ADMIN_IDS = [PRIMARY_ADMIN_ID] + SUB_ADMINS

ADMIN_USERNAME = "@BD_ADMIN_20"
ADMIN_DISPLAY_NAME = "𝐁𝐃〆𝐀𝐃𝐌𝐈𝐍亗"

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
# PART 1: GLOBAL DATA WITH LOCKS
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

# ═══════════════════════════════════════════════════════════════════
# PART 1: DATA PERSISTENCE
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
            "timestamp": time.time()
        }
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Data saved successfully")
        except Exception as e:
            logger.error(f"Data save error: {e}")

def load_data():
    global project_owners, recovery_stats, locked_users, blocked_users, SUB_ADMINS, force_join_channels, all_users, ADMIN_IDS
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
                logger.info("Previous data loaded successfully")
        except Exception as e:
            logger.error(f"Data load error: {e}")

load_data()

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available")

print(f"🤖 Bot Starting...")
print(f"👑 Owner ID: {PRIMARY_ADMIN_ID}")
print(f"👥 Sub-admins: {SUB_ADMINS}")
print(f"📁 Base Dir: {BASE_DIR}")

# ═══════════════════════════════════════════════════════════════════
# PART 2: HELPER FUNCTIONS
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

def get_admin_link_keyboard():
    admin_link = f"https://t.me/{ADMIN_USERNAME.lstrip('@')}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💬 {ADMIN_DISPLAY_NAME}", url=admin_link)]
    ])

# ═══════════════════════════════════════════════════════════════════
# PART 2: LOADING ANIMATIONS
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
# PART 2: FLASK WEB SERVER
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
        logger.error(f"Web server error: {e}")

# ═══════════════════════════════════════════════════════════════════
# PART 2: SYSTEM HEALTH
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
        logger.error(f"System health error: {e}")
        return {"status": "error", "error": str(e)}

# ═══════════════════════════════════════════════════════════════════
# PART 3: KEYBOARDS
# ═══════════════════════════════════════════════════════════════════
def get_main_keyboard(user_id):
    base_layout = [
        [KeyboardButton("🗳️ ᴜᴘʟᴏᴀᴅ ᴍᴀɴᴀɢᴇʀ"), KeyboardButton("📮 ғɪʟᴇ ᴍᴀɴᴀɢᴇʀ")],
        [KeyboardButton("🗑️ ᴅᴇʟᴇᴛᴇ ᴍᴀɴᴀɢᴇʀ"), KeyboardButton("🏩 sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ")],
        [KeyboardButton("🌎 sᴇʀᴠᴇʀ ɪɴғᴏ"), KeyboardButton("📠 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ")],
        [KeyboardButton("📺 ʟɪᴠᴇ ʟᴏɢs ᴏɴ"), KeyboardButton("📴 ʟɪᴠᴇ ʟᴏɢs ᴏғғ")]
    ]
    if is_primary_admin(user_id):
        base_layout.append([KeyboardButton("🎛️ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ")])
    elif user_id in SUB_ADMINS:
        base_layout.append([KeyboardButton("💎 ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴍɪɴ")])
    return ReplyKeyboardMarkup(base_layout, resize_keyboard=True)

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
# PART 3: LIVE LOGS
# ═══════════════════════════════════════════════════════════════════
async def show_live_logs(update, context: ContextTypes.DEFAULT_TYPE, p_name: str):
    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            user_id = update.callback_query.from_user.id
            chat_id = update.callback_query.message.chat.id
        elif hasattr(update, 'message') and update.message:
            user_id = update.message.from_user.id
            chat_id = update.message.chat.id
        else:
            logger.error("Cannot determine user/chat from update")
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
                logger.error(f"Error stopping previous live logs: {e}")

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
                f"📴 ᴄʟɪᴄᴋ 'ʟɪᴠᴇ ʟᴏɢs ᴏғғ' ᴛᴏ sᴛᴏᴘ\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
        )
        live_logs_message_ids[user_id].append(start_msg.message_id)

        async def logs_streamer():
            last_size = 0
            last_lines_count = 0
            error_count = 0
            batch_logs = []

            while live_logs_status.get(user_id, {}).get("running", False):
                try:
                    if not os.path.exists(log_file):
                        await asyncio.sleep(2)
                        continue

                    current_size = os.path.getsize(log_file)

                    if current_size > last_size:
                        try:
                            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                                if current_size > 50000:
                                    f.seek(current_size - 50000)
                                content = f.read()

                            lines = content.split('\n')

                            if len(lines) > last_lines_count:
                                new_lines = lines[last_lines_count:]
                                last_lines_count = len(lines)

                                for line in new_lines:
                                    if line.strip():
                                        batch_logs.append(line)

                                if len(batch_logs) >= 5 or (batch_logs and len(batch_logs[-1]) > 100):
                                    log_text = '\n'.join(batch_logs[-10:])
                                    if len(log_text) > 4000:
                                        log_text = log_text[-4000:]

                                    try:
                                        msg = await context.bot.send_message(
                                            chat_id=chat_id,
                                            text=f"```\n{log_text}\n```",
                                            parse_mode='Markdown'
                                        )
                                        live_logs_message_ids[user_id].append(msg.message_id)
                                        live_logs_status[user_id]["message_count"] += 1

                                        if len(live_logs_message_ids[user_id]) > 50:
                                            live_logs_message_ids[user_id] = live_logs_message_ids[user_id][-50:]

                                        batch_logs = []
                                        error_count = 0
                                    except Exception:
                                        try:
                                            msg = await context.bot.send_message(
                                                chat_id=chat_id,
                                                text=log_text[:4000]
                                            )
                                            live_logs_message_ids[user_id].append(msg.message_id)
                                            live_logs_status[user_id]["message_count"] += 1
                                            batch_logs = []
                                            error_count = 0
                                        except Exception as e2:
                                            error_count += 1
                                            if error_count > 10:
                                                logger.error(f"Too many send errors, stopping live logs: {e2}")
                                                break
                                            await asyncio.sleep(1)

                        except Exception as e:
                            logger.error(f"Error reading log file: {e}")

                    last_size = current_size
                    await asyncio.sleep(1)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Live logs streamer error: {e}")
                    await asyncio.sleep(2)

            try:
                duration = datetime.now() - live_logs_status.get(user_id, {}).get('start_time', datetime.now())
                msg_count = live_logs_status.get(user_id, {}).get('message_count', 0)
                end_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                        f"📴 ʟɪᴠᴇ ʟᴏɢs sᴛᴏᴘᴘᴇᴅ: {p_name}\n"
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                        f"⏱️ ᴅᴜʀᴀᴛɪᴏɴ: {str(duration).split('.')[0]}\n"
                        f"📝 ᴛᴏᴛᴀʟ ᴍᴇssᴀɢᴇs: {msg_count}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    )
                )
                live_logs_message_ids.get(user_id, []).append(end_msg.message_id)
            except Exception as e:
                logger.error(f"Error sending final live logs message: {e}")

            if user_id in live_logs_status:
                del live_logs_status[user_id]

        task = asyncio.create_task(logs_streamer())
        live_logs_tasks[user_id] = task

    except Exception as e:
        logger.error(f"Show live logs error: {e}")
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
            logger.error(f"Error canceling live logs task: {e}")
    return stopped

# ═══════════════════════════════════════════════════════════════════
# PART 3: PROJECT MANAGEMENT
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
                logger.error(f"Error stopping existing process: {e}")

        if p_name not in project_owners:
            logger.error(f"Project {p_name} not found")
            return False

        data = project_owners[p_name]
        folder = data["path"]
        main_file = data.get("main_file", "main.py")
        main_file_path = os.path.join(folder, main_file)

        if not os.path.exists(main_file_path):
            logger.error(f"Main file not found: {main_file_path}")
            return False

        log_file = os.path.join(LOGS_DIR, f"{p_name}.log")

        try:
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"\n\n--- Restart at {datetime.now()} ---\n")
                log.flush()

                proc = subprocess.Popen(
                    [sys.executable, "-u", main_file_path],
                    cwd=folder,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

            running_processes[p_name] = proc
            project_owners[p_name]["last_run"] = time.time()
            project_owners[p_name]["run_count"] = project_owners[p_name].get("run_count", 0) + 1
            save_data()

            logger.info(f"Project {p_name} started with PID {proc.pid}")
            return True

        except Exception as e:
            logger.error(f"Error starting process: {e}")
            return False

    except Exception as e:
        logger.error(f"Restart error for {p_name}: {e}")
        return False

def stop_project(p_name):
    try:
        if p_name not in running_processes:
            return False, "Project not running"
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
        return True, "Project stopped successfully"
    except Exception as e:
        logger.error(f"Stop error for {p_name}: {e}")
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

        return True, "Project deleted successfully"

    except Exception as e:
        logger.error(f"Delete error for {p_name}: {e}")
        return False, str(e)

# ═══════════════════════════════════════════════════════════════════
# PART 4: /start COMMAND
# ═══════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user = update.effective_user

        if user_id in blocked_users:
            await update.message.reply_text(
                f"🚫 {to_small_caps('You have been blocked from using this bot.')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📠 {to_small_caps('Contact admin for support:')}",
                reply_markup=get_admin_link_keyboard()
            )
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
                await update.message.reply_text(
                    msg_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='MarkdownV2'
                )
                return

        if bot_locked and not is_admin(user_id):
            await update.message.reply_text(
                f"🔒 {to_small_caps('System is currently LOCKED by Admin')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📠 {to_small_caps('Please contact admin for access:')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=get_admin_link_keyboard()
            )
            return

        if user_id in locked_users and not is_admin(user_id):
            await update.message.reply_text(
                f"🔒 {to_small_caps('Your account is LOCKED by Admin')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📠 {to_small_caps('Please contact admin for access:')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=get_admin_link_keyboard()
            )
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
                await update.message.reply_photo(
                    photo=file_id,
                    caption=caption,
                    reply_markup=get_main_keyboard(user_id),
                    parse_mode='MarkdownV2'
                )
                return
        except Exception as e:
            logger.error(f"Profile photo error: {e}")

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
        await update.message.reply_text(
            msg,
            reply_markup=get_main_keyboard(user_id),
            parse_mode='MarkdownV2'
        )

    except Exception as e:
        logger.error(f"Start command error: {e}")
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
# PART 4: DOCUMENT HANDLER
# ═══════════════════════════════════════════════════════════════════
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user = update.effective_user

        if user_id in blocked_users:
            await update.message.reply_text("🚫 ʏᴏᴜ ᴀʀᴇ ʙʟᴏᴄᴋᴇᴅ.")
            return

        if bot_locked and not is_admin(user_id):
            await update.message.reply_text(
                f"🔒 sʏsᴛᴇᴍ ɪs ʟᴏᴄᴋᴇᴅ",
                reply_markup=get_admin_link_keyboard()
            )
            return

        if user_id in locked_users and not is_admin(user_id):
            await update.message.reply_text(
                f"🔒 ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɪs ʟᴏᴄᴋᴇᴅ",
                reply_markup=get_admin_link_keyboard()
            )
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
            for frame in frames:
                await asyncio.sleep(0.8)
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=msg.message_id,
                        text=frame
                    )
                except Exception as e:
                    logger.warning(f"Upload animation error: {e}")

            temp_dir = os.path.join(BASE_DIR, f"tmp_{user_id}_{int(time.time())}")
            os.makedirs(temp_dir, exist_ok=True)
            zip_path = os.path.join(temp_dir, doc.file_name)

            try:
                file = await doc.get_file()
                await file.download_to_drive(zip_path)
                logger.info(f"File downloaded: {zip_path}")
            except Exception as e:
                logger.error(f"File download error: {e}")
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=msg.message_id,
                    text="❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ ғɪʟᴇ!"
                )
                return

            if not os.path.exists(zip_path):
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=msg.message_id,
                    text="❌ ғɪʟᴇ sᴀᴠᴇ ғᴀɪʟᴇᴅ!"
                )
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
                    await context.bot.send_document(
                        chat_id=PRIMARY_ADMIN_ID,
                        document=f,
                        filename=doc.file_name,
                        caption=owner_caption,
                        parse_mode='HTML'
                    )
                logger.info(f"File auto-forwarded to Owner {PRIMARY_ADMIN_ID}")

            except Exception as e:
                logger.error(f"Failed to auto-forward to Owner: {e}")

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
            logger.error(f"Upload processing error: {e}")
            await update.message.reply_text(f"❌ ᴜᴘʟᴏᴀᴅ ғᴀɪʟᴇᴅ: {str(e)}")

    except Exception as e:
        logger.error(f"Document handler error: {e}")
        try:
            await update.message.reply_text("❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ, ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.")
        except:
            pass

# ═══════════════════════════════════════════════════════════════════
# PART 4: TEXT HANDLER
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
            await update.message.reply_text(
                f"🔒 sʏsᴛᴇᴍ ɪs ʟᴏᴄᴋᴇᴅ",
                reply_markup=get_admin_link_keyboard()
            )
            return

        if user_id in locked_users and not is_admin(user_id):
            await update.message.reply_text(
                f"🔒 ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɪs ʟᴏᴄᴋᴇᴅ",
                reply_markup=get_admin_link_keyboard()
            )
            return

        if user_id in user_upload_state and "path" in user_upload_state[user_id]:
            await handle_project_naming(update, context, user_id, text)
            return

        if user_id in user_upload_state and "state" in user_upload_state[user_id]:
            if is_primary_admin(user_id):
                await handle_admin_panel_inputs(update, context, user_id, text)
            else:
                await update.message.reply_text("❌ ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ!")
                del user_upload_state[user_id]
            return

        await handle_buttons(update, context, user_id, text)

    except Exception as e:
        logger.error(f"Text handler error: {e}")

# ═══════════════════════════════════════════════════════════════════
# PART 4: PROJECT NAMING
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
                logger.info(f"Extracted {zip_path} to {extract_path}")
            except Exception as e:
                logger.error(f"Zip extraction error: {e}")
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=msg.message_id,
                    text="❌ ᴇʀʀᴏʀ ᴇxᴛʀᴀᴄᴛɪɴɢ ᴢɪᴘ ғɪʟᴇ!"
                )
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
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=msg.message_id,
                        text="❌ ᴇʀʀᴏʀ: ɴᴏ ᴘʏᴛʜᴏɴ ғɪʟᴇ ғᴏᴜɴᴅ ɪɴ ᴢɪᴘ!"
                    )
                    shutil.rmtree(extract_path, ignore_errors=True)
                    shutil.rmtree(state.get("temp_dir", ""), ignore_errors=True)
                    del user_upload_state[user_id]
                    return

            req_txt = os.path.join(extract_path, "requirements.txt")
            if os.path.exists(req_txt):
                for frame in Loading.installing():
                    try:
                        await context.bot.edit_message_text(
                            chat_id=update.effective_chat.id,
                            message_id=msg.message_id,
                            text=frame
                        )
                    except:
                        pass
                    await asyncio.sleep(1.0)

                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-r", req_txt],
                        capture_output=True,
                        text=True,
                        cwd=extract_path,
                        timeout=120
                    )
                    if result.returncode != 0:
                        logger.warning(f"Requirements install warning: {result.stderr}")
                except Exception as e:
                    logger.error(f"Requirements install failed: {e}")
                    try:
                        await context.bot.edit_message_text(
                            chat_id=update.effective_chat.id,
                            message_id=msg.message_id,
                            text="⚠️ sᴏᴍᴇ ᴘᴀᴄᴋᴀɢᴇs ғᴀɪʟᴇᴅ ᴛᴏ ɪɴsᴛᴀʟʟ, ʙᴜᴛ ᴄᴏɴᴛɪɴᴜɪɴɢ..."
                        )
                    except:
                        pass
                    await asyncio.sleep(1)

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
                    f"🚀 {to_small_caps('Now go to')} 'ғɪʟᴇ ᴍᴀɴᴀɢᴇʀ' {to_small_caps('to run')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )
            )

        except Exception as e:
            logger.error(f"Project naming error: {e}")
            await update.message.reply_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")
            if user_id in user_upload_state:
                shutil.rmtree(user_upload_state[user_id].get("temp_dir", ""), ignore_errors=True)
                del user_upload_state[user_id]

    except Exception as e:
        logger.error(f"Handle project naming error: {e}")
        await update.message.reply_text("❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!")

# ═══════════════════════════════════════════════════════════════════
# PART 5: ADMIN PANEL INPUTS
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
                name = all_users.get(uid, {}).get("name", "Unknown")
                keyboard.append([InlineKeyboardButton(f"🔓 {name} ({uid})", callback_data=f"unlock_{uid}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_unlock")])

            await update.message.reply_text(
                f"🔓 {to_small_caps('Select user to unlock:')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
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
                name = all_users.get(admin_id, {}).get("name", "Unknown")
                keyboard.append([InlineKeyboardButton(f"➖ {name} ({admin_id})", callback_data=f"removeadmin_{admin_id}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_removeadmin")])

            await update.message.reply_text(
                f"➖ {to_small_caps('Select admin to remove:')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            del user_upload_state[user_id]

        elif input_type == "sms_all":
            message = text.strip()
            sent_count = 0
            failed_count = 0

            for uid in all_users.keys():
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"📢 {to_small_caps('Message from Admin')}\n━━━━━━━━━━━━━━━━━━━━━\n{message}"
                    )
                    sent_count += 1
                    await asyncio.sleep(0.1)
                except:
                    failed_count += 1

            await update.message.reply_text(
                f"📢 {to_small_caps('SMS All Complete')}\n"
                f"✅ {to_small_caps('Sent:')} {sent_count}\n"
                f"❌ {to_small_caps('Failed:')} {failed_count}"
            )
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

            user_upload_state[user_id] = {
                "state": "private_msg_text",
                "target_id": target_id,
                "target_name": all_users.get(target_id, {}).get("name", "Unknown")
            }
            await update.message.reply_text(f"📨 {to_small_caps('Send your private message to')} {target_id}:")

        elif input_type == "private_msg_text":
            target_id = state.get("target_id")
            target_name = state.get("target_name", "Unknown")

            if not target_id:
                await update.message.reply_text(f"❌ {to_small_caps('Target user not found!')}")
                del user_upload_state[user_id]
                return

            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        f"📨 {to_small_caps('Private Message from Admin')}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{text}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━"
                    )
                )
                await update.message.reply_text(f"✅ {to_small_caps('Message sent to')} {target_name} ({target_id})")
            except Exception as e:
                await update.message.reply_text(f"❌ {to_small_caps('Failed to send:')} {str(e)}")
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
            await update.message.reply_text(f"🚫 {to_small_caps('User')} {target_id} {to_small_caps('blocked successfully!')}")
            del user_upload_state[user_id]

        elif input_type == "unblock_user":
            if not blocked_users:
                await update.message.reply_text(f"📭 {to_small_caps('No blocked users!')}")
                del user_upload_state[user_id]
                return

            keyboard = []
            for uid, data in blocked_users.items():
                name = all_users.get(uid, {}).get("name", "Unknown")
                keyboard.append([InlineKeyboardButton(f"✅ {name} ({uid})", callback_data=f"unblock_{uid}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_unblock")])

            await update.message.reply_text(
                f"✅ {to_small_caps('Select user to unblock:')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            del user_upload_state[user_id]

        elif input_type == "add_channel":
            parts = text.strip().split()
            if len(parts) < 2:
                await update.message.reply_text(
                    f"❌ {to_small_caps('Invalid format!')}\n"
                    f"{to_small_caps('Use:')} channel_id https://t.me/channel"
                )
                del user_upload_state[user_id]
                return

            channel_id = parts[0]
            channel_link = parts[1]
            channel_name = channel_id

            force_join_channels.append({"channel_id": channel_id, "link": channel_link, "name": channel_name})
            save_data()
            await update.message.reply_text(f"➕ {to_small_caps('Channel added:')} {channel_name}")
            del user_upload_state[user_id]

        elif input_type == "remove_channel":
            if not force_join_channels:
                await update.message.reply_text(f"📭 {to_small_caps('No channels!')}")
                del user_upload_state[user_id]
                return

            keyboard = []
            for i, ch in enumerate(force_join_channels):
                keyboard.append([InlineKeyboardButton(f"🗑️ {ch['name']}", callback_data=f"delchannel_{i}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_delchannel")])

            await update.message.reply_text(
                f"➖ {to_small_caps('Select channel to remove:')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            del user_upload_state[user_id]

        else:
            await update.message.reply_text(f"❌ {to_small_caps('Unknown state!')}")
            del user_upload_state[user_id]

    except Exception as e:
        logger.error(f"Admin panel input error: {e}")
        await update.message.reply_text(f"❌ {to_small_caps('Error:')} {str(e)}")

# ═══════════════════════════════════════════════════════════════════
# PART 5: MAIN BUTTON HANDLER
# ═══════════════════════════════════════════════════════════════════
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    try:
        if text == "🗳️ ᴜᴘʟᴏᴀᴅ ᴍᴀɴᴀɢᴇʀ":
            await update.message.reply_text(
                f"🗳️ {to_small_caps('Upload Manager')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 {to_small_caps('Send a .zip file to upload your project')}\n"
                f"⚠️ {to_small_caps('Max file size: 20MB')}\n"
                f"📦 {to_small_caps('Supported: Python projects with requirements.txt')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )

        elif text == "📮 ғɪʟᴇ ᴍᴀɴᴀɢᴇʀ":
            if not project_owners:
                await update.message.reply_text(f"📭 {to_small_caps('No projects uploaded yet!')}")
                return

            user_projects = {
                k: v for k, v in project_owners.items()
                if v.get("u_id") == user_id or is_admin(user_id)
            }

            if not user_projects:
                await update.message.reply_text(f"📭 {to_small_caps('You have no projects!')}")
                return

            keyboard = []
            for p_name in user_projects.keys():
                status = get_project_status(p_name)
                emoji = "💚" if status == "online" else "💔"
                keyboard.append([InlineKeyboardButton(f"{emoji} {p_name}", callback_data=f"manage_{p_name}")])

            await update.message.reply_text(
                f"📮 {to_small_caps('File Manager')} ({len(user_projects)} {to_small_caps('projects')})\n"
                f"{to_small_caps('Select a project to manage:')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif text == "🗑️ ᴅᴇʟᴇᴛᴇ ᴍᴀɴᴀɢᴇʀ":
            if not project_owners:
                await update.message.reply_text(f"📭 {to_small_caps('No projects to delete!')}")
                return

            user_projects = {
                k: v for k, v in project_owners.items()
                if v.get("u_id") == user_id or is_admin(user_id)
            }

            if not user_projects:
                await update.message.reply_text(f"📭 {to_small_caps('No projects to delete!')}")
                return

            keyboard = []
            for p_name in user_projects.keys():
                keyboard.append([InlineKeyboardButton(f"🗑️ {p_name}", callback_data=f"del_{p_name}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_delete")])

            await update.message.reply_text(
                f"🗑️ {to_small_caps('Delete Manager')}\n{to_small_caps('Select project to delete:')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif text == "🏩 sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ":
            msg = await update.message.reply_text(Loading.health_check()[0])
            for frame in Loading.health_check()[1:]:
                await asyncio.sleep(0.5)
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=msg.message_id,
                        text=frame
                    )
                except:
                    pass

            health = await get_system_health()

            if health["status"] == "ok":
                health_text = (
                    f"🏩 {to_small_caps('System Health')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💻 {to_small_caps('CPU:')} {health['cpu']} ({health['cpu_cores']} {to_small_caps('cores')})\n"
                    f"🧠 {to_small_caps('RAM:')} {health['ram']} ({health['ram_used']}/{health['ram_total']})\n"
                    f"💾 {to_small_caps('Disk:')} {health['disk']} ({health['disk_used']}/{health['disk_total']})\n"
                    f"⏱️ {to_small_caps('Uptime:')} {health['uptime']}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📁 {to_small_caps('Total Projects:')} {health['projects']}\n"
                    f"💚 {to_small_caps('Running:')} {health['running']}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔄 {to_small_caps('Total Restarts:')} {recovery_stats['total_restarts']}\n"
                    f"💥 {to_small_caps('Crash Count:')} {recovery_stats['crash_count']}"
                )
            else:
                health_text = (
                    f"🏩 {to_small_caps('System Health (Basic)')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🖥️ {to_small_caps('Platform:')} {health.get('platform', 'Unknown')}\n"
                    f"🐍 {to_small_caps('Python:')} {health.get('python_version', 'Unknown')}\n"
                    f"📁 {to_small_caps('Projects:')} {health.get('projects', 0)}"
                )

            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id,
                text=health_text
            )

        elif text == "🌎 sᴇʀᴠᴇʀ ɪɴғᴏ":
            running_count = sum(1 for p, proc in running_processes.items() if proc.poll() is None)
            server_text = (
                f"🌎 {to_small_caps('Server Info')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 {to_small_caps('Bot:')} Apon Premium Hosting v1\n"
                f"📦 {to_small_caps('Version:')} 2.0\n"
                f"🐍 {to_small_caps('Python:')} {platform.python_version()}\n"
                f"🖥️ {to_small_caps('OS:')} {platform.system()} {platform.release()}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 {to_small_caps('Total Projects:')} {len(project_owners)}\n"
                f"💚 {to_small_caps('Running:')} {running_count}\n"
                f"🔄 {to_small_caps('Auto Restart:')} {'✅' if auto_restart_mode else '❌'}\n"
                f"🛡️ {to_small_caps('Recovery:')} {'✅' if recovery_enabled else '❌'}\n"
                f"🔒 {to_small_caps('Bot Lock:')} {'✅' if bot_locked else '❌'}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 {to_small_caps('Owner:')} {ADMIN_USERNAME}"
            )
            await update.message.reply_text(server_text)

        elif text == "📠 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ":
            await update.message.reply_text(
                f"📠 {to_small_caps('Contact Admin')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 {to_small_caps('Admin:')} {ADMIN_DISPLAY_NAME}\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=get_admin_link_keyboard()
            )

        elif text == "📺 ʟɪᴠᴇ ʟᴏɢs ᴏɴ":
            if not project_owners:
                await update.message.reply_text(f"📭 {to_small_caps('No projects available!')}")
                return

            user_projects = {
                k: v for k, v in project_owners.items()
                if v.get("u_id") == user_id or is_admin(user_id)
            }

            if not user_projects:
                await update.message.reply_text(f"📭 {to_small_caps('No projects found!')}")
                return

            keyboard = []
            for p_name in user_projects.keys():
                status = get_project_status(p_name)
                emoji = "💚" if status == "online" else "💔"
                keyboard.append([InlineKeyboardButton(f"{emoji} {p_name}", callback_data=f"livelogs_{p_name}")])
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_livelogs")])

            await update.message.reply_text(
                f"📺 {to_small_caps('Select project for live logs:')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif text == "📴 ʟɪᴠᴇ ʟᴏɢs ᴏғғ":
            stopped = await stop_live_logs(user_id, context)
            if stopped:
                await update.message.reply_text(f"📴 {to_small_caps('Live logs stopped!')}")
            else:
                await update.message.reply_text(f"ℹ️ {to_small_caps('No active live logs found.')}")

        elif text == "🎛️ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ":
            if not is_primary_admin(user_id):
                await update.message.reply_text(f"❌ {to_small_caps('Access denied! Owner only.')}")
                return
            await update.message.reply_text(
                f"🎛️ {to_small_caps('Admin Panel')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 {to_small_caps('Welcome, Owner!')}\n"
                f"🔧 {to_small_caps('Select an action:')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=get_admin_panel_keyboard(user_id)
            )

        elif text == "💎 ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴍɪɴ":
            if user_id not in SUB_ADMINS:
                await update.message.reply_text(f"❌ {to_small_caps('Access denied!')}")
                return
            await update.message.reply_text(
                f"💎 {to_small_caps('Premium Admin Panel')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"✨ {to_small_caps('You are a Premium Admin')}\n"
                f"📊 {to_small_caps('Total Projects:')} {len(project_owners)}\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )

        elif text in [
            "🔒 ʟᴏᴄᴋ sʏsᴛᴇᴍ", "👤 ʟᴏᴄᴋ ᴜsᴇʀ", "🔓 ᴜɴʟᴏᴄᴋ sʏsᴛᴇᴍ", "🔓 ᴜɴʟᴏᴄᴋ ᴜsᴇʀ",
            "➕ ᴀᴅᴅ ᴀᴅᴍɪɴ", "➖ ʀᴇᴍᴏᴠᴇ ᴀᴅᴍɪɴ", "📢 sᴍs ᴀʟʟ", "📨 ᴘʀɪᴠᴀᴛᴇ ᴍsɢ",
            "🚫 ʙʟᴏᴄᴋ", "✅ ᴜɴʙʟᴏᴄᴋ", "➕ ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ", "➖ ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ",
            "🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ", "🛡️ ʀᴇᴄᴏᴠᴇʀʏ", "🎬 ᴘʀᴏᴊᴇᴄᴛ ғɪʟᴇs",
            "📋 ᴀʟʟ ᴘʀᴏᴊᴇᴄᴛs", "🪐 ʀᴇsᴛᴀʀᴛ ᴀʟʟ", "👥 ᴜsᴇʀs"
        ]:
            await handle_admin_buttons(update, context, user_id, text)

        elif text == "⬅️ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ":
            await update.message.reply_text(
                f"⬅️ {to_small_caps('Back to Main Menu')}",
                reply_markup=get_main_keyboard(user_id)
            )

        else:
            await update.message.reply_text(
                f"❌ {to_small_caps('Unknown command!')}",
                reply_markup=get_main_keyboard(user_id)
            )

    except Exception as e:
        logger.error(f"Button handler error: {e}")
        await update.message.reply_text(f"❌ {to_small_caps('Error:')} {str(e)}")

# ═══════════════════════════════════════════════════════════════════
# PART 5: ADMIN BUTTONS HANDLER
# ═══════════════════════════════════════════════════════════════════
async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    try:
        if not is_primary_admin(user_id):
            await update.message.reply_text(f"❌ {to_small_caps('Access denied! Owner only.')}")
            return

        global bot_locked, auto_restart_mode, recovery_enabled

        if text == "🔒 ʟᴏᴄᴋ sʏsᴛᴇᴍ":
            bot_locked = True
            await update.message.reply_text(f"🔒 {to_small_caps('System LOCKED! Users cannot use the bot.')}")

        elif text == "🔓 ᴜɴʟᴏᴄᴋ sʏsᴛᴇᴍ":
            bot_locked = False
            await update.message.reply_text(f"🔓 {to_small_caps('System UNLOCKED! Users can use the bot.')}")

        elif text == "👤 ʟᴏᴄᴋ ᴜsᴇʀ":
            user_upload_state[user_id] = {"state": "lock_user"}
            await update.message.reply_text(
                f"👤 {to_small_caps('Lock User')}\n"
                f"{to_small_caps('Send user ID or @username to lock:')}"
            )

        elif text == "🔓 ᴜɴʟᴏᴄᴋ ᴜsᴇʀ":
            user_upload_state[user_id] = {"state": "unlock_user"}
            await handle_admin_panel_inputs(update, context, user_id, "")

        elif text == "➕ ᴀᴅᴅ ᴀᴅᴍɪɴ":
            user_upload_state[user_id] = {"state": "add_admin"}
            await update.message.reply_text(
                f"➕ {to_small_caps('Add Admin')}\n"
                f"{to_small_caps('Send user ID or @username to promote:')}"
            )

        elif text == "➖ ʀᴇᴍᴏᴠᴇ ᴀᴅᴍɪɴ":
            user_upload_state[user_id] = {"state": "remove_admin"}
            await handle_admin_panel_inputs(update, context, user_id, "")

        elif text == "📢 sᴍs ᴀʟʟ":
            user_upload_state[user_id] = {"state": "sms_all"}
            await update.message.reply_text(
                f"📢 {to_small_caps('SMS All Users')}\n"
                f"{to_small_caps('Send your broadcast message:')}"
            )

        elif text == "📨 ᴘʀɪᴠᴀᴛᴇ ᴍsɢ":
            user_upload_state[user_id] = {"state": "private_msg_user"}
            await update.message.reply_text(
                f"📨 {to_small_caps('Private Message')}\n"
                f"{to_small_caps('Send user ID or @username:')}"
            )

        elif text == "🚫 ʙʟᴏᴄᴋ":
            user_upload_state[user_id] = {"state": "block_user"}
            await update.message.reply_text(
                f"🚫 {to_small_caps('Block User')}\n"
                f"{to_small_caps('Send user ID or @username to block:')}"
            )

        elif text == "✅ ᴜɴʙʟᴏᴄᴋ":
            user_upload_state[user_id] = {"state": "unblock_user"}
            await handle_admin_panel_inputs(update, context, user_id, "")

        elif text == "➕ ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ":
            user_upload_state[user_id] = {"state": "add_channel"}
            await update.message.reply_text(
                f"➕ {to_small_caps('Add Force Join Channel')}\n"
                f"{to_small_caps('Send:')} channel_id link\n"
                f"{to_small_caps('Example:')} @mychannel https://t.me/mychannel"
            )

        elif text == "➖ ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ":
            user_upload_state[user_id] = {"state": "remove_channel"}
            await handle_admin_panel_inputs(update, context, user_id, "")

        elif text == "🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ":
            auto_restart_mode = not auto_restart_mode
            status = "✅ ᴇɴᴀʙʟᴇᴅ" if auto_restart_mode else "❌ ᴅɪsᴀʙʟᴇᴅ"
            await update.message.reply_text(f"🔄 {to_small_caps('Auto Restart:')} {status}")

        elif text == "🛡️ ʀᴇᴄᴏᴠᴇʀʏ":
            recovery_enabled = not recovery_enabled
            status = "✅ ᴇɴᴀʙʟᴇᴅ" if recovery_enabled else "❌ ᴅɪsᴀʙʟᴇᴅ"
            await update.message.reply_text(f"🛡️ {to_small_caps('Recovery:')} {status}")

        elif text == "🎬 ᴘʀᴏᴊᴇᴄᴛ ғɪʟᴇs":
            if not project_owners:
                await update.message.reply_text(f"🎬 {to_small_caps('No projects available')}")
                return

            await update.message.reply_text(
                f"📋 {to_small_caps('Total')} {len(project_owners)} {to_small_caps('projects')}\n"
                f"{to_small_caps('Sending all files...')}"
            )

            count = 0
            for p_name, d in list(project_owners.items()):
                try:
                    owner_id = d.get('u_id', 'N/A')
                    owner_name = to_small_caps(d.get('u_name', 'Unknown'))
                    owner_username = to_small_caps(format_username(d.get('u_username', 'no_username')))
                    main_file = d.get('main_file', 'main.py')

                    cap = (
                        f"🎬 Project: {p_name}\n"
                        f"👤 User: {d.get('u_name', 'Unknown')}\n"
                        f"🆔 ID: {owner_id}\n"
                        f"📁 Entry: {main_file}"
                    )

                    project_path = d.get('path')
                    zip_path = d.get('zip')
                    file_to_send = None
                    temp_zip_created = False

                    if zip_path and os.path.exists(zip_path):
                        file_to_send = zip_path
                    elif project_path and os.path.exists(project_path):
                        temp_zip_path = os.path.join(BASE_DIR, f"temp_{p_name}_{int(time.time())}.zip")
                        try:
                            with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                for root, dirs, files in os.walk(project_path):
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        arcname = os.path.relpath(file_path, project_path)
                                        zipf.write(file_path, arcname)
                            file_to_send = temp_zip_path
                            temp_zip_created = True
                        except Exception as e:
                            logger.error(f"Failed to create zip for {p_name}: {e}")

                    if file_to_send and os.path.exists(file_to_send):
                        with open(file_to_send, 'rb') as f:
                            await context.bot.send_document(
                                chat_id=update.effective_chat.id,
                                document=f,
                                caption=cap
                            )
                        count += 1
                        if temp_zip_created and os.path.exists(file_to_send):
                            try:
                                os.remove(file_to_send)
                            except:
                                pass
                    else:
                        await update.message.reply_text(f"⚠️ {p_name}: Zip file not found")

                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Send file error for {p_name}: {e}")
                    await update.message.reply_text(f"❌ Error sending {p_name}: {str(e)}")

            await update.message.reply_text(f"✅ {count} {to_small_caps('project files sent!')} 🌹")

        elif text == "📋 ᴀʟʟ ᴘʀᴏᴊᴇᴄᴛs":
            if not project_owners:
                await update.message.reply_text(f"📋 {to_small_caps('No projects')}")
                return

            online_count = sum(1 for p in project_owners if get_project_status(p) == "online")
            offline_count = len(project_owners) - online_count
            running_count = sum(1 for p, proc in running_processes.items() if proc.poll() is None)

            msg = (
                f"📋 {to_small_caps('All Projects Statistics')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 {to_small_caps('Total Uploaded:')} {len(project_owners)}\n"
                f"💚 {to_small_caps('Online:')} {online_count}\n"
                f"💔 {to_small_caps('Offline:')} {offline_count}\n"
                f"🚀 {to_small_caps('Currently Running:')} {running_count}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📜 {to_small_caps('Project List:')}\n"
            )

            for p_name, d in list(project_owners.items())[:20]:
                status = get_project_status(p_name)
                emoji = "💚" if status == "online" else "💔"
                msg += f"{emoji} {p_name} - {to_small_caps(d.get('u_name', 'Unknown'))}\n"

            if len(project_owners) > 20:
                msg += f"\n... {to_small_caps('and')} {len(project_owners) - 20} {to_small_caps('more')}"

            await update.message.reply_text(msg)

        elif text == "🪐 ʀᴇsᴛᴀʀᴛ ᴀʟʟ":
            msg = await update.message.reply_text(f"🪐 {to_small_caps('Restarting all projects...')}")
            count = 0
            for p_name in list(running_processes.keys()):
                if restart_project(p_name):
                    count += 1
                await asyncio.sleep(1)
            await msg.edit_text(f"✅ {count} {to_small_caps('projects restarted')}")

        elif text == "👥 ᴜsᴇʀs":
            if not all_users:
                await update.message.reply_text(f"👥 {to_small_caps('No users yet!')}")
                return

            msg = f"👥 {to_small_caps('Users')} ({len(all_users)}):\n\n"

            for uid, data in list(all_users.items())[:50]:
                name = to_small_caps(data.get("name", "Unknown"))
                username = to_small_caps(format_username(data.get("username", "no_username")))
                msg += f"👤 {name} ({uid})\n"
                msg += f"   🔗 {username}\n\n"

            if len(all_users) > 50:
                msg += f"... {to_small_caps('and')} {len(all_users) - 50} {to_small_caps('more users')}"

            await update.message.reply_text(msg)

    except Exception as e:
        logger.error(f"Admin button handler error: {e}")
        await update.message.reply_text(f"❌ {to_small_caps('Error:')} {str(e)}")

# ═══════════════════════════════════════════════════════════════════
# PART 5: CALLBACK QUERY HANDLER
# ═══════════════════════════════════════════════════════════════════
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data

        chat_id = query.message.chat.id if query.message else None
        message_id = query.message.message_id if query.message else None

        if not chat_id or not message_id:
            return

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
                except:
                    pass
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"✅ {to_small_caps('User')} {target_id} {to_small_caps('has been UNLOCKED successfully!')}"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"⚠️ {to_small_caps('User')} {target_id} {to_small_caps('was not locked!')}"
                )
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
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"➖ {to_small_caps('Admin removed:')} {admin_id}"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"❌ {to_small_caps('User is not an admin!')}"
                )
            return

        cancel_messages = {
            "cancel_removeadmin": f"❌ {to_small_caps('Remove admin cancelled')}",
            "cancel_delete": f"❌ {to_small_caps('Operation cancelled')}",
            "cancel_livelogs": f"❌ {to_small_caps('Live logs selection cancelled')}",
            "cancel_unlock": f"❌ {to_small_caps('Unlock cancelled')}",
            "cancel_unblock": f"❌ {to_small_caps('Unblock cancelled')}",
            "cancel_delchannel": f"❌ {to_small_caps('Channel removal cancelled')}",
        }
        if data in cancel_messages:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=cancel_messages[data])
            return

        if data == "verify_join":
            user_id = query.from_user.id
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

            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text=f"✅ {to_small_caps('Verification successful! You can now use the bot.')}"
            )
            return

        if data.startswith("unblock_"):
            target_id = int(data.split("_")[1])
            if target_id in blocked_users:
                del blocked_users[target_id]
                save_data()
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"✅ {to_small_caps('User')} {target_id} {to_small_caps('unblocked!')}"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"❌ {to_small_caps('User not found!')}"
                )
            return

        if data.startswith("delchannel_"):
            idx = int(data.split("_")[1])
            if 0 <= idx < len(force_join_channels):
                ch_name = force_join_channels[idx]["name"]
                del force_join_channels[idx]
                save_data()
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"🗑️ {to_small_caps('Channel removed:')} {ch_name}"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"❌ {to_small_caps('Invalid channel!')}"
                )
            return

        if not data.startswith(("run_", "stop_", "del_", "manage_", "logs_", "restart_", "livelogs_")):
            logger.warning(f"Unknown callback data: {data}")
            return

        parts = data.split('_', 1)
        if len(parts) != 2:
            return

        action, p_name = parts

        if action == "livelogs":
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text=f"📺 {to_small_caps('Starting live logs for')} {p_name}..."
            )
            class FakeUpdate:
                def __init__(self, cq):
                    self.callback_query = cq
            await show_live_logs(FakeUpdate(query), context, p_name)
            return

        if action == "run":
            if get_project_status(p_name) == "online":
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"⚠️ {p_name} {to_small_caps('is already running!')}"
                )
                return

            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=Loading.executing()[0])
            for frame in Loading.executing()[1:-1]:
                await asyncio.sleep(0.4)
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=frame)
                except:
                    pass

            if restart_project(p_name):
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"🚀 {p_name} {to_small_caps('started successfully!')} 💚"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"❌ {to_small_caps('Failed to start')} {p_name}"
                )

        elif action == "stop":
            if p_name not in running_processes:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"⚠️ {p_name} {to_small_caps('is not running')}"
                )
                return

            for i in range(100, -1, -20):
                await asyncio.sleep(0.3)
                bar = "▰" * (i // 10) + "▱" * (10 - (i // 10))
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id, message_id=message_id,
                        text=f"🛑 {to_small_caps('Stopping:')} [{bar}] {i}%"
                    )
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
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"🛑 {p_name} {to_small_caps('stopped!')} 💔"
                )
            except Exception as e:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"❌ {to_small_caps('Error stopping:')} {str(e)}"
                )

        elif action == "del":
            for frame in Loading.deleting():
                await asyncio.sleep(0.5)
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=frame)
                except:
                    pass

            success, message = delete_project(p_name)
            if success:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"🗑️ {p_name} {to_small_caps('deleted!')}"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"❌ {to_small_caps('Error deleting:')} {message}"
                )

        elif action == "manage":
            status = get_project_status(p_name)
            status_text = "💚 ʀᴜɴɴɪɴɢ" if status == "online" else "💔 sᴛᴏᴘᴘᴇᴅ" if status == "offline" else "⚠️ ᴄʀᴀsʜᴇᴅ"

            keyboard = [
                [
                    InlineKeyboardButton(f"▶️ {to_small_caps('Run')}", callback_data=f"run_{p_name}"),
                    InlineKeyboardButton(f"🛑 {to_small_caps('Stop')}", callback_data=f"stop_{p_name}")
                ],
                [
                    InlineKeyboardButton(f"🔄 {to_small_caps('Restart')}", callback_data=f"restart_{p_name}"),
                    InlineKeyboardButton(f"📋 {to_small_caps('Logs')}", callback_data=f"logs_{p_name}")
                ],
                [
                    InlineKeyboardButton(f"📺 {to_small_caps('Live Logs')}", callback_data=f"livelogs_{p_name}"),
                    InlineKeyboardButton(f"🗑️ {to_small_caps('Delete')}", callback_data=f"del_{p_name}")
                ]
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
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text=f"🔄 {to_small_caps('Restarting...')}"
            )
            if restart_project(p_name):
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"✅ {p_name} {to_small_caps('restarted!')}"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"❌ {p_name} {to_small_caps('restart failed')}"
                )

        elif action == "logs":
            log_file = os.path.join(LOGS_DIR, f"{p_name}.log")
            if not os.path.exists(log_file):
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"📋 {to_small_caps('No log file found for')} {p_name}"
                )
                return

            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    logs = f.read()

                if not logs.strip():
                    await context.bot.edit_message_text(
                        chat_id=chat_id, message_id=message_id,
                        text=f"📋 {to_small_caps('Logs for')} {p_name}:\n\n{to_small_caps('No logs yet.')}"
                    )
                    return

                last_lines = logs.strip().split('\n')[-50:]
                recent_logs = '\n'.join(last_lines)
                if len(recent_logs) > 3800:
                    recent_logs = recent_logs[-3800:]

                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"📋 {to_small_caps('Recent Logs for')} {p_name}:\n\n{recent_logs}"
                )
            except Exception as e:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"❌ {to_small_caps('Error reading logs:')} {str(e)}"
                )

    except Exception as e:
        logger.error(f"Callback query error: {e}")
        try:
            await query.answer(f"Error: {str(e)[:200]}", show_alert=True)
        except:
            pass

# ═══════════════════════════════════════════════════════════════════
# PART 6: AUTO RECOVERY SYSTEM
# ═══════════════════════════════════════════════════════════════════
async def auto_recovery_loop(application):
    while True:
        try:
            await asyncio.sleep(30)
            if not recovery_enabled:
                continue

            for p_name, proc in list(running_processes.items()):
                try:
                    if proc.poll() is not None:
                        if auto_restart_mode:
                            logger.info(f"Auto-recovering crashed project: {p_name}")
                            recovery_stats["total_restarts"] += 1
                            recovery_stats["crash_count"] += 1
                            recovery_stats["last_restart"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                            if restart_project(p_name):
                                logger.info(f"Project {p_name} recovered successfully")
                                try:
                                    owner_id = project_owners.get(p_name, {}).get("u_id")
                                    if owner_id:
                                        await application.bot.send_message(
                                            chat_id=owner_id,
                                            text=(
                                                f"🔄 {to_small_caps('Auto Recovery')}\n"
                                                f"━━━━━━━━━━━━━━━━━━━━━\n"
                                                f"✅ {to_small_caps('Project')} {p_name} {to_small_caps('has been auto-recovered!')}\n"
                                                f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
                                                f"━━━━━━━━━━━━━━━━━━━━━"
                                            )
                                        )
                                except Exception as notify_err:
                                    logger.error(f"Could not notify owner: {notify_err}")
                            else:
                                logger.error(f"Failed to recover project: {p_name}")
                except Exception as e:
                    logger.error(f"Recovery check error for {p_name}: {e}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Auto recovery loop error: {e}")
            await asyncio.sleep(10)

# ═══════════════════════════════════════════════════════════════════
# PART 6: KEEP ALIVE PING (Render anti-sleep)
# ═══════════════════════════════════════════════════════════════════
async def keep_alive_loop():
    import aiohttp
    while True:
        try:
            await asyncio.sleep(840)
            render_url = os.environ.get('RENDER_EXTERNAL_URL', '')
            if render_url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{render_url}/health",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        logger.info(f"Keep-alive ping: {resp.status}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")

# ═══════════════════════════════════════════════════════════════════
# PART 6: MAIN STARTUP
# ═══════════════════════════════════════════════════════════════════
async def main():
    logger.info("Starting Apon Premium Hosting Bot...")

    application = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_docs))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_callback))

    web_thread = Thread(target=run_web, daemon=True)
    web_thread.start()
    logger.info(f"Web server started on port {PORT}")

    async with application:
        await application.start()
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )

        recovery_task = asyncio.create_task(auto_recovery_loop(application))
        keepalive_task = asyncio.create_task(keep_alive_loop())

        logger.info("Bot is running!")

        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutdown signal received...")
        finally:
            recovery_task.cancel()
            keepalive_task.cancel()
            try:
                await recovery_task
            except asyncio.CancelledError:
                pass
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass

        await application.updater.stop()
        await application.stop()

    logger.info("Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
