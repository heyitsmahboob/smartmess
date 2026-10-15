import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "smartmess.db"

SECRET_KEY = os.environ.get("SECRET_KEY", "smartmess-super-secret-production-key-2026")
COOKIE_NAME = "smartmess_session"
STUDENT_COOKIE_NAME = "smartmess_student_session"
ADMIN_COOKIE_NAME = "smartmess_admin_session"

# Food estimation defaults
DEFAULT_BUFFER_PERCENT = 10.0
DEFAULT_ESTIMATION_MODE = "standard"  # "conservative", "standard", "strict"
DEFAULT_NO_RESPONSE_RATIO = 0.40  # In standard mode, assume 40% of no-response will eat

# Real-world Indian Mess Schedule & Response Deadlines (IST - Asia/Kolkata)
# Standard Indian Hostel meal service and cutoff timings:
REAL_WORLD_INDIAN_MEAL_SCHEDULE = {
    "breakfast": {
        "title": "Breakfast",
        "service_start": "07:30",
        "service_end": "09:30",
        "response_deadline_time": "06:30",  # 6:30 AM (or night before)
        "notification_time": "06:00"
    },
    "lunch": {
        "title": "Lunch",
        "service_start": "12:30",
        "service_end": "14:30",
        "response_deadline_time": "10:00",  # 10:00 AM IST
        "notification_time": "08:30"
    },
    "snacks": {
        "title": "Evening Snacks / High Tea",
        "service_start": "16:30",
        "service_end": "18:00",
        "response_deadline_time": "15:00",  # 3:00 PM IST
        "notification_time": "14:00"
    },
    "dinner": {
        "title": "Dinner",
        "service_start": "19:30",
        "service_end": "21:45",
        "response_deadline_time": "17:00",  # 5:00 PM IST (as specified)
        "notification_time": "15:30"
    }
}
