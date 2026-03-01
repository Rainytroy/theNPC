import asyncio
import os
import sys
import httpx

# Add parent dir to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings

async def test_generation():
    print("Starting Image Generation Test (Exhaustive)...")
    
    url = settings.IMAGE_SERVICE_URL
    print(f"URL: {url}")
    
    keys = [
        settings.GEMINI_API_KEY,
        "sk-f47bf165fa5b4566a2e9e3410c4920a1" # DashScope
    ]
    
    payload = {
        "prompt": "Test",
        "aspectRatio": "9:16",
        "imageSize": "2K",
        "enableGoogleSearch": False
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for key in keys:
            if not key: continue
            print(f"\nTesting Key: {key[:5]}...")
            
            # Try different headers
            header_variants = [
                {"token": key},
                {"token": f"Bearer {key}"},
                {"Authorization": key},
                {"Authorization": f"Bearer {key}"},
                {"x-api-key": key}
            ]
            
            for headers in header_variants:
                headers["Content-Type"] = "application/json"
                try:
                    print(f"  Trying headers: {list(headers.keys())}")
                    resp = await client.post(url, headers=headers, json=payload)
                    print(f"  Result: {resp.status_code}")
                    if resp.status_code == 200:
                        print("  SUCCESS!")
                        print(resp.json())
                        return
                except Exception as e:
                    print(f"  Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_generation())
