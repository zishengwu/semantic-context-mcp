
from pathlib import Path
from fastmcp import FastMCP
from hashlib import md5
from openai import OpenAI
import os
import threading
import time
import logging

from .code_indexer import IncrementalCodeIndexer
from .vector_db import VectorDBManager


# persist_dir in user's home to centralize chromadb storage
user_chroma_dir = str(Path.home() / ".chromadb")
vdb = VectorDBManager(persist_dir=user_chroma_dir)
embedding_client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY",""), 
    base_url=os.environ.get("OPENAI_BASE_URL","")
)
indexer = IncrementalCodeIndexer(
    embedding_client=embedding_client,
    vector_db_manager=vdb
)


mcp = FastMCP("Semantic Context MCP Server!")

# 定时任务管理器
class BackgroundIndexer:
    def __init__(self, indexer):
        self.indexer = indexer
        self.running = False
        self.thread = None
        self.current_project = None
        
    def start_auto_indexing(self, project_path: str):
        """启动自动索引，包括初始化全量索引和定时增量索引"""
        self.current_project = project_path
        
        # 在后台线程中执行初始化全量索引
        init_thread = threading.Thread(
            target=self._initial_full_index,
            args=(project_path,),
            daemon=True
        )
        init_thread.start()
        
        # 启动定时增量索引
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._periodic_incremental_index, daemon=True)
            self.thread.start()
    
    def _initial_full_index(self, project_path: str):
        """初始化全量索引"""
        try:
            logging.info(f"Starting initial full index for {project_path}")
            self.indexer.full_index(project_path)
            logging.info(f"Initial full index completed for {project_path}")
        except Exception as e:
            logging.error(f"Error during initial full index: {e}")
    
    def _periodic_incremental_index(self):
        """每5分钟执行一次增量索引"""
        while self.running:
            if self.current_project:
                try:
                    logging.info("Running periodic incremental index...")
                    self.indexer.run_incremental_indexing(self.current_project)
                    logging.info("Periodic incremental index completed")
                except Exception as e:
                    logging.error(f"Error during periodic incremental index: {e}")
            
            # 等待5分钟
            time.sleep(300)  # 300秒 = 5分钟
    
    def stop(self):
        """停止定时任务"""
        self.running = False

# 创建后台索引器实例
background_indexer = BackgroundIndexer(indexer)

@mcp.tool()
def full_index(project_path: str):
    try:
        background_indexer.start_auto_indexing(project_path)
        return {
            "status": "ok",
            "message": "Full indexing ensured (started in background if not present)"
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def status(project_path: str):
    try:
        return indexer.get_index_status(project_path)
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def query(project_path: str, text: str, top_k: int = 5):
    try:
        project_root = Path(project_path)
        proj_name = project_root.name
        proj_hash = md5(str(project_root.resolve()).encode()).hexdigest()[:8]
        collection_name = f"{proj_name}-{proj_hash}"

        emb = embedding_client.embeddings.create(
            input=[text],
            model=os.environ.get("OPENAI_MODEL_NAME", "")
        ).data[0].embedding

        res = vdb.query_by_embedding(
            collection_name=collection_name, embedding=emb, top_k=top_k
        )
        return res
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()