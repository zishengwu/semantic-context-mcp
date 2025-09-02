import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

import chromadb


class VectorDBManager:
    """A minimal Chroma-backed vector DB manager used for code block storage.

    Note: Chroma requires metadata values to be scalar (str/int/float/bool) or None.
    We sanitize lists/dicts by JSON-encoding them before upsert.
    """

    def __init__(self,  persist_dir: Optional[str] = None):
        # default persist dir is user's home .chromadb (cross-platform)
        if persist_dir is None:
            from pathlib import Path

            persist_dir = str(Path.home() / ".chromadb")
        os.makedirs(persist_dir, exist_ok=True)


        try:
            self.client = chromadb.PersistentClient(path=persist_dir)
        except Exception:
            # fallback to default client if Settings not available
            # Save To Memory
            self.client = chromadb.Client()

    @staticmethod
    def _sanitize_value(v: Any) -> Optional[Any]:
        # Allowed scalar types: str, int, float, bool, None
        if v is None:
            return None
        if isinstance(v, (str, int, float, bool)):
            return v
        # For lists/dicts/other objects, JSON-encode to keep metadata information
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            # Fallback to string representation
            return str(v)

    def _sanitize_metadata(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        return {k: self._sanitize_value(v) for k, v in meta.items()}

    def upsert_blocks(self, collection_name: str, blocks: List[Dict], embeddings: List[List[float]]):
        try:
            collection = self.client.get_collection(name=collection_name)
        except Exception:
            collection = self.client.create_collection(name=collection_name)

        ids = [b['id'] for b in blocks]
        raw_metadatas = [{
            'type': b.get('type'),
            'name': b.get('name'),
            'file_path': b.get('file_path'),
            'line_number': b.get('line_number'),
            'signature': b.get('signature'),
            'last_updated': datetime.now().isoformat()
        } for b in blocks]

        metadatas = [self._sanitize_metadata(m) for m in raw_metadatas]
        documents = [b.get('code', '')[:10000] for b in blocks]

        try:
            collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
        except Exception:
            # fallback for older clients
            collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)

        try:
            if hasattr(self.client, 'persist'):
                self.client.persist()
        except Exception:
            pass

    def delete_blocks_by_file(self, collection_name: str, file_path: str):
        try:
            collection = self.client.get_collection(name=collection_name)
            collection.delete(where={"file_path": file_path})
        except Exception:
            pass
        return
   
    def get_block_by_id(self, collection_name: str, block_id: str) -> Dict:
        try:
            collection = self.client.get_collection(name=collection_name)
            return collection.get(ids=[block_id])
        except Exception:
            return {}

    def query_by_embedding(self, collection_name: str, embedding: List[float], top_k: int = 5) -> Dict:
        try:
            collection = self.client.get_collection(name=collection_name)
            return collection.query(query_embeddings=[embedding], n_results=top_k, include=['metadatas', 'documents', 'distances'])
        except Exception:
            return {}