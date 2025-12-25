import asyncio
import json
import redis
import os
import numpy as np
import xgboost as xgb
import shap
import warnings
import sys

# Force prints to flush immediately
sys.stdout.reconfigure(line_buffering=True)
warnings.filterwarnings("ignore")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
print(f"🔍 DEBUG: Attempting to connect to Redis at {REDIS_HOST}...")

try:
    r = redis.Redis(host=REDIS_HOST, port=6379, db=0)
    pubsub = r.pubsub()
    pubsub.subscribe('analysis_results')
    print("✅ DEBUG: Connected to Redis! Subscribed to 'analysis_results'.")
except Exception as e:
    print(f"❌ DEBUG: Redis Connection Failed: {e}")

# --- DUMMY MODEL SETUP ---
print("🤖 DEBUG: Building XGBoost Model...")
X_train = np.array([[20, -5, -2], [80, 5, 2], [50, 0, 0]])
y_train = np.array([1, 0, 0]) 
model = xgb.XGBClassifier(n_estimators=10, max_depth=2, eval_metric='logloss')
model.fit(X_train, y_train)
explainer = shap.TreeExplainer(model)
print("🤖 DEBUG: Model Ready. Entering Loop...")

def run_inference():
    print("👂 DEBUG: Listening for messages...")
    
    for message in pubsub.listen():
        if message['type'] != 'message':
            continue
            
        print("📨 DEBUG: Received a message!") 
        
        try:
            # 1. Parse Data
            data = json.loads(message['data'])
            
            if data['signal'] == "WAIT (Gathering Data...)":
                continue

            # 2. Extract Features
            ind = data['indicators']
            rsi = float(ind.get('rsi', 50))
            macd = float(ind.get('macd', 0))
            roc = float(ind.get('roc', 0))

            features = np.array([[rsi, macd, roc]])

            # 3. Predict
            probs = model.predict_proba(features)[0]
            # --- THE FIX IS HERE: Convert numpy float to standard python float ---
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
            print(f"❌ CRASH INSIDE LOOP: {e}")

if __name__ == "__main__":
    run_inference()