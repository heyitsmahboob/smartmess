from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse
import json
from app.database import db_session
from app.services.estimation import calculate_meal_requirement
from app.time_utils import (
    ist_now,
    ist_today_str,
    to_iso_ist_string,
    format_time_12h,
    format_deadline_display,
    parse_ist_datetime
)

router = APIRouter(prefix="/api/realtime")

@router.get("/meal-stats")
async def get_live_meal_stats(
    hostel_id: int = Query(None),
    buffer_percent: float = Query(None),
    mode: str = Query(None)
):
    today_str = ist_today_str()
    current_ist = ist_now()

    with db_session() as conn:
        cursor = conn.cursor()

        # Settings defaults if not supplied
        cursor.execute("SELECT key, value FROM system_settings")
        settings = {r["key"]: r["value"] for r in cursor.fetchall()}
        buf = buffer_percent if buffer_percent is not None else float(settings.get("buffer_percentage", 10.0))
        calc_mode = mode if mode else settings.get("estimation_mode", "standard")
        no_resp_ratio = float(settings.get("no_response_ratio", 0.40))

        # Total active population
        if hostel_id:
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE status = 'active' AND hostel_id = ?", (hostel_id,))
        else:
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE status = 'active'")
        total_residents = cursor.fetchone()["count"]

        # Today's meals
        query = """
            SELECT m.id, m.meal_type, m.meal_date, m.meal_time, m.menu_items, m.status, m.response_deadline
            FROM meals m
            WHERE m.meal_date = ? AND m.status != 'cancelled'
        """
        params = [today_str]
        if hostel_id:
            query += " AND (m.hostel_id = ? OR m.hostel_id IS NULL)"
            params.append(hostel_id)
        query += " ORDER BY m.meal_time ASC"

        cursor.execute(query, params)
        meal_rows = cursor.fetchall()

        meals_data = []
        for mr in meal_rows:
            meal = dict(mr)
            meal_id = meal["id"]

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
                buffer_percent=buf,
                mode=calc_mode,
                no_response_ratio=no_resp_ratio
            )

            deadline_dt = parse_ist_datetime(meal["response_deadline"])
            is_locked = (current_ist > deadline_dt) or (meal["status"] in ("closed", "paused"))
            meal["is_locked"] = is_locked
            meal["is_closed"] = (current_ist > deadline_dt) or (meal["status"] == "closed")
            meal["is_paused"] = (meal["status"] == "paused")
            meal["is_closed_early"] = (meal["status"] == "closed" and current_ist <= deadline_dt)
            meal["iso_deadline"] = to_iso_ist_string(deadline_dt)
            meal["deadline_display"] = format_deadline_display(deadline_dt) + " IST"
            meal["time_display"] = format_time_12h(meal["meal_time"])
            meal["stats"] = calc
            meals_data.append(meal)

    return {
        "timestamp_ist": current_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "total_residents": total_residents,
        "buffer_percent": buf,
        "mode": calc_mode,
        "meals": meals_data
    }

@router.get("/student-sync")
async def student_sync_status():
    """Lightweight real-time endpoint for student dashboard to detect admin pause/close/resume actions instantly."""
    today_str = ist_today_str()
    current_ist = ist_now()

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, meal_type, meal_date, meal_time, response_deadline, status
            FROM meals
            WHERE meal_date = ? AND status != 'cancelled'
            ORDER BY meal_time ASC
        """, (today_str,))
        rows = cursor.fetchall()

        meals = []
        for r in rows:
            m = dict(r)
            deadline_dt = parse_ist_datetime(m["response_deadline"])
            is_locked = (current_ist > deadline_dt) or (m["status"] in ("closed", "paused"))
            is_paused = (m["status"] == "paused")
            is_closed_early = (m["status"] == "closed" and current_ist <= deadline_dt)
            is_past_deadline = (current_ist > deadline_dt)

            meals.append({
                "id": m["id"],
                "meal_type": m["meal_type"],
                "status": m["status"],
                "is_locked": is_locked,
                "is_paused": is_paused,
                "is_closed_early": is_closed_early,
                "is_past_deadline": is_past_deadline,
                "deadline_display": format_deadline_display(deadline_dt) + " IST",
                "iso_deadline": to_iso_ist_string(deadline_dt)
            })

    return {
        "timestamp_ist": current_ist.strftime("%I:%M:%S %p IST"),
        "meals": meals
    }
