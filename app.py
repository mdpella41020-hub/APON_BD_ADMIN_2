from flask import Flask, request, jsonify, make_response
import requests
import binascii
import jwt
import urllib3
import json
import base64
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

try:
    import my_pb2
    import output_pb2
except ImportError:
    pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

DEFAULT_REGION = "IND"

# ==================== PROTOBUF DEFINITIONS (Naruto Code) ====================

_sym_db = _symbol_database.Default()

# --- MajorLoginReq protobuf ---
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x13MajorLoginReq.proto\"\xfa\n\n\nMajorLogin\x12\x12\n\nevent_time\x18\x03 \x01(\t\x12\x11\n\tgame_name\x18\x04 \x01(\t\x12\x13\n\x0bplatform_id\x18\x05 \x01(\x05\x12\x16\n\x0e\x63lient_version\x18\x07 \x01(\t\x12\x17\n\x0fsystem_software\x18\x08 \x01(\t\x12\x17\n\x0fsystem_hardware\x18\t \x01(\t\x12\x18\n\x10telecom_operator\x18\n \x01(\t\x12\x14\n\x0cnetwork_type\x18\x0b \x01(\t\x12\x14\n\x0cscreen_width\x18\x0c \x01(\r\x12\x15\n\rscreen_height\x18\r \x01(\r\x12\x12\n\nscreen_dpi\x18\x0e \x01(\t\x12\x19\n\x11processor_details\x18\x0f \x01(\t\x12\x0e\n\x06memory\x18\x10 \x01(\r\x12\x14\n\x0cgpu_renderer\x18\x11 \x01(\t\x12\x13\n\x0bgpu_version\x18\x12 \x01(\t\x12\x18\n\x10unique_device_id\x18\x13 \x01(\t\x12\x11\n\tclient_ip\x18\x14 \x01(\t\x12\x10\n\x08language\x18\x15 \x01(\t\x12\x0f\n\x07open_id\x18\x16 \x01(\t\x12\x14\n\x0copen_id_type\x18\x17 \x01(\t\x12\x13\n\x0b\x64\x65vice_type\x18\x18 \x01(\t\x12\'\n\x10memory_available\x18\x19 \x01(\x0b\x32\r.GameSecurity\x12\x14\n\x0c\x61\x63\x63\x65ss_token\x18\x1d \x01(\t\x12\x17\n\x0fplatform_sdk_id\x18\x1e \x01(\x05\x12\x1a\n\x12network_operator_a\x18) \x01(\t\x12\x16\n\x0enetwork_type_a\x18* \x01(\t\x12\x1c\n\x14\x63lient_using_version\x18\x39 \x01(\t\x12\x1e\n\x16\x65xternal_storage_total\x18< \x01(\x05\x12\"\n\x1a\x65xternal_storage_available\x18= \x01(\x05\x12\x1e\n\x16internal_storage_total\x18> \x01(\x05\x12\"\n\x1ainternal_storage_available\x18? \x01(\x05\x12#\n\x1bgame_disk_storage_available\x18@ \x01(\x05\x12\x1f\n\x17game_disk_storage_total\x18\x41 \x01(\x05\x12%\n\x1d\x65xternal_sdcard_avail_storage\x18\x42 \x01(\x05\x12%\n\x1d\x65xternal_sdcard_total_storage\x18\x43 \x01(\x05\x12\x10\n\x08login_by\x18I \x01(\x05\x12\x14\n\x0clibrary_path\x18J \x01(\t\x12\x12\n\nreg_avatar\x18L \x01(\x05\x12\x15\n\rlibrary_token\x18M \x01(\t\x12\x14\n\x0c\x63hannel_type\x18N \x01(\x05\x12\x10\n\x08\x63pu_type\x18O \x01(\x05\x12\x18\n\x10\x63pu_architecture\x18Q \x01(\t\x12\x1b\n\x13\x63lient_version_code\x18S \x01(\t\x12\x14\n\x0cgraphics_api\x18V \x01(\t\x12\x1d\n\x15supported_astc_bitset\x18W \x01(\r\x12\x1a\n\x12login_open_id_type\x18X \x01(\x05\x12\x18\n\x10\x61nalytics_detail\x18Y \x01(\x0c\x12\x14\n\x0cloading_time\x18\\ \x01(\r\x12\x17\n\x0frelease_channel\x18] \x01(\t\x12\x12\n\nextra_info\x18^ \x01(\t\x12 \n\x18\x61ndroid_engine_init_flag\x18_ \x01(\r\x12\x0f\n\x07if_push\x18\x61 \x01(\x05\x12\x0e\n\x06is_vpn\x18\x62 \x01(\x05\x12\x1c\n\x14origin_platform_type\x18\x63 \x01(\t\x12\x1d\n\x15primary_platform_type\x18\x64 \x01(\t\"5\n\x0cGameSecurity\x12\x0f\n\x07version\x18\x06 \x01(\x05\x12\x14\n\x0chidden_value\x18\x08 \x01(\x04\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'MajorLoginReq_pb2', _globals)
MajorLogin = _globals['MajorLogin']
GameSecurity = _globals['GameSecurity']

# --- MajorLoginRes protobuf ---
DESCRIPTOR2 = _descriptor_pool.Default().AddSerializedFile(b'\n\x13MajorLoginRes.proto\"|\n\rMajorLoginRes\x12\x13\n\x0b\x61\x63\x63ount_uid\x18\x01 \x01(\x04\x12\x0e\n\x06region\x18\x02 \x01(\t\x12\r\n\x05token\x18\x08 \x01(\t\x12\x0b\n\x03url\x18\n \x01(\t\x12\x11\n\ttimestamp\x18\x15 \x01(\x03\x12\x0b\n\x03key\x18\x16 \x01(\x0c\x12\n\n\x02iv\x18\x17 \x01(\x0c\x62\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR2, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR2, 'MajorLoginRes_pb2', _globals)
MajorLoginRes = _globals['MajorLoginRes']

# ==================== AES CONSTANTS ====================

AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

def encrypt_data(data_bytes):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    padded = pad(data_bytes, AES.block_size)
    return cipher.encrypt(padded)

# ==================== ACCESS TOKEN -> JWT (Naruto Method) ====================

def get_jwt_from_access_token(access_token):
    """Convert access token to JWT using Major Login"""
    try:
        # Step 1: Get open_id from token inspect endpoint
        inspect_url = f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}"
        insp_resp = requests.get(inspect_url, timeout=10)
        
        if insp_resp.status_code != 200:
            return None, None, None
        
        insp_data = insp_resp.json()
        open_id = insp_data.get('open_id')
        
        if not open_id:
            return None, None, None
        
        # Step 2: Try different platform types
        platform_types = [2, 3, 4, 6, 8]
        
        for pt in platform_types:
            try:
                # Build Major Login request
                major = MajorLogin()
                major.event_time = "2025-03-23 12:00:00"
                major.game_name = "free fire"
                major.platform_id = 1
                major.client_version = "1.123.1"
                major.system_software = "Android OS 9 / API-28 (PQ3B.190801.10101846/G9650ZHU2ARC6)"
                major.system_hardware = "Handheld"
                major.telecom_operator = "Verizon"
                major.network_type = "WIFI"
                major.screen_width = 1920
                major.screen_height = 1080
                major.screen_dpi = "280"
                major.processor_details = "ARM64 FP ASIMD AES VMH | 2865 | 4"
                major.memory = 3003
                major.gpu_renderer = "Adreno (TM) 640"
                major.gpu_version = "OpenGL ES 3.1 v1.46"
                major.unique_device_id = "Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57"
                major.client_ip = "223.191.51.89"
                major.language = "en"
                major.open_id = open_id
                major.open_id_type = "4"
                major.device_type = "Handheld"
                major.memory_available.version = 55
                major.memory_available.hidden_value = 81
                major.access_token = access_token
                major.platform_sdk_id = 1
                major.network_operator_a = "Verizon"
                major.network_type_a = "WIFI"
                major.client_using_version = "7428b253defc164018c604a1ebbfebdf"
                major.external_storage_total = 36235
                major.external_storage_available = 31335
                major.internal_storage_total = 2519
                major.internal_storage_available = 703
                major.game_disk_storage_available = 25010
                major.game_disk_storage_total = 26628
                major.external_sdcard_avail_storage = 32992
                major.external_sdcard_total_storage = 36235
                major.login_by = 3
                major.library_path = "/data/app/com.dts.freefireth-YPKM8jHEwAJlhpmhDhv5MQ==/lib/arm64"
                major.reg_avatar = 1
                major.library_token = "5b892aaabd688e571f688053118a162b|/data/app/com.dts.freefireth-YPKM8jHEwAJlhpmhDhv5MQ==/base.apk"
                major.channel_type = 3
                major.cpu_type = 2
                major.cpu_architecture = "64"
                major.client_version_code = "2019118695"
                major.graphics_api = "OpenGLES2"
                major.supported_astc_bitset = 16383
                major.login_open_id_type = 4
                major.analytics_detail = b"FwQVTgUPX1UaUllDDwcWCRBpWA0FUgsvA1snWlBaO1kFYg=="
                major.loading_time = 13564
                major.release_channel = "android"
                major.extra_info = "KqsHTymw5/5GB23YGniUYN2/q47GATrq7eFeRatf0NkwLKEMQ0PK5BKEk72dPflAxUlEBir6Vtey83XqF593qsl8hwY="
                major.android_engine_init_flag = 110009
                major.if_push = 1
                major.is_vpn = 1
                major.origin_platform_type = str(pt)
                major.primary_platform_type = str(pt)
                
                payload = major.SerializeToString()
                encrypted_payload = encrypt_data(payload)
                
                url = "https://loginbp.ggblueshark.com/MajorLogin"
                headers = {
                    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; ASUS_Z01QD Build/PI)",
                    "Connection": "Keep-Alive",
                    "Accept-Encoding": "gzip",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Unity-Version": "2018.4.11f1",
                    "X-GA": "v1 1",
                    "ReleaseVersion": "OB53"
                }
                
                resp = requests.post(url, data=encrypted_payload, headers=headers, verify=False, timeout=10)
                
                if resp.status_code == 200:
                    major_res = MajorLoginRes()
                    major_res.ParseFromString(resp.content)
                    if major_res.token:
                        return major_res.token, str(major_res.account_uid), major_res.region
            except Exception as e:
                continue
        
        return None, None, None
        
    except Exception as e:
        return None, None, None

# ==================== REGION CONFIGURATION ====================

MIDDLE_EAST_REGIONS = [
    "EUROPE", "MIDDLEEAST", "MIDDLE_EAST", "ME", "DUBAI", "UAE", "SAUDI",
    "SAUDIARABIA", "KSA", "EGYPT", "EG", "TURKEY", "TR", "IRAQ", "IQ",
    "QATAR", "QA", "KUWAIT", "KW", "OMAN", "OM", "BAHRAIN", "BH", "PAKISTAN", "PK"
]

REGION_ALIASES = {
    "EUROPE": "ME", "MIDDLEEAST": "ME", "DUBAI": "ME", "UAE": "ME",
    "SAUDI": "ME", "EGYPT": "ME", "TURKEY": "ME", "PAKISTAN": "ME", "PK": "ME",
    "ASIA": "SG", "SOUTHAMERICA": "BR", "NORTH_AMERICA": "NA"
}

REGION_MAP = {
    "IND": {"update_url": "https://client.ind.freefiremobile.com/UpdateSocialBasicInfo", "major_login_url": "https://loginbp.ggpolarbear.com/MajorLogin"},
    "ME": {"update_url": "https://clientbp.ggblueshark.com/UpdateSocialBasicInfo", "major_login_url": "https://loginbp.ggpolarbear.com/MajorLogin"},
    "BD": {"update_url": "https://clientbp.ggwhitehawk.com/UpdateSocialBasicInfo", "major_login_url": "https://loginbp.ggpolarbear.com/MajorLogin"},
    "PK": {"update_url": "https://clientbp.ggblueshark.com/UpdateSocialBasicInfo", "major_login_url": "https://loginbp.ggpolarbear.com/MajorLogin"},
    "SG": {"update_url": "https://clientbp.ggpolarbear.com/UpdateSocialBasicInfo", "major_login_url": "https://loginbp.ggpolarbear.com/MajorLogin"},
    "BR": {"update_url": "https://client.us.freefiremobile.com/UpdateSocialBasicInfo", "major_login_url": "https://loginbp.ggpolarbear.com/MajorLogin"},
    "NA": {"update_url": "https://client.us.freefiremobile.com/UpdateSocialBasicInfo", "major_login_url": "https://loginbp.ggpolarbear.com/MajorLogin"},
}

FREEFIRE_VERSION = "OB53"
OAUTH_URL = "https://100067.connect.garena.com/oauth/guest/token/grant"

BIO_HEADERS = {
    "Expect": "100-continue",
    "X-Unity-Version": "2018.4.11f1",
    "X-GA": "v1 1",
    "ReleaseVersion": FREEFIRE_VERSION,
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Dalvik/2.1.0 (Linux; Android)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
}

_sym_db = _symbol_database.Default()

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
b'\n\ndata.proto"\xbb\x01\n\x04\x44\x61ta\x12\x0f\n\x07\x66ield_2\x18\x02 \x01(\x05\x12\x1e\n\x07\x66ield_5\x18\x05 \x01(\x0b\x32\r.EmptyMessage\x12\x1e\n\x07\x66ield_6\x18\x06 \x01(\x0b\x32\r.EmptyMessage\x12\x0f\n\x07\x66ield_8\x18\x08 \x01(\t\x12\x0f\n\x07\x66ield_9\x18\t \x01(\x05\x12\x1f\n\x08\x66ield_11\x18\x0b \x01(\x0b\x32\r.EmptyMessage\x12\x1f\n\x08\x66ield_12\x18\x0c \x01(\x0b\x32\r.EmptyMessage"\x0e\n\x0c\x45mptyMessageb\x06proto3'
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'data1_pb2', _globals)

BioData = _sym_db.GetSymbol('Data')
EmptyMessage = _sym_db.GetSymbol('EmptyMessage')


def decode_jwt_full(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        return {
            "uid": str(decoded.get("account_id")),
            "name": decoded.get("nickname"),
            "region": (decoded.get("lock_region") or decoded.get("region") or "").upper(),
            "country": decoded.get("country_code")
        }
    except:
        return None

def map_region(jwt_region):
    if not jwt_region:
        return DEFAULT_REGION
    jwt_region = jwt_region.upper()
    if jwt_region in REGION_MAP:
        return jwt_region
    if jwt_region in REGION_ALIASES:
        return REGION_ALIASES[jwt_region]
    return DEFAULT_REGION

def _add_region_param(url, region):
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q["region"] = region
    return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, urlencode(q), parts.fragment))

def get_region_urls(region):
    region = region.upper() if region else DEFAULT_REGION
    if region not in REGION_MAP:
        region = DEFAULT_REGION
    update_url = _add_region_param(REGION_MAP[region]["update_url"], region)
    return region, update_url

def upload_bio_request(jwt_token, bio_text, update_url):
    try:
        data = BioData()
        data.field_2 = 17
        data.field_5.CopyFrom(EmptyMessage())
        data.field_6.CopyFrom(EmptyMessage())
        data.field_8 = bio_text
        data.field_9 = 1
        data.field_11.CopyFrom(EmptyMessage())
        data.field_12.CopyFrom(EmptyMessage())

        data_bytes = data.SerializeToString()
        encrypted = encrypt_data(data_bytes)

        headers = BIO_HEADERS.copy()
        headers["Authorization"] = f"Bearer {jwt_token}"

        resp = requests.post(update_url, headers=headers, data=encrypted, verify=False)

        status = "✅ Success" if resp.status_code == 200 else "❌ Failed"
        return {
            "status": status,
            "code": resp.status_code,
            "server_response": binascii.hexlify(resp.content).decode()
        }
    except Exception as e:
        return {"status": str(e), "code": 500, "server_response": ""}

# ==================== MAIN ROUTE ====================

@app.route("/bio", methods=["GET", "POST"])
def combined_bio_upload():
    bio = request.args.get("bio") or request.form.get("bio")
    jwt_token = request.args.get("jwt") or request.form.get("jwt")
    uid = request.args.get("uid") or request.form.get("uid")
    password = request.args.get("pass") or request.form.get("pass")
    access_token = request.args.get("access") or request.args.get("access_token") or request.form.get("access") or request.form.get("access_token")

    if not bio:
        return jsonify({"status": "❌ Missing bio"}), 400

    final_jwt = None
    jwt_info = None
    login_method = "Unknown"

    # Direct JWT
    if jwt_token:
        login_method = "Direct JWT"
        final_jwt = jwt_token
        jwt_info = decode_jwt_full(final_jwt)

    # UID + Password (Guest Login + Major Login)
    elif uid and password:
        login_method = "UID/Pass Login"
        payload = {
            'uid': uid, 'password': password, 'response_type': "token",
            'client_type': "2", 'client_secret': "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            'client_id': "100067"
        }
        headers = {'User-Agent': "GarenaMSDK/4.0.19P9(SM-M526B ;Android 13;pt;BR;)"}
        
        try:
            resp = requests.post(OAUTH_URL, data=payload, headers=headers, verify=False)
            data = resp.json()
            acc_token = data.get('access_token')
            open_id = data.get('open_id')
            
            if acc_token and open_id:
                # Try all regions for major login
                for region_code in REGION_MAP.keys():
                    _, major_url = get_region_urls(region_code)
                    # Here you'd call major login with acc_token and open_id
                    pass
        except:
            pass

    # Access Token -> JWT (Naruto Method - Direct Major Login)
    elif access_token:
        login_method = "Access Token -> JWT (Major Login)"
        final_jwt, account_uid, region = get_jwt_from_access_token(access_token)
        
        if final_jwt:
            jwt_info = decode_jwt_full(final_jwt)
            if not jwt_info:
                jwt_info = {"uid": account_uid, "region": region}

    else:
        return jsonify({"status": "❌ Provide JWT, UID/Pass, or Access Token"}), 400

    if not final_jwt:
        return jsonify({"status": "❌ JWT Generation Failed", "code": 500}), 500

    # Upload bio
    jwt_region = jwt_info.get("region") if jwt_info else DEFAULT_REGION
    mapped_region = map_region(jwt_region)
    _, update_url = get_region_urls(mapped_region)
    result = upload_bio_request(final_jwt, bio, update_url)

    response_data = {
        "login_method": login_method,
        "status": result["status"],
        "code": result["code"],
        "bio": bio,
        "uid": jwt_info.get("uid") if jwt_info else None,
        "name": jwt_info.get("name") if jwt_info else None,
        "region_detected": jwt_region,
        "region_used": mapped_region,
        "generated_jwt": final_jwt,
        "server_response": result["server_response"]
    }

    return jsonify(response_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)