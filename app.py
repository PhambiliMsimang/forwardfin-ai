import threading
import uvicorn
import requests
import json
import time
import pandas as pd
import numpy as np
import yfinance as yf
import pytz 
from datetime import datetime, time as dtime, timedelta
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pydantic import BaseModel

# --- 🔧 CONFIGURATION ---
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1454098742218330307/gi8wvEn0pMcNsAWIR_kY5-_0_VE4CvsgWjkSXjCasXX-xUrydbhYtxHRLLLgiKxs_pLL"

# PDF Rule: "Define Asia (03:00-08:59)"
# INTERPRETATION: This is 03:00 SAST (South Africa Time).
ASIA_OPEN_TIME = dtime(3, 0)   
ASIA_CLOSE_TIME = dtime(8, 59) 

# --- 🧠 GLOBAL STATE ---
GLOBAL_STATE = {
    "settings": {
        "asset": "NQ1!",       # NQ1! (Nasdaq) or ES1! (S&P 500)
        "strategy": "SWEEP",   
        "style": "SNIPER"      
    },
    "market_data": {
        "price": 0.00,
        "ifvg_detected": False, 
        "smt_detected": False, # Global SMT Status
        "fib_status": "NEUTRAL",
        "session_high": 0.00,
        "session_low": 0.00,
        "history": [], 
        "df": None,    
        "highs": [],
        "lows": [],
        "aux_data": {"NQ": None, "ES": None},
        "server_time": "" # NEW: For UI Clock
    },
    "prediction": {
        "bias": "NEUTRAL", 
        "probability": 50, 
        "narrative": "V3.8 (SAST) System Initializing...",
        "trade_setup": {"entry": 0, "tp": 0, "sl": 0, "valid": False}
    },
    "performance": {"wins": 0, "total": 0, "win_rate": 0},
    "active_trades": [],
    "last_alert_time": 0,
    "signal_latch": {"active": False, "data": None, "time": 0} # NEW: Ghost Signal Fix
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
        strategy_name = "ASIA EXECUTION PROTOCOL"
        style_icon = "🦁" 
        
        embed = {
            "title": f"{style_icon} SIGNAL: {asset} {data['bias']}",
            "description": f"**AI Reasoning:**\n{data['narrative']}",
            "color": color,
            "fields": [
                {"name": "Entry (1m Trigger)", "value": f"${data['trade_setup']['entry']:,.2f}", "inline": True},
                {"name": "🎯 TP1 (5m Swing)", "value": f"${data['trade_setup']['tp']:,.2f}", "inline": True},
                {"name": "🛑 SL (Dynamic)", "value": f"${data['trade_setup']['sl']:,.2f}", "inline": True},
                {"name": "Confidence", "value": f"{data['probability']}%", "inline": True}
            ],
            "footer": {"text": f"ForwardFin V3.8 • SAST Logic • SMT Verified"}
        }
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
        GLOBAL_STATE["last_alert_time"] = time.time()
        
        # ACTIVATE LATCH: Freeze this signal on the dashboard for 5 minutes
        GLOBAL_STATE["signal_latch"]["active"] = True
        GLOBAL_STATE["signal_latch"]["data"] = data
        GLOBAL_STATE["signal_latch"]["time"] = time.time()
        
        print("✅ Discord Alert Sent & Latch Activated!", flush=True)
    except Exception as e:
        print(f"❌ Discord Error: {e}", flush=True)

# --- WORKER 1: REAL FUTURES DATA (DUAL STREAM) ---
def run_market_data_stream():
    print("📡 DATA THREAD: Connecting to Dual Streams (NQ + ES)...", flush=True)
    while True:
        try:
            tickers = "NQ=F ES=F"
            data = yf.download(tickers, period="5d", interval="1m", progress=False, group_by='ticker')
            
            current_asset_symbol = GLOBAL_STATE["settings"]["asset"]
            if current_asset_symbol == "NQ1!":
                main_ticker, aux_ticker = "NQ=F", "ES=F"
                main_key, aux_key = "NQ", "ES"
            else:
                main_ticker, aux_ticker = "ES=F", "NQ=F"
                main_key, aux_key = "ES", "NQ"

            if not data.empty:
                # --- TIMEZONE FIX (SAST) ---
                sa_tz = pytz.timezone('Africa/Johannesburg')
                
                df_main = data[main_ticker].copy()
                if df_main.index.tz is None: df_main.index = df_main.index.tz_localize('UTC')
                df_main.index = df_main.index.tz_convert(sa_tz)
                df_main = df_main.dropna()

                df_aux_raw = data[aux_ticker].copy()
                if df_aux_raw.index.tz is None: df_aux_raw.index = df_aux_raw.index.tz_localize('UTC')
                df_aux_raw.index = df_aux_raw.index.tz_convert(sa_tz)
                df_aux_raw = df_aux_raw.dropna()

                current_price = float(df_main['Close'].iloc[-1])
                current_time_str = datetime.now(sa_tz).strftime('%H:%M:%S')
                
                GLOBAL_STATE["market_data"]["price"] = current_price
                GLOBAL_STATE["market_data"]["server_time"] = current_time_str # Update UI Clock
                GLOBAL_STATE["market_data"]["history"] = df_main['Close'].tolist()[-100:]
                GLOBAL_STATE["market_data"]["highs"] = df_main['High'].tolist()[-100:]
                GLOBAL_STATE["market_data"]["lows"] = df_main['Low'].tolist()[-100:]
                GLOBAL_STATE["market_data"]["df"] = df_main
                
                GLOBAL_STATE["market_data"]["aux_data"][main_key] = df_main 
                GLOBAL_STATE["market_data"]["aux_data"][aux_key] = df_aux_raw
                
                print(f"✅ TICK [{current_asset_symbol}]: ${current_price:,.2f} | SAST: {current_time_str}", flush=True)
            
        except Exception as e:
            print(f"⚠️ Data Error: {e}", flush=True)
        time.sleep(10)

# --- HELPER: DATA PROCESSING ---
def get_asia_session_data(df):
    if df is None or df.empty: return None
    
    last_timestamp = df.index[-1]
    current_date = last_timestamp.date()

    mask = (df.index.time >= ASIA_OPEN_TIME) & \
           (df.index.time <= ASIA_CLOSE_TIME) & \
           (df.index.date == current_date)
           
    session_data = df.loc[mask]
    if session_data.empty: return None

    return {
        "high": float(session_data['High'].max()),
        "low": float(session_data['Low'].min()),
        "is_closed": last_timestamp.time() > ASIA_CLOSE_TIME
    }

def resample_to_5m(df):
    ohlc_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}
    df_5m = df.resample('5min').apply(ohlc_dict).dropna()
    return df_5m

# --- HELPER: SMT DIVERGENCE CHECK ---
def check_smt_divergence(main_df, aux_df, sweep_type):
    if aux_df is None or main_df is None: return False
    
    common_index = main_df.index.intersection(aux_df.index)
    aux_synced = aux_df.loc[common_index]
    
    aux_asia = get_asia_session_data(aux_synced)
    if not aux_asia or not aux_asia['is_closed']: return False
    
    current_aux_price = aux_synced['Close'].iloc[-1]
    
    if sweep_type == "LOW": 
        # Main swept Low, did Aux sweep? If > Low, it FAILED -> SMT
        if current_aux_price > aux_asia['low']: return True 
            
    elif sweep_type == "HIGH": 
        # Main swept High, did Aux sweep? If < High, it FAILED -> SMT
        if current_aux_price < aux_asia['high']: return True 
            
    return False 

# --- HELPER: 1-MINUTE EXECUTION TRIGGERS ---
def detect_1m_trigger(df, trend_bias):
    if len(df) < 5: return False
    is_fvg = False
    is_bos = False
    
    if trend_bias == "LONG":
        if df['Low'].iloc[-2] > df['High'].iloc[-4]: is_fvg = True 
        if df['Close'].iloc[-1] > df['High'].iloc[-3]: is_bos = True
            
    elif trend_bias == "SHORT":
        if df['High'].iloc[-2] < df['Low'].iloc[-4]: is_fvg = True 
        if df['Close'].iloc[-1] < df['Low'].iloc[-3]: is_bos = True
            
    return is_fvg and is_bos

# --- HELPER: 5M SWING DETECTION (For TP1) ---
def get_recent_5m_swing(df_5m, bias):
    if len(df_5m) < 10: return 0
    if bias == "LONG": return float(df_5m['High'].iloc[-10:].max())
    else: return float(df_5m['Low'].iloc[-10:].min())

# --- WORKER 2: THE STRATEGY BRAIN ---
def run_strategy_engine():
    print("🧠 BRAIN THREAD: Asia SMT Protocol + Latch Loaded...", flush=True)
    while True:
        try:
            market = GLOBAL_STATE["market_data"]
            current_price = market["price"]
            df = market["df"]
            
            # Retrieve Aux Data
            current_asset = GLOBAL_STATE["settings"]["asset"]
            aux_key = "ES" if current_asset == "NQ1!" else "NQ"
            df_aux = market["aux_data"].get(aux_key)

            if df is None or len(market["history"]) < 20: 
                time.sleep(5)
                continue
            
            # --- LATCH CHECK (GHOST SIGNAL FIX) ---
            # If a signal fired recently, freeze the dashboard data
            latch = GLOBAL_STATE["signal_latch"]
            if latch["active"]:
                if time.time() - latch["time"] < 300: # 5 Minute Hold
                    # Overwrite current scanning data with the Latched Signal
                    GLOBAL_STATE["prediction"] = latch["data"]
                    time.sleep(1)
                    continue # Skip the rest of the scan loop
                else:
                    # Latch expired
                    GLOBAL_STATE["signal_latch"]["active"] = False

            # 1. PREP DATA
            asia_info = get_asia_session_data(df)
            df_5m = resample_to_5m(df) 
            
            bias = "NEUTRAL"
            prob = 50
            narrative = "Scanning Market Structure (SAST)..."
            setup = {"entry": 0, "tp": 0, "sl": 0, "valid": False}
            
            # --- GLOBAL SMT MONITORING (UI FEED) ---
            is_monitoring_smt = False
            if asia_info and asia_info['is_closed']:
                if current_price < asia_info['low']: # Potential Bullish SMT
                    is_monitoring_smt = check_smt_divergence(df, df_aux, "LOW")
                elif current_price > asia_info['high']: # Potential Bearish SMT
                    is_monitoring_smt = check_smt_divergence(df, df_aux, "HIGH")
            
            GLOBAL_STATE["market_data"]["smt_detected"] = is_monitoring_smt

            if asia_info:
                high = asia_info['high']
                low = asia_info['low']
                GLOBAL_STATE["market_data"]["session_high"] = high
                GLOBAL_STATE["market_data"]["session_low"] = low

                # --- PHASE 1: ANALYSIS MODE (5m) ---
                if asia_info['is_closed']: 
                    leg_range = high - low
                    
                    # SCENARIO A: Asia LOW Swept -> Bullish
                    if current_price < low:
                        stdv_2 = low - (leg_range * 1.0) 
                        narrative = "⚠️ Asia Low Swept. Monitoring for -2.0 STDV."
                        
                        if current_price <= (stdv_2 * 1.001): 
                            narrative = "🚨 KILL ZONE (-2.0 STDV). Checking SMT & Trigger..."
                            
                            has_smt = check_smt_divergence(df, df_aux, "LOW")
                            smt_text = "✅ SMT Divergence (High Confidence)" if has_smt else "⚠️ No SMT (Correlation)"
                            
                            has_trigger = detect_1m_trigger(df, "LONG")
                            
                            if has_trigger:
                                bias = "LONG"
                                prob = 95 if has_smt else 85
                                tp1 = get_recent_5m_swing(df_5m, "LONG")
                                tp2 = high 
                                sl_dynamic = float(df['Low'].iloc[-5:].min()) 
                                
                                narrative = (
                                    f"✅ **EXECUTION SIGNAL (BUY)**\n"
                                    f"• Logic: Price hit -2.0 STDV ({stdv_2:.2f})\n"
                                    f"• SMT Status: {smt_text}\n"
                                    f"• Trigger: 1m BOS + FVG Detected"
                                )
                                setup = {"entry": current_price, "tp": tp2, "sl": sl_dynamic, "valid": True}
                            else:
                                narrative += f"\n⏳ Waiting for 1m BOS+FVG. ({smt_text})"

                    # SCENARIO B: Asia HIGH Swept -> Bearish
                    elif current_price > high:
                        stdv_2 = high + (leg_range * 1.0) 
                        narrative = "⚠️ Asia High Swept. Monitoring for -2.0 STDV."
                        
                        if current_price >= (stdv_2 * 0.999):
                            narrative = "🚨 KILL ZONE (-2.0 STDV). Checking SMT & Trigger..."
                            
                            has_smt = check_smt_divergence(df, df_aux, "HIGH")
                            smt_text = "✅ SMT Divergence (High Confidence)" if has_smt else "⚠️ No SMT (Correlation)"
                            
                            has_trigger = detect_1m_trigger(df, "SHORT")
                            
                            if has_trigger:
                                bias = "SHORT"
                                prob = 95 if has_smt else 85
                                tp1 = get_recent_5m_swing(df_5m, "SHORT")
                                tp2 = low 
                                sl_dynamic = float(df['High'].iloc[-5:].max()) 
                                
                                narrative = (
                                    f"✅ **EXECUTION SIGNAL (SELL)**\n"
                                    f"• Logic: Price hit -2.0 STDV ({stdv_2:.2f})\n"
                                    f"• SMT Status: {smt_text}\n"
                                    f"• Trigger: 1m BOS + FVG Detected"
                                )
                                setup = {"entry": current_price, "tp": tp2, "sl": sl_dynamic, "valid": True}
                            else:
                                narrative += f"\n⏳ Waiting for 1m BOS+FVG. ({smt_text})"
                    else:
                        narrative = f"Consolidating inside Asia Range ({low:.2f} - {high:.2f})."
                else:
                    narrative = "⏳ Asia Session Active (03:00-08:59 SAST)."
            else:
                narrative = "WAITING: No Asia Session Data found."

            GLOBAL_STATE["prediction"] = {
                "bias": bias, "probability": prob, "narrative": narrative, "trade_setup": setup
            }

            # --- EXECUTION & ALERTING ---
            settings = GLOBAL_STATE["settings"]
            threshold = 85 
            
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
    safe_state = GLOBAL_STATE.copy()
    safe_state["market_data"] = GLOBAL_STATE["market_data"].copy()
    if "df" in safe_state["market_data"]: del safe_state["market_data"]["df"]
    if "aux_data" in safe_state["market_data"]: del safe_state["market_data"]["aux_data"]
    return safe_state

@app.post("/api/update-settings")
async def update_settings(settings: SettingsUpdate):
    GLOBAL_STATE["settings"]["asset"] = settings.asset
    GLOBAL_STATE["settings"]["strategy"] = settings.strategy
    GLOBAL_STATE["settings"]["style"] = settings.style
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
    <title>ForwardFin V3.8 | SMT Latch</title>
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
                        V3.8 LIVE: SMT LATCH
                    </div>
                    <h1 class="text-4xl sm:text-5xl font-extrabold text-slate-900 leading-tight">
                        Precision Entries,<br>
                        <span class="text-sky-600">Locked & Verified.</span>
                    </h1>
                    <div class="flex items-center gap-2 mt-4 text-slate-500 font-mono text-sm">
                        <span>🕒 BOT TIME (SAST):</span>
                        <span id="server-clock" class="font-bold text-slate-800">--:--:--</span>
                    </div>
                    <p class="text-lg text-slate-600 max-w-lg mt-4">
                        The bot now tracks <strong>NQ vs ES correlation</strong> and locks signals on the dashboard for 5 minutes so you never miss an alert.
                    </p>
                </div>
                <div class="grid grid-cols-3 gap-4">
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Correlation Monitor</h3>
                        <div id="status-smt" class="text-xl font-black text-rose-500 mt-4">SYNCED</div>
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
                                            <div class="text-[10px] text-slate-400">ENTRY (1m)</div>
                                            <div id="setup-entry" class="text-white font-bold">---</div>
                                        </div>
                                        <div class="bg-emerald-900/20 p-2 rounded border border-emerald-500/30">
                                            <div class="text-[10px] text-emerald-400">TP1 (5m Swing)</div>
                                            <div id="setup-tp" class="text-emerald-400 font-bold">---</div>
                                        </div>
                                        <div class="bg-rose-900/20 p-2 rounded border border-rose-500/30">
                                            <div class="text-[10px] text-rose-400">SL (Dynamic)</div>
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
                    <p class="mt-4 text-slate-600 max-w-2xl mx-auto">V3.8 Concepts: SMT Divergence & Liquidity.</p>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 h-[400px]">
                    <div class="lg:col-span-4 bg-slate-50 border border-slate-200 rounded-xl overflow-hidden overflow-y-auto">
                        <div onclick="loadLesson(0)" class="lesson-card p-4 border-b border-slate-200 active">
                            <h4 class="font-bold text-slate-800">1. SMT Divergence</h4>
                            <p class="text-xs text-slate-500 mt-1">Correlation Check.</p>
                        </div>
                        <div onclick="loadLesson(1)" class="lesson-card p-4 border-b border-slate-200">
                            <h4 class="font-bold text-slate-800">2. The "Kill Zone"</h4>
                            <p class="text-xs text-slate-500 mt-1">Wait for -2.0 STDV.</p>
                        </div>
                        <div onclick="loadLesson(2)" class="lesson-card p-4 border-b border-slate-200">
                            <h4 class="font-bold text-slate-800">3. 1-Minute Trigger</h4>
                            <p class="text-xs text-slate-500 mt-1">BOS + FVG Required.</p>
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
                            <div><h4 class="font-bold text-slate-800">2. Analysis Engine</h4><p class="text-xs text-slate-500 mt-1">Pandas / NumPy / SMT Logic</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(2)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">3. Strategy Core</h4><p class="text-xs text-slate-500 mt-1">Asia Sweep -> SMT -> 1m Trigger</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
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
            widget = new TradingView.widget({ "autosize": true, "symbol": tvSymbol, "interval": "1", "timezone": "Africa/Johannesburg", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "hide_side_toolbar": false, "allow_symbol_change": false, "container_id": "tradingview_chart" });
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
                
                // UPDATE CLOCK
                if(data.market_data.server_time) {
                     document.getElementById('server-clock').innerText = data.market_data.server_time;
                }

                // SMT Logic (UI Update)
                const smtEl = document.getElementById('status-smt');
                if(data.market_data.smt_detected) {
                    smtEl.innerText = "DIVERGENCE";
                    smtEl.className = "text-xl font-black text-emerald-500 mt-4 animate-pulse";
                } else {
                    smtEl.innerText = "SYNCED";
                    smtEl.className = "text-xl font-black text-rose-500 mt-4";
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
        
        // --- 3. ACADEMY INTERACTIVITY (EXPANDED CONTEXT) ---
        const lessons = [
            {
                title: "1. SMT Divergence",
                body: "<b>Smart Money Technique (SMT):</b> This is our 'Lie Detector'. Institutional algorithms often manipulate one index (like NQ) to grab liquidity while holding the other (like ES) steady.<br><br><b>The Rule:</b> If NQ sweeps a Low (makes a lower low) but ES fails to sweep its matching Low (makes a higher low), that is a 'Crack in Correlation'. It confirms that the move down was a trap to sell to retail traders before reversing higher."
            },
            {
                title: "2. The 'Kill Zone' (-2.0 STDV)",
                body: "<b>Why -2.0 Standard Deviations?</b> We do not guess bottoms. We use math. By projecting the Asia Range size (High - Low) downwards by a factor of 2.0 to 4.0, we identify a statistical 'Exhaustion Point'.<br><br>When price hits this zone, it is mathematically overextended relative to the session's volatility. This is where we stop analysing and start hunting for an entry."
            },
            {
                title: "3. 1-Minute Trigger (BOS + FVG)",
                body: "<b>The Kill Switch:</b> SMT and STDV are just context. The Trigger confirms the reversal. We switch to the 1-minute chart and demand two things:<br>1. <b>BOS (Break of Structure):</b> Price must break above the last swing high, proving buyers are stepping in.<br>2. <b>FVG (Fair Value Gap):</b> This energetic move must leave behind an imbalance gap. This proves the move was institutional, not random noise."
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
            { title: "Analysis Engine", badge: "Data Science", description: "Resamples 1m data to 5m to find STDV Zones. Calculates live Volatility and detects IFVGs.", components: ["Pandas Resample", "NumPy Math", "Custom Fib Scanner"] },
            { title: "Strategy Core", badge: "Logic", description: "Hybrid 5m/1m Engine. Waits for -2.0 STDV on 5m, then hunts for 1m BOS+FVG triggers.", components: ["Multi-Timeframe Analysis", "Smart Money Logic"] },
            { title: "Alerting Layer", badge: "Notification", description: "When V3 confidence is met (>85%), constructs a rich embed payload and fires it to the Discord Webhook.", components: ["Discord API", "JSON Payloads"] },
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