import json
import redis
import os
import numpy as np
import pandas as pd
import yfinance as yf
import sys
import time
import urllib.request

# --- SAFE IMPORT BLOCK ---
try:
    import xgboost as xgb
    HAS_ML = True
except ImportError:
    print("⚠️ WARNING: 'xgboost' not found. Using simple logic mode.")
    HAS_ML = False

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# 🚨 DISCORD WEBHOOK
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1454098742218330307/gi8wvEn0pMcNsAWIR_kY5-_0_VE4CvsgWjkSXjCasXX-xUrydbhYtxHRLLLgiKxs_pLL"
CONFIDENCE_THRESHOLD = 70.0
ALERT_COOLDOWN = 3600
last_alert_time = 0

print("🧠 AI BRAIN: Started (Safe Mode)", flush=True)

def train_model():
    if not HAS_ML: return None
    print("🎓 TRAINER: Downloading Bitcoin history...")
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

# --- THE JUDGE ---
def update_scoreboard(current_price):
    stats = r.get("scoreboard_stats")
    if not stats: stats = {"wins": 0, "total": 0, "win_rate": 0}
    else: stats = json.loads(stats)
    
    last_trade = r.get("memory_last_trade")
    if last_trade:
        memory = json.loads(last_trade)
        entry = memory['price']
        bias = memory['bias']
        if abs(current_price - entry) > 50:
            outcome = "HOLD"
            if bias == "BULLISH" and current_price > entry: outcome = "WIN"
            elif bias == "BEARISH" and current_price < entry: outcome = "WIN"
            elif bias == "BULLISH" and current_price < entry: outcome = "LOSS"
            elif bias == "BEARISH" and current_price > entry: outcome = "LOSS"
            
            if outcome != "HOLD":
                stats['total'] += 1
                if outcome == "WIN": stats['wins'] += 1
                if stats['total'] > 0: stats['win_rate'] = int((stats['wins'] / stats['total']) * 100)
                r.set("scoreboard_stats", json.dumps(stats))
    return stats

def run_inference():
    pubsub = r.pubsub()
    pubsub.subscribe('analysis_results')
    print("👂 AI LISTENER: Ready...")
    
    for message in pubsub.listen():
        if message['type'] != 'message': continue
        try:
            data = json.loads(message['data'])
            ind = data['indicators']
            price = float(data.get('price', 0))
            rsi = float(ind.get('rsi', 50))
            macd = float(ind.get('macd', 0))
            roc = (macd / price) * 100 if price != 0 else 0
            sentiment = float(ind.get('sentiment', 0.0))
            headline = ind.get('headline', "")
            risk = ind.get('risk_level', 'LOW')

            stats = update_scoreboard(price)

            # Prediction Logic
            if HAS_ML and model:
                features = pd.DataFrame([[rsi, macd, roc]], columns=['RSI', 'MACD', 'ROC'])
                probs = model.predict_proba(features)[0]
                bullish_prob = float(probs[1] * 100)
            else:
                # Fallback Logic
                bullish_prob = 50.0
                if rsi < 30: bullish_prob = 70.0
                if rsi > 70: bullish_prob = 30.0

            adjustment = sentiment * 10 
            final_prob = max(0.0, min(100.0, round(bullish_prob + adjustment, 1)))
            final_bias = "BULLISH" if final_prob > 50 else "BEARISH"

            # --- NARRATIVE GENERATOR ---
            narrative = f"Technical Analysis ({final_bias}): {final_prob}% confidence."
            
            if headline and headline != "News module loading..." and headline != "News Disabled (Install vaderSentiment)":
                 narrative += f" News context: {headline}"
            else:
                 narrative += " (No breaking news detected)"

            # Print to log to prove it's the new code
            print(f"🔮 PRED: {final_bias} ({final_prob}%) | NEWS: {headline}")
            
            result = { 
                "symbol": data['symbol'], "bias": final_bias, "probability": final_prob, 
                "win_rate": stats.get('win_rate', 0), "total_trades": stats.get('total', 0) 
            }
            
            r.set("latest_prediction", json.dumps(result))
            r.set("latest_narrative", narrative)
            r.publish("inference_results", json.dumps(result))
            
            memory_packet = {"price": price, "bias": final_bias}
            r.set("memory_last_trade", json.dumps(memory_packet))

            # Discord Alert
            if (final_prob > CONFIDENCE_THRESHOLD or final_prob < (100-CONFIDENCE_THRESHOLD)) and risk != "HIGH":
                 # Simple Alert Logic
                 pass 

        except Exception as e:
            print(f"⚠️ Inference Error: {e}")

if __name__ == "__main__":
    run_inference()