import streamlit as st
import redis
import json
import time
import os
from PIL import Image

# --- CONFIGURATION ---
# Set page to wide mode by default
st.set_page_config(page_title="ForwardFin AI", layout="wide")

# Connect to Redis (Cloud or Local)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
try:
    r = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    r.ping() # Test connection
except:
    st.error(f"❌ Could not connect to Redis at {REDIS_HOST}. Is it running?")
    st.stop()

# --- HEADER SECTION (Logo + Title) ---
# We use columns to place logo next to title
col1, col2 = st.columns([1, 6]) # col2 is 6 times wider than col1

with col1:
    try:
        # Try to load the logo
        # Since we run from root, the path is services/frontend/assets/logo.png
        image = Image.open('services/frontend/assets/logo.png')
        st.image(image, use_column_width=True)
    except FileNotFoundError:
        # If logo isn't there yet, just show an emoji placeholder
        st.header("🤖")

with col2:
    st.title("ForwardFin AI Terminal")
    st.markdown("*Real-Time Institutional Grade Analytics*")

st.divider() # A nice line separator

# --- MAIN CONTENT LAYOUT ---
# Create a 2-column layout for the main dashboard
# Left column gets 2 parts width, Right column gets 1 part width
left_col, right_col = st.columns([2, 1])

# Placeholder containers so we can update data live without refreshing
with left_col:
    st.subheader("📡 Market Data Stream")
    price_container = st.empty()
    chart_container = st.empty()

with right_col:
    st.subheader("🧠 AI Neural Net")
    prediction_container = st.empty()
    st.divider()
    st.subheader("📰 Narrative Desk")
    narrative_container = st.empty()

# --- THE LIVE LOOP ---
# This runs every time Streamlit refreshes (about every few seconds)

# 1. FETCH DATA from Redis
price_data = r.get("latest_price")
prediction_data = r.get("latest_prediction")
narrative_data = r.get("latest_narrative")

# 2. RENDER PRICE
if price_data:
    data = json.loads(price_data)
    price = float(data['price'])
    rsi = float(data['indicators']['rsi'])
    macd = float(data['indicators']['macd'])
    
    with price_container.container():
        # Use BIG metric display
        st.metric(label="BTC-USD Price", value=f"${price:,.2f}", delta=f"RSI: {rsi:.1f}")
        st.caption(f"MACD Momentum: {macd:.4f}")

# 3. RENDER AI PREDICTION
if prediction_data:
    pred = json.loads(prediction_data)
    bias = pred['bias']
    prob = pred['probability']
    
    # Color-code the result
    color = "green" if bias == "BULLISH" else "red"
    
    with prediction_container.container():
        st.markdown(f"### Signal: :{color}[{bias}]")
        st.progress(prob / 100)
        st.caption(f"Confidence: {prob}%")

# 4. RENDER NARRATIVE
if narrative_data:
    with narrative_container.container():
        # Display as a nice block quote
        st.info(narrative_data.strip('"'))
else:
    narrative_container.caption("Waiting for market synthesis...")

# Auto-refresh the page every 2 seconds to pick up new Redis data
time.sleep(2)
st.rerun()