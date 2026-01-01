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
        "asset": "NQ1!",       # NQ1! (Nasdaq Futures) or ES1! (S&P Futures)
        "strategy": "SWEEP",   # SWEEP (Asia Liquidity) or STD_DEV (Mean Reversion)
        "style": "SNIPER"      # SCALP, SWING, or SNIPER
    },
    "market_data": {
        "price": 0.00,
        "change": 0.00,
        "session_high": 0.00,
        "session_low": 0.00,
        "history": []
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
        strategy_name = "Asia Liquidity Sweep" if GLOBAL_STATE['settings']['strategy'] == "SWEEP" else "Standard Deviation Reversion"
        style_icon = "🔫" if GLOBAL_STATE['settings']['style'] == "SNIPER" else ("⚡" if GLOBAL_STATE['settings']['style'] == "SCALP" else "🌊")
        
        embed = {
            "title": f"{style_icon} V2 SIGNAL: {asset} {data['bias']}",
            "description": f"**Strategy:** {strategy_name}\n**Reasoning:** {data['narrative']}",
            "color": color,
            "fields": [
                {"name": "Entry", "value": f"${data['trade_setup']['entry']:,.2f}", "inline": True},
                {"name": "🎯 TP", "value": f"${data['trade_setup']['tp']:,.2f}", "inline": True},
                {"name": "🛑 SL", "value": f"${data['trade_setup']['sl']:,.2f}", "inline": True}
            ],
            "footer": {"text": "ForwardFin V2 • Institutional Futures"}
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
            # Map user friendly "NQ1!" to Yahoo's ugly "NQ=F"
            ticker_map = {"NQ1!": "NQ=F", "ES1!": "ES=F"}
            current_asset = GLOBAL_STATE["settings"]["asset"]
            ticker = ticker_map.get(current_asset, "NQ=F")

            data = yf.download(ticker, period="1d", interval="1m", progress=False)
            
            if not data.empty:
                current_price = float(data['Close'].iloc[-1])
                GLOBAL_STATE["market_data"]["price"] = current_price
                GLOBAL_STATE["market_data"]["history"] = data['Close'].tolist()
                GLOBAL_STATE["market_data"]["session_high"] = float(data['High'].max())
                GLOBAL_STATE["market_data"]["session_low"] = float(data['Low'].min())
                
                print(f"✅ TICK [{current_asset}]: ${current_price:,.2f}", flush=True)
            
        except Exception as e:
            print(f"⚠️ Data Error: {e}", flush=True)
        time.sleep(10)

# --- WORKER 2: THE BRAIN (Sniper Logic Added) ---
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

            bias = "NEUTRAL"
            prob = 50
            narrative = "Scanning market structure..."
            
            # --- STRATEGY LOGIC ---
            if settings["strategy"] == "SWEEP":
                high = market["session_high"]
                low = market["session_low"]
                recent_high = max(history[-5:])
                recent_low = min(history[-5:])

                if recent_high >= high and current_price < high:
                    bias = "SHORT"
                    prob = 80
                    narrative = f"Liquidity Sweep detected at High ({high}). Price rejected. Bearish rotation likely."
                elif recent_low <= low and current_price > low:
                    bias = "LONG"
                    prob = 80
                    narrative = f"Liquidity Sweep detected at Low ({low}). Price reclaimed range. Bullish rotation likely."
                else:
                    narrative = f"Price inside range ({low:.0f} - {high:.0f}). Waiting for stop hunt."

            elif settings["strategy"] == "STD_DEV":
                series = pd.Series(history)
                mean = series.rolling(20).mean().iloc[-1]
                std = series.rolling(20).std().iloc[-1]
                upper = mean + (2 * std)
                lower = mean - (2 * std)

                if current_price > upper:
                    bias = "SHORT"
                    prob = 75
                    narrative = "Price extended +2 StdDev. Mean reversion imminent."
                elif current_price < lower:
                    bias = "LONG"
                    prob = 75
                    narrative = "Price extended -2 StdDev. Mean reversion imminent."

            # --- SNIPER MODIFIER ---
            style = settings["style"]
            
            if style == "SNIPER":
                # Sniper only takes high probability trades
                if prob < 80: 
                    bias = "NEUTRAL"
                    narrative += " (Sniper Mode: Waiting for A+ Setup)"
                else:
                    prob += 10 # Boost confidence if criteria met
                    narrative = "🎯 SNIPER ENTRY: " + narrative

            # --- RISK MANAGEMENT ---
            # Volatility (ATR-ish)
            volatility = pd.Series(history).diff().std() * 2
            if pd.isna(volatility) or volatility == 0: volatility = 10.0

            if style == "SCALP":
                tp_mult, sl_mult = 1.5, 1.0
            elif style == "SWING":
                tp_mult, sl_mult = 3.0, 2.0
            elif style == "SNIPER":
                tp_mult, sl_mult = 4.0, 0.5 # High Reward, Tight Risk

            if bias == "LONG":
                tp = current_price + (volatility * tp_mult)
                sl = current_price - (volatility * sl_mult)
            elif bias == "SHORT":
                tp = current_price - (volatility * tp_mult)
                sl = current_price + (volatility * sl_mult)
            else:
                tp, sl = 0, 0

            GLOBAL_STATE["prediction"] = {
                "bias": bias,
                "probability": min(prob, 99),
                "narrative": narrative,
                "trade_setup": {"entry": current_price, "tp": tp, "sl": sl, "valid": bias != "NEUTRAL"}
            }

            # --- EXECUTION ---
            threshold = 85 if style == "SNIPER" else 75
            
            if prob >= threshold and bias != "NEUTRAL":
                if not any(t for t in GLOBAL_STATE["active_trades"] if time.time() - t['time'] < 300):
                    GLOBAL_STATE["active_trades"].append({
                        "type": bias, "entry": current_price, "time": time.time(), "asset": settings["asset"]
                    })
                    send_discord_alert(GLOBAL_STATE["prediction"], settings["asset"])

            # Grading
            for trade in GLOBAL_STATE["active_trades"][:]:
                if time.time() - trade['time'] > 300:
                    is_win = False
                    if trade['type'] == "LONG" and current_price > trade['entry']: is_win = True
                    if trade['type'] == "SHORT" and current_price < trade['entry']: is_win = True
                    
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
    <title>ForwardFin V2 | Futures Intelligence</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #f8fafc; color: #334155; }
        .arch-layer { transition: all 0.3s ease; cursor: pointer; border-left: 4px solid transparent; }
        .arch-layer:hover { background-color: #f1f5f9; transform: translateX(4px); }
        .arch-layer.active { background-color: #e0f2fe; border-left-color: #0284c7; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        select { background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e"); background-position: right 0.5rem center; background-repeat: no-repeat; background-size: 1.5em 1.5em; padding-right: 2.5rem; -webkit-print-color-adjust: exact; }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 antialiased flex flex-col min-h-screen">

    <nav class="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-200 shadow-sm">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <div class="flex items-center gap-4">
                    <div class="h-10 w-10 bg-slate-900 rounded-lg flex items-center justify-center text-white font-bold text-xl">FF</div>
                    <div id="nav-ticker" class="font-mono text-sm font-bold text-slate-600 flex items-center gap-2">
                        <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> Connecting...
                    </div>
                </div>
                <div class="hidden md:flex space-x-8 text-sm font-medium text-slate-600">
                    <a href="#overview" class="hover:text-sky-600">Terminal</a>
                    <a href="#simulation" class="hover:text-sky-600">Analysis</a>
                    <a href="#architecture" class="hover:text-sky-600">Architecture</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="flex-grow">
        <section id="overview" class="pt-20 pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
                <div class="space-y-6">
                    <div class="inline-flex items-center px-3 py-1 rounded-full bg-sky-100 text-sky-700 text-xs font-semibold uppercase">V2 LIVE: FUTURES ENABLED</div>
                    <h1 class="text-4xl sm:text-5xl font-extrabold text-slate-900 leading-tight">
                        Sniper Logic for<br><span class="text-sky-600">Futures Markets.</span>
                    </h1>
                    <p class="text-lg text-slate-600 max-w-lg">Tracking <strong>NQ1!</strong> and <strong>ES1!</strong>. Switch between Scalp, Swing, or Sniper modes instantly.</p>
                </div>
                <div class="grid grid-cols-3 gap-4">
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Confidence</h3>
                        <div style="height: 100px; width: 100px; position: relative;"><canvas id="heroChart"></canvas></div>
                        <p id="hero-bias" class="text-sm font-bold text-slate-800 mt-2">---</p>
                    </div>
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center justify-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Win Rate</h3>
                        <div class="text-center my-2"><span id="win-rate" class="text-4xl font-black text-slate-800">0%</span></div>
                        <div class="w-full bg-slate-100 h-2 rounded-full overflow-hidden mt-1 mb-2"><div id="win-bar" class="bg-slate-800 h-full w-0 transition-all duration-1000"></div></div>
                    </div>
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center justify-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Active Style</h3>
                        <div id="style-display" class="text-4xl mt-2">⚡</div>
                        <p id="style-text" class="text-xs text-slate-400 mt-2 font-bold">SCALP</p>
                    </div>
                </div>
            </div>
        </section>

        <section class="py-10 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
            <div class="bg-slate-900 rounded-2xl shadow-2xl border border-slate-800 overflow-hidden">
                <div class="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/50 backdrop-blur">
                    <h3 class="font-bold text-white flex items-center gap-2"><span>📈</span> Live Market Action</h3>
                    <span class="text-xs text-slate-500 font-mono">SOURCE: TRADINGVIEW</span>
                </div>
                <div class="h-[500px] w-full" id="tradingview_chart"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                <script type="text/javascript">
                new TradingView.widget({ "autosize": true, "symbol": "CME:NQ1!", "interval": "1", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "hide_side_toolbar": false, "allow_symbol_change": true, "container_id": "tradingview_chart", "studies": ["BB@tv-basicstudies"] });
                </script>
            </div>
        </section>

        <section id="simulation" class="py-10 bg-slate-900 text-white">
            <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
                        <label class="text-xs font-bold text-sky-400 uppercase">1. Futures Asset</label>
                        <select id="sel-asset" onchange="updateSettings()" class="w-full mt-2 bg-slate-900 border border-slate-600 text-white rounded-lg p-2.5">
                            <option value="NQ1!" selected>NQ1! (Nasdaq Futures)</option>
                            <option value="ES1!">ES1! (S&P Futures)</option>
                        </select>
                    </div>
                    <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
                        <label class="text-xs font-bold text-sky-400 uppercase">2. Strategy</label>
                        <select id="sel-strategy" onchange="updateSettings()" class="w-full mt-2 bg-slate-900 border border-slate-600 text-white rounded-lg p-2.5">
                            <option value="SWEEP" selected>Asia Liquidity Sweep</option>
                            <option value="STD_DEV">Std Deviation (Reversion)</option>
                        </select>
                    </div>
                    <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
                        <label class="text-xs font-bold text-sky-400 uppercase">3. Execution Mode</label>
                        <select id="sel-style" onchange="updateSettings()" class="w-full mt-2 bg-slate-900 border border-slate-600 text-white rounded-lg p-2.5">
                            <option value="SCALP">Scalp (Quick)</option>
                            <option value="SWING">Swing (Hold)</option>
                            <option value="SNIPER" selected>🎯 Sniper (High Precision)</option>
                        </select>
                    </div>
                </div>

                <div class="bg-slate-800 rounded-2xl shadow-xl border border-slate-700 p-6 flex flex-col md:flex-row gap-6">
                    <div class="w-full md:w-1/3 space-y-4">
                        <div class="bg-slate-700/50 p-4 rounded-lg">
                            <span class="text-xs text-slate-400">LIVE PRICE</span>
                            <div id="res-price" class="text-3xl font-mono font-bold text-white mt-1">---</div>
                        </div>
                        <div class="bg-slate-700/50 p-4 rounded-lg">
                            <span class="text-xs text-slate-400">SIGNAL BIAS</span>
                            <div id="res-bias" class="text-xl font-bold mt-1 text-slate-300">NEUTRAL</div>
                        </div>
                        <div class="bg-slate-700/50 p-4 rounded-lg">
                            <span class="text-xs text-slate-400">PROBABILITY</span>
                            <div id="res-prob" class="text-4xl font-bold text-sky-400 mt-1">---%</div>
                            <div class="w-full bg-slate-900 h-1.5 mt-2 rounded-full overflow-hidden"><div id="prob-bar" class="bg-sky-500 h-full w-0 transition-all duration-1000"></div></div>
                        </div>
                    </div>
                    
                    <div class="w-full md:w-2/3 flex flex-col gap-4">
                         <div class="bg-slate-700/30 rounded-lg border border-slate-600 p-4">
                            <div class="flex justify-between items-center mb-3">
                                <h4 class="text-xs font-bold text-sky-400 uppercase">Trade Setup</h4>
                                <span id="setup-validity" class="text-[10px] bg-slate-700 px-2 py-1 rounded">WAITING</span>
                            </div>
                            <div class="grid grid-cols-3 gap-3 text-center">
                                <div class="bg-slate-800 p-2 rounded"><div class="text-[10px] text-slate-400">ENTRY</div><div id="setup-entry" class="text-white font-bold">---</div></div>
                                <div class="bg-emerald-900/20 p-2 rounded border border-emerald-500/30"><div class="text-[10px] text-emerald-400">TP</div><div id="setup-tp" class="text-emerald-400 font-bold">---</div></div>
                                <div class="bg-rose-900/20 p-2 rounded border border-rose-500/30"><div class="text-[10px] text-rose-400">SL</div><div id="setup-sl" class="text-rose-400 font-bold">---</div></div>
                            </div>
                        </div>
                        <div class="bg-slate-700/30 rounded-lg border border-slate-600 p-6 flex-grow relative overflow-hidden">
                            <div class="absolute top-0 left-0 w-1 h-full bg-sky-500"></div>
                            <h3 class="text-lg font-bold text-white mb-4">🤖 AI Reasoning</h3>
                            <p id="res-reason" class="text-slate-300 font-light text-lg">Initializing V2 Logic...</p>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section id="architecture" class="py-16 bg-slate-50 border-t border-slate-200">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="mb-10">
                    <h2 class="text-3xl font-bold text-slate-900">V2 System Architecture</h2>
                    <p class="mt-4 text-slate-600">The updated 5-layer stack powering ForwardFin V2.</p>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
                    <div class="lg:col-span-5 space-y-3">
                        <div onclick="selectLayer(0)" class="arch-layer active bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">1. Data Ingestion</h4><p class="text-xs text-slate-500 mt-1">Yahoo Finance API (yfinance)</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(1)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">2. Analysis Engine</h4><p class="text-xs text-slate-500 mt-1">Pandas / NumPy (StdDev & Means)</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(2)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">3. V2 Strategy Core</h4><p class="text-xs text-slate-500 mt-1">Sniper Logic & Asia Sweeps</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(3)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">4. Alerting</h4><p class="text-xs text-slate-500 mt-1">Discord Webhooks</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                         <div onclick="selectLayer(4)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">5. Frontend</h4><p class="text-xs text-slate-500 mt-1">FastAPI / Tailwind / JS</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                    </div>
                    <div class="lg:col-span-7">
                        <div class="bg-white rounded-xl shadow-lg border border-slate-200 h-full p-6 flex flex-col">
                            <div class="flex justify-between items-center mb-4 border-b border-slate-100 pb-4">
                                <h3 id="detail-title" class="text-xl font-bold text-slate-800">Data Ingestion</h3>
                                <span id="detail-badge" class="px-2 py-1 bg-sky-100 text-sky-700 text-xs rounded font-mono">Infrastructure</span>
                            </div>
                            <p id="detail-desc" class="text-slate-600 mb-6 flex-grow">Connects to Yahoo Finance to fetch real-time 1-minute candle data for NQ=F and ES=F futures contracts.</p>
                            <h5 class="font-semibold text-slate-800 mb-3 text-sm uppercase">Tech Stack</h5>
                            <ul id="detail-list" class="space-y-3"></ul>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <footer class="bg-slate-900 text-slate-400 py-12 border-t border-slate-800 text-center">
            <p class="text-sm mb-6">ForwardFin V2 • Sniper Futures Intelligence</p>
            <div class="text-xs text-slate-600">&copy; 2026 ForwardFin.</div>
        </footer>
    </main>

    <script>
        // ARCHITECTURE DATA
        const architectureData = [
            { title: "Data Ingestion", badge: "Infrastructure", description: "Connects to Yahoo Finance to fetch real-time 1-minute candle data for NQ=F and ES=F futures contracts.", components: ["yfinance", "Python Requests"] },
            { title: "Analysis Engine", badge: "Data Science", description: "Calculates live Volatility, Moving Averages, and Standard Deviations for mean reversion logic.", components: ["Pandas Rolling", "NumPy Math"] },
            { title: "V2 Strategy Core", badge: "Logic", description: "Evaluates price against Asian Session Highs/Lows for 'Sweeps' or uses Statistical Bands for Reversals.", components: ["Sniper Mode", "Risk Calculator"] },
            { title: "Alerting Layer", badge: "Notification", description: "When V2 confidence is met, formats a rich embed with Entry, TP, and SL and fires to Discord.", components: ["Discord API", "JSON"] },
            { title: "Frontend", badge: "UI/UX", description: "Real-time dashboard allowing users to switch assets and strategies instantly.", components: ["FastAPI", "Tailwind CSS", "JavaScript"] }
        ];

        function selectLayer(index) {
            document.querySelectorAll('.arch-layer').forEach((el, i) => {
                if (i === index) el.classList.add('active', 'bg-sky-50', 'border-l-sky-600');
                else el.classList.remove('active', 'bg-sky-50', 'border-l-sky-600');
            });
            const data = architectureData[index];
            document.getElementById('detail-title').innerText = data.title;
            document.getElementById('detail-badge').innerText = data.badge;
            document.getElementById('detail-desc').innerText = data.description;
            const list = document.getElementById('detail-list');
            list.innerHTML = '';
            data.components.forEach(comp => { list.innerHTML += `<li class="flex items-start text-sm text-slate-700"><span class="w-1.5 h-1.5 bg-sky-500 rounded-full mt-1.5 mr-2"></span>${comp}</li>`; });
        }

        async function updateSettings() {
            const asset = document.getElementById('sel-asset').value;
            const strategy = document.getElementById('sel-strategy').value;
            const style = document.getElementById('sel-style').value;
            
            await fetch('/api/update-settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ asset, strategy, style })
            });
            updateDashboard();
        }

        let heroChart = null;
        function initHeroChart() {
            const ctx = document.getElementById('heroChart').getContext('2d');
            heroChart = new Chart(ctx, {
                type: 'doughnut',
                data: { datasets: [{ data: [0, 100], backgroundColor: ['#0ea5e9', '#e2e8f0'], borderWidth: 0 }] },
                options: { responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: { tooltip: { enabled: false } }, animation: { duration: 1000 } }
            });
        }

        async function updateDashboard() {
            try {
                const res = await fetch('/api/live-data');
                const data = await res.json();
                
                // Update Ticker
                document.getElementById('nav-ticker').innerHTML = `<span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> ${data.settings.asset}: $${data.market_data.price.toLocaleString()}`;
                
                // Update Style Icon
                const style = data.settings.style;
                document.getElementById('style-display').innerText = style === "SNIPER" ? "🎯" : (style === "SCALP" ? "⚡" : "🌊");
                document.getElementById('style-text').innerText = style;

                // Update Chart & Bias
                const prob = data.prediction.probability;
                document.getElementById('res-prob').innerText = prob + "%";
                document.getElementById('prob-bar').style.width = prob + "%";
                document.getElementById('res-bias').innerText = data.prediction.bias;
                document.getElementById('res-price').innerText = "$" + data.market_data.price.toLocaleString();
                document.getElementById('res-reason').innerText = data.prediction.narrative;
                
                if(heroChart) {
                    heroChart.data.datasets[0].data = [prob, 100-prob];
                    heroChart.data.datasets[0].backgroundColor = data.prediction.bias === "LONG" ? ['#10b981', '#e2e8f0'] : ['#f43f5e', '#e2e8f0'];
                    heroChart.update();
                }

                // Update Setup
                const setup = data.prediction.trade_setup;
                if(setup.valid) {
                     document.getElementById('setup-validity').innerText = "ACTIVE";
                     document.getElementById('setup-validity').className = "text-[10px] bg-emerald-600 px-2 py-1 rounded text-white";
                     document.getElementById('setup-entry').innerText = "$" + setup.entry.toLocaleString();
                     document.getElementById('setup-tp').innerText = "$" + setup.tp.toLocaleString();
                     document.getElementById('setup-sl').innerText = "$" + setup.sl.toLocaleString();
                } else {
                     document.getElementById('setup-validity').innerText = "WAITING";
                     document.getElementById('setup-validity').className = "text-[10px] bg-slate-700 px-2 py-1 rounded text-slate-400";
                }

                if (data.performance) {
                    const wr = data.performance.win_rate;
                    document.getElementById('win-rate').innerText = wr + "%";
                    document.getElementById('win-bar').style.width = wr + "%";
                }

            } catch(e) { console.log(e); }
        }

        document.addEventListener('DOMContentLoaded', () => {
            initHeroChart();
            selectLayer(0);
            updateDashboard();
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