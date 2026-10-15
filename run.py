import os
import sys

# Ensure current directory is in sys.path
curr_dir = os.path.dirname(os.path.abspath(__file__))
if curr_dir not in sys.path:
    sys.path.insert(0, curr_dir)

import uvicorn
from app.main import app

if __name__ == "__main__":
    print("==================================================================")
    print("  SmartMess: Food Demand Estimation & Waste Reduction System")
    print("  Live URL: http://0.0.0.0:8000")
    print("  Resident Portal: http://0.0.0.0:8000/login")
    print("  Admin Portal:    http://0.0.0.0:8000/admin/login")
    print("==================================================================")

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))

    # Pass the app object directly
    uvicorn.run(app, host=host, port=port, reload=False)
