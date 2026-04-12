from flask import Flask, request, jsonify
import sys
import jwt
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import RemoveFriend_Req_pb2
from byte import Encrypt_ID, encrypt_api
import binascii
import data_pb2
import uid_generator_pb2
import my_pb2
import output_pb2
from datetime import datetime
import json
import time
import urllib3
import warnings

# -----------------------------
# Security Warnings Disable
# -----------------------------
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=UserWarning, message="Unverified HTTPS request")

app = Flask(__name__)

# -----------------------------
# AES Configuration
# -----------------------------
AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

def encrypt_message(data_bytes):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(data_bytes, AES.block_size))

def encrypt_message_hex(data_bytes):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    encrypted = cipher.encrypt(pad(data_bytes, AES.block_size))
    return binascii.hexlify(encrypted).decode('utf-8')

# -----------------------------
# Region-based URL Configuration
# -----------------------------
def get_base_url(server_name):
    server_name = server_name.upper()
    if server_name == "IND":
        return "https://client.ind.freefiremobile.com/"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/"
    else:
        return "https://clientbp.ggblueshark.com/"

def get_server_from_token(token):
    """Extract server region from JWT token"""
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        lock_region = decoded.get("lock_region", "IND")
        return lock_region.upper()
    except:
        return "IND"

# -----------------------------
# Retry Decorator with better error handling
# -----------------------------
def retry_operation(max_retries=3, delay=2):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    if result:
                        # Check if result has status
                        if isinstance(result, dict):
                            if result.get('status') == 'success':
                                return result
                            elif result.get('status') == 'failed' and attempt < max_retries - 1:
                                print(f"Attempt {attempt + 1} failed, retrying...")
                                time.sleep(delay)
                                continue
                        return result
                except Exception as e:
                    last_exception = e
                    print(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
            
            return {
                "status": "error",
                "message": f"All {max_retries} attempts failed",
                "error": str(last_exception) if last_exception else "Unknown error"
            }
        return wrapper
    return decorator

# -----------------------------
# TOKEN GENERATION METHODS - FIXED
# -----------------------------

# Method 1: Guest Login (UID + Password) se JWT - IMPROVED
def get_jwt_from_guest(uid, password):
    """Guest login: UID + Password -> JWT Token"""
    try:
        print(f"Attempting guest login for UID: {uid}")
        
        oauth_url = "https://100067.connect.garena.com/oauth/guest/token/grant"
        payload = {
            'uid': uid,
            'password': password,
            'response_type': "token",
            'client_type': "2",
            'client_secret': "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            'client_id': "100067"
        }
        
        headers = {
            'User-Agent': "GarenaMSDK/4.0.19P9(SM-M526B ;Android 13;pt;BR;)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip"
        }

        oauth_response = requests.post(oauth_url, data=payload, headers=headers, timeout=15, verify=False)
        
        print(f"OAuth Response Status: {oauth_response.status_code}")
        
        if oauth_response.status_code != 200:
            return None, f"OAuth failed with status {oauth_response.status_code}"
        
        oauth_data = oauth_response.json()
        print(f"OAuth Response Keys: {oauth_data.keys()}")
        
        if 'access_token' not in oauth_data:
            return None, "OAuth response missing access_token"

        access_token = oauth_data['access_token']
        open_id = oauth_data.get('open_id', '')
        
        print(f"Got access_token: {access_token[:20]}...")
        print(f"Open ID: {open_id}")
        
        # Try platform login with better error handling
        platforms = [4, 2, 1, 3, 5, 6]  # Priority order
        
        for platform_type in platforms:
            print(f"Trying platform {platform_type}...")
            result = platform_login(open_id, access_token, platform_type)
            if result and 'token' in result:
                print(f"Success with platform {platform_type}")
                return result['token'], None
        
        return None, "JWT generation failed on all platforms"

    except Exception as e:
        print(f"Guest login error: {str(e)}")
        return None, str(e)

# Method 2: Access Token se JWT
def get_jwt_from_access_token(access_token):
    """Access Token -> JWT Token"""
    try:
        print(f"Converting access token to JWT...")
        api_url = f"http://217.160.125.125:14965/token?access_token={access_token}"
        
        response = requests.get(api_url, timeout=15, verify=False)
        response.raise_for_status()
        
        data = response.json()
        print(f"Access token API response: {data.keys() if data else 'No data'}")
        
        if data and 'token' in data:
            return data['token'], None
        else:
            return None, "JWT not found in response"
            
    except Exception as e:
        print(f"Access token conversion error: {str(e)}")
        return None, str(e)

# Method 3: External API se JWT
def get_jwt_from_external_api(uid, password):
    """External API: UID + Password -> JWT Token"""
    try:
        print(f"Calling external API for UID: {uid}")
        external_url = f"https://star-jwt-gen.vercel.app/token?uid={uid}&password={password}"
        
        response = requests.get(external_url, timeout=15, verify=False)
        response.raise_for_status()
        
        data = response.json()
        print(f"External API response: {data.keys() if data else 'No data'}")
        
        if data and 'token' in data:
            return data['token'], None
        else:
            return None, "Token not found in response"
            
    except Exception as e:
        print(f"External API error: {str(e)}")
        return None, str(e)

def platform_login(open_id, access_token, platform_type):
    """Platform login to get JWT - FIXED"""
    try:
        game_data = my_pb2.GameData()
        game_data.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game_data.game_name = "free fire"
        game_data.game_version = 1
        game_data.version_code = "1.108.3"
        game_data.os_info = "Android OS 13 / API-33"
        game_data.device_type = "Handheld"
        game_data.network_provider = "Verizon Wireless"
        game_data.connection_type = "WIFI"
        game_data.screen_width = 1080
        game_data.screen_height = 1920
        game_data.dpi = "420"
        game_data.cpu_info = "ARMv8 VFPv3 NEON VMH | 2800 | 8"
        game_data.total_ram = 8192
        game_data.gpu_name = "Adreno 650"
        game_data.gpu_version = "OpenGL ES 3.2"
        game_data.user_id = f"Google|{open_id}"
        game_data.ip_address = "172.190.111.97"
        game_data.language = "en"
        game_data.open_id = open_id
        game_data.access_token = access_token
        game_data.platform_type = platform_type
        game_data.field_99 = str(platform_type)
        game_data.field_100 = str(platform_type)

        serialized_data = game_data.SerializeToString()
        encrypted_data = encrypt_message(serialized_data)
        hex_encrypted_data = binascii.hexlify(encrypted_data).decode('utf-8')

        url = "https://loginbp.ggblueshark.com/MajorLogin"
        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; SM-S918B Build/TP1A)",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/octet-stream",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB53"
        }
        
        edata = bytes.fromhex(hex_encrypted_data)

        response = requests.post(url, data=edata, headers=headers, timeout=15, verify=False)
        
        print(f"Platform {platform_type} login response status: {response.status_code}")
        
        if response.status_code == 200:
            # Try to parse as protobuf first
            try:
                example_msg = output_pb2.Garena_420()
                example_msg.ParseFromString(response.content)
                
                # Check if token exists
                if hasattr(example_msg, 'token') and example_msg.token:
                    print(f"Found token in protobuf response")
                    return {"token": example_msg.token}
                    
            except Exception as e:
                print(f"Protobuf parse error: {e}")
                
            # Try as JSON
            try:
                data_dict = response.json()
                if data_dict and "token" in data_dict:
                    print(f"Found token in JSON response")
                    return {"token": data_dict["token"]}
            except:
                pass
        
        return None

    except Exception as e:
        print(f"Platform {platform_type} login error: {str(e)}")
        return None

# -----------------------------
# Player Info Functions
# -----------------------------
def create_info_protobuf(uid):
    message = uid_generator_pb2.uid_generator()
    message.saturn_ = int(uid)
    message.garena = 1
    return message.SerializeToString()

def get_player_info(target_uid, token, server_name=None):
    """Get detailed player information"""
    try:
        if not server_name:
            server_name = get_server_from_token(token)
            
        protobuf_data = create_info_protobuf(target_uid)
        encrypted_data = encrypt_message_hex(protobuf_data)
        endpoint = get_base_url(server_name) + "GetPlayerPersonalShow"

        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 13; SM-S918B)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB53"
        }

        response = requests.post(endpoint, data=bytes.fromhex(encrypted_data), headers=headers, verify=False, timeout=15)
        
        if response.status_code != 200:
            print(f"Player info failed with status: {response.status_code}")
            return None

        hex_response = response.content.hex()
        binary = bytes.fromhex(hex_response)
        
        info = data_pb2.AccountPersonalShowInfo()
        info.ParseFromString(binary)
        
        return info
    except Exception as e:
        print(f"Error getting player info: {e}")
        return None

def extract_player_info(info_data):
    """Extract player information from protobuf response"""
    if not info_data:
        return None

    basic_info = info_data.basic_info
    return {
        'uid': str(basic_info.account_id),
        'nickname': basic_info.nickname,
        'level': basic_info.level,
        'region': basic_info.region,
        'likes': basic_info.liked,
        'release_version': basic_info.release_version
    }

def decode_author_uid(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        account_id = decoded.get("account_id") or decoded.get("sub")
        print(f"Decoded UID from token: {account_id}")
        return str(account_id) if account_id else None
    except Exception as e:
        print(f"Token decode error: {e}")
        return None

# -----------------------------
# Friend Operations - FIXED with better error handling
# -----------------------------
@retry_operation(max_retries=3, delay=2)
def remove_friend_operation(author_uid, target_uid, token, server_name=None):
    """Remove friend operation"""
    try:
        if not server_name:
            server_name = get_server_from_token(token)
            
        print(f"Removing friend: {target_uid} for author: {author_uid}")
        
        # Get player info first
        player_info = get_player_info(target_uid, token, server_name)
        
        msg = RemoveFriend_Req_pb2.RemoveFriend()
        msg.AuthorUid = int(author_uid)
        msg.TargetUid = int(target_uid)
        encrypted_bytes = encrypt_message(msg.SerializeToString())

        url = get_base_url(server_name) + "RemoveFriend"
        headers = {
            'Authorization': f"Bearer {token}",
            'User-Agent': "Dalvik/2.1.0 (Linux; Android 13)",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB53"
        }

        res = requests.post(url, data=encrypted_bytes, headers=headers, verify=False, timeout=15)
        
        print(f"Remove friend response status: {res.status_code}")
        
        player_data = None
        if player_info:
            player_data = extract_player_info(player_info)
        
        if res.status_code == 200:
            return {
                "status": "success",
                "author_uid": author_uid,
                "nickname": player_data.get('nickname') if player_data else "Unknown",
                "uid": target_uid,
                "level": player_data.get('level') if player_data else 0,
                "likes": player_data.get('likes') if player_data else 0,
                "region": player_data.get('region') if player_data else server_name,
                "release_version": player_data.get('release_version') if player_data else "Unknown",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            return {
                "status": "failed",
                "message": f"HTTP {res.status_code}",
                "response": res.text[:200] if res.text else "No response"
            }

    except Exception as e:
        print(f"Remove friend error: {e}")
        return {
            "status": "failed",
            "message": str(e)
        }

@retry_operation(max_retries=3, delay=2)
def add_friend_operation(author_uid, target_uid, token, server_name=None):
    """Add friend operation"""
    try:
        if not server_name:
            server_name = get_server_from_token(token)
            
        print(f"Adding friend: {target_uid} for author: {author_uid}")
        
        # Get player info first
        player_info = get_player_info(target_uid, token, server_name)
        
        encrypted_id = Encrypt_ID(target_uid)
        payload = f"08a7c4839f1e10{encrypted_id}1801"
        encrypted_payload = encrypt_api(payload)

        url = get_base_url(server_name) + "RequestAddingFriend"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB53",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Dalvik/2.1.0 (Linux; Android 13)"
        }

        r = requests.post(url, headers=headers, data=bytes.fromhex(encrypted_payload), verify=False, timeout=15)
        
        print(f"Add friend response status: {r.status_code}")
        
        player_data = None
        if player_info:
            player_data = extract_player_info(player_info)
        
        if r.status_code == 200:
            return {
                "status": "success",
                "author_uid": author_uid,
                "nickname": player_data.get('nickname') if player_data else "Unknown",
                "uid": target_uid,
                "level": player_data.get('level') if player_data else 0,
                "likes": player_data.get('likes') if player_data else 0,
                "region": player_data.get('region') if player_data else server_name,
                "release_version": player_data.get('release_version') if player_data else "Unknown",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            return {
                "status": "failed",
                "message": f"HTTP {r.status_code}",
                "response": r.text[:200] if r.text else "No response"
            }
        
    except Exception as e:
        print(f"Add friend error: {e}")
        return {
            "status": "failed",
            "message": str(e)
        }

# ============================================
# API ENDPOINTS
# ============================================

# -----------------------------
# GUEST LOGIN ENDPOINTS
# -----------------------------

@app.route('/guest/add_friend', methods=['GET'])
def guest_add_friend():
    """Guest login se friend add"""
    uid = request.args.get('uid')
    password = request.args.get('password')
    friend_uid = request.args.get('friend_uid')
    server_name = request.args.get('server_name', 'IND')

    if not uid or not password or not friend_uid:
        return jsonify({"status": "failed", "message": "Missing uid, password, or friend_uid"}), 400

    # Guest login se JWT generate
    token, error = get_jwt_from_guest(uid, password)
    if error:
        return jsonify({"status": "failed", "message": f"Guest login failed: {error}"}), 400
    
    print(f"Generated JWT: {token[:50]}...")
    
    author_uid = decode_author_uid(token)
    if not author_uid:
        return jsonify({"status": "failed", "message": "Failed to decode token"}), 400
        
    result = add_friend_operation(author_uid, friend_uid, token, server_name)
    result['auth_method'] = 'guest_login'
    return jsonify(result)

@app.route('/guest/remove_friend', methods=['GET'])
def guest_remove_friend():
    """Guest login se friend remove"""
    uid = request.args.get('uid')
    password = request.args.get('password')
    friend_uid = request.args.get('friend_uid')
    server_name = request.args.get('server_name', 'IND')

    if not uid or not password or not friend_uid:
        return jsonify({"status": "failed", "message": "Missing uid, password, or friend_uid"}), 400

    token, error = get_jwt_from_guest(uid, password)
    if error:
        return jsonify({"status": "failed", "message": f"Guest login failed: {error}"}), 400
    
    author_uid = decode_author_uid(token)
    if not author_uid:
        return jsonify({"status": "failed", "message": "Failed to decode token"}), 400
        
    result = remove_friend_operation(author_uid, friend_uid, token, server_name)
    result['auth_method'] = 'guest_login'
    return jsonify(result)

@app.route('/guest/player_info', methods=['GET'])
def guest_player_info():
    """Guest login se player info"""
    uid = request.args.get('uid')
    password = request.args.get('password')
    friend_uid = request.args.get('friend_uid')
    server_name = request.args.get('server_name', 'IND')

    if not uid or not password or not friend_uid:
        return jsonify({"status": "failed", "message": "Missing uid, password, or friend_uid"}), 400

    token, error = get_jwt_from_guest(uid, password)
    if error:
        return jsonify({"status": "failed", "message": f"Guest login failed: {error}"}), 400

    player_info = get_player_info(friend_uid, token, server_name)
    if not player_info:
        return jsonify({"status": "failed", "message": "Info not found"}), 400

    player_data = extract_player_info(player_info)
    player_data.update({
        "status": "success", 
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "auth_method": "guest_login"
    })
    return jsonify(player_data)

# -----------------------------
# ACCESS TOKEN ENDPOINTS
# -----------------------------

@app.route('/access/add_friend', methods=['GET'])
def access_add_friend():
    """Access Token se friend add"""
    access_token = request.args.get('access_token')
    friend_uid = request.args.get('friend_uid')
    server_name = request.args.get('server_name', 'IND')

    if not access_token or not friend_uid:
        return jsonify({"status": "failed", "message": "Missing access_token or friend_uid"}), 400

    jwt_token, error = get_jwt_from_access_token(access_token)
    if error:
        return jsonify({"status": "failed", "message": f"Access token conversion failed: {error}"}), 400
    
    author_uid = decode_author_uid(jwt_token)
    if not author_uid:
        return jsonify({"status": "failed", "message": "Failed to decode token"}), 400
        
    result = add_friend_operation(author_uid, friend_uid, jwt_token, server_name)
    result['auth_method'] = 'access_token'
    return jsonify(result)

@app.route('/access/remove_friend', methods=['GET'])
def access_remove_friend():
    """Access Token se friend remove"""
    access_token = request.args.get('access_token')
    friend_uid = request.args.get('friend_uid')
    server_name = request.args.get('server_name', 'IND')

    if not access_token or not friend_uid:
        return jsonify({"status": "failed", "message": "Missing access_token or friend_uid"}), 400

    jwt_token, error = get_jwt_from_access_token(access_token)
    if error:
        return jsonify({"status": "failed", "message": f"Access token conversion failed: {error}"}), 400
    
    author_uid = decode_author_uid(jwt_token)
    if not author_uid:
        return jsonify({"status": "failed", "message": "Failed to decode token"}), 400
        
    result = remove_friend_operation(author_uid, friend_uid, jwt_token, server_name)
    result['auth_method'] = 'access_token'
    return jsonify(result)

@app.route('/access/player_info', methods=['GET'])
def access_player_info():
    """Access Token se player info"""
    access_token = request.args.get('access_token')
    friend_uid = request.args.get('friend_uid')
    server_name = request.args.get('server_name', 'IND')

    if not access_token or not friend_uid:
        return jsonify({"status": "failed", "message": "Missing access_token or friend_uid"}), 400

    jwt_token, error = get_jwt_from_access_token(access_token)
    if error:
        return jsonify({"status": "failed", "message": f"Access token conversion failed: {error}"}), 400

    player_info = get_player_info(friend_uid, jwt_token, server_name)
    if not player_info:
        return jsonify({"status": "failed", "message": "Info not found"}), 400

    player_data = extract_player_info(player_info)
    player_data.update({
        "status": "success", 
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "auth_method": "access_token"
    })
    return jsonify(player_data)

# -----------------------------
# DIRECT JWT ENDPOINTS
# -----------------------------

@app.route('/jwt/add_friend', methods=['GET', 'POST'])
def jwt_add_friend():
    """Direct JWT Token se friend add"""
    if request.method == 'GET':
        jwt_token = request.args.get('jwt_token')
        friend_uid = request.args.get('friend_uid')
        server_name = request.args.get('server_name', 'IND')
    else:
        data = request.get_json()
        jwt_token = data.get('jwt_token')
        friend_uid = data.get('friend_uid')
        server_name = data.get('server_name', 'IND')

    if not jwt_token or not friend_uid:
        return jsonify({"status": "failed", "message": "Missing jwt_token or friend_uid"}), 400
    
    author_uid = decode_author_uid(jwt_token)
    if not author_uid:
        return jsonify({"status": "failed", "message": "Invalid JWT token"}), 400
        
    result = add_friend_operation(author_uid, friend_uid, jwt_token, server_name)
    result['auth_method'] = 'jwt_token'
    return jsonify(result)

@app.route('/jwt/remove_friend', methods=['GET', 'POST'])
def jwt_remove_friend():
    """Direct JWT Token se friend remove"""
    if request.method == 'GET':
        jwt_token = request.args.get('jwt_token')
        friend_uid = request.args.get('friend_uid')
        server_name = request.args.get('server_name', 'IND')
    else:
        data = request.get_json()
        jwt_token = data.get('jwt_token')
        friend_uid = data.get('friend_uid')
        server_name = data.get('server_name', 'IND')

    if not jwt_token or not friend_uid:
        return jsonify({"status": "failed", "message": "Missing jwt_token or friend_uid"}), 400
    
    author_uid = decode_author_uid(jwt_token)
    if not author_uid:
        return jsonify({"status": "failed", "message": "Invalid JWT token"}), 400
        
    result = remove_friend_operation(author_uid, friend_uid, jwt_token, server_name)
    result['auth_method'] = 'jwt_token'
    return jsonify(result)

@app.route('/jwt/player_info', methods=['GET', 'POST'])
def jwt_player_info():
    """Direct JWT Token se player info"""
    if request.method == 'GET':
        jwt_token = request.args.get('jwt_token')
        friend_uid = request.args.get('friend_uid')
        server_name = request.args.get('server_name', 'IND')
    else:
        data = request.get_json()
        jwt_token = data.get('jwt_token')
        friend_uid = data.get('friend_uid')
        server_name = data.get('server_name', 'IND')

    if not jwt_token or not friend_uid:
        return jsonify({"status": "failed", "message": "Missing jwt_token or friend_uid"}), 400

    player_info = get_player_info(friend_uid, jwt_token, server_name)
    if not player_info:
        return jsonify({"status": "failed", "message": "Info not found"}), 400

    player_data = extract_player_info(player_info)
    player_data.update({
        "status": "success", 
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "auth_method": "jwt_token"
    })
    return jsonify(player_data)

# -----------------------------
# TOKEN GENERATION ENDPOINTS
# -----------------------------

@app.route('/generate/guest', methods=['GET'])
def generate_guest_token():
    """Generate JWT from Guest Login"""
    uid = request.args.get('uid')
    password = request.args.get('password')
    
    if not uid or not password:
        return jsonify({"status": "failed", "message": "Missing uid or password"}), 400
    
    token, error = get_jwt_from_guest(uid, password)
    if error:
        return jsonify({"status": "failed", "message": error}), 400
    
    author_uid = decode_author_uid(token)
    return jsonify({
        "status": "success",
        "token": token,
        "author_uid": author_uid,
        "method": "guest_login"
    })

@app.route('/generate/access', methods=['GET'])
def generate_access_token_jwt():
    """Generate JWT from Access Token"""
    access_token = request.args.get('access_token')
    
    if not access_token:
        return jsonify({"status": "failed", "message": "Missing access_token"}), 400
    
    token, error = get_jwt_from_access_token(access_token)
    if error:
        return jsonify({"status": "failed", "message": error}), 400
    
    author_uid = decode_author_uid(token)
    return jsonify({
        "status": "success",
        "token": token,
        "author_uid": author_uid,
        "method": "access_token_conversion"
    })

@app.route('/generate/external', methods=['GET'])
def generate_external_token():
    """Generate JWT from External API"""
    uid = request.args.get('uid')
    password = request.args.get('password')
    
    if not uid or not password:
        return jsonify({"status": "failed", "message": "Missing uid or password"}), 400
    
    token, error = get_jwt_from_external_api(uid, password)
    if error:
        return jsonify({"status": "failed", "message": error}), 400
    
    author_uid = decode_author_uid(token)
    return jsonify({
        "status": "success",
        "token": token,
        "author_uid": author_uid,
        "method": "external_api"
    })

# -----------------------------
# DEBUG ENDPOINT
# -----------------------------

@app.route('/debug/token', methods=['GET'])
def debug_token():
    """Debug endpoint to check token validity"""
    token = request.args.get('token')
    
    if not token:
        return jsonify({"status": "failed", "message": "Missing token"}), 400
    
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        return jsonify({
            "status": "success",
            "decoded": decoded,
            "account_id": decoded.get("account_id"),
            "lock_region": decoded.get("lock_region")
        })
    except Exception as e:
        return jsonify({
            "status": "failed",
            "error": str(e)
        })

# -----------------------------
# HEALTH CHECK
# -----------------------------

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy", 
        "service": "FreeFire-API",
        "version": "2.0",
        "auth_methods": {
            "guest_login": {
                "description": "Use UID and Password",
                "endpoints": [
                    "/guest/add_friend?uid=xxx&password=xxx&friend_uid=xxx",
                    "/guest/remove_friend?uid=xxx&password=xxx&friend_uid=xxx",
                    "/guest/player_info?uid=xxx&password=xxx&friend_uid=xxx"
                ]
            },
            "access_token": {
                "description": "Use Access Token directly",
                "endpoints": [
                    "/access/add_friend?access_token=xxx&friend_uid=xxx",
                    "/access/remove_friend?access_token=xxx&friend_uid=xxx",
                    "/access/player_info?access_token=xxx&friend_uid=xxx"
                ]
            },
            "jwt_token": {
                "description": "Use JWT Token directly",
                "endpoints": [
                    "/jwt/add_friend?jwt_token=xxx&friend_uid=xxx",
                    "/jwt/remove_friend?jwt_token=xxx&friend_uid=xxx",
                    "/jwt/player_info?jwt_token=xxx&friend_uid=xxx"
                ]
            },
            "token_generation": {
                "endpoints": [
                    "/generate/guest?uid=xxx&password=xxx",
                    "/generate/access?access_token=xxx",
                    "/generate/external?uid=xxx&password=xxx"
                ]
            },
            "debug": {
                "/debug/token?token=xxx": "Check token validity"
            }
        }
    }), 200

# -----------------------------
# Run Server
# ----------------------------

if __name__ == '__main__':
    print("=" * 50)
    print("FreeFire API Server Started")
    print("=" * 50)
    print("Available endpoints:")
    print("  Guest Login: /guest/add_friend?uid=xxx&password=xxx&friend_uid=xxx")
    print("  Access Token: /access/add_friend?access_token=xxx&friend_uid=xxx")
    print("  JWT Token: /jwt/add_friend?jwt_token=xxx&friend_uid=xxx")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
    
# MADEBYAJAY