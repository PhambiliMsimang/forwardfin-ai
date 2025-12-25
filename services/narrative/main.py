import asyncio
import json
import redis
import os
import random

# Connect to Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0)
pubsub = r.pubsub()

print(f"🗣️ Narrative Service: Connected to Redis at {REDIS_HOST}")

async def narrate_market():
    # Listen to the AI's predictions
    pubsub.subscribe('inference_results')
    print("🗣️ Narrative Service: Listening for AI predictions...")

    for message in pubsub.listen():
        if message['type'] == 'message':
            # 1. Parse the AI's math
            data = json.loads(message['data'])
            symbol = data['symbol']
            bias = data['bias']
            prob = data['probability']
            
            # 2. The "Writer's Room" (Rule-Based Logic)
            # This simulates what an LLM would do, but using rules for speed/cost.
            
            headline = ""
            explanation = ""
            
            # A. Generate Headline
            if prob > 70:
                headline = f"Strong {bias} Signal Detected for {symbol}"
            elif prob > 55:
                headline = f"Moderate {bias} Lean for {symbol}"
            else:
                headline = f"Uncertain Outlook for {symbol} (Hold)"

            # B. Generate Explanation based on bias
            if bias == "BULLISH":
                reasons = [
                    "momentum indicators suggest a recovery is underway.",
                    "buying pressure is slowly returning to the market.",
                    "technical factors are aligning for a potential move up."
                ]
                risk = "However, maintain caution as volume is not yet peak."
            else:
                reasons = [
                    "technical structure is weakening.",
                    "selling pressure is outweighing buyer interest.",
                    "momentum is fading, suggesting further downside."
                ]
                risk = "Watch for a break of support levels."

            # Pick a random phrasing to make it feel natural
            explanation = f"{symbol} is showing {bias} potential ({prob}% confidence) because {random.choice(reasons)} {risk}"

            # 3. Create the Final Packet for the User
            narrative_packet = {
                "symbol": symbol,
                "headline": headline,
                "story": explanation,
                "probability": prob,
                "bias": bias
            }
            
            # 4. Publish to Frontend
            print(f"🗣️ Narrated: {headline}")
            r.publish("narrative_results", json.dumps(narrative_packet))

if __name__ == "__main__":
    asyncio.run(narrate_market())