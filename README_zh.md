
# 🚀 项目简介

**Semantic Context MCP Server** 是一个模型上下文协议（MCP）服务器，它利用向量数据库来高效地索引和查询您的代码库，以实现语义搜索。

它能智能地将您的代码解析为结构化块（如函数和类），将它们转换为向量嵌入，并存储在本地的向量数据库中。这使您可以使用自然语言查询来查找语义上相关的代码片段，而不仅仅是进行关键词匹配。

该服务器在后台运行，自动跟踪文件变更并增量更新其索引，确保您的代码上下文始终保持最新。

# ✨ 功能特性

- **增量索引**: 使用 Merkle 树来检测文件变更，确保只对修改过的文件进行重新索引，效率极高。
- **多语言支持**: 采用 AST（抽象语法树）解析，支持包括 Python、Java、C++、JavaScript、TypeScript 和 Go 在内的多种编程语言。
- **语义代码搜索**: 根据代码的含义和上下文进行搜索，而不仅仅是关键词。
- **后台自动化**: 自动执行初始全量索引，并每 5 分钟运行一次周期性的增量更新。
- **简洁的 MCP 接口**: 提供易于使用的工具（`full_index`, `status`, `query`），方便与其他系统集成。
- **本地优先**: 所有数据（向量数据库、索引元数据）都存储在您用户主目录下的本地文件夹中（`~/.chromadb`）。

# 🛠️ 工作原理

1.  **检测变更**: 通过文件内容的哈希值构建 Merkle 树，以快速识别新增、修改或删除的文件。
2.  **解析代码**: 使用 AST 解析器对变更的文件进行解析，提取出有意义的代码块（函数、类等）。
3.  **生成嵌入**: 使用嵌入模型（如 Jina、OpenAI）将提取的代码块转换为数值表示（向量嵌入）。
4.  **存入向量数据库**: 将这些嵌入及相关的元数据存储在本地的 ChromaDB 实例中。
5.  **执行查询**: 当收到查询时，服务器会将其转换为一个嵌入向量，并用它在向量数据库中查找最相似的代码块。

# 📂 项目结构

```
.
├── vector_search/
│   ├── ast_parser.py          # 支持多种语言的智能 AST 解析器
│   ├── code_change_tracker.py # 使用 Merkle 树检测文件变更
│   ├── code_indexer.py        # 增量和全量索引的核心逻辑
│   ├── fast_mcp_server.py     # 提供 MCP 工具的服务器
│   └── vector_db.py           # 向量数据库管理器 (ChromaDB 封装)
├── LICENSE
├── README_zh.md
└── README.md
```

# ⚙️ 环境要求

- Python 3.8+
- 一个兼容 OpenAI 的用于生成嵌入的 API。您需要设置以下环境变量：
  ```bash
  export OPENAI_API_KEY="你的_api_key"
  export OPENAI_BASE_URL="你的_api_base_url"
  export OPENAI_MODEL_NAME="你的_embedding_model_name"
  ```

# 📦 安装

1.  克隆仓库：
    ```bash
    git clone https://github.com/zishengwu/semantic-context-mcp
    cd semantic-context-mcp
    ```


# 🚀 使用方法

1.  在IDE中配置MCP JSON文件:
    ```bash
    {
  "mcpServers": {
    "Semantic Context MCP Server": {
      "command": "fastmcp",
      "args": [
        "run",
        "your_code_base/semantic-context-mcp/vector_search/fast_mcp_server.py:mcp"
      ],
      "env": {
        "OPENAI_API_KEY": "your_api_key",
        "OPENAI_BASE_URL": "your_api_base_url",
        "OPENAI_MODEL_NAME": "your_embedding_model_name"
      }
    }
  }
}
    ```

    开始使用吧！👏
