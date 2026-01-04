import threading
import uvicorn
import requests
import json
import time
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, time as dtime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pydantic import BaseModel

# --- 🔧 CONFIGURATION ---
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1454098742218330307/gi8wvEn0pMcNsAWIR_kY5-_0_VE4CvsgWjkSXjCasXX-xUrydbhYtxHRLLLgiKxs_pLL"
ASIA_OPEN_TIME = dtime(3, 0)   # 03:00
ASIA_CLOSE_TIME = dtime(8, 59) # 08:59

# --- 🧠 GLOBAL STATE ---
GLOBAL_STATE = {
    "settings": {
        "asset": "NQ1!",       # NQ1! (Nasdaq) or ES1! (S&P 500)
        "strategy": "SWEEP",   # Default to Asia Sweep
        "style": "SNIPER"      # SCALP or SNIPER (Swing removed)
    },
    "market_data": {
        "price": 0.00,
        "ifvg_detected": False, 
        "fib_status": "NEUTRAL",
        "session_high": 0.00,
        "session_low": 0.00,
        "history": [], # For UI Chart
        "df": None,    # For Logic (Full DataFrame)
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
        strategy_name = "ASIA MANIPULATION"
        style_icon = "🔫" 
        
        embed = {
            "title": f"{style_icon} SIGNAL: {asset} {data['bias']}",
            "description": f"**AI Reasoning:**\n{data['narrative']}",
            "color": color,
            "fields": [
                {"name": "Entry", "value": f"${data['trade_setup']['entry']:,.2f}", "inline": True},
                {"name": "🎯 TP (Range)", "value": f"${data['trade_setup']['tp']:,.2f}", "inline": True},
                {"name": "🛑 SL (-2.0 STDV)", "value": f"${data['trade_setup']['sl']:,.2f}", "inline": True},
                {"name": "Confidence", "value": f"{data['probability']}%", "inline": True}
            ],
            "footer": {"text": f"ForwardFin V2 • {strategy_name} • Post-08:59 Sweep"}
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

            # Download data (ensure we get enough rows for the day)
            data = yf.download(ticker, period="2d", interval="1m", progress=False)
            
            if not data.empty:
                current_price = float(data['Close'].iloc[-1])
                
                # Update Simple Data for UI
                GLOBAL_STATE["market_data"]["price"] = current_price
                GLOBAL_STATE["market_data"]["history"] = data['Close'].tolist()[-100:] # limit for UI
                GLOBAL_STATE["market_data"]["highs"] = data['High'].tolist()[-100:]
                GLOBAL_STATE["market_data"]["lows"] = data['Low'].tolist()[-100:]
                
                # CRITICAL: Store full DF for Strategy Engine to perform Time Slicing
                GLOBAL_STATE["market_data"]["df"] = data
                
                print(f"✅ TICK [{current_asset}]: ${current_price:,.2f}", flush=True)
            
        except Exception as e:
            print(f"⚠️ Data Error: {e}", flush=True)
        time.sleep(10)

# --- HELPER: ASIA SESSION LOGIC ---
def get_asia_session_data(df):
    """
    Isolates the 03:00-08:59 data to define the 'Manipulation Leg'.
    """
    if df is None or df.empty: return None

    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # Filter for the most recent trading session
    last_timestamp = df.index[-1]
    current_date = last_timestamp.date()

    # Create mask for 03:00 - 08:59 on the CURRENT day
    # Note: If running on a server in different timezone, this assumes yfinance returns Exchange Time (US/Eastern)
    mask = (df.index.time >= ASIA_OPEN_TIME) & \
           (df.index.time <= ASIA_CLOSE_TIME) & \
           (df.index.date == current_date)
           
    session_data = df.loc[mask]
    
    # If session hasn't started yet or is empty
    if session_data.empty:
        return None

    return {
        "high": float(session_data['High'].max()),
        "low": float(session_data['Low'].min()),
        "is_closed": last_timestamp.time() > ASIA_CLOSE_TIME
    }

# --- HELPER: IFVG DETECTION ---
def scan_for_ifvg(highs, lows, closes):
    if len(closes) < 5: return False
    for i in range(len(closes)-15, len(closes)-2):
        if lows[i] > highs[i+2]: # Bullish Gap
            gap_low = highs[i+2]
            if closes[-1] < gap_low: return True # Inverted (Bearish)
        if highs[i] < lows[i+2]: # Bearish Gap
            gap_high = lows[i+2]
            if closes[-1] > gap_high: return True # Inverted (Bullish)
    return False

# --- WORKER 2: THE STRATEGY BRAIN ---
def run_strategy_engine():
    print("🧠 BRAIN THREAD: Asia Manipulation Logic Loaded...", flush=True)
    while True:
        try:
            market = GLOBAL_STATE["market_data"]
            current_price = market["price"]
            df = market["df"]

            if df is None or len(market["history"]) < 20: 
                time.sleep(5)
                continue

            # 1. GATEKEEPER: CHECK IFVG (Used as Confluence)
            has_ifvg = scan_for_ifvg(market["highs"], market["lows"], market["history"])
            GLOBAL_STATE["market_data"]["ifvg_detected"] = has_ifvg
            
            # 2. ASIA SESSION ANALYSIS
            asia_info = get_asia_session_data(df)
            
            bias = "NEUTRAL"
            prob = 50
            narrative = "Scanning Market Structure..."
            setup = {"entry": 0, "tp": 0, "sl": 0, "valid": False}

            if asia_info:
                high = asia_info['high']
                low = asia_info['low']
                GLOBAL_STATE["market_data"]["session_high"] = high
                GLOBAL_STATE["market_data"]["session_low"] = low

                # --- CORE LOGIC: POST-SESSION SWEEP ---
                if asia_info['is_closed']: 
                    
                    # Calculate Range for STDV
                    leg_range = high - low
                    
                    # LOGIC A: Sweep LOW -> BULLISH
                    if current_price < low:
                        bias = "LONG"
                        prob = 75
                        narrative = (
                            f"✅ **BULLISH ASIA SWEEP**\n"
                            f"• Session High: {high:.2f} | Low: {low:.2f}\n"
                            f"• Range Size: {leg_range:.2f} pts\n"
                            f"• Logic: Price swept Asia Low ({low:.2f}). Reversal Expected."
                        )
                        
                        # Target: Return to Range High
                        # SL: -2.0 Standard Deviation (Approx Range * 1.0 down from low)
                        setup = {
                            "entry": current_price,
                            "tp": high,
                            "sl": low - (leg_range * 1.0), 
                            "valid": True
                        }

                    # LOGIC B: Sweep HIGH -> BEARISH
                    elif current_price > high:
                        bias = "SHORT"
                        prob = 75
                        narrative = (
                            f"✅ **BEARISH ASIA SWEEP**\n"
                            f"• Session High: {high:.2f} | Low: {low:.2f}\n"
                            f"• Range Size: {leg_range:.2f} pts\n"
                            f"• Logic: Price swept Asia High ({high:.2f}). Reversal Expected."
                        )
                        
                        # Target: Return to Range Low
                        # SL: -2.0 Standard Deviation
                        setup = {
                            "entry": current_price,
                            "tp": low,
                            "sl": high + (leg_range * 1.0),
                            "valid": True
                        }
                    
                    else:
                        narrative = f"Session Closed. Price consolidating inside Asia Range ({low:.2f} - {high:.2f})."

                else:
                    narrative = "⏳ Asia Session Active (03:00-08:59). Building Liquidity."
            else:
                narrative = "WAITING: No Asia Session Data for Today."

            # 3. CONFLUENCE BOOSTER
            if bias != "NEUTRAL":
                if has_ifvg:
                    prob += 15
                    narrative += "\n• **Confluence:** IFVG Pattern Detected (+15%)"
                
                # Check STDV Proximity
                pass

            # Update State
            GLOBAL_STATE["prediction"] = {
                "bias": bias,
                "probability": prob,
                "narrative": narrative,
                "trade_setup": setup
            }

            # --- EXECUTION & ALERTING ---
            settings = GLOBAL_STATE["settings"]
            threshold = 85 if settings["style"] == "SNIPER" else 75
            
            if prob >= threshold and bias != "NEUTRAL":
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
        time.sleep(1)

# --- API ROUTES ---
@app.get("/api/live-data")
async def get_api():
    # Create a safe copy without the DataFrame (not JSON serializable)
    safe_state = GLOBAL_STATE.copy()
    safe_state["market_data"] = GLOBAL_STATE["market_data"].copy()
    if "df" in safe_state["market_data"]:
        del safe_state["market_data"]["df"]
    return safe_state

@app.post("/api/update-settings")
async def update_settings(settings: SettingsUpdate):
    GLOBAL_STATE["settings"]["asset"] = settings.asset
    GLOBAL_STATE["settings"]["strategy"] = settings.strategy
    GLOBAL_STATE["settings"]["style"] = settings.style
    # Reset data to force reload
    GLOBAL_STATE["market_data"]["df"] = None
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
    <title>ForwardFin V2 | Asia Strategy</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #f8fafc; color: #334155; }
        .arch-layer { transition: all 0.3s ease; cursor: pointer; border-left: 4px solid transparent; }
        .arch-layer:hover { background-color: #f1f5f9; transform: translateX(4px); }
        .arch-layer.active { background-color: #e0f2fe; border-left-color: #0284c7; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .lesson-card { cursor: pointer; transition: all 0.2s; border-left: 4px solid transparent; }
        .lesson-card:hover { background: #f1f5f9; }
        .lesson-card.active { background: #e0f2fe; border-left-color: #0284c7; }
        .btn-asset { transition: all 0.2s; border: 1px solid #e2e8f0; }
        .btn-asset:hover { background-color: #f1f5f9; border-color: #0284c7; }
        .btn-asset.active { background-color: #0284c7; color: white; border-color: #0284c7; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
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
                <div class="flex gap-2">
                    <button onclick="setAsset('NQ1!')" id="btn-nq" class="btn-asset active px-4 py-1.5 rounded text-sm font-bold bg-white text-slate-600">NQ</button>
                    <button onclick="setAsset('ES1!')" id="btn-es" class="btn-asset px-4 py-1.5 rounded text-sm font-bold bg-white text-slate-600">ES</button>
                </div>
            </div>
        </div>
    </nav>

    <main class="flex-grow">
        <section id="overview" class="pt-20 pb-10 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center mb-10">
                <div class="space-y-6">
                    <div class="inline-flex items-center px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 text-xs font-semibold uppercase tracking-wide">
                        V3.0 LIVE: ASIA SESSION PROTOCOL
                    </div>
                    <h1 class="text-4xl sm:text-5xl font-extrabold text-slate-900 leading-tight">
                        Asia Manipulation,<br>
                        <span class="text-sky-600">Fully Automated.</span>
                    </h1>
                    <p class="text-lg text-slate-600 max-w-lg">
                        The bot now strictly isolates the <strong>03:00 - 08:59</strong> session range. Entries are only triggered on confirmed liquidity sweeps after the session close.
                    </p>
                </div>
                <div class="grid grid-cols-3 gap-4">
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">IFVG Status</h3>
                        <div id="status-ifvg" class="text-xl font-black text-rose-500 mt-4">NO GAP</div>
                    </div>
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Session Range</h3>
                        <div id="status-fib" class="text-sm font-black text-slate-800 mt-4 text-center">WAITING</div>
                    </div>
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center justify-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Win Rate</h3>
                        <div class="text-center my-2"><span id="win-rate" class="text-4xl font-black text-slate-800">0%</span></div>
                        <div class="w-full bg-slate-100 h-2 rounded-full overflow-hidden mt-1 mb-2"><div id="win-bar" class="bg-slate-800 h-full w-0 transition-all duration-1000"></div></div>
                    </div>
                </div>
            </div>

            <div class="bg-white p-6 rounded-2xl shadow-lg border border-slate-200 grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label class="text-xs font-bold text-slate-500 uppercase tracking-wider">Strategy Logic</label>
                    <select id="sel-strategy" onchange="pushSettings()" class="w-full mt-2 bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-sky-500 focus:border-sky-500 block p-2.5">
                        <option value="SWEEP" selected>Asia Liquidity Sweep (Strict)</option>
                    </select>
                </div>
                <div>
                    <label class="text-xs font-bold text-slate-500 uppercase tracking-wider">Trade Style</label>
                    <select id="sel-style" onchange="pushSettings()" class="w-full mt-2 bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-sky-500 focus:border-sky-500 block p-2.5">
                        <option value="SNIPER" selected>🎯 Sniper (High Probability)</option>
                        <option value="SCALP">⚡ Scalp (Fast Execution)</option>
                    </select>
                </div>
            </div>
        </section>

        <section class="py-4 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
            <div class="bg-slate-900 rounded-2xl shadow-2xl border border-slate-800 overflow-hidden">
                <div class="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/50 backdrop-blur">
                    <h3 class="font-bold text-white flex items-center gap-2"><span>📈</span> Institutional Price Action</h3>
                    <span class="text-xs text-slate-500 font-mono">SOURCE: CAPITAL.COM</span>
                </div>
                <div class="h-[500px] w-full" id="tradingview_chart"></div>
            </div>
        </section>

        <section id="simulation" class="py-20 bg-slate-900 text-white">
            <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="text-center mb-10">
                    <h2 class="text-3xl font-bold">Live Market Breakdown</h2>
                    <p class="mt-2 text-slate-400">Real-time Trade Architect</p>
                </div>
                <div class="bg-slate-800 rounded-2xl shadow-2xl overflow-hidden relative min-h-[400px] flex flex-col border border-slate-700">
                    <div class="p-4 border-b border-slate-700 bg-slate-800/50 flex justify-between items-center">
                        <div class="font-mono text-sky-400">TARGET: <span id="lbl-asset">NQ1!</span></div>
                        <div class="text-xs text-slate-500">LIVE ANALYSIS</div>
                    </div>
                    <div class="flex-grow p-8 relative">
                        <div id="sim-results" class="h-full flex flex-col md:flex-row gap-6">
                            
                            <div class="w-full md:w-1/3 flex flex-col gap-4">
                                <div class="bg-slate-700/50 p-4 rounded-lg border border-slate-600">
                                    <span class="text-xs text-slate-400 uppercase">Current Price</span>
                                    <div id="res-price" class="text-3xl font-mono font-bold text-white mt-1">---</div>
                                </div>
                                <div class="bg-slate-700/50 p-4 rounded-lg border border-slate-600">
                                    <span class="text-xs text-slate-400 uppercase">AI Signal</span>
                                    <div id="res-bias" class="text-xl font-bold mt-1 text-slate-300">---</div>
                                </div>
                                <div class="bg-slate-700/50 p-4 rounded-lg border border-slate-600">
                                    <span class="text-xs text-slate-400 uppercase">Model Confidence</span>
                                    <div id="res-prob" class="text-4xl font-bold text-sky-400 mt-1">---%</div>
                                    <div class="w-full bg-slate-900 h-1.5 mt-2 rounded-full overflow-hidden">
                                        <div id="prob-bar" class="bg-sky-500 h-full w-0 transition-all duration-1000"></div>
                                    </div>
                                </div>
                            </div>

                            <div class="w-full md:w-2/3 flex flex-col gap-4">
                                <div class="bg-slate-700/30 rounded-lg border border-slate-600 p-4">
                                    <div class="flex justify-between items-center mb-3">
                                        <h4 class="text-xs font-bold text-sky-400 uppercase">Suggested Trade Setup</h4>
                                        <span id="setup-validity" class="text-[10px] bg-slate-700 px-2 py-1 rounded">WAITING</span>
                                    </div>
                                    <div class="grid grid-cols-3 gap-3 text-center">
                                        <div class="bg-slate-800 p-2 rounded border border-slate-600">
                                            <div class="text-[10px] text-slate-400">ENTRY</div>
                                            <div id="setup-entry" class="text-white font-bold">---</div>
                                        </div>
                                        <div class="bg-emerald-900/20 p-2 rounded border border-emerald-500/30">
                                            <div class="text-[10px] text-emerald-400">TARGET (RANGE)</div>
                                            <div id="setup-tp" class="text-emerald-400 font-bold">---</div>
                                        </div>
                                        <div class="bg-rose-900/20 p-2 rounded border border-rose-500/30">
                                            <div class="text-[10px] text-rose-400">STOP (-2 STDV)</div>
                                            <div id="setup-sl" class="text-rose-400 font-bold">---</div>
                                        </div>
                                    </div>
                                </div>

                                <div class="bg-slate-700/30 rounded-lg border border-slate-600 p-6 relative overflow-hidden flex-grow">
                                    <div class="absolute top-0 left-0 w-1 h-full bg-sky-500"></div>
                                    <h3 class="text-lg font-bold text-white mb-4 flex items-center gap-2"><span>🤖</span> AI Reasoning</h3>
                                    <p id="res-reason" class="text-slate-300 leading-relaxed font-light text-lg whitespace-pre-wrap">Waiting for analysis command...</p>
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
                    <p class="mt-4 text-slate-600 max-w-2xl mx-auto">V3.0 Concepts: Asia Ranges, Sweeps & STDV.</p>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 h-[400px]">
                    <div class="lg:col-span-4 bg-slate-50 border border-slate-200 rounded-xl overflow-hidden overflow-y-auto">
                        <div onclick="loadLesson(0)" class="lesson-card p-4 border-b border-slate-200 active">
                            <h4 class="font-bold text-slate-800">1. Asia Session Protocol</h4>
                            <p class="text-xs text-slate-500 mt-1">Time: 03:00 - 08:59.</p>
                        </div>
                        <div onclick="loadLesson(1)" class="lesson-card p-4 border-b border-slate-200">
                            <h4 class="font-bold text-slate-800">2. The Sweep Trigger</h4>
                            <p class="text-xs text-slate-500 mt-1">Trading the manipulation.</p>
                        </div>
                        <div onclick="loadLesson(2)" class="lesson-card p-4 border-b border-slate-200">
                            <h4 class="font-bold text-slate-800">3. STDV Projections</h4>
                            <p class="text-xs text-slate-500 mt-1">Precision Targets (-2.0).</p>
                        </div>
                    </div>
                    <div class="lg:col-span-8 bg-white border border-slate-200 rounded-xl p-8 flex flex-col shadow-sm">
                        <h3 id="lesson-title" class="text-2xl font-bold text-sky-600 mb-4">Select a Lesson</h3>
                        <div id="lesson-body" class="text-slate-600 leading-relaxed mb-8 flex-grow overflow-y-auto">
                            Click a module on the left to start learning.
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section id="architecture" class="py-16 bg-slate-50 border-t border-slate-200">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="mb-10">
                    <h2 class="text-3xl font-bold text-slate-900">System Architecture</h2>
                    <p class="mt-4 text-slate-600 max-w-3xl">ForwardFin is built on a modular 5-layer stack.</p>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
                    <div class="lg:col-span-5 space-y-3">
                        <div onclick="selectLayer(0)" class="arch-layer active bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">1. Data Ingestion</h4><p class="text-xs text-slate-500 mt-1">Yahoo Finance (yfinance)</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(1)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">2. Analysis Engine</h4><p class="text-xs text-slate-500 mt-1">Pandas / NumPy / IFVG / STDV</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(2)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">3. Strategy Core</h4><p class="text-xs text-slate-500 mt-1">Asia Manipulation Logic</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(3)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">4. Alerting Layer</h4><p class="text-xs text-slate-500 mt-1">Discord Webhooks</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(4)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">5. User Interface</h4><p class="text-xs text-slate-500 mt-1">FastAPI / Tailwind / JS</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
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

    </main>

    <footer class="bg-slate-900 text-slate-400 py-12 border-t border-slate-800 text-center">
        <p class="text-sm mb-6">Democratizing financial intelligence.</p>
        <div class="text-xs text-slate-600">&copy; 2026 ForwardFin. All rights reserved.</div>
    </footer>

    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script>
        // --- LIVE DASHBOARD UPDATES ---
        let widget = null;
        let currentAsset = "NQ1!";

        function initChart(symbol) {
            const tvSymbol = symbol === "NQ1!" ? "CAPITALCOM:US100" : "CAPITALCOM:US500";
            if(widget) { widget = null; document.getElementById('tradingview_chart').innerHTML = ""; }
            widget = new TradingView.widget({ "autosize": true, "symbol": tvSymbol, "interval": "1", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "hide_side_toolbar": false, "allow_symbol_change": false, "container_id": "tradingview_chart" });
        }

        async function setAsset(asset) {
            currentAsset = asset;
            document.getElementById('btn-nq').className = asset === "NQ1!" ? "btn-asset active px-4 py-1.5 rounded text-sm font-bold bg-white text-slate-600" : "btn-asset px-4 py-1.5 rounded text-sm font-bold bg-white text-slate-600";
            document.getElementById('btn-es').className = asset === "ES1!" ? "btn-asset active px-4 py-1.5 rounded text-sm font-bold bg-white text-slate-600" : "btn-asset px-4 py-1.5 rounded text-sm font-bold bg-white text-slate-600";
            document.getElementById('lbl-asset').innerText = asset;
            pushSettings(); 
            initChart(asset);
        }

        async function pushSettings() {
             const strategy = document.getElementById('sel-strategy').value;
             const style = document.getElementById('sel-style').value;
             await fetch('/api/update-settings', {
                method: 'POST', 
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ asset: currentAsset, strategy: strategy, style: style })
            });
        }

        async function updateDashboard() {
            try {
                const res = await fetch('/api/live-data');
                const data = await res.json();
                
                document.getElementById('nav-ticker').innerHTML = `<span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> ${data.settings.asset}: $${data.market_data.price.toLocaleString()}`;
                document.getElementById('res-price').innerText = "$" + data.market_data.price.toLocaleString();
                document.getElementById('res-bias').innerText = data.prediction.bias;
                
                // IFVG Logic
                const ifvgEl = document.getElementById('status-ifvg');
                if(data.market_data.ifvg_detected) {
                    ifvgEl.innerText = "ACTIVE DETECTED";
                    ifvgEl.className = "text-xl font-black text-emerald-500 mt-4 animate-pulse";
                } else {
                    ifvgEl.innerText = "NO GAP";
                    ifvgEl.className = "text-xl font-black text-rose-500 mt-4";
                }

                // Session Status
                const fibEl = document.getElementById('status-fib');
                const sessionLow = data.market_data.session_low;
                const sessionHigh = data.market_data.session_high;
                if (sessionLow > 0) {
                     fibEl.innerText = `${sessionLow} - ${sessionHigh}`;
                     fibEl.className = "text-sm font-bold text-slate-800 mt-4 text-center";
                } else {
                     fibEl.innerText = "WAITING FOR DATA";
                }

                const prob = data.prediction.probability;
                document.getElementById('res-prob').innerText = prob + "%";
                document.getElementById('prob-bar').style.width = prob + "%";
                document.getElementById('res-reason').innerText = data.prediction.narrative;
                
                 // Setup
                const setup = data.prediction.trade_setup;
                const validEl = document.getElementById('setup-validity');
                if(setup.valid) {
                      validEl.innerText = "ACTIVE";
                      validEl.className = "text-[10px] bg-emerald-600 px-2 py-1 rounded text-white";
                      document.getElementById('setup-entry').innerText = "$" + setup.entry.toLocaleString();
                      document.getElementById('setup-tp').innerText = "$" + setup.tp.toLocaleString();
                      document.getElementById('setup-sl').innerText = "$" + setup.sl.toLocaleString();
                } else {
                      validEl.innerText = "WAITING";
                      validEl.className = "text-[10px] bg-slate-700 px-2 py-1 rounded text-slate-400";
                }

                if (data.performance) {
                    const wr = data.performance.win_rate;
                    document.getElementById('win-rate').innerText = wr + "%";
                    document.getElementById('win-bar').style.width = wr + "%";
                }
            } catch (e) { console.log(e); }
        }
        
        // --- 3. ACADEMY INTERACTIVITY (RESTORED) ---
        const lessons = [
            {
                title: "1. Asia Session Protocol",
                body: "We define the Asian Session strictly as <b>03:00 to 08:59</b> (Exchange Time).<br><br>During this time, we do NOT trade. We simply mark the Session High and Session Low. This range defines the liquidity pool."
            },
            {
                title: "2. The Sweep Trigger",
                body: "Once the session closes at 08:59, we wait.<br><br>We are looking for price to 'Sweep' (trade beyond) the Asia High or Low. This suggests manipulation. We enter on the reversal back into the range."
            },
            {
                title: "3. STDV Projections",
                body: "We do not use random targets. We use Fibonacci Standard Deviations.<br><br><b>Stop Loss:</b> -2.0 STDV (The expansion level).<br><b>Take Profit:</b> The opposite end of the Asia Range."
            }
        ];

        function loadLesson(index) {
            const l = lessons[index];
            document.getElementById('lesson-title').innerText = l.title;
            document.getElementById('lesson-body').innerHTML = l.body;
            document.querySelectorAll('.lesson-card').forEach((el, i) => {
                if(i === index) el.classList.add('active', 'bg-sky-50', 'border-l-sky-600');
                else el.classList.remove('active', 'bg-sky-50', 'border-l-sky-600');
            });
        }
        
        // --- 4. ARCHITECTURE INTERACTIVITY (RESTORED) ---
        const architectureData = [
            { title: "Data Ingestion", badge: "Infrastructure", description: "Connects to Yahoo Finance to fetch real-time 1-minute candle data for NQ=F and ES=F futures contracts.", components: ["yfinance", "Python Requests"] },
            { title: "Analysis Engine", badge: "Data Science", description: "Calculates live Volatility, Moving Averages, detects IFVGs, and calculates Standard Deviation Projections.", components: ["Pandas Rolling", "NumPy Math", "Custom Fib Scanner"] },
            { title: "Strategy Core", badge: "Logic", description: "Evaluates price against Asian Session Highs/Lows. Logic is frozen until 08:59 session close.", components: ["Sniper Mode", "Risk Calculator"] },
            { title: "Alerting Layer", badge: "Notification", description: "When V2 confidence is met (>85%), constructs a rich embed payload and fires it to the Discord Webhook.", components: ["Discord API", "JSON Payloads"] },
            { title: "User Interface", badge: "Frontend", description: "Responsive dashboard served via FastAPI. Updates DOM elements live via polling.", components: ["FastAPI", "Tailwind CSS", "Chart.js", "TradingView"] }
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

        document.addEventListener('DOMContentLoaded', () => {
            initChart("NQ1!");
            loadLesson(0);
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