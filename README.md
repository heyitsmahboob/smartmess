# 🍲 SmartMess - Food Demand Estimation & Waste Reduction System

**SmartMess** is a modern, responsive full-stack web application designed for hostels, PGs, universities, and central mess facilities across India. It eliminates daily food wastage by enabling residents to confirm meal attendance in advance, allowing mess administrators to cook exact quantities with configurable safety buffers.

---

## 📁 Clean Project Structure

```
smartmess/
├── app/
│   ├── routes/              # FastAPI Routers (admin, user, auth, realtime APIs)
│   ├── services/            # Food estimation engine, analytics, notifications, CSV export
│   ├── static/              # CSS styles, vanilla JS, images, icons
│   ├── templates/           # Jinja2 HTML templates (mobile-first resident & admin dashboards)
│   ├── auth.py              # JWT authentication & password hashing (PBKDF2-SHA256)
│   ├── common.py            # Global Jinja environment & filters
│   ├── config.py            # Secret keys, cookies, database path configuration
│   ├── database.py          # SQLite connection manager & relational schema
│   ├── main.py              # FastAPI application factory & middleware
│   └── time_utils.py        # India Standard Time (IST, UTC+05:30) helper library
├── Procfile                 # Cloud web process entry point for Render/Heroku
├── README.md                # Project documentation & credentials
├── requirements.txt         # Clean, compatible production dependencies
├── run.py                   # Server startup script with dynamic host/port binding
├── smartmess.db             # Pre-seeded SQLite database with sample residents & meals
└── start_windows.bat        # 1-click startup batch script for Windows
```

---

## 🔐 Default Demo Logins

### 🛡️ Mess Admin & Kitchen Supervisor Portal (`/admin/login`)
- **Admin**: `admin@smartmess.com` | Password: `admin123`
- **Supervisor**: `manager@hostel.edu` | Password: `admin123`

### 👤 Student Residents Portal (`/login`)
- **Arjun Sharma**: `arjun@hostel.edu` | Password: `student123` *(Boys Hostel A • Room 101)*
- **Priya Patel**: `priya@hostel.edu` | Password: `student123` *(Girls Hostel A • Room 205)*
- **Rahul Verma**: `rahul@hostel.edu` | Password: `student123` *(Boys Hostel B • Room 104)*
- **Ananya Iyer**: `ananya@hostel.edu` | Password: `student123` *(Girls Hostel B • Room 302)*

*(New residents can also register freely at `/register`)*

---

## 🚀 Deployment on Render.com (100% Free)

1. Push this folder to your **GitHub** repository.
2. In [Render Dashboard](https://dashboard.render.com), click **New +** &rarr; **Web Service**.
3. Connect your repository.
4. Settings:
   - **Language**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python run.py` (or leave default, `Procfile` is detected automatically)
5. Environment Variable:
   - Key: `TZ` | Value: `Asia/Kolkata`
6. Click **Deploy Web Service** &rarr; Done!

---

## 💻 Running Locally

```bash
pip install -r requirements.txt
python run.py
```
Or double-click `start_windows.bat` on Windows.
Open `http://127.0.0.1:8000` in your browser.
