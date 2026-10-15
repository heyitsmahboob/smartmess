from fastapi import APIRouter, Request, HTTPException, status, Form, Query, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from datetime import timedelta
from typing import Optional
from app.auth import get_current_user_from_request, hash_password
from app.database import db_session
from app.services.estimation import calculate_meal_requirement
from app.services.analytics import get_analytics_summary
from app.services.report_export import generate_consumption_report_data, export_report_to_csv
from app.services.notification import notification_service
from app.common import render_template
from app.time_utils import (
    ist_now,
    ist_today_str,
    ist_now_str,
    parse_ist_datetime,
    to_iso_ist_string,
    format_time_12h,
    format_deadline_display
)

router = APIRouter(prefix="/admin")

def require_admin(request: Request):
    user = get_current_user_from_request(request)
    if not user or not user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"}
        )
    return user

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    hostel_id: Optional[int] = Query(None),
    date_str: Optional[str] = Query(None)
):
    try:
        admin = require_admin(request)
    except HTTPException as e:
        return RedirectResponse(e.headers.get("Location", "/admin/login"))

    today_str = date_str or ist_today_str()
    current_ist = ist_now()

    with db_session() as conn:
        cursor = conn.cursor()

        # Hostels list for filter
        cursor.execute("SELECT id, name, code, total_capacity FROM hostels ORDER BY name ASC")
        hostels = [dict(h) for h in cursor.fetchall()]

        # Active settings
        cursor.execute("SELECT key, value FROM system_settings")
        settings_map = {row["key"]: row["value"] for row in cursor.fetchall()}
        buffer_percent = float(settings_map.get("buffer_percentage", 10.0))
        estimation_mode = settings_map.get("estimation_mode", "standard")
        no_response_ratio = float(settings_map.get("no_response_ratio", 0.40))

        # Total active population (filtered by hostel if specified)
        if hostel_id:
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE status = 'active' AND hostel_id = ?", (hostel_id,))
        else:
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE status = 'active'")
        total_residents = cursor.fetchone()["count"]

        # Meals for requested date
        query = """
            SELECT m.id, m.hostel_id, m.meal_type, m.meal_date, m.meal_time, m.menu_items,
                   m.response_deadline, m.status, h.name as hostel_name
            FROM meals m
            LEFT JOIN hostels h ON m.hostel_id = h.id
            WHERE m.meal_date = ? AND m.status != 'cancelled'
        """
        params = [today_str]
        if hostel_id:
            query += " AND (m.hostel_id = ? OR m.hostel_id IS NULL)"
            params.append(hostel_id)
        query += " ORDER BY m.meal_time ASC"

        cursor.execute(query, params)
        meal_rows = cursor.fetchall()

        meal_summaries = []

        for mr in meal_rows:
            meal = dict(mr)
            meal_id = meal["id"]

            # Count responses
            if hostel_id:
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN r.response = 'will_eat' THEN 1 ELSE 0 END) as will_eat,
                        SUM(CASE WHEN r.response = 'not_eating' THEN 1 ELSE 0 END) as not_eating
                    FROM meal_responses r
                    JOIN users u ON r.user_id = u.id
                    WHERE r.meal_id = ? AND u.hostel_id = ? AND u.status = 'active'
                """, (meal_id, hostel_id))
            else:
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN r.response = 'will_eat' THEN 1 ELSE 0 END) as will_eat,
                        SUM(CASE WHEN r.response = 'not_eating' THEN 1 ELSE 0 END) as not_eating
                    FROM meal_responses r
                    JOIN users u ON r.user_id = u.id
                    WHERE r.meal_id = ? AND u.status = 'active'
                """, (meal_id,))
            
            resp_counts = cursor.fetchone()
            will_eat = resp_counts["will_eat"] or 0
            not_eating = resp_counts["not_eating"] or 0
            no_response = max(0, total_residents - (will_eat + not_eating))

            calc = calculate_meal_requirement(
                confirmed_eating=will_eat,
                confirmed_not_eating=not_eating,
                no_response=no_response,
                buffer_percent=buffer_percent,
                mode=estimation_mode,
                no_response_ratio=no_response_ratio
            )

            meal["calc"] = calc
            meal["will_eat"] = will_eat
            meal["not_eating"] = not_eating
            meal["no_response"] = no_response
            meal["response_rate"] = calc["response_rate"]
            meal["recommended_servings"] = calc["recommended_servings"]
            meal["formula_display"] = calc["formula_display"]

            # Deadline status check in IST
            deadline_dt = parse_ist_datetime(meal["response_deadline"])
            meal["is_closed"] = (current_ist > deadline_dt) or (meal["status"] == "closed")
            meal["deadline_display"] = format_deadline_display(deadline_dt) + " IST"
            meal["time_display"] = format_time_12h(meal["meal_time"])

            # Check if consumption recorded
            cursor.execute("SELECT id, food_prepared_portions, actual_eaters, estimated_wasted_portions FROM meal_consumptions WHERE meal_id = ?", (meal_id,))
            consumption = cursor.fetchone()
            meal["consumption"] = dict(consumption) if consumption else None

            meal_summaries.append(meal)

        # Quick stats
        total_portions_recommended = sum(m["recommended_servings"] for m in meal_summaries)
        avg_response_rate = round(sum(m["response_rate"] for m in meal_summaries) / len(meal_summaries), 1) if meal_summaries else 0.0

    return render_template(request, "admin/dashboard.html", {
        "user": admin,
        "admin": admin,
        "hostels": hostels,
        "selected_hostel_id": hostel_id,
        "selected_date": today_str,
        "current_time_ist": current_ist.strftime("%I:%M %p IST"),
        "total_residents": total_residents,
        "buffer_percent": buffer_percent,
        "estimation_mode": estimation_mode,
        "meal_summaries": meal_summaries,
        "total_portions_recommended": total_portions_recommended,
        "avg_response_rate": avg_response_rate
    })

@router.post("/api/settings")
async def update_settings(
    request: Request,
    buffer_percentage: Optional[float] = Form(None),
    estimation_mode: Optional[str] = Form(None),
    no_response_ratio: Optional[float] = Form(None)
):
    require_admin(request)
    now_ist_str = ist_now_str()
    with db_session() as conn:
        cursor = conn.cursor()
        if buffer_percentage is not None:
            cursor.execute("INSERT OR REPLACE INTO system_settings (key, value, updated_at) VALUES ('buffer_percentage', ?, ?)", (str(buffer_percentage), now_ist_str))
        if estimation_mode is not None and estimation_mode in ("conservative", "standard", "strict"):
            cursor.execute("INSERT OR REPLACE INTO system_settings (key, value, updated_at) VALUES ('estimation_mode', ?, ?)", (estimation_mode, now_ist_str))
        if no_response_ratio is not None:
            cursor.execute("INSERT OR REPLACE INTO system_settings (key, value, updated_at) VALUES ('no_response_ratio', ?, ?)", (str(no_response_ratio), now_ist_str))

    return {"success": True, "message": "Settings updated successfully"}

@router.get("/meals", response_class=HTMLResponse)
async def admin_meals(request: Request, hostel_id: Optional[int] = Query(None)):
    try:
        admin = require_admin(request)
    except HTTPException as e:
        return RedirectResponse(e.headers.get("Location", "/admin/login"))

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM hostels ORDER BY name ASC")
        hostels = [dict(h) for h in cursor.fetchall()]

        cursor.execute("""
            SELECT m.id, m.hostel_id, m.meal_type, m.meal_date, m.meal_time, m.menu_items,
                   m.response_deadline, m.status, h.name as hostel_name,
                   (SELECT COUNT(*) FROM meal_responses r WHERE r.meal_id = m.id AND r.response = 'will_eat') as confirmed_eating,
                   (SELECT COUNT(*) FROM meal_responses r WHERE r.meal_id = m.id AND r.response = 'not_eating') as confirmed_not_eating,
                   (SELECT COUNT(*) FROM users WHERE status = 'active') as total_residents
            FROM meals m
            LEFT JOIN hostels h ON m.hostel_id = h.id
            ORDER BY m.meal_date DESC, m.meal_time DESC
            LIMIT 40
        """)
        meals = []
        for r in cursor.fetchall():
            m = dict(r)
            total = m["total_residents"] or 1
            eaters = m["confirmed_eating"] or 0
            non_eaters = m["confirmed_not_eating"] or 0
            m["no_response"] = max(0, total - (eaters + non_eaters))
            m["response_rate"] = round((eaters + non_eaters) / total * 100, 1)
            deadline_dt = parse_ist_datetime(m["response_deadline"])
            m["deadline_display"] = format_deadline_display(deadline_dt) + " IST"
            m["time_display"] = format_time_12h(m["meal_time"])
            meals.append(m)

    return render_template(request, "admin/meals.html", {
        "user": admin,
        "admin": admin,
        "meals": meals,
        "hostels": hostels
    })

@router.post("/meals/create")
async def create_meal(
    request: Request,
    meal_type: str = Form(...),
    meal_date: str = Form(...),
    meal_time: str = Form(...),
    menu_items: str = Form(...),
    response_deadline_time: str = Form(...), # e.g. "17:00"
    hostel_id: Optional[str] = Form(None)
):
    require_admin(request)
    hostel_val = int(hostel_id) if hostel_id and hostel_id.strip() and hostel_id != "all" else None
    deadline_full = f"{meal_date} {response_deadline_time}:00"
    now_ist_str = ist_now_str()

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO meals (hostel_id, meal_type, meal_date, meal_time, menu_items, response_deadline, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
        """, (hostel_val, meal_type.lower(), meal_date, meal_time, menu_items.strip(), deadline_full, now_ist_str, now_ist_str))
        meal_id = cursor.lastrowid

    # Broadcast notification to residents
    notification_service.broadcast_meal_reminder(meal_id, reminder_type="open")

    return RedirectResponse("/admin/meals?created=1", status_code=status.HTTP_302_FOUND)

@router.post("/meals/{meal_id}/status")
async def update_meal_status(
    meal_id: int,
    request: Request,
    status_val: str = Form(...)
):
    require_admin(request)
    if status_val not in ("open", "closed", "paused", "cancelled"):
        raise HTTPException(status_code=400, detail="Invalid status")

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE meals SET status = ?, updated_at = ? WHERE id = ?", (status_val, ist_now_str(), meal_id))
        
        # Fetch meal details to inform residents
        cursor.execute("SELECT meal_type, meal_date FROM meals WHERE id = ?", (meal_id,))
        meal_info = cursor.fetchone()
        if meal_info:
            m_type = meal_info["meal_type"].capitalize()
            if status_val == "paused":
                title = f"⏸️ {m_type} Responses Paused"
                msg = f"Kitchen administration has temporarily paused response submissions for {m_type}."
            elif status_val == "closed":
                title = f"🔒 {m_type} Responses Closed"
                msg = f"Response window for {m_type} on {meal_info['meal_date']} has been closed by Mess Admin."
            elif status_val == "open":
                title = f"▶️ {m_type} Responses Active"
                msg = f"Response window for {m_type} is now open. Please confirm if you will eat."
            else:
                title = f"❌ {m_type} Meal Cancelled"
                msg = f"{m_type} for {meal_info['meal_date']} has been cancelled."

            # Broadcast alert to all active residents
            cursor.execute("SELECT id FROM users WHERE status = 'active'")
            for u in cursor.fetchall():
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, type, action_url)
                    VALUES (?, ?, ?, 'system', '/dashboard')
                """, (u["id"], title, msg))

    return RedirectResponse("/admin/meals", status_code=status.HTTP_302_FOUND)


@router.post("/meals/{meal_id}/notify")
async def trigger_meal_notification(meal_id: int, request: Request):
    require_admin(request)
    count = notification_service.broadcast_meal_reminder(meal_id, reminder_type="deadline_approaching")
    return JSONResponse({"success": True, "count": count, "message": f"Broadcasted reminder to {count} unresponded residents."})

@router.get("/consumption", response_class=HTMLResponse)
async def admin_consumption(request: Request):
    try:
        admin = require_admin(request)
    except HTTPException as e:
        return RedirectResponse(e.headers.get("Location", "/admin/login"))

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.meal_type, m.meal_date, m.meal_time, m.menu_items,
                   c.id as consumption_id, c.food_prepared_portions, c.actual_eaters,
                   c.remaining_portions, c.estimated_wasted_portions, c.notes,
                   (SELECT COUNT(*) FROM meal_responses r WHERE r.meal_id = m.id AND r.response = 'will_eat') as confirmed_eating
            FROM meals m
            LEFT JOIN meal_consumptions c ON m.id = c.meal_id
            WHERE m.status != 'cancelled'
            ORDER BY m.meal_date DESC, m.meal_time DESC
            LIMIT 30
        """)
        meals_with_consumption = []
        for r in cursor.fetchall():
            d = dict(r)
            d["time_display"] = format_time_12h(d["meal_time"])
            meals_with_consumption.append(d)

    return render_template(request, "admin/consumption.html", {
        "user": admin,
        "admin": admin,
        "meals": meals_with_consumption
    })

@router.post("/consumption/save")
async def save_consumption(
    request: Request,
    meal_id: int = Form(...),
    food_prepared_portions: int = Form(...),
    actual_eaters: int = Form(...),
    remaining_portions: int = Form(...),
    notes: Optional[str] = Form(None)
):
    admin = require_admin(request)
    wasted = max(0, food_prepared_portions - actual_eaters)
    now_ist_str = ist_now_str()

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO meal_consumptions (
                meal_id, food_prepared_portions, actual_eaters,
                remaining_portions, estimated_wasted_portions, notes, recorded_by, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(meal_id) DO UPDATE SET
                food_prepared_portions = excluded.food_prepared_portions,
                actual_eaters = excluded.actual_eaters,
                remaining_portions = excluded.remaining_portions,
                estimated_wasted_portions = excluded.estimated_wasted_portions,
                notes = excluded.notes,
                recorded_by = excluded.recorded_by,
                recorded_at = excluded.recorded_at
        """, (meal_id, food_prepared_portions, actual_eaters, remaining_portions, wasted, notes or "", admin["full_name"], now_ist_str))

        # Only mark meal closed if its response deadline has passed or it was already scheduled
        cursor.execute("SELECT response_deadline FROM meals WHERE id = ?", (meal_id,))
        m_row = cursor.fetchone()
        if m_row:
            d_dt = parse_ist_datetime(m_row["response_deadline"])
            if ist_now() >= d_dt:
                cursor.execute("UPDATE meals SET status = 'closed', updated_at = ? WHERE id = ?", (now_ist_str, meal_id))


    return RedirectResponse("/admin/consumption?saved=1", status_code=status.HTTP_302_FOUND)

@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    search: Optional[str] = Query(None),
    hostel_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None)
):
    try:
        admin = require_admin(request)
    except HTTPException as e:
        return RedirectResponse(e.headers.get("Location", "/admin/login"))

    today_str = ist_today_str()

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM hostels ORDER BY name ASC")
        hostels = [dict(h) for h in cursor.fetchall()]

        # Find today's latest/current meal
        cursor.execute("SELECT id, meal_type FROM meals WHERE meal_date = ? AND status != 'cancelled' ORDER BY meal_time DESC LIMIT 1", (today_str,))
        latest_meal = cursor.fetchone()
        latest_meal_id = latest_meal["id"] if latest_meal else None
        latest_meal_type = latest_meal["meal_type"].capitalize() if latest_meal else "Dinner"

        query = """
            SELECT u.id, u.student_id, u.full_name, u.email, u.phone, u.status,
                   h.name as hostel_name, r.room_number,
                   resp.response as today_response
            FROM users u
            LEFT JOIN hostels h ON u.hostel_id = h.id
            LEFT JOIN rooms r ON u.room_id = r.id
            LEFT JOIN meal_responses resp ON resp.meal_id = ? AND resp.user_id = u.id
            WHERE 1=1
        """
        params = [latest_meal_id]

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            query += " AND (LOWER(u.full_name) LIKE ? OR LOWER(u.student_id) LIKE ? OR LOWER(u.email) LIKE ?)"
            params.extend([term, term, term])

        if hostel_id:
            query += " AND u.hostel_id = ?"
            params.append(hostel_id)

        if status_filter and status_filter in ("active", "inactive"):
            query += " AND u.status = ?"
            params.append(status_filter)

        query += " ORDER BY u.full_name ASC LIMIT 100"
        cursor.execute(query, params)
        users = [dict(row) for row in cursor.fetchall()]

    return render_template(request, "admin/users.html", {
        "user": admin,
        "admin": admin,
        "users": users,
        "hostels": hostels,
        "search": search,
        "selected_hostel": hostel_id,
        "status_filter": status_filter,
        "latest_meal_type": latest_meal_type
    })

@router.post("/users/create")
async def admin_create_user(
    request: Request,
    student_id: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    hostel_id: int = Form(...),
    room_number: str = Form(...),
    password: str = Form("student123")
):
    require_admin(request)
    now_ist_str = ist_now_str()
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM rooms WHERE hostel_id = ? AND room_number = ?", (hostel_id, room_number.strip()))
        room = cursor.fetchone()
        room_id = room["id"] if room else None
        if not room_id:
            cursor.execute("INSERT INTO rooms (hostel_id, room_number) VALUES (?, ?)", (hostel_id, room_number.strip()))
            room_id = cursor.lastrowid

        pwd_hash = hash_password(password)
        cursor.execute("""
            INSERT INTO users (student_id, full_name, email, phone, password_hash, hostel_id, room_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """, (student_id.strip().upper(), full_name.strip(), email.strip().lower(), phone.strip(), pwd_hash, hostel_id, room_id, now_ist_str, now_ist_str))

    return RedirectResponse("/admin/users?created=1", status_code=status.HTTP_302_FOUND)

@router.post("/users/{user_id}/status")
async def toggle_user_status(user_id: int, request: Request, status_val: str = Form(...)):
    require_admin(request)
    if status_val not in ("active", "inactive"):
        raise HTTPException(status_code=400, detail="Invalid status")
    with db_session() as conn:
        conn.execute("UPDATE users SET status = ?, updated_at = ? WHERE id = ?", (status_val, ist_now_str(), user_id))
    return RedirectResponse("/admin/users", status_code=status.HTTP_302_FOUND)

@router.post("/users/{user_id}/delete")
async def delete_user(user_id: int, request: Request):
    require_admin(request)
    with db_session() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return RedirectResponse("/admin/users", status_code=status.HTTP_302_FOUND)

@router.get("/analytics", response_class=HTMLResponse)
async def admin_analytics(request: Request, days: int = Query(14)):
    try:
        admin = require_admin(request)
    except HTTPException as e:
        return RedirectResponse(e.headers.get("Location", "/admin/login"))

    stats = get_analytics_summary(days=days)

    return render_template(request, "admin/analytics.html", {
        "user": admin,
        "admin": admin,
        "stats": stats,
        "days": days
    })

@router.get("/reports", response_class=HTMLResponse)
async def admin_reports(
    request: Request,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    hostel_id: Optional[int] = Query(None)
):
    try:
        admin = require_admin(request)
    except HTTPException as e:
        return RedirectResponse(e.headers.get("Location", "/admin/login"))

    current_ist = ist_now()
    if not start_date:
        start_date = (current_ist - timedelta(days=14)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = current_ist.strftime("%Y-%m-%d")

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM hostels ORDER BY name ASC")
        hostels = [dict(h) for h in cursor.fetchall()]

    report_data = generate_consumption_report_data(start_date=start_date, end_date=end_date, hostel_id=hostel_id)

    total_prep = sum(r["food_prepared_portions"] or 0 for r in report_data)
    total_ate = sum(r["actual_eaters"] or 0 for r in report_data)
    total_waste = sum(r["estimated_wasted_portions"] or 0 for r in report_data)
    total_saved = sum(r["portions_saved_vs_occupancy"] or 0 for r in report_data)

    return render_template(request, "admin/reports.html", {
        "user": admin,
        "admin": admin,
        "hostels": hostels,
        "report_data": report_data,
        "start_date": start_date,
        "end_date": end_date,
        "selected_hostel": hostel_id,
        "summary": {
            "total_prep": total_prep,
            "total_ate": total_ate,
            "total_waste": total_waste,
            "total_saved": total_saved
        }
    })

@router.get("/reports/csv")
async def download_reports_csv(
    request: Request,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    hostel_id: Optional[int] = Query(None)
):
    require_admin(request)
    report_data = generate_consumption_report_data(start_date=start_date, end_date=end_date, hostel_id=hostel_id)
    csv_content = export_report_to_csv(report_data)

    filename = f"smartmess_report_IST_{start_date or 'all'}_to_{end_date or 'today'}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
