import asyncio
import sys
import os

# Add current directory to path so we can import config/llm_client
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from llm_client import llm_client
from config import settings

async def main():
    print(f"Testing connection to LLM Service at: {settings.LLM_SERVICE_URL}")
    
    # 1. Check Health
    print("1. Checking Health...", end=" ")
    try:
        # Check Health Manually to see details
        print(f"   Debug: Sending GET request to {settings.LLM_SERVICE_URL}/health")
        import httpx
        # trust_env=False to ignore system proxies
        async with httpx.AsyncClient(trust_env=False) as client:
            resp = await client.get(f"{settings.LLM_SERVICE_URL}/health", timeout=5.0)
            print(f"   Debug: Status Code: {resp.status_code}")
            print(f"   Debug: Response: {resp.text}")
            
        is_healthy = await llm_client.check_health()
        if is_healthy:
            print("✅ Connected!")
        else:
            print("❌ Failed to connect (Health check returned False).")
            return
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    # 2. Test Simple Chat
    print("2. Testing Simple Chat...", end=" ")
    try:
        response = await llm_client.simple_chat("Hello, are you ready?")
        print("✅ Response received:")
        print(f"   > {response}")
    except Exception as e:
        print(f"❌ Chat failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
