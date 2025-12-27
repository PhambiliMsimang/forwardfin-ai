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
# Discord Webhook inserted below
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
    "last_alert_time": 0
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
analyzer = SentimentIntensityAnalyzer()

# --- 🔔 DISCORD ALERT SYSTEM ---
def send_discord_alert(data):
    # Don't spam: Only alert once every 15 minutes to keep it high quality
    if time.time() - GLOBAL_MEMORY["last_alert_time"] < 900:
        return

    try:
        color = 5763719 if data['bias'] == "BULLISH" else 15548997
        embed = {
            "title": f"🚨 TRADE SIGNAL: {data['bias']} ({data['probability']}%)",
            "description": data['narrative'],
            "color": color,
            "fields": [
                {"name": "Entry Price", "value": f"${data['trade_setup']['entry']:,.2f}", "inline": True},
                {"name": "🎯 Take Profit (2.0x)", "value": f"${data['trade_setup']['tp']:,.2f}", "inline": True},
                {"name": "🛑 Stop Loss (1.0x)", "value": f"${data['trade_setup']['sl']:,.2f}", "inline": True}
            ],
            "footer": {"text": "ForwardFin Academy • Learning through Live Action"}
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

# --- WORKER 2: AI BRAIN & TRADE ARCHITECT ---
def run_fundamental_brain():
    print("🧠 BRAIN THREAD: Starting...", flush=True)
    while True:
        try:
            # 1. Fetch News
            headlines = []
            avg_sentiment = 0.0
            try:
                resp = requests.get("https://cointelegraph.com/rss", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                root = ET.fromstring(resp.content)
                for item in root.findall('./channel/item')[:5]:
                    headlines.append(item.find('title').text)
                if headlines:
                    avg_sentiment = sum([analyzer.polarity_scores(h)['compound'] for h in headlines]) / len(headlines)
            except: pass

            # 2. Analyze Technicals
            prices = GLOBAL_MEMORY["history"]
            if len(prices) > 20:
                # RSI Calculation
                series = pd.Series(prices)
                delta = series.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                rsi_val = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
                
                # Volatility (Standard Deviation) for TP/SL
                # We use this to set dynamic stops based on market noise
                volatility = series.rolling(20).std().iloc[-1]
                if pd.isna(volatility) or volatility == 0: volatility = 50.0 

                # 3. Decision Logic
                bias = "NEUTRAL"
                prob = 50
                entry = prices[-1]
                
                # Signal Generation (Confluence of RSI + News)
                if rsi_val < 40 and avg_sentiment > -0.1:
                    bias = "BULLISH"
                    prob = 78 + (avg_sentiment * 10)
                    # Long Strategy: TP is 4x vol, SL is 2x vol (2:1 Ratio)
                    tp = entry + (4 * volatility)
                    sl = entry - (2 * volatility)
                
                elif rsi_val > 60 and avg_sentiment < 0.1:
                    bias = "BEARISH"
                    prob = 78 - (avg_sentiment * 10)
                    # Short Strategy
                    tp = entry - (4 * volatility)
                    sl = entry + (2 * volatility)
                
                else:
                    # Neutral state - keep values strictly hypothetical
                    tp = entry * 1.01
                    sl = entry * 0.99

                # 4. Update Memory
                prob = min(max(int(prob), 10), 95)
                trade_setup = {"entry": entry, "tp": tp, "sl": sl, "valid": bias != "NEUTRAL"}
                
                narrative = (
                    f"Market is {bias}. RSI ({rsi_val:.1f}) suggests {'oversold' if rsi_val<40 else 'overbought' if rsi_val>60 else 'neutral'} conditions. "
                    f"News sentiment is {avg_sentiment:.2f}. "
                    f"Stops set based on current volatility of ${volatility:.2f}."
                )

                GLOBAL_MEMORY["prediction"] = {
                    "bias": bias,
                    "probability": prob,
                    "narrative": narrative,
                    "trade_setup": trade_setup
                }

                # 5. Send Alert if Confidence > 75%
                if prob > 75 and bias != "NEUTRAL":
                    send_discord_alert(GLOBAL_MEMORY["prediction"])

        except Exception as e:
            print(f"❌ Brain Error: {e}", flush=True)
        time.sleep(10)

# --- WORKER 3: THE WEBSITE ---
@app.get("/")
async def root():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ForwardFin | Live Academy</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #e2e8f0; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); }
        .btn { background: #0ea5e9; color: white; padding: 10px 20px; border-radius: 8px; font-weight: bold; transition: 0.2s; cursor: pointer; }
        .btn:hover { background: #0284c7; transform: translateY(-1px); }
        .lesson-card { cursor: pointer; transition: all 0.2s; border-left: 4px solid transparent; }
        .lesson-card:hover { background: #334155; }
        .lesson-card.active { background: #1e293b; border-left-color: #0ea5e9; }
        .stat-box { background: rgba(15, 23, 42, 0.6); border-radius: 8px; padding: 12px; }
    </style>
</head>
<body class="flex flex-col min-h-screen">

    <nav class="border-b border-slate-700 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="h-8 w-8 bg-gradient-to-br from-sky-500 to-indigo-600 rounded-lg flex items-center justify-center text-white font-bold">FF</div>
                <div class="font-black text-2xl text-white tracking-tighter">FORWARD<span class="text-sky-500">FIN</span></div>
            </div>
            <div id="price-ticker" class="font-mono text-emerald-400 font-bold bg-emerald-500/10 px-4 py-2 rounded-full border border-emerald-500/20">Connecting...</div>
        </div>
    </nav>

    <main class="flex-grow max-w-7xl mx-auto w-full p-6 space-y-8">
        
        <section class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="card lg:col-span-1 space-y-6 flex flex-col justify-center">
                <div>
                    <div class="text-xs text-slate-400 uppercase font-bold tracking-widest mb-1">AI Signal</div>
                    <div id="bias-display" class="text-5xl font-black text-white tracking-tight">---</div>
                </div>
                <div>
                    <div class="flex justify-between text-sm text-slate-400 mb-2">
                        <span>Confidence</span>
                        <span id="conf-text" class="text-white font-bold">0%</span>
                    </div>
                    <div class="w-full bg-slate-700 h-3 rounded-full overflow-hidden">
                        <div id="conf-bar" class="bg-sky-500 h-full w-0 transition-all duration-1000 ease-out"></div>
                    </div>
                </div>
            </div>

            <div class="card lg:col-span-2 flex flex-col justify-center relative overflow-hidden">
                <div class="absolute top-0 right-0 p-4 opacity-10 text-9xl">🎯</div>
                <div class="flex items-center justify-between mb-6">
                    <div class="text-xs text-slate-400 uppercase font-bold tracking-widest">Suggested Trade Setup (2:1 Ratio)</div>
                    <div id="setup-status" class="text-xs font-bold px-2 py-1 rounded bg-slate-700 text-slate-400">WAITING FOR SIGNAL</div>
                </div>
                
                <div class="grid grid-cols-3 gap-4 text-center">
                    <div class="stat-box border border-slate-600">
                        <div class="text-slate-500 text-xs font-bold mb-1">ENTRY PRICE</div>
                        <div id="setup-entry" class="text-2xl font-black text-white">---</div>
                    </div>
                    <div class="stat-box border border-emerald-500/30 bg-emerald-900/10">
                        <div class="text-emerald-500 text-xs font-bold mb-1">TAKE PROFIT (Target)</div>
                        <div id="setup-tp" class="text-2xl font-black text-emerald-400">---</div>
                    </div>
                    <div class="stat-box border border-rose-500/30 bg-rose-900/10">
                        <div class="text-rose-500 text-xs font-bold mb-1">STOP LOSS (Risk)</div>
                        <div id="setup-sl" class="text-2xl font-black text-rose-400">---</div>
                    </div>
                </div>
                <div id="ai-narrative" class="mt-6 text-sm text-slate-300 font-mono bg-slate-900/50 p-4 rounded-lg border-l-4 border-sky-500">
                    > System Initializing...
                </div>
            </div>
        </section>

        <section>
            <div class="flex items-center gap-3 mb-6">
                <span class="text-3xl">🎓</span>
                <h2 class="text-3xl font-bold text-white">Trader's Academy</h2>
            </div>
            
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[600px]">
                
                <div class="lg:col-span-4 bg-slate-800 rounded-2xl overflow-y-auto border border-slate-700 custom-scroll">
                    <div class="p-4 bg-slate-900/50 border-b border-slate-700 font-bold text-sky-400 text-sm">COURSE MODULES</div>
                    <div onclick="loadLesson(0)" class="lesson-card p-5 border-b border-slate-700 active group">
                        <h3 class="font-bold text-white group-hover:text-sky-400 transition-colors">1. The Golden Rule</h3>
                        <p class="text-xs text-slate-400 mt-1">Risk Management & The 2:1 Ratio</p>
                    </div>
                    <div onclick="loadLesson(1)" class="lesson-card p-5 border-b border-slate-700 group">
                        <h3 class="font-bold text-white group-hover:text-sky-400 transition-colors">2. Understanding RSI</h3>
                        <p class="text-xs text-slate-400 mt-1">Detecting Overbought vs Oversold</p>
                    </div>
                    <div onclick="loadLesson(2)" class="lesson-card p-5 border-b border-slate-700 group">
                        <h3 class="font-bold text-white group-hover:text-sky-400 transition-colors">3. Stop Loss Placement</h3>
                        <p class="text-xs text-slate-400 mt-1">Using Volatility (ATR) to survive</p>
                    </div>
                    <div onclick="loadLesson(3)" class="lesson-card p-5 border-b border-slate-700 group">
                        <h3 class="font-bold text-white group-hover:text-sky-400 transition-colors">4. Market Sentiment</h3>
                        <p class="text-xs text-slate-400 mt-1">How News moves price</p>
                    </div>
                </div>

                <div class="lg:col-span-8 bg-slate-800 rounded-2xl border border-slate-700 p-8 flex flex-col relative shadow-2xl">
                    <h2 id="lesson-title" class="text-3xl font-black text-sky-400 mb-6">Select a Lesson</h2>
                    <div id="lesson-body" class="text-slate-300 text-lg leading-relaxed mb-8 flex-grow overflow-y-auto pr-4">
                        Welcome to the ForwardFin Academy. Click a module on the left to start learning how to trade professionally.
                    </div>
                    
                    <div id="quiz-area" class="bg-slate-900/80 p-6 rounded-xl border border-slate-600 hidden backdrop-blur-sm">
                        <div class="font-bold text-white mb-4 flex items-center gap-2"><span>💡</span> Quick Quiz</div>
                        <p id="quiz-question" class="text-md text-slate-300 mb-6">Question goes here...</p>
                        <div class="grid grid-cols-2 gap-4">
                            <button id="btn-a" onclick="checkAnswer('A')" class="btn bg-slate-700 hover:bg-slate-600 border border-slate-600 py-3">Option A</button>
                            <button id="btn-b" onclick="checkAnswer('B')" class="btn bg-slate-700 hover:bg-slate-600 border border-slate-600 py-3">Option B</button>
                        </div>
                        <div id="quiz-result" class="mt-4 text-center text-lg font-bold min-h-[30px]"></div>
                    </div>
                </div>
            </div>
        </section>

    </main>

    <script>
        // --- LIVE DATA FEED ---
        async function updateData() {
            try {
                const res = await fetch('/api/live-data');
                const data = await res.json();
                
                // Update Price
                document.getElementById('price-ticker').innerText = `${data.price.symbol}: $${data.price.price.toLocaleString()}`;
                
                // Update Bias
                const bias = data.prediction.bias;
                const biasEl = document.getElementById('bias-display');
                biasEl.innerText = bias;
                biasEl.className = bias === "BULLISH" ? "text-5xl font-black text-emerald-400 tracking-tight" : (bias === "BEARISH" ? "text-5xl font-black text-rose-400 tracking-tight" : "text-5xl font-black text-slate-400 tracking-tight");
                
                // Update Confidence
                document.getElementById('conf-text').innerText = data.prediction.probability + "%";
                document.getElementById('conf-bar').style.width = data.prediction.probability + "%";
                
                // Update Narrative
                document.getElementById('ai-narrative').innerText = "> " + data.prediction.narrative;

                // Update Trade Setup
                const setup = data.prediction.trade_setup;
                const statusEl = document.getElementById('setup-status');
                
                if (setup && setup.valid) {
                    statusEl.innerText = "ACTIVE SETUP";
                    statusEl.className = "text-xs font-bold px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
                    document.getElementById('setup-entry').innerText = "$" + setup.entry.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    document.getElementById('setup-tp').innerText = "$" + setup.tp.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    document.getElementById('setup-sl').innerText = "$" + setup.sl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                } else {
                    statusEl.innerText = "WAITING FOR SIGNAL";
                    statusEl.className = "text-xs font-bold px-2 py-1 rounded bg-slate-700 text-slate-400";
                    document.getElementById('setup-entry').innerText = "---";
                    document.getElementById('setup-tp').innerText = "---";
                    document.getElementById('setup-sl').innerText = "---";
                }

            } catch(e) { console.log(e); }
        }
        setInterval(updateData, 3000);

        // --- ACADEMY CONTENT ---
        const lessons = [
            {
                title: "1. The Golden Rule: 2:1 Ratio",
                body: "Never enter a trade unless you can make $2 for every $1 you risk. <br><br>Imagine flipping a coin. If heads (win), you get $200. If tails (loss), you lose $100. Even if you only win 50% of the time, you will be profitable. <br><br><b>ForwardFin calculates this automatically:</b> Look at the trade card above. The Green number (TP) is always 2x larger than the distance to the Red number (SL).",
                question: "If your Stop Loss risks $50, where should your Take Profit be?",
                a: "$50 profit (1:1 Ratio)",
                b: "$100 profit (2:1 Ratio)",
                correct: "B",
                explanation: "Correct! Risking $50 to make $100 creates a positive expectancy."
            },
            {
                title: "2. Understanding RSI",
                body: "The Relative Strength Index (RSI) is like a speedometer for price. <br><br><b>Above 70 (Overbought):</b> The car is going too fast. It might crash (reverse down). <br><b>Below 30 (Oversold):</b> The car is stopped. It might start moving (reverse up). <br><br>ForwardFin uses this to decide if it's safe to buy. We rarely buy when RSI is > 70.",
                question: "RSI is currently at 85. What does this usually mean?",
                a: "Price is Overbought (Likely to drop)",
                b: "Price is Oversold (Likely to rise)",
                correct: "A",
                explanation: "Correct! High RSI (>70) suggests the buyers are exhausted."
            },
            {
                title: "3. Stop Loss Placement",
                body: "Where do you put your safety net? <br><br>If you put it too close, normal market wiggles will kick you out. If you put it too far, you lose too much money. <br><br>ForwardFin uses <b>Volatility (Standard Deviation)</b>. We measure how much Bitcoin jumps around on average, and place the Stop Loss exactly 2 jumps away. This gives the trade room to breathe.",
                question: "Why shouldn't you place a tight Stop Loss in a volatile market?",
                a: "You will lose more money.",
                b: "You will get stopped out by random noise.",
                correct: "B",
                explanation: "Correct! Volatile markets need wider stops to avoid random noise."
            },
            {
                title: "4. Market Sentiment",
                body: "Charts don't tell the whole story. News does. <br><br>ForwardFin reads CoinTelegraph RSS feeds every 60 seconds using an AI library called VADER. <br><br>If the news is scary (FUD), we lower our Buy confidence. If the news is hype, we increase it. <br><br><b>Never fight the news trend.</b>",
                question: "If RSI says BUY but News says SELL (Bad News), what should you do?",
                a: "Buy anyway.",
                b: "Wait or Reduce Position Size.",
                correct: "B",
                explanation: "Correct! When signals conflict, cash is a position. Wait for clarity."
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
            
            // Update active state in menu
            document.querySelectorAll('.lesson-card').forEach((el, i) => {
                if(i === index) el.classList.add('active', 'bg-slate-700', 'border-l-sky-500');
                else el.classList.remove('active', 'bg-slate-700', 'border-l-sky-500');
            });
        }

        function checkAnswer(answer) {
            const l = lessons[currentLesson];
            const res = document.getElementById('quiz-result');
            if (answer === l.correct) {
                res.innerHTML = `<span class="text-emerald-400">✅ ${l.explanation}</span>`;
            } else {
                res.innerHTML = `<span class="text-rose-400">❌ Incorrect. Try again!</span>`;
            }
        }

        // Load first lesson on start
        loadLesson(0);
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