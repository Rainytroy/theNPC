"""
MemoryService - NPC Memory Storage using ChromaDB

Supports both old (0.3.x) and new (0.4.x+) ChromaDB APIs.
"""
import chromadb
import logging
from typing import List, Dict, Optional
import os
import uuid
import hashlib
from datetime import datetime
from ..core.config import settings

logger = logging.getLogger(__name__)


class SimpleHashEmbeddingFunction:
    """
    Simple hash-based embedding function that works offline.
    This is not semantic search, but works for metadata-based filtering.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
    
    def __call__(self, input: List[str]) -> List[List[float]]:
        embeddings = []
        texts = input if isinstance(input, list) else [input]
        for text in texts:
            # Create a deterministic hash-based "embedding"
            hash_bytes = hashlib.sha384(text.encode('utf-8')).digest()
            # Convert to floats between -1 and 1
            embedding = [(b / 127.5 - 1.0) for b in hash_bytes]
            embeddings.append(embedding)
        return embeddings


class MemoryService:
    _instances: Dict[str, 'MemoryService'] = {}

    def __init__(self, world_id: str):
        self.world_id = world_id
        self.is_new_api = False  # Track which API version we're using
        
        # Persist to disk
        persist_path = os.path.join(settings.DATA_DIR, "worlds", world_id, "memory_db")
        os.makedirs(persist_path, exist_ok=True)
        
        # Safe collection name
        safe_world_id = world_id.replace("-", "_")
        self.collection_name = f"world_{safe_world_id}_memory"
        
        # Create embedding function
        self.hash_func = SimpleHashEmbeddingFunction()
        
        # Try to initialize ChromaDB client (auto-detect version)
        self.client = None
        self.collection = None
        
        try:
            # Try new API first (0.4.x+)
            if hasattr(chromadb, 'PersistentClient'):
                self.client = chromadb.PersistentClient(path=persist_path)
                self.is_new_api = True
                logger.info(f"Using ChromaDB new API (PersistentClient)")
            else:
                raise AttributeError("PersistentClient not found")
        except (AttributeError, TypeError):
            try:
                # Try old API (0.3.x)
                from chromadb.config import Settings as ChromaSettings
                self.client = chromadb.Client(ChromaSettings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=persist_path,
                    anonymized_telemetry=False
                ))
                self.is_new_api = False
                logger.info(f"Using ChromaDB old API (0.3.x)")
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB with old API: {e}")
                # Last fallback: in-memory client
                try:
                    self.client = chromadb.Client()
                    self.is_new_api = False
                    logger.warning("Using in-memory ChromaDB client (no persistence)")
                except Exception as e2:
                    logger.error(f"Failed to initialize any ChromaDB client: {e2}")
                    self.client = None
        
        # Get or create collection
        if self.client:
            try:
                if self.is_new_api:
                    self.collection = self.client.get_or_create_collection(
                        name=self.collection_name,
                        metadata={"hnsw:space": "cosine"}
                    )
                else:
                    # Old API with embedding function
                    self.collection = self.client.get_or_create_collection(
                        name=self.collection_name,
                        embedding_function=self.hash_func
                    )
                logger.info(f"MemoryService initialized for world {world_id}")
            except Exception as e:
                logger.error(f"Failed to create collection: {e}")
                self.collection = None

    @classmethod
    def get_instance(cls, world_id: str) -> 'MemoryService':
        if world_id not in cls._instances:
            cls._instances[world_id] = MemoryService(world_id)
        return cls._instances[world_id]

    def add_memory(self, npc_id: str, content: str, game_time: str, memory_type: str = "social", importance: int = 1):
        """Add a memory fragment"""
        if not self.collection:
            logger.warning("No collection available, skipping add_memory")
            return
            
        try:
            mem_id = str(uuid.uuid4())
            
            # Metadata for filtering
            metadata = {
                "npc_id": npc_id,
                "type": memory_type,
                "importance": importance,
                "game_time": game_time,
                "created_at": datetime.now().isoformat()
            }
            
            if self.is_new_api:
                # New API: manually provide embeddings
                embedding = self.hash_func([content])[0]
                self.collection.add(
                    documents=[content],
                    metadatas=[metadata],
                    ids=[mem_id],
                    embeddings=[embedding]
                )
            else:
                # Old API: collection has embedding function built-in
                self.collection.add(
                    documents=[content],
                    metadatas=[metadata],
                    ids=[mem_id]
                )
            logger.debug(f"Added memory for {npc_id}: {content[:30]}...")
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")

    def query_memory(self, npc_id: str, query_text: str, n_results: int = 3) -> List[str]:
        """Retrieve relevant memories for an NPC"""
        if not self.collection:
            return []
            
        try:
            # Check if collection is empty
            if self.collection.count() == 0:
                return []

            if self.is_new_api:
                # New API: use query_embeddings
                query_embedding = self.hash_func([query_text])[0]
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where={"npc_id": npc_id}
                )
            else:
                # Old API: use query_texts
                results = self.collection.query(
                    query_texts=[query_text],
                    n_results=n_results,
                    where={"npc_id": npc_id}
                )
            
            if results and results.get('documents'):
                return results['documents'][0]
            return []
        except Exception as e:
            logger.error(f"Failed to query memory: {e}")
            return []

    def get_recent_memories(self, npc_id: str, limit: int = 5) -> List[str]:
        """Get most recent memories for an NPC (fallback)"""
        if not self.collection:
            return []
            
        try:
            if self.collection.count() == 0:
                return []
            
            results = self.collection.get(
                where={"npc_id": npc_id},
                limit=limit
            )
            
            if results and results.get('documents'):
                return results['documents']
            return []
        except Exception as e:
            logger.error(f"Failed to get recent memories: {e}")
            return []

    def clear_all_memories(self):
        """Delete and recreate the entire memory collection"""
        if not self.client:
            logger.warning("No client available, skipping clear_all_memories")
            return
            
        try:
            logger.warning(f"Clearing all memories for world {self.world_id}")
            
            # Delete collection
            self.client.delete_collection(self.collection_name)
            
            # Recreate collection
            if self.is_new_api:
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            else:
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    embedding_function=self.hash_func
                )
            logger.info("Memory collection recreated successfully.")
        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")
            raise e
