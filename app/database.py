import sqlite3
from contextlib import contextmanager
from datetime import datetime
from app.config import DB_PATH

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

@contextmanager
def db_session():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with db_session() as conn:
        cursor = conn.cursor()

        # Hostels
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS hostels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL UNIQUE,
            total_capacity INTEGER NOT NULL DEFAULT 150,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Rooms
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostel_id INTEGER NOT NULL,
            room_number TEXT NOT NULL,
            floor INTEGER DEFAULT 1,
            capacity INTEGER DEFAULT 2,
            FOREIGN KEY (hostel_id) REFERENCES hostels(id) ON DELETE CASCADE,
            UNIQUE(hostel_id, room_number)
        );
        """)

        # Users / Residents
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            password_hash TEXT NOT NULL,
            hostel_id INTEGER NOT NULL,
            room_id INTEGER,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
            role TEXT NOT NULL DEFAULT 'resident',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hostel_id) REFERENCES hostels(id),
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        );
        """)

        # Admins
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'mess_manager' CHECK (role IN ('superadmin', 'mess_manager', 'staff')),
            hostel_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hostel_id) REFERENCES hostels(id)
        );
        """)

        # Meals
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostel_id INTEGER, -- NULL means all hostels or central mess
            meal_type TEXT NOT NULL CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snacks')),
            meal_date DATE NOT NULL,
            meal_time TEXT NOT NULL,
            menu_items TEXT NOT NULL,
            response_deadline TIMESTAMP NOT NULL,
            notification_time TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'paused', 'cancelled')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hostel_id) REFERENCES hostels(id)
        );
        """)


        # Meal Responses
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS meal_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            response TEXT NOT NULL CHECK (response IN ('will_eat', 'not_eating')),
            responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(meal_id, user_id)
        );
        """)

        # Meal Consumptions (Actual post-meal data)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS meal_consumptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER NOT NULL UNIQUE,
            food_prepared_portions INTEGER NOT NULL,
            actual_eaters INTEGER NOT NULL,
            remaining_portions INTEGER NOT NULL,
            estimated_wasted_portions INTEGER NOT NULL,
            notes TEXT,
            recorded_by TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE
        );
        """)

        # Notifications
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'system',
            action_url TEXT,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)

        # System Settings
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Indexes for fast query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_hostel ON users(hostel_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_meals_date ON meals(meal_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_meals_status ON meals(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_responses_meal_user ON meal_responses(meal_id, user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id, is_read);")
