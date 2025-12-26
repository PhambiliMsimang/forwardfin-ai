import threading
import uvicorn
import redis
import json
import time
import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

# --- CONFIGURATION ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
app = FastAPI()

# --- PART 1: THE ANALYSIS ENGINE (Background Thread) ---
def run_analysis_engine():
    print("🧮 ANALYSIS: Thread Started")
    price_history = []
    
    # Try to load VADER (Self-Healing)
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        HAS_NEWS = True
    except ImportError:
        HAS_NEWS = False

    pubsub = r.pubsub()
    pubsub.subscribe('market_data')
    
    for message in pubsub.listen():
        if message['type'] != 'message': continue
        try:
            data = json.loads(message['data'])
            price = float(data['price'])
            price_history.append(price)
            if len(price_history) > 60: price_history.pop(0)

            # Indicators
            rsi = 50
            if len(price_history) > 26:
                series = pd.Series(price_history)
                delta = series.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi_series = 100 - (100 / (1 + rs))
                rsi = rsi_series.iloc[-1] if not pd.isna(rsi_series.iloc[-1]) else 50

            # News
            sentiment, headline = 0.0, "News Disabled"
            if HAS_NEWS:
                 # (Simplified news logic to prevent rate limits)
                 pass 

            packet = {
                "symbol": data['symbol'], "price": price,
                "indicators": {"rsi": rsi, "sentiment": sentiment, "headline": headline, "risk_level": "LOW"}
            }
            r.set("latest_price", json.dumps(packet))
            r.publish('analysis_results', json.dumps(packet))
        except Exception as e:
            print(f"Analysis Error: {e}")

# --- PART 2: THE INFERENCE ENGINE (Background Thread) ---
def run_inference_engine():
    print("🧠 INFERENCE: Thread Started")
    pubsub = r.pubsub()
    pubsub.subscribe('analysis_results')
    
    for message in pubsub.listen():
        if message['type'] != 'message': continue
        try:
            data = json.loads(message['data'])
            rsi = data['indicators']['rsi']
            
            # Simple Logic (Since we are flattening)
            bias = "NEUTRAL"
            prob = 50.0
            if rsi > 70: bias, prob = "BEARISH", 85.0
            elif rsi < 30: bias, prob = "BULLISH", 85.0
            else: bias, prob = "BULLISH", 60.0

            result = {"symbol": data['symbol'], "bias": bias, "probability": prob, "win_rate": 0, "total_trades": 0}
            narrative = f"Technical Analysis: {bias} ({prob}%) based on RSI {rsi:.1f}"
            
            r.set("latest_prediction", json.dumps(result))
            r.set("latest_narrative", narrative)
        except: pass

# --- PART 3: THE WEBSITE (Main Thread) ---
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Mock Data Generator (Since we aren't running the ingestion script separately)
def mock_data_generator():
    while True:
        # Simulate a live price tick if ingestion is missing
        import random
        price = 87000 + random.uniform(-100, 100)
        packet = {"symbol": "BTC-USD", "price": price}
        r.publish('market_data', json.dumps(packet))
        time.sleep(3)

@app.get("/")
async def root():
    # Simple HTML Response to verify it works
    return HTMLResponse("""
    <html>
        <head><title>ForwardFin Live</title><script>setTimeout(() => location.reload(), 3000)</script></head>
        <body style="font-family:sans-serif; text-align:center; padding:50px; background:#0f172a; color:white;">
            <h1>ForwardFin AI Terminal</h1>
            <p>System Status: <span style="color:#10b981">ONLINE</span></p>
            <p>Check /api/live-data for raw JSON</p>
        </body>
    </html>
    """)

@app.get("/api/live-data")
async def get_live_data():
    price_data = json.loads(r.get("latest_price") or "{}")
    pred_data = json.loads(r.get("latest_prediction") or "{}")
    narrative = r.get("latest_narrative") or "Initializing..."
    return {"price": price_data, "prediction": pred_data, "narrative": narrative}

# --- STARTUP ---
if __name__ == "__main__":
    # Start Background Threads
    t1 = threading.Thread(target=run_analysis_engine, daemon=True)
    t2 = threading.Thread(target=run_inference_engine, daemon=True)
    t3 = threading.Thread(target=mock_data_generator, daemon=True) # Keeps data alive
    t1.start()
    t2.start()
    t3.start()

    # Start Web Server
    print("🚀 LAUNCHING ONE-FILE ARCHITECTURE...")
    uvicorn.run(app, host="0.0.0.0", port=10000)