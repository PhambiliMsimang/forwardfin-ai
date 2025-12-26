import subprocess
import sys
import time
import os

print("🚀 START MANAGER: Launching ForwardFin Services...")

# 1. Start Analysis Engine (Background)
print("   - Starting Analysis Engine...")
analysis = subprocess.Popen([sys.executable, "services/analysis/main.py"])

# 2. Start Inference Engine (Background)
print("   - Starting Inference Engine...")
inference = subprocess.Popen([sys.executable, "services/inference/main.py"])

# Give them a second to warm up
time.sleep(2)

# 3. Start Gateway (Foreground)
# We use 'python -m uvicorn' to guarantee we find the command
print("✅ Gateway Service Starting on Port 10000...")

# This command blocks the script from exiting, keeping the server alive
try:
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "10000"],
        check=True
    )
except KeyboardInterrupt:
    print("🛑 Stopping services...")
    analysis.terminate()
    inference.terminate()