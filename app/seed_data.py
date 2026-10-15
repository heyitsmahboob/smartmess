import random
from datetime import timedelta
from app.database import db_session, init_db
from app.auth import hash_password
from app.time_utils import ist_now, ist_today_date, ist_today_str, ist_now_str
from app.config import REAL_WORLD_INDIAN_MEAL_SCHEDULE

def seed_database():
    init_db()

    with db_session() as conn:
        cursor = conn.cursor()

        # Check if already seeded
        cursor.execute("SELECT COUNT(*) as count FROM users")
        if cursor.fetchone()["count"] > 0:
            return

        print("Seeding SmartMess database with real-world India Standard Time (IST) schedules...")

        # 1. System Settings
        settings = [
            ("buffer_percentage", "10.0", "Default safety buffer percentage"),
            ("estimation_mode", "standard", "Active calculation mode: conservative, standard, strict"),
            ("no_response_ratio", "0.40", "Expected ratio of unresponded residents who will eat in standard mode"),
            ("cost_per_portion_inr", "55", "Average procurement/prep cost per portion in INR")
        ]
        for key, val, desc in settings:
            cursor.execute("""
                INSERT OR REPLACE INTO system_settings (key, value, description)
                VALUES (?, ?, ?)
            """, (key, val, desc))

        # 2. Hostels
        hostels_data = [
            ("Boys Hostel A", "BHA", 150, "North Campus, Block 1"),
            ("Boys Hostel B", "BHB", 150, "North Campus, Block 2"),
            ("Girls Hostel A", "GHA", 150, "South Campus, Wing A"),
            ("PG Building 1", "PG1", 100, "Executive Campus, Tower 1")
        ]
        hostel_ids = []
        for name, code, cap, addr in hostels_data:
            cursor.execute("""
                INSERT INTO hostels (name, code, total_capacity, address)
                VALUES (?, ?, ?, ?)
            """, (name, code, cap, addr))
            hostel_ids.append(cursor.lastrowid)

        # 3. Rooms for each hostel
        room_ids = []
        for h_id in hostel_ids:
            for floor in [1, 2, 3]:
                for r_num in range(1, 6):
                    room_number = f"{floor}0{r_num}"
                    cursor.execute("""
                        INSERT INTO rooms (hostel_id, room_number, floor, capacity)
                        VALUES (?, ?, ?, 2)
                    """, (h_id, room_number, floor))
                    room_ids.append(cursor.lastrowid)

        # 4. Admins
        admin_pass = hash_password("admin123")
        cursor.execute("""
            INSERT INTO admins (full_name, email, password_hash, role, hostel_id)
            VALUES (?, ?, ?, 'superadmin', NULL)
        """, ("Chief Mess Officer", "admin@smartmess.com", admin_pass))

        cursor.execute("""
            INSERT INTO admins (full_name, email, password_hash, role, hostel_id)
            VALUES (?, ?, ?, 'mess_manager', ?)
        """, ("Ramesh Kumar (Supervisor)", "manager@hostel.edu", admin_pass, hostel_ids[0]))

        # 5. Realistic Residents (75 residents across Indian states)
        first_names = [
            "Arjun", "Priya", "Rahul", "Ananya", "Rohan", "Sneha", "Vikram", "Divya",
            "Tanmay", "Neha", "Aditya", "Pooja", "Karan", "Ishita", "Siddharth", "Meera",
            "Varun", "Riya", "Kavya", "Aman", "Shreya", "Nikhil", "Deepak", "Anjali",
            "Gaurav", "Swati", "Manish", "Bhavna", "Harsh", "Simran", "Pranav", "Tanvi",
            "Abhishek", "Pallavi", "Akash", "Kritika", "Suresh", "Radhika", "Mohit", "Tara"
        ]
        last_names = [
            "Sharma", "Patel", "Verma", "Iyer", "Gupta", "Nair", "Singh", "Rao",
            "Joshi", "Kulkarni", "Deshmukh", "Mehta", "Chopra", "Reddy", "Bose", "Menon",
            "Kapoor", "Chatterjee", "Mishra", "Pandey", "Saxena", "Bhat", "Das", "Pillai"
        ]

        resident_pass = hash_password("student123")
        user_ids = []

        # Primary demo student accounts
        cursor.execute("""
            INSERT INTO users (student_id, full_name, email, phone, password_hash, hostel_id, room_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
        """, ("2024CS001", "Arjun Sharma", "arjun@hostel.edu", "9876543210", resident_pass, hostel_ids[0], room_ids[0]))
        user_ids.append(cursor.lastrowid)

        cursor.execute("""
            INSERT INTO users (student_id, full_name, email, phone, password_hash, hostel_id, room_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
        """, ("2024CS002", "Priya Patel", "priya@hostel.edu", "9876543211", resident_pass, hostel_ids[2], room_ids[30]))
        user_ids.append(cursor.lastrowid)

        # Generate 73 additional residents
        random.seed(42)
        departments = ["CS", "ME", "EC", "EE", "CE", "CH", "BT", "DS"]

        for idx in range(3, 76):
            dept = random.choice(departments)
            student_id = f"2024{dept}{idx:03d}"
            fn = random.choice(first_names)
            ln = random.choice(last_names)
            full_name = f"{fn} {ln}"
            email = f"{fn.lower()}.{ln.lower()}{idx}@hostel.edu"
            phone = f"98{random.randint(10000000, 99999999)}"
            h_id = random.choice(hostel_ids)
            r_id = random.choice(room_ids)

            cursor.execute("""
                INSERT INTO users (student_id, full_name, email, phone, password_hash, hostel_id, room_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            """, (student_id, full_name, email, phone, resident_pass, h_id, r_id))
            user_ids.append(cursor.lastrowid)

        # 6. Indian Hostel Menus (Authentic regional hostel menus)
        menus = {
            "breakfast": [
                "Poha, Boiled Eggs / Banana, Masala Chai, Mint Chutney",
                "Masala Dosa, Sambar, Coconut Chutney, Filter Coffee",
                "Aloo Paratha, Curd, Pickle, Adrak Chai",
                "Idli-Vada, Vegetable Sambar, Tomato Chutney, Tea",
                "Chole Bhature, Onion Salad, Masala Buttermilk",
                "Methi Thepla, Curd, Mango Pickle, Ginger Tea",
                "Upma, Sheera, Chana Masala, Hot Coffee"
            ],
            "lunch": [
                "Steamed Basmati Rice, Yellow Dal Tadka, Aloo Gobhi, Tawa Roti, Salad, Curd",
                "Jeera Rice, Rajma Masala, Bhindi Fry, Phulka, Boondi Raita",
                "Veg Pulao, Paneer Makhani, Mixed Dal, Butter Naan, Gulab Jamun",
                "Rice, Sambar, Rasam, Cabbage Poriyal, Appalam, Curd",
                "Kadhi Pakoda, Khichdi, Papad, Aloo Jeera, Green Salad",
                "Hyderabadi Veg Biryani, Mirchi Ka Salan, Onion Raita, Phirni",
                "Rice, Chana Dal, Baingan Bharta, Chapati, Tomato Cucumber Salad"
            ],
            "dinner": [
                "Steamed Basmati Rice, Dal Tadka, Paneer Butter Masala, Butter Tawa Roti, Green Salad, Gulab Jamun",
                "Tawa Pulao, Palak Paneer, Yellow Moong Dal, Roti, Roasted Papad, Ice Cream",
                "Peas Pulao, Malai Kofta, Mix Veg, Phulka, Boondi Raita, Kheer",
                "Veg Fried Rice, Manchurian Gravy, Hakka Noodles, Spring Roll, Kimchi",
                "Roti, Dal Fry, Kadai Paneer, Jeera Rice, Green Salad, Rasgulla",
                "Khichdi, Kadhi, Gujarati Aloo, Papad, Chaas, Sweet Shrikhand",
                "Biryani, Paneer Tikka Masala, Raita, Garlic Naan, Moong Dal Halwa"
            ]
        }

        # 7. Past 7 days: Meals with Indian timings, consumptions & responses
        today_date = ist_today_date()

        for days_ago in range(7, 0, -1):
            past_date = today_date - timedelta(days=days_ago)
            date_str = past_date.strftime("%Y-%m-%d")

            for m_type in ["breakfast", "lunch", "dinner"]:
                timing_info = REAL_WORLD_INDIAN_MEAL_SCHEDULE[m_type]
                menu = menus[m_type][(past_date.day + len(m_type)) % len(menus[m_type])]
                deadline_dt = f"{date_str} {timing_info['response_deadline_time']}:00"

                cursor.execute("""
                    INSERT INTO meals (meal_type, meal_date, meal_time, menu_items, response_deadline, status)
                    VALUES (?, ?, ?, ?, ?, 'closed')
                """, (m_type, date_str, timing_info["service_start"], menu, deadline_dt))
                meal_id = cursor.lastrowid

                # Responses: ~70-75% will_eat, ~15% not_eating, rest no_response
                confirmed_eating = 0
                for u_id in user_ids:
                    roll = random.random()
                    if roll < 0.72:
                        cursor.execute("""
                            INSERT INTO meal_responses (meal_id, user_id, response, responded_at)
                            VALUES (?, ?, 'will_eat', ?)
                        """, (meal_id, u_id, deadline_dt))
                        confirmed_eating += 1
                    elif roll < 0.88:
                        cursor.execute("""
                            INSERT INTO meal_responses (meal_id, user_id, response, responded_at)
                            VALUES (?, ?, 'not_eating', ?)
                        """, (meal_id, u_id, deadline_dt))

                # Post-meal actual consumption
                prepared = int(confirmed_eating * 1.10)
                variance = random.randint(-4, 2)
                actual_eaters = max(10, confirmed_eating + variance)
                remaining = max(0, prepared - actual_eaters)
                wasted = remaining

                cursor.execute("""
                    INSERT INTO meal_consumptions (
                        meal_id, food_prepared_portions, actual_eaters,
                        remaining_portions, estimated_wasted_portions, notes, recorded_by
                    ) VALUES (?, ?, ?, ?, ?, ?, 'Ramesh Kumar (Supervisor)')
                """, (meal_id, prepared, actual_eaters, remaining, wasted, "Standard meal service concluded"))

        # TODAY'S MEALS IN IST
        today_str = today_date.strftime("%Y-%m-%d")

        # Today Breakfast (Service: 07:30, Deadline: 06:30 IST) -> Completed & Closed
        bf_deadline = f"{today_str} {REAL_WORLD_INDIAN_MEAL_SCHEDULE['breakfast']['response_deadline_time']}:00"
        cursor.execute("""
            INSERT INTO meals (meal_type, meal_date, meal_time, menu_items, response_deadline, status)
            VALUES ('breakfast', ?, ?, ?, ?, 'closed')
        """, (today_str, REAL_WORLD_INDIAN_MEAL_SCHEDULE['breakfast']['service_start'], menus["breakfast"][0], bf_deadline))
        today_bf_id = cursor.lastrowid

        bf_eaters = 0
        for u_id in user_ids:
            roll = random.random()
            if roll < 0.74:
                cursor.execute("INSERT INTO meal_responses (meal_id, user_id, response) VALUES (?, ?, 'will_eat')", (today_bf_id, u_id))
                bf_eaters += 1
            elif roll < 0.90:
                cursor.execute("INSERT INTO meal_responses (meal_id, user_id, response) VALUES (?, ?, 'not_eating')", (today_bf_id, u_id))

        bf_prep = int(bf_eaters * 1.10)
        cursor.execute("""
            INSERT INTO meal_consumptions (
                meal_id, food_prepared_portions, actual_eaters,
                remaining_portions, estimated_wasted_portions, notes, recorded_by
            ) VALUES (?, ?, ?, ?, ?, 'Breakfast concluded smoothly', 'Ramesh Kumar')
        """, (today_bf_id, bf_prep, bf_eaters - 2, 2, 2))

        # Today Lunch (Service: 12:30, Deadline: 10:00 IST) -> Completed & Closed
        lunch_deadline = f"{today_str} {REAL_WORLD_INDIAN_MEAL_SCHEDULE['lunch']['response_deadline_time']}:00"
        cursor.execute("""
            INSERT INTO meals (meal_type, meal_date, meal_time, menu_items, response_deadline, status)
            VALUES ('lunch', ?, ?, ?, ?, 'closed')
        """, (today_str, REAL_WORLD_INDIAN_MEAL_SCHEDULE['lunch']['service_start'], menus["lunch"][0], lunch_deadline))
        today_lunch_id = cursor.lastrowid

        lunch_eaters = 0
        for u_id in user_ids:
            roll = random.random()
            if roll < 0.78:
                cursor.execute("INSERT INTO meal_responses (meal_id, user_id, response) VALUES (?, ?, 'will_eat')", (today_lunch_id, u_id))
                lunch_eaters += 1
            elif roll < 0.92:
                cursor.execute("INSERT INTO meal_responses (meal_id, user_id, response) VALUES (?, ?, 'not_eating')", (today_lunch_id, u_id))

        lunch_prep = int(lunch_eaters * 1.10)
        cursor.execute("""
            INSERT INTO meal_consumptions (
                meal_id, food_prepared_portions, actual_eaters,
                remaining_portions, estimated_wasted_portions, notes, recorded_by
            ) VALUES (?, ?, ?, ?, ?, 'Lunch completed with minimal leftovers', 'Ramesh Kumar')
        """, (today_lunch_id, lunch_prep, lunch_eaters - 3, 3, 3))

        # TODAY'S DINNER (Service: 19:30 [7:30 PM], Deadline: 17:00 [5:00 PM IST])
        # Open and active! Residents are responding right now!
        dinner_deadline = f"{today_str} {REAL_WORLD_INDIAN_MEAL_SCHEDULE['dinner']['response_deadline_time']}:00"
        cursor.execute("""
            INSERT INTO meals (meal_type, meal_date, meal_time, menu_items, response_deadline, status)
            VALUES ('dinner', ?, ?, ?, ?, 'open')
        """, (today_str, REAL_WORLD_INDIAN_MEAL_SCHEDULE['dinner']['service_start'], 
              "Steamed Basmati Rice, Yellow Dal Tadka, Paneer Butter Masala, Butter Tawa Roti, Papad, Green Salad, Gulab Jamun", 
              dinner_deadline))
        today_dinner_id = cursor.lastrowid

        # Seed realistic responses for Dinner: ~52 will eat, ~14 not eating, ~8 no response
        # Arjun has not responded yet so user can immediately test!
        for u_id in user_ids[1:]:
            roll = random.random()
            if roll < 0.72:
                cursor.execute("INSERT INTO meal_responses (meal_id, user_id, response) VALUES (?, ?, 'will_eat')", (today_dinner_id, u_id))
            elif roll < 0.90:
                cursor.execute("INSERT INTO meal_responses (meal_id, user_id, response) VALUES (?, ?, 'not_eating')", (today_dinner_id, u_id))

        # TOMORROW'S MEALS IN IST (All open for advance response)
        tomorrow_date = today_date + timedelta(days=1)
        tomorrow_str = tomorrow_date.strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO meals (meal_type, meal_date, meal_time, menu_items, response_deadline, status)
            VALUES ('breakfast', ?, ?, ?, ?, 'open')
        """, (tomorrow_str, REAL_WORLD_INDIAN_MEAL_SCHEDULE['breakfast']['service_start'], menus["breakfast"][1], f"{tomorrow_str} 06:30:00"))

        cursor.execute("""
            INSERT INTO meals (meal_type, meal_date, meal_time, menu_items, response_deadline, status)
            VALUES ('lunch', ?, ?, ?, ?, 'open')
        """, (tomorrow_str, REAL_WORLD_INDIAN_MEAL_SCHEDULE['lunch']['service_start'], menus["lunch"][1], f"{tomorrow_str} 10:00:00"))

        cursor.execute("""
            INSERT INTO meals (meal_type, meal_date, meal_time, menu_items, response_deadline, status)
            VALUES ('dinner', ?, ?, ?, ?, 'open')
        """, (tomorrow_str, REAL_WORLD_INDIAN_MEAL_SCHEDULE['dinner']['service_start'], menus["dinner"][1], f"{tomorrow_str} 17:00:00"))

        # DAY AFTER TOMORROW
        day2_date = today_date + timedelta(days=2)
        day2_str = day2_date.strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO meals (meal_type, meal_date, meal_time, menu_items, response_deadline, status)
            VALUES ('lunch', ?, ?, ?, ?, 'open')
        """, (day2_str, REAL_WORLD_INDIAN_MEAL_SCHEDULE['lunch']['service_start'], menus["lunch"][2], f"{day2_str} 10:00:00"))
        cursor.execute("""
            INSERT INTO meals (meal_type, meal_date, meal_time, menu_items, response_deadline, status)
            VALUES ('dinner', ?, ?, ?, ?, 'open')
        """, (day2_str, REAL_WORLD_INDIAN_MEAL_SCHEDULE['dinner']['service_start'], menus["dinner"][2], f"{day2_str} 17:00:00"))

        # Notifications
        arjun_id = user_ids[0]
        notifications_data = [
            (arjun_id, "🍽️ Dinner response is open", "Will you have dinner today? Response closes at 5:00 PM IST. Tap to respond in 2 seconds.", "deadline_reminder", "/dashboard"),
            (arjun_id, "⏰ Reminder: Response Window Closing Soon", "Dinner response deadline is approaching at 5:00 PM IST. Please confirm if you will eat.", "deadline_reminder", "/dashboard"),
            (arjun_id, "📢 Tomorrow's Lunch Special", "Special Paneer Butter Masala & Naan added to tomorrow's lunch menu!", "menu_update", "/my-meals"),
            (arjun_id, "✅ Response Recorded", "Your breakfast response was successfully registered.", "response_confirmation", "/my-meals")
        ]
        for u_id, title, msg, n_type, action_url in notifications_data:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, action_url, is_read)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (u_id, title, msg, n_type, action_url))

        print(f"Successfully seeded database with IST timings and {len(user_ids)} residents!")

if __name__ == "__main__":
    seed_database()
