from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pathlib import Path
from app.config import BASE_DIR
from app.database import init_db
from app.seed_data import seed_database
from app.auth import get_current_user_from_request
from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router
from app.routes.admin_routes import router as admin_router
from app.routes.api_routes import router as api_router

app = FastAPI(
    title="SmartMess - Food Demand Estimation & Waste Reduction System",
    description="Modern hostel and mess demand estimation system.",
    version="1.0.0"
)

# Initialize database schema and seed demo data on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    seed_database()

# Static files
static_dir = BASE_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include Routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(admin_router)
app.include_router(api_router)

@app.get("/")
async def root(request: Request):
    user = get_current_user_from_request(request)
    if user:
        if user.get("is_admin"):
            return RedirectResponse("/admin/dashboard")
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")
