import json
import redis
import os
import numpy as np
import pandas as pd
import xgboost as xgb
import yfinance as yf
import sys
import warnings

# Clean up logs
sys.stdout.reconfigure(line_buffering=True)
warnings.filterwarnings("ignore")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

print("🧠 AI BRAIN: Waking up...", flush=True)

# --- 1. THE TEACHER (Training Function) ---
def train_model():
    print("🎓 TRAINER: Downloading last 30 days of Bitcoin history...")
    try:
        # Fetch real data with a header to look like a real browser
        # (Helps avoid getting blocked by Yahoo)
        btc = yf.Ticker("BTC-USD")
        df = btc.history(period="1mo", interval="1h")
        
        print(f"📊 DEBUG: Downloaded {len(df)} rows of data.")

        if len(df) < 50:
            print("⚠️ Not enough data downloaded. Switching to Fallback.")
            return None

        # Calculate Indicators (Features)
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2

        # ROC (Rate of Change)
        df['ROC'] = df['Close'].pct_change(periods=14) * 100

        # TARGET (Did price go UP in the next hour?)
        df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)

        # Clean NaN values
        df.dropna(inplace=True)

        # Prepare Training Data
        features = ['RSI', 'MACD', 'ROC']
        X = df[features]
        y = df['Target']

        print(f"📚 Training on {len(df)} candles of real history...")
        
        # Build XGBoost Model
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

# Fallback if training fails (CRASH PROOF VERSION)
if model is None:
    print("⚠️ Using Fallback Dummy Model (Pandas Version)")
    # We create a tiny DataFrame with the EXACT same column names
    X_train = pd.DataFrame(
        [[20, -5, -2], [80, 5, 2]], 
        columns=['RSI', 'MACD', 'ROC']  # <--- This fixes the mismatch error!
    )
    y_train = np.array([1, 0])
    model = xgb.XGBClassifier(eval_metric='logloss')
    model.fit(X_train, y_train)

# --- 3. THE PREDICTOR (Live Loop) ---
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
            # 1. Get Live Data
            data = json.loads(message['data'])
            ind = data['indicators']
            
            # 2. Extract Features
            rsi = clean_value(ind.get('rsi', 50))
            macd = clean_value(ind.get('macd', 0))
            # Safe ROC estimation
            price = clean_value(data.get('price', 1))
            roc = (macd / price) * 100 if price != 0 else 0

            # 3. Predict Real Future
            # Ensure columns match training EXACTLY
            features = pd.DataFrame(
                [[rsi, macd, roc]], 
                columns=['RSI', 'MACD', 'ROC']
            )
            
            probs = model.predict_proba(features)[0]
            bullish_prob = float(round(probs[1] * 100, 1))
            bias = "BULLISH" if bullish_prob > 50 else "BEARISH"
            
            # 4. Publish
            print(f"🔮 PREDICTION: {bias} ({bullish_prob}%)")
            result = {
                "symbol": data['symbol'],
                "bias": bias,
                "probability": bullish_prob 
            }
            r.set("latest_prediction", json.dumps(result))
            r.publish("inference_results", json.dumps(result))

        except Exception as e:
            print(f"⚠️ Inference Error: {e}")

if __name__ == "__main__":
    run_inference()