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

# --- [AUTO INSTALLATION SYSTEM] ---
class AutoInstaller:
    REQUIRED_PACKAGES = [
        'flask',
        'python-telegram-bot',
        'psutil',
        'aiohttp',
        'requests',
        'watchdog'
    ]
    
    @staticmethod
    def check_and_install():
        print("🔍 ᴄʜᴇᴄᴋɪɴɢ ʀᴇǫᴜɪʀᴇᴅ ᴘᴀᴄᴋᴀɢᴇs...")
        missing = []
        
        for package in AutoInstaller.REQUIRED_PACKAGES:
            try:
                if package == 'python-telegram-bot':
                    from telegram import Update
                elif package == 'flask':
                    from flask import Flask
                elif package == 'psutil':
                    import psutil
                elif package == 'aiohttp':
                    import aiohttp
                elif package == 'requests':
                    import requests
                elif package == 'watchdog':
                    from watchdog.observers import Observer
                print(f"✅ {package} - ᴏᴋ")
            except ImportError:
                print(f"❌ {package} - ᴍɪssɪɴɢ")
                missing.append(package)
        
        if missing:
            print(f"\n📦 ɪɴsᴛᴀʟʟɪɴɢ {len(missing)} ᴍɪssɪɴɢ ᴘᴀᴄᴋᴀɢᴇs...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", "--upgrade", "pip"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                for package in missing:
                    print(f"⬇️ ɪɴsᴛᴀʟʟɪɴɢ {package}...")
                    subprocess.check_call([
                        sys.executable, "-m", "pip", "install", package
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print(f"✅ {package} ɪɴsᴛᴀʟʟᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!")
                
                print("\n🎉 ᴀʟʟ ᴘᴀᴄᴋᴀɢᴇs ɪɴsᴛᴀʟʟᴇᴅ! ʀᴇsᴛᴀʀᴛɪɴɢ...")
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as e:
                print(f"❌ ɪɴsᴛᴀʟʟᴀᴛɪᴏɴ ғᴀɪʟᴇᴅ: {e}")
                sys.exit(1)
        else:
            print("🚀 ᴀʟʟ ᴘᴀᴄᴋᴀɢᴇs ᴀʀᴇ ʀᴇᴀᴅʏ!\n")

# Run auto installer
AutoInstaller.check_and_install()

# Now import all (after package install)
from flask import Flask, jsonify, request
from telegram import ReplyKeyboardMarkup, KeyboardButton, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- [CONFIGURATION] ---
TOKEN = os.environ.get('BOT_TOKEN', '8673472964:AAF4Wne-zENnUlXTRgv0L4ql-YelVoe50GE')

ADMIN_IDS = [
    int(os.environ.get('ADMIN_ID_1', '8423357174')),
    int(os.environ.get('ADMIN_ID_2', '0')),
    int(os.environ.get('ADMIN_ID_3', '0')),
    int(os.environ.get('ADMIN_ID_4', '0')),
    int(os.environ.get('ADMIN_ID_5', '0')),
    int(os.environ.get('OWNER_ID', '0')),
]
ADMIN_IDS = [aid for aid in ADMIN_IDS if aid != 0]

PRIMARY_ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else 8423357174
ADMIN_USERNAME = "@BD_ADMIN_20"
ADMIN_DISPLAY_NAME = "💞 ʙᴅ ᴀᴅᴍɪɴ 💞"

BASE_DIR = os.path.join(os.getcwd(), "hosted_projects")
LOGS_DIR = os.path.join(os.getcwd(), "logs")
DATA_FILE = os.path.join(os.getcwd(), "bot_data.json")
PORT = int(os.environ.get('PORT', 8080))

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create directories
for dir_path in [BASE_DIR, LOGS_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# --- [GLOBAL DATA WITH LOCKS] ---
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

live_logs_tasks = {}
live_logs_status = {}
live_logs_message_ids = {}

# --- [DATA PERSISTENCE] ---
def save_data():
    with data_lock:
        data = {
            "project_owners": project_owners,
            "recovery_stats": recovery_stats,
            "timestamp": time.time()
        }
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("ᴅᴀᴛᴀ sᴀᴠᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ")
        except Exception as e:
            logger.error(f"ᴅᴀᴛᴀ sᴀᴠᴇ ᴇʀʀᴏʀ: {e}")

def load_data():
    global project_owners, recovery_stats
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                project_owners = data.get("project_owners", {})
                recovery_stats = data.get("recovery_stats", recovery_stats)
                logger.info("ᴘʀᴇᴠɪᴏᴜs ᴅᴀᴛᴀ ʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ")
        except Exception as e:
            logger.error(f"ᴅᴀᴛᴀ ʟᴏᴀᴅ ᴇʀʀᴏʀ: {e}")

load_data()

# --- [PSUTIL CHECK] ---
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("ᴘsᴜᴛɪʟ ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ")

# --- [HELPER FUNCTIONS] ---
def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_project_status(p_name):
    if p_name not in running_processes:
        return "offline"
    proc = running_processes[p_name]
    if proc.poll() is None:
        return "online"
    return "crashed"

def to_small_caps(text):
    """Convert text to small caps (ᴛʜɪs ғᴏɴᴛ) - preserves special chars"""
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
    """Escape markdown special characters"""
    if not text:
        return ""
    escape_chars = r'_*[]()~>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, '\\' + char)
    return text

def format_username(username):
    """Format username properly preserving hyphens and underscores"""
    if not username:
        return "ɴᴏ ᴜsᴇʀɴᴀᴍᴇ"
    
    username = username.strip()
    if username.startswith('@'):
        username = username[1:]
    
    return f"@{username}"

def safe_caption(text):
    """Make text safe for caption by escaping markdown and converting to small caps"""
    if not text:
        return ""
    small = to_small_caps(text)
    return small

# --- [LOADING ANIMATIONS] ---
class Loading:
    @staticmethod
    def executing():
        return [
            "🌺 ᴇxᴇᴄᴜᴛɪɴɢ: [▱▱▱▱▱▱▱▱▱▱] 0%",
            "🌼 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▱▱▱▱▱▱▱▱▱] 10%",
            "🌻 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▱▱▱▱▱▱▱▱] 20%",
            "🌸 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▱▱▱▱▱▱▱] 30%",
            "🌹 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▱▱▱▱▱▱] 40%",
            "🍁 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▰▱▱▱▱▱] 50%",
            "🌿 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▰▰▱▱▱▱] 60%",
            "🌳 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▰▰▰▱▱▱] 70%",
            "🌲 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▰▰▰▰▱▱] 80%",
            "🪷 ᴇxᴇᴄᴜᴛɪɴɢ: [▰▰▰▰▰▰▰▰▰▱] 90%",
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

# --- [FLASK WEB SERVER] ---
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

# --- [KEYBOARD SETUP] ---
def get_main_keyboard(user_id):
    lock_status = "🔓 ᴜɴʟᴏᴄᴋ sʏsᴛᴇᴍ" if bot_locked else "🔒 ʟᴏᴄᴋ sʏsᴛᴇᴍ"
    restart_status = "🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ: ᴏɴ" if auto_restart_mode else "🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ: ᴏғғ"
    recovery_status = "🛡️ ʀᴇᴄᴏᴠᴇʀʏ: ᴏɴ" if recovery_enabled else "🛡️ ʀᴇᴄᴏᴠᴇʀʏ: ᴏғғ"

    if is_admin(user_id):
        layout = [
            [KeyboardButton("🗳️ ᴜᴘʟᴏᴀᴅ ᴍᴀɴᴀɢᴇʀ"), KeyboardButton("📮 ғɪʟᴇ ᴍᴀɴᴀɢᴇʀ")],
            [KeyboardButton("🗑️ ᴅᴇʟᴇᴛᴇ ᴍᴀɴᴀɢᴇʀ"), KeyboardButton("🏩 sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ")],
            [KeyboardButton("🌎 sᴇʀᴠᴇʀ ɪɴғᴏ"), KeyboardButton("📠 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ")],
            [KeyboardButton("📺 ʟɪᴠᴇ ʟᴏɢs ᴏɴ"), KeyboardButton("📴 ʟɪᴠᴇ ʟᴏɢs ᴏғғ")],
            [KeyboardButton(lock_status), KeyboardButton(restart_status)],
            [KeyboardButton(recovery_status), KeyboardButton("🎬 ᴘʀᴏᴊᴇᴄᴛ ғɪʟᴇs")],
            [KeyboardButton("📋 ᴀʟʟ ᴘʀᴏᴊᴇᴄᴛs"), KeyboardButton("🪐 ʀᴇsᴛᴀʀᴛ ᴀʟʟ")]
        ]
    else:
        layout = [
            [KeyboardButton("🗳️ ᴜᴘʟᴏᴀᴅ ᴍᴀɴᴀɢᴇʀ"), KeyboardButton("📮 ғɪʟᴇ ᴍᴀɴᴀɢᴇʀ")],
            [KeyboardButton("🗑️ ᴅᴇʟᴇᴛᴇ ᴍᴀɴᴀɢᴇʀ"), KeyboardButton("🏩 sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ")],
            [KeyboardButton("🌎 sᴇʀᴠᴇʀ ɪɴғᴏ"), KeyboardButton("📠 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ")],
            [KeyboardButton("📺 ʟɪᴠᴇ ʟᴏɢs ᴏɴ"), KeyboardButton("📴 ʟɪᴠᴇ ʟᴏɢs ᴏғғ")]
        ]
    return ReplyKeyboardMarkup(layout, resize_keyboard=True)

# --- [SYSTEM HEALTH FUNCTION] ---
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
# --- [FIXED LIVE LOGS FUNCTIONS - CONTINUOUS REPLY MODE] ---
async def show_live_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, p_name: str):
    """
    FIXED: Continuous reply mode - sends new messages like terminal/console output
    instead of editing the same message. Stops only when user clicks OFF.
    """
    try:
        # Get user info from callback or message
        if hasattr(update, 'callback_query') and update.callback_query:
            user_id = update.callback_query.from_user.id
            chat_id = update.callback_query.message.chat.id
        elif hasattr(update, 'message') and update.message:
            user_id = update.message.from_user.id
            chat_id = update.message.chat.id
        else:
            logger.error("ᴄᴀɴɴᴏᴛ ᴅᴇᴛᴇʀᴍɪɴᴇ ᴜsᴇʀ/ᴄʜᴀᴛ ғʀᴏᴍ ᴜᴘᴅᴀᴛᴇ")
            return
        
        # Stop any existing live logs for this user first
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
                text=f"❌ ɴᴏ ʟᴏɢ ғɪʟᴇ ғᴏᴜɴᴅ ғᴏʀ {p_name}\\!\nᴘʟᴇᴀsᴇ ʀᴜɴ ᴛʜᴇ ᴘʀᴏᴊᴇᴄᴛ ғɪʀsᴛ\\.",
                parse_mode='MarkdownV2'
            )
            return
        
        # Initialize live logs status
        live_logs_status[user_id] = {
            "project": p_name, 
            "running": True,
            "chat_id": chat_id,
            "start_time": datetime.now(),
            "message_count": 0
        }
        
        # Clear old message IDs for this user
        if user_id in live_logs_message_ids:
            live_logs_message_ids[user_id] = []
        else:
            live_logs_message_ids[user_id] = []
        
        # Send START message
        start_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴\n"
                f"📺 ʟɪᴠᴇ ʟᴏɢs sᴛᴀʀᴛᴇᴅ: {escape_markdown(p_name)}\n"
                f"🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴🟢🔴\n"
                f"⏱️ sᴛᴀʀᴛᴇᴅ ᴀᴛ: {datetime.now().strftime('%H:%M:%S')}\n"
                f"📝 ɴᴇᴡ ʟᴏɢs ᴡɪʟʟ ᴀᴘᴘᴇᴀʀ ʙᴇʟᴏᴡ\\.\\.\\.\n"
                f"📴 ᴄʟɪᴄᴋ 'ʟɪᴠᴇ ʟᴏɢs ᴏғғ' ᴛᴏ sᴛᴏᴘ\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            parse_mode='MarkdownV2'
        )
        live_logs_message_ids[user_id].append(start_msg.message_id)
        
        # Background task for continuous log replies
        async def logs_streamer():
            last_size = 0
            last_lines_count = 0
            error_count = 0
            batch_logs = []  # Collect logs to batch send
            
            while live_logs_status.get(user_id, {}).get("running", False):
                try:
                    if not os.path.exists(log_file):
                        await asyncio.sleep(2)
                        continue
                    
                    current_size = os.path.getsize(log_file)
                    
                    # Only process if file changed
                    if current_size > last_size:
                        try:
                            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                                if current_size > 50000:  # If file > 50KB, read last part only
                                    f.seek(current_size - 50000)
                                content = f.read()
                            
                            lines = content.split('\n')
                            
                            # Find new lines only
                            if len(lines) > last_lines_count:
                                new_lines = lines[last_lines_count:]
                                last_lines_count = len(lines)
                                
                                # Add to batch
                                for line in new_lines:
                                    if line.strip():  # Skip empty lines
                                        batch_logs.append(line)
                                
                                # Send batch if we have enough lines or enough time passed
                                if len(batch_logs) >= 5 or (batch_logs and len(batch_logs[-1]) > 100):
                                    # Format as console output
                                    log_text = '\n'.join(batch_logs[-10:])  # Last 10 lines max per message
                                    
                                    # Escape for MarkdownV2
                                    safe_text = escape_markdown(log_text[:4000])
                                    
                                    # Send as NEW message (not edit)
                                    try:
                                        msg = await context.bot.send_message(
                                            chat_id=chat_id,
                                            text=f"`\n{safe_text}\n```",  # Code block style
                                            parse_mode='MarkdownV2'
                                        )
                                        live_logs_message_ids[user_id].append(msg.message_id)
                                        live_logs_status[user_id]["message_count"] += 1
                                        
                                        # Keep only last 50 message IDs to prevent memory issues
                                        if len(live_logs_message_ids[user_id]) > 50:
                                            live_logs_message_ids[user_id] = live_logs_message_ids[user_id][-50:]
                                        
                                        batch_logs = []  # Clear batch
                                        error_count = 0
                                    except Exception as e:
                                        error_count += 1
                                        if error_count > 10:
                                            logger.error(f"ᴛᴏᴏ ᴍᴀɴʏ sᴇɴᴅ ᴇʀʀᴏʀs, sᴛᴏᴘᴘɪɴɢ ʟɪᴠᴇ ʟᴏɢs: {e}")
                                            break
                                        await asyncio.sleep(1)
                            
                        except Exception as e:
                            logger.error(f"ᴇʀʀᴏʀ ʀᴇᴀᴅɪɴɢ ʟᴏɢ ғɪʟᴇ: {e}")
                    
                    last_size = current_size
                    await asyncio.sleep(1)  # Check every 1 second
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"ʟɪᴠᴇ ʟᴏɢs sᴛʀᴇᴀᴍᴇʀ ᴇʀʀᴏʀ: {e}")
                    await asyncio.sleep(2)
            
            # Send STOP message
            try:
                duration = datetime.now() - live_logs_status[user_id]['start_time']
                end_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                        f"📴 ʟɪᴠᴇ ʟᴏɢs sᴛᴏᴘᴘᴇᴅ: {escape_markdown(p_name)}\n"
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                        f"⏱️ ᴅᴜʀᴀᴛɪᴏɴ: {str(duration).split('.')[0]}\n"
                        f"📝 ᴛᴏᴛᴀʟ ᴍᴇssᴀɢᴇs: {live_logs_status[user_id]['message_count']}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    parse_mode='MarkdownV2'
                )
                live_logs_message_ids[user_id].append(end_msg.message_id)
            except Exception as e:
                logger.error(f"ᴇʀʀᴏʀ sᴇɴᴅɪɴɢ ғɪɴᴀʟ ʟɪᴠᴇ ʟᴏɢs ᴍᴇssᴀɢᴇ: {e}")
            
            # Cleanup
            if user_id in live_logs_status:
                del live_logs_status[user_id]
        
        # Start background task
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
    """
    Stop live logs for a user - sets running=False so the loop stops
    """
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

# --- [PROJECT MANAGEMENT FUNCTIONS] ---
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
            logger.error(f"ᴘʀᴏᴊᴇᴄᴛ {p_name} ɴᴏᴛ ғᴏᴜɴᴅ ɪɴ ᴘʀᴏᴊᴇᴄᴛ_ᴏᴡɴᴇʀs")
            return False

        data = project_owners[p_name]
        folder = data["path"]
        main_file = data.get("main_file", "main.py")
        main_file_path = os.path.join(folder, main_file)
        
        if not os.path.exists(main_file_path):
            logger.error(f"ᴍᴀɪɴ ғɪʟᴇ ɴᴏᴛ ғᴏᴜɴᴅ: {main_file_path}")
            return False
        
        log_file = os.path.join(LOGS_DIR, f"{p_name}.log")
        
        try:
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"\n\n--- ʀᴇsᴛᴀʀᴛ ᴀᴛ {datetime.now()} ---\n")
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
            
            logger.info(f"ᴘʀᴏᴊᴇᴄᴛ {p_name} sᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ᴡɪᴛʜ ᴘɪᴅ {proc.pid}")
            return True
            
        except Exception as e:
            logger.error(f"ᴇʀʀᴏʀ sᴛᴀʀᴛɪɴɢ ᴘʀᴏᴄᴇss: {e}")
            return False
            
    except Exception as e:
        logger.error(f"ʀᴇsᴛᴀʀᴛ ᴇʀʀᴏʀ ғᴏʀ {p_name}: {e}")
        return False

# --- [COMMAND HANDLERS] ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        user = update.effective_user
        
        if bot_locked and not is_admin(user_id):
            await update.message.reply_text(
                "🔒 sʏsᴛᴇᴍ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ʟᴏᴄᴋᴇᴅ ʙʏ ᴀᴅᴍɪɴ",
                parse_mode='Markdown'
            )
            return
        
        # Properly format user info with small caps
        user_name = to_small_caps(user.full_name or "Unknown")
        username_raw = user.username if user.username else None
        username_formatted = format_username(username_raw)
        username_display = to_small_caps(username_formatted) if username_raw else "ɴᴏ ᴜsᴇʀɴᴀᴍᴇ"
        user_id_str = str(user_id)
        
        # Escape for MarkdownV2
        user_name_escaped = escape_markdown(user_name)
        username_display_escaped = escape_markdown(username_display)
        
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
        logger.error(f"sᴛᴀʀᴛ ᴄᴏᴍᴍᴀɴᴅ ᴇʀʀᴏʀ: {e}")
        # Fallback without markdown if error occurs
        try:
            await update.message.reply_text(
                f"{to_small_caps('Welcome to Apon Premium Hosting v1')}\n"
                f"{to_small_caps('Your ID:')} {user_id}\n"
                f"{to_small_caps('Owner:')} {ADMIN_USERNAME}",
                reply_markup=get_main_keyboard(user_id)
            )
        except:
            pass

# --- [DOCUMENT HANDLER] ---
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        if bot_locked and not is_admin(user_id):
            await update.message.reply_text(
                "🔒 sʏsᴛᴇᴍ ɪs ʟᴏᴄᴋᴇᴅ",
                parse_mode='Markdown'
            )
            return
        
        if not update.message.document:
            await update.message.reply_text(
                "❌ ɴᴏ ғɪʟᴇ ғᴏᴜɴᴅ!",
                parse_mode='Markdown'
            )
            return
        
        doc = update.message.document
        
        if not doc.file_name.endswith('.zip'):
            await update.message.reply_text(
                "❌ ᴏɴʟʏ .ᴢɪᴘ ғɪʟᴇs ᴀʀᴇ ᴀᴄᴄᴇᴘᴛᴇᴅ!",
                parse_mode='Markdown'
            )
            return
        
        if doc.file_size > 20 * 1024 * 1024:
            await update.message.reply_text(
                "❌ ғɪʟᴇ sɪᴢᴇ ᴍᴀxɪᴍᴜᴍ 20ᴍʙ!",
                parse_mode='Markdown'
            )
            return
        
        msg = await update.message.reply_text("🗳️ ᴜᴘʟᴏᴀᴅɪɴɢ: [▱▱▱▱▱▱▱▱▱▱] 0%")
        
        try:
            frames = Loading.uploading()
            for i, frame in enumerate(frames):
                await asyncio.sleep(0.8)
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=msg.message_id,
                        text=frame
                    )
                except Exception as e:
                    logger.warning(f"ᴜᴘʟᴏᴀᴅ ᴀɴɪᴍᴀᴛɪᴏɴ ғʀᴀᴍᴇ ᴇʀʀᴏʀ: {e}")
            
            temp_dir = os.path.join(BASE_DIR, f"tmp_{user_id}_{int(time.time())}")
            os.makedirs(temp_dir, exist_ok=True)
            zip_path = os.path.join(temp_dir, doc.file_name)
            
            try:
                file = await doc.get_file()
                await file.download_to_drive(zip_path)
                logger.info(f"ғɪʟᴇ ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ ᴛᴏ: {zip_path}")
            except Exception as e:
                logger.error(f"ғɪʟᴇ ᴅᴏᴡɴʟᴏᴀᴅ ᴇʀʀᴏʀ: {e}")
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=msg.message_id,
                    text="❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ ғɪʟᴇ!",
                    parse_mode='Markdown'
                )
                return
            
            if not os.path.exists(zip_path):
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=msg.message_id,
                    text="❌ ғɪʟᴇ sᴀᴠᴇ ғᴀɪʟᴇᴅ!",
                    parse_mode='Markdown'
                )
                return
            
            user_upload_state[user_id] = {
                "path": zip_path,
                "u_name": update.effective_user.full_name or "Unknown",
                "original_name": doc.file_name,
                "temp_dir": temp_dir,
                "chat_id": update.effective_chat.id,
                "message_id": msg.message_id
            }
            
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
            await update.message.reply_text(
                f"❌ ᴜᴘʟᴏᴀᴅ ғᴀɪʟᴇᴅ: {str(e)}"
            )
            
    except Exception as e:
        logger.error(f"ᴅᴏᴄᴜᴍᴇɴᴛ ʜᴀɴᴅʟᴇʀ ᴇʀʀᴏʀ: {e}")
        try:
            await update.message.reply_text(
                "❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ, ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ."
            )
        except:
            pass
# --- [TEXT HANDLER] ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text
        global bot_locked, auto_restart_mode, recovery_enabled

        if bot_locked and not is_admin(user_id):
            await update.message.reply_text(
                "🔒 sʏsᴛᴇᴍ ɪs ʟᴏᴄᴋᴇᴅ"
            )
            return

        if user_id in user_upload_state and "path" in user_upload_state[user_id]:
            await handle_project_naming(update, context, user_id, text)
            return

        await handle_buttons(update, context, user_id, text)
        
    except Exception as e:
        logger.error(f"ᴛᴇxᴛ ʜᴀɴᴅʟᴇʀ ᴇʀʀᴏʀ: {e}")

async def handle_project_naming(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    try:
        state = user_upload_state[user_id]
        
        # Sanitize project name
        p_name = text.replace(" ", "_").replace("/", "_").replace("\\", "_").replace("..", "_")
        
        if not p_name or p_name.startswith(".") or p_name.startswith("_"):
            await update.message.reply_text(
                "❌ ɪɴᴠᴀʟɪᴅ ɴᴀᴍᴇ! ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ."
            )
            return
        
        if len(p_name) > 50:
            await update.message.reply_text(
                "❌ ɴᴀᴍᴇ ᴛᴏᴏ ʟᴏɴɢ! ᴍᴀxɪᴍᴜᴍ 50 ᴄʜᴀʀᴀᴄᴛᴇʀs."
            )
            return
        
        extract_path = os.path.join(BASE_DIR, p_name)
        
        if os.path.exists(extract_path):
            await update.message.reply_text(
                "⚠️ ᴀ ᴘʀᴏᴊᴇᴄᴛ ᴡɪᴛʜ ᴛʜɪs ɴᴀᴍᴇ ᴀʟʀᴇᴀᴅʏ ᴇxɪsᴛs! ᴄʜᴏᴏsᴇ ᴀɴᴏᴛʜᴇʀ ɴᴀᴍᴇ."
            )
            return
        
        msg = await update.message.reply_text(Loading.executing()[0])
        
        try:
            os.makedirs(extract_path, exist_ok=True)
            zip_path = state["path"]
            
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                logger.info(f"ᴇxᴛʀᴀᴄᴛᴇᴅ {zip_path} ᴛᴏ {extract_path}")
            except Exception as e:
                logger.error(f"ᴢɪᴘ ᴇxᴛʀᴀᴄᴛɪᴏɴ ᴇʀʀᴏʀ: {e}")
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
                        logger.warning(f"ʀᴇǫᴜɪʀᴇᴍᴇɴᴛs ɪɴsᴛᴀʟʟ ᴡᴀʀɴɪɴɢ: {result.stderr}")
                except Exception as e:
                    logger.error(f"ʀᴇǫᴜɪʀᴇᴍᴇɴᴛs ɪɴsᴛᴀʟʟ ғᴀɪʟᴇᴅ: {e}")
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
                "u_username": update.effective_user.username or "no_username",
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
            
            final_text = (
                f"✅ ᴘʀᴏᴊᴇᴄᴛ {p_name} sᴀᴠᴇᴅ!\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"📁 {to_small_caps('Entry Point:')} {main_file}\n"
                f"🚀 {to_small_caps('Now go to')} 'ғɪʟᴇ ᴍᴀɴᴀɢᴇʀ' {to_small_caps('to run')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )
            
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id,
                text=final_text
            )
            
        except Exception as e:
            logger.error(f"ᴘʀᴏᴊᴇᴄᴛ ɴᴀᴍɪɴɢ ᴇʀʀᴏʀ: {e}")
            await update.message.reply_text(
                f"❌ ᴇʀʀᴏʀ: {str(e)}"
            )
            if user_id in user_upload_state:
                shutil.rmtree(user_upload_state[user_id].get("temp_dir", ""), ignore_errors=True)
                del user_upload_state[user_id]
                
    except Exception as e:
        logger.error(f"ʜᴀɴᴅʟᴇ ᴘʀᴏᴊᴇᴄᴛ ɴᴀᴍɪɴɢ ᴇʀʀᴏʀ: {e}")
        await update.message.reply_text(
            "❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!"
        )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    global bot_locked, auto_restart_mode, recovery_enabled
    
    try:
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
                await update.message.reply_text(
                    f"❌ {to_small_caps('You have no projects! Please upload first.')}"
                )
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
                await update.message.reply_text(
                    f"❌ {to_small_caps('You have no projects')}"
                )
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
                await update.message.reply_text(
                    f"❌ {to_small_caps('You have no projects! Please upload first.')}"
                )
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
                f"{to_small_caps('Select which project to view logs:')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif text == "📴 ʟɪᴠᴇ ʟᴏɢs ᴏғғ":
            stopped = await stop_live_logs(user_id, context)
            if stopped:
                await update.message.reply_text(
                    f"📴 {to_small_caps('Live Logs Off')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ {to_small_caps('Live log monitoring stopped')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )
            else:
                await update.message.reply_text(
                    f"📴 {to_small_caps('Live Logs Off')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"⚠️ {to_small_caps('No live logs were running')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )

        elif text == "🏩 sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ":
            msg = await update.message.reply_text("🏩 sʏsᴛᴇᴍ ᴄʜᴇᴄᴋ: [▱▱▱▱▱▱▱▱▱▱] 0%")
            
            try:
                for frame in Loading.health_check()[1:]:
                    await asyncio.sleep(0.3)
                    try:
                        await context.bot.edit_message_text(
                            chat_id=update.effective_chat.id,
                            message_id=msg.message_id,
                            text=frame
                        )
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
                
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=msg.message_id,
                    text=msg_text
                )
                
            except Exception as e:
                logger.error(f"sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ ᴅɪsᴘʟᴀʏ ᴇʀʀᴏʀ: {e}")
                await update.message.reply_text(
                    f"❌ {to_small_caps('Error loading health data')}"
                )

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
                await update.message.reply_text(
                    f"🌎 {to_small_caps('Server Info')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🚀 {to_small_caps('Port:')} {PORT}\n"
                    f"🔄 {to_small_caps('Auto-Restart:')} {'ᴏɴ' if auto_restart_mode else 'ᴏғғ'}\n"
                    f"🛡️ {to_small_caps('Auto-Recovery:')} {'ᴏɴ' if recovery_enabled else 'ᴏғғ'}\n"
                    f"📋 {to_small_caps('Total Projects:')} {len(project_owners)}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━"
                )

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

        elif is_admin(user_id):
            if text == "🔒 ʟᴏᴄᴋ sʏsᴛᴇᴍ":
                bot_locked = True
                await update.message.reply_text("🔒 sʏsᴛᴇᴍ ʟᴏᴄᴋᴇᴅ")
                await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_main_keyboard(user_id))
            
            elif text == "🔓 ᴜɴʟᴏᴄᴋ sʏsᴛᴇᴍ":
                bot_locked = False
                await update.message.reply_text("🔓 sʏsᴛᴇᴍ ᴜɴʟᴏᴄᴋᴇᴅ")
                await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_main_keyboard(user_id))
            
            elif text == "🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ: ᴏɴ":
                auto_restart_mode = False
                await update.message.reply_text("🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ: ᴏғғ")
                await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_main_keyboard(user_id))

            elif text == "🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ: ᴏғғ":
                auto_restart_mode = True
                await update.message.reply_text("🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ: ᴏɴ")
                await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_main_keyboard(user_id))

            elif text == "🛡️ ʀᴇᴄᴏᴠᴇʀʏ: ᴏɴ":
                recovery_enabled = False
                await update.message.reply_text("🛡️ ʀᴇᴄᴏᴠᴇʀʏ: ᴏғғ")
                await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_main_keyboard(user_id))

            elif text == "🛡️ ʀᴇᴄᴏᴠᴇʀʏ: ᴏғғ":
                recovery_enabled = True
                await update.message.reply_text("🛡️ ʀᴇᴄᴏᴠᴇʀʏ: ᴏɴ")
                await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_main_keyboard(user_id))

            elif text == "🎬 ᴘʀᴏᴊᴇᴄᴛ ғɪʟᴇs":
                # FIXED: Send ALL project files to admin with proper MarkdownV2 escaping
                if not project_owners:
                    await update.message.reply_text(f"🎬 {to_small_caps('No projects available')}")
                    return
                
                await update.message.reply_text(
                    f"📋 {to_small_caps('Total')} {len(project_owners)} {to_small_caps('projects')}\n"
                    f"{to_small_caps('Sending all files with full information to admin...')}"
                )
                
                count = 0
                for p_name, d in list(project_owners.items()):
                    try:
                        # Get user info with proper formatting
                        owner_id = d.get('u_id', 'N/A')
                        owner_name = d.get('u_name', 'Unknown')
                        owner_username_raw = d.get('u_username', 'no_username')
                        owner_username = format_username(owner_username_raw)
                        
                        # Convert to small caps
                        owner_name_small = to_small_caps(owner_name)
                        owner_username_small = to_small_caps(owner_username)
                        
                        main_file = d.get('main_file', 'main.py')
                        created_at = d.get('created_at', 0)
                        created_date = datetime.fromtimestamp(created_at).strftime('%Y-%m-%d %H:%M') if created_at else to_small_caps('Unknown')
                        last_run = d.get('last_run')
                        last_run_str = datetime.fromtimestamp(last_run).strftime('%Y-%m-%d %H:%M') if last_run else to_small_caps('Never')
                        run_count = d.get('run_count', 0)
                        status = get_project_status(p_name)
                        status_emoji = "💚 ᴏɴʟɪɴᴇ" if status == "online" else "💔 ᴏғғʟɪɴᴇ" if status == "offline" else "⚠️ ᴄʀᴀsʜᴇᴅ"
                        
                        # Escape all text for MarkdownV2
                        p_name_escaped = escape_markdown(p_name)
                        owner_name_escaped = escape_markdown(owner_name_small)
                        owner_username_escaped = escape_markdown(owner_username_small)
                        main_file_escaped = escape_markdown(main_file)
                        created_date_escaped = escape_markdown(created_date)
                        last_run_escaped = escape_markdown(last_run_str)
                        
                        # SCREENSHOT STYLE CAPTION - SHORT & CLEAN
                        cap = (
                            f"🎬 {escape_markdown(to_small_caps('Project:'))} {p_name_escaped}\n"
                            f"👤 {escape_markdown(to_small_caps('User:'))} {owner_name_escaped}\n"
                            f"🆔 {escape_markdown(to_small_caps('ID:'))} {owner_id}\n"
                            f"📁 {escape_markdown(to_small_caps('Entry:'))} {main_file_escaped}"
                        )
                        
                        # FIX: Create zip from project folder if zip not found
                        project_path = d.get('path')
                        zip_path = d.get('zip')
                        
                        # Check if original zip exists
                        file_to_send = None
                        temp_zip_created = False
                        
                        if zip_path and os.path.exists(zip_path):
                            file_to_send = zip_path
                        elif project_path and os.path.exists(project_path):
                            # CREATE NEW ZIP FROM PROJECT FOLDER
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
                                logger.info(f"✅ Created temp zip for {p_name}: {temp_zip_path}")
                            except Exception as e:
                                logger.error(f"❌ Failed to create zip for {p_name}: {e}")
                        
                        if file_to_send and os.path.exists(file_to_send):
                            with open(file_to_send, 'rb') as f:
                                await context.bot.send_document(
                                    chat_id=update.effective_chat.id,
                                    document=f,
                                    caption=cap,
                                    parse_mode='MarkdownV2'
                                )
                            count += 1
                            
                            # Clean up temp zip if created
                            if temp_zip_created and os.path.exists(file_to_send):
                                try:
                                    os.remove(file_to_send)
                                except:
                                    pass
                        else:
                            # If zip not found, send info without file
                            await update.message.reply_text(
                                f"⚠️ {p_name_escaped}\n"
                                f"❌ {escape_markdown(to_small_caps('Zip file not found on server'))}\n"
                                f"{escape_markdown(to_small_caps('But project data exists in database.'))}",
                                parse_mode='MarkdownV2'
                            )
                        
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"sᴇɴᴅ ғɪʟᴇ ᴇʀʀᴏʀ ғᴏʀ {p_name}: {e}")
                        await update.message.reply_text(f"❌ {to_small_caps('Error sending')} {p_name}: {str(e)}")
                
                await update.message.reply_text(f"✅ {count} {to_small_caps('project files sent successfully!')} 🌹")

            elif text == "📋 ᴀʟʟ ᴘʀᴏᴊᴇᴄᴛs":
                if not project_owners:
                    await update.message.reply_text(f"📋 {to_small_caps('No projects')}")
                    return
                
                online_count = sum(1 for p in project_owners if get_project_status(p) == "online")
                msg = (
                    f"📋 {to_small_caps('All Projects')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📁 {to_small_caps('Total:')} {len(project_owners)}\n"
                    f"💚 {to_small_caps('Running:')} {online_count}\n"
                    f"💔 {to_small_caps('Stopped:')} {len(project_owners) - online_count}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                )
                
                for p_name, d in list(project_owners.items())[:20]:
                    status = get_project_status(p_name)
                    emoji = "💚" if status == "online" else "💔"
                    msg += f"{emoji} {p_name} - {to_small_caps(d.get('u_name', 'Unknown'))}\n"
                
                await update.message.reply_text(msg)

            elif text == "🪐 ʀᴇsᴛᴀʀᴛ ᴀʟʟ":
                msg = await update.message.reply_text(f"🪐 {to_small_caps('Restarting all projects...')}")
                count = 0
                for p_name in list(running_processes.keys()):
                    if restart_project(p_name):
                        count += 1
                    await asyncio.sleep(1)
                
                await msg.edit_text(f"✅ {count} {to_small_caps('projects restarted')}")
        
        else:
            await update.message.reply_text(
                f"❌ {to_small_caps('Unknown command! Please select from the menu below.')}",
                reply_markup=get_main_keyboard(user_id)
            )
            
    except Exception as e:
        logger.error(f"ʙᴜᴛᴛᴏɴ ʜᴀɴᴅʟᴇʀ ᴇʀʀᴏʀ: {e}")
        try:
            await update.message.reply_text(
                f"❌ {to_small_caps('An error occurred, please try again.')}"
            )
        except:
            pass
# --- [CALLBACK QUERY HANDLER] ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        chat_id = query.message.chat.id if query.message else None
        message_id = query.message.message_id if query.message else None
        
        if not chat_id or not message_id:
            logger.error("ɴᴏ ᴄʜᴀᴛ_ɪᴅ ᴏʀ ᴍᴇssᴀɢᴇ_ɪᴅ ɪɴ ᴄᴀʟʟʙᴀᴄᴋ")
            return
        
        if data == "cancel_delete":
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ {to_small_caps('Operation cancelled')}"
            )
            return
        
        if data == "cancel_livelogs":
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ {to_small_caps('Live logs selection cancelled')}"
            )
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
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"📺 {to_small_caps('Starting live logs for')} {p_name}..."
            )
            
            class FakeUpdate:
                def __init__(self, callback_query):
                    self.callback_query = callback_query
            
            fake_update = FakeUpdate(query)
            await show_live_logs(fake_update, context, p_name)
            return

        if action == "run":
            if get_project_status(p_name) == "online":
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"⚠️ {p_name} {to_small_caps('is already running!')}"
                )
                return
            
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=Loading.executing()[0]
            )
            
            for frame in Loading.executing()[1:-1]:
                await asyncio.sleep(0.4)
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=frame
                    )
                except:
                    pass
            
            if restart_project(p_name):
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"🚀 {p_name} {to_small_caps('started successfully!')} 💚"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ {to_small_caps('Failed to start')} {p_name}\n{to_small_caps('Check logs.')}"
                )
        
        elif action == "stop":
            if p_name not in running_processes:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"⚠️ {p_name} {to_small_caps('is not running')}"
                )
                return
            
            for i in range(100, -1, -20):
                await asyncio.sleep(0.3)
                bar = "▰" * (i // 10) + "▱" * (10 - (i // 10))
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
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
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"🛑 {p_name} {to_small_caps('stopped!')} 💔"
                )
            except Exception as e:
                logger.error(f"sᴛᴏᴘ ᴇʀʀᴏʀ: {e}")
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ {to_small_caps('Error stopping:')} {str(e)}"
                )
        
        elif action == "del":
            for frame in Loading.deleting():
                await asyncio.sleep(0.5)
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=frame
                    )
                except:
                    pass
            
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
                        await stop_live_logs(uid, context)
                
                path = os.path.join(BASE_DIR, p_name)
                if os.path.exists(path):
                    shutil.rmtree(path)
                
                if p_name in project_owners:
                    del project_owners[p_name]
                    save_data()
                
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"🗑️ {p_name} {to_small_caps('deleted!')}"
                )
                
            except Exception as e:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ {to_small_caps('Error deleting:')} {str(e)}"
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
                chat_id=chat_id,
                message_id=message_id,
                text=f"🔄 {to_small_caps('Restarting...')}"
            )
            
            if restart_project(p_name):
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"✅ {p_name} {to_small_caps('restarted!')}"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ {p_name} {to_small_caps('restart failed')}"
                )
        
        elif action == "logs":
            log_file = os.path.join(LOGS_DIR, f"{p_name}.log")
            
            if not os.path.exists(log_file):
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=to_small_caps("No log file found")
                )
                return
            
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    logs = f.read()
                
                if len(logs) > 3500:
                    logs = "...[truncated]...\n" + logs[-3500:]
                
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"📋 {to_small_caps('Logs for')} {p_name}\n`\n{logs}\n```"
                )
                
            except Exception as e:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ {to_small_caps('Error reading logs:')} {str(e)}"
                )
                
    except Exception as e:
        logger.error(f"ᴄᴀʟʟʙᴀᴄᴋ ᴇʀʀᴏʀ: {e}")
        try:
            if 'chat_id' in locals() and 'message_id' in locals():
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ {to_small_caps('An error occurred!')}"
                )
        except:
            pass

# --- [RECOVERY SYSTEM] ---
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
                    else:
                        self.crash_log.append({
                            "project": p_name,
                            "time": time.time(),
                            "reason": "Max retries exceeded"
                        })
                        
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

# --- [MAIN FUNCTION] ---
def main():
    try:
        web_thread = Thread(target=run_web, daemon=True)
        web_thread.start()
        logger.info("ᴡᴇʙ sᴇʀᴠᴇʀ sᴛᴀʀᴛᴇᴅ")
        
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.Document.ZIP, handle_docs))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(CallbackQueryHandler(button_callback))
        
        logger.info("🚀 ʙᴏᴛ sᴛᴀʀᴛᴇᴅ ᴡɪᴛʜ ᴀᴅᴠᴀɴᴄᴇᴅ ʀᴇᴄᴏᴠᴇʀʏ sʏsᴛᴇᴍ!")
        
        # Start recovery system in background
        async def start_recovery():
            await asyncio.sleep(2)  # Wait for bot to start
            await recovery_system.start_monitoring(application)
        
        # Create task for recovery
        loop = asyncio.get_event_loop()
        loop.create_task(start_recovery())
        
        # Run bot
        application.run_polling(
            drop_pending_updates=True,
            close_loop=False
        )
        
    except Exception as e:
        logger.critical(f"ᴍᴀɪɴ ᴇʀʀᴏʀ: {e}")
        raise

if __name__ == '__main__':
    main()
