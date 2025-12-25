import redis
import json
import os
import random

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

print("📰 Narrative Desk: Waiting for scoops...")

def generate_narrative(data):
    bias = data.get('bias', 'NEUTRAL')
    prob = data.get('probability', 50)
    symbol = data.get('symbol', 'ASSET')
    
    if bias == "BULLISH":
        reasons = [
            "momentum is building on the hourly chart",
            "buyers are stepping in at key support levels",
            "RSI is recovering from oversold conditions"
        ]
        return f"{symbol} shows BULLISH strength ({prob}% confidence) as {random.choice(reasons)}."
    else:
        reasons = [
            "selling pressure is increasing",
            "momentum is fading near resistance",
            "technical indicators suggest a pullback"
        ]
        return f"{symbol} is looking BEARISH ({prob}% confidence) because {random.choice(reasons)}."

def process_stream():
    pubsub = r.pubsub()
    pubsub.subscribe('inference_results')
    
    for message in pubsub.listen():
        if message['type'] != 'message': continue
        
        try:
            data = json.loads(message['data'])
            story = generate_narrative(data)
            
            print(f"🗣️ Narrated: {story}")
            
            # --- THE FIX: SAVE TO REDIS CACHE ---
            r.set("latest_narrative", story) # <--- Website reads this!
            # We don't necessarily need to publish this further, saving is enough

        except Exception as e:
            print(f"❌ Narrative Error: {e}")

if __name__ == "__main__":
    process_stream()