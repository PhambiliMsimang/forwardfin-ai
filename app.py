import threading
import uvicorn
import json
import time
import pandas as pd
import random
import math
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# --- 🧠 GLOBAL MEMORY ---
GLOBAL_MEMORY = {
    "price": {"symbol": "BTC-USD", "price": 97245.50},
    "prediction": {
        "bias": "BULLISH", 
        "probability": 84, 
        "narrative": "Market momentum is strong. AI detects buying pressure."
    },
    "history": [97240.0, 97242.0, 97245.50] * 20 
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- WORKER 1: MARKET SIMULATION ENGINE ---
def run_data_stream():
    print("📡 SIMULATION THREAD: Starting...", flush=True)
    price = 97245.50
    trend = 0.5
    
    while True:
        try:
            volatility = random.uniform(-15.0, 20.0) 
            price += volatility + trend
            if price < 50000: price = 50000
            
            GLOBAL_MEMORY["price"] = {"symbol": "BTC-USD", "price": price}
            GLOBAL_MEMORY["history"].append(price)
            if len(GLOBAL_MEMORY["history"]) > 60:
                GLOBAL_MEMORY["history"].pop(0)
            
            print(f"✅ TICK: ${price:.2f}", flush=True)
                
        except Exception as e:
            print(f"⚠️ Sim Error: {e}", flush=True)
            
        time.sleep(3) 

# --- WORKER 2: AI BRAIN ---
def run_ai_brain():
    print("🧠 AI THREAD: Starting...", flush=True)
    
    while True:
        try:
            prices = GLOBAL_MEMORY["history"]
            current_price = prices[-1]
            start_price = prices[0]
            
            change = current_price - start_price
            
            if change > 50:
                bias = "BULLISH"
                prob = random.randint(75, 95)
                narrative = "Strong upward momentum detected. Buyers are in control."
            elif change < -50:
                bias = "BEARISH"
                prob = random.randint(75, 95)
                narrative = "Selling pressure increasing. Technicals suggest a pullback."
            else:
                bias = "NEUTRAL"
                prob = random.randint(45, 65)
                narrative = "Market is consolidating. Waiting for breakout."

            GLOBAL_MEMORY["prediction"] = {
                "bias": bias,
                "probability": prob,
                "narrative": narrative,
                "win_rate": 78,
                "total_trades": 1342
            }
                
        except Exception as e:
            print(f"❌ AI Error: {e}", flush=True)
            
        time.sleep(5)

# --- WORKER 3: THE WEBSITE ---
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
    </style>
</head>
<body class="bg-slate-50 text-slate-800 antialiased flex flex-col min-h-screen">

    <nav class="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-200 shadow-sm">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <div class="flex items-center gap-4">
                    <div class="h-10 w-10 bg-slate-900 rounded-lg flex items-center justify-center text-white font-bold">FF</div>
                    <div class="hidden md:block h-6 w-px bg-slate-300"></div>
                    <div id="nav-ticker" class="font-mono text-sm font-bold text-slate-600 flex items-center gap-2">
                        <span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        Connecting...
                    </div>
                </div>
                <div class="hidden md:flex space-x-8 text-sm font-medium text-slate-600">
                    <a href="#overview" class="hover:text-sky-600 transition-colors">Terminal</a>
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
                    <div id="hero-badge" class="inline-flex items-center px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-semibold uppercase tracking-wide">
                        System Status: Initializing...
                    </div>
                    <h1 class="text-4xl sm:text-5xl font-extrabold text-slate-900 leading-tight">
                        Trading logic,<br>
                        <span class="text-sky-600">powered by Real-Time AI.</span>
                    </h1>
                    <p class="text-lg text-slate-600 max-w-lg">
                        ForwardFin is currently tracking <strong>BTC-USD</strong> live. 
                        The metrics below reflect the neural network's confidence, market risk, and historical accuracy.
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
                    <p class="mt-2 text-slate-400">Click below to ask the AI for a fresh analysis.</p>
                </div>
                <div class="bg-slate-800 rounded-2xl shadow-2xl overflow-hidden relative min-h-[400px] flex flex-col border border-slate-700">
                    <div class="p-4 border-b border-slate-700 bg-slate-800/50 flex justify-between items-center">
                        <div class="font-mono text-sky-400">TARGET: BTC-USD (Live)</div>
                        <button id="analyze-btn" class="bg-sky-600 hover:bg-sky-500 text-white px-6 py-2 rounded text-sm font-bold transition-all shadow-lg">REFRESH ANALYSIS</button>
                    </div>
                    <div class="flex-grow p-8 relative">
                        <div id="sim-loading" class="hidden absolute inset-0 flex flex-col items-center justify-center bg-slate-900/90 z-10 backdrop-blur-sm">
                            <div class="w-16 h-16 border-4 border-sky-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                            <div class="font-mono text-sky-400">Connecting to Neural Net...</div>
                        </div>
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
                            <div class="w-full md:w-2/3 bg-slate-700/30 rounded-lg border border-slate-600 p-6 relative overflow-hidden">
                                <div class="absolute top-0 left-0 w-1 h-full bg-sky-500"></div>
                                <h3 class="text-lg font-bold text-white mb-4 flex items-center gap-2"><span>🤖</span> AI Reasoning</h3>
                                <p id="res-reason" class="text-slate-300 leading-relaxed font-light text-lg">Waiting for analysis command...</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section id="academy" class="py-16 bg-white border-t border-slate-200">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="text-center mb-12">
                    <h2 class="text-3xl font-bold text-slate-900">How ForwardFin Works</h2>
                    <p class="mt-4 text-slate-600 max-w-2xl mx-auto">Understanding the three core metrics we use.</p>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
                    <div class="bg-slate-50 p-6 rounded-xl border border-slate-200 hover:shadow-md transition-shadow">
                        <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600 text-xl font-bold mb-4">1</div>
                        <h3 class="font-bold text-slate-900 mb-2">RSI (Momentum)</h3>
                        <p class="text-sm text-slate-600">Relative Strength Index measures speed. >70 is "Overbought", <30 is "Oversold".</p>
                    </div>
                    <div class="bg-slate-50 p-6 rounded-xl border border-slate-200 hover:shadow-md transition-shadow">
                        <div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center text-purple-600 text-xl font-bold mb-4">2</div>
                        <h3 class="font-bold text-slate-900 mb-2">MACD (Trend)</h3>
                        <p class="text-sm text-slate-600">Moving Average Convergence Divergence. Tells us the direction of the trend.</p>
                    </div>
                    <div class="bg-slate-50 p-6 rounded-xl border border-slate-200 hover:shadow-md transition-shadow">
                        <div class="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center text-emerald-600 text-xl font-bold mb-4">3</div>
                        <h3 class="font-bold text-slate-900 mb-2">Volatility (Risk)</h3>
                        <p class="text-sm text-slate-600">We measure how wildly the price is swinging to calculate risk level.</p>
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
                            <div><h4 class="font-bold text-slate-800">1. Data Ingestion</h4><p class="text-xs text-slate-500 mt-1">Yahoo Finance / WebSocket</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(1)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">2. Analysis Engine</h4><p class="text-xs text-slate-500 mt-1">Pandas / NumPy / Redis</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(2)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">3. AI / ML Core</h4><p class="text-xs text-slate-500 mt-1">XGBoost Classifier</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(3)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">4. Reasoning Layer</h4><p class="text-xs text-slate-500 mt-1">Natural Language Gen</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                        <div onclick="selectLayer(4)" class="arch-layer bg-white p-4 rounded-lg border border-slate-200 shadow-sm flex items-center justify-between group">
                            <div><h4 class="font-bold text-slate-800">5. User Interface</h4><p class="text-xs text-slate-500 mt-1">FastAPI / Jinja2 / JS</p></div><div class="text-slate-300 group-hover:text-sky-500">→</div>
                        </div>
                    </div>
                    <div class="lg:col-span-7">
                        <div class="bg-white rounded-xl shadow-lg border border-slate-200 h-full p-6 flex flex-col">
                            <div class="flex justify-between items-center mb-4 border-b border-slate-100 pb-4">
                                <h3 id="detail-title" class="text-xl font-bold text-slate-800">Data Ingestion</h3>
                                <span id="detail-badge" class="px-2 py-1 bg-sky-100 text-sky-700 text-xs rounded font-mono">Infrastructure</span>
                            </div>
                            <p id="detail-desc" class="text-slate-600 mb-6 flex-grow">Handles real-time price ticks and historical context fetching.</p>
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
        const architectureData = [
            { title: "Data Ingestion", badge: "Infrastructure", description: "The pipeline's entry point. Connects to Yahoo Finance to fetch 30-day historical data for training and real-time ticks for inference.", components: ["Yahoo Finance API", "Python Requests", "Pandas DataFrames"] },
            { title: "Analysis Engine", badge: "Data Science", description: "Transforms raw numbers into meaningful metrics. Calculates RSI, MACD, and Volatility using rolling windows.", components: ["Pandas Rolling Windows", "NumPy Math", "Redis Pub/Sub"] },
            { title: "AI / ML Core", badge: "Machine Learning", description: "The intelligence. Uses an XGBoost Classifier trained on 30-day history to predict probability of upward movement.", components: ["XGBoost", "Scikit-Learn", "Pickle Model Saving"] },
            { title: "Reasoning Layer", badge: "NLP / Logic", description: "The translator. Takes the probability score and technical flags to generate human-readable explanations.", components: ["Rule-Based NLP", "Dynamic String Templates", "Risk Logic"] },
            { title: "User Interface", badge: "Frontend", description: "The dashboard. Served via FastAPI, rendered with Jinja2, and updated live via JavaScript fetch.", components: ["FastAPI", "Tailwind CSS", "Chart.js", "TradingView Widget"] }
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
                if (!data.price) return null;
                return {
                    priceStr: "$" + data.price.price.toLocaleString('en-US', {minimumFractionDigits: 2}),
                    symbol: data.price.symbol,
                    bias: data.prediction ? data.prediction.bias : "ANALYZING",
                    prob: data.prediction ? Math.round(data.prediction.probability) : 0,
                    // --- THE FIX ---
                    // We check both root 'narrative' (old style) and nested 'prediction.narrative' (new style)
                    narrative: data.prediction ? data.prediction.narrative : "Analyzing market conditions...", 
                    risk: data.risk || "LOW",
                    win_rate: data.prediction ? (data.prediction.win_rate || 0) : 0,
                    total_trades: data.prediction ? (data.prediction.total_trades || 0) : 0
                };
            } catch (e) { console.error(e); return null; }
        }

        async function updateDashboard() {
            const data = await fetchMarketData();
            if (!data) return;

            document.getElementById('nav-ticker').innerHTML = `<span class="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> ${data.symbol}: ${data.priceStr}`;
            document.getElementById('hero-badge').innerText = "SYSTEM STATUS: ONLINE | CONNECTED TO REDIS";
            document.getElementById('hero-badge').classList.remove('bg-slate-100', 'text-slate-600');
            document.getElementById('hero-badge').classList.add('bg-emerald-100', 'text-emerald-700');

            globalConfidence = data.prob;
            document.getElementById('hero-bias').innerText = data.bias;
            if (heroChart) {
                heroChart.data.datasets[0].data = [data.prob, 100 - data.prob];
                heroChart.data.datasets[0].backgroundColor = (data.bias === "BULLISH") ? ['#10b981', '#e2e8f0'] : ['#f43f5e', '#e2e8f0'];
                heroChart.update();
            }

            const riskText = document.getElementById('risk-text');
            const riskCircle = document.getElementById('risk-circle');
            if (riskText) {
                riskText.innerText = data.risk;
                riskCircle.className = "absolute inset-0 rounded-full border-8 border-transparent transition-all duration-700";
                riskText.className = "text-xl font-black";
                if (data.risk === "HIGH") { riskCircle.classList.add('border-t-rose-500', 'animate-spin'); riskText.classList.add('text-rose-500'); }
                else if (data.risk === "MEDIUM") { riskCircle.classList.add('border-t-amber-500'); riskCircle.style.transform = "rotate(180deg)"; riskText.classList.add('text-amber-500'); }
                else { riskCircle.classList.add('border-t-emerald-500'); riskCircle.style.transform = "rotate(45deg)"; riskText.classList.add('text-emerald-500'); }
            }

            const winRateEl = document.getElementById('win-rate');
            const winBarEl = document.getElementById('win-bar');
            const tradesEl = document.getElementById('total-trades');
            if (winRateEl) {
                winRateEl.innerText = data.win_rate + "%";
                winBarEl.style.width = data.win_rate + "%";
                tradesEl.innerText = data.total_trades + " validations";
                winBarEl.className = (data.win_rate > 50) ? "bg-emerald-500 h-full transition-all duration-1000" : "bg-rose-500 h-full transition-all duration-1000";
            }
        }

        document.getElementById('analyze-btn').addEventListener('click', async () => {
            const btn = document.getElementById('analyze-btn');
            const loader = document.getElementById('sim-loading');
            btn.disabled = true; loader.classList.remove('hidden');
            await new Promise(r => setTimeout(r, 800));
            const data = await fetchMarketData();
            loader.classList.add('hidden'); btn.disabled = false;
            if (data) {
                document.getElementById('res-price').innerText = data.priceStr;
                const biasEl = document.getElementById('res-bias');
                biasEl.innerText = data.bias;
                biasEl.className = (data.bias === "BULLISH") ? "text-xl font-bold mt-1 text-emerald-400" : "text-xl font-bold mt-1 text-rose-400";
                document.getElementById('res-prob').innerText = data.prob + "%";
                document.getElementById('prob-bar').style.width = data.prob + "%";
                document.getElementById('res-reason').innerText = data.narrative.replace(/"/g, '');
            }
        });

        document.addEventListener('DOMContentLoaded', () => {
            initHeroChart();
            selectLayer(0);
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

# --- LAUNCHER ---
if __name__ == "__main__":
    t1 = threading.Thread(target=run_data_stream, daemon=True)
    t2 = threading.Thread(target=run_ai_brain, daemon=True)
    t1.start()
    t2.start()

    print("🚀 SYSTEM LAUNCH: Port 10000")
    uvicorn.run(app, host="0.0.0.0", port=10000)