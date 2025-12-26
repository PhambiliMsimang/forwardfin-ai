import redis
import json
import time
import os
import pandas as pd
import numpy as np

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

print("🧮 Analysis Engine: Ready to crunch numbers...", flush=True)

price_history = []

def calculate_volatility(prices, window=20):
    if len(prices) < window: return 0.0
    
    # Create Series
    series = pd.Series(prices)
    
    # Calculate percentage returns
    returns = series.pct_change()
    
    # Calculate Standard Deviation (Volatility) over the window
    vol = returns.rolling(window=window).std().iloc[-1]
    
    # Scale up for readability (e.g., 0.001 -> 0.1)
    return vol * 100 if not pd.isna(vol) else 0.0

def calculate_rsi(prices, period=14):
    if len(prices) < period: return 50
    series = pd.Series(prices)
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50

def calculate_macd(prices):
    if len(prices) < 26: return 0
    series = pd.Series(prices)
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    return macd.iloc[-1]

def process_stream():
    pubsub = r.pubsub()
    pubsub.subscribe('market_data')
    
    for message in pubsub.listen():
        if message['type'] != 'message': continue

        try:
            data = json.loads(message['data'])
            price = float(data['price'])
            
            price_history.append(price)
            # Keep slightly more history for volatility calc
            if len(price_history) > 60: price_history.pop(0)

            # --- CALCULATE INDICATORS ---
            rsi = calculate_rsi(price_history)
            macd = calculate_macd(price_history)
            volatility = calculate_volatility(price_history)
            
            # --- DETERMINE SIGNAL & RISK ---
            signal = "NEUTRAL"
            if rsi > 70: signal = "SELL"
            elif rsi < 30: signal = "BUY"

            risk_level = "LOW"
            if volatility > 0.05: risk_level = "MEDIUM"
            if volatility > 0.15: risk_level = "HIGH"

            print(f"📊 {data['symbol']} | Vol: {volatility:.4f}% ({risk_level}) | RSI: {rsi:.1f}")

            # --- PACK & SHIP ---
            packet = {
                "symbol": data['symbol'],
                "price": price,
                "indicators": {
                    "rsi": rsi, 
                    "macd": macd, 
                    "signal": signal,
                    "volatility": volatility,
                    "risk_level": risk_level
                }
            }
            
            r.set("latest_price", json.dumps(packet))
            r.publish('analysis_results', json.dumps(packet))

        except Exception as e:
            print(f"❌ Analysis Error: {e}")

if __name__ == "__main__":
    process_stream()