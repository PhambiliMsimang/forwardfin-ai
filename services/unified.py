import threading
import runpy
import time
import os

# This script merges all your backend robots into one memory-efficient process
print("🤖 MEGABOT: Initializing Unified Backend...")

def run_service(path):
    print(f"🚀 Launching Service: {path}")
    try:
        # This runs your existing main.py files exactly as they are
        runpy.run_path(path, run_name="__main__")
    except Exception as e:
        print(f"❌ CRASH in {path}: {e}")

if __name__ == "__main__":
    # List of robots to start
    services = [
        "services/ingestion/main.py",
        "services/analysis/main.py",
        "services/inference/main.py",
        "services/narrative/main.py"
    ]
    
    threads = []
    for service in services:
        # Create a thread for each robot
        t = threading.Thread(target=run_service, args=(service,))
        t.daemon = True  # Ensures they die when the main script dies
        t.start()
        time.sleep(2) # Give each one a breather before starting the next

    print("✅ MEGABOT: All services launched. Monitoring...")
    
    # Keep the main heart beating
    while True:
        time.sleep(10)