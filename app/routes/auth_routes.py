from fastapi import APIRouter, Request, Response, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth import (
    hash_password,
    verify_password,
    create_session_token,
    get_current_user_from_request,
    get_current_resident_from_request,
    get_current_admin_from_request
)
from app.config import COOKIE_NAME, STUDENT_COOKIE_NAME, ADMIN_COOKIE_NAME
from app.database import db_session
from app.common import render_template

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, success: str = None):
    # Only redirect if already logged in as a resident
    resident = get_current_resident_from_request(request)
    if resident:
        return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    
    return render_template(request, "auth/login.html", {
        "error": error,
        "success": success
    })

@router.post("/login")
async def login_submit(
    request: Request,
    response: Response,
    identifier: str = Form(...),  # email, phone, or student_id
    password: str = Form(...)
):
    identifier_clean = identifier.strip().lower()
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, student_id, full_name, email, phone, password_hash, status, role
            FROM users
            WHERE (LOWER(email) = ? OR LOWER(student_id) = ? OR phone = ?)
        """, (identifier_clean, identifier_clean, identifier.strip()))
        user = cursor.fetchone()

        if not user or not verify_password(password, user["password_hash"]):
            return render_template(request, "auth/login.html", {
                "error": "Invalid email/ID or password. Please try again.",
                "identifier": identifier
            }, status_code=status.HTTP_401_UNAUTHORIZED)

        if user["status"] != "active":
            return render_template(request, "auth/login.html", {
                "error": "Your account has been deactivated by the hostel administration.",
                "identifier": identifier
            }, status_code=status.HTTP_403_FORBIDDEN)

        token = create_session_token({"sub": user["id"], "role": "resident", "name": user["full_name"]})
        redirect_res = RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
        # Dedicated student cookie
        redirect_res.set_cookie(
            key=STUDENT_COOKIE_NAME,
            value=token,
            max_age=7 * 86400,
            httponly=True,
            samesite="lax"
        )
        redirect_res.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=7 * 86400,
            httponly=True,
            samesite="lax"
        )
        return redirect_res

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None):
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, code FROM hostels ORDER BY name ASC")
        hostels = [dict(h) for h in cursor.fetchall()]
        cursor.execute("SELECT id, hostel_id, room_number FROM rooms ORDER BY room_number ASC")
        rooms = [dict(r) for r in cursor.fetchall()]

    return render_template(request, "auth/register.html", {
        "hostels": hostels,
        "rooms": rooms,
        "error": error
    })

@router.post("/register")
async def register_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    student_id: str = Form(...),
    hostel_id: int = Form(...),
    room_number: str = Form(...),
    password: str = Form(...)
):
    with db_session() as conn:
        cursor = conn.cursor()

        # Check existing
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ? OR LOWER(student_id) = ?", 
                       (email.strip().lower(), student_id.strip().lower()))
        if cursor.fetchone():
            cursor.execute("SELECT id, name, code FROM hostels ORDER BY name ASC")
            hostels = [dict(h) for h in cursor.fetchall()]
            return render_template(request, "auth/register.html", {
                "hostels": hostels,
                "error": "A resident with this email or Student ID already exists.",
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "student_id": student_id,
                "hostel_id": hostel_id,
                "room_number": room_number
            }, status_code=status.HTTP_400_BAD_REQUEST)

        # Find or create room
        cursor.execute("SELECT id FROM rooms WHERE hostel_id = ? AND room_number = ?", (hostel_id, room_number.strip()))
        room = cursor.fetchone()
        if room:
            room_id = room["id"]
        else:
            cursor.execute("INSERT INTO rooms (hostel_id, room_number) VALUES (?, ?)", (hostel_id, room_number.strip()))
            room_id = cursor.lastrowid

        pwd_hash = hash_password(password)
        cursor.execute("""
            INSERT INTO users (student_id, full_name, email, phone, password_hash, hostel_id, room_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
        """, (student_id.strip().upper(), full_name.strip(), email.strip().lower(), phone.strip(), pwd_hash, hostel_id, room_id))
        new_user_id = cursor.lastrowid

        # Welcome notification
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type, action_url)
            VALUES (?, 'Welcome to SmartMess!', 'Your resident account is active. Start responding to daily meals to save food.', 'system', '/dashboard')
        """, (new_user_id,))

        token = create_session_token({"sub": new_user_id, "role": "resident", "name": full_name.strip()})
        res = RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
        res.set_cookie(key=STUDENT_COOKIE_NAME, value=token, max_age=7 * 86400, httponly=True, samesite="lax")
        res.set_cookie(key=COOKIE_NAME, value=token, max_age=7 * 86400, httponly=True, samesite="lax")
        return res

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request, success: str = None, error: str = None):
    return render_template(request, "auth/forgot_password.html", {
        "success": success,
        "error": error
    })

@router.post("/forgot-password")
async def forgot_password_submit(
    request: Request,
    email: str = Form(...),
    new_password: str = Form(...)
):
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email.strip().lower(),))
        user = cursor.fetchone()
        if not user:
            return render_template(request, "auth/forgot_password.html", {
                "error": "No resident registered with that email address."
            })
        
        new_hash = hash_password(new_password)
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
        
        return render_template(request, "auth/forgot_password.html", {
            "success": "Your password has been successfully reset! You can now log in."
        })

@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, error: str = None):
    # Only redirect if already logged in as admin
    admin = get_current_admin_from_request(request)
    if admin:
        return RedirectResponse("/admin/dashboard", status_code=status.HTTP_302_FOUND)

    return render_template(request, "auth/admin_login.html", {
        "error": error
    })

@router.post("/admin/login")
async def admin_login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, full_name, email, password_hash, role, hostel_id FROM admins WHERE LOWER(email) = ?", (email.strip().lower(),))
        admin = cursor.fetchone()

        if not admin or not verify_password(password, admin["password_hash"]):
            return render_template(request, "auth/admin_login.html", {
                "error": "Invalid administrative credentials.",
                "email": email
            }, status_code=status.HTTP_401_UNAUTHORIZED)

        token = create_session_token({"sub": admin["id"], "role": "admin", "name": admin["full_name"]})
        res = RedirectResponse("/admin/dashboard", status_code=status.HTTP_302_FOUND)
        # Dedicated admin cookie: DOES NOT overwrite or touch student cookie!
        res.set_cookie(key=ADMIN_COOKIE_NAME, value=token, max_age=7 * 86400, httponly=True, samesite="lax")
        return res

@router.get("/admin/logout")
async def admin_logout(request: Request):
    res = RedirectResponse("/admin/login", status_code=status.HTTP_302_FOUND)
    res.delete_cookie(ADMIN_COOKIE_NAME)
    return res

@router.get("/logout")
async def logout(request: Request):
    # If called from admin area, log out admin
    if request.url.path.startswith("/admin") or request.headers.get("referer", "").endswith("/admin"):
        res = RedirectResponse("/admin/login", status_code=status.HTTP_302_FOUND)
        res.delete_cookie(ADMIN_COOKIE_NAME)
        return res

    # Otherwise log out student resident
    res = RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    res.delete_cookie(STUDENT_COOKIE_NAME)
    res.delete_cookie(COOKIE_NAME)
    return res
