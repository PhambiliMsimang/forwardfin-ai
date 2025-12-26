import redis
import json
import time
import os
import pandas as pd
import numpy as np
import yfinance as yf
import sys

# --- SAFE IMPORT BLOCK ---
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    HAS_NEWS = True
    analyzer = SentimentIntensityAnalyzer()
except ImportError:
    print("⚠️ WARNING: 'vaderSentiment' not found. News features disabled.")
    HAS_NEWS = False

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

print("🧮 ANALYSIS ENGINE: Started (Safe Mode)", flush=True)

price_history = []
last_news_fetch = 0
cached_sentiment = 0.0
cached_headline = "News module loading..."

def fetch_crypto_news():
    global last_news_fetch, cached_sentiment, cached_headline
    
    if not HAS_NEWS:
        return 0.0, "News Disabled (Install vaderSentiment)"

    if time.time() - last_news_fetch < 900: 
        return cached_sentiment, cached_headline

    try:
        print("📰 FETCHING: Checking for breaking news...")
        btc = yf.Ticker("BTC-USD")
        news_list = btc.news
        if not news_list: return 0.0, "Market is quiet."

        scores = []
        top_stories = news_list[:3]
        for article in top_stories:
            title = article.get('title', '')
            vs = analyzer.polarity_scores(title)
            scores.append(vs['compound'])
        
        avg_score = sum(scores) / len(scores) if scores else 0.0
        top_headline = top_stories[0].get('title', 'News unavailable')
        
        cached_sentiment = avg_score
        cached_headline = top_headline
        last_news_fetch = time.time()
        print(f"📰 NEWS PROCESSED: {top_headline} (Score: {avg_score:.2f})")
        return avg_score, top_headline
    except Exception as e:
        print(f"⚠️ News Error: {e}")
        return 0.0, "News feed unavailable."

def calculate_indicators(prices):
    if len(prices) < 26: return 50, 0, 0, "LOW"
    series = pd.Series(prices)
    
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_val = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    macd_val = macd.iloc[-1]
    
    returns = series.pct_change()
    vol = returns.rolling(window=20).std().iloc[-1] * 100
    vol = vol if not pd.isna(vol) else 0.0
    
    risk = "LOW"
    if vol > 0.05: risk = "MEDIUM"
    if vol > 0.15: risk = "HIGH"
    
    return rsi_val, macd_val, vol, risk

def process_stream():
    pubsub = r.pubsub()
    pubsub.subscribe('market_data')
    for message in pubsub.listen():
        if message['type'] != 'message': continue
        try:
            data = json.loads(message['data'])
            price = float(data['price'])
            price_history.append(price)
            if len(price_history) > 60: price_history.pop(0)

            rsi, macd, vol, risk = calculate_indicators(price_history)
            sentiment, headline = fetch_crypto_news()

            packet = {
                "symbol": data['symbol'],
                "price": price,
                "indicators": {
                    "rsi": rsi, 
                    "macd": macd, 
                    "volatility": vol,
                    "risk_level": risk,
                    "sentiment": sentiment,
                    "headline": headline
                }
            }
            # Print log to prove it's running
            if len(price_history) % 10 == 0:
                print(f"🧮 CALC: RSI={rsi:.1f} Risk={risk}")
                
            r.set("latest_price", json.dumps(packet))
            r.publish('analysis_results', json.dumps(packet))
        except Exception as e:
            print(f"❌ Analysis Error: {e}")

if __name__ == "__main__":
    process_stream()