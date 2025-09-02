import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class MerkleNode:
    """Merkle树节点"""
    hash: str
    left: Optional['MerkleNode'] = None
    right: Optional['MerkleNode'] = None
    file_path: Optional[str] = None
    is_leaf: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'hash': self.hash,
            'left': self.left.to_dict() if self.left else None,
            'right': self.right.to_dict() if self.right else None,
            'file_path': self.file_path,
            'is_leaf': self.is_leaf
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MerkleNode':
        """从字典反序列化"""
        if data is None:
            return None
        node = cls(
            hash=data['hash'],
            file_path=data.get('file_path'),
            is_leaf=data.get('is_leaf', False)
        )
        if data.get('left'):
            node.left = cls.from_dict(data['left'])
        if data.get('right'):
            node.right = cls.from_dict(data['right'])
        return node


class CodeChangeTracker:
    """简单的代码变更追踪器，基于文件内容哈希检测增删改"""

    @staticmethod
    def _get_index_dir(project_root: str, index_dir: str = ".code_index") -> Path:
        """获取索引目录路径"""
        project_path = Path(project_root)
        index_path = project_path / index_dir
        index_path.mkdir(parents=True, exist_ok=True)
        return index_path

    @staticmethod
    def _get_metadata_file(project_root: str, index_dir: str = ".code_index") -> Path:
        """获取元数据文件路径"""
        return CodeChangeTracker._get_index_dir(project_root, index_dir) / "metadata.json"

    @staticmethod
    def _get_merkle_tree_file(project_root: str, index_dir: str = ".code_index") -> Path:
        """获取Merkle树文件路径"""
        return CodeChangeTracker._get_index_dir(project_root, index_dir) / "merkle_tree.json"

    @staticmethod
    def _hash_pair(left_hash: str, right_hash: str) -> str:
        """计算两个哈希的组合哈希"""
        combined = left_hash + right_hash
        return hashlib.sha256(combined.encode()).hexdigest()

    @staticmethod
    def _build_merkle_tree(file_hashes: Dict[str, str]) -> Optional[MerkleNode]:
        """构建Merkle树"""
        if not file_hashes:
            return None

        # 按文件路径排序确保一致性
        sorted_files = sorted(file_hashes.items())
        
        # 创建叶子节点
        leaves = []
        for file_path, file_hash in sorted_files:
            leaf = MerkleNode(
                hash=file_hash,
                file_path=file_path,
                is_leaf=True
            )
            leaves.append(leaf)

        # 如果只有一个文件，直接返回
        if len(leaves) == 1:
            return leaves[0]

        # 构建树
        current_level = leaves
        while len(current_level) > 1:
            next_level = []
            
            # 处理成对节点
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else None
                
                if right is None:
                    # 奇数个节点，复制最后一个节点
                    right = left
                
                # 计算父节点哈希
                parent_hash = CodeChangeTracker._hash_pair(left.hash, right.hash)
                parent = MerkleNode(
                    hash=parent_hash,
                    left=left,
                    right=right
                )
                next_level.append(parent)
            
            current_level = next_level

        return current_level[0] if current_level else None

    @staticmethod
    def load_merkle_tree(project_root: str, index_dir: str = ".code_index") -> Optional[MerkleNode]:
        """加载Merkle树"""
        merkle_file = CodeChangeTracker._get_merkle_tree_file(project_root, index_dir)
        if merkle_file.exists():
            try:
                with open(merkle_file, 'r') as f:
                    tree_data = json.load(f)
                    return CodeChangeTracker._deserialize_merkle_tree(tree_data.get('tree'))
            except Exception as e:
                print(f"加载Merkle树失败: {e}")
                return None
        return None

    @staticmethod
    def save_merkle_tree(project_root: str, root: Optional[MerkleNode], index_dir: str = ".code_index"):
        """保存Merkle树"""
        from datetime import datetime
        merkle_file = CodeChangeTracker._get_merkle_tree_file(project_root, index_dir)
        tree_data = {
            'root_hash': root.hash if root else None,
            'tree': CodeChangeTracker._serialize_merkle_tree(root),
            'timestamp': datetime.now().isoformat()
        }
        with open(merkle_file, 'w') as f:
            json.dump(tree_data, f, indent=2)

    @staticmethod
    def get_merkle_root_hash(project_root: str, index_dir: str = ".code_index") -> Optional[str]:
        """获取Merkle根哈希"""
        tree = CodeChangeTracker.load_merkle_tree(project_root, index_dir)
        return tree.hash if tree else None

    @staticmethod
    def load_metadata(project_root: str, index_dir: str = ".code_index") -> dict:
        """加载元数据"""
        metadata_file = CodeChangeTracker._get_metadata_file(project_root, index_dir)
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = {
                'last_index_time': None,
                'total_files_indexed': 0,
                'total_blocks_indexed': 0,
                'merkle_root_hash': None
            }
        return metadata

    @staticmethod
    def save_metadata(project_root: str, metadata: dict, index_dir: str = ".code_index"):
        """保存元数据"""
        metadata_file = CodeChangeTracker._get_metadata_file(project_root, index_dir)
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """计算文件哈希"""
        try:
            content = file_path.read_text(encoding='utf-8')
            return hashlib.sha256(content.encode()).hexdigest()
        except Exception as e:
            print(f"计算文件哈希失败 {file_path}: {e}")
            return ""

    @staticmethod
    def _collect_file_hashes(project_root: str) -> Dict[str, str]:
        """收集所有文件的哈希值"""
        # 这个是最新的所有文件的哈希
        project_path = Path(project_root)
        file_hashes = {}
        EXTS = {".py", ".java", ".cpp", ".cc", ".cxx", ".c", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".go"}
        for file_path in project_path.rglob('*'):
            if file_path.suffix.lower() in EXTS:
                if CodeChangeTracker._should_index_file(file_path):
                    rel_path = str(file_path.relative_to(project_path))
                    file_hash = CodeChangeTracker.compute_file_hash(file_path)
                    file_hashes[rel_path] = file_hash
        
        return file_hashes

    @staticmethod
    def detect_changes(project_root: str, index_dir: str = ".code_index") -> Dict[str, List[str]]:
        """使用Merkle树检测代码变更"""
        # project_path = Path(project_root)
        
        # 获取当前所有文件哈希（最新的），需要实时计算
        current_file_hashes = CodeChangeTracker._collect_file_hashes(project_root)
        
        # 获取旧的Merkle根哈希
        old_root_hash = CodeChangeTracker.get_merkle_root_hash(project_root, index_dir)
        
        # 构建新的Merkle树
        new_tree = CodeChangeTracker._build_merkle_tree(current_file_hashes)
        new_root_hash = new_tree.hash if new_tree else None
        
        changes = {'added': [], 'modified': [], 'deleted': [], 'unchanged': []}
        
        # 如果根哈希相同，没有变更
        if old_root_hash == new_root_hash:
            # 所有文件都是未变更的
            changes['unchanged'] = list(current_file_hashes.keys())
            return changes
        
        # 根哈希不同，需要详细检测变更
        old_tree = CodeChangeTracker.load_merkle_tree(project_root, index_dir)
        
        # 从旧树中提取文件哈希（如果存在）
        old_file_hashes = {}
        if old_tree:
            old_file_hashes = CodeChangeTracker._extract_file_hashes_from_tree(old_tree)
        
        # 检测变更
        current_files = set(current_file_hashes.keys())
        old_files = set(old_file_hashes.keys())
        
        changes['added'] = list(current_files - old_files)
        changes['deleted'] = list(old_files - current_files)
        
        # 检查共同文件的变更
        common_files = current_files & old_files
        for file_path in common_files:
            if current_file_hashes[file_path] != old_file_hashes[file_path]:
                changes['modified'].append(file_path)
            else:
                changes['unchanged'].append(file_path)
        
        # 保存新的Merkle树
        new_tree = CodeChangeTracker._build_merkle_tree(current_file_hashes)
        CodeChangeTracker.save_merkle_tree(project_root, new_tree, index_dir)
        
        return changes

    @staticmethod
    def _extract_file_hashes_from_tree(root: MerkleNode) -> Dict[str, str]:
        """从Merkle树中提取文件哈希"""
        # 这个应该是旧的记录
        file_hashes = {}
        
        def traverse(node: MerkleNode):
            if node.is_leaf and node.file_path:
                file_hashes[node.file_path] = node.hash
            if node.left:
                traverse(node.left)
            if node.right:
                traverse(node.right)
        
        if root:
            traverse(root)
        return file_hashes

    @staticmethod
    def _serialize_merkle_tree(root: Optional[MerkleNode]) -> Optional[Dict]:
        """序列化Merkle树为字典"""
        if not root:
            return None
        
        def serialize_node(node: MerkleNode) -> Dict:
            return {
                'hash': node.hash,
                'file_path': node.file_path,
                'is_leaf': node.is_leaf,
                'left': serialize_node(node.left) if node.left else None,
                'right': serialize_node(node.right) if node.right else None
            }
        
        return serialize_node(root)

    @staticmethod
    def _deserialize_merkle_tree(data: Optional[Dict]) -> Optional[MerkleNode]:
        """从字典反序列化Merkle树"""
        if not data:
            return None
        
        def deserialize_node(node_data: Dict) -> Optional[MerkleNode]:
            if not node_data:
                return None
            
            node = MerkleNode(
                hash=node_data['hash'],
                file_path=node_data['file_path'],
                is_leaf=node_data['is_leaf']
            )
            
            if node_data.get('left'):
                node.left = deserialize_node(node_data['left'])
            if node_data.get('right'):
                node.right = deserialize_node(node_data['right'])
            
            return node
        
        return deserialize_node(data)

    @staticmethod
    def _should_index_file(file_path: Path) -> bool:
        """判断是否应该索引文件"""
        ignore_patterns = ['__pycache__', '.pytest_cache', '.venv', 'env', 'venv', 'node_modules', '.git', '.idea', '.vscode']
        s = str(file_path)
        if any(p in s for p in ignore_patterns):
            return False
        # skip test files by naming
        if file_path.name.startswith('test_') or file_path.name.endswith('_test.py'):
            return False
        return True

    @staticmethod
    def update_file_hashes(project_root: str, file_paths: List[str], hashes: List[str], index_dir: str = ".code_index"):
        """更新文件哈希并重建Merkle树"""
        current_file_hashes = CodeChangeTracker._collect_file_hashes(project_root)
        for rel, h in zip(file_paths, hashes):
            current_file_hashes[rel] = h
        # 虽然这个字典只更新其中部分内容，但是重建树用的是一整个字典
        new_tree = CodeChangeTracker._build_merkle_tree(current_file_hashes)
        CodeChangeTracker.save_merkle_tree(project_root, new_tree, index_dir)

    @staticmethod
    def remove_file_hash(project_root: str, file_paths: List[str], index_dir: str = ".code_index"):
        """移除文件哈希并重建Merkle树"""
        current_file_hashes = CodeChangeTracker._collect_file_hashes(project_root)
        for rel in file_paths:
            current_file_hashes.pop(rel, None)
        new_tree = CodeChangeTracker._build_merkle_tree(current_file_hashes)
        CodeChangeTracker.save_merkle_tree(project_root, new_tree, index_dir)