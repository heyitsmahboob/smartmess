from fastapi import APIRouter, Request, HTTPException, status, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from datetime import datetime
from app.auth import get_current_user_from_request, get_current_resident_from_request, get_current_admin_from_request
from app.database import db_session
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

router = APIRouter()

def require_resident(request: Request):
    resident = get_current_resident_from_request(request)
    if not resident:
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": "/login"})
    return resident

@router.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request):
    try:
        user = require_resident(request)
    except HTTPException as e:
        return RedirectResponse(e.headers.get("Location", "/login"))

    today_str = ist_today_str()
    current_ist = ist_now()

    with db_session() as conn:
        cursor = conn.cursor()

        # Unread notifications count
        cursor.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0", (user["id"],))
        unread_notifications = cursor.fetchone()["count"]

        # Today's meals with current user's response
        cursor.execute("""
            SELECT 
                m.id, m.meal_type, m.meal_date, m.meal_time, m.menu_items,
                m.response_deadline, m.status as meal_status,
                r.response as user_response, r.responded_at
            FROM meals m
            LEFT JOIN meal_responses r ON m.id = r.meal_id AND r.user_id = ?
            WHERE m.meal_date = ? AND m.status != 'cancelled'
            ORDER BY m.meal_time ASC
        """, (user["id"], today_str))
        today_meals = []
        for r in cursor.fetchall():
            m = dict(r)
            deadline_dt = parse_ist_datetime(m["response_deadline"])
            is_locked = (current_ist > deadline_dt) or (m["meal_status"] in ("closed", "paused"))
            
            m["is_locked"] = is_locked
            m["is_paused"] = (m["meal_status"] == "paused")
            m["is_closed_early"] = (m["meal_status"] == "closed" and current_ist <= deadline_dt)
            m["deadline_dt"] = deadline_dt
            m["iso_deadline"] = to_iso_ist_string(deadline_dt)
            m["deadline_display"] = format_deadline_display(deadline_dt) + " IST"
            m["time_display"] = format_time_12h(m["meal_time"])
            today_meals.append(m)


        # User stats
        cursor.execute("""
            SELECT COUNT(*) as count FROM meal_responses
            WHERE user_id = ? AND response = 'will_eat'
        """, (user["id"],))
        meals_eaten_count = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT COUNT(*) as count FROM meal_responses
            WHERE user_id = ?
        """, (user["id"],))
        total_responses_count = cursor.fetchone()["count"]

    return render_template(request, "user/dashboard.html", {
        "user": user,
        "today_meals": today_meals,
        "today_str": current_ist.strftime("%A, %B %d, %Y") + " (IST)",
        "current_time_display": current_ist.strftime("%I:%M %p IST"),
        "unread_notifications": unread_notifications,
        "meals_eaten_count": meals_eaten_count,
        "total_responses_count": total_responses_count
    })

@router.get("/my-meals", response_class=HTMLResponse)
async def my_meals_page(request: Request):
    try:
        user = require_resident(request)
    except HTTPException as e:
        return RedirectResponse(e.headers.get("Location", "/login"))

    current_ist = ist_now()
    today_str = ist_today_str()

    with db_session() as conn:
        cursor = conn.cursor()

        # Unread notifications count
        cursor.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0", (user["id"],))
        unread_notifications = cursor.fetchone()["count"]

        # All upcoming and recent meals
        cursor.execute("""
            SELECT 
                m.id, m.meal_type, m.meal_date, m.meal_time, m.menu_items,
                m.response_deadline, m.status as meal_status,
                r.response as user_response, r.responded_at
            FROM meals m
            LEFT JOIN meal_responses r ON m.id = r.meal_id AND r.user_id = ?
            WHERE m.meal_date >= DATE(?, '-2 days') AND m.status != 'cancelled'
            ORDER BY m.meal_date ASC, m.meal_time ASC
            LIMIT 30
        """, (user["id"], today_str))

        meals_by_section = {
            "today": [],
            "tomorrow": [],
            "upcoming": [],
            "past": []
        }

        today_date = current_ist.date()

        for r in cursor.fetchall():
            m = dict(r)
            deadline_dt = parse_ist_datetime(m["response_deadline"])
            is_locked = (current_ist > deadline_dt) or (m["meal_status"] in ("closed", "paused"))

            m["is_locked"] = is_locked
            m["is_paused"] = (m["meal_status"] == "paused")
            m["iso_deadline"] = to_iso_ist_string(deadline_dt)
            m["deadline_display"] = format_deadline_display(deadline_dt) + " IST"
            m["time_display"] = format_time_12h(m["meal_time"])

            
            meal_date_obj = parse_ist_datetime(m["meal_date"]).date()
            m["date_display"] = meal_date_obj.strftime("%a, %b %d")

            if meal_date_obj < today_date:
                meals_by_section["past"].append(m)
            elif meal_date_obj == today_date:
                meals_by_section["today"].append(m)
            elif (meal_date_obj - today_date).days == 1:
                meals_by_section["tomorrow"].append(m)
            else:
                meals_by_section["upcoming"].append(m)

    return render_template(request, "user/my_meals.html", {
        "user": user,
        "meals_by_section": meals_by_section,
        "unread_notifications": unread_notifications
    })

@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    try:
        user = require_resident(request)
    except HTTPException as e:
        return RedirectResponse(e.headers.get("Location", "/login"))

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, message, type, action_url, is_read, created_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        """, (user["id"],))
        notifications = [dict(n) for n in cursor.fetchall()]

        cursor.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0", (user["id"],))
        unread_notifications = cursor.fetchone()["count"]

    return render_template(request, "user/notifications.html", {
        "user": user,
        "notifications": notifications,
        "unread_notifications": unread_notifications
    })

@router.post("/api/meals/{meal_id}/respond")
async def respond_to_meal(
    meal_id: int,
    request: Request,
    payload: dict = Body(...)
):
    user = get_current_resident_from_request(request) or get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    response_choice = payload.get("response")
    if response_choice not in ("will_eat", "not_eating"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid response value. Must be 'will_eat' or 'not_eating'.")

    current_ist = ist_now()
    now_ist_formatted = ist_now_str()

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, meal_type, meal_date, meal_time, response_deadline, status
            FROM meals WHERE id = ?
        """, (meal_id,))
        meal = cursor.fetchone()

        if not meal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal not found")

        if meal["status"] == "cancelled":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This meal has been cancelled.")

        # Business Rule 2 & 3: Check response deadline and active status
        if not user.get("is_admin"):
            deadline_dt = parse_ist_datetime(meal["response_deadline"])
            if meal["status"] == "paused":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Meal responses have been temporarily paused by Mess Admin. Please check back shortly."
                )
            if meal["status"] == "closed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Responses for this meal were closed early by the kitchen administration."
                )
            if current_ist > deadline_dt:
                deadline_str = format_deadline_display(deadline_dt)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Response deadline ({deadline_str} IST) has passed. Responses are locked."
                )


        # Upsert response (Business Rule 1: Single response per meal)
        cursor.execute("""
            INSERT INTO meal_responses (meal_id, user_id, response, responded_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(meal_id, user_id) DO UPDATE SET
                response = excluded.response,
                updated_at = excluded.updated_at
        """, (meal_id, user["id"], response_choice, now_ist_formatted, now_ist_formatted))

        # In-app notification confirmation
        meal_title = meal["meal_type"].capitalize()
        status_text = "confirmed you WILL eat" if response_choice == "will_eat" else "recorded that you will NOT eat"
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type, action_url)
            VALUES (?, ?, ?, 'response_confirmation', '/my-meals')
        """, (user["id"], f"✅ Response Recorded: {meal_title}", f"You have {status_text} for {meal_title} on {meal['meal_date']} (recorded at {current_ist.strftime('%I:%M %p IST')})."))

        # Return updated counts
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM meal_responses WHERE meal_id = ? AND response = 'will_eat') as will_eat,
                (SELECT COUNT(*) FROM meal_responses WHERE meal_id = ? AND response = 'not_eating') as not_eating,
                (SELECT COUNT(*) FROM users WHERE status = 'active') as total_residents
        """, (meal_id, meal_id))
        stats = dict(cursor.fetchone())
        no_response = max(0, stats["total_residents"] - (stats["will_eat"] + stats["not_eating"]))

    return {
        "success": True,
        "meal_id": meal_id,
        "response": response_choice,
        "timestamp_ist": current_ist.strftime("%I:%M %p IST"),
        "message": f"Successfully updated response to: {'Will Eat' if response_choice == 'will_eat' else 'Will NOT Eat'}",
        "stats": {
            "will_eat": stats["will_eat"],
            "not_eating": stats["not_eating"],
            "no_response": no_response,
            "total_residents": stats["total_residents"]
        }
    }

@router.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, request: Request):
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    with db_session() as conn:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notification_id, user["id"]))

    return {"success": True}

@router.post("/api/notifications/read-all")
async def mark_all_notifications_read(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    with db_session() as conn:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user["id"],))

    return {"success": True}
