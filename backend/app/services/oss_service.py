import oss2
import os
import uuid
import time
from datetime import datetime
from ..core.config import settings

class OSSService:
    def __init__(self):
        self.access_key_id = settings.ALIYUN_ACCESS_KEY_ID
        self.access_key_secret = settings.ALIYUN_ACCESS_KEY_SECRET
        self.bucket_name = settings.OSS_BUCKET_NAME
        self.endpoint = settings.OSS_ENDPOINT
        
        if self.access_key_id and self.access_key_secret and self.bucket_name and self.endpoint:
            self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)
        else:
            print("WARNING: OSS Configuration missing. OSS Service disabled.")
            self.bucket = None

    def upload_file(self, file_data: bytes, object_name: str, max_retries: int = 3) -> str:
        """
        Upload generic file bytes to OSS with specified object name (path).
        Includes retry logic for network stability.
        """
        if not self.bucket:
            raise Exception("OSS Service not configured")
            
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                self.bucket.put_object(object_name, file_data)
                
                # Construct URL
                protocol = "https://"
                domain = self.endpoint.replace("http://", "").replace("https://", "")
                
                url = f"{protocol}{self.bucket_name}.{domain}/{object_name}"
                return url
                
            except Exception as e:
                last_exception = e
                print(f"OSS Upload Attempt {attempt + 1}/{max_retries} Failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait 2 seconds before retry
                    
        raise last_exception or Exception("OSS Upload Failed after retries")

    def upload_from_url(self, image_data: bytes, world_id: str, npc_id: str) -> str:
        """
        Upload image bytes to OSS.
        Path: theNPC/{world_id}/npcs/{npc_id}_{timestamp}.png
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        object_name = f"theNPC/{world_id}/npcs/{npc_id}_{timestamp}.png"
        return self.upload_file(image_data, object_name)

    def upload_custom_avatar(self, file_data: bytes, world_id: str, npc_id: str, extension: str = "png") -> str:
        """
        Upload user uploaded avatar to OSS.
        Path: theNPC/{world_id}/custom_avatars/{npc_id}_{timestamp}.{extension}
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        object_name = f"theNPC/{world_id}/custom_avatars/{npc_id}_{timestamp}.{extension}"
        return self.upload_file(file_data, object_name)

    def file_exists(self, object_name: str) -> bool:
        """Check if file exists in OSS"""
        if not self.bucket:
            return False
        return self.bucket.object_exists(object_name)

oss_service = OSSService()
