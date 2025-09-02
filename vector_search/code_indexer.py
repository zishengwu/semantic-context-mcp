from pathlib import Path
from datetime import datetime
from typing import List, Dict
from hashlib import md5
import os
from openai import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter

from .vector_db import VectorDBManager
from .ast_parser import SmartASTParser
from .code_change_tracker import CodeChangeTracker

class IncrementalCodeIndexer:
    """增量代码索引系统

    提供：
    - run_incremental_indexing() : 仅处理变更的文件
    - full_index() : 首次或强制全量索引
    """

    def __init__(self, embedding_client:OpenAI, vector_db_manager: VectorDBManager):
        self.parser = SmartASTParser()
        self.vector_db = vector_db_manager
        self.embedding_client = embedding_client

    def run_incremental_indexing(self, project_root_str: str):
        """执行增量索引"""
        print("🔍 检测代码变更...")
        changes = CodeChangeTracker.detect_changes(project_root_str)

        print(f"📊 变更统计:")
        print(f"新增文件: {len(changes['added'])}")
        print(f"修改文件: {len(changes['modified'])}")
        print(f"删除文件: {len(changes['deleted'])}")
        print(f"未变更文件: {len(changes['unchanged'])}")

        project_root = Path(project_root_str)
        proj_name = project_root.name
        proj_hash = md5(str(project_root.resolve()).encode()).hexdigest()[:8]
        collection_name = f"{proj_name}-{proj_hash}"

        # 处理删除的文件
        if changes['deleted']:
            print("🗑️  处理删除的文件...")
            for file_path in changes['deleted']:
                self.vector_db.delete_blocks_by_file(collection_name, file_path)
            CodeChangeTracker.remove_file_hash(project_root_str, changes['deleted'])

        # 处理新增和修改的文件
        files_to_process = changes['added'] + changes['modified']
        if files_to_process:
            print(f"🔄 处理 {len(files_to_process)} 个文件...")
            self._process_files(project_root_str, files_to_process)

        # 更新元数据
        metadata = CodeChangeTracker.load_metadata(project_root_str)
        metadata['last_index_time'] = datetime.now().isoformat()
        file_hashes = CodeChangeTracker._collect_file_hashes(project_root_str)
        metadata['total_files_indexed'] = len(file_hashes)
        CodeChangeTracker.save_metadata(project_root_str, metadata)

        print("✅ 增量索引完成！")

    def full_index(self, project_root_str: str):
        """执行完整索引：扫描所有可索引的 .py 文件并作为新增处理"""
        all_py_files = []
        EXTS = {".py", ".java", ".cpp", ".cc", ".cxx", ".c", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".go"}
        project_path = Path(project_root_str)
        for file_path in project_path.rglob('*'):
            if file_path.suffix.lower() in EXTS:
                if CodeChangeTracker._should_index_file(file_path):
                    rel_path = str(file_path.relative_to(project_path))
                    all_py_files.append(rel_path)

        if not all_py_files:
            print("No python files found to index.")
            return

        # treat everything as added for first-time index
        print(f"🔁 全量索引：发现 {len(all_py_files)} 个文件，开始处理...")
        self._process_files(project_root_str, all_py_files)
        # update metadata
        metadata = CodeChangeTracker.load_metadata(project_root_str)
        metadata['last_index_time'] = datetime.now().isoformat()
        file_hashes = CodeChangeTracker._collect_file_hashes(project_root_str)
        metadata['total_files_indexed'] = len(file_hashes)
        CodeChangeTracker.save_metadata(project_root_str, metadata)

    def _process_files(self, project_root_str:str, file_paths: List[str]):
        """处理文件列表"""
        new_hashes = []
        all_blocks = []

        project_root = Path(project_root_str)
        proj_name = project_root.name
        proj_hash = md5(str(project_root.resolve()).encode()).hexdigest()[:8]
        collection_name = f"{proj_name}-{proj_hash}"

        file_hashes = CodeChangeTracker._collect_file_hashes(project_root_str)
        for rel_path in file_paths:
            file_path = Path(project_root_str) / rel_path

            # 删除旧索引（对于修改的文件）
            if rel_path in file_hashes:
                self.vector_db.delete_blocks_by_file(collection_name, str(file_path))

            # 解析新代码块
            blocks = self.parser.extract_code_blocks(file_path)
            all_blocks.extend(blocks)

            # 计算文件哈希
            file_hash = CodeChangeTracker.compute_file_hash(file_path)
            new_hashes.append((rel_path, file_hash))

            print(f"  处理 {rel_path}: 找到 {len(blocks)} 个代码块")

        # 生成嵌入向量
        if all_blocks:
            print("🧠 生成嵌入向量...")
            
            # 处理长文本块的切分
            all_processed_blocks = []
            all_processed_texts = []
            
            for block in all_blocks:
                text = self._prepare_text_for_embedding(block)
                
                # 检查是否需要切分
                max_length = os.environ.get("MAX_LENGTH", 8000)
                if len(text) <= max_length:
                    all_processed_blocks.append(block)
                    all_processed_texts.append(text)
                else:
                        
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=int(os.environ.get("CHUNK_SIZE", 4000)),
                        chunk_overlap=int(os.environ.get("CHUNK_OVERLAP", 200)),
                        length_function=len,
                        separators=["\n\n", "\n", " ", ""]
                    )
                    chunks = text_splitter.split_text(text)
                    
                    # 为每个chunk创建新的block
                    for i, chunk in enumerate(chunks):
                        new_block = block.copy()
                        new_block['name'] = f"{block['name']}_chunk_{i+1}"
                        new_block['code'] = chunk  # 使用切分后的代码
                        new_block['signature'] = f"{block['signature']} (part {i+1})"
                        # 为切分后的块生成唯一ID
                        new_block['id'] = f"{block['id']}_chunk_{i+1}"
                        all_processed_blocks.append(new_block)
                        all_processed_texts.append(chunk)

            print(f"处理后的文本块: {len(all_processed_texts)}")
            
            embeddings = []
            valid_blocks = []
            
            for i, (text, block) in enumerate(zip(all_processed_texts, all_processed_blocks)):
                try:
                    response = self.embedding_client.embeddings.create(input=[text], model="jina")
                    embeddings.append(response.data[0].embedding)
                    valid_blocks.append(block)
                except Exception as e:
                    print(f"处理文本块 {i} 时出错: {e}")
                    print(f"文本长度: {len(text)}")
                    continue
            
            # 更新向量数据库
            print("💾 更新向量数据库...")
            if embeddings and valid_blocks:
                self.vector_db.upsert_blocks(collection_name, valid_blocks, embeddings)
            else:
                print("⚠️  没有有效的嵌入向量或代码块需要更新")

        # 更新文件哈希记录
        file_paths, hashes = zip(*new_hashes) if new_hashes else ([], [])
        CodeChangeTracker.update_file_hashes(project_root_str, list(file_paths), list(hashes))

    def _prepare_text_for_embedding(self, block: Dict) -> str:
        """准备用于嵌入的文本"""
        # 组合代码、签名和上下文信息
        parts = [
            f"Type: {block['type']}",
            f"Name: {block['name']}",
            f"Signature: {block['signature']}",
            f"Code: {block['code']}"
        ]
        return "\n".join(parts)

    def get_index_status(self, project_root_str: str):
        """获取索引状态"""
        metadata = CodeChangeTracker.load_metadata(project_root_str)
        file_hashes = CodeChangeTracker._collect_file_hashes(project_root_str)
        return {
            'last_index_time': metadata['last_index_time'],
            'total_files': len(file_hashes),
            'file_hashes': file_hashes,
            'path': str(Path(project_root_str) / ".code_index")
        }