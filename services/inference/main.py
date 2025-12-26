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
import urllib.request  # <--- Library for sending Discord messages

# Clean up logs
sys.stdout.reconfigure(line_buffering=True)
warnings.filterwarnings("ignore")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# --- CONFIGURATION ---
# 🚨 PASTE YOUR WEBHOOK URL HERE 🚨
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1454098742218330307/gi8wvEn0pMcNsAWIR_kY5-_0_VE4CvsgWjkSXjCasXX-xUrydbhYtxHRLLLgiKxs_pLL"

# Alert Settings
CONFIDENCE_THRESHOLD = 70.0  # Only alert if AI is >70% sure
ALERT_COOLDOWN = 3600        # Wait 1 hour between alerts (to avoid spam)
last_alert_time = 0

print("🧠 AI BRAIN: Waking up...", flush=True)

# --- 1. THE TEACHER (Training Function) ---
def train_model():
    print("🎓 TRAINER: Downloading last 30 days of Bitcoin history...")
    try:
        btc = yf.Ticker("BTC-USD")
        df = btc.history(period="1mo", interval="1h")
        
        if len(df) < 50:
            return None

        # Features
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['ROC'] = df['Close'].pct_change(periods=14) * 100

        # Target
        df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
        df.dropna(inplace=True)

        features = ['RSI', 'MACD', 'ROC']
        X = df[features]
        y = df['Target']
        
        model = xgb.XGBClassifier(n_estimators=100, max_depth=3, eval_metric='logloss')
        model.fit(X, y)
        
        score = model.score(X, y)
        print(f"✅ REAL MODEL TRAINED! Accuracy: {score*100:.1f}%")
        return model

    except Exception as e:
        print(f"❌ TRAINING FAILED: {e}")
        return None

# --- 2. INITIALIZE ---
model = train_model()

if model is None:
    print("⚠️ Using Fallback Dummy Model")
    X_train = pd.DataFrame([[20, -5, -2], [80, 5, 2]], columns=['RSI', 'MACD', 'ROC'])
    y_train = np.array([1, 0])
    model = xgb.XGBClassifier(eval_metric='logloss')
    model.fit(X_train, y_train)

# --- 3. THE WATCHDOG (Discord Alerts) ---
def send_discord_alert(symbol, bias, prob, price, risk):
    global last_alert_time
    
    # Check Cooldown
    if time.time() - last_alert_time < ALERT_COOLDOWN:
        return

    print(f"🚨 SENDING DISCORD ALERT: {bias} on {symbol}")
    
    # Create the Message
    color = 5763719 # Green
    if bias == "BEARISH": color = 15548997 # Red

    payload = {
        "username": "ForwardFin AI",
        "embeds": [{
            "title": f"🚨 TRADE ALERT: {symbol}",
            "description": f"The AI has detected a high-probability setup.",
            "color": color,
            "fields": [
                {"name": "Signal", "value": f"**{bias}**", "inline": True},
                {"name": "Confidence", "value": f"{prob}%", "inline": True},
                {"name": "Price", "value": f"${price:,.2f}", "inline": True},
                {"name": "Market Risk", "value": f"{risk}", "inline": True}
            ],
            "footer": {"text": "ForwardFin Real-Time Terminal"}
        }]
    }

    try:
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL, 
            data=json.dumps(payload).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req)
        last_alert_time = time.time() # Reset timer
        print("✅ Alert Sent Successfully.")
    except Exception as e:
        print(f"❌ Failed to send alert: {e}")

# --- 4. THE JUDGE (Scoreboard) ---
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

# --- 5. THE PREDICTOR (Live Loop) ---
def clean_value(val):
    try:
        if isinstance(val, list): return float(val[0])
        return float(val)
    except: return 0.0

def run_inference():
    pubsub = r.pubsub()
    pubsub.subscribe('analysis_results')
    print("👂 AI LISTENER: Waiting for live market data...")
    
    for message in pubsub.listen():
        if message['type'] != 'message': continue
            
        try:
            data = json.loads(message['data'])
            ind = data['indicators']
            current_price = clean_value(data.get('price', 0))
            risk_level = ind.get('risk_level', "HIGH") # <--- Get Risk
            
            # 1. Judge Past Performance
            stats = update_scoreboard(current_price)
            
            # 2. Predict Future
            rsi = clean_value(ind.get('rsi', 50))
            macd = clean_value(ind.get('macd', 0))
            roc = (macd / current_price) * 100 if current_price != 0 else 0

            features = pd.DataFrame([[rsi, macd, roc]], columns=['RSI', 'MACD', 'ROC'])
            probs = model.predict_proba(features)[0]
            bullish_prob = float(round(probs[1] * 100, 1))
            bias = "BULLISH" if bullish_prob > 50 else "BEARISH"
            
            # 3. CHECK FOR ALERTS (The New Watchdog Logic) 🐕
            # If AI is Confident (>70%) AND Risk is NOT HIGH
            if (bullish_prob > CONFIDENCE_THRESHOLD or bullish_prob < (100-CONFIDENCE_THRESHOLD)) and risk_level != "HIGH":
                send_discord_alert(data['symbol'], bias, bullish_prob, current_price, risk_level)

            # 4. Save Memory
            memory_packet = {"price": current_price, "bias": bias}
            r.set("memory_last_trade", json.dumps(memory_packet))
            
            # 5. Publish
            print(f"🔮 PREDICTION: {bias} ({bullish_prob}%)")
            result = {
                "symbol": data['symbol'],
                "bias": bias,
                "probability": bullish_prob,
                "win_rate": stats.get('win_rate', 0),
                "total_trades": stats.get('total', 0)
            }
            r.set("latest_prediction", json.dumps(result))
            r.publish("inference_results", json.dumps(result))

        except Exception as e:
            print(f"⚠️ Inference Error: {e}")

if __name__ == "__main__":
    run_inference()