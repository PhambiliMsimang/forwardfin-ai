from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import redis
import json
import os

app = FastAPI()

# 1. Setup Folders
# Tell the server where the HTML and Images are
app.mount("/static", StaticFiles(directory="services/frontend/static"), name="static")
templates = Jinja2Templates(directory="services/frontend/templates")

# 2. Connect to Redis (The Data Source)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# 3. The Home Page Route
@app.get("/")
async def read_root(request: Request):
    # This serves your exact HTML file
    return templates.TemplateResponse("index.html", {"request": request})

# 4. The Data API (Your HTML will ask this for updates)
@app.get("/api/live-data")
async def get_data():
    try:
        # Fetch latest data from Redis
        price_data = r.get("latest_price")
        prediction_data = r.get("latest_prediction")
        narrative_data = r.get("latest_narrative")

        # Parse it safely
        price = json.loads(price_data) if price_data else None
        pred = json.loads(prediction_data) if prediction_data else None
        narrative = narrative_data if narrative_data else "Waiting for insights..."

        return {
            "price": price,
            "prediction": pred,
            "narrative": narrative
        }
    except Exception as e:
        return {"error": str(e)}

# Note: We don't run app.run() here. 
# The Cloud will run it using 'uvicorn' command.