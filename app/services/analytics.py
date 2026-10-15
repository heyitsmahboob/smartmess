from typing import Dict, Any, List
from datetime import timedelta
from app.database import db_session
from app.time_utils import ist_today_date, ist_today_str

def get_analytics_summary(days: int = 14) -> Dict[str, Any]:
    cutoff_date = (ist_today_date() - timedelta(days=days)).strftime("%Y-%m-%d")

    with db_session() as conn:
        cursor = conn.cursor()

        # 1. Total counts
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE status = 'active'")
        total_active_residents = cursor.fetchone()["count"]

        # 2. Consumption and wastage totals
        cursor.execute("""
            SELECT 
                COUNT(c.id) as recorded_meals,
                COALESCE(SUM(c.food_prepared_portions), 0) as total_prepared,
                COALESCE(SUM(c.actual_eaters), 0) as total_eaters,
                COALESCE(SUM(c.remaining_portions), 0) as total_remaining,
                COALESCE(SUM(c.estimated_wasted_portions), 0) as total_wasted
            FROM meal_consumptions c
            JOIN meals m ON c.meal_id = m.id
            WHERE m.meal_date >= ?
        """, (cutoff_date,))
        totals = dict(cursor.fetchone())

        total_prepared = totals["total_prepared"]
        total_eaters = totals["total_eaters"]
        total_wasted = totals["total_wasted"]

        avg_wastage_rate = round((total_wasted / total_prepared * 100), 1) if total_prepared > 0 else 0.0

        # Portions saved: If hostel cooked for total capacity vs total_prepared
        recorded_meals = totals["recorded_meals"]
        potential_cooking = total_active_residents * recorded_meals
        portions_saved = max(0, potential_cooking - total_prepared)
        # Cost saving @ ₹55 per meal serving
        estimated_cost_saved_inr = portions_saved * 55

        # 3. Overall response rate across recent meals
        cursor.execute("""
            SELECT 
                m.id, m.meal_date, m.meal_type,
                (SELECT COUNT(*) FROM meal_responses r WHERE r.meal_id = m.id) as responses_count
            FROM meals m
            WHERE m.status != 'cancelled'
              AND m.meal_date >= ?
            ORDER BY m.meal_date ASC, m.meal_time ASC
        """, (cutoff_date,))
        recent_meals = cursor.fetchall()

        total_possible_responses = len(recent_meals) * total_active_residents
        total_actual_responses = sum(r["responses_count"] for r in recent_meals)
        avg_response_rate = round((total_actual_responses / total_possible_responses * 100), 1) if total_possible_responses > 0 else 0.0

        # 4. Expected vs Actual chart data (last 10 completed meals)
        cursor.execute("""
            SELECT 
                m.meal_date, m.meal_type,
                c.food_prepared_portions, c.actual_eaters, c.estimated_wasted_portions,
                (SELECT COUNT(*) FROM meal_responses r WHERE r.meal_id = m.id AND r.response = 'will_eat') as confirmed_eaters
            FROM meal_consumptions c
            JOIN meals m ON c.meal_id = m.id
            ORDER BY m.meal_date DESC, m.meal_time DESC
            LIMIT 10
        """)
        consumption_rows = cursor.fetchall()
        consumption_history = [dict(r) for r in reversed(consumption_rows)]

        # 5. Wastage trend by date (daily wastage)
        cursor.execute("""
            SELECT 
                m.meal_date,
                SUM(c.estimated_wasted_portions) as daily_wasted,
                SUM(c.food_prepared_portions) as daily_prepared,
                SUM(c.actual_eaters) as daily_eaters
            FROM meal_consumptions c
            JOIN meals m ON c.meal_id = m.id
            WHERE m.meal_date >= ?
            GROUP BY m.meal_date
            ORDER BY m.meal_date ASC
        """, (cutoff_date,))
        daily_trend = [dict(r) for r in cursor.fetchall()]

        # 6. Meal-wise participation (Breakfast vs Lunch vs Dinner averages)
        cursor.execute("""
            SELECT 
                m.meal_type,
                COUNT(c.id) as meals_count,
                ROUND(AVG(c.actual_eaters), 1) as avg_eaters,
                ROUND(AVG(c.food_prepared_portions), 1) as avg_prepared,
                ROUND(AVG(c.estimated_wasted_portions), 1) as avg_wasted
            FROM meal_consumptions c
            JOIN meals m ON c.meal_id = m.id
            GROUP BY m.meal_type
        """)
        meal_type_stats = [dict(r) for r in cursor.fetchall()]

        return {
            "total_active_residents": total_active_residents,
            "recorded_meals": recorded_meals,
            "total_prepared": total_prepared,
            "total_eaters": total_eaters,
            "total_wasted": total_wasted,
            "avg_wastage_rate": avg_wastage_rate,
            "portions_saved": portions_saved,
            "estimated_cost_saved_inr": estimated_cost_saved_inr,
            "avg_response_rate": avg_response_rate,
            "consumption_history": consumption_history,
            "daily_trend": daily_trend,
            "meal_type_stats": meal_type_stats
        }
