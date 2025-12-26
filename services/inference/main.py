import json
import redis
import os
import numpy as np
import pandas as pd
import xgboost as xgb
import yfinance as yf
import sys
import warnings
import time
import urllib.request

# Clean up logs
sys.stdout.reconfigure(line_buffering=True)
warnings.filterwarnings("ignore")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# 🚨 DISCORD WEBHOOK (Your Alerts)
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1454098742218330307/gi8wvEn0pMcNsAWIR_kY5-_0_VE4CvsgWjkSXjCasXX-xUrydbhYtxHRLLLgiKxs_pLL"

CONFIDENCE_THRESHOLD = 70.0
ALERT_COOLDOWN = 3600
last_alert_time = 0

print("🧠 AI BRAIN: Waking up...", flush=True)

# --- 1. TRAINING (Technical Only) ---
def train_model():
    print("🎓 TRAINER: Downloading last 30 days of Bitcoin history...")
    try:
        btc = yf.Ticker("BTC-USD")
        df = btc.history(period="1mo", interval="1h")
        if len(df) < 50: return None

        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['ROC'] = df['Close'].pct_change(periods=14) * 100
        df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
        df.dropna(inplace=True)

        features = ['RSI', 'MACD', 'ROC']
        model = xgb.XGBClassifier(n_estimators=100, max_depth=3, eval_metric='logloss')
        model.fit(df[features], df['Target'])
        return model
    except: return None

model = train_model()
if model is None:
    X_train = pd.DataFrame([[20, -5, -2], [80, 5, 2]], columns=['RSI', 'MACD', 'ROC'])
    y_train = np.array([1, 0])
    model = xgb.XGBClassifier(eval_metric='logloss')
    model.fit(X_train, y_train)

# --- 2. THE JUDGE (Scoreboard Tracker) ---
# 🚨 THIS IS THE MISSING PART THAT FIXES YOUR WIN RATE 🚨
def update_scoreboard(current_price):
    last_trade = r.get("memory_last_trade")
    stats = r.get("scoreboard_stats")
    
    if not stats: stats = {"wins": 0, "total": 0, "win_rate": 0}
    else: stats = json.loads(stats)

    if last_trade:
        memory = json.loads(last_trade)
        entry_price = memory['price']
        bias = memory['bias']
        
        # Only judge significant moves ($50 diff to avoid noise)
        if abs(current_price - entry_price) > 50:
            outcome = "HOLD"
            if bias == "BULLISH" and current_price > entry_price: outcome = "WIN"
            elif bias == "BEARISH" and current_price < entry_price: outcome = "WIN"
            elif bias == "BULLISH" and current_price < entry_price: outcome = "LOSS"
            elif bias == "BEARISH" and current_price > entry_price: outcome = "LOSS"
            
            if outcome != "HOLD":
                stats['total'] += 1
                if outcome == "WIN": stats['wins'] += 1
                if stats['total'] > 0: stats['win_rate'] = int((stats['wins'] / stats['total']) * 100)
                r.set("scoreboard_stats", json.dumps(stats))

    return stats

# --- 3. GENERATE REASONING ---
def generate_narrative(bias, prob, rsi, sentiment, headline):
    """Creates a human-readable explanation combining Tech + News."""
    reason = f"Technical indicators suggest a {bias} trend ({prob}% confidence)."
    
    # Add Technical Context
    if rsi > 70: reason += " However, the asset is currently Overbought (RSI > 70)."
    elif rsi < 30: reason += " The asset is currently Oversold (RSI < 30), suggesting a potential bounce."
    
    # Add Fundamental Context (The News)
    if headline != "No major news detected.":
        if sentiment > 0.05:
            reason += f" Fundamentally, sentiment is POSITIVE due to news: '{headline}'."
        elif sentiment < -0.05:
            reason += f" Fundamentally, sentiment is NEGATIVE due to news: '{headline}'."
        else:
            reason += f" News sentiment is neutral ('{headline}')."
            
    return reason

# --- 4. WATCHDOG (Discord) ---
def send_discord_alert(symbol, bias, prob, price, risk, headline):
    global last_alert_time
    if time.time() - last_alert_time < ALERT_COOLDOWN: return

    color = 5763719 if bias == "BULLISH" else 15548997
    payload = {
        "username": "ForwardFin AI",
        "embeds": [{
            "title": f"🚨 TRADE ALERT: {symbol}",
            "description": f"AI Confidence > {CONFIDENCE_THRESHOLD}%",
            "color": color,
            "fields": [
                {"name": "Signal", "value": f"**{bias}**", "inline": True},
                {"name": "Confidence", "value": f"{prob}%", "inline": True},
                {"name": "Price", "value": f"${price:,.2f}", "inline": True},
                {"name": "News Context", "value": headline, "inline": False}
            ],
            "footer": {"text": "ForwardFin Real-Time Terminal"}
        }]
    }
    try:
        req = urllib.request.Request(DISCORD_WEBHOOK_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req)
        last_alert_time = time.time()
    except Exception as e: print(f"Discord Error: {e}")

# --- 5. LIVE PREDICTION LOOP ---
def run_inference():
    pubsub = r.pubsub()
    pubsub.subscribe('analysis_results')
    print("👂 AI LISTENER: Waiting for live market data...")
    
    for message in pubsub.listen():
        if message['type'] != 'message': continue
            
        try:
            data = json.loads(message['data'])
            ind = data['indicators']
            price = float(data.get('price', 0))
            
            # Extract Data
            rsi = float(ind.get('rsi', 50))
            macd = float(ind.get('macd', 0))
            roc = (macd / price) * 100 if price != 0 else 0
            sentiment = float(ind.get('sentiment', 0.0))
            headline = ind.get('headline', "")
            risk = ind.get('risk_level', 'LOW')

            # A. Update Scoreboard (The Judge)
            stats = update_scoreboard(price)

            # B. Base Technical Prediction
            features = pd.DataFrame([[rsi, macd, roc]], columns=['RSI', 'MACD', 'ROC'])
            probs = model.predict_proba(features)[0]
            bullish_prob = float(probs[1] * 100)

            # C. Apply "Fundamental Bias" (News Adjustment)
            adjustment = sentiment * 10 
            final_prob = bullish_prob + adjustment
            final_prob = max(0.0, min(100.0, final_prob))
            final_prob = round(final_prob, 1)
            final_bias = "BULLISH" if final_prob > 50 else "BEARISH"

            # D. Generate Narrative
            narrative = generate_narrative(final_bias, final_prob, rsi, sentiment, headline)

            # E. Publish
            print(f"🔮 PRED: {final_bias} ({final_prob}%) | News: {sentiment:.2f}")
            result = {
                "symbol": data['symbol'],
                "bias": final_bias,
                "probability": final_prob,
                "win_rate": stats.get('win_rate', 0), 
                "total_trades": stats.get('total', 0)
            }
            r.set("latest_prediction", json.dumps(result))
            r.set("latest_narrative", narrative)
            r.publish("inference_results", json.dumps(result))

            # F. Save Memory (For future judging)
            memory_packet = {"price": price, "bias": final_bias}
            r.set("memory_last_trade", json.dumps(memory_packet))

            # G. Discord Alert
            if (final_prob > CONFIDENCE_THRESHOLD or final_prob < (100-CONFIDENCE_THRESHOLD)) and risk != "HIGH":
                send_discord_alert(data['symbol'], final_bias, final_prob, price, risk, headline)

        except Exception as e:
            print(f"⚠️ Inference Error: {e}")

if __name__ == "__main__":
    run_inference()