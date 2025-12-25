import asyncio
import json
import redis
import os
import numpy as np
import xgboost as xgb
import sys
import warnings

# Force prints to flush immediately
sys.stdout.reconfigure(line_buffering=True)
warnings.filterwarnings("ignore")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
print(f"🔍 DEBUG: Connecting to Redis at {REDIS_HOST}...")

try:
    r = redis.Redis(host=REDIS_HOST, port=6379, db=0)
    pubsub = r.pubsub()
    pubsub.subscribe('analysis_results')
    print("✅ DEBUG: Connected to Redis!")
except Exception as e:
    print(f"❌ DEBUG: Redis Connection Failed: {e}")

# --- DUMMY MODEL SETUP ---
print("🤖 DEBUG: Building XGBoost Model...")
X_train = np.array([[20, -5, -2], [80, 5, 2], [50, 0, 0]])
y_train = np.array([1, 0, 0]) 
model = xgb.XGBClassifier(n_estimators=10, max_depth=2, eval_metric='logloss')
model.fit(X_train, y_train)
print("🤖 DEBUG: Model Ready.")

# --- THE FIX: A Helper to Clean Dirty Data ---
def clean_value(val):
    """
    Removes brackets [] if the number arrives as a string list.
    Example: "[0.33]" -> 0.33
    """
    try:
        if isinstance(val, str):
            val = val.replace('[', '').replace(']', '')
        if isinstance(val, list):
            return float(val[0])
        return float(val)
    except:
        return 0.0

def run_inference():
    print("👂 DEBUG: Listening for messages...")
    
    for message in pubsub.listen():
        if message['type'] != 'message':
            continue
            
        try:
            # 1. Parse Data
            data = json.loads(message['data'])
            
            if data.get('signal') == "WAIT (Gathering Data...)":
                continue

            # 2. Extract Features (Using the Cleaner!)
            ind = data['indicators']
            rsi = clean_value(ind.get('rsi', 50))
            macd = clean_value(ind.get('macd', 0))
            roc = clean_value(ind.get('roc', 0))

            features = np.array([[rsi, macd, roc]])

            # 3. Predict
            probs = model.predict_proba(features)[0]
            bullish_prob = float(round(probs[1] * 100, 1))

            # 4. Result
            bias = "BULLISH" if bullish_prob > 50 else "BEARISH"
            print(f"🔮 PREDICTION SUCCESS: {bias} ({bullish_prob}%)")
            
            # Publish result
            result = {
                "symbol": data['symbol'],
                "bias": bias,
                "probability": bullish_prob 
            }
            r.publish("inference_results", json.dumps(result))

        except Exception as e:
            # Now we print the error but KEEP GOING (Don't crash the loop)
            print(f"⚠️ SKIPPING BAD PACKET: {e}")

if __name__ == "__main__":
    run_inference()