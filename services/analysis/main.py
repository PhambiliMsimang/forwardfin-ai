import redis
import json
import time
import os
import pandas as pd
import numpy as np

# Connect to Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0)

print("🧮 Analysis Engine: Ready to crunch numbers...")

# We need a small memory to calculate trends (RSI needs 14 previous numbers)
price_history = []

def calculate_rsi(prices, period=14):
    if len(prices) < period:
        return 50  # Default neutral
    
    # Create a pandas Series for easy math
    series = pd.Series(prices)
    delta = series.diff()
    
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # Handle division by zero or NaN
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50

def calculate_macd(prices):
    if len(prices) < 26:
        return 0
        
    series = pd.Series(prices)
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    return macd.iloc[-1]

def process_stream():
    pubsub = r.pubsub()
    pubsub.subscribe('market_data')
    
    for message in pubsub.listen():
        if message['type'] != 'message':
            continue

        try:
            # 1. Parse Data
            data = json.loads(message['data'])
            price = float(data['price'])
            
            # 2. Add to History (Keep last 50 prices)
            price_history.append(price)
            if len(price_history) > 50:
                price_history.pop(0)

            # 3. Calculate Indicators (Using Pandas)
            rsi = calculate_rsi(price_history)
            macd = calculate_macd(price_history)
            
            # Determine Signal
            signal = "NEUTRAL"
            if rsi > 70: signal = "SELL"
            elif rsi < 30: signal = "BUY"

            print(f"📊 {data['symbol']} | RSI: {rsi:.2f} | MACD: {macd:.2f} | Sig: {signal}")

            # 4. Publish Results
            analysis_packet = {
                "symbol": data['symbol'],
                "price": price,
                "indicators": {
                    "rsi": rsi,
                    "macd": macd,
                    "signal": signal
                }
            }
            r.publish('analysis_results', json.dumps(analysis_packet))

        except Exception as e:
            print(f"❌ Analysis Error: {e}")

if __name__ == "__main__":
    process_stream()