import httpx
import json
import base64
import hashlib
import asyncio
import traceback
from io import BytesIO
from typing import Optional, List
from PIL import Image
from ..core.config import settings
from .oss_service import oss_service
from datetime import datetime

class ImageService:
    def __init__(self):
        # Text to Image (Avatar)
        self.api_url = settings.IMAGE_SERVICE_URL

        # Image Edit (Manga)
        self.edit_api_url = settings.IMAGE_EDIT_URL
        self.token = settings.GEMINI_API_KEY
        
    async def generate_avatar(self, prompt: str, world_id: str, npc_id: str, max_retries: int = 3) -> Optional[str]:
        """
        Generate avatar from text, upload to OSS, return OSS URL.
        Includes retry logic for API stability.
        """
        if not self.api_url or not self.token:
            print("Image Service not configured")
            return None
            
        print(f"Generating avatar for NPC {npc_id} in World {world_id}...")
        
        headers = {
            "token": self.token,
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": prompt,
            "aspectRatio": "9:16",
            "imageSize": "1K",
            "enableGoogleSearch": True
        }
        
        for attempt in range(max_retries):
            try:
                print(f"DEBUG: Image Generation Attempt {attempt + 1}/{max_retries}")
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(self.api_url, headers=headers, json=payload)
                    
                    if response.status_code != 200:
                        print(f"Image API Failed (Attempt {attempt+1}): {response.status_code}")
                        print(f"Response Body: {response.text}")
                        # Retry on server errors or rate limits
                        if response.status_code in [429, 500, 502, 503, 504]:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 * (attempt + 1))
                                continue
                        return None
                    
                    # Parse Response
                    try:
                        data = response.json()
                    except json.JSONDecodeError:
                        print(f"Image API returned invalid JSON: {response.text}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        return None
                    
                    # Check for successful response
                    if data.get("httpCode") != 200:
                        print(f"Image API Error: {data.get('msg', 'Unknown error')}")
                        print(f"Full Response: {json.dumps(data, ensure_ascii=False)}")
                        return None
                    
                    # Extract image URL from result
                    result = data.get("result", {})
                    image_url = result.get("imageUrl")
                    
                    if not image_url:
                        print("No imageUrl in API response")
                        return None
                    
                    print(f"Image generated successfully: {image_url}")
                    
                    # Download the image
                    print(f"Downloading generated image from {image_url}...")
                    img_resp = await client.get(image_url)
                    if img_resp.status_code == 200:
                        image_data = img_resp.content
                    else:
                        print(f"Failed to download generated image: {img_resp.status_code}")
                        return None
                    
                    # Upload to OSS
                    oss_url = oss_service.upload_from_url(image_data, world_id, npc_id)
                    print(f"Avatar uploaded to OSS: {oss_url}")
                    return oss_url
                    
            except Exception as e:
                print(f"Error generating avatar (Attempt {attempt+1}): {e}")
                traceback.print_exc()
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 * (attempt + 1))
        
        print(f"Failed to generate avatar after {max_retries} attempts.")
        return None

    async def combine_reference_images(self, world_id: str, npc_urls: List[str]) -> Optional[str]:
        """
        Combine multiple NPC avatars into a single reference image.
        Uses caching based on hash of URLs.
        """
        if not npc_urls:
            return None
            
        # 1. Generate Fingerprint (Hash)
        # Sort to ensure order doesn't matter for same set
        sorted_urls = sorted(npc_urls)
        combined_str = "".join(sorted_urls)
        ref_hash = hashlib.md5(combined_str.encode('utf-8')).hexdigest()
        
        object_name = f"theNPC/{world_id}/manga/refs/{ref_hash}.jpg"
        
        # 2. Check Cache (OSS)
        if oss_service.file_exists(object_name):
            # Reconstruct URL
            # This logic mimics oss_service logic, slightly redundant but safe
            protocol = "https://"
            domain = oss_service.endpoint.replace("http://", "").replace("https://", "")
            return f"{protocol}{oss_service.bucket_name}.{domain}/{object_name}"
            
        print(f"Cache miss for reference image {ref_hash}. Stitching...")
        
        # 3. Download Images
        images = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for url in sorted_urls:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        images.append(Image.open(BytesIO(resp.content)))
                    else:
                        print(f"Failed to download avatar: {url}")
            
            if not images:
                return None
                
            # 4. Stitch Images
            # Resize all to height 512, keeping aspect ratio
            target_height = 512
            resized_images = []
            total_width = 0
            
            for img in images:
                aspect = img.width / img.height
                new_width = int(target_height * aspect)
                resized_img = img.resize((new_width, target_height), Image.Resampling.LANCZOS)
                resized_images.append(resized_img)
                total_width += new_width
            
            # Create canvas
            combined_img = Image.new('RGB', (total_width, target_height))
            
            # Paste
            current_x = 0
            for img in resized_images:
                combined_img.paste(img, (current_x, 0))
                current_x += img.width
                
            # Save to buffer
            output_buffer = BytesIO()
            combined_img.save(output_buffer, format='JPEG', quality=90)
            file_data = output_buffer.getvalue()
            
            # 5. Upload to OSS
            return oss_service.upload_file(file_data, object_name)
            
        except Exception as e:
            print(f"Error combining reference images: {e}")
            return None

    async def generate_manga_page(self, prompt: str, reference_image: str, world_id: str) -> Optional[str]:
        """
        Generate a manga page using reference image editing.
        Returns the OSS URL of the saved page.
        """
        if not self.edit_api_url or not self.token:
            print("Manga Image Service not configured")
            return None

        print(f"Generating manga page for World {world_id}...")

        headers = {
            "token": self.token,
            "Content-Type": "application/json"
        }

        # POC confirmed config:
        # aspectRatio: 2:3
        # inputImage: String URL (not list)
        payload = {
            "prompt": prompt,
            "inputImage": reference_image,
            "enableGoogleSearch": True,
            #"aspectRatio": "2:3", # User requested to remove parameter and rely on prompt
            "imageSize": "1K"
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self.edit_api_url, headers=headers, json=payload)

                if response.status_code != 200:
                    print(f"Manga API Failed: {response.status_code} - {response.text}")
                    return None

                data = response.json()
                
                if data.get("httpCode") != 200:
                    print(f"Manga API Error: {data.get('msg', 'Unknown error')}")
                    return None

                result = data.get("result", {})
                image_url = result.get("imageUrl")

                if not image_url:
                    print("No imageUrl in Manga API response")
                    return None

                print(f"Manga page generated: {image_url}")

                # Download and Upload to OSS
                print(f"Downloading manga page from {image_url}...")
                img_resp = await client.get(image_url)
                if img_resp.status_code == 200:
                    image_data = img_resp.content
                else:
                    print(f"Failed to download manga page: {img_resp.status_code}")
                    return None

                # Upload to OSS
                # Generate a unique ID for the page (timestamp)
                page_id = f"page_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                oss_url = oss_service.upload_file(image_data, f"theNPC/{world_id}/manga/{page_id}.jpg")
                print(f"Manga page uploaded to OSS: {oss_url}")
                return oss_url

        except Exception as e:
            print(f"Error generating manga page: {e}")
            return None

image_service = ImageService()
