import requests
import json

def test_gemini():
    url = "http://127.0.0.1:25998/chat"
    payload = {
        "messages": [{"role": "user", "content": "Hello, are you there?"}],
        "model": "gemini-3-pro-preview",
        "temperature": 0.7
    }
    
    print(f"Connecting to {url}...")
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Gemini Service is UP and Working!")
        else:
            print("❌ Gemini Service returned error.")
            
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        print("Is the service running? Check the CMD window for errors.")

if __name__ == "__main__":
    test_gemini()
