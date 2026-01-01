import threading
import uvicorn
import requests
import json
import time
import pandas as pd
import numpy as np
import yfinance as yf
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pydantic import BaseModel

# --- 🔧 CONFIGURATION ---
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1454098742218330307/gi8wvEn0pMcNsAWIR_kY5-_0_VE4CvsgWjkSXjCasXX-xUrydbhYtxHRLLLgiKxs_pLL"

# --- 🧠 GLOBAL STATE ---
GLOBAL_STATE = {
    "settings": {
        "asset": "NQ1!",       # NQ1! (Nasdaq) or ES1! (S&P 500)
        "strategy": "SWEEP",   # SWEEP or STD_DEV
        "style": "SNIPER"      # SCALP, SWING, or SNIPER
    },
    "market_data": {
        "price": 0.00,
        "ifvg_detected": False, # IFVG Status
        "session_high": 0.00,
        "session_low": 0.00,
        "history": [],
        "highs": [],
        "lows": []
    },
    "prediction": {
        "bias": "NEUTRAL", 
        "probability": 50, 
        "narrative": "V2 System Initializing...",
        "trade_setup": {"entry": 0, "tp": 0, "sl": 0, "valid": False}
    },
    "performance": {"wins": 0, "total": 0, "win_rate": 0},
    "active_trades": [],
    "last_alert_time": 0
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
analyzer = SentimentIntensityAnalyzer()

class SettingsUpdate(BaseModel):
    asset: str
    strategy: str
    style: str

# --- 🔔 DISCORD ALERT SYSTEM ---
def send_discord_alert(data, asset):
    if time.time() - GLOBAL_STATE["last_alert_time"] < 300: return

    try:
        color = 5763719 if data['bias'] == "LONG" else 15548997
        strategy_name = "Asia Sweep + IFVG"
        style_icon = "🔫" if GLOBAL_STATE['settings']['style'] == "SNIPER" else "⚡"
        
        embed = {
            "title": f"{style_icon} SIGNAL: {asset} {data['bias']}",
            "description": f"**Logic:** {data['narrative']}",
            "color": color,
            "fields": [
                {"name": "Entry", "value": f"${data['trade_setup']['entry']:,.2f}", "inline": True},
                {"name": "🎯 TP", "value": f"${data['trade_setup']['tp']:,.2f}", "inline": True},
                {"name": "🛑 SL", "value": f"${data['trade_setup']['sl']:,.2f}", "inline": True}
            ],
            "footer": {"text": "ForwardFin V2 • IFVG Validated"}
        }
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
        GLOBAL_STATE["last_alert_time"] = time.time()
        print("✅ Discord Alert Sent!", flush=True)
    except Exception as e:
        print(f"❌ Discord Error: {e}", flush=True)

# --- WORKER 1: REAL FUTURES DATA ---
def run_market_data_stream():
    print("📡 DATA THREAD: Connecting to CME Futures...", flush=True)
    while True:
        try:
            ticker_map = {"NQ1!": "NQ=F", "ES1!": "ES=F"}
            current_asset = GLOBAL_STATE["settings"]["asset"]
            ticker = ticker_map.get(current_asset, "NQ=F")

            data = yf.download(ticker, period="1d", interval="1m", progress=False)
            
            if not data.empty:
                current_price = float(data['Close'].iloc[-1])
                GLOBAL_STATE["market_data"]["price"] = current_price
                GLOBAL_STATE["market_data"]["history"] = data['Close'].tolist()
                GLOBAL_STATE["market_data"]["highs"] = data['High'].tolist()
                GLOBAL_STATE["market_data"]["lows"] = data['Low'].tolist()
                GLOBAL_STATE["market_data"]["session_high"] = float(data['High'].max())
                GLOBAL_STATE["market_data"]["session_low"] = float(data['Low'].min())
                
                print(f"✅ TICK [{current_asset}]: ${current_price:,.2f}", flush=True)
            
        except Exception as e:
            print(f"⚠️ Data Error: {e}", flush=True)
        time.sleep(10)

# --- HELPER: IFVG DETECTION LOGIC ---
def scan_for_ifvg(highs, lows, closes):
    # This function scans the last 15 candles for an Inversion Fair Value Gap
    if len(closes) < 5: return False
    
    # Logic: Look for a gap that was created, then BROKEN (Inverted)
    for i in range(len(closes)-15, len(closes)-2):
        # Bullish Gap Created? (Low[i] > High[i+2])
        if lows[i] > highs[i+2]:
            gap_low = highs[i+2]
            gap_high = lows[i]
            # Did price later close BELOW this gap? (Inversion)
            if closes[-1] < gap_low:
                return True # Bearish IFVG Detected

        # Bearish Gap Created? (High[i] < Low[i+2])
        if highs[i] < lows[i+2]:
            gap_low = highs[i]
            gap_high = lows[i+2]
            # Did price later close ABOVE this gap? (Inversion)
            if closes[-1] > gap_high:
                return True # Bullish IFVG Detected
                
    return False

# --- WORKER 2: THE BRAIN ---
def run_strategy_engine():
    print("🧠 BRAIN THREAD: V2 Logic Loaded...", flush=True)
    while True:
        try:
            settings = GLOBAL_STATE["settings"]
            market = GLOBAL_STATE["market_data"]
            history = market["history"]
            current_price = market["price"]

            if len(history) < 20: 
                time.sleep(5)
                continue

            # 1. GATEKEEPER: CHECK IFVG FIRST
            has_ifvg = scan_for_ifvg(market["highs"], market["lows"], history)
            GLOBAL_STATE["market_data"]["ifvg_detected"] = has_ifvg

            bias = "NEUTRAL"
            prob = 50
            narrative = "Scanning market structure..."

            if has_ifvg:
                narrative = "⚡ IFVG DETECTED. Looking for setup..."
                
                # 2. STRATEGY LOGIC (Only runs if IFVG exists)
                if settings["strategy"] == "SWEEP":
                    high = market["session_high"]
                    low = market["session_low"]
                    if current_price < high and max(history[-5:]) >= high:
                        bias = "SHORT"
                        prob = 85
                        narrative = "IFVG + Asia High Sweep confirmed."
                    elif current_price > low and min(history[-5:]) <= low:
                        bias = "LONG"
                        prob = 85
                        narrative = "IFVG + Asia Low Sweep confirmed."
                
                elif settings["strategy"] == "STD_DEV":
                    series = pd.Series(history)
                    mean = series.rolling(20).mean().iloc[-1]
                    upper = mean + (2 * series.rolling(20).std().iloc[-1])
                    lower = mean - (2 * series.rolling(20).std().iloc[-1])

                    if current_price > upper:
                        bias = "SHORT"
                        prob = 80
                        narrative = "IFVG + 2SD Extension (Overbought)."
                    elif current_price < lower:
                        bias = "LONG"
                        prob = 80
                        narrative = "IFVG + 2SD Extension (Oversold)."
            else:
                narrative = "⛔ NO TRADES: Waiting for IFVG formation."

            # --- SNIPER MODIFIER ---
            style = settings["style"]
            if style == "SNIPER" and prob < 80:
                bias = "NEUTRAL" # Force neutral if not perfect

            # --- RISK CALC ---
            volatility = pd.Series(history).diff().std() * 2
            if pd.isna(volatility) or volatility == 0: volatility = 10.0
            
            tp_mult = 4.0 if style == "SNIPER" else 2.0
            sl_mult = 0.5 if style == "SNIPER" else 1.0

            if bias == "LONG":
                tp = current_price + (volatility * tp_mult)
                sl = current_price - (volatility * sl_mult)
            elif bias == "SHORT":
                tp = current_price - (volatility * tp_mult)
                sl = current_price + (volatility * sl_mult)
            else: tp, sl = 0, 0

            GLOBAL_STATE["prediction"] = {
                "bias": bias,
                "probability": prob,
                "narrative": narrative,
                "trade_setup": {"entry": current_price, "tp": tp, "sl": sl, "valid": bias != "NEUTRAL"}
            }

            # --- EXECUTION ---
            if prob >= 80 and bias != "NEUTRAL":
                if not any(t for t in GLOBAL_STATE["active_trades"] if time.time() - t['time'] < 300):
                    GLOBAL_STATE["active_trades"].append({
                        "type": bias, "entry": current_price, "time": time.time()
                    })
                    send_discord_alert(GLOBAL_STATE["prediction"], settings["asset"])

            # Grading
            for trade in GLOBAL_STATE["active_trades"][:]:
                if time.time() - trade['time'] > 300:
                    is_win = (trade['type'] == "LONG" and current_price > trade['entry']) or \
                             (trade['type'] == "SHORT" and current_price < trade['entry'])
                    GLOBAL_STATE["performance"]["total"] += 1
                    if is_win: GLOBAL_STATE["performance"]["wins"] += 1
                    GLOBAL_STATE["active_trades"].remove(trade)

            total = GLOBAL_STATE["performance"]["total"]
            wins = GLOBAL_STATE["performance"]["wins"]
            GLOBAL_STATE["performance"]["win_rate"] = int((wins/total)*100) if total > 0 else 0

        except Exception as e:
            print(f"❌ Brain Error: {e}", flush=True)
        time.sleep(5)

# --- API ROUTES ---
@app.get("/api/live-data")
async def get_api():
    return GLOBAL_STATE

@app.post("/api/update-settings")
async def update_settings(settings: SettingsUpdate):
    GLOBAL_STATE["settings"]["asset"] = settings.asset
    GLOBAL_STATE["settings"]["strategy"] = settings.strategy
    GLOBAL_STATE["settings"]["style"] = settings.style
    GLOBAL_STATE["market_data"]["history"] = [] 
    return {"status": "success"}

@app.get("/")
async def root():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ForwardFin V2 | IFVG Sniper</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #e2e8f0; }
        .btn-asset { transition: all 0.2s; border: 1px solid #334155; }
        .btn-asset:hover { background-color: #1e293b; border-color: #0ea5e9; }
        .btn-asset.active { background-color: #0ea5e9; color: white; border-color: #0ea5e9; box-shadow: 0 0 15px rgba(14, 165, 233, 0.5); }
        .lesson-card { cursor: pointer; transition: all 0.2s; border-left: 4px solid transparent; }
        .lesson-card:hover { background: #1e293b; }
        .lesson-card.active { background: #1e293b; border-left-color: #0ea5e9; }
    </style>
</head>
<body class="antialiased min-h-screen flex flex-col">

    <nav class="border-b border-slate-800 bg-slate-900/50 backdrop-blur-xl sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
            <div class="flex items-center gap-4">
                <div class="h-8 w-8 bg-sky-500 rounded flex items-center justify-center font-bold text-white">FF</div>
                <div class="text-sm font-mono text-slate-400" id="nav-ticker">CONNECTING...</div>
            </div>
            <div class="flex gap-2">
                <button onclick="setAsset('NQ1!')" id="btn-nq" class="btn-asset active px-4 py-1.5 rounded text-sm font-bold bg-slate-800 text-slate-300">NQ</button>
                <button onclick="setAsset('ES1!')" id="btn-es" class="btn-asset px-4 py-1.5 rounded text-sm font-bold bg-slate-800 text-slate-300">ES</button>
            </div>
        </div>
    </nav>

    <main class="flex-grow p-4 md:p-8 max-w-7xl mx-auto w-full space-y-6">
        
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
                <div class="text-[10px] text-slate-400 font-bold tracking-wider">IFVG STATUS</div>
                <div id="status-ifvg" class="text-lg font-bold text-rose-500 mt-1">NO GAP FOUND</div>
            </div>
            <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
                <div class="text-[10px] text-slate-400 font-bold tracking-wider">CONFIDENCE</div>
                <div id="res-prob" class="text-lg font-bold text-sky-400 mt-1">0%</div>
            </div>
            <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
                <div class="text-[10px] text-slate-400 font-bold tracking-wider">WIN RATE</div>
                <div id="win-rate" class="text-lg font-bold text-emerald-400 mt-1">0%</div>
            </div>
             <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
                <div class="text-[10px] text-slate-400 font-bold tracking-wider">MODE</div>
                <div class="text-lg font-bold text-white mt-1">🎯 SNIPER</div>
            </div>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl h-[500px] relative">
            <div id="tradingview_chart" class="h-full w-full"></div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="md:col-span-2 bg-slate-800 border border-slate-700 rounded-xl p-6">
                <div class="flex items-center gap-2 mb-4">
                    <span class="h-2 w-2 rounded-full bg-sky-500 animate-pulse"></span>
                    <h3 class="font-bold text-white">Live AI Logic</h3>
                </div>
                <p id="res-reason" class="text-slate-300 font-mono text-sm leading-relaxed">Initializing System...</p>
            </div>
            <div class="bg-slate-800 border border-slate-700 rounded-xl p-6">
                <h3 class="font-bold text-white mb-4 text-xs uppercase text-slate-400">Projected Execution</h3>
                <div class="space-y-3">
                    <div class="flex justify-between text-sm"><span class="text-slate-500">ENTRY</span> <span id="setup-entry" class="font-mono text-white">---</span></div>
                    <div class="flex justify-between text-sm"><span class="text-slate-500">TP (4.0R)</span> <span id="setup-tp" class="font-mono text-emerald-400">---</span></div>
                    <div class="flex justify-between text-sm"><span class="text-slate-500">SL (0.5R)</span> <span id="setup-sl" class="font-mono text-rose-400">---</span></div>
                </div>
            </div>
        </div>

        <section id="academy" class="py-10 border-t border-slate-800">
            <div class="mb-6">
                <h2 class="text-xl font-bold text-white">ForwardFin Academy</h2>
                <p class="mt-1 text-slate-400 text-sm">Review core concepts while you trade.</p>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 h-[400px]">
                <div class="bg-slate-800 border border-slate-700 rounded-xl overflow-y-auto">
                    <div onclick="loadLesson(0)" class="lesson-card p-4 border-b border-slate-700 active">
                        <h4 class="font-bold text-white text-sm">1. IFVG (The Gap)</h4>
                    </div>
                    <div onclick="loadLesson(1)" class="lesson-card p-4 border-b border-slate-700">
                        <h4 class="font-bold text-white text-sm">2. Asia Sweeps</h4>
                    </div>
                     <div onclick="loadLesson(2)" class="lesson-card p-4 border-b border-slate-700">
                        <h4 class="font-bold text-white text-sm">3. Sniper Risk</h4>
                    </div>
                </div>
                <div class="md:col-span-2 bg-slate-800 border border-slate-700 rounded-xl p-6 flex flex-col">
                     <h3 id="lesson-title" class="text-lg font-bold text-sky-400 mb-4">1. IFVG (The Gap)</h3>
                     <div id="lesson-body" class="text-slate-300 text-sm leading-relaxed overflow-y-auto"></div>
                </div>
            </div>
        </section>
        
         <section id="architecture" class="py-10 border-t border-slate-800">
            <div class="mb-6">
                <h2 class="text-xl font-bold text-white">System Architecture</h2>
                <p class="mt-1 text-slate-400 text-sm">V2.1 with IFVG Filtering.</p>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
                <div class="bg-slate-800 p-3 rounded border border-slate-700"><h4 class="font-bold text-white text-sm">1. Yahoo API</h4><p class="text-[10px] text-slate-400">Market Data</p></div>
                <div class="bg-slate-800 p-3 rounded border border-slate-700"><h4 class="font-bold text-white text-sm">2. Pandas</h4><p class="text-[10px] text-slate-400">Analysis</p></div>
                <div class="bg-slate-800 p-3 rounded border border-slate-700 border-sky-500"><h4 class="font-bold text-sky-400 text-sm">3. IFVG Core</h4><p class="text-[10px] text-slate-400">Gap Logic</p></div>
                <div class="bg-slate-800 p-3 rounded border border-slate-700"><h4 class="font-bold text-white text-sm">4. Discord</h4><p class="text-[10px] text-slate-400">Alerts</p></div>
                <div class="bg-slate-800 p-3 rounded border border-slate-700"><h4 class="font-bold text-white text-sm">5. FastAPI</h4><p class="text-[10px] text-slate-400">Frontend</p></div>
            </div>
        </section>

    </main>

    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script>
        let currentAsset = "NQ1!";
        let widget = null;

        function initChart(symbol) {
            const tvSymbol = symbol === "NQ1!" ? "CAPITALCOM:US100" : "CAPITALCOM:US500";
            if(widget) { widget = null; document.getElementById('tradingview_chart').innerHTML = ""; }
            widget = new TradingView.widget({ "autosize": true, "symbol": tvSymbol, "interval": "1", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "hide_side_toolbar": false, "allow_symbol_change": false, "container_id": "tradingview_chart", "studies": ["BB@tv-basicstudies"] });
        }

        async function setAsset(asset) {
            currentAsset = asset;
            // UI Toggle
            document.getElementById('btn-nq').className = asset === "NQ1!" ? "btn-asset active px-4 py-1.5 rounded text-sm font-bold bg-slate-800 text-slate-300" : "btn-asset px-4 py-1.5 rounded text-sm font-bold bg-slate-800 text-slate-300";
            document.getElementById('btn-es').className = asset === "ES1!" ? "btn-asset active px-4 py-1.5 rounded text-sm font-bold bg-slate-800 text-slate-300" : "btn-asset px-4 py-1.5 rounded text-sm font-bold bg-slate-800 text-slate-300";
            
            // Backend Update
            await fetch('/api/update-settings', {
                method: 'POST', 
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ asset: asset, strategy: "SWEEP", style: "SNIPER" })
            });
            
            // Chart Update
            initChart(asset);
        }

        async function updateDashboard() {
            try {
                const res = await fetch('/api/live-data');
                const data = await res.json();
                
                document.getElementById('nav-ticker').innerText = `${data.settings.asset} $${data.market_data.price.toLocaleString()}`;
                
                // IFVG Status
                const ifvgEl = document.getElementById('status-ifvg');
                if(data.market_data.ifvg_detected) {
                    ifvgEl.innerText = "ACTIVE DETECTED";
                    ifvgEl.className = "text-lg font-bold text-emerald-400 mt-1 animate-pulse";
                } else {
                    ifvgEl.innerText = "NO GAP FOUND";
                    ifvgEl.className = "text-lg font-bold text-rose-500 mt-1";
                }

                document.getElementById('res-prob').innerText = data.prediction.probability + "%";
                document.getElementById('res-reason').innerText = data.prediction.narrative;
                
                // Setup
                const setup = data.prediction.trade_setup;
                document.getElementById('setup-entry').innerText = "$" + setup.entry.toLocaleString();
                document.getElementById('setup-tp').innerText = "$" + setup.tp.toLocaleString();
                document.getElementById('setup-sl').innerText = "$" + setup.sl.toLocaleString();
                
                if (data.performance) {
                    document.getElementById('win-rate').innerText = data.performance.win_rate + "%";
                }

            } catch(e) { console.log(e); }
        }

        // --- ACADEMY LOGIC RESTORED ---
        const lessons = [
            {
                title: "1. IFVG (The Gap)",
                body: "An <b>Inversion Fair Value Gap (IFVG)</b> is a market structure fingerprint. <br><br>1. A standard Fair Value Gap (FVG) is a 3-candle sequence where the wicks of Candle 1 and Candle 3 do not overlap.<br>2. Usually, price respects this gap as support/resistance.<br>3. An <b>IFVG</b> happens when price <b>breaks through</b> the gap and closes on the other side. The gap then 'inverts' polarity (Support becomes Resistance)."
            },
            {
                title: "2. Asia Sweeps",
                body: "Institutions execute orders where liquidity exists. <br><br>The High and Low of the Asian Session (6pm - 3am EST) act as magnets. <br><br><b>The Strategy:</b> Wait for price to poke above the Asian High, trap the breakout traders, and then aggressively reverse back inside the range. We enter on the return."
            },
            {
                title: "3. Sniper Risk",
                body: "Sniper mode is about <b>High Reward, Low Risk</b>. <br><br>- <b>Stop Loss:</b> Very tight (0.5x Volatility). If the trade doesn't work immediately, we get out.<br>- <b>Take Profit:</b> Aggressive (4.0x Volatility). We are catching the explosive move after a trap."
            }
        ];

        function loadLesson(index) {
            const l = lessons[index];
            document.getElementById('lesson-title').innerText = l.title;
            document.getElementById('lesson-body').innerHTML = l.body;
            document.querySelectorAll('.lesson-card').forEach((el, i) => {
                if(i === index) el.classList.add('active', 'border-l-sky-500');
                else el.classList.remove('active', 'border-l-sky-500');
            });
        }

        document.addEventListener('DOMContentLoaded', () => {
            initChart("NQ1!");
            loadLesson(0);
            setInterval(updateDashboard, 5000);
        });
    </script>
</body>
</html>
""")

if __name__ == "__main__":
    t1 = threading.Thread(target=run_market_data_stream, daemon=True)
    t2 = threading.Thread(target=run_strategy_engine, daemon=True)
    t1.start()
    t2.start()
    uvicorn.run(app, host="0.0.0.0", port=10000)