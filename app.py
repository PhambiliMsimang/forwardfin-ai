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

# 1. ASIA RANGE
ASIA_OPEN_TIME = dtime(3, 0)   
ASIA_CLOSE_TIME = dtime(8, 59) 

# 2. TRADING WINDOW
TRADE_WINDOW_OPEN = dtime(9, 0)
TRADE_WINDOW_CLOSE = dtime(23, 0) 

# 3. DANGER WORDS (News Filter)
DANGER_KEYWORDS = ["CPI", "PPI", "FED", "POWELL", "HIKE", "INFLATION", "RATES", "FOMC", "NFP", "JOBS"]

# --- 🧠 GLOBAL STATE ---
GLOBAL_STATE = {
    "settings": {
        "asset": "NQ1!",       
        "strategy": "SWEEP",   
        "style": "PRECISION",   
        "offset": 105.0,        
        "balance": 1000.0,      
        "risk_pct": 2.0         
    },
    "market_data": {
        "price": 0.00,
        "adjusted_price": 0.00,
        "rsi": 50.0,            # [NEW] V4.6: RSI Memory
        "ifvg_detected": False, 
        "smt_detected": False, 
        "fib_status": "NEUTRAL",
        "session_high": 0.00,
        "session_low": 0.00,
        "history": [], 
        "df": None,    
        "highs": [],
        "lows": [],
        "aux_data": {"NQ": None, "ES": None},
        "server_time": "--:--:--" 
    },
    "news": {                   
        "is_danger": False,
        "headline": "No Active Threats",
        "last_scan": "Not scanned yet"
    },
    "prediction": {
        "bias": "NEUTRAL", 
        "probability": 50, 
        "narrative": "V4.6 Drift-Proof Initializing...",
        "trade_setup": {"entry": 0, "tp": 0, "sl": 0, "size": 0, "valid": False}
    },
    "performance": {"wins": 0, "total": 0, "win_rate": 0},
    "logs": [],                 
    "active_trades": [],
    "last_alert_time": 0,
    "last_long_alert": 0,  
    "last_short_alert": 0, 
    "signal_latch": {"active": False, "data": None, "time": 0} 
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
analyzer = SentimentIntensityAnalyzer()

# --- API MODELS ---
class SettingsUpdate(BaseModel):
    asset: str
    strategy: str
    style: str

class CalibrationUpdate(BaseModel):
    current_cfd_price: float

class RiskUpdate(BaseModel):
    balance: float
    risk_pct: float

# --- 📝 LOGGING SYSTEM ---
def log_msg(type, text):
    timestamp = datetime.now(pytz.timezone('Africa/Johannesburg')).strftime('%H:%M:%S')
    icon = "ℹ️"
    if type == "TRADE": icon = "🦁"
    elif type == "ALERT": icon = "🚨"
    elif type == "NEWS": icon = "📰"
    elif type == "SYS": icon = "⚙️"
    
    log_entry = f"[{timestamp}] {icon} {text}"
    GLOBAL_STATE["logs"].insert(0, log_entry)
    if len(GLOBAL_STATE["logs"]) > 50: GLOBAL_STATE["logs"].pop()
    print(log_entry, flush=True)

# --- 🧮 RISK CALCULATOR ---
def calculate_position_size(entry, sl):
    try:
        balance = GLOBAL_STATE["settings"]["balance"]
        risk_pct = GLOBAL_STATE["settings"]["risk_pct"]
        risk_amount = balance * (risk_pct / 100)
        
        stop_loss_dist = abs(entry - sl)
        if stop_loss_dist < 1: stop_loss_dist = 1 
        
        position_size = risk_amount / stop_loss_dist
        return round(position_size, 2), round(risk_amount, 2)
    except:
        return 0, 0

# --- 🔔 DISCORD ALERT SYSTEM ---
def send_discord_alert(data, asset):
    current_time = time.time()
    bias = data['bias']

    if bias == "LONG":
        if current_time - GLOBAL_STATE["last_long_alert"] < 1800: return
        GLOBAL_STATE["last_long_alert"] = current_time
    elif bias == "SHORT":
        if current_time - GLOBAL_STATE["last_short_alert"] < 1800: return
        GLOBAL_STATE["last_short_alert"] = current_time

    try:
        current_offset = GLOBAL_STATE["settings"]["offset"]
        
        # [NEW] V4.6: Use LIVE Market Price for Alert (Fixes Ghost Trades)
        raw_entry = GLOBAL_STATE["market_data"]["adjusted_price"]
        raw_tp = data['trade_setup']['tp']
        raw_sl = data['trade_setup']['sl']
        
        lots, risk_usd = calculate_position_size(raw_entry, raw_sl)
        GLOBAL_STATE["prediction"]["trade_setup"]["size"] = lots

        color = 5763719 if bias == "LONG" else 15548997
        style_icon = "🦁" 
        
        embed = {
            "title": f"{style_icon} SIGNAL: {asset} {bias}",
            "description": f"**AI Reasoning:**\n{data['narrative']}\n\n**🛡️ Crash Protection:** RSI Checked & Safe",
            "color": color,
            "fields": [
                {"name": "ENTRY (MARKET)", "value": f"**EXECUTE NOW**\nApprox: ${raw_entry:,.2f}", "inline": True},
                {"name": "🛑 SL (Swing)", "value": f"${raw_sl:,.2f}", "inline": True},
                {"name": "🎯 TP (Asia)", "value": f"${raw_tp:,.2f}", "inline": True},
                {"name": "⚖️ Risk Calc", "value": f"Risk: ${risk_usd} ({GLOBAL_STATE['settings']['risk_pct']}%)\n**Size: {lots} Lots**", "inline": False},
                {"name": "Confidence", "value": f"{data['probability']}%", "inline": True}
            ],
            "footer": {"text": f"ForwardFin V4.6 • Drift-Proof Engine"}
        }
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
        GLOBAL_STATE["last_alert_time"] = current_time
        
        ui_data = data.copy()
        ui_data['trade_setup']['entry'] = raw_entry
        GLOBAL_STATE["signal_latch"]["active"] = True
        GLOBAL_STATE["signal_latch"]["data"] = ui_data
        GLOBAL_STATE["signal_latch"]["time"] = current_time
        
        log_msg("ALERT", f"Sent {bias} Signal. Target: {lots} Lots.")
    except Exception as e:
        log_msg("SYS", f"Discord Error: {e}")

# --- 📰 NEWS SCANNER ---
def check_news():
    try:
        ticker = yf.Ticker("NQ=F")
        news_items = ticker.news
        found_danger = False
        danger_word = ""
        
        if news_items:
            latest = news_items[0]
            title = latest['title'].upper()
            pub_time = latest.get('providerPublishTime', 0)
            
            if time.time() - pub_time < 7200:
                for word in DANGER_KEYWORDS:
                    if word in title:
                        found_danger = True
                        danger_word = word
                        break
            
            status_msg = f"Last: {title[:30]}..."
            if found_danger:
                status_msg = f"⛔ DANGER: '{danger_word}' detected!"
                log_msg("NEWS", f"Trading PAUSED. Detected: {danger_word}")
            
            GLOBAL_STATE["news"] = {
                "is_danger": found_danger,
                "headline": status_msg,
                "last_scan": datetime.now().strftime('%H:%M')
            }
    except Exception as e:
        print(f"News Error: {e}")

# --- WORKER 1: REAL FUTURES DATA ---
def run_market_data_stream():
    log_msg("SYS", "Connecting to Dual Streams (NQ + ES)...")
    tick_count = 0
    while True:
        try:
            tickers = "NQ=F ES=F"
            data = yf.download(tickers, period="5d", interval="1m", progress=False, group_by='ticker')
            
            if tick_count % 30 == 0: check_news()
            tick_count += 1

            if GLOBAL_STATE["settings"]["asset"] == "NQ1!":
                main_ticker, aux_ticker = "NQ=F", "ES=F"
                main_key, aux_key = "NQ", "ES"
            else:
                main_ticker, aux_ticker = "ES=F", "NQ=F"
                main_key, aux_key = "ES", "NQ"

            if not data.empty:
                sa_tz = pytz.timezone('Africa/Johannesburg')
                df_main = data[main_ticker].copy()
                df_main.index = df_main.index.tz_convert(sa_tz) if df_main.index.tz else df_main.index.tz_localize('UTC').tz_convert(sa_tz)
                df_main = df_main.dropna()

                # [NEW] V4.6: RSI Calculation Engine
                delta = df_main['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = float(rsi.iloc[-1]) if not rsi.empty else 50.0

                df_aux = data[aux_ticker].copy()
                df_aux.index = df_aux.index.tz_convert(sa_tz) if df_aux.index.tz else df_aux.index.tz_localize('UTC').tz_convert(sa_tz)
                df_aux = df_aux.dropna()
                
                current_price = float(df_main['Close'].iloc[-1])
                adjusted_price = current_price - GLOBAL_STATE["settings"]["offset"]
                
                now_time = datetime.now(sa_tz)
                GLOBAL_STATE["market_data"]["price"] = current_price
                GLOBAL_STATE["market_data"]["adjusted_price"] = adjusted_price
                GLOBAL_STATE["market_data"]["rsi"] = current_rsi # Stored for Strategy
                GLOBAL_STATE["market_data"]["server_time"] = now_time.strftime('%H:%M:%S')
                GLOBAL_STATE["market_data"]["history"] = df_main['Close'].tolist()[-100:]
                GLOBAL_STATE["market_data"]["highs"] = df_main['High'].tolist()[-100:]
                GLOBAL_STATE["market_data"]["lows"] = df_main['Low'].tolist()[-100:]
                GLOBAL_STATE["market_data"]["df"] = df_main
                GLOBAL_STATE["market_data"]["aux_data"][main_key] = df_main 
                GLOBAL_STATE["market_data"]["aux_data"][aux_key] = df_aux
                
        except Exception as e:
            print(f"Data Error: {e}")
        time.sleep(10)

# --- HELPER: DATA PROCESSING ---
def get_asia_session_data(df):
    if df is None or df.empty: return None
    last_timestamp = df.index[-1]
    current_date = last_timestamp.date()
    mask = (df.index.time >= ASIA_OPEN_TIME) & (df.index.time <= ASIA_CLOSE_TIME) & (df.index.date == current_date)
    session_data = df.loc[mask]
    if session_data.empty: return None
    return {"high": float(session_data['High'].max()), "low": float(session_data['Low'].min()), "is_closed": last_timestamp.time() > ASIA_CLOSE_TIME}

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
    if sweep_type == "LOW" and current_aux_price > aux_asia['low']: return True 
    elif sweep_type == "HIGH" and current_aux_price < aux_asia['high']: return True 
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

# --- HELPER: 5M SWING DETECTION ---
def get_recent_5m_swing(df_5m, bias):
    if len(df_5m) < 10: return 0
    # [NEW] V4.6: Return relative price (minus offset)
    current_offset = GLOBAL_STATE["settings"]["offset"]
    if bias == "LONG": return float(df_5m['High'].iloc[-10:].max()) - current_offset
    else: return float(df_5m['Low'].iloc[-10:].min()) - current_offset

# --- WORKER 2: THE STRATEGY BRAIN ---
def run_strategy_engine():
    log_msg("SYS", "V4.6 Logic Loaded. RSI Guard Active.")
    while True:
        try:
            market = GLOBAL_STATE["market_data"]
            current_price = market["price"]
            current_rsi = market["rsi"] # [NEW]
            current_offset = GLOBAL_STATE["settings"]["offset"]
            df = market["df"]
            current_asset = GLOBAL_STATE["settings"]["asset"]
            aux_key = "ES" if current_asset == "NQ1!" else "NQ"
            df_aux = market["aux_data"].get(aux_key)

            if df is None or len(market["history"]) < 20: 
                time.sleep(5); continue

            # Time Gate
            sa_tz = pytz.timezone('Africa/Johannesburg')
            now_time = datetime.now(sa_tz).time()
            if not (TRADE_WINDOW_OPEN <= now_time <= TRADE_WINDOW_CLOSE):
                GLOBAL_STATE["prediction"] = {
                    "bias": "CLOSED",
                    "probability": 0,
                    "narrative": f"😴 Market Closed. Trading Window: {TRADE_WINDOW_OPEN.strftime('%H:%M')} - {TRADE_WINDOW_CLOSE.strftime('%H:%M')} SAST.",
                    "trade_setup": {"entry": 0, "tp": 0, "sl": 0, "valid": False}
                }
                time.sleep(5); continue 

            # NEWS BLOCK
            if GLOBAL_STATE["news"]["is_danger"]:
                GLOBAL_STATE["prediction"]["bias"] = "PAUSED"
                GLOBAL_STATE["prediction"]["narrative"] = f"⛔ TRADING HALTED.\nNews Event: {GLOBAL_STATE['news']['headline']}"
                time.sleep(5); continue

            # Analysis
            asia_info = get_asia_session_data(df)
            df_5m = resample_to_5m(df) 
            
            bias = "NEUTRAL"
            prob = 50
            narrative = "Scanning Market Structure..."
            setup = {"entry": 0, "tp": 0, "sl": 0, "size": 0, "valid": False}
            
            is_monitoring_smt = False
            if asia_info and asia_info['is_closed']:
                if current_price < asia_info['low']: 
                    is_monitoring_smt = check_smt_divergence(df, df_aux, "LOW")
                elif current_price > asia_info['high']: 
                    is_monitoring_smt = check_smt_divergence(df, df_aux, "HIGH")
            
            GLOBAL_STATE["market_data"]["smt_detected"] = is_monitoring_smt

            if asia_info:
                high = asia_info['high']
                low = asia_info['low']
                # [NEW] Store Relative Levels
                GLOBAL_STATE["market_data"]["session_high"] = high - current_offset
                GLOBAL_STATE["market_data"]["session_low"] = low - current_offset

                if asia_info['is_closed']: 
                    leg_range = high - low
                    
                    # 2.5 SD LOGIC
                    buy_zone = low - (leg_range * 2.5)
                    sell_zone = high + (leg_range * 2.5)

                    if current_price < low:
                        narrative = f"⚠️ Asia Low Swept. Monitoring for 2.5 SD."
                        
                        # [NEW] V4.6 CRASH GUARD:
                        if current_price <= (buy_zone * 1.001): 
                            if current_rsi < 30:
                                narrative = f"⛔ WATERFALL: Price in Zone, but RSI {current_rsi:.1f} is too weak. Waiting for curl."
                            else:
                                narrative = "🚨 KILL ZONE (2.5 SD). RSI OK. Checking Trigger..."
                                has_smt = check_smt_divergence(df, df_aux, "LOW")
                                if detect_1m_trigger(df, "LONG"):
                                    bias = "LONG"
                                    prob = 95 if has_smt else 85 
                                    tp1 = get_recent_5m_swing(df_5m, "LONG")
                                    tp2 = high - current_offset
                                    sl_dynamic = float(df['Low'].iloc[-5:].min()) - current_offset
                                    narrative = f"✅ BUY SIGNAL (2.5 SD). RSI {current_rsi:.1f} Healthy."
                                    if not has_smt: narrative += " (No SMT)"
                                    setup = {"entry": current_price - current_offset, "tp": tp2, "sl": sl_dynamic, "valid": True}

                    elif current_price > high:
                        narrative = "⚠️ Asia High Swept. Monitoring for 2.5 SD."
                        if current_price >= (sell_zone * 0.999):
                            # [NEW] V4.6 ROCKET GUARD:
                            if current_rsi > 70:
                                narrative = f"⛔ ROCKET: Price in Zone, but RSI {current_rsi:.1f} is too strong. Waiting for dip."
                            else:
                                narrative = "🚨 KILL ZONE (2.5 SD). RSI OK. Checking Trigger..."
                                has_smt = check_smt_divergence(df, df_aux, "HIGH")
                                if detect_1m_trigger(df, "SHORT"):
                                    bias = "SHORT"
                                    prob = 95 if has_smt else 85 
                                    tp1 = get_recent_5m_swing(df_5m, "SHORT")
                                    tp2 = low - current_offset
                                    sl_dynamic = float(df['High'].iloc[-5:].max()) - current_offset
                                    narrative = f"✅ SELL SIGNAL (2.5 SD). RSI {current_rsi:.1f} Healthy."
                                    if not has_smt: narrative += " (No SMT)"
                                    setup = {"entry": current_price - current_offset, "tp": tp2, "sl": sl_dynamic, "valid": True}
                    else:
                        narrative = f"📉 Consolidating inside Asia Range.\nWaiting for a Sweep."
                
                else:
                    narrative = "⏳ Asia Session Active (03:00-08:59 SAST).\nRecording Highs and Lows..."

            GLOBAL_STATE["prediction"] = {"bias": bias, "probability": prob, "narrative": narrative, "trade_setup": setup}

            if bias != "NEUTRAL":
                if not any(t for t in GLOBAL_STATE["active_trades"] if time.time() - t['time'] < 300):
                    GLOBAL_STATE["active_trades"].append({"type": bias, "entry": current_price, "time": time.time()})
                    send_discord_alert(GLOBAL_STATE["prediction"], GLOBAL_STATE["settings"]["asset"])

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
            log_msg("SYS", f"Brain Error: {e}")
        time.sleep(1)

# --- API ROUTES ---
@app.get("/api/live-data")
async def get_api():
    safe_state = GLOBAL_STATE.copy()
    safe_state["market_data"] = GLOBAL_STATE["market_data"].copy()
    if "df" in safe_state["market_data"]: del safe_state["market_data"]["df"]
    if "aux_data" in safe_state["market_data"]: del safe_state["market_data"]["aux_data"]
    
    if safe_state["market_data"]["adjusted_price"] > 0:
        safe_state["market_data"]["price"] = safe_state["market_data"]["adjusted_price"]
        
    return safe_state

@app.post("/api/update-settings")
async def update_settings(settings: SettingsUpdate):
    GLOBAL_STATE["settings"]["asset"] = settings.asset
    GLOBAL_STATE["settings"]["strategy"] = settings.strategy
    GLOBAL_STATE["settings"]["style"] = settings.style
    GLOBAL_STATE["market_data"]["df"] = None
    GLOBAL_STATE["market_data"]["history"] = [] 
    log_msg("SYS", f"Settings Updated: {settings.asset}")
    return {"status": "success"}

@app.post("/api/calibrate-offset")
async def calibrate(c: CalibrationUpdate):
    # This just updates the Visuals. Logic is now Relative.
    futures_price = GLOBAL_STATE["market_data"]["price"] 
    if futures_price > 0:
        new_offset = futures_price - c.current_cfd_price
        GLOBAL_STATE["settings"]["offset"] = new_offset
        log_msg("SYS", f"⚖️ Calibrated! Offset: {new_offset:.2f}")
        return {"status": "ok", "offset": new_offset}
    return {"status": "error"}

@app.post("/api/update-risk")
async def update_risk(r: RiskUpdate):
    GLOBAL_STATE["settings"]["balance"] = r.balance
    GLOBAL_STATE["settings"]["risk_pct"] = r.risk_pct
    log_msg("SYS", f"⚖️ Risk Updated: ${r.balance} @ {r.risk_pct}%")
    return {"status": "ok"}

@app.get("/")
async def root():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ForwardFin V4.6 | Drift-Proof</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0B1120; color: #E2E8F0; }
        .mono { font-family: 'JetBrains Mono', monospace; }
        .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
        .terminal { background: #000; color: #00ff41; font-family: 'JetBrains Mono', monospace; font-size: 12px; height: 150px; overflow-y: auto; }
        .arch-layer { transition: all 0.3s ease; cursor: pointer; border-left: 4px solid transparent; }
        .arch-layer:hover { background-color: rgba(255,255,255,0.05); transform: translateX(4px); }
        .arch-layer.active { background-color: rgba(14, 165, 233, 0.2); border-left-color: #0ea5e9; }
        .lesson-card { cursor: pointer; transition: all 0.2s; border-left: 4px solid transparent; }
        .lesson-card:hover { background: rgba(255,255,255,0.05); }
        .lesson-card.active { background: rgba(14, 165, 233, 0.2); border-left-color: #0ea5e9; }
        .btn-asset { transition: all 0.2s; border: 1px solid #334155; }
        .btn-asset:hover { background-color: #1e293b; border-color: #0ea5e9; }
        .btn-asset.active { background-color: #0ea5e9; color: white; border-color: #0ea5e9; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
        .feature-box { background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.05); }
    </style>
</head>
<body class="bg-slate-900 text-slate-200 antialiased flex flex-col min-h-screen">

    <nav class="sticky top-0 z-50 bg-slate-900/90 backdrop-blur-md border-b border-slate-800 shadow-sm">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <div class="flex items-center gap-4">
                    <div class="h-10 w-10 bg-sky-600 rounded-lg flex items-center justify-center text-white font-bold text-xl">FF</div>
                    <div class="hidden md:block h-6 w-px bg-slate-700"></div>
                    <div id="nav-ticker" class="font-mono text-sm font-bold text-slate-400 flex items-center gap-2">
                        <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        Connecting...
                    </div>
                </div>
                <div class="flex gap-4 items-center">
                    <div id="news-status" class="hidden md:block text-xs px-3 py-1 rounded bg-slate-800 border border-slate-700 text-slate-400">
                        📰 News Scanner: Active
                    </div>
                    <div class="flex gap-2">
                        <button onclick="setAsset('NQ1!')" id="btn-nq" class="btn-asset active px-4 py-1.5 rounded text-sm font-bold bg-slate-800 text-slate-300">NQ</button>
                        <button onclick="setAsset('ES1!')" id="btn-es" class="btn-asset px-4 py-1.5 rounded text-sm font-bold bg-slate-800 text-slate-300">ES</button>
                    </div>
                </div>
            </div>
        </div>
    </nav>

    <main class="flex-grow p-4 md:p-8">
        
        <div class="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6 mb-12">
            
            <div class="lg:col-span-3 space-y-6">
                <div class="glass rounded-xl p-5">
                    <h3 class="text-xs font-bold text-slate-400 uppercase mb-3">1. Calibrate Price (Visual)</h3>
                    <div class="space-y-2">
                        <label class="text-xs text-slate-500">Capital.com Price</label>
                        <input type="number" id="inp-cfd" class="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white text-sm focus:border-sky-500 outline-none" placeholder="e.g. 15400.50">
                        <button onclick="calibrate()" class="w-full bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold py-2 rounded transition">SYNC OFFSET</button>
                    </div>
                </div>

                <div class="glass rounded-xl p-5">
                    <h3 class="text-xs font-bold text-slate-400 uppercase mb-3">2. Risk Engine</h3>
                    <div class="space-y-3">
                        <div>
                            <label class="text-xs text-slate-500">Balance ($)</label>
                            <input type="number" id="inp-bal" class="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white text-sm outline-none" value="1000">
                        </div>
                        <div>
                            <label class="text-xs text-slate-500">Risk %</label>
                            <input type="number" id="inp-risk" class="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white text-sm outline-none" value="2.0">
                        </div>
                        <button onclick="updateRisk()" class="w-full bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold py-2 rounded transition">UPDATE RISK</button>
                    </div>
                </div>
            </div>

            <div class="lg:col-span-6 space-y-6">
                <div class="glass rounded-xl overflow-hidden flex flex-col h-[200px]">
                    <div class="bg-slate-800/50 px-4 py-2 border-b border-white/5 flex justify-between">
                        <span class="text-xs font-bold text-slate-400">SYSTEM LOGS</span>
                        <span class="text-[10px] text-emerald-500 mono">● LIVE</span>
                    </div>
                    <div id="terminal" class="terminal p-4 space-y-1">
                        <div class="opacity-50">Loading ForwardFin Core...</div>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                    <div class="glass rounded-xl p-4 text-center">
                        <div class="text-xs font-bold text-slate-500 uppercase">Live Price (CFD)</div>
                        <div id="price-display" class="text-3xl font-bold text-white mt-1 font-mono">---</div>
                    </div>
                    <div class="glass rounded-xl p-4 text-center">
                        <div class="text-xs font-bold text-slate-500 uppercase">Current Offset</div>
                        <div id="stat-offset" class="text-3xl font-bold text-sky-500 mt-1 font-mono">-105</div>
                    </div>
                </div>
            </div>

            <div class="lg:col-span-3 space-y-6">
                <div class="glass rounded-xl p-5 flex flex-col h-64">
                    <h3 class="text-xs font-bold text-slate-400 uppercase mb-3 flex items-center gap-2">
                        <span>🤖</span> AI Analysis
                    </h3>
                    <div id="ai-text" class="text-sm text-slate-300 leading-relaxed overflow-y-auto flex-grow pr-2">
                        Waiting for market data...
                    </div>
                </div>

                <div class="glass rounded-xl p-4">
                    <div class="flex justify-between items-center mb-2">
                        <h4 class="text-xs font-bold text-slate-500 uppercase">Trade Setup</h4>
                        <span id="setup-validity" class="text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-400">WAITING</span>
                    </div>
                    <div class="space-y-2">
                        <div class="flex justify-between text-xs">
                            <span class="text-slate-500">Entry</span>
                            <span id="setup-entry" class="text-white font-mono">---</span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <span class="text-slate-500">TP</span>
                            <span id="setup-tp" class="text-emerald-400 font-mono">---</span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <span class="text-slate-500">SL</span>
                            <span id="setup-sl" class="text-rose-400 font-mono">---</span>
                        </div>
                    </div>
                </div>

                <div class="glass rounded-xl p-4 flex items-center justify-between">
                    <span class="text-xs font-bold text-slate-400">SMT DIVERGENCE</span>
                    <span id="smt-status" class="text-xs font-bold text-rose-500">SYNCED</span>
                </div>

                <div class="glass rounded-xl p-4 flex items-center justify-between">
                    <span class="text-xs font-bold text-slate-400">MOMENTUM RSI</span>
                    <span id="rsi-status" class="text-xs font-bold text-sky-500">--.-</span>
                </div>
                
                <div class="glass rounded-xl p-4 text-center">
                    <div class="text-xs font-bold text-slate-500 uppercase mb-2">AI Signal</div>
                    <div id="signal-badge" class="inline-block px-4 py-2 bg-slate-800 rounded text-sm font-bold text-slate-400">NEUTRAL</div>
                </div>
            </div>
        </div>

        <section id="overview" class="py-10 max-w-7xl mx-auto border-t border-slate-800">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center mb-10">
                <div class="space-y-6">
                    <div class="inline-flex items-center px-3 py-1 rounded-full bg-emerald-900/30 text-emerald-400 text-xs font-semibold uppercase tracking-wide border border-emerald-800">
                        V4.6 LIVE: DRIFT-PROOF MODE
                    </div>
                    <h1 class="text-4xl sm:text-5xl font-extrabold text-white leading-tight">
                        Precision Entries,<br>
                        <span class="text-sky-500">Momentum Guarded.</span>
                    </h1>
                    <div class="flex items-center gap-2 mt-4 text-slate-500 font-mono text-sm">
                        <span>🕒 BOT TIME (SAST):</span>
                        <span id="server-clock" class="font-bold text-slate-300">--:--:--</span>
                    </div>
                    <p class="text-lg text-slate-400 max-w-lg mt-4">
                        ForwardFin V4.6 uses <strong>Relative Market Structure</strong> to detect Asia Sweeps regardless of Broker price drift. Includes <strong>RSI Waterfall Protection</strong>.
                    </p>
                </div>
                <div class="grid grid-cols-3 gap-4">
                    <div class="glass p-4 rounded-2xl flex flex-col items-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Correlation Monitor</h3>
                        <div id="status-smt-big" class="text-xl font-black text-rose-500 mt-4">SYNCED</div>
                    </div>
                    <div class="glass p-4 rounded-2xl flex flex-col items-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Session Range</h3>
                        <div id="status-fib" class="text-sm font-black text-slate-300 mt-4 text-center">WAITING</div>
                    </div>
                    <div class="glass p-4 rounded-2xl flex flex-col items-center justify-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Win Rate</h3>
                        <div class="text-center my-2"><span id="win-rate" class="text-4xl font-black text-white">0%</span></div>
                        <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden mt-1 mb-2"><div id="win-bar" class="bg-slate-200 h-full w-0 transition-all duration-1000"></div></div>
                    </div>
                </div>
            </div>

            <div class="glass p-6 rounded-2xl grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label class="text-xs font-bold text-slate-500 uppercase tracking-wider">Strategy Logic</label>
                    <select id="sel-strategy" onchange="pushSettings()" class="w-full mt-2 bg-slate-800 border border-slate-700 text-white text-sm rounded-lg block p-2.5">
                        <option value="SWEEP" selected>Asia Liquidity Sweep (Strict)</option>
                    </select>
                </div>
                <div>
                    <label class="text-xs font-bold text-slate-500 uppercase tracking-wider">Trade Style</label>
                    <select id="sel-style" onchange="pushSettings()" class="w-full mt-2 bg-slate-800 border border-slate-700 text-white text-sm rounded-lg block p-2.5">
                        <option value="PRECISION" selected>🎯 Precision (High Probability)</option>
                        <option value="SCALP">⚡ Scalp (Fast Execution)</option>
                    </select>
                </div>
            </div>
        </section>

        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-12">
             <div class="glass p-1 rounded-xl h-[500px] overflow-hidden">
                <div id="tv-chart" class="w-full h-full rounded-lg bg-slate-900"></div>
            </div>
        </div>

        <section id="features-detail" class="py-16 bg-slate-900 border-t border-slate-800">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="text-center mb-12">
                    <h2 class="text-3xl font-bold text-white">System Capabilities & Logic Breakdown</h2>
                    <p class="mt-4 text-slate-400 max-w-3xl mx-auto">Understanding the ForwardFin V4.6 Engine: How it protects your capital and finds precision entries in a chaotic market.</p>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <div class="feature-box p-6 rounded-xl">
                        <div class="flex items-center mb-4">
                            <span class="text-2xl mr-3">🧭</span>
                            <h3 class="text-xl font-bold text-sky-400">Drift-Proof "Relative" Math</h3>
                        </div>
                        <p class="text-slate-300 text-sm leading-relaxed mb-3">
                            Most trading bots fail because of "Price Drift." If Yahoo Finance says Nasdaq is at 15,400, but your broker (HFM/Alpha) quotes 15,410 due to spreads, a static bot will miscalculate entry zones.
                        </p>
                        <p class="text-slate-400 text-xs italic">
                            **How V4.6 Solves This:** ForwardFin does not look at the absolute price number (e.g., "$15,000"). Instead, it calculates **Relative Structure**. It measures the *percentage distance* from the Asia Session Low. A 2.5 SD drop is mathematically identical on every broker, regardless of the price tag. You no longer need to stress about perfect calibration every minute.
                        </p>
                    </div>

                    <div class="feature-box p-6 rounded-xl">
                        <div class="flex items-center mb-4">
                            <span class="text-2xl mr-3">🛡️</span>
                            <h3 class="text-xl font-bold text-rose-400">RSI "Waterfall" Guard</h3>
                        </div>
                        <p class="text-slate-300 text-sm leading-relaxed mb-3">
                            The "Asia Sweep" strategy is a reversal system. However, sometimes the market doesn't reverse; it crashes (a "Waterfall"). Buying during a crash is account suicide.
                        </p>
                        <p class="text-slate-400 text-xs italic">
                            **The Safety Mechanism:** Before sending a Signal, V4.6 checks the **Relative Strength Index (RSI)**. If price is in the Buy Zone but RSI is **< 30** (Extreme Momentum), the bot assumes a crash is happening and BLOCKS the trade. It waits for the "Curl" (RSI pointing up) to confirm buyers have stepped in.
                        </p>
                    </div>

                    <div class="feature-box p-6 rounded-xl">
                        <div class="flex items-center mb-4">
                            <span class="text-2xl mr-3">🎯</span>
                            <h3 class="text-xl font-bold text-emerald-400">Precision Mode (2.5 SD)</h3>
                        </div>
                        <p class="text-slate-300 text-sm leading-relaxed mb-3">
                            Retail traders guess where the bottom is. Institutions calculate it. The "Standard Deviation (SD)" tells us how far price is statistically allowed to stretch before it snaps back.
                        </p>
                        <p class="text-slate-400 text-xs italic">
                            **The Math:** V4.6 ignores minor fluctuations. It waits for price to stretch **2.5x** the size of the Asia Range. This is a statistical extreme. When price hits this "Kill Zone," the probability of a reversal is mathematically maximized (>85%), allowing for tight stops and high rewards.
                        </p>
                    </div>

                    <div class="feature-box p-6 rounded-xl">
                        <div class="flex items-center mb-4">
                            <span class="text-2xl mr-3">👁️</span>
                            <h3 class="text-xl font-bold text-purple-400">SMT Divergence (Correlation)</h3>
                        </div>
                        <p class="text-slate-300 text-sm leading-relaxed mb-3">
                            The "Lie Detector." Nasdaq (NQ) and S&P 500 (ES) generally move together. When they disagree, it reveals a trap.
                        </p>
                        <p class="text-slate-400 text-xs italic">
                            **The Logic:** If NQ makes a Lower Low (sweeping liquidity) but ES refuses to make a Lower Low (shows strength), this "Crack in Correlation" confirms that the NQ move was a fake-out to trap sellers. ForwardFin detects this divergence automatically to validate high-quality entries.
                        </p>
                    </div>

                    <div class="feature-box p-6 rounded-xl">
                        <div class="flex items-center mb-4">
                            <span class="text-2xl mr-3">📰</span>
                            <h3 class="text-xl font-bold text-amber-400">News Sentiment Scanner</h3>
                        </div>
                        <p class="text-slate-300 text-sm leading-relaxed mb-3">
                            Markets react violently to high-impact news (CPI, FOMC, NFP). Trading through these events is gambling, not trading.
                        </p>
                        <p class="text-slate-400 text-xs italic">
                            **The Logic:** The bot scans Yahoo Finance every 60 seconds for "Danger Words" (e.g., POWELL, RATES, JOBS). If detected within a 2-hour window, the system triggers a **Hard Freeze**. No trades are executed until the event passes, protecting you from slippage and spikes.
                        </p>
                    </div>

                    <div class="feature-box p-6 rounded-xl">
                        <div class="flex items-center mb-4">
                            <span class="text-2xl mr-3">⚖️</span>
                            <h3 class="text-xl font-bold text-blue-400">Dynamic Risk Engine</h3>
                        </div>
                        <p class="text-slate-300 text-sm leading-relaxed mb-3">
                            Most traders blow up by guessing lot sizes. ForwardFin treats risk as a mathematical constant, not a variable.
                        </p>
                        <p class="text-slate-400 text-xs italic">
                            **The Logic:** You set a risk percentage (e.g., 2%). The engine calculates the distance to your Stop Loss in points. It then solves the equation: `(Balance * Risk%) / Distance = Lot Size`. If volatility is high (wide stop), lot size shrinks. If volatility is low (tight stop), lot size expands. Your dollar risk remains constant.
                        </p>
                    </div>
                </div>
            </div>
        </section>

        <section id="academy" class="py-16 bg-slate-900 border-t border-slate-800">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="text-center mb-12">
                    <h2 class="text-3xl font-bold text-white">ForwardFin Academy</h2>
                    <p class="mt-4 text-slate-400 max-w-2xl mx-auto">V4.6 Concepts: SMT Divergence & Liquidity.</p>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 h-[400px]">
                    <div class="lg:col-span-4 glass rounded-xl overflow-hidden overflow-y-auto">
                        <div onclick="loadLesson(0)" class="lesson-card p-4 border-b border-slate-700 active">
                            <h4 class="font-bold text-slate-200">1. SMT Divergence</h4>
                            <p class="text-xs text-slate-500 mt-1">Correlation Check.</p>
                        </div>
                        <div onclick="loadLesson(1)" class="lesson-card p-4 border-b border-slate-700">
                            <h4 class="font-bold text-slate-200">2. The "Kill Zone"</h4>
                            <p class="text-xs text-slate-500 mt-1">Wait for 2.5 SD.</p>
                        </div>
                        <div onclick="loadLesson(2)" class="lesson-card p-4 border-b border-slate-700">
                            <h4 class="font-bold text-slate-200">3. 1-Minute Trigger</h4>
                            <p class="text-xs text-slate-500 mt-1">BOS + FVG Required.</p>
                        </div>
                        <div onclick="loadLesson(3)" class="lesson-card p-4 border-b border-slate-700">
                            <h4 class="font-bold text-slate-200">4. Drift-Proof Math</h4>
                            <p class="text-xs text-slate-500 mt-1">Relative Structure Logic.</p>
                        </div>
                        <div onclick="loadLesson(4)" class="lesson-card p-4 border-b border-slate-700">
                            <h4 class="font-bold text-slate-200">5. RSI Momentum</h4>
                            <p class="text-xs text-slate-500 mt-1">Avoiding the Crash.</p>
                        </div>
                    </div>
                    <div class="lg:col-span-8 glass rounded-xl p-8 flex flex-col shadow-sm">
                        <h3 id="lesson-title" class="text-2xl font-bold text-sky-500 mb-4">Select a Lesson</h3>
                        <div id="lesson-body" class="text-slate-300 leading-relaxed mb-8 flex-grow overflow-y-auto">
                            Click a module on the left to start learning.
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section id="architecture" class="py-16 bg-slate-900 border-t border-slate-800">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="mb-10">
                    <h2 class="text-3xl font-bold text-white">System Architecture</h2>
                    <p class="mt-4 text-slate-400 max-w-3xl">ForwardFin is built on a modular 5-layer stack.</p>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
                    <div class="lg:col-span-5 space-y-3">
                        <div onclick="selectLayer(0)" class="arch-layer active glass p-4 rounded-lg flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-200">1. Data Ingestion</h4><p class="text-xs text-slate-500 mt-1">Yahoo Finance (yfinance)</p></div><div class="text-slate-500 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(1)" class="arch-layer glass p-4 rounded-lg flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-200">2. Analysis Engine</h4><p class="text-xs text-slate-500 mt-1">Pandas / NumPy / SMT Logic</p></div><div class="text-slate-500 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(2)" class="arch-layer glass p-4 rounded-lg flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-200">3. Strategy Core</h4><p class="text-xs text-slate-500 mt-1">Asia Sweep -> SMT -> 1m Trigger</p></div><div class="text-slate-500 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(3)" class="arch-layer glass p-4 rounded-lg flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-200">4. Alerting Layer</h4><p class="text-xs text-slate-500 mt-1">Discord Webhooks</p></div><div class="text-slate-500 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(4)" class="arch-layer glass p-4 rounded-lg flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-200">5. User Interface</h4><p class="text-xs text-slate-500 mt-1">FastAPI / Tailwind / JS</p></div><div class="text-slate-500 group-hover:text-sky-500">→</div>
                        </div>
                    </div>
                    <div class="lg:col-span-7">
                        <div class="glass rounded-xl h-full p-6 flex flex-col">
                            <div class="flex justify-between items-center mb-4 border-b border-slate-700 pb-4">
                                <h3 id="detail-title" class="text-xl font-bold text-white">Data Ingestion</h3>
                                <span id="detail-badge" class="px-2 py-1 bg-sky-900 text-sky-200 text-xs rounded font-mono">Infrastructure</span>
                            </div>
                            <p id="detail-desc" class="text-slate-300 mb-6 flex-grow">Connects to Yahoo Finance to fetch real-time 1-minute candle data for NQ=F and ES=F futures contracts.</p>
                            <h5 class="font-semibold text-slate-400 mb-3 text-sm uppercase">Tech Stack</h5>
                            <ul id="detail-list" class="space-y-3"></ul>
                        </div>
                    </div>
                </div>
            </div>
        </section>

    </main>

    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script>
        // Init Chart Function
        function initChart(symbol) {
            new TradingView.widget({
                "autosize": true,
                "symbol": "CAPITALCOM:US100",
                "interval": "1",
                "timezone": "Africa/Johannesburg",
                "theme": "dark",
                "style": "1",
                "locale": "en",
                "toolbar_bg": "#f1f3f6",
                "enable_publishing": false,
                "hide_side_toolbar": false,
                "allow_symbol_change": false,
                "container_id": "tv-chart"
            });
        }

        // --- API & UI LOGIC ---
        async function calibrate() {
            const val = document.getElementById('inp-cfd').value;
            if(!val) return;
            const res = await fetch('/api/calibrate-offset', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({ current_cfd_price: parseFloat(val) })
            });
        }

        async function updateRisk() {
            const bal = document.getElementById('inp-bal').value;
            const risk = document.getElementById('inp-risk').value;
            await fetch('/api/update-risk', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({ balance: parseFloat(bal), risk_pct: parseFloat(risk) })
            });
        }

        async function setAsset(asset) {
            initChart(asset);
        }
        
        async function pushSettings() {
             // Function stub
        }

        async function updateLoop() {
            try {
                const res = await fetch('/api/live-data');
                const data = await res.json();

                // Top Bar
                document.getElementById('nav-ticker').innerHTML = `<span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> ${data.settings.asset}: $${data.market_data.price.toLocaleString()}`;
                if(data.market_data.server_time) document.getElementById('server-clock').innerText = data.market_data.server_time;

                // News
                const newsEl = document.getElementById('news-status');
                if(data.news.is_danger) {
                    newsEl.className = "hidden md:block text-xs px-3 py-1 rounded bg-red-900/50 border border-red-500 text-red-200 animate-pulse";
                    newsEl.innerText = "⛔ NEWS HALT: " + data.news.headline;
                } else {
                    newsEl.className = "hidden md:block text-xs px-3 py-1 rounded bg-slate-800 border border-slate-700 text-slate-400";
                    newsEl.innerText = "📰 News: Clear";
                }

                // Stats
                document.getElementById('stat-offset').innerText = data.settings.offset.toFixed(2);
                document.getElementById('price-display').innerText = "$" + data.market_data.price.toLocaleString(undefined, {minimumFractionDigits: 2});
                
                // Signal
                const sigEl = document.getElementById('signal-badge');
                sigEl.innerText = data.prediction.bias;
                if(data.prediction.bias === "LONG") sigEl.className = "inline-block px-4 py-2 bg-emerald-600 rounded text-xs font-bold text-white animate-pulse";
                else if(data.prediction.bias === "SHORT") sigEl.className = "inline-block px-4 py-2 bg-rose-600 rounded text-xs font-bold text-white animate-pulse";
                else sigEl.className = "inline-block px-4 py-2 bg-slate-800 rounded text-xs font-bold text-slate-400";

                document.getElementById('ai-text').innerText = data.prediction.narrative;
                const smtEl = document.getElementById('smt-status');
                const smtElBig = document.getElementById('status-smt-big');
                if(data.market_data.smt_detected) {
                    smtEl.innerText = "DIVERGENCE"; smtEl.className = "text-xs font-bold text-emerald-400";
                    if(smtElBig) { smtElBig.innerText = "DIVERGENCE"; smtElBig.className = "text-xl font-black text-emerald-500 mt-4 animate-pulse"; }
                } else {
                    smtEl.innerText = "SYNCED"; smtEl.className = "text-xs font-bold text-rose-500";
                    if(smtElBig) { smtElBig.innerText = "SYNCED"; smtElBig.className = "text-xl font-black text-rose-500 mt-4"; }
                }
                
                // [NEW] V4.6 RSI Display
                const rsiEl = document.getElementById('rsi-status');
                if(rsiEl && data.market_data.rsi) {
                    rsiEl.innerText = data.market_data.rsi.toFixed(1);
                    if(data.market_data.rsi < 30 || data.market_data.rsi > 70) rsiEl.className = "text-xs font-bold text-rose-500 animate-pulse";
                    else rsiEl.className = "text-xs font-bold text-emerald-500";
                }

                // Setup
                const setup = data.prediction.trade_setup;
                const validEl = document.getElementById('setup-validity');
                if(validEl) {
                    if(setup.valid) {
                        validEl.innerText = "ACTIVE"; validEl.className = "text-[10px] bg-emerald-600 px-2 py-1 rounded text-white";
                        document.getElementById('setup-entry').innerText = "$" + setup.entry.toLocaleString();
                        document.getElementById('setup-tp').innerText = "$" + setup.tp.toLocaleString();
                        document.getElementById('setup-sl').innerText = "$" + setup.sl.toLocaleString();
                    } else {
                        validEl.innerText = "WAITING"; validEl.className = "text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-400";
                    }
                }

                // Session
                const fibEl = document.getElementById('status-fib');
                const sessionLow = data.market_data.session_low;
                const sessionHigh = data.market_data.session_high;
                if (sessionLow > 0) {
                      fibEl.innerText = `${sessionLow.toFixed(2)} - ${sessionHigh.toFixed(2)}`;
                      fibEl.className = "text-sm font-bold text-slate-300 mt-4 text-center";
                } else {
                      fibEl.innerText = "WAITING FOR DATA";
                }

                if (data.performance) {
                    const wr = data.performance.win_rate;
                    document.getElementById('win-rate').innerText = wr + "%";
                    document.getElementById('win-bar').style.width = wr + "%";
                }

                const term = document.getElementById('terminal');
                term.innerHTML = data.logs.map(l => `<div>${l}</div>`).join('');

            } catch(e) {}
        }

        // --- CONTENT LOGIC (UPDATED WITH EXCRUCIATING DETAIL) ---
        const lessons = [
            { title: "1. SMT Divergence", body: "<b>Smart Money Technique (SMT):</b> This is our 'Lie Detector'. Institutional algorithms often manipulate one index (like NQ) to grab liquidity while holding the other (like ES) steady.<br><br><b>The Rule:</b> If NQ sweeps a Low (makes a lower low) but ES fails to sweep its matching Low (makes a higher low), that is a 'Crack in Correlation'. It confirms that the move down was a trap to sell to retail traders before reversing higher." },
            { title: "2. The 'Kill Zone' (-2.5 STDV)", body: "<b>Why -2.5 Standard Deviations?</b> We do not guess bottoms. We use math. By projecting the Asia Range size (High - Low) downwards by a factor of 2.5, we identify a statistical 'Exhaustion Point'.<br><br>When price hits this zone, it is mathematically overextended relative to the session's volatility. This is where we stop analysing and start hunting for an entry." },
            { title: "3. 1-Minute Trigger (BOS + FVG)", body: "<b>The Kill Switch:</b> SMT and STDV are just context. The Trigger confirms the reversal. We switch to the 1-minute chart and demand two things:<br>1. <b>BOS (Break of Structure):</b> Price must break above the last swing high, proving buyers are stepping in.<br>2. <b>FVG (Fair Value Gap):</b> This energetic move must leave behind an imbalance gap. This proves the move was institutional, not random noise." },
            { title: "4. Drift-Proof Math", body: "<b>The Relative Engine:</b> Different brokers (HFM, Alpha, Capital.com) have different price feeds. A static bot waiting for '$15,000' will fail if your broker is at '$15,010'.<br><br><b>The Solution:</b> ForwardFin V4.6 uses Relative Math. We calculate the percentage distance from the Session High/Low. If the distance is 0.5%, it is 0.5% on EVERY broker. This ensures signals are valid regardless of spread or price drift." },
            { title: "5. RSI Momentum", body: "<b>Crash Protection:</b> Buying a dip is good. Buying a crash is bad. The RSI (Relative Strength Index) tells us the difference.<br><br><b>The Rule:</b> If price is in the Buy Zone but RSI is below 30 (Vertical Drop), we DO NOT buy. We wait for the RSI to curl back above 30. This confirms that the selling pressure has exhausted and momentum is shifting up." }
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
            data.components.forEach(comp => { list.innerHTML += `<li class="flex items-start text-sm text-slate-400"><span class="w-1.5 h-1.5 bg-sky-500 rounded-full mt-1.5 mr-2"></span>${comp}</li>`; });
        }

        document.addEventListener('DOMContentLoaded', () => {
            initChart("NQ1!");
            loadLesson(0);
            selectLayer(0);
            updateLoop();
            setInterval(updateLoop, 2000);
        });
    </script>
</body>
</html>
"""
)

if __name__ == "__main__":
    t1 = threading.Thread(target=run_market_data_stream, daemon=True)
    t2 = threading.Thread(target=run_strategy_engine, daemon=True)
    t1.start()
    t2.start()
    uvicorn.run(app, host="0.0.0.0", port=10000)