import csv
import io
from datetime import timedelta
from typing import Dict, Any, List, Optional
from app.database import db_session
from app.time_utils import ist_today_date, ist_today_str

def generate_consumption_report_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    hostel_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    today_dt = ist_today_date()
    if not start_date:
        start_date = (today_dt - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = today_dt.strftime("%Y-%m-%d")

    with db_session() as conn:
        cursor = conn.cursor()

        query = """
            SELECT 
                m.id as meal_id,
                m.meal_date,
                m.meal_type,
                m.menu_items,
                m.status as meal_status,
                h.name as hostel_name,
                c.food_prepared_portions,
                c.actual_eaters,
                c.remaining_portions,
                c.estimated_wasted_portions,
                c.notes,
                c.recorded_at,
                (SELECT COUNT(*) FROM meal_responses r WHERE r.meal_id = m.id AND r.response = 'will_eat') as confirmed_eating,
                (SELECT COUNT(*) FROM meal_responses r WHERE r.meal_id = m.id AND r.response = 'not_eating') as confirmed_not_eating,
                (SELECT COUNT(*) FROM users u WHERE u.status = 'active') as total_residents
            FROM meals m
            LEFT JOIN hostels h ON m.hostel_id = h.id
            LEFT JOIN meal_consumptions c ON m.id = c.meal_id
            WHERE m.meal_date BETWEEN ? AND ?
        """
        params = [start_date, end_date]

        if hostel_id:
            query += " AND (m.hostel_id = ? OR m.hostel_id IS NULL)"
            params.append(hostel_id)

        query += " ORDER BY m.meal_date DESC, m.meal_time DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        report = []
        for r in rows:
            d = dict(r)
            total = d["total_residents"] or 1
            will_eat = d["confirmed_eating"] or 0
            not_eat = d["confirmed_not_eating"] or 0
            no_resp = max(0, total - (will_eat + not_eat))
            d["no_response"] = no_resp
            d["response_rate"] = round(((will_eat + not_eat) / total * 100), 1)

            prep = d["food_prepared_portions"] or 0
            eaters = d["actual_eaters"] or 0
            waste = d["estimated_wasted_portions"] or 0
            d["wastage_rate"] = round((waste / prep * 100), 1) if prep > 0 else 0.0

            d["portions_saved_vs_occupancy"] = max(0, total - prep) if prep > 0 else 0
            report.append(d)

        return report

def export_report_to_csv(data: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Meal ID",
        "Date (IST)",
        "Meal Type",
        "Hostel",
        "Menu Items",
        "Total Residents",
        "Confirmed Will Eat",
        "Confirmed Not Eating",
        "No Response",
        "Response Rate (%)",
        "Portions Prepared",
        "Actual Eaters",
        "Remaining Portions",
        "Wasted Portions",
        "Wastage Rate (%)",
        "Portions Saved vs 100% Occupancy",
        "Notes"
    ])

    for row in data:
        writer.writerow([
            row.get("meal_id", ""),
            row.get("meal_date", ""),
            (row.get("meal_type", "")).capitalize(),
            row.get("hostel_name") or "Central / All Hostels",
            row.get("menu_items", ""),
            row.get("total_residents", 0),
            row.get("confirmed_eating", 0),
            row.get("confirmed_not_eating", 0),
            row.get("no_response", 0),
            f"{row.get('response_rate', 0)}%",
            row.get("food_prepared_portions") or "N/A",
            row.get("actual_eaters") or "N/A",
            row.get("remaining_portions") or "N/A",
            row.get("estimated_wasted_portions") or "N/A",
            f"{row.get('wastage_rate', 0)}%" if row.get("food_prepared_portions") else "N/A",
            row.get("portions_saved_vs_occupancy", 0),
            row.get("notes") or ""
        ])

    return output.getvalue()
