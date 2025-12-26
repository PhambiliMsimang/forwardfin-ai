import subprocess
import time
import sys

print("🚀 START MANAGER: Launching ForwardFin Services...")

# 1. Start Analysis Engine (Background)
subprocess.Popen([sys.executable, "services/analysis/main.py"])
print("✅ Analysis Service Started")

# 2. Start Inference Engine (Background)
subprocess.Popen([sys.executable, "services/inference/main.py"])
print("✅ Inference Service Started")

# 3. Start Gateway (Foreground - Keeps the app running)
# We use .run() here so the script stays alive listening for requests
print("✅ Gateway Service Starting on Port 10000...")
subprocess.run(["uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "10000"])