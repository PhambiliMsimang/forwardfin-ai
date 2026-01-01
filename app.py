import threading
import uvicorn
import requests
import json
import time
import pandas as pd
import numpy as np
import yfinance as yf # NEW: For Stock Market Data
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pydantic import BaseModel

# --- 🔧 CONFIGURATION ---
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1454098742218330307/gi8wvEn0pMcNsAWIR_kY5-_0_VE4CvsgWjkSXjCasXX-xUrydbhYtxHRLLLgiKxs_pLL"

# --- 🧠 GLOBAL MEMORY & STATE ---
# We now store user preferences here
GLOBAL_STATE = {
    "settings": {
        "asset": "NS11",       # NS11 (Nasdaq) or ES11 (S&P 500)
        "strategy": "SWEEP",   # SWEEP (Asia Liquidity) or STD_DEV (Mean Reversion)
        "style": "SCALP"       # SCALP (Tight stops) or SWING (Wide stops)
    },
    "market_data": {
        "price": 0.00,
        "change": 0.00,
        "session_high": 0.00, # Mock Asia High
        "session_low": 0.00,  # Mock Asia Low
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

# Data Model for settings updates
class SettingsUpdate(BaseModel):
    asset: str
    strategy: str
    style: str

# --- 🔔 DISCORD ALERT SYSTEM (Optimized for V2) ---
def send_discord_alert(data, asset):
    if time.time() - GLOBAL_STATE["last_alert_time"] < 300: return # 5 min cooldown

    try:
        color = 5763719 if data['bias'] == "LONG" else 15548997
        strategy_name = "Asia Liquidity Sweep" if GLOBAL_STATE['settings']['strategy'] == "SWEEP" else "Standard Deviation Reversion"
        
        embed = {
            "title": f"🚨 V2 SIGNAL: {asset} {data['bias']}",
            "description": f"**Strategy:** {strategy_name}\n**Reasoning:** {data['narrative']}",
            "color": color,
            "fields": [
                {"name": "Entry", "value": f"${data['trade_setup']['entry']:,.2f}", "inline": True},
                {"name": "🎯 TP", "value": f"${data['trade_setup']['tp']:,.2f}", "inline": True},
                {"name": "🛑 SL", "value": f"${data['trade_setup']['sl']:,.2f}", "inline": True}
            ],
            "footer": {"text": "ForwardFin V2 • Futures Intelligence"}
        }
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
        GLOBAL_STATE["last_alert_time"] = time.time()
        print("✅ Discord Alert Sent!", flush=True)
    except Exception as e:
        print(f"❌ Discord Error: {e}", flush=True)

# --- WORKER 1: REAL MARKET DATA (Yahoo Finance) ---
def run_market_data_stream():
    print("📡 DATA THREAD: Connecting to Global Markets...", flush=True)
    while True:
        try:
            # Map user "NS11/ES11" to Yahoo Tickers
            ticker_map = {"NS11": "^IXIC", "ES11": "^GSPC"} # Nasdaq Composite / S&P 500
            current_asset = GLOBAL_STATE["settings"]["asset"]
            ticker = ticker_map.get(current_asset, "^IXIC")

            # Fetch Data
            data = yf.download(ticker, period="1d", interval="1m", progress=False)
            
            if not data.empty:
                current_price = float(data['Close'].iloc[-1])
                GLOBAL_STATE["market_data"]["price"] = current_price
                GLOBAL_STATE["market_data"]["history"] = data['Close'].tolist()
                
                # Mocking Session Highs (In production, you'd calculate this based on UTC time)
                GLOBAL_STATE["market_data"]["session_high"] = float(data['High'].max())
                GLOBAL_STATE["market_data"]["session_low"] = float(data['Low'].min())
                
                print(f"✅ TICK [{current_asset}]: ${current_price:,.2f}", flush=True)
            
        except Exception as e:
            print(f"⚠️ Data Error: {e}", flush=True)
        time.sleep(10) # Yahoo rate limit protection

# --- WORKER 2: THE V2 BRAIN (Logic Swap) ---
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

            # --- LOGIC SELECTION ---
            bias = "NEUTRAL"
            prob = 50
            narrative = "Analyzing market structure..."
            
            # 1. STRATEGY: ASIA SWEEP (Liquidity Grab)
            if settings["strategy"] == "SWEEP":
                # Logic: If price broke High but closed below -> Bearish Sweep
                high = market["session_high"]
                low = market["session_low"]
                
                # Simple simulation of sweep logic using recent history
                recent_high = max(history[-5:])
                recent_low = min(history[-5:])

                if recent_high >= high and current_price < high:
                    bias = "SHORT"
                    prob = 85
                    narrative = f"Detected Sweep of Session High ({high}). Price failed to hold above. Liquidity grabbed."
                elif recent_low <= low and current_price > low:
                    bias = "LONG"
                    prob = 85
                    narrative = f"Detected Sweep of Session Low ({low}). Price failed to hold below. Liquidity grabbed."
                else:
                    narrative = f"Price inside session range ({low:.0f} - {high:.0f}). Waiting for manipulation."

            # 2. STRATEGY: STANDARD DEVIATION (Mean Reversion)
            elif settings["strategy"] == "STD_DEV":
                series = pd.Series(history)
                mean = series.rolling(20).mean().iloc[-1]
                std = series.rolling(20).std().iloc[-1]
                upper_band = mean + (2 * std)
                lower_band = mean - (2 * std)

                if current_price > upper_band:
                    bias = "SHORT"
                    prob = 75
                    narrative = "Price extended +2 Std Dev from Mean. Statistical reversion likely."
                elif current_price < lower_band:
                    bias = "LONG"
                    prob = 75
                    narrative = "Price extended -2 Std Dev from Mean. Statistical reversion likely."
                else:
                    narrative = "Price within 2 Standard Deviations. No statistical edge."

            # --- RISK MANAGEMENT (SCALP vs SWING) ---
            tp_mult = 1.5 if settings["style"] == "SCALP" else 3.0
            sl_mult = 1.0 if settings["style"] == "SCALP" else 2.0
            volatility = pd.Series(history).diff().std() * 2 # Proxy for ATR

            if bias == "LONG":
                tp = current_price + (volatility * tp_mult)
                sl = current_price - (volatility * sl_mult)
            elif bias == "SHORT":
                tp = current_price - (volatility * tp_mult)
                sl = current_price + (volatility * sl_mult)
            else:
                tp = 0
                sl = 0

            GLOBAL_STATE["prediction"] = {
                "bias": bias,
                "probability": prob,
                "narrative": narrative,
                "trade_setup": {"entry": current_price, "tp": tp, "sl": sl, "valid": bias != "NEUTRAL"}
            }

            # --- TRADE EXECUTION (Paper) ---
            if prob >= 75 and bias != "NEUTRAL":
                 # Check if trade already exists recently
                if not any(t for t in GLOBAL_STATE["active_trades"] if time.time() - t['time'] < 300):
                    GLOBAL_STATE["active_trades"].append({
                        "type": bias, "entry": current_price, "time": time.time(), "asset": settings["asset"]
                    })
                    send_discord_alert(GLOBAL_STATE["prediction"], settings["asset"])

            # Grade Trades
            for trade in GLOBAL_STATE["active_trades"][:]:
                if time.time() - trade['time'] > 300: # 5 mins
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
    # Reset data for new asset
    GLOBAL_STATE["market_data"]["history"] = [] 
    return {"status": "success", "message": f"Switched to {settings.asset} using {settings.strategy}"}

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
        .chart-container { position: relative; width: 100%; max-width: 600px; margin: auto; height: 300px; }
        .arch-layer { transition: all 0.3s ease; cursor: pointer; border-left: 4px solid transparent; }
        .arch-layer:hover { background-color: #f1f5f9; transform: translateX(4px); }
        .arch-layer.active { background-color: #e0f2fe; border-left-color: #0284c7; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .lesson-card { cursor: pointer; transition: all 0.2s; border-left: 4px solid transparent; }
        .lesson-card:hover { background: #f1f5f9; }
        .lesson-card.active { background: #e0f2fe; border-left-color: #0284c7; }
        select { background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e"); background-position: right 0.5rem center; background-repeat: no-repeat; background-size: 1.5em 1.5em; padding-right: 2.5rem; -webkit-print-color-adjust: exact; }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 antialiased flex flex-col min-h-screen">

    <nav class="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-200 shadow-sm">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <div class="flex items-center gap-4">
                    <div class="h-10 w-10 bg-slate-900 rounded-lg flex items-center justify-center text-white font-bold text-xl">FF</div>
                    <div class="hidden md:block h-6 w-px bg-slate-300"></div>
                    <div id="nav-ticker" class="font-mono text-sm font-bold text-slate-600 flex items-center gap-2">
                        <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        Connecting...
                    </div>
                </div>
                <div class="hidden md:flex space-x-8 text-sm font-medium text-slate-600">
                    <a href="#overview" class="hover:text-sky-600 transition-colors">Terminal</a>
                    <a href="#simulation" class="hover:text-sky-600 transition-colors">Analysis</a>
                    <a href="#academy" class="hover:text-sky-600 transition-colors">Academy</a>
                    <a href="#architecture" class="hover:text-sky-600 transition-colors">Architecture</a>
                </div>
            </div>
        </div>
    </nav>

    <main class="flex-grow">
        <section id="overview" class="pt-20 pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
                <div class="space-y-6">
                    <div id="hero-badge" class="inline-flex items-center px-3 py-1 rounded-full bg-sky-100 text-sky-700 text-xs font-semibold uppercase tracking-wide">
                        V2 UPDATE: FUTURES & STOCKS ENABLED
                    </div>
                    <h1 class="text-4xl sm:text-5xl font-extrabold text-slate-900 leading-tight">
                        Institutional Grade,<br>
                        <span class="text-sky-600">Futures Intelligence.</span>
                    </h1>
                    <p class="text-lg text-slate-600 max-w-lg">
                        ForwardFin V2 tracks <strong>Nasdaq (NS11)</strong> and <strong>S&P 500 (ES11)</strong> using advanced statistical models and session liquidity sweeps.
                    </p>
                </div>
                <div class="grid grid-cols-3 gap-4">
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Algorithm Confidence</h3>
                        <div style="height: 100px; width: 100px; position: relative;"><canvas id="heroChart"></canvas></div>
                        <p id="hero-bias" class="text-sm font-bold text-slate-800 mt-2">---</p>
                    </div>
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Strategy Risk</h3>
                        <div class="h-[100px] w-[100px] flex items-center justify-center relative">
                            <div class="absolute inset-0 rounded-full border-8 border-slate-100"></div>
                            <div id="risk-circle" class="absolute inset-0 rounded-full border-8 border-transparent border-t-emerald-500 transition-all duration-700 rotate-45"></div>
                            <div class="text-center z-10"><span id="risk-text" class="text-xl font-black text-emerald-500">LOW</span></div>
                        </div>
                        <p class="text-xs text-slate-400 mt-2">Based on StdDev</p>
                    </div>
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center justify-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">V2 Accuracy</h3>
                        <div class="text-center my-2"><span id="win-rate" class="text-4xl font-black text-slate-800">0%</span></div>
                        <div class="w-full bg-slate-100 h-2 rounded-full overflow-hidden mt-1 mb-2"><div id="win-bar" class="bg-slate-800 h-full w-0 transition-all duration-1000"></div></div>
                        <p id="total-trades" class="text-xs text-slate-400">Calibrating...</p>
                    </div>
                </div>
            </div>
        </section>

        <section class="py-10 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
            <div class="bg-slate-900 rounded-2xl shadow-2xl border border-slate-800 overflow-hidden">
                <div class="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/50 backdrop-blur">
                    <h3 class="font-bold text-white flex items-center gap-2"><span>📈</span> Market Data</h3>
                    <span class="text-xs text-slate-500 font-mono">SOURCE: TRADINGVIEW / YAHOO</span>
                </div>
                <div class="h-[500px] w-full" id="tradingview_chart"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                <script type="text/javascript">
                new TradingView.widget({ "autosize": true, "symbol": "NASDAQ:NDX", "interval": "5", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "hide_side_toolbar": false, "allow_symbol_change": true, "container_id": "tradingview_chart", "studies": ["BB@tv-basicstudies"] });
                </script>
            </div>
        </section>

        <section id="simulation" class="py-20 bg-slate-900 text-white">
            <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="text-center mb-10">
                    <h2 class="text-3xl font-bold">V2 Trade Architect</h2>
                    <p class="mt-2 text-slate-400">Configure your strategy parameters below.</p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
                        <label class="text-xs font-bold text-sky-400 uppercase tracking-wide">1. Select Asset</label>
                        <select id="sel-asset" onchange="updateSettings()" class="w-full mt-2 bg-slate-900 border border-slate-600 text-white text-sm rounded-lg focus:ring-sky-500 focus:border-sky-500 block p-2.5">
                            <option value="NS11" selected>NS11 (Nasdaq 100)</option>
                            <option value="ES11">ES11 (S&P 500)</option>
                        </select>
                    </div>
                    <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
                        <label class="text-xs font-bold text-sky-400 uppercase tracking-wide">2. Strategy Logic</label>
                        <select id="sel-strategy" onchange="updateSettings()" class="w-full mt-2 bg-slate-900 border border-slate-600 text-white text-sm rounded-lg focus:ring-sky-500 focus:border-sky-500 block p-2.5">
                            <option value="SWEEP" selected>Asia Liquidity Sweep</option>
                            <option value="STD_DEV">Std Deviation (Mean Rev)</option>
                        </select>
                    </div>
                    <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
                        <label class="text-xs font-bold text-sky-400 uppercase tracking-wide">3. Trade Duration</label>
                        <select id="sel-style" onchange="updateSettings()" class="w-full mt-2 bg-slate-900 border border-slate-600 text-white text-sm rounded-lg focus:ring-sky-500 focus:border-sky-500 block p-2.5">
                            <option value="SCALP" selected>Scalp (Tight Stops)</option>
                            <option value="SWING">Swing (Wide Stops)</option>
                        </select>
                    </div>
                </div>

                <div class="bg-slate-800 rounded-2xl shadow-2xl overflow-hidden relative min-h-[400px] flex flex-col border border-slate-700">
                    <div class="p-4 border-b border-slate-700 bg-slate-800/50 flex justify-between items-center">
                        <div class="font-mono text-sky-400">ACTIVE: <span id="lbl-asset">NS11</span></div>
                        <div class="text-xs text-slate-500">Updating every 5s...</div>
                    </div>
                    <div class="flex-grow p-8 relative">
                        <div id="sim-results" class="h-full flex flex-col md:flex-row gap-6">
                            
                            <div class="w-full md:w-1/3 flex flex-col gap-4">
                                <div class="bg-slate-700/50 p-4 rounded-lg border border-slate-600">
                                    <span class="text-xs text-slate-400 uppercase">Live Price</span>
                                    <div id="res-price" class="text-3xl font-mono font-bold text-white mt-1">---</div>
                                </div>
                                <div class="bg-slate-700/50 p-4 rounded-lg border border-slate-600">
                                    <span class="text-xs text-slate-400 uppercase">Signal Bias</span>
                                    <div id="res-bias" class="text-xl font-bold mt-1 text-slate-300">NEUTRAL</div>
                                </div>
                                <div class="bg-slate-700/50 p-4 rounded-lg border border-slate-600">
                                    <span class="text-xs text-slate-400 uppercase">Algorithm Confidence</span>
                                    <div id="res-prob" class="text-4xl font-bold text-sky-400 mt-1">---%</div>
                                    <div class="w-full bg-slate-900 h-1.5 mt-2 rounded-full overflow-hidden">
                                        <div id="prob-bar" class="bg-sky-500 h-full w-0 transition-all duration-1000"></div>
                                    </div>
                                </div>
                            </div>

                            <div class="w-full md:w-2/3 flex flex-col gap-4">
                                <div class="bg-slate-700/30 rounded-lg border border-slate-600 p-4">
                                    <div class="flex justify-between items-center mb-3">
                                        <h4 class="text-xs font-bold text-sky-400 uppercase">Projected Trade Setup</h4>
                                        <span id="setup-validity" class="text-[10px] bg-slate-700 px-2 py-1 rounded">WAITING</span>
                                    </div>
                                    <div class="grid grid-cols-3 gap-3 text-center">
                                        <div class="bg-slate-800 p-2 rounded border border-slate-600">
                                            <div class="text-[10px] text-slate-400">ENTRY</div>
                                            <div id="setup-entry" class="text-white font-bold">---</div>
                                        </div>
                                        <div class="bg-emerald-900/20 p-2 rounded border border-emerald-500/30">
                                            <div class="text-[10px] text-emerald-400">TAKE PROFIT</div>
                                            <div id="setup-tp" class="text-emerald-400 font-bold">---</div>
                                        </div>
                                        <div class="bg-rose-900/20 p-2 rounded border border-rose-500/30">
                                            <div class="text-[10px] text-rose-400">STOP LOSS</div>
                                            <div id="setup-sl" class="text-rose-400 font-bold">---</div>
                                        </div>
                                    </div>
                                </div>

                                <div class="bg-slate-700/30 rounded-lg border border-slate-600 p-6 relative overflow-hidden flex-grow">
                                    <div class="absolute top-0 left-0 w-1 h-full bg-sky-500"></div>
                                    <h3 class="text-lg font-bold text-white mb-4 flex items-center gap-2"><span>🤖</span> AI Narrative</h3>
                                    <p id="res-reason" class="text-slate-300 leading-relaxed font-light text-lg">Initializing V2 Logic...</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section id="academy" class="py-16 bg-white border-t border-slate-200">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="text-center mb-12">
                    <h2 class="text-3xl font-bold text-slate-900">ForwardFin Academy</h2>
                    <p class="mt-4 text-slate-600 max-w-2xl mx-auto">Mastering the new V2 Concepts.</p>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 h-[500px]">
                     <div class="lg:col-span-4 bg-slate-50 border border-slate-200 rounded-xl overflow-hidden overflow-y-auto">
                        <div onclick="loadLesson(0)" class="lesson-card p-4 border-b border-slate-200 active">
                            <h4 class="font-bold text-slate-800">1. The Asia Sweep</h4>
                            <p class="text-xs text-slate-500 mt-1">Why we wait for the fakeout.</p>
                        </div>
                        <div onclick="loadLesson(1)" class="lesson-card p-4 border-b border-slate-200">
                            <h4 class="font-bold text-slate-800">2. Standard Deviation</h4>
                            <p class="text-xs text-slate-500 mt-1">Trading mean reversion.</p>
                        </div>
                    </div>
                    <div class="lg:col-span-8 bg-white border border-slate-200 rounded-xl p-8 flex flex-col shadow-sm">
                        <h3 id="lesson-title" class="text-2xl font-bold text-sky-600 mb-4">Select a Lesson</h3>
                        <div id="lesson-body" class="text-slate-600 leading-relaxed mb-8 flex-grow overflow-y-auto">
                            Click a module on the left.
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <footer class="bg-slate-900 text-slate-400 py-12 border-t border-slate-800 text-center">
            <p class="text-sm mb-6">ForwardFin V2 • Powered by Python & Yahoo Finance</p>
            <div class="text-xs text-slate-600">&copy; 2026 ForwardFin.</div>
        </footer>

    </main>

    <script>
        // --- 1. SETTINGS MANAGEMENT ---
        async function updateSettings() {
            const asset = document.getElementById('sel-asset').value;
            const strategy = document.getElementById('sel-strategy').value;
            const style = document.getElementById('sel-style').value;
            
            document.getElementById('lbl-asset').innerText = asset;

            await fetch('/api/update-settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ asset, strategy, style })
            });
        }

        // --- 2. LIVE DASHBOARD UPDATES ---
        let globalConfidence = 0;
        let heroChart = null;

        function initHeroChart() {
            const ctx = document.getElementById('heroChart').getContext('2d');
            heroChart = new Chart(ctx, {
                type: 'doughnut',
                data: { labels: ['Confidence', 'Uncertainty'], datasets: [{ data: [0, 100], backgroundColor: ['#0ea5e9', '#e2e8f0'], borderWidth: 0 }] },
                options: { responsive: true, maintainAspectRatio: false, cutout: '75%', plugins: { legend: { display: false }, tooltip: { enabled: false } }, animation: { duration: 1000 } },
                plugins: [{
                    id: 'textCenter',
                    beforeDraw: function(chart) {
                        var width = chart.width, height = chart.height, ctx = chart.ctx;
                        ctx.restore();
                        var fontSize = (height / 100).toFixed(2);
                        ctx.font = "bold " + fontSize + "em sans-serif";
                        ctx.textBaseline = "middle";
                        ctx.fillStyle = "#0f172a"; 
                        var text = globalConfidence + "%", textX = Math.round((width - ctx.measureText(text).width) / 2), textY = height / 2;
                        ctx.fillText(text, textX, textY);
                        ctx.save();
                    }
                }]
            });
        }

        async function fetchMarketData() {
            try {
                const response = await fetch('/api/live-data');
                const data = await response.json();
                return data;
            } catch (e) { console.error(e); return null; }
        }

        async function updateDashboard() {
            const data = await fetchMarketData();
            if (!data) return;

            const asset = data.settings.asset;
            const price = data.market_data.price;
            
            // Header Ticker
            document.getElementById('nav-ticker').innerHTML = `<span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> ${asset}: $${price.toLocaleString(undefined, {minimumFractionDigits: 2})}`;

            // Hero Chart
            globalConfidence = data.prediction.probability;
            document.getElementById('hero-bias').innerText = data.prediction.bias;
            if (heroChart) {
                heroChart.data.datasets[0].data = [globalConfidence, 100 - globalConfidence];
                heroChart.data.datasets[0].backgroundColor = (data.prediction.bias === "LONG") ? ['#10b981', '#e2e8f0'] : (data.prediction.bias === "SHORT") ? ['#f43f5e', '#e2e8f0'] : ['#64748b', '#e2e8f0'];
                heroChart.update();
            }

            // Analysis Section
            document.getElementById('res-price').innerText = "$" + price.toLocaleString(undefined, {minimumFractionDigits: 2});
            
            const biasEl = document.getElementById('res-bias');
            biasEl.innerText = data.prediction.bias;
            biasEl.className = (data.prediction.bias === "LONG") ? "text-xl font-bold mt-1 text-emerald-400" : (data.prediction.bias === "SHORT") ? "text-xl font-bold mt-1 text-rose-400" : "text-xl font-bold mt-1 text-slate-400";
            
            document.getElementById('res-prob').innerText = data.prediction.probability + "%";
            document.getElementById('prob-bar').style.width = data.prediction.probability + "%";
            document.getElementById('res-reason').innerText = data.prediction.narrative;

            // Setup Details
            const setup = data.prediction.trade_setup;
            const validEl = document.getElementById('setup-validity');
            if (setup && setup.valid) {
                validEl.innerText = "ACTIVE"; validEl.className = "text-[10px] bg-emerald-600 px-2 py-1 rounded text-white";
                document.getElementById('setup-entry').innerText = "$" + setup.entry.toLocaleString(undefined, {minimumFractionDigits: 2});
                document.getElementById('setup-tp').innerText = "$" + setup.tp.toLocaleString(undefined, {minimumFractionDigits: 2});
                document.getElementById('setup-sl').innerText = "$" + setup.sl.toLocaleString(undefined, {minimumFractionDigits: 2});
            } else {
                validEl.innerText = "WAITING"; validEl.className = "text-[10px] bg-slate-700 px-2 py-1 rounded text-slate-400";
            }
            
            // Win Rate
             if (data.performance) {
                const wr = data.performance.win_rate;
                document.getElementById('win-rate').innerText = wr + "%";
                document.getElementById('win-bar').style.width = wr + "%";
                document.getElementById('total-trades').innerText = `${data.performance.total} Simulated Trades`;
            }
        }

        // --- 3. ACADEMY CONTENT ---
        const lessons = [
            {
                title: "1. The Asia Sweep",
                body: "<b>The Concept:</b> Institutions need liquidity (orders) to enter large positions. They find this liquidity at the Highs and Lows of the Asian Session (overnight).<br><br><b>The Strategy:</b> We do NOT chase the breakout. We wait for price to break the Asian High, trap the breakout traders, and then CLOSE back inside the range. This is the 'Sweep'."
            },
            {
                title: "2. Standard Deviation",
                body: "<b>The Concept:</b> Markets are mean-reverting. Price can only stretch so far from the average before it snaps back.<br><br><b>The Strategy:</b> We calculate the Rolling Mean (20-period Average) and add 2 Standard Deviations above and below. If price touches the Upper Band, it is statistically expensive (Short). If it touches the Lower Band, it is cheap (Long)."
            }
        ];

        function loadLesson(index) {
            document.getElementById('lesson-title').innerText = lessons[index].title;
            document.getElementById('lesson-body').innerHTML = lessons[index].body;
            document.querySelectorAll('.lesson-card').forEach((el, i) => {
                if(i === index) el.classList.add('active', 'bg-sky-50', 'border-l-sky-600');
                else el.classList.remove('active', 'bg-sky-50', 'border-l-sky-600');
            });
        }

        document.addEventListener('DOMContentLoaded', () => {
            initHeroChart();
            loadLesson(0);
            updateDashboard();
            setInterval(updateDashboard, 5000); // 5s refresh
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
    print("🚀 FORWARDFIN V2 LAUNCHED: http://localhost:10000")
    uvicorn.run(app, host="0.0.0.0", port=10000)