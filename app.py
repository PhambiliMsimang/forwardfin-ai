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
    <title>ForwardFin V4.8 | Cyber-Glass</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        /* BASE THEME & GRID BACKGROUND */
        body { 
            font-family: 'Inter', sans-serif; 
            background-color: #020617; 
            color: #E2E8F0; 
            background-image: 
                linear-gradient(rgba(30, 41, 59, 0.3) 1px, transparent 1px), 
                linear-gradient(90deg, rgba(30, 41, 59, 0.3) 1px, transparent 1px);
            background-size: 30px 30px;
        }

        .mono { font-family: 'JetBrains Mono', monospace; }

        /* GLASS CARD STYLING */
        .glass { 
            background: rgba(15, 23, 42, 0.75); 
            backdrop-filter: blur(12px); 
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08); 
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37); 
        }

        /* TERMINAL WINDOW */
        .terminal { 
            background: #0f172a; 
            color: #10b981; 
            font-family: 'JetBrains Mono', monospace; 
            font-size: 12px; 
            height: 180px; 
            overflow-y: auto; 
            border-top: 1px solid #1e293b; 
        }

        /* SIDEBAR NAVIGATION (ARCH LAYERS) */
        .arch-layer { 
            transition: all 0.3s ease; 
            cursor: pointer; 
            border-left: 4px solid transparent; 
        }
        .arch-layer:hover { 
            background-color: rgba(56, 189, 248, 0.1); 
            transform: translateX(4px); 
        }
        .arch-layer.active { 
            background-color: rgba(14, 165, 233, 0.15); 
            border-left-color: #0ea5e9; 
        }

        /* LESSON CARDS */
        .lesson-card { 
            cursor: pointer; 
            transition: all 0.2s; 
            border-left: 4px solid transparent; 
        }
        .lesson-card:hover { background: rgba(255,255,255,0.05); }
        .lesson-card.active { 
            background: rgba(14, 165, 233, 0.15); 
            border-left-color: #0ea5e9; 
        }

        /* ASSET SWITCHER BUTTONS (PILL SHAPE + GLOW) */
        .btn-asset { 
            transition: all 0.3s; 
            border: 1px solid #334155; 
            border-radius: 9999px; 
        }
        .btn-asset:hover { 
            border-color: #38bdf8; 
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.3); 
        }
        .btn-asset.active { 
            background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%); 
            color: white; 
            border-color: transparent; 
            box-shadow: 0 0 15px rgba(14, 165, 233, 0.5); 
        }

        /* LIVE PULSE ANIMATION */
        @keyframes pulse-glow { 
            0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); } 
            70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); } 
            100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); } 
        }
        .live-pulse { animation: pulse-glow 2s infinite; }
        
        /* SCROLLBAR CUSTOMIZATION */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
        
        /* FEATURE BOX HOVER EFFECT */
        .feature-box { 
            background: rgba(30, 41, 59, 0.4); 
            border: 1px solid rgba(255,255,255,0.05); 
            transition: transform 0.2s, border-color 0.2s; 
        }
        .feature-box:hover { 
            transform: translateY(-4px); 
            border-color: #38bdf8; 
        }
    </style>
</head>
<body class="antialiased flex flex-col min-h-screen">

    <nav class="sticky top-0 z-50 glass border-b border-slate-800/50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <div class="flex items-center gap-4">
                    <div class="h-10 w-10 bg-gradient-to-br from-sky-500 to-blue-700 rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-sky-900/20">FF</div>
                    <div class="hidden md:block h-6 w-px bg-slate-700"></div>
                    
                    <div id="nav-ticker" class="font-mono text-sm font-bold text-slate-300 flex items-center gap-2">
                        <span class="relative flex h-3 w-3">
                          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                          <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                        </span>
                        Connecting to ForwardFin Neural Net...
                    </div>
                </div>
                
                <div class="flex gap-4 items-center">
                    <div id="news-status" class="hidden md:block text-[10px] uppercase font-bold tracking-wider px-3 py-1.5 rounded-full bg-slate-900/50 border border-slate-700 text-slate-400">
                        📰 SCANNING NEWS...
                    </div>
                    
                    <div class="flex gap-2 bg-slate-900/50 p-1 rounded-full border border-slate-800">
                        <button onclick="setAsset('NQ1!')" id="btn-nq" class="btn-asset active px-5 py-1.5 text-xs font-bold text-slate-300">NQ</button>
                        <button onclick="setAsset('ES1!')" id="btn-es" class="btn-asset px-5 py-1.5 text-xs font-bold text-slate-300">ES</button>
                    </div>
                </div>
            </div>
        </div>
    </nav>

    <main class="flex-grow p-4 md:p-8">
        
        <div class="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6 mb-12">
            
            <div class="lg:col-span-3 space-y-6">
                <div class="glass rounded-2xl p-6">
                    <h3 class="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-4">1. Calibration</h3>
                    <div class="space-y-3">
                        <label class="text-xs text-slate-400 font-semibold">Broker Price (CFD)</label>
                        <div class="relative">
                            <span class="absolute left-3 top-2.5 text-slate-500">$</span>
                            <input type="number" id="inp-cfd" class="w-full bg-slate-900/50 border border-slate-700 rounded-lg pl-6 pr-3 py-2 text-white text-sm focus:border-sky-500 focus:ring-1 focus:ring-sky-500 outline-none transition" placeholder="e.g. 15400.50">
                        </div>
                        <button onclick="calibrate()" class="w-full bg-gradient-to-r from-sky-600 to-blue-600 hover:from-sky-500 hover:to-blue-500 text-white text-xs font-bold py-2.5 rounded-lg shadow-lg shadow-sky-900/20 transition transform active:scale-95">SYNC OFFSET</button>
                    </div>
                </div>

                <div class="glass rounded-2xl p-6">
                    <h3 class="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-4">2. Risk Engine</h3>
                    <div class="space-y-4">
                        <div>
                            <label class="text-xs text-slate-400 font-semibold">Account Balance</label>
                            <div class="relative mt-1">
                                <span class="absolute left-3 top-2.5 text-slate-500">$</span>
                                <input type="number" id="inp-bal" class="w-full bg-slate-900/50 border border-slate-700 rounded-lg pl-6 pr-3 py-2 text-white text-sm outline-none" value="1000">
                            </div>
                        </div>
                        <div>
                            <label class="text-xs text-slate-400 font-semibold">Risk Per Trade (%)</label>
                            <input type="number" id="inp-risk" class="mt-1 w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm outline-none" value="2.0">
                        </div>
                        <button onclick="updateRisk()" class="w-full bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold py-2.5 rounded-lg border border-slate-700 transition">UPDATE PARAMETERS</button>
                    </div>
                </div>
            </div>

            <div class="lg:col-span-6 space-y-6">
                <div class="glass rounded-2xl overflow-hidden flex flex-col h-[240px] shadow-2xl">
                    <div class="bg-slate-900/80 px-4 py-2 border-b border-slate-800 flex justify-between items-center">
                        <div class="flex items-center gap-2">
                            <div class="w-2 h-2 rounded-full bg-emerald-500"></div>
                            <span class="text-xs font-bold text-slate-300 tracking-wide">ENGINE LOGS</span>
                        </div>
                        <span class="text-[10px] text-slate-500 mono">v4.8-STABLE</span>
                    </div>
                    <div id="terminal" class="terminal p-4 space-y-1.5 opacity-90">
                        <div class="text-slate-500">Initializing ForwardFin Core Systems...</div>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                    <div class="glass rounded-2xl p-5 text-center relative overflow-hidden group">
                        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-white/20 to-transparent transform -translate-x-full group-hover:translate-x-full transition-transform duration-1000"></div>
                        <div class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Live Price (CFD)</div>
                        <div id="price-display" class="text-3xl font-bold text-white mt-2 font-mono tracking-tight">---</div>
                    </div>
                    <div class="glass rounded-2xl p-5 text-center">
                        <div class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Active Offset</div>
                        <div id="stat-offset" class="text-3xl font-bold text-sky-400 mt-2 font-mono tracking-tight">-105</div>
                    </div>
                </div>
            </div>

            <div class="lg:col-span-3 space-y-6">
                <div class="glass rounded-2xl p-6 flex flex-col h-64 relative overflow-hidden">
                    <div class="absolute top-0 right-0 p-4 opacity-10 text-6xl">🧠</div>
                    <h3 class="text-[10px] font-black text-sky-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                        AI NARRATIVE
                    </h3>
                    <div id="ai-text" class="text-xs text-slate-300 leading-relaxed font-mono overflow-y-auto flex-grow pr-2 border-l-2 border-slate-700 pl-3">
                        Waiting for market data stream...
                    </div>
                </div>

                <div class="glass rounded-2xl p-5 border-l-4 border-slate-700" id="setup-card">
                    <div class="flex justify-between items-center mb-4">
                        <h4 class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Trade Setup</h4>
                        <span id="setup-validity" class="text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-500 font-bold">INACTIVE</span>
                    </div>
                    <div class="space-y-3 font-mono text-xs">
                        <div class="flex justify-between">
                            <span class="text-slate-500">ENTRY</span>
                            <span id="setup-entry" class="text-white font-bold">---</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-slate-500">TAKE PROFIT</span>
                            <span id="setup-tp" class="text-emerald-400 font-bold">---</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-slate-500">STOP LOSS</span>
                            <span id="setup-sl" class="text-rose-400 font-bold">---</span>
                        </div>
                    </div>
                </div>

                <div class="glass rounded-2xl p-4 flex items-center justify-between">
                    <span class="text-[10px] font-bold text-slate-500 uppercase">SMT DIVERGENCE</span>
                    <span id="smt-status" class="text-xs font-black text-rose-500 tracking-wider">SYNCED</span>
                </div>

                <div class="glass rounded-2xl p-4 flex items-center justify-between">
                    <span class="text-[10px] font-bold text-slate-500 uppercase">MOMENTUM (RSI)</span>
                    <span id="rsi-status" class="text-xs font-black text-sky-500 tracking-wider font-mono">--.-</span>
                </div>
                
                <div class="glass rounded-2xl p-6 text-center">
                    <div class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Core Bias</div>
                    <div id="signal-badge" class="inline-block px-6 py-2 bg-slate-800 rounded-full text-xs font-bold text-slate-400 border border-slate-700">NEUTRAL</div>
                </div>
            </div>
        </div>

        <section id="overview" class="py-12 max-w-7xl mx-auto border-t border-slate-800/50">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center mb-12">
                <div class="space-y-6">
                    <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-900/20 text-emerald-400 text-[10px] font-bold uppercase tracking-widest border border-emerald-900/50">
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                        System Operational
                    </div>
                    <h1 class="text-5xl font-black text-white leading-tight tracking-tight">
                        Algorithmic<br>
                        <span class="text-transparent bg-clip-text bg-gradient-to-r from-sky-400 to-blue-500">Precision.</span>
                    </h1>
                    <div class="flex items-center gap-3 mt-4 text-slate-500 font-mono text-xs">
                        <span class="text-sky-500">SERVER TIME:</span>
                        <span id="server-clock" class="font-bold text-slate-300">--:--:--</span>
                    </div>
                    <p class="text-slate-400 max-w-lg mt-4 leading-relaxed">
                        ForwardFin V4.7 uses <strong>Relative Structure Analysis</strong> to identify high-probability institutional sweeps. Equipped with <span class="text-rose-400">RSI Waterfall Guard</span> technology.
                    </p>
                </div>
                <div class="grid grid-cols-3 gap-4">
                    <div class="glass p-5 rounded-2xl flex flex-col items-center border border-slate-700/50">
                        <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Correlation</h3>
                        <div id="status-smt-big" class="text-xl font-black text-rose-500 mt-2">SYNCED</div>
                    </div>
                    <div class="glass p-5 rounded-2xl flex flex-col items-center border border-slate-700/50">
                        <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Asia Range</h3>
                        <div id="status-fib" class="text-xs font-bold text-slate-300 mt-2 text-center font-mono">CALCULATING</div>
                    </div>
                    <div class="glass p-5 rounded-2xl flex flex-col items-center justify-center border border-slate-700/50 relative overflow-hidden">
                        <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Win Rate</h3>
                        <div class="text-center my-1"><span id="win-rate" class="text-3xl font-black text-white">0%</span></div>
                        <div class="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mt-2"><div id="win-bar" class="bg-gradient-to-r from-sky-500 to-blue-600 h-full w-0 transition-all duration-1000"></div></div>
                    </div>
                </div>
            </div>

            <div class="glass p-8 rounded-2xl grid grid-cols-1 md:grid-cols-2 gap-8 border border-slate-700/50">
                <div>
                    <label class="text-xs font-bold text-slate-500 uppercase tracking-widest">Core Logic</label>
                    <div class="relative mt-2">
                        <select id="sel-strategy" onchange="pushSettings()" class="appearance-none w-full bg-slate-900 border border-slate-700 text-white text-sm rounded-lg block p-3 pr-10 focus:border-sky-500 focus:ring-1 focus:ring-sky-500 outline-none">
                            <option value="SWEEP" selected>Asia Liquidity Sweep (Strict)</option>
                        </select>
                        <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-slate-400">▼</div>
                    </div>
                </div>
                <div>
                    <label class="text-xs font-bold text-slate-500 uppercase tracking-widest">Execution Style</label>
                    <div class="relative mt-2">
                        <select id="sel-style" onchange="pushSettings()" class="appearance-none w-full bg-slate-900 border border-slate-700 text-white text-sm rounded-lg block p-3 pr-10 focus:border-sky-500 focus:ring-1 focus:ring-sky-500 outline-none">
                            <option value="PRECISION" selected>🎯 Precision (High Probability)</option>
                            <option value="SCALP">⚡ Scalp (Fast Execution)</option>
                        </select>
                        <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-slate-400">▼</div>
                    </div>
                </div>
            </div>
        </section>

        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-12">
             <div class="glass p-1.5 rounded-2xl h-[600px] overflow-hidden shadow-2xl border border-slate-700/50">
                <div id="tv-chart" class="w-full h-full rounded-xl bg-slate-900"></div>
            </div>
        </div>

        <section id="features-detail" class="py-20 bg-slate-950/50 border-t border-slate-800">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="text-center mb-16">
                    <h2 class="text-3xl font-black text-white tracking-tight">System Capabilities</h2>
                    <p class="mt-4 text-slate-400 max-w-2xl mx-auto">V4.7 Logic Architecture</p>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <div class="feature-box p-6 rounded-2xl group">
                        <div class="w-12 h-12 rounded-lg bg-sky-900/30 flex items-center justify-center mb-4 group-hover:bg-sky-600/20 transition">
                            <span class="text-2xl">🧭</span>
                        </div>
                        <h3 class="text-lg font-bold text-white mb-2">Drift-Proof Math</h3>
                        <p class="text-sm text-slate-400 leading-relaxed">Uses relative percentage structure instead of static price levels to ignore broker spreads.</p>
                    </div>
                    <div class="feature-box p-6 rounded-2xl group">
                        <div class="w-12 h-12 rounded-lg bg-rose-900/30 flex items-center justify-center mb-4 group-hover:bg-rose-600/20 transition">
                            <span class="text-2xl">🛡️</span>
                        </div>
                        <h3 class="text-lg font-bold text-white mb-2">RSI Crash Guard</h3>
                        <p class="text-sm text-slate-400 leading-relaxed">Blocks entries if Momentum (RSI) is below 20, preventing "catching a falling knife."</p>
                    </div>
                    <div class="feature-box p-6 rounded-2xl group">
                        <div class="w-12 h-12 rounded-lg bg-emerald-900/30 flex items-center justify-center mb-4 group-hover:bg-emerald-600/20 transition">
                            <span class="text-2xl">🎯</span>
                        </div>
                        <h3 class="text-lg font-bold text-white mb-2">Precision Mode</h3>
                        <p class="text-sm text-slate-400 leading-relaxed">Strictly waits for price to hit 2.5 Standard Deviations from the mean before executing.</p>
                    </div>
                    <div class="feature-box p-6 rounded-2xl group">
                        <div class="w-12 h-12 rounded-lg bg-purple-900/30 flex items-center justify-center mb-4 group-hover:bg-purple-600/20 transition">
                            <span class="text-2xl">👁️</span>
                        </div>
                        <h3 class="text-lg font-bold text-white mb-2">SMT Divergence</h3>
                        <p class="text-sm text-slate-400 leading-relaxed">Correlates NQ vs ES price action to detect "Fake Moves" and institutional traps.</p>
                    </div>
                    <div class="feature-box p-6 rounded-2xl group">
                        <div class="w-12 h-12 rounded-lg bg-amber-900/30 flex items-center justify-center mb-4 group-hover:bg-amber-600/20 transition">
                            <span class="text-2xl">📰</span>
                        </div>
                        <h3 class="text-lg font-bold text-white mb-2">News Scanner</h3>
                        <p class="text-sm text-slate-400 leading-relaxed">Scans for keywords (CPI, FED, POWELL) every 60s and freezes trading during high-impact events.</p>
                    </div>
                    <div class="feature-box p-6 rounded-2xl group">
                        <div class="w-12 h-12 rounded-lg bg-blue-900/30 flex items-center justify-center mb-4 group-hover:bg-blue-600/20 transition">
                            <span class="text-2xl">⚖️</span>
                        </div>
                        <h3 class="text-lg font-bold text-white mb-2">Dynamic Risk</h3>
                        <p class="text-sm text-slate-400 leading-relaxed">Auto-calculates lot size based on Stop Loss distance to keep dollar risk constant.</p>
                    </div>
                </div>
            </div>
        </section>

        <section class="py-16 border-t border-slate-800 bg-slate-900/30">
             <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-12">
                    <div>
                        <h3 class="text-xl font-bold text-white mb-6">Strategy Docs</h3>
                        <div class="space-y-2">
                            <div onclick="loadLesson(0)" class="lesson-card p-4 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:bg-slate-800 cursor-pointer transition">
                                <h4 class="font-bold text-sky-400 text-sm">1. SMT Divergence</h4>
                            </div>
                            <div onclick="loadLesson(1)" class="lesson-card p-4 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:bg-slate-800 cursor-pointer transition">
                                <h4 class="font-bold text-sky-400 text-sm">2. 2.5 SD Kill Zone</h4>
                            </div>
                            <div onclick="loadLesson(2)" class="lesson-card p-4 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:bg-slate-800 cursor-pointer transition">
                                <h4 class="font-bold text-sky-400 text-sm">3. 1-Minute Trigger (BOS)</h4>
                            </div>
                            <div onclick="loadLesson(3)" class="lesson-card p-4 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:bg-slate-800 cursor-pointer transition">
                                <h4 class="font-bold text-sky-400 text-sm">4. Drift-Proof Math</h4>
                            </div>
                            <div onclick="loadLesson(4)" class="lesson-card p-4 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:bg-slate-800 cursor-pointer transition">
                                <h4 class="font-bold text-sky-400 text-sm">5. RSI Momentum Guard</h4>
                            </div>
                        </div>
                        <div id="lesson-body" class="mt-6 p-4 bg-slate-900 rounded-xl border border-slate-800 text-sm text-slate-400 min-h-[100px] leading-relaxed">
                            Select a module to view details.
                        </div>
                    </div>
                    <div>
                        <h3 class="text-xl font-bold text-white mb-6">System Stack</h3>
                        <div class="space-y-3">
                            <div onclick="selectLayer(0)" class="arch-layer flex items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-700/30 hover:bg-slate-800 cursor-pointer transition">
                                <span class="text-sm font-bold text-slate-300">1. Data Ingestion</span>
                                <span class="text-xs text-slate-500 font-mono">yFinance API</span>
                            </div>
                            <div onclick="selectLayer(1)" class="arch-layer flex items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-700/30 hover:bg-slate-800 cursor-pointer transition">
                                <span class="text-sm font-bold text-slate-300">2. Logic Engine</span>
                                <span class="text-xs text-slate-500 font-mono">NumPy / Pandas</span>
                            </div>
                            <div onclick="selectLayer(2)" class="arch-layer flex items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-700/30 hover:bg-slate-800 cursor-pointer transition">
                                <span class="text-sm font-bold text-slate-300">3. Execution</span>
                                <span class="text-xs text-slate-500 font-mono">FastAPI Async</span>
                            </div>
                            <div onclick="selectLayer(3)" class="arch-layer flex items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-700/30 hover:bg-slate-800 cursor-pointer transition">
                                <span class="text-sm font-bold text-slate-300">4. Alerting Layer</span>
                                <span class="text-xs text-slate-500 font-mono">Discord Webhooks</span>
                            </div>
                            <div onclick="selectLayer(4)" class="arch-layer flex items-center justify-between p-3 rounded-lg bg-slate-800/30 border border-slate-700/30 hover:bg-slate-800 cursor-pointer transition">
                                <span class="text-sm font-bold text-slate-300">5. User Interface</span>
                                <span class="text-xs text-slate-500 font-mono">HTML5 / Tailwind</span>
                            </div>
                        </div>
                        <div id="detail-desc" class="mt-6 p-4 bg-slate-900 rounded-xl border border-slate-800 text-sm text-slate-400 min-h-[80px] leading-relaxed">
                            Click a layer above to view technical specs.
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
            let tvSymbol = "CAPITALCOM:US100";
            if(symbol.includes("ES")) tvSymbol = "CAPITALCOM:US500";
            
            new TradingView.widget({
                "autosize": true,
                "symbol": tvSymbol,
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

        // [RESTORED] Asset Switching Logic
        async function setAsset(asset) {
            // Visual Update
            document.querySelectorAll('.btn-asset').forEach(b => b.classList.remove('active'));
            if(asset.includes("NQ")) document.getElementById('btn-nq').classList.add('active');
            else document.getElementById('btn-es').classList.add('active');
            
            // Backend Update
            await fetch('/api/update-settings', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({ asset: asset, strategy: "SWEEP", style: "PRECISION" })
            });
            
            initChart(asset);
        }
        
        async function pushSettings() { }

        async function updateLoop() {
            try {
                const res = await fetch('/api/live-data');
                const data = await res.json();

                // Top Bar
                document.getElementById('nav-ticker').innerHTML = `<span class="relative flex h-3 w-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span></span> ${data.settings.asset}: $${data.market_data.price.toLocaleString()}`;
                if(data.market_data.server_time) document.getElementById('server-clock').innerText = data.market_data.server_time;

                // News
                const newsEl = document.getElementById('news-status');
                if(data.news.is_danger) {
                    newsEl.className = "hidden md:block text-[10px] uppercase font-bold tracking-wider px-3 py-1.5 rounded-full bg-red-900/50 border border-red-500 text-red-200 animate-pulse";
                    newsEl.innerText = "⛔ NEWS HALT: " + data.news.headline;
                } else {
                    newsEl.className = "hidden md:block text-[10px] uppercase font-bold tracking-wider px-3 py-1.5 rounded-full bg-slate-900/50 border border-slate-700 text-slate-400";
                    newsEl.innerText = "📰 SCANNING NEWS...";
                }

                // Stats
                document.getElementById('stat-offset').innerText = data.settings.offset.toFixed(2);
                document.getElementById('price-display').innerText = "$" + data.market_data.price.toLocaleString(undefined, {minimumFractionDigits: 2});
                
                // Signal
                const sigEl = document.getElementById('signal-badge');
                sigEl.innerText = data.prediction.bias;
                if(data.prediction.bias === "LONG") sigEl.className = "inline-block px-6 py-2 bg-emerald-600 rounded-full text-xs font-bold text-white shadow-lg shadow-emerald-900/50 live-pulse";
                else if(data.prediction.bias === "SHORT") sigEl.className = "inline-block px-6 py-2 bg-rose-600 rounded-full text-xs font-bold text-white shadow-lg shadow-rose-900/50 live-pulse";
                else sigEl.className = "inline-block px-6 py-2 bg-slate-800 rounded-full text-xs font-bold text-slate-400 border border-slate-700";

                document.getElementById('ai-text').innerText = data.prediction.narrative;
                const smtEl = document.getElementById('smt-status');
                const smtElBig = document.getElementById('status-smt-big');
                if(data.market_data.smt_detected) {
                    smtEl.innerText = "DIVERGENCE"; smtEl.className = "text-xs font-black text-emerald-400";
                    if(smtElBig) { smtElBig.innerText = "DIVERGENCE"; smtElBig.className = "text-xl font-black text-emerald-500 mt-2 animate-pulse"; }
                } else {
                    smtEl.innerText = "SYNCED"; smtEl.className = "text-xs font-black text-rose-500";
                    if(smtElBig) { smtElBig.innerText = "SYNCED"; smtElBig.className = "text-xl font-black text-rose-500 mt-2"; }
                }
                
                // RSI Display
                const rsiEl = document.getElementById('rsi-status');
                if(rsiEl && data.market_data.rsi) {
                    rsiEl.innerText = data.market_data.rsi.toFixed(1);
                    if(data.market_data.rsi < 20 || data.market_data.rsi > 80) rsiEl.className = "text-xs font-black text-rose-500 animate-pulse font-mono";
                    else rsiEl.className = "text-xs font-black text-emerald-500 font-mono";
                }

                // Setup Card Glow
                const setup = data.prediction.trade_setup;
                const setupCard = document.getElementById('setup-card');
                const validEl = document.getElementById('setup-validity');
                
                if(validEl) {
                    if(setup.valid) {
                        validEl.innerText = "ACTIVE"; validEl.className = "text-[10px] bg-emerald-600 px-2 py-1 rounded text-white font-bold";
                        setupCard.classList.add('border-emerald-500', 'shadow-lg', 'shadow-emerald-900/20');
                        setupCard.classList.remove('border-slate-700');
                        document.getElementById('setup-entry').innerText = "$" + setup.entry.toLocaleString();
                        document.getElementById('setup-tp').innerText = "$" + setup.tp.toLocaleString();
                        document.getElementById('setup-sl').innerText = "$" + setup.sl.toLocaleString();
                    } else {
                        validEl.innerText = "WAITING"; validEl.className = "text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-500 font-bold";
                        setupCard.classList.remove('border-emerald-500', 'shadow-lg', 'shadow-emerald-900/20');
                        setupCard.classList.add('border-slate-700');
                    }
                }

                // Session
                const fibEl = document.getElementById('status-fib');
                const sessionLow = data.market_data.session_low;
                const sessionHigh = data.market_data.session_high;
                if (sessionLow > 0) {
                      fibEl.innerText = `${sessionLow.toFixed(2)} - ${sessionHigh.toFixed(2)}`;
                      fibEl.className = "text-xs font-bold text-slate-300 mt-2 text-center font-mono";
                } else {
                      fibEl.innerText = "CALCULATING";
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

        const lessons = [
            { title: "1. SMT Divergence", body: "<b>Smart Money Technique (SMT):</b> This is our 'Lie Detector'. Institutional algorithms often manipulate one index (like NQ) to grab liquidity while holding the other (like ES) steady.<br><br><b>The Rule:</b> If NQ sweeps a Low (makes a lower low) but ES fails to sweep its matching Low (makes a higher low), that is a 'Crack in Correlation'. It confirms that the move down was a trap to sell to retail traders before reversing higher." },
            { title: "2. The 'Kill Zone' (-2.5 STDV)", body: "<b>Why -2.5 Standard Deviations?</b> We do not guess bottoms. We use math. By projecting the Asia Range size (High - Low) downwards by a factor of 2.5, we identify a statistical 'Exhaustion Point'.<br><br>When price hits this zone, it is mathematically overextended relative to the session's volatility. This is where we stop analysing and start hunting for an entry." },
            { title: "3. 1-Minute Trigger (BOS + FVG)", body: "<b>The Kill Switch:</b> SMT and STDV are just context. The Trigger confirms the reversal. We switch to the 1-minute chart and demand two things:<br>1. <b>BOS (Break of Structure):</b> Price must break above the last swing high, proving buyers are stepping in.<br>2. <b>FVG (Fair Value Gap):</b> This energetic move must leave behind an imbalance gap. This proves the move was institutional, not random noise." },
            { title: "4. Drift-Proof Math", body: "<b>The Relative Engine:</b> Different brokers (HFM, Alpha, Capital.com) have different price feeds. A static bot waiting for '$15,000' will fail if your broker is at '$15,010'.<br><br><b>The Solution:</b> ForwardFin V4.7 uses Relative Math. We calculate the percentage distance from the Session High/Low. If the distance is 0.5%, it is 0.5% on EVERY broker. This ensures signals are valid regardless of spread or price drift." },
            { title: "5. RSI Momentum", body: "<b>Crash Protection:</b> Buying a dip is good. Buying a crash is bad. The RSI (Relative Strength Index) tells us the difference.<br><br><b>The Rule:</b> If price is in the Buy Zone but RSI is below 20 (Vertical Drop), we DO NOT buy. We wait for the RSI to curl back above 30. This confirms that the selling pressure has exhausted and momentum is shifting up." }
        ];

        function loadLesson(index) {
            const l = lessons[index];
            document.getElementById('lesson-body').innerHTML = `<b>${l.title}</b><br><br>${l.body}`;
        }
        
        const architectureData = [
            { title: "Data Ingestion", badge: "Infrastructure", description: "Connects to Yahoo Finance to fetch real-time 1-minute candle data for NQ=F and ES=F futures contracts.", components: ["yfinance", "Python Requests"] },
            { title: "Analysis Engine", badge: "Data Science", description: "Resamples 1m data to 5m to find STDV Zones. Calculates live Volatility and detects IFVGs.", components: ["Pandas Resample", "NumPy Math", "Custom Fib Scanner"] },
            { title: "Strategy Core", badge: "Logic", description: "Hybrid 5m/1m Engine. Waits for 2.5 STDV on 5m, then hunts for 1m BOS+FVG triggers.", components: ["Multi-Timeframe Analysis", "Smart Money Logic"] },
            { title: "Alerting Layer", badge: "Notification", description: "When V4.6 confidence is met (>85% via RSI & SMT), constructs a rich embed payload and fires it to the Discord Webhook.", components: ["Discord API", "JSON Payloads"] },
            { title: "User Interface", badge: "Frontend", description: "Responsive dashboard served via FastAPI. Updates DOM elements live via polling.", components: ["FastAPI", "Tailwind CSS", "Chart.js", "TradingView"] }
        ];

        function selectLayer(index) {
            document.querySelectorAll('.arch-layer').forEach((el, i) => {
                if (i === index) el.classList.add('active', 'bg-sky-50', 'border-l-sky-600');
                else el.classList.remove('active', 'bg-sky-50', 'border-l-sky-600');
            });
            const data = architectureData[index];
            document.getElementById('detail-desc').innerText = `<b>${data.title}</b><br>${data.description}<br><br>Components: ${data.components.join(', ')}`;
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