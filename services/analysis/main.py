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
    print("⚠️ VADER MISSING: News features disabled.")
    HAS_NEWS = False

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

print("🧮 ANALYSIS ENGINE: Started", flush=True)

price_history = []
last_news_fetch = 0
cached_sentiment = 0.0
cached_headline = "News module loading..."

def fetch_crypto_news():
    global last_news_fetch, cached_sentiment, cached_headline
    if not HAS_NEWS: return 0.0, "News Disabled (Check Render Logs)"

    if time.time() - last_news_fetch < 900: 
        return cached_sentiment, cached_headline

    try:
        btc = yf.Ticker("BTC-USD")
        news_list = btc.news
        if not news_list: return 0.0, "Market is quiet."

        scores = []
        top_stories = news_list[:3]
        for article in top_stories:
            vs = analyzer.polarity_scores(article.get('title', ''))
            scores.append(vs['compound'])

        cached_sentiment = sum(scores) / len(scores)
        cached_headline = top_stories[0].get('title', 'News unavailable')
        last_news_fetch = time.time()
        return cached_sentiment, cached_headline
    except: return 0.0, "News Error"

def calculate_indicators(prices):
    if len(prices) < 26: return 50, 0, 0, "LOW"
    series = pd.Series(prices)
    rsi = 100 - (100 / (1 + (series.diff().where(lambda x: x>0,0).rolling(14).mean() / -series.diff().where(lambda x: x<0,0).rolling(14).mean())))
    return rsi.iloc[-1], 0, 0, "LOW" # Simplified for safety

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

            rsi, _, _, risk = calculate_indicators(price_history)
            sentiment, headline = fetch_crypto_news()

            packet = {
                "symbol": data['symbol'], "price": price,
                "indicators": {"rsi": rsi, "macd": 0, "volatility": 0, "risk_level": risk, "sentiment": sentiment, "headline": headline}
            }
            r.set("latest_price", json.dumps(packet))
            r.publish('analysis_results', json.dumps(packet))
        except: pass

if __name__ == "__main__":
    process_stream()