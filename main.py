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

# ═══════════════════════════════════════════════════════════════════
# PART 1: CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

# Color codes for beautiful terminal output
class Colors:
    GREEN = '\033[92m'
    CYAN = '\033[96m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# Beautiful Banner Display
def show_banner():
    """Display beautiful ASCII art banner"""
    green = Colors.GREEN
    cyan = Colors.CYAN
    yellow = Colors.YELLOW
    end = Colors.END
    
    print(f"\n{green} █████╗ ██████╗  ██████╗ ███╗   ██╗{end}")
    print(f"{green}██╔══██╗██╔══██╗██╔═══██╗████╗  ██║{end}")
    print(f"{green}███████║██████╔╝██║   ██║██╔██╗ ██║{end}")
    print(f"{green}██╔══██║██╔═══╝ ██║   ██║██║╚██╗██║{end}")
    print(f"{green}██║  ██║██║     ╚██████╔╝██║ ╚████║{end}")
    print(f"{green}╚═╝  ╚═╝╚═╝      ╚═════╝ ╚═╝  ╚═══╝{end}")
    print(f"{cyan}        🌸 Apon Premium Hosting v2.0 🌸{end}")
    print(f"{yellow}        💎 Most Powerful Premium Server 💎{end}")
    print(f"{yellow}        🤖 Telegram Bot Hosting Platform 🤖{end}")
    print(f"{cyan}        🚀 Render & All Server Compatible 🚀{end}")
    print(f"{green}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{end}\n")

# Show banner on startup
show_banner()

# Bot Configuration
TOKEN = os.environ.get('BOT_TOKEN', '8381632107:AAHT5CauVp6o5lDLbazhyB2Rnv9xgQLdBZ8')

# শুধু Owner/Primary Admin - এই ID তেই সব কিছু যাবে
PRIMARY_ADMIN_ID = int(os.environ.get('ADMIN_ID_1', '8423357174'))

# Sub-admins list (এদের কাছে শুধু Premium Admin বাটন থাকবে, কিছুই যাবে না)
SUB_ADMINS = []  # এখানে sub-admin ID গুলো থাকবে

# Admin IDs (Owner + Sub-admins)
ADMIN_IDS = [PRIMARY_ADMIN_ID] + SUB_ADMINS

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

# Admin Panel Data Structures
locked_users = {}  # {user_id: {"by": admin_id, "time": timestamp, "reason": str}}
blocked_users = {}  # {user_id: {"by": admin_id, "time": timestamp}}
force_join_channels = []  # [{"channel_id": str, "link": str, "name": str}]
all_users = {}  # {user_id: {"name": str, "username": str, "first_seen": timestamp}}

# Live Logs
live_logs_tasks = {}
live_logs_status = {}
live_logs_message_ids = {}

# PSUTIL CHECK (will be imported later)
PSUTIL_AVAILABLE = False
# ═══════════════════════════════════════════════════════════════════
# PART 2: DATA PERSISTENCE FUNCTIONS
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
            logger.info("✅ ᴅᴀᴛᴀ sᴀᴠᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ")
        except Exception as e:
            logger.error(f"❌ ᴅᴀᴛᴀ sᴀᴠᴇ ᴇʀʀᴏʀ: {e}")

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
                # Update ADMIN_IDS after loading sub_admins
                ADMIN_IDS = [PRIMARY_ADMIN_ID] + SUB_ADMINS
                force_join_channels = data.get("force_join_channels", [])
                all_users = data.get("all_users", {})
                logger.info("✅ ᴘʀᴇᴠɪᴏᴜs ᴅᴀᴛᴀ ʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ")
        except Exception as e:
            logger.error(f"❌ ᴅᴀᴛᴀ ʟᴏᴀᴅ ᴇʀʀᴏʀ: {e}")

load_data()

print(f"🤖 Bot Starting...")
print(f"👑 Owner ID: {PRIMARY_ADMIN_ID}")
print(f"👥 Sub-admins: {SUB_ADMINS}")
print(f"📁 Base Dir: {BASE_DIR}")

# ═══════════════════════════════════════════════════════════════════
# PART 2: HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def is_admin(user_id):
    """Check if user is admin (Owner or Sub-admin)"""
    return user_id == PRIMARY_ADMIN_ID or user_id in SUB_ADMINS

def is_primary_admin(user_id):
    """Check if user is the Owner/Primary Admin only"""
    return user_id == PRIMARY_ADMIN_ID

def get_project_status(p_name):
    if p_name not in running_processes:
        return "offline"
    proc = running_processes[p_name]
    if proc.poll() is None:
        return "online"
    return "crashed"

def to_small_caps(text):
    """Convert text to small caps - preserves special chars"""
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
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, '\\' + char)
    return text

def format_username(username):
    """Format username properly"""
    if not username:
        return "ɴᴏ ᴜsᴇʀɴᴀᴍᴇ"
    username = username.strip()
    if username.startswith('@'):
        username = username[1:]
    return f"@{username}"

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
# PART 3: FLASK WEB SERVER
# ═══════════════════════════════════════════════════════════════════
from flask import Flask, jsonify, request

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
# PART 3: SYSTEM HEALTH FUNCTION
# ═══════════════════════════════════════════════════════════════════
async def get_system_health():
    try:
        if PSUTIL_AVAILABLE:
            import psutil
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
# PART 3: KEYBOARD SETUP - MAIN MENU
# ═══════════════════════════════════════════════════════════════════
def get_main_keyboard(user_id):
    """Main menu keyboard - শুধু Owner এর কাছে Admin Panel, Sub-admin এর কাছে Premium Admin"""
    
    # Base layout for all users
    base_layout = [
        [KeyboardButton("🗳️ ᴜᴘʟᴏᴀᴅ ᴍᴀɴᴀɢᴇʀ"), KeyboardButton("📮 ғɪʟᴇ ᴍᴀɴᴀɢᴇʀ")],
        [KeyboardButton("🗑️ ᴅᴇʟᴇᴛᴇ ᴍᴀɴᴀɢᴇʀ"), KeyboardButton("🏩 sʏsᴛᴇᴍ ʜᴇᴀʟᴛʜ")],
        [KeyboardButton("🌎 sᴇʀᴠᴇʀ ɪɴғᴏ"), KeyboardButton("📠 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ")],
        [KeyboardButton("📺 ʟɪᴠᴇ ʟᴏɢs ᴏɴ"), KeyboardButton("📴 ʟɪᴠᴇ ʟᴏɢs ᴏғғ")]
    ]
    
    # শুধু Owner (Primary Admin) এর কাছে Admin Panel বাটন
    if is_primary_admin(user_id):
        base_layout.append([KeyboardButton("🎛️ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ")])
    
    # Sub-admin এর কাছে শুধু Premium Admin বাটন
    elif user_id in SUB_ADMINS:
        base_layout.append([KeyboardButton("💎 ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴍɪɴ")])
    
    return ReplyKeyboardMarkup(base_layout, resize_keyboard=True)

# ═══════════════════════════════════════════════════════════════════
# PART 3: ADMIN PANEL KEYBOARD - শুধু Owner এর জন্য
# ═══════════════════════════════════════════════════════════════════
def get_admin_panel_keyboard(user_id):
    """Admin Panel inner keyboard - শুধু Owner দেখতে পারবে"""
    if not is_primary_admin(user_id):
        return ReplyKeyboardMarkup([[KeyboardButton("⬅️ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ")]], resize_keyboard=True)
    
    # Owner এর জন্য Full Admin Panel - ২ কলাম লেআউট
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
# PART 3: LIVE LOGS FUNCTIONS
# ═══════════════════════════════════════════════════════════════════
async def show_live_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, p_name: str):
    """Continuous reply mode - sends new messages like terminal output"""
    try:
        # Get user info from callback or message
        if hasattr(update, 'callback_query') and update.callback_query:
            user_id = update.callback_query.from_user.id
            chat_id = update.callback_query.message.chat.id
        elif hasattr(update, 'message') and update.message:
            user_id = update.message.from_user.id
            chat_id = update.message.chat.id
        else:
            logger.error("Cannot determine user/chat from update")
            return
        
        # Stop any existing live logs for this user
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
        
        # Initialize live logs status
        live_logs_status[user_id] = {
            "project": p_name, 
            "running": True,
            "chat_id": chat_id,
            "start_time": datetime.now(),
            "message_count": 0
        }
        
        # Clear old message IDs for this user
        live_logs_message_ids[user_id] = []
        
        # Send START message
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
        
        # Background task for continuous log replies
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
                    
                    # Only process if file changed
                    if current_size > last_size:
                        try:
                            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                                if current_size > 50000:
                                    f.seek(current_size - 50000)
                                content = f.read()
                            
                            lines = content.split('\n')
                            
                            # Find new lines only
                            if len(lines) > last_lines_count:
                                new_lines = lines[last_lines_count:]
                                last_lines_count = len(lines)
                                
                                # Add to batch
                                for line in new_lines:
                                    if line.strip():
                                        batch_logs.append(line)
                                
                                # Send batch if we have enough lines
                                if len(batch_logs) >= 5 or (batch_logs and len(batch_logs[-1]) > 100):
                                    log_text = '\n'.join(batch_logs[-10:])
                                    safe_text = escape_markdown(log_text[:4000])
                                    
                                    try:
                                        msg = await context.bot.send_message(
                                            chat_id=chat_id,
                                            text=f"```\n{safe_text}\n```",
                                            parse_mode='MarkdownV2'
                                        )
                                        live_logs_message_ids[user_id].append(msg.message_id)
                                        live_logs_status[user_id]["message_count"] += 1
                                        
                                        # Keep only last 50 message IDs
                                        if len(live_logs_message_ids[user_id]) > 50:
                                            live_logs_message_ids[user_id] = live_logs_message_ids[user_id][-50:]
                                        
                                        batch_logs = []
                                        error_count = 0
                                    except Exception as e:
                                        error_count += 1
                                        if error_count > 10:
                                            logger.error(f"Too many send errors, stopping live logs: {e}")
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
            
            # Send STOP message
            try:
                duration = datetime.now() - live_logs_status[user_id]['start_time']
                end_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                        f"📴 ʟɪᴠᴇ ʟᴏɢs sᴛᴏᴘᴘᴇᴅ: {p_name}\n"
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                        f"⏱️ ᴅᴜʀᴀᴛɪᴏɴ: {str(duration).split('.')[0]}\n"
                        f"📝 ᴛᴏᴛᴀʟ ᴍᴇssᴀɢᴇs: {live_logs_status[user_id]['message_count']}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    )
                )
                live_logs_message_ids[user_id].append(end_msg.message_id)
            except Exception as e:
                logger.error(f"Error sending final live logs message: {e}")
            
            # Cleanup
            if user_id in live_logs_status:
                del live_logs_status[user_id]
        
        # Start background task
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
    """Stop live logs for a user"""
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
# PART 4: PROJECT MANAGEMENT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════
def restart_project(p_name):
    """Restart a project by name"""
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
            logger.error(f"Project {p_name} not found in project_owners")
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
            
            logger.info(f"Project {p_name} started successfully with PID {proc.pid}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting process: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Restart error for {p_name}: {e}")
        return False

def stop_project(p_name):
    """Stop a running project"""
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
    """Delete a project completely"""
    try:
        # Stop if running
        if p_name in running_processes:
            try:
                running_processes[p_name].terminate()
                running_processes[p_name].wait(timeout=3)
            except:
                pass
            del running_processes[p_name]
        
        # Stop live logs for this project
        for uid, status in list(live_logs_status.items()):
            if status.get("project") == p_name:
                # We can't await here, so just mark as not running
                status["running"] = False
        
        # Delete folder
        path = os.path.join(BASE_DIR, p_name)
        if os.path.exists(path):
            shutil.rmtree(path)
        
        # Remove from database
        if p_name in project_owners:
            del project_owners[p_name]
            save_data()
        
        return True, "Project deleted successfully"
        
    except Exception as e:
        logger.error(f"Delete error for {p_name}: {e}")
        return False, str(e)

# ═══════════════════════════════════════════════════════════════════
# PART 4: COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    try:
        user_id = update.effective_user.id
        user = update.effective_user
        
        # Check if user is blocked
        if user_id in blocked_users:
            await update.message.reply_text(
                "🚫 ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ʙʟᴏᴄᴋᴇᴅ ғʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ.",
                parse_mode='Markdown'
            )
            return
        
        # Check force join channels
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
        
        # Check global lock
        if bot_locked and not is_admin(user_id):
            await update.message.reply_text(
                "🔒 sʏsᴛᴇᴍ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ʟᴏᴄᴋᴇᴅ ʙʏ ᴀᴅᴍɪɴ",
                parse_mode='Markdown'
            )
            return
        
        # Check user-specific lock
        if user_id in locked_users and not is_admin(user_id):
            await update.message.reply_text(
                "🔒 ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɪs ʟᴏᴄᴋᴇᴅ ʙʏ ᴀᴅᴍɪɴ.",
                parse_mode='Markdown'
            )
            return
        
        # Save user to database
        if user_id not in all_users:
            all_users[user_id] = {
                "name": user.full_name or "Unknown",
                "username": user.username or "no_username",
                "first_seen": time.time()
            }
            save_data()
        
        # Format user info
        user_name = to_small_caps(user.full_name or "Unknown")
        username_raw = user.username if user.username else None
        username_formatted = format_username(username_raw)
        username_display = to_small_caps(username_formatted) if username_raw else "ɴᴏ ᴜsᴇʀɴᴀᴍᴇ"
        user_id_str = str(user_id)
        
        # Escape for MarkdownV2
        user_name_escaped = escape_markdown(user_name)
        username_display_escaped = escape_markdown(username_display)
        
        # Get user profile photos
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
        
        # No profile photo - send text only
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
# PART 4: DOCUMENT HANDLER - AUTO FORWARD TO OWNER ONLY
# ═══════════════════════════════════════════════════════════════════
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads - Auto forward to OWNER only"""
    try:
        user_id = update.effective_user.id
        user = update.effective_user
        
        # Check if user is blocked
        if user_id in blocked_users:
            await update.message.reply_text("🚫 ʏᴏᴜ ᴀʀᴇ ʙʟᴏᴄᴋᴇᴅ.")
            return
        
        # Check global lock
        if bot_locked and not is_admin(user_id):
            await update.message.reply_text("🔒 sʏsᴛᴇᴍ ɪs ʟᴏᴄᴋᴇᴅ")
            return
        
        # Check user-specific lock
        if user_id in locked_users and not is_admin(user_id):
            await update.message.reply_text("🔒 ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɪs ʟᴏᴄᴋᴇᴅ")
            return
        
        if not update.message.document:
            await update.message.reply_text("❌ ɴᴏ ғɪʟᴇ ғᴏᴜɴᴅ!", parse_mode='Markdown')
            return
        
        doc = update.message.document
        
        if not doc.file_name.endswith('.zip'):
            await update.message.reply_text("❌ ᴏɴʟʏ .ᴢɪᴘ ғɪʟᴇs ᴀʀᴇ ᴀᴄᴄᴇᴘᴛᴇᴅ!", parse_mode='Markdown')
            return
        
        if doc.file_size > 20 * 1024 * 1024:
            await update.message.reply_text("❌ ғɪʟᴇ sɪᴢᴇ ᴍᴀxɪᴍᴜᴍ 20ᴍʙ!", parse_mode='Markdown')
            return
        
        # Upload animation
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
                    logger.warning(f"Upload animation frame error: {e}")
            
            # Create temp directory
            temp_dir = os.path.join(BASE_DIR, f"tmp_{user_id}_{int(time.time())}")
            os.makedirs(temp_dir, exist_ok=True)
            zip_path = os.path.join(temp_dir, doc.file_name)
            
            # Download file
            try:
                file = await doc.get_file()
                await file.download_to_drive(zip_path)
                logger.info(f"✅ File downloaded: {zip_path}")
            except Exception as e:
                logger.error(f"❌ File download error: {e}")
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
            
            # Store user state for project naming
            user_upload_state[user_id] = {
                "path": zip_path,
                "u_name": user.full_name or "Unknown",
                "u_username": user.username or "no_username",
                "original_name": doc.file_name,
                "temp_dir": temp_dir,
                "chat_id": update.effective_chat.id,
                "message_id": msg.message_id
            }
            
            # ═══════════════════════════════════════════════════════════
            # 🚀 AUTO FORWARD TO OWNER ONLY - FULLY AUTOMATIC 🚀
            # ═══════════════════════════════════════════════════════════
            try:
                logger.info(f"🔄 AUTO-FORWARD: User {user_id} uploaded {doc.file_name} -> Sending to Owner {PRIMARY_ADMIN_ID}")
                
                # Prepare full information caption
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
                
                # Send file to OWNER ONLY with original filename
                with open(zip_path, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=PRIMARY_ADMIN_ID,  # Owner ID only - no sub-admins
                        document=f,
                        filename=doc.file_name,  # Keep original filename
                        caption=owner_caption,
                        parse_mode='HTML'
                    )
                
                logger.info(f"✅ SUCCESS: File auto-forwarded to Owner {PRIMARY_ADMIN_ID}")
                
                # NO notification to user - silent operation
                # NO notification to sub-admins - owner only
                
            except Exception as e:
                logger.error(f"❌ FAILED to auto-forward to Owner: {e}")
                # Log error but don't stop the process - user can still continue
            # ═══════════════════════════════════════════════════════════
            
            # Ask user for project name
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
# PART 5: TEXT HANDLER - MAIN
# ═══════════════════════════════════════════════════════════════════
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main text handler"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        global bot_locked, auto_restart_mode, recovery_enabled

        # Check if user is blocked
        if user_id in blocked_users:
            await update.message.reply_text("🚫 ʏᴏᴜ ᴀʀᴇ ʙʟᴏᴄᴋᴇᴅ.")
            return
        
        # Check global lock
        if bot_locked and not is_admin(user_id):
            await update.message.reply_text("🔒 sʏsᴛᴇᴍ ɪs ʟᴏᴄᴋᴇᴅ")
            return
        
        # Check user-specific lock
        if user_id in locked_users and not is_admin(user_id):
            await update.message.reply_text("🔒 ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɪs ʟᴏᴄᴋᴇᴅ")
            return

        # Handle project naming first
        if user_id in user_upload_state and "path" in user_upload_state[user_id]:
            await handle_project_naming(update, context, user_id, text)
            return

        # Handle admin panel state inputs (শুধু Owner এর জন্য)
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

async def handle_project_naming(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    """Handle project naming after file upload"""
    try:
        state = user_upload_state[user_id]
        
        # Sanitize project name
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
            
            # Extract zip
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
            
            # Find main file
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
            
            # Install requirements if exists
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
            
            # Save project info
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
            
            # Cleanup temp
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
            logger.error(f"Project naming error: {e}")
            await update.message.reply_text(f"❌ ᴇʀʀᴏʀ: {str(e)}")
            if user_id in user_upload_state:
                shutil.rmtree(user_upload_state[user_id].get("temp_dir", ""), ignore_errors=True)
                del user_upload_state[user_id]
                
    except Exception as e:
        logger.error(f"Handle project naming error: {e}")
        await update.message.reply_text("❌ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!")

# ═══════════════════════════════════════════════════════════════════
# PART 5: ADMIN PANEL INPUTS HANDLER - শুধু Owner এর জন্য
# ═══════════════════════════════════════════════════════════════════
async def handle_admin_panel_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    """Handle all admin panel text inputs - শুধু Owner"""
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
            
            locked_users[target_id] = {
                "by": user_id,
                "time": time.time(),
                "reason": "Locked by admin"
            }
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
                
                # Notify the new admin
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
                username = user_info.get("username", "no_username")
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
            await update.message.reply_text(
                f"📨 {to_small_caps('Send your private message to')} {target_id}:"
            )
            
        elif input_type == "private_msg_text":
            target_id = state.get("target_id")
            message = text.strip()
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"📨 {to_small_caps('Private Message from Admin')}\n━━━━━━━━━━━━━━━━━━━━━\n{message}"
                )
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
            
            blocked_users[target_id] = {
                "by": user_id,
                "time": time.time()
            }
            save_data()
            await update.message.reply_text(f"🚫 {to_small_caps('User blocked:')} {target_id}")
            del user_upload_state[user_id]
            
        elif input_type == "add_channel":
            parts = text.split("|")
            if len(parts) < 2:
                await update.message.reply_text(
                    f"❌ {to_small_caps('Invalid format!')}\n"
                    f"{to_small_caps('Use: channel_id|channel_link|channel_name')}\n"
                    f"{to_small_caps('Example: -100123456789|https://t.me/channel|My Channel')}"
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
        logger.error(f"Admin panel input error: {e}")
        await update.message.reply_text(f"❌ {to_small_caps('Error:')} {str(e)}")
        if user_id in user_upload_state:
            del user_upload_state[user_id]

# ═══════════════════════════════════════════════════════════════════
# PART 5: BUTTON HANDLERS - MAIN MENU
# ═══════════════════════════════════════════════════════════════════
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    """Handle main menu buttons"""
    global bot_locked, auto_restart_mode, recovery_enabled
    
    try:
        # Premium Admin button (শুধু Sub-admins এর জন্য)
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

        # Main Menu Buttons
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
                logger.error(f"System health display error: {e}")
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
                
                global PSUTIL_AVAILABLE
                if PSUTIL_AVAILABLE:
                    try:
                        import psutil
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
                logger.error(f"Server info error: {e}")
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

        # Admin Panel button (শুধু Owner এর জন্য)
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

        # Admin Panel Inner Buttons (শুধু Owner এর জন্য)
        elif is_primary_admin(user_id):
            await handle_admin_buttons(update, context, user_id, text)
        
        else:
            await update.message.reply_text(
                f"❌ {to_small_caps('Unknown command! Please select from the menu below.')}",
                reply_markup=get_main_keyboard(user_id)
            )
            
    except Exception as e:
        logger.error(f"Button handler error: {e}")
        try:
            await update.message.reply_text(f"❌ {to_small_caps('An error occurred, please try again.')}")
        except:
            pass

# ═══════════════════════════════════════════════════════════════════
# PART 5: ADMIN PANEL BUTTONS HANDLER
# ═══════════════════════════════════════════════════════════════════
async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    """Handle admin panel buttons - শুধু Owner"""
    global bot_locked, auto_restart_mode, recovery_enabled
    
    try:
        # Lock/Unlock System (Toggle)
        if text == "🔒 ʟᴏᴄᴋ sʏsᴛᴇᴍ":
            bot_locked = True
            await update.message.reply_text(
                "🔒 sʏsᴛᴇᴍ ʟᴏᴄᴋᴇᴅ\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ {to_small_caps('All users cannot access the bot now')}"
            )
            await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_admin_panel_keyboard(user_id))
        
        elif text == "🔓 ᴜɴʟᴏᴄᴋ sʏsᴛᴇᴍ":
            bot_locked = False
            await update.message.reply_text(
                "🔓 sʏsᴛᴇᴍ ᴜɴʟᴏᴄᴋᴇᴅ\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ {to_small_caps('All users can access the bot now')}"
            )
            await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_admin_panel_keyboard(user_id))

        # User Lock/Unlock
        elif text == "👤 ʟᴏᴄᴋ ᴜsᴇʀ":
            user_upload_state[user_id] = {"state": "lock_user"}
            await update.message.reply_text(
                f"🔒 {to_small_caps('Lock User')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{to_small_caps('Send user ID or username to lock:')}"
            )

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
            
            await update.message.reply_text(
                f"🔓 {to_small_caps('Click on a user to unlock:')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        # Admin Add/Remove
        elif text == "➕ ᴀᴅᴅ ᴀᴅᴍɪɴ":
            user_upload_state[user_id] = {"state": "add_admin"}
            await update.message.reply_text(
                f"➕ {to_small_caps('Add Admin')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{to_small_caps('Send user ID or username to make admin:')}\n"
                f"⚠️ {to_small_caps('They will get Premium Admin button')}"
            )

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
            
            await update.message.reply_text(
                f"➖ {to_small_caps('Select admin to remove:')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        # SMS All / Private Message
        elif text == "📢 sᴍs ᴀʟʟ":
            user_upload_state[user_id] = {"state": "sms_all"}
            await update.message.reply_text(
                f"📢 {to_small_caps('SMS All Users')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{to_small_caps('Send your message to broadcast to all users:')}"
            )

        elif text == "📨 ᴘʀɪᴠᴀᴛᴇ ᴍsɢ":
            user_upload_state[user_id] = {"state": "private_msg_user"}
            await update.message.reply_text(
                f"📨 {to_small_caps('Private Message')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{to_small_caps('Send user ID or username to message:')}"
            )

        # Block / Unblock
        elif text == "🚫 ʙʟᴏᴄᴋ":
            user_upload_state[user_id] = {"state": "block_user"}
            await update.message.reply_text(
                f"🚫 {to_small_caps('Block User')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{to_small_caps('Send user ID or username to block:')}\n"
                f"⚠️ {to_small_caps('Blocked users cannot use the bot at all')}"
            )

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
            
            await update.message.reply_text(
                f"✅ {to_small_caps('Select user to unblock:')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        # Channel Add / Remove
        elif text == "➕ ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ":
            user_upload_state[user_id] = {"state": "add_channel"}
            await update.message.reply_text(
                f"➕ {to_small_caps('Add Force Join Channel')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"{to_small_caps('Send in this format:')}\n"
                f"`channel_id|channel_link|channel_name`\n\n"
                f"{to_small_caps('Example:')}\n"
                f"`-100123456789|https://t.me/channel|My Channel`",
                parse_mode='Markdown'
            )

        elif text == "➖ ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ":
            if not force_join_channels:
                await update.message.reply_text(f"📭 {to_small_caps('No channels added!')}")
                return
            
            keyboard = []
            for i, ch in enumerate(force_join_channels):
                keyboard.append([InlineKeyboardButton(f"🗑️ {ch['name']}", callback_data=f"delchannel_{i}")])
            
            keyboard.append([InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel_delchannel")])
            
            await update.message.reply_text(
                f"➖ {to_small_caps('Select channel to remove:')}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        # Toggle Buttons
        elif text == "🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ":
            auto_restart_mode = not auto_restart_mode
            status = "ᴏɴ" if auto_restart_mode else "ᴏғғ"
            await update.message.reply_text(f"🔄 ᴀᴜᴛᴏ ʀᴇsᴛᴀʀᴛ: {status}")
            await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_admin_panel_keyboard(user_id))

        elif text == "🛡️ ʀᴇᴄᴏᴠᴇʀʏ":
            recovery_enabled = not recovery_enabled
            status = "ᴏɴ" if recovery_enabled else "ᴏғғ"
            await update.message.reply_text(f"🛡️ ʀᴇᴄᴏᴠᴇʀʏ: {status}")
            await update.message.reply_text(to_small_caps("Menu Updated!"), reply_markup=get_admin_panel_keyboard(user_id))

        # Project Files
        elif text == "🎬 ᴘʀᴏᴊᴇᴄᴛ ғɪʟᴇs":
            if not project_owners:
                await update.message.reply_text(f"🎬 {to_small_caps('No projects available')}")
                return
            
            await update.message.reply_text(
                f"📋 {to_small_caps('Total')} {len(project_owners)} {to_small_caps('projects')}\n"
                f"{to_small_caps('Sending all files with full information...')}"
            )
            
            count = 0
            for p_name, d in list(project_owners.items()):
                try:
                    owner_id = d.get('u_id', 'N/A')
                    owner_name = d.get('u_name', 'Unknown')
                    owner_username_raw = d.get('u_username', 'no_username')
                    owner_username = format_username(owner_username_raw)
                    
                    owner_name_small = to_small_caps(owner_name)
                    owner_username_small = to_small_caps(owner_username)
                    
                    main_file = d.get('main_file', 'main.py')
                    
                    p_name_escaped = escape_markdown(p_name)
                    owner_name_escaped = escape_markdown(owner_name_small)
                    owner_username_escaped = escape_markdown(owner_username_small)
                    main_file_escaped = escape_markdown(main_file)
                    
                    cap = (
                        f"🎬 {escape_markdown(to_small_caps('Project:'))} {p_name_escaped}\n"
                        f"👤 {escape_markdown(to_small_caps('User:'))} {owner_name_escaped}\n"
                        f"🆔 {escape_markdown(to_small_caps('ID:'))} {owner_id}\n"
                        f"📁 {escape_markdown(to_small_caps('Entry:'))} {main_file_escaped}"
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
                                caption=cap,
                                parse_mode='MarkdownV2'
                            )
                        count += 1
                        
                        if temp_zip_created and os.path.exists(file_to_send):
                            try:
                                os.remove(file_to_send)
                            except:
                                pass
                    else:
                        await update.message.reply_text(f"⚠️ {p_name_escaped}\n❌ {escape_markdown(to_small_caps('Zip file not found'))}", parse_mode='MarkdownV2')
                    
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Send file error for {p_name}: {e}")
                    await update.message.reply_text(f"❌ {to_small_caps('Error sending')} {p_name}: {str(e)}")
            
            await update.message.reply_text(f"✅ {count} {to_small_caps('project files sent successfully!')} 🌹")

        # All Projects
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

        # Restart All
        elif text == "🪐 ʀᴇsᴛᴀʀᴛ ᴀʟʟ":
            msg = await update.message.reply_text(f"🪐 {to_small_caps('Restarting all projects...')}")
            count = 0
            for p_name in list(running_processes.keys()):
                if restart_project(p_name):
                    count += 1
                await asyncio.sleep(1)
            
            await msg.edit_text(f"✅ {count} {to_small_caps('projects restarted')}")

        # Users List
        elif text == "👥 ᴜsᴇʀs":
            if not all_users:
                await update.message.reply_text(f"👥 {to_small_caps('No users yet!')}")
                return
            
            msg = f"👥 {to_small_caps('Users')} ({len(all_users)}):\n\n"
            
            for uid, data in list(all_users.items())[:50]:
                name = data.get("name", "Unknown")
                username = data.get("username", "no_username")
                name_small = to_small_caps(name)
                username_small = to_small_caps(format_username(username))
                
                msg += f"👤 {name_small} ({uid})\n"
                msg += f"   🔗 {username_small}\n\n"
            
            if len(all_users) > 50:
                msg += f"... {to_small_caps('and')} {len(all_users) - 50} {to_small_caps('more users')}"
            
            await update.message.reply_text(msg)

        # Back to Main
        elif text == "⬅️ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ":
            await update.message.reply_text(
                f"⬅️ {to_small_caps('Back to Main Menu')}",
                reply_markup=get_main_keyboard(user_id)
            )

        else:
            await update.message.reply_text(
                f"❌ {to_small_caps('Unknown command!')}",
                reply_markup=get_admin_panel_keyboard(user_id)
            )
            
    except Exception as e:
        logger.error(f"Admin button handler error: {e}")
        await update.message.reply_text(f"❌ {to_small_caps('Error:')} {str(e)}")

# ═══════════════════════════════════════════════════════════════════
# PART 5: CALLBACK QUERY HANDLER
# ═══════════════════════════════════════════════════════════════════
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries"""
    try:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        chat_id = query.message.chat.id if query.message else None
        message_id = query.message.message_id if query.message else None
        
        if not chat_id or not message_id:
            logger.error("No chat_id or message_id in callback")
            return
        
        # UNLOCK USER CALLBACK - MAIN FIX
        if data.startswith("unlock_"):
            target_id = int(data.split("_")[1])
            
            if target_id in locked_users:
                del locked_users[target_id]
                save_data()
                
                # Notify the unlocked user
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
                    logger.warning(f"Could not notify unlocked user: {e}")
                
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"✅ {to_small_caps('User')} {target_id} {to_small_caps('has been UNLOCKED successfully!')}"
                )
                logger.info(f"User {target_id} unlocked successfully")
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"⚠️ {to_small_caps('User')} {target_id} {to_small_caps('was not locked!')}"
                )
            return
        
        # REMOVE ADMIN CALLBACK
        if data.startswith("removeadmin_"):
            admin_id = int(data.split("_")[1])
            if admin_id in SUB_ADMINS:
                SUB_ADMINS.remove(admin_id)
                global ADMIN_IDS
                ADMIN_IDS = [PRIMARY_ADMIN_ID] + SUB_ADMINS
                save_data()
                
                # Notify the removed admin
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
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"➖ {to_small_caps('Admin removed:')} {admin_id}"
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ {to_small_caps('User is not an admin!')}"
                )
            return
        
        # Cancel Buttons
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
        
        # Verify Join
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
                chat_id=chat_id,
                message_id=message_id,
                text=f"✅ {to_small_caps('Verification successful! You can now use the bot.')}"
            )
            # Trigger start again
            class FakeUpdate:
                def __init__(self, message, user):
                    self.message = message
                    self.effective_user = user
            fake_msg = type('obj', (object,), {'reply_text': update.message.reply_text if update.message else lambda **kwargs: None})()
            fake_update = FakeUpdate(fake_msg, query.from_user)
            await start(fake_update, context)
            return
        
        # Unblock User
        if data.startswith("unblock_"):
            target_id = int(data.split("_")[1])
            if target_id in blocked_users:
                del blocked_users[target_id]
                save_data()
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"✅ {to_small_caps('User')} {target_id} {to_small_caps('unblocked!')}")
            else:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('User not found!')}")
            return
        
        # Delete Channel
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
        
        # Project Actions
        if not data.startswith(("run_", "stop_", "del_", "manage_", "logs_", "restart_", "livelogs_")):
            logger.warning(f"Unknown callback data: {data}")
            return
        
        parts = data.split('_', 1)
        if len(parts) != 2:
            logger.error(f"Invalid callback data format: {data}")
            return
        
        action, p_name = parts

        if action == "livelogs":
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"📺 {to_small_caps('Starting live logs for')} {p_name}...")
            
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
                logger.error(f"Stop error: {e}")
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
        logger.error(f"Callback error: {e}")
        try:
            if 'chat_id' in locals() and 'message_id' in locals():
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=f"❌ {to_small_caps('An error occurred!')}")
        except:
            pass

# ═══════════════════════════════════════════════════════════════════
# PART 5: RECOVERY SYSTEM
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
        logger.info("🛡️ Advanced recovery system started")
        
        while self.running:
            try:
                await self.check_bot_health(application)
                
                if recovery_enabled:
                    await self.recover_projects()
                
                await self.memory_cleanup()
                
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Recovery loop error: {e}")
                self.consecutive_failures += 1
                if self.consecutive_failures > 5:
                    logger.critical("Too many failures, waiting 60s...")
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
            logger.error(f"Bot health check failed: {e}")
            self.consecutive_failures += 1
            
            if self.consecutive_failures >= 3:
                await self.emergency_restart(application)
    
    async def recover_projects(self):
        for p_name in list(running_processes.keys()):
            try:
                status = get_project_status(p_name)
                
                if status == "crashed":
                    logger.warning(f"Project {p_name} crashed, recovering...")
                    
                    for attempt in range(3):
                        if restart_project(p_name):
                            recovery_stats["total_restarts"] += 1
                            recovery_stats["last_restart"] = time.time()
                            save_data()
                            logger.info(f"✅ {p_name} recovered (attempt {attempt + 1})")
                            break
                        else:
                            logger.error(f"❌ Recovery attempt {attempt + 1} failed for {p_name}")
                            await asyncio.sleep(2)
                    else:
                        self.crash_log.append({
                            "project": p_name,
                            "time": time.time(),
                            "reason": "Max retries exceeded"
                        })
                        
            except Exception as e:
                logger.error(f"Error recovering {p_name}: {e}")
    
    async def memory_cleanup(self):
        try:
            global PSUTIL_AVAILABLE
            if PSUTIL_AVAILABLE:
                import psutil
                mem = psutil.virtual_memory()
                if mem.percent > 90:
                    logger.warning("High memory detected, cleaning up...")
                    for log_file in os.listdir(LOGS_DIR):
                        file_path = os.path.join(LOGS_DIR, log_file)
                        try:
                            if os.path.getsize(file_path) > 10 * 1024 * 1024:
                                with open(file_path, 'w') as f:
                                    f.write(f"Log cleared at {datetime.now()}\n")
                        except:
                            pass
        except Exception as e:
            logger.error(f"Memory cleanup error: {e}")
    
    async def emergency_restart(self, application):
        if self.restart_count >= self.max_restarts:
            logger.critical("Max restarts reached, giving up")
            return
        
        self.restart_count += 1
        logger.critical(f"🚨 Emergency restart #{self.restart_count}")
        
        try:
            await application.stop()
            await asyncio.sleep(3)
            await application.start()
            await application.updater.start_polling(drop_pending_updates=True)
            
            recovery_stats["total_restarts"] += 1
            recovery_stats["last_restart"] = time.time()
            save_data()
            
            logger.info("✅ Emergency restart successful")
            self.consecutive_failures = 0
            
        except Exception as e:
            logger.critical(f"Emergency restart failed: {e}")
    
    def stop(self):
        self.running = False

recovery_system = AdvancedRecovery()

def signal_handler(signum, frame):
    logger.info("Shutdown signal received, stopping recovery...")
    recovery_system.stop()
    save_data()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ═══════════════════════════════════════════════════════════════════
# PART 5: MAIN FUNCTION
# ═══════════════════════════════════════════════════════════════════
def main():
    try:
        # Start web server
        web_thread = Thread(target=run_web, daemon=True)
        web_thread.start()
        logger.info("Web server started")
        
        # Import telegram libraries here (after requirements.txt install)
        try:
            from telegram import ReplyKeyboardMarkup, KeyboardButton, Update, InlineKeyboardButton, InlineKeyboardMarkup
            from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
            logger.info("✅ Telegram libraries imported successfully")
        except ImportError as e:
            logger.error(f"❌ Failed to import telegram libraries: {e}")
            print(f"{Colors.RED}❌ Please install requirements: pip install -r requirements.txt{Colors.END}")
            sys.exit(1)
        
        # Build application
        application = Application.builder().token(TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.Document.ZIP, handle_docs))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(CallbackQueryHandler(button_callback))
        
        logger.info("🚀 Bot started with advanced recovery system!")
        logger.info(f"👑 Owner ID: {PRIMARY_ADMIN_ID}")
        logger.info(f"👥 Sub-admins: {SUB_ADMINS if SUB_ADMINS else 'None'}")
        
        # Start recovery system in background
        async def start_recovery():
            await asyncio.sleep(2)
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
        logger.critical(f"Main error: {e}")
        raise

if __name__ == '__main__':
    main()
