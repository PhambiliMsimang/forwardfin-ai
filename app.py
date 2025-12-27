import threading
import uvicorn
import requests
import json
import time
import pandas as pd
import xml.etree.ElementTree as ET
import random
import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# --- 🔧 CONFIGURATION ---
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1454098742218330307/gi8wvEn0pMcNsAWIR_kY5-_0_VE4CvsgWjkSXjCasXX-xUrydbhYtxHRLLLgiKxs_pLL"

# --- 🧠 GLOBAL MEMORY ---
GLOBAL_MEMORY = {
    "price": {"symbol": "BTC-USD", "price": 0.00},
    "prediction": {
        "bias": "NEUTRAL", 
        "probability": 50, 
        "narrative": "AI is calibrating market data...",
        "trade_setup": {"entry": 0, "tp": 0, "sl": 0, "valid": False}
    },
    "history": [],
    "performance": {"wins": 0, "total": 0, "win_rate": 0}, # Session Scoreboard
    "active_trades": [], # Open paper trades
    "last_alert_time": 0
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
analyzer = SentimentIntensityAnalyzer()

# --- 🔔 DISCORD ALERT SYSTEM ---
def send_discord_alert(data):
    # Prevent spam (15 min cooldown)
    if time.time() - GLOBAL_MEMORY["last_alert_time"] < 900: return

    try:
        color = 5763719 if data['bias'] == "BULLISH" else 15548997
        embed = {
            "title": f"🚨 TRADE SIGNAL: {data['bias']} ({data['probability']}%)",
            "description": data['narrative'],
            "color": color,
            "fields": [
                {"name": "Entry", "value": f"${data['trade_setup']['entry']:,.2f}", "inline": True},
                {"name": "🎯 Take Profit (2.0R)", "value": f"${data['trade_setup']['tp']:,.2f}", "inline": True},
                {"name": "🛑 Stop Loss (1.0R)", "value": f"${data['trade_setup']['sl']:,.2f}", "inline": True}
            ],
            "footer": {"text": "ForwardFin AI • Institutional Grade Analysis"}
        }
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
        GLOBAL_MEMORY["last_alert_time"] = time.time()
        print("✅ Discord Alert Sent!", flush=True)
    except Exception as e:
        print(f"❌ Discord Error: {e}", flush=True)

# --- WORKER 1: REAL DATA STREAM ---
def run_real_data_stream():
    print("📡 DATA THREAD: Connecting to Coinbase...", flush=True)
    while True:
        try:
            url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            price = float(response.json()['data']['amount'])
            
            GLOBAL_MEMORY["price"] = {"symbol": "BTC-USD", "price": price}
            GLOBAL_MEMORY["history"].append(price)
            if len(GLOBAL_MEMORY["history"]) > 100: GLOBAL_MEMORY["history"].pop(0)
            
            print(f"✅ TICK: ${price:,.2f}", flush=True)
        except Exception as e:
            print(f"⚠️ Data Error: {e}", flush=True)
        time.sleep(3)

# --- WORKER 2: AI BRAIN & SELF-GRADING ENGINE ---
def run_fundamental_brain():
    print("🧠 BRAIN THREAD: Starting...", flush=True)
    while True:
        try:
            # 1. Fetch News
            headlines = []
            avg_sentiment = 0.0
            top_story = "No major news."
            try:
                resp = requests.get("https://cointelegraph.com/rss", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                root = ET.fromstring(resp.content)
                for item in root.findall('./channel/item')[:5]:
                    headlines.append(item.find('title').text)
                if headlines:
                    avg_sentiment = sum([analyzer.polarity_scores(h)['compound'] for h in headlines]) / len(headlines)
                    top_story = headlines[0]
            except: pass

            # 2. Analyze Technicals
            prices = GLOBAL_MEMORY["history"]
            if len(prices) > 20:
                series = pd.Series(prices)
                current_price = prices[-1]
                
                # RSI & Volatility
                delta = series.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                rsi_val = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
                volatility = series.rolling(20).std().iloc[-1]
                if pd.isna(volatility) or volatility == 0: volatility = 50.0 

                # Decision Logic
                bias = "NEUTRAL"
                prob = 50
                
                if rsi_val < 40 and avg_sentiment > -0.1:
                    bias = "BULLISH"
                    prob = 78 + (avg_sentiment * 10)
                    tp = current_price + (3 * volatility)
                    sl = current_price - (1.5 * volatility)
                elif rsi_val > 60 and avg_sentiment < 0.1:
                    bias = "BEARISH"
                    prob = 78 - (avg_sentiment * 10)
                    tp = current_price - (3 * volatility)
                    sl = current_price + (1.5 * volatility)
                else:
                    tp = current_price * 1.01
                    sl = current_price * 0.99

                prob = min(max(int(prob), 10), 95)
                trade_setup = {"entry": current_price, "tp": tp, "sl": sl, "valid": bias != "NEUTRAL"}
                
                sentiment_desc = "POSITIVE" if avg_sentiment > 0.05 else ("NEGATIVE" if avg_sentiment < -0.05 else "NEUTRAL")
                narrative = (
                    f"Market is {bias}. Fundamentals are {sentiment_desc} (Score: {avg_sentiment:.2f}) driven by top story: '{top_story}'. "
                    f"Technicals show RSI at {rsi_val:.1f}. Stops adjusted for volatility (${volatility:.2f})."
                )

                GLOBAL_MEMORY["prediction"] = {
                    "bias": bias,
                    "probability": prob,
                    "narrative": narrative,
                    "trade_setup": trade_setup
                }

                # --- 3. TRADE MANAGEMENT (Updated for 70% Rule) ---
                
                # A. Open 'Paper Trade' ONLY if Confidence >= 70%
                if prob >= 70 and bias != "NEUTRAL":
                    if not any(t for t in GLOBAL_MEMORY["active_trades"] if time.time() - t['time'] < 300):
                        GLOBAL_MEMORY["active_trades"].append({
                            "type": bias,
                            "entry": current_price,
                            "time": time.time()
                        })
                        send_discord_alert(GLOBAL_MEMORY["prediction"])

                # B. Grade old trades (Check 5 mins later)
                for trade in GLOBAL_MEMORY["active_trades"][:]:
                    if time.time() - trade['time'] > 300: # 5 minutes passed
                        is_win = False
                        if trade['type'] == "BULLISH" and current_price > trade['entry']: is_win = True
                        if trade['type'] == "BEARISH" and current_price < trade['entry']: is_win = True
                        
                        GLOBAL_MEMORY["performance"]["total"] += 1
                        if is_win: GLOBAL_MEMORY["performance"]["wins"] += 1
                        
                        wins = GLOBAL_MEMORY["performance"]["wins"]
                        total = GLOBAL_MEMORY["performance"]["total"]
                        GLOBAL_MEMORY["performance"]["win_rate"] = int((wins / total) * 100) if total > 0 else 0
                        
                        GLOBAL_MEMORY["active_trades"].remove(trade)
                        print(f"⚖️ TRADE GRADED: {trade['type']} Win? {is_win}", flush=True)

        except Exception as e:
            print(f"❌ Brain Error: {e}", flush=True)
        time.sleep(10)

# --- WORKER 3: THE RICH WEBSITE (Academy + Win Rate) ---
@app.get("/")
async def root():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ForwardFin | Live AI Terminal</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #f8fafc; color: #334155; }
        .chart-container { position: relative; width: 100%; max-width: 600px; margin: auto; height: 300px; }
        @media (min-width: 768px) { .chart-container { height: 350px; } }
        .arch-layer { transition: all 0.3s ease; cursor: pointer; border-left: 4px solid transparent; }
        .arch-layer:hover { background-color: #f1f5f9; transform: translateX(4px); }
        .arch-layer.active { background-color: #e0f2fe; border-left-color: #0284c7; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .custom-scroll::-webkit-scrollbar { width: 6px; }
        .custom-scroll::-webkit-scrollbar-track { background: #f1f5f9; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
        .lesson-card { cursor: pointer; transition: all 0.2s; border-left: 4px solid transparent; }
        .lesson-card:hover { background: #f1f5f9; }
        .lesson-card.active { background: #e0f2fe; border-left-color: #0284c7; }
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
                    <div id="hero-badge" class="inline-flex items-center px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 text-xs font-semibold uppercase tracking-wide">
                        System Status: ONLINE | LIVE DATA
                    </div>
                    <h1 class="text-4xl sm:text-5xl font-extrabold text-slate-900 leading-tight">
                        Trading logic,<br>
                        <span class="text-sky-600">powered by Real-Time AI.</span>
                    </h1>
                    <p class="text-lg text-slate-600 max-w-lg">
                        ForwardFin is currently tracking <strong>BTC-USD</strong> on Coinbase. 
                        It analyzes technicals and news sentiment to generate discord alerts and risk-managed trade setups.
                    </p>
                </div>
                <div class="grid grid-cols-3 gap-4">
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">AI Confidence</h3>
                        <div style="height: 100px; width: 100px; position: relative;"><canvas id="heroChart"></canvas></div>
                        <p id="hero-bias" class="text-sm font-bold text-slate-800 mt-2">---</p>
                    </div>
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Market Risk</h3>
                        <div class="h-[100px] w-[100px] flex items-center justify-center relative">
                            <div class="absolute inset-0 rounded-full border-8 border-slate-100"></div>
                            <div id="risk-circle" class="absolute inset-0 rounded-full border-8 border-transparent border-t-emerald-500 transition-all duration-700 rotate-45"></div>
                            <div class="text-center z-10"><span id="risk-text" class="text-xl font-black text-emerald-500">LOW</span></div>
                        </div>
                        <p class="text-xs text-slate-400 mt-2">Volatility</p>
                    </div>
                    <div class="bg-white p-4 rounded-2xl shadow-lg border border-slate-100 flex flex-col items-center justify-center">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Live Accuracy</h3>
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
                    <h3 class="font-bold text-white flex items-center gap-2"><span>📈</span> Institutional Price Action</h3>
                    <span class="text-xs text-slate-500 font-mono">SOURCE: TRADINGVIEW</span>
                </div>
                <div class="h-[500px] w-full" id="tradingview_chart"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                <script type="text/javascript">
                new TradingView.widget({ "autosize": true, "symbol": "COINBASE:BTCUSD", "interval": "1", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#f1f3f6", "enable_publishing": false, "hide_side_toolbar": false, "allow_symbol_change": true, "container_id": "tradingview_chart", "studies": ["RSI@tv-basicstudies", "MASimple@tv-basicstudies"] });
                </script>
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
                        <div class="font-mono text-sky-400">TARGET: BTC-USD (Live)</div>
                        <button id="analyze-btn" class="bg-sky-600 hover:bg-sky-500 text-white px-6 py-2 rounded text-sm font-bold transition-all shadow-lg">REFRESH ANALYSIS</button>
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
                                        <h4 class="text-xs font-bold text-sky-400 uppercase">Suggested Trade Setup (2:1 Reward)</h4>
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
                                    <h3 class="text-lg font-bold text-white mb-4 flex items-center gap-2"><span>🤖</span> AI Reasoning</h3>
                                    <p id="res-reason" class="text-slate-300 leading-relaxed font-light text-lg">Waiting for analysis command...</p>
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
                    <p class="mt-4 text-slate-600 max-w-2xl mx-auto">From Zero to Institutional Trader.</p>
                </div>
                
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 h-[500px]">
                    <div class="lg:col-span-4 bg-slate-50 border border-slate-200 rounded-xl overflow-hidden overflow-y-auto">
                        <div onclick="loadLesson(0)" class="lesson-card p-4 border-b border-slate-200 active">
                            <h4 class="font-bold text-slate-800">1. Basics: Structure & Candles</h4>
                            <p class="text-xs text-slate-500 mt-1">Start here if you are brand new.</p>
                        </div>
                        <div onclick="loadLesson(1)" class="lesson-card p-4 border-b border-slate-200">
                            <h4 class="font-bold text-slate-800">2. Liquidity: The Fuel</h4>
                            <p class="text-xs text-slate-500 mt-1">Why price moves where it moves.</p>
                        </div>
                        <div onclick="loadLesson(2)" class="lesson-card p-4 border-b border-slate-200">
                            <h4 class="font-bold text-slate-800">3. Strategy: The Asia Sweep</h4>
                            <p class="text-xs text-slate-500 mt-1">Trading the London Open fakeout.</p>
                        </div>
                        <div onclick="loadLesson(3)" class="lesson-card p-4 border-b border-slate-200">
                            <h4 class="font-bold text-slate-800">4. Strategy: Divergences</h4>
                            <p class="text-xs text-slate-500 mt-1">Spotting reversals with ES/NQ.</p>
                        </div>
                        <div onclick="loadLesson(4)" class="lesson-card p-4 border-b border-slate-200">
                            <h4 class="font-bold text-slate-800">5. Risk: Survival Rules</h4>
                            <p class="text-xs text-slate-500 mt-1">Position sizing for small accounts.</p>
                        </div>
                    </div>

                    <div class="lg:col-span-8 bg-white border border-slate-200 rounded-xl p-8 flex flex-col shadow-sm">
                        <h3 id="lesson-title" class="text-2xl font-bold text-sky-600 mb-4">Select a Lesson</h3>
                        <div id="lesson-body" class="text-slate-600 leading-relaxed mb-8 flex-grow overflow-y-auto">
                            Click a module on the left to start learning.
                        </div>
                        <div id="quiz-area" class="bg-slate-50 p-6 rounded-lg border border-slate-200 hidden">
                            <div class="font-bold text-slate-800 mb-2">💡 Quick Quiz</div>
                            <p id="quiz-question" class="text-sm text-slate-600 mb-4">...</p>
                            <div class="flex gap-4">
                                <button id="btn-a" onclick="checkAnswer('A')" class="px-4 py-2 bg-white border border-slate-300 rounded hover:bg-slate-100 text-sm font-bold text-slate-700">Option A</button>
                                <button id="btn-b" onclick="checkAnswer('B')" class="px-4 py-2 bg-white border border-slate-300 rounded hover:bg-slate-100 text-sm font-bold text-slate-700">Option B</button>
                            </div>
                            <div id="quiz-result" class="mt-3 text-sm font-bold"></div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section id="architecture" class="py-16 bg-slate-50 border-t border-slate-200">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="mb-10">
                    <h2 class="text-3xl font-bold text-slate-900">System Architecture</h2>
                    <p class="mt-4 text-slate-600 max-w-3xl">ForwardFin is built on a modular 5-layer stack. Click any layer for details.</p>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
                    <div class="lg:col-span-5 space-y-3">
                        <div onclick="selectLayer(0)" class="arch-layer active bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">1. Data Ingestion</h4><p class="text-xs text-slate-500 mt-1">Coinbase API / CoinTelegraph RSS</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(1)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">2. Analysis Engine</h4><p class="text-xs text-slate-500 mt-1">Pandas / NumPy / VADER</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(2)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">3. AI / ML Core</h4><p class="text-xs text-slate-500 mt-1">Sentiment & Technical Confluence</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
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
                            <p id="detail-desc" class="text-slate-600 mb-6 flex-grow">Handles real-time price ticks from Coinbase and Sentiment from News Feeds.</p>
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
        <div class="text-xs text-slate-600">&copy; 2025 ForwardFin. All rights reserved.</div>
    </footer>

    <script>
        // --- 1. ARCHITECTURE INTERACTIVITY ---
        const architectureData = [
            { title: "Data Ingestion", badge: "Infrastructure", description: "Connects to Coinbase Pro API for real-time price ticks and CoinTelegraph RSS for news headlines.", components: ["Coinbase API", "Python Requests", "XML Parsing"] },
            { title: "Analysis Engine", badge: "Data Science", description: "Calculates live RSI, Volatility (Std Dev), and moving averages using Pandas.", components: ["Pandas Rolling Windows", "NumPy Math"] },
            { title: "AI / ML Core", badge: "Machine Learning", description: "Uses VADER (Valence Aware Dictionary for Sentiment Reasoning) to score news, then combines it with Technicals.", components: ["VADER Sentiment", "Logic Gates", "Risk Calc"] },
            { title: "Alerting Layer", badge: "Notification", description: "When Confidence > 75%, constructs a rich embed payload and fires it to the Discord Webhook.", components: ["Discord API", "JSON Payloads"] },
            { title: "User Interface", badge: "Frontend", description: "Responsive dashboard served via FastAPI. Updates DOM elements live without refreshing.", components: ["FastAPI", "Tailwind CSS", "Chart.js", "TradingView"] }
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

            document.getElementById('nav-ticker').innerHTML = `<span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> ${data.price.symbol}: $${data.price.price.toLocaleString()}`;

            globalConfidence = data.prediction.probability;
            document.getElementById('hero-bias').innerText = data.prediction.bias;
            if (heroChart) {
                heroChart.data.datasets[0].data = [globalConfidence, 100 - globalConfidence];
                heroChart.data.datasets[0].backgroundColor = (data.prediction.bias === "BULLISH") ? ['#10b981', '#e2e8f0'] : ['#f43f5e', '#e2e8f0'];
                heroChart.update();
            }

            const riskText = document.getElementById('risk-text');
            if (riskText) {
                if (data.prediction.probability > 80) riskText.innerText = "HIGH";
                else riskText.innerText = "LOW";
            }

            // NEW: UPDATE WIN RATE
            const winRateEl = document.getElementById('win-rate');
            const winBarEl = document.getElementById('win-bar');
            const tradesEl = document.getElementById('total-trades');
            
            if (winRateEl && data.performance) {
                const wr = data.performance.win_rate;
                const total = data.performance.total;
                
                winRateEl.innerText = wr + "%";
                winBarEl.style.width = wr + "%";
                winBarEl.className = (wr >= 50) ? "bg-emerald-500 h-full transition-all duration-1000" : "bg-rose-500 h-full transition-all duration-1000";
                
                if (total === 0) {
                    tradesEl.innerText = "Calibrating (No trades yet)...";
                } else {
                    tradesEl.innerText = `${total} Paper Trades Validated`;
                }
            }

            const setup = data.prediction.trade_setup;
            const validEl = document.getElementById('setup-validity');
            if (setup && setup.valid) {
                if(validEl) { validEl.innerText = "ACTIVE"; validEl.className = "text-[10px] bg-emerald-600 px-2 py-1 rounded text-white"; }
                document.getElementById('setup-entry').innerText = "$" + setup.entry.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                document.getElementById('setup-tp').innerText = "$" + setup.tp.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                document.getElementById('setup-sl').innerText = "$" + setup.sl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            } else {
                if(validEl) { validEl.innerText = "WAITING"; validEl.className = "text-[10px] bg-slate-700 px-2 py-1 rounded text-slate-400"; }
            }
        }

        document.getElementById('analyze-btn').addEventListener('click', async () => {
            const btn = document.getElementById('analyze-btn');
            btn.innerText = "ANALYZING...";
            btn.disabled = true;
            
            const data = await fetchMarketData();
            await new Promise(r => setTimeout(r, 800)); // Fake delay for effect
            
            btn.innerText = "REFRESH ANALYSIS";
            btn.disabled = false;

            if (data) {
                document.getElementById('res-price').innerText = "$" + data.price.price.toLocaleString();
                const biasEl = document.getElementById('res-bias');
                biasEl.innerText = data.prediction.bias;
                biasEl.className = (data.prediction.bias === "BULLISH") ? "text-xl font-bold mt-1 text-emerald-400" : "text-xl font-bold mt-1 text-rose-400";
                
                document.getElementById('res-prob').innerText = data.prediction.probability + "%";
                document.getElementById('prob-bar').style.width = data.prediction.probability + "%";
                document.getElementById('res-reason').innerText = data.prediction.narrative;
            }
        });

        // --- 3. ACADEMY LOGIC ---
        const lessons = [
            {
                title: "1. Basics: Structure & Candles",
                body: "Before we trade, we must understand the language of the market. <br><br><b>1. Candlesticks:</b> A green candle means price went UP (Closed higher than it Opened). A red candle means price went DOWN. The 'Wicks' (thin lines) show how far price reached before pulling back. <br><br><b>2. Trends:</b> Prices don't move in straight lines. They move in waves. <br>- <b>Uptrend:</b> Making Higher Highs and Higher Lows. <br>- <b>Downtrend:</b> Making Lower Highs and Lower Lows.",
                question: "In an Uptrend, what should you generally look for?",
                a: "Lower Highs",
                b: "Higher Highs",
                correct: "B",
                explanation: "Correct! Uptrends are defined by price consistently making new highs."
            },
            {
                title: "2. Liquidity: The Fuel",
                body: "Why does price move? It seeks <b>Liquidity</b>. <br><br>Liquidity is just a fancy word for 'Orders'. Big institutions need to buy huge amounts, so they drive price to where lots of people have their Stop Losses (which are sell orders). <br><br>Common Liquidity Zones: <br>- <b>Asia Highs/Lows:</b> The high and low price reached during the Asian session (overnight). <br>- <b>Data Wicks:</b> Wicks created by news events (CPI, NFP).",
                question: "Why does price often target the Asia Highs or Lows?",
                a: "Because there is a lot of liquidity (Stop Losses) there.",
                b: "Because it's a random movement.",
                correct: "A",
                explanation: "Correct! The market seeks these areas to fill large institutional orders."
            },
            {
                title: "3. Strategy: The Asia Sweep",
                body: "Now we can learn a strategy. <br><br><b>Step 1:</b> Identify the High and Low of the Asian Session. <br><b>Step 2:</b> Wait for the London Session (8am - 10am). <br><b>Step 3:</b> Watch for a 'Sweep'. This is when price breaks the High/Low but then CLOSES back inside the range. This is a fake-out! <br><br><b>Step 4:</b> Enter a reversal trade targeting the opposite side.",
                question: "For a valid Asia Sweep, what must the candle do after breaking the level?",
                a: "Keep going in that direction.",
                b: "Close back inside the range (Fakeout).",
                correct: "B",
                explanation: "Correct! The 'Close back inside' confirms it was just a liquidity grab, not a breakout."
            },
            {
                title: "4. Strategy: Divergences",
                body: "A Divergence is a crack in the market's armor. We look at two correlated assets, like <b>NQ (Tech Stocks)</b> and <b>ES (S&P 500)</b>. They should move together. <br><br><b>Bearish Divergence:</b> NQ makes a Higher High, but ES makes a Lower High. This shows weakness (one is failing to keep up). <br><b>Bullish Divergence:</b> NQ makes a Lower Low, but ES makes a Higher Low. This shows hidden strength.",
                question: "NQ makes a Higher High, but ES makes a Lower High. What is this?",
                a: "Bearish Divergence (Reversal Signal)",
                b: "Bullish Continuation",
                correct: "A",
                explanation: "Correct! Disagreement between correlated assets often precedes a reversal."
            },
            {
                title: "5. Risk: Survival Rules",
                body: "You cannot trade if you lose all your money. Preservation is #1. <br><br><b>Rule 1: Stop Losses.</b> Never trade without one. It stops a scratch from becoming a gash. <br><b>Rule 2: Position Sizing.</b> For a small account (e.g., $100), use the smallest size possible (0.01 lots). <br><b>Rule 3: Timing.</b> The best days to trade are Tuesday, Wednesday, and Thursday. Mondays and Fridays are often choppy.",
                question: "What is the primary goal of a trader?",
                a: "To make a million dollars quickly.",
                b: "To protect capital (Preservation).",
                correct: "B",
                explanation: "Correct! If you survive, you can thrive. Protect your downside first."
            }
        ];

        let currentLesson = 0;

        function loadLesson(index) {
            currentLesson = index;
            const l = lessons[index];
            document.getElementById('lesson-title').innerText = l.title;
            document.getElementById('lesson-body').innerHTML = l.body;
            document.getElementById('quiz-area').classList.remove('hidden');
            document.getElementById('quiz-question').innerText = l.question;
            document.getElementById('btn-a').innerText = l.a;
            document.getElementById('btn-b').innerText = l.b;
            document.getElementById('quiz-result').innerText = "";
            
            document.querySelectorAll('.lesson-card').forEach((el, i) => {
                if(i === index) el.classList.add('active', 'bg-sky-50', 'border-l-sky-600');
                else el.classList.remove('active', 'bg-sky-50', 'border-l-sky-600');
            });
        }

        function checkAnswer(answer) {
            const l = lessons[currentLesson];
            const res = document.getElementById('quiz-result');
            if (answer === l.correct) {
                res.innerHTML = `<span class="text-emerald-600">✅ ${l.explanation}</span>`;
            } else {
                res.innerHTML = `<span class="text-rose-600">❌ Incorrect. Try again!</span>`;
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            initHeroChart();
            selectLayer(0);
            loadLesson(0);
            updateDashboard();
            setInterval(updateDashboard, 3000);
        });
    </script>
</body>
</html>
""")

@app.get("/api/live-data")
async def get_api():
    return GLOBAL_MEMORY

if __name__ == "__main__":
    t1 = threading.Thread(target=run_real_data_stream, daemon=True)
    t2 = threading.Thread(target=run_fundamental_brain, daemon=True)
    t1.start()
    t2.start()
    print("🚀 SYSTEM LAUNCH: Port 10000")
    uvicorn.run(app, host="0.0.0.0", port=10000)