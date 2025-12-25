import asyncio
import json
import redis
import os
import yfinance as yf
import datetime

# Connect to Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0)

print(f"🔌 Ingestion Service: Connecting to Real Market Data (Yahoo Finance)...")

async def fetch_market_data():
    symbol = "BTC-USD"
    print(f"🚀 Tracking: {symbol}")

    while True:
        try:
            # 1. Get Real Data
            # We fetch the last 1 minute of data
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="1m")

            if not data.empty:
                # Get the very latest price
                latest = data.iloc[-1]
                price = float(latest['Close'])
                volume = int(latest['Volume'])
                
                # Yahoo updates every ~60 seconds, but we want our loop to feel alive.
                # In a pro app, we would use websockets. For this MVP, this works great.
                
                # 2. Create the Packet
                market_data = {
                    "symbol": symbol,
                    "price": round(price, 2),
                    "volume": volume,
                    "timestamp": datetime.datetime.now().isoformat()
                }

                # 3. Send to Factory
                r.publish('market_data', json.dumps(market_data))
                print(f"📡 Live: {symbol} @ ${market_data['price']}")

            else:
                print("⚠️ Yahoo returned no data (Market might be quiet)")

        except Exception as e:
            print(f"❌ Error fetching data: {e}")

        # Wait 10 seconds before next check (Yahoo limits are generous but let's be polite)
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(fetch_market_data())