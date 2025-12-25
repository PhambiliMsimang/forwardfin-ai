import json
import redis
import os
import numpy as np
import xgboost as xgb
import sys
import warnings

sys.stdout.reconfigure(line_buffering=True)
warnings.filterwarnings("ignore")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

# Dummy Model
X_train = np.array([[20, -5, -2], [80, 5, 2], [50, 0, 0]])
y_train = np.array([1, 0, 0]) 
model = xgb.XGBClassifier(n_estimators=10, max_depth=2, eval_metric='logloss')
model.fit(X_train, y_train)
print("🤖 DEBUG: Model Ready.")

def clean_value(val):
    try:
        if isinstance(val, list): return float(val[0])
        return float(val)
    except: return 0.0

def run_inference():
    pubsub = r.pubsub()
    pubsub.subscribe('analysis_results')
    print("👂 DEBUG: Listening for analysis...")
    
    for message in pubsub.listen():
        if message['type'] != 'message': continue
            
        try:
            data = json.loads(message['data'])
            ind = data['indicators']
            rsi = clean_value(ind.get('rsi', 50))
            macd = clean_value(ind.get('macd', 0))
            roc = 0.0

            features = np.array([[rsi, macd, roc]])
            probs = model.predict_proba(features)[0]
            bullish_prob = float(round(probs[1] * 100, 1))

            bias = "BULLISH" if bullish_prob > 50 else "BEARISH"
            print(f"🔮 PREDICTION SUCCESS: {bias} ({bullish_prob}%)")
            
            result = {
                "symbol": data['symbol'],
                "bias": bias,
                "probability": bullish_prob 
            }
            
            # --- THE FIX: SAVE TO REDIS CACHE ---
            r.set("latest_prediction", json.dumps(result)) # <--- Website reads this!
            r.publish("inference_results", json.dumps(result))

        except Exception as e:
            print(f"⚠️ Inference Error: {e}")

if __name__ == "__main__":
    run_inference()