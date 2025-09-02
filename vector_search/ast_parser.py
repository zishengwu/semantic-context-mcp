import ast
from pathlib import Path
from typing import List, Dict, Optional
from tree_sitter_languages import get_parser


class SmartASTParser:
    """智能AST解析器，支持 Python / Java / C++ / JavaScript / TypeScript / Go 等语言"""

    @staticmethod
    def extract_code_blocks(file_path: Path) -> List[Dict]:
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"读取文件失败 {file_path}: {e}")
            return []

        language = SmartASTParser._guess_language(file_path)

        if language == "python":
            print(f"python 语言")
            return SmartASTParser._extract_python(file_path, content)
        else:
            # return []
            print(f"其他语言： {language}")
            return SmartASTParser._extract_other(file_path, content, language)

    # ---------------- 文件后缀 → 语言映射 ---------------- #
    @staticmethod
    def _guess_language(file_path: Path) -> str:
        ext_map = {
            ".py": "python",
            ".java": "java",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".c": "c",
            ".js": "javascript",
            ".jsx": "javascript",
            ".mjs": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
        }
        return ext_map.get(file_path.suffix.lower(), "python")  # 默认当作 Python

    # ---------------- Python AST 解析 ---------------- #
    @staticmethod
    def _extract_python(file_path: Path, content: str) -> List[Dict]:
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            print(f"语法错误在文件 {file_path}: {e}")
            return []

        blocks: List[Dict] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                block_info = SmartASTParser._parse_python_node(node, content, file_path)
                blocks.append(block_info)
        return blocks

    @staticmethod
    def _parse_python_node(node, content: str, file_path: Path) -> Dict:
        block_type = "unknown"
        if isinstance(node, ast.FunctionDef):
            block_type = "function"
        elif isinstance(node, ast.AsyncFunctionDef):
            block_type = "async_function"
        elif isinstance(node, ast.ClassDef):
            block_type = "class"

        block_code = ast.get_source_segment(content, node) or ""
        
        # 生成唯一ID，包含行号和列号避免重复
        line_num = getattr(node, 'lineno', 0)
        col_num = getattr(node, 'col_offset', 0)
        name = getattr(node, 'name', '<anon>')
        
        return {
            "id": f"{file_path.as_posix()}:{name}:{line_num}:{col_num}",
            "type": block_type,
            "name": name,
            "code": block_code,
            "file_path": str(file_path),
            "line_number": line_num,
            "end_line_number": getattr(node, "end_lineno", None),
            "signature": SmartASTParser._get_signature(node)
        }

    @staticmethod
    def _get_signature(node) -> str:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [arg.arg for arg in node.args.args]
            return f"{getattr(node, 'name', '<anon>')}({', '.join(args)})"
        return getattr(node, "name", "")

    # ---------------- 其他语言解析 ---------------- #
    @staticmethod
    def _extract_other(file_path: Path, content: str, language: str) -> List[Dict]:
        try:
            parser = get_parser(language)
            if parser is None:
                print(f"不支持的语言: {language} ({file_path})")
                return []
        except Exception as e:
            print(f"加载 parser 失败 {language} ({file_path}): {e}")
            return []

        try:
            tree = parser.parse(bytes(content, "utf8"))
        except Exception as e:
            print(f"解析失败 {file_path} ({language}): {e}")
            return []

        root = tree.root_node
        blocks: List[Dict] = []
        SmartASTParser._walk(root, content, file_path, blocks, language)
        return blocks

    @staticmethod
    def _walk(node, content: str, file_path: Path, blocks: List[Dict], language: str):
        node_type = node.type

        # 定义不同语言的 函数/类 节点
        lang_nodes = {
            "java": ["class_declaration", "method_declaration"],
            "cpp": ["function_definition", "class_specifier"],
            "c": ["function_definition"],
            "javascript": ["function_declaration", "class_declaration", "method_definition"],
            "typescript": ["function_declaration", "class_declaration", "method_definition"],
            "go": ["function_declaration", "method_declaration", "type_declaration"],  # type 可代表 struct
        }

        if language in lang_nodes and node_type in lang_nodes[language]:
            blocks.append(SmartASTParser._parse_other_node(node, content, file_path))

        for child in node.children:
            SmartASTParser._walk(child, content, file_path, blocks, language)

    @staticmethod
    def _parse_other_node(node, content: str, file_path: Path) -> Dict:
        start_line, end_line = node.start_point[0] + 1, node.end_point[0] + 1
        start_col = node.start_point[1]
        code_segment = content[node.start_byte:node.end_byte]

        # 生成唯一ID，包含行列信息
        name = SmartASTParser._extract_name(node, content) or node.type
        
        return {
            "id": f"{file_path}:{name}:{start_line}:{start_col}",
            "type": node.type,
            "name": name,
            "code": code_segment,
            "file_path": str(file_path),
            "line_number": start_line,
            "end_line_number": end_line,
            "signature": name
        }

    @staticmethod
    def _extract_name(node, content: str) -> Optional[str]:
        """提取函数/类名（依赖 identifier 节点）"""
        for child in node.children:
            if child.type == "identifier":
                return content[child.start_byte:child.end_byte]
        return None

