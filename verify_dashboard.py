
import requests
import time
import subprocess
import sys
import threading

def run_server():
    try:
        subprocess.run(["uvicorn", "main:app", "--port", "8001"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

def test_dashboard():
    # Start server in thread
    server_process = subprocess.Popen(["uvicorn", "main:app", "--port", "8011"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(5) # Wait for startup
    
    try:
        # 1. Test Static File Serving
        print("Testing Static File Serving...")
        resp = requests.get("http://127.0.0.1:8011/")
        if resp.status_code == 200 and "<!DOCTYPE html>" in resp.text:
            print("[OK] Dashboard (index.html) served successfully.")
        else:
            print(f"[FAIL] Failed to serve dashboard. Status: {resp.status_code}")
            
        # 2. Test API Connectivity
        print("Testing API...")
        resp = requests.get("http://127.0.0.1:8011/api/info")
        if resp.status_code == 200:
             print("[OK] API (/api/info) is responsive.")
        else:
             print(f"[FAIL] API check failed. Status: {resp.status_code}")
             
    except Exception as e:
        print(f"[FAIL] Test failed with exception: {e}")
    finally:
        server_process.terminate()

if __name__ == "__main__":
    test_dashboard()
