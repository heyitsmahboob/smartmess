import hashlib
import hmac
import base64
import json
import time
import secrets
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from app.config import SECRET_KEY, COOKIE_NAME, STUDENT_COOKIE_NAME, ADMIN_COOKIE_NAME
from app.database import db_session

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations and random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}:{key.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against salt:key format."""
    try:
        salt, key_hex = hashed.split(":", 1)
        expected_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return hmac.compare_digest(expected_key.hex(), key_hex)
    except Exception:
        return False

def sign_data(data: str) -> str:
    sig = hmac.new(SECRET_KEY.encode('utf-8'), data.encode('utf-8'), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode('utf-8')

def create_session_token(payload: Dict[str, Any], max_age_days: int = 7) -> str:
    payload_copy = payload.copy()
    payload_copy["exp"] = int(time.time()) + (max_age_days * 86400)
    raw = json.dumps(payload_copy, separators=(',', ':'))
    raw_b64 = base64.urlsafe_b64encode(raw.encode('utf-8')).decode('utf-8')
    signature = sign_data(raw_b64)
    return f"{raw_b64}.{signature}"

def decode_session_token(token: str) -> Optional[Dict[str, Any]]:
    if not token or "." not in token:
        return None
    try:
        raw_b64, signature = token.split(".", 1)
        expected_sig = sign_data(raw_b64)
        if not hmac.compare_digest(signature, expected_sig):
            return None
        raw_json = base64.urlsafe_b64decode(raw_b64.encode('utf-8')).decode('utf-8')
        payload = json.loads(raw_json)
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None

def _get_user_from_token(token: Optional[str], expected_role: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    payload = decode_session_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    role = payload.get("role")
    if expected_role and role != expected_role:
        return None

    with db_session() as conn:
        cursor = conn.cursor()
        if role == "admin":
            cursor.execute("SELECT id, full_name, email, role, hostel_id FROM admins WHERE id = ?", (user_id,))
            admin = cursor.fetchone()
            if admin:
                return {
                    "id": admin["id"],
                    "full_name": admin["full_name"],
                    "email": admin["email"],
                    "role": "admin",
                    "admin_role": admin["role"],
                    "hostel_id": admin["hostel_id"],
                    "is_admin": True
                }
        else:
            cursor.execute("""
                SELECT u.id, u.student_id, u.full_name, u.email, u.phone, u.status, u.role,
                       u.hostel_id, u.room_id, h.name as hostel_name, r.room_number
                FROM users u
                LEFT JOIN hostels h ON u.hostel_id = h.id
                LEFT JOIN rooms r ON u.room_id = r.id
                WHERE u.id = ? AND u.status = 'active'
            """, (user_id,))
            user = cursor.fetchone()
            if user:
                return {
                    "id": user["id"],
                    "student_id": user["student_id"],
                    "full_name": user["full_name"],
                    "email": user["email"],
                    "phone": user["phone"],
                    "status": user["status"],
                    "role": "resident",
                    "hostel_id": user["hostel_id"],
                    "room_id": user["room_id"],
                    "hostel_name": user["hostel_name"],
                    "room_number": user["room_number"],
                    "is_admin": False
                }
    return None

def get_current_resident_from_request(request: Request) -> Optional[Dict[str, Any]]:
    # 1. Try student-specific cookie
    token = request.cookies.get(STUDENT_COOKIE_NAME)
    res = _get_user_from_token(token, expected_role="resident")
    if res:
        return res
    # 2. Try legacy cookie if it contains resident
    token = request.cookies.get(COOKIE_NAME)
    res = _get_user_from_token(token, expected_role="resident")
    if res:
        return res
    # 3. Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return _get_user_from_token(auth_header[7:], expected_role="resident")
    return None

def get_current_admin_from_request(request: Request) -> Optional[Dict[str, Any]]:
    # 1. Try admin-specific cookie
    token = request.cookies.get(ADMIN_COOKIE_NAME)
    adm = _get_user_from_token(token, expected_role="admin")
    if adm:
        return adm
    # 2. Try legacy cookie if it contains admin
    token = request.cookies.get(COOKIE_NAME)
    adm = _get_user_from_token(token, expected_role="admin")
    if adm:
        return adm
    # 3. Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return _get_user_from_token(auth_header[7:], expected_role="admin")
    return None

def get_current_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    path = request.url.path
    if path.startswith("/admin"):
        return get_current_admin_from_request(request) or get_current_resident_from_request(request)
    else:
        return get_current_resident_from_request(request) or get_current_admin_from_request(request)
