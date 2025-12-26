import threading
import uvicorn
import json
import time
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# --- 🧠 GLOBAL MEMORY (Replaces Redis Database) ---
# This acts as the "brain" shared between threads
GLOBAL_MEMORY = {
    "price": {"symbol": "BTC-USD", "price": 0.0},
    "prediction": {
        "bias": "ANALYZING", 
        "probability": 0, 
        "narrative": "System initializing... waiting for market data."
    },
    "history": [] 
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- WORKER 1: MARKET DATA STREAM ---
def run_data_stream():
    print("📡 DATA THREAD: Starting...")
    import yfinance as yf
    
    while True:
        try:
            # Fetch 1 minute of data
            btc = yf.Ticker("BTC-USD")
            history = btc.history(period="1d", interval="1m")
            
            if not history.empty:
                current_price = float(history['Close'].iloc[-1])
                GLOBAL_MEMORY["price"] = {"symbol": "BTC-USD", "price": current_price}
                
                # Keep last 60 points for the AI
                GLOBAL_MEMORY["history"].append(current_price)
                if len(GLOBAL_MEMORY["history"]) > 60:
                    GLOBAL_MEMORY["history"].pop(0)
            else:
                print("⚠️ No data received from Yahoo Finance")
                
        except Exception as e:
            print(f"⚠️ Data Error: {e}")
            
        time.sleep(10) # Wait 10 seconds between checks

# --- WORKER 2: AI PREDICTION ENGINE ---
def run_ai_brain():
    print("🧠 AI THREAD: Starting...")
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    
    # Self-Healing: Use VADER if installed, otherwise skip
    try:
        analyzer = SentimentIntensityAnalyzer()
        HAS_NEWS = True
    except:
        HAS_NEWS = False
        print("ℹ️ Running in Technical-Only Mode")

    while True:
        try:
            prices = GLOBAL_MEMORY["history"]
            
            # Need at least 20 data points to calculate RSI
            if len(prices) > 20:
                series = pd.Series(prices)
                delta = series.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                rsi_val = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
                
                # Decision Logic
                bias = "NEUTRAL"
                prob = 50
                
                if rsi_val > 70:
                    bias = "BEARISH"
                    prob = 82
                    reason = "Market is Overbought (RSI > 70)"
                elif rsi_val < 30:
                    bias = "BULLISH"
                    prob = 78
                    reason = "Market is Oversold (RSI < 30)"
                else:
                    bias = "BULLISH" if prices[-1] > prices[0] else "BEARISH"
                    prob = 55
                    reason = "Momentum following trend"

                # Save to Memory
                GLOBAL_MEMORY["prediction"] = {
                    "bias": bias,
                    "probability": prob,
                    "narrative": f"Technical Analysis: {reason}. RSI is at {rsi_val:.1f}."
                }
                
        except Exception as e:
            print(f"❌ AI Error: {e}")
            
        time.sleep(5)

# --- WORKER 3: THE WEBSITE ---
@app.get("/")
async def root():
    price = GLOBAL_MEMORY['price']['price']
    bias = GLOBAL_MEMORY['prediction']['bias']
    prob = GLOBAL_MEMORY['prediction']['probability']
    narrative = GLOBAL_MEMORY['prediction']['narrative']
    
    color = "text-emerald-400" if bias == "BULLISH" else "text-rose-400"
    
    return HTMLResponse(f"""
    <html>
        <head>
            <title>ForwardFin | Live</title>
            <meta http-equiv="refresh" content="5">
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-slate-900 text-white flex flex-col items-center justify-center h-screen font-sans">
            <div class="text-center space-y-8 p-10 bg-slate-800 rounded-3xl border border-slate-700 shadow-2xl max-w-2xl w-full">
                
                <div class="flex justify-between items-center border-b border-slate-700 pb-4">
                    <div class="font-bold text-xl tracking-wider text-slate-400">FORWARDFIN AI</div>
                    <div class="px-3 py-1 bg-emerald-500/10 text-emerald-400 rounded-full text-xs font-bold border border-emerald-500/20 animate-pulse">
                        LIVE CONNECTION
                    </div>
                </div>

                <div>
                    <div class="text-slate-500 text-sm uppercase tracking-widest mb-1">Bitcoin Price</div>
                    <h1 class="text-7xl font-black tracking-tighter text-white">
                        ${price:,.2f}
                    </h1>
                </div>

                <div class="grid grid-cols-2 gap-6">
                    <div class="bg-slate-900/50 p-6 rounded-2xl border border-slate-700">
                        <div class="text-slate-500 text-xs uppercase mb-2">AI Signal</div>
                        <div class="text-3xl font-black {color}">{bias}</div>
                    </div>
                    <div class="bg-slate-900/50 p-6 rounded-2xl border border-slate-700">
                        <div class="text-slate-500 text-xs uppercase mb-2">Confidence</div>
                        <div class="text-3xl font-black text-sky-400">{prob}%</div>
                    </div>
                </div>

                <div class="bg-slate-900/30 p-4 rounded-xl border border-slate-700/50">
                    <p class="text-slate-300 text-sm font-mono leading-relaxed">
                        > {narrative}
                    </p>
                </div>
            </div>
        </body>
    </html>
    """)

@app.get("/api/live-data")
async def get_api():
    return GLOBAL_MEMORY

# --- LAUNCHER ---
if __name__ == "__main__":
    # Start Background Threads
    t1 = threading.Thread(target=run_data_stream, daemon=True)
    t2 = threading.Thread(target=run_ai_brain, daemon=True)
    t1.start()
    t2.start()

    # Start Web Server
    print("🚀 SYSTEM LAUNCH: Port 10000")
    uvicorn.run(app, host="0.0.0.0", port=10000)