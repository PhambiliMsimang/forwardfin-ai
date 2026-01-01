import threading
import uvicorn
import time
import pytz
import yfinance as yf
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# --- 🔧 CONFIGURATION ---
ASSET_CLASS = "FUTURES" 
TICKER = "NQ=F" # Nasdaq 100 Futures (Trades 23/5)

# --- 🧠 V2 GLOBAL MEMORY ---
GLOBAL_MEMORY = {
    "market_data": {
        "symbol": TICKER, 
        "current_price": 0.00,
        "last_updated": "Waiting..."
    },
    "asia_session": {
        "status": "WAITING", 
        "start_time": "03:00",
        "end_time": "08:59",
        "high": -1.0,  
        "low": 1000000.0, 
    },
    "strategy_state": {
        "active_setup": None, 
        "anchor_high": 0,
        "anchor_low": 0
    },
    "targets": {
        "ote_0705": 0,      
        "target_20": 0      
    },
    "logs": []
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- 🛠️ HELPER: SOUTH AFRICA TIME (SAST) ---
def get_sast_time():
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    return utc_now.astimezone(pytz.timezone('Africa/Johannesburg'))

def log_event(message):
    timestamp = get_sast_time().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    GLOBAL_MEMORY["logs"].insert(0, log_entry)
    if len(GLOBAL_MEMORY["logs"]) > 50: GLOBAL_MEMORY["logs"].pop()

# --- 🧠 WORKER: STRATEGY ENGINE (THE BRAIN) ---
def run_strategy_engine():
    log_event(f"✅ STRATEGY ENGINE STARTED. Tracking {TICKER} on SAST Time.")
    
    while True:
        try:
            now = get_sast_time()
            price = GLOBAL_MEMORY["market_data"]["current_price"]
            
            # Skip logic if data hasn't arrived yet
            if price == 0:
                time.sleep(1)
                continue

            # === PHASE 1: ASIA RECORDING (03:00 - 08:59 SAST) ===
            if 3 <= now.hour < 9: 
                GLOBAL_MEMORY["asia_session"]["status"] = "RECORDING"
                
                # Logic: Track Highs and Lows
                if price > GLOBAL_MEMORY["asia_session"]["high"]:
                    GLOBAL_MEMORY["asia_session"]["high"] = price
                if price < GLOBAL_MEMORY["asia_session"]["low"]:
                    GLOBAL_MEMORY["asia_session"]["low"] = price
                    
            # === PHASE 2: MONITORING SWEEPS (09:00 Onwards) ===
            elif now.hour >= 9:
                GLOBAL_MEMORY["asia_session"]["status"] = "CLOSED"
                asia_high = GLOBAL_MEMORY["asia_session"]["high"]
                asia_low = GLOBAL_MEMORY["asia_session"]["low"]
                
                # Setup: Wait for price to break High or Low
                if GLOBAL_MEMORY["strategy_state"]["active_setup"] is None:
                    
                    # BULLISH SWEEP (Low Broken)
                    if price < asia_low:
                        log_event(f"🚨 SWEEP DETECTED: ASIA LOW ({asia_low}) BROKEN")
                        GLOBAL_MEMORY["strategy_state"]["active_setup"] = "BULLISH_SWEEP"
                        
                        # Calculate Targets (High -> Low Anchor)
                        rng = asia_high - asia_low
                        GLOBAL_MEMORY["targets"]["ote_0705"] = round(asia_low - (rng * 0.705), 2)
                        GLOBAL_MEMORY["targets"]["target_20"] = round(asia_low - (rng * 2.0), 2)
                        log_event(f"🎯 TARGET SET: -2.0 StdDev @ {GLOBAL_MEMORY['targets']['target_20']}")

                    # BEARISH SWEEP (High Broken)
                    elif price > asia_high:
                        log_event(f"🚨 SWEEP DETECTED: ASIA HIGH ({asia_high}) BROKEN")
                        GLOBAL_MEMORY["strategy_state"]["active_setup"] = "BEARISH_SWEEP"
                        
                        # Calculate Targets (Low -> High Anchor)
                        rng = asia_high - asia_low
                        GLOBAL_MEMORY["targets"]["ote_0705"] = round(asia_high + (rng * 0.705), 2)
                        GLOBAL_MEMORY["targets"]["target_20"] = round(asia_high + (rng * 2.0), 2)
                        log_event(f"🎯 TARGET SET: -2.0 StdDev @ {GLOBAL_MEMORY['targets']['target_20']}")

            # Reset at 02:59 AM
            if now.hour == 2 and now.minute == 59:
                 GLOBAL_MEMORY["asia_session"]["high"] = -1
                 GLOBAL_MEMORY["asia_session"]["low"] = 1000000
                 GLOBAL_MEMORY["strategy_state"]["active_setup"] = None

        except Exception as e:
            print(f"Logic Error: {e}")
        
        time.sleep(1)

# --- 🔌 WORKER: REAL MARKET DATA (YAHOO FINANCE) ---
def run_market_data():
    log_event(f"🔌 CONNECTING TO YAHOO FINANCE: {TICKER}...")
    
    while True:
        try:
            # Fetch 1-minute data for the last valid period
            # interval='1m' is the fastest free data available
            data = yf.download(tickers=TICKER, period="1d", interval="1m", progress=False)
            
            if not data.empty:
                # Get the very last closing price
                latest_price = data['Close'].iloc[-1].item()
                GLOBAL_MEMORY["market_data"]["current_price"] = round(latest_price, 2)
                GLOBAL_MEMORY["market_data"]["last_updated"] = datetime.now().strftime("%H:%M:%S")
            else:
                print("⚠️ No data received from Yahoo (Market might be closed/sleeping)")

            # Sleep 10 seconds to respect Yahoo rate limits
            time.sleep(10)
            
        except Exception as e:
            print(f"❌ Data Error: {e}")
            time.sleep(5)

# --- 🖥️ DASHBOARD ---
@app.get("/")
async def root():
    return HTMLResponse("""
    <html>
        <head>
            <title>ForwardFin V2 | Live NQ Terminal</title>
            <meta http-equiv="refresh" content="3">
            <style>
                body { font-family: 'Courier New', monospace; background: #0d1117; color: #c9d1d9; padding: 20px; }
                .box { border: 1px solid #30363d; padding: 20px; margin-bottom: 20px; border-radius: 6px; }
                h1 { color: #58a6ff; }
                .highlight { color: #f0883e; font-weight: bold; }
                .green { color: #7ee787; }
                .red { color: #ff7b72; }
            </style>
        </head>
        <body>
            <h1>🚀 ForwardFin V2 (Live NQ)</h1>
            <div class="box">
                <h3>📡 Live Market Data ({ticker})</h3>
                <p>Price: <span class="highlight" style="font-size: 24px;" id="price">LOADING...</span></p>
                <p>Last Update: <span id="update">--</span></p>
                <p>Time (SAST): <span id="time">LOADING...</span></p>
            </div>
            
            <div class="box">
                <h3>🌏 Asia Session (03:00 - 08:59 SAST)</h3>
                <p>Status: <span id="asia-status">--</span></p>
                <p>High: <span class="green" id="asia-high">--</span></p>
                <p>Low: <span class="red" id="asia-low">--</span></p>
            </div>

            <div class="box">
                <h3>🎯 Strategy Engine</h3>
                <p>Active Setup: <span class="highlight" id="setup">NONE</span></p>
                <p>Target (-2.0 StdDev): <span class="highlight" id="target">--</span></p>
                <p>OTE Level (-0.705): <span id="ote">--</span></p>
            </div>

            <div class="box">
                <h3>📜 System Logs</h3>
                <div id="logs" style="font-size: 12px; opacity: 0.8;"></div>
            </div>

            <script>
                async function update() {
                    let response = await fetch('/api/v2/status');
                    let data = await response.json();
                    
                    document.getElementById('price').innerText = data.market_data.current_price;
                    document.getElementById('update').innerText = data.market_data.last_updated;
                    document.getElementById('time').innerText = new Date().toLocaleTimeString('en-ZA', {timeZone: 'Africa/Johannesburg'});
                    
                    document.getElementById('asia-status').innerText = data.asia_session.status;
                    document.getElementById('asia-high').innerText = data.asia_session.high;
                    document.getElementById('asia-low').innerText = data.asia_session.low;
                    
                    document.getElementById('setup').innerText = data.strategy_state.active_setup || "WAITING";
                    document.getElementById('target').innerText = data.targets.target_20 || "--";
                    document.getElementById('ote').innerText = data.targets.ote_0705 || "--";
                    
                    document.getElementById('logs').innerHTML = data.logs.join('<br>');
                }
                update();
            </script>
        </body>
    </html>
    """.replace("{ticker}", TICKER))

@app.get("/api/v2/status")
async def status():
    return GLOBAL_MEMORY

if __name__ == "__main__":
    t1 = threading.Thread(target=run_market_data, daemon=True)
    t2 = threading.Thread(target=run_strategy_engine, daemon=True)
    t1.start()
    t2.start()
    print("🚀 ForwardFin V2 Live Launching on Port 10000...")
    uvicorn.run(app, host="0.0.0.0", port=10000)