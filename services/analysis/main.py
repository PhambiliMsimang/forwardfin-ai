import asyncio
import json
import redis
import os
import talib
import numpy as np

# Connect to Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0)
pubsub = r.pubsub()

# We keep a slightly longer history now for accurate MACD
price_history = []

async def analyze_market():
    print(f"🧠 Analysis Service (Advanced) Connected to Redis at {REDIS_HOST}")
    pubsub.subscribe('market_data')
    print("Waiting for data stream...")

    for message in pubsub.listen():
        if message['type'] == 'message':
            # 1. Parse Data
            raw_data = json.loads(message['data'])
            price = float(raw_data['price'])
            symbol = raw_data['symbol']
            
            # 2. Update History
            price_history.append(price)
            # MACD needs 26 periods + signal (approx 35 data points minimum to start)
            if len(price_history) > 50: 
                price_history.pop(0)

            # 3. Calculate Indicators (Defaults)
            indicators = {
                "rsi": 0, "sma": 0, "macd": 0, "macd_signal": 0, 
                "upper_band": 0, "lower_band": 0, "roc": 0
            }
            signal = "WAIT (Gathering Data...)"
            
            # Convert to numpy for TA-Lib
            np_prices = np.array(price_history, dtype='float')

            # --- THE MATH LAB ---
            if len(price_history) >= 35:
                # A. RSI (14) - Momentum
                indicators['rsi'] = talib.RSI(np_prices, timeperiod=14)[-1]
                
                # B. SMA (20) - Trend
                indicators['sma'] = talib.SMA(np_prices, timeperiod=20)[-1]

                # C. MACD (12, 26, 9) - Trend Reversal
                macd, macd_signal, _ = talib.MACD(np_prices, fastperiod=12, slowperiod=26, signalperiod=9)
                indicators['macd'] = macd[-1]
                indicators['macd_signal'] = macd_signal[-1]

                # D. Bollinger Bands (20, 2 std dev) - Volatility
                upper, middle, lower = talib.BBANDS(np_prices, timeperiod=20, nbdevup=2, nbdevdn=2)
                indicators['upper_band'] = upper[-1]
                indicators['lower_band'] = lower[-1]
                
                # E. ROC (Rate of Change) - Velocity
                indicators['roc'] = talib.ROC(np_prices, timeperiod=10)[-1]

                # --- THE COACH'S LOGIC ---
                # Default
                signal = "NEUTRAL"

                # Logic 1: RSI Extremes (Reversion)
                if indicators['rsi'] > 75:
                    signal = "SELL (Overbought + Hype)"
                elif indicators['rsi'] < 25:
                    signal = "BUY (Oversold + Fear)"
                
                # Logic 2: Bollinger Band Squeeze (Breakout)
                # If price breaks the upper band, it's a breakout
                elif price > indicators['upper_band']:
                    signal = "BUY (Volatility Breakout)"
                
                # Logic 3: MACD Crossover (Trend Shift)
                # If MACD line crosses ABOVE Signal line
                elif indicators['macd'] > indicators['macd_signal'] and indicators['macd'] < 0:
                     signal = "BUY (Momentum Recovery)"

            # 4. Publish Advanced Insight
            output = {
                "symbol": symbol,
                "price": price,
                "indicators": {k: round(v, 2) for k, v in indicators.items()},
                "signal": signal
            }
            
            # Print a clean dashboard line
            print(f"💵 ${price} | RSI: {output['indicators']['rsi']} | MACD: {output['indicators']['macd']} | Sig: {signal}")
            
            r.publish("analysis_results", json.dumps(output))

if __name__ == "__main__":
    asyncio.run(analyze_market())