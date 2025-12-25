import streamlit as st
import redis
import json
import time
import os
import pandas as pd

# Page Config (The Title Bar)
st.set_page_config(
    page_title="ForwardFin Terminal",
    page_icon="🔮",
    layout="wide"
)

# Custom CSS to make it look like a pro terminal
st.markdown("""
<style>
    .stMetric {
        background-color: #0E1117;
        padding: 15px;
        border-radius: 5px;
        border: 1px solid #262730;
    }
</style>
""", unsafe_allow_html=True)

# Connect to Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
r = redis.Redis(host=REDIS_HOST, port=6379, db=0)
pubsub = r.pubsub()
pubsub.subscribe('narrative_results')

# --- SIDEBAR ---
with st.sidebar:
    st.title("🔮 ForwardFin")
    st.caption("AI-Powered Trading Assistant")
    st.markdown("---")
    st.header("System Health")
    st.success("🟢 Ingestion: Active")
    st.success("🟢 Analysis: Active")
    st.success("🟢 AI Brain: Active")
    st.markdown("---")
    st.info(f"📡 Connected to: {REDIS_HOST}")

# --- MAIN LOOP SETUP ---
st.title("Live Market Intelligence")

# We create a SINGLE empty container that holds the whole dashboard
# This prevents the "stacking" glitch
dashboard_placeholder = st.empty()

# Initialize session state for the chart
if 'chart_data' not in st.session_state:
    st.session_state['chart_data'] = []

def get_redis_data():
    message = pubsub.get_message()
    if message and message['type'] == 'message':
        return json.loads(message['data'])
    return None

# --- THE GAME LOOP ---
while True:
    data = get_redis_data()
    
    if data:
        # Update Chart History
        st.session_state['chart_data'].append(data['probability'])
        if len(st.session_state['chart_data']) > 100:
            st.session_state['chart_data'].pop(0)

        # Update the Dashboard inside the placeholder
        with dashboard_placeholder.container():
            # 1. KPI Row
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Asset", data['symbol'])
            
            with col2:
                # Color code the bias
                bias_color = "normal"
                if data['bias'] == "BULLISH": bias_color = "off" # Streamlit handles green automatically for + delta
                st.metric("AI Bias", data['bias'], delta=data['bias'])

            with col3:
                # Clean up the long decimal number
                prob = float(data['probability'])
                st.metric("Confidence", f"{prob:.1f}%")
                
            with col4:
                 st.metric("Signal Source", "XGBoost + MACD")

            st.markdown("---")

            # 2. Main Layout (Chart + Story)
            chart_col, story_col = st.columns([2, 1])
            
            with chart_col:
                st.subheader("⚠️ Confidence Trend")
                # Create a simple dataframe for the chart
                df = pd.DataFrame(st.session_state['chart_data'], columns=["Bullish Probability"])
                st.line_chart(df)

            with story_col:
                st.subheader("📝 AI Narrative")
                st.info(f"**{data['headline']}**")
                st.write(data['story'])
                st.caption("Updated just now")

    # Sleep briefly to save CPU
    time.sleep(0.1)