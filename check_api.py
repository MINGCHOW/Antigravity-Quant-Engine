import requests
import json
import time

URL = "https://jpthermjdexc.ap-northeast-1.clawcloudrun.com/analyze_full"

payload = {
    "code": "601958",
    "balance": 100000,
    "risk": 0.01
}

print(f"Testing API: {URL}")
print(f"Payload: {payload}")

try:
    start = time.time()
    resp = requests.post(URL, json=payload, timeout=20)
    end = time.time()
    
    print(f"Status Code: {resp.status_code}")
    print(f"Time Taken: {end - start:.2f}s")
    
    try:
        data = resp.json()
        print("Response JSON keys:", data.keys())
        if 'technical' in data:
            print("Technical keys:", data['technical'].keys())
        if 'signal' in data:
            print("Signal:", data['signal'])
            
    except Exception as e:
        print("Failed to parse JSON:", e)
        print("Raw text:", resp.text[:500])

except Exception as e:
    print(f"Request Failed: {e}")
