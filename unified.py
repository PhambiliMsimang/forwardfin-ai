import threading
import uvicorn
import os
import sys
import time

# Force Python to see the current folder as a package
sys.path.append(os.getcwd())

print("🚀 SYSTEM STARTUP: Initializing Unified Core...")

def start_analysis_service():
    print("   ↳ 🧮 Launching Analysis Engine...")
    try:
        from services.analysis.main import process_stream
        process_stream()
    except Exception as e:
        print(f"❌ Analysis Crash: {e}")

def start_inference_service():
    print("   ↳ 🧠 Launching Inference Brain...")
    try:
        from services.inference.main import run_inference
        run_inference()
    except Exception as e:
        print(f"❌ Inference Crash: {e}")

if __name__ == "__main__":
    # 1. Start Analysis in a Background Thread
    analysis_thread = threading.Thread(target=start_analysis_service, daemon=True)
    analysis_thread.start()

    # 2. Start Inference in a Background Thread
    inference_thread = threading.Thread(target=start_inference_service, daemon=True)
    inference_thread.start()

    # 3. Start the Website (Blocking Main Thread)
    print("✅ STARTUP COMPLETE. Hosting Dashboard on Port 10000...")
    
    # We import the app object directly to avoid path issues
    try:
        from services.gateway.main import app
        uvicorn.run(app, host="0.0.0.0", port=10000)
    except ImportError as e:
        print(f"❌ Gateway Import Error: {e}")
        # Fallback to string import if direct import fails
        uvicorn.run("services.gateway.main:app", host="0.0.0.0", port=10000)