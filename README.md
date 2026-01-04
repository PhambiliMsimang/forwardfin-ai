🦁 ForwardFin V3.0 | Asia Session Protocol
ForwardFin V3.0 is an automated market analysis engine designed to trade institutional liquidity sweeps. It abandons lagging indicators (RSI, MACD) in favor of time-based price action protocols and Fibonacci Standard Deviation projections.

⚡ Core Philosophy
The bot operates on the "Asia Manipulation" thesis:

Accumulation: The market builds liquidity between 03:00 and 08:59 (Exchange Time).

Manipulation: Institutions "sweep" the High or Low of this range after the session close.

Distribution: Price reverses to target the opposing side of the range or specific STDV levels.

🛠️ Technical Architecture
ForwardFin runs on a multi-threaded Python architecture:

Worker 1 (Data Stream): Fetches real-time 1-minute OHLC data via yfinance (NQ=F / ES=F).

Worker 2 (Strategy Engine): Performs time-slicing using Pandas, detects liquidity sweeps, and calculates Fibonacci STDV targets.

API Layer (FastAPI): serves the React/Tailwind frontend for live monitoring.

Alerting Layer: Pushes "Glass Box" reasoning and trade setups to Discord via Webhooks.

📋 Prerequisites
Python 3.9+

Internet connection (for Data Streaming & Discord Alerts)

🚀 Installation
Clone or Download the Repository

Bash

git clone https://github.com/yourusername/ForwardFin.git
cd ForwardFin
Install Dependencies

Bash

pip install fastapi uvicorn requests pandas numpy yfinance vaderSentiment
Configure Discord

Open main.py.

Replace the DISCORD_WEBHOOK_URL variable with your own channel's webhook URL.

💻 Usage
Start the Engine:

Bash

python main.py
Access the Dashboard:

Open your browser and navigate to: http://localhost:10000

Live Dashboard: View real-time price, current bias, and win rates.

Settings: Toggle between NQ (Nasdaq) and ES (S&P 500).

🧠 Strategy Logic (V3.0)
1. The Accumulation Phase (03:00 - 08:59)
The bot isolates this specific time window. It calculates the Session High and Session Low. During this time, the status is Waiting.

2. The Trigger (Post-09:00)
Once the session closes, the bot waits for price to trade outside the established range.

Bullish Signal: Price sweeps below the Asia Low.

Bearish Signal: Price sweeps above the Asia High.

3. The Execution (STDV)
Upon a confirmed sweep, the bot generates a setup:

Entry: Current Price (at the moment of the sweep).

Take Profit: The opposing side of the Asia Range.

Stop Loss: The -2.0 Standard Deviation level (Expansion Point).

🔔 Discord Alert Example
When a high-confidence setup (Probability > 85%) is detected, you receive:

🔫 SIGNAL: NQ1! LONG

AI Reasoning: ✅ BULLISH ASIA SWEEP • Session High: 15,420.50 | Low: 15,380.00 • Range Size: 40.50 pts • Logic: Price swept Asia Low. Reversal Expected.

Entry: $15,378.00 🎯 TP: $15,420.50 🛑 SL: $15,339.50 (-2.0 STDV) Confidence: 90%

⚖️ Disclaimer
This software is for educational and research purposes only. ForwardFin does not guarantee profits. Futures trading involves substantial risk of loss.