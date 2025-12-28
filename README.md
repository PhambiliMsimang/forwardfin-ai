# 🚀 ForwardFin | AI-Powered Trading Terminal

**ForwardFin** is an institutional-grade trading terminal that bridges the gap between automated AI analysis and human education. It combines real-time sentiment analysis, technical indicators, and a gamified learning academy into a single, high-performance web application.

## 🌟 Key Features

* **🧠 Real-Time AI Brain:** Analyzing Bitcoin prices 24/7 using a custom Python engine.
* **📰 Sentiment Analysis:** Scrapes and scores global news using VADER to detect market FUD or Hype.
* **📉 Dynamic Risk Management:** Automatically calculates volatility-adjusted Stop Losses and Take Profits.
* **🎓 Interactive Academy:** A built-in "Zero-to-Hero" educational module teaching institutional concepts like *Asia Sweeps* and *Divergences*.
* **🤖 Self-Grading Engine:** The bot "paper trades" its own signals and tracks its win rate live on the dashboard.
* **🔔 Discord Integration:** Broadcasts high-confidence trade setups (>70%) to a Discord community.

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI, Uvicorn, Threading
* **Data Science:** Pandas, NumPy, VaderSentiment
* **Frontend:** HTML5, Tailwind CSS, Chart.js, TradingView Widgets
* **Infrastructure:** Render (Cloud Hosting), Discord Webhooks

## 🏗️ System Architecture

The application runs on a 3-Worker Thread system to ensure non-blocking performance:
1.  **Worker 1 (Data Stream):** Connects to Coinbase API for millisecond-latency price updates.
2.  **Worker 2 (The Brain):** Runs the infinite analysis loop (News + RSI + Volatility Logic).
3.  **Worker 3 (The Interface):** Serves the FastAPI frontend to users.

---
*Built by Phambili Msimang*