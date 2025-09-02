
# [中文](https://github.com/zishengwu/semantic-context-mcp/blob/main/README_zh.md)

# 🚀 Overview

**Semantic Context MCP Server** is a Model Context Protocol (MCP) server that leverages a vector database to efficiently index and perform semantic searches across your codebase.

It intelligently parses your code into structural blocks (like functions and classes), converts them into vector embeddings, and stores them in a local vector database. This allows you to find semantically relevant code snippets using natural language queries, rather than just keyword matching.

The server runs in the background, automatically tracking file changes and incrementally updating its index, ensuring your code context is always up-to-date.

# ✨ Features

- **Incremental Indexing**: Uses a Merkle Tree to detect file changes, ensuring only modified files are re-indexed, which is highly efficient.
- **Multi-Language Support**: Employs AST (Abstract Syntax Tree) parsing to support a wide range of languages, including Python, Java, C++, JavaScript, TypeScript, and Go.
- **Semantic Code Search**: Find code based on meaning and context, not just keywords.
- **Background Automation**: Automatically performs an initial full index and then runs periodic incremental updates every 5 minutes.
- **Simple MCP Interface**: Provides easy-to-use tools (`full_index`, `status`, `query`) for integration with other systems.
- **Local First**: All data (vector database, index metadata) is stored locally in your user home directory (`~/.chromadb`).

# 🛠️ How It Works

1.  **Detect Changes**: A Merkle Tree is built from file content hashes to quickly identify added, modified, or deleted files.
2.  **Parse Code**: Changed files are parsed using an AST parser to extract meaningful code blocks (functions, classes, etc.).
3.  **Generate Embeddings**: The extracted code blocks are converted into numerical representations (vector embeddings) using an embedding model (e.g., Jina, OpenAI).
4.  **Store in Vector DB**: These embeddings and associated metadata are stored in a local ChromaDB instance.
5.  **Query**: When a query is received, it's converted into an embedding and used to find the most similar code blocks in the vector database.

# 📂 Project Structure

```
.
├── vector_search/
│   ├── ast_parser.py          # Smart AST parser for multiple languages
│   ├── code_change_tracker.py # Detects file changes using a Merkle Tree
│   ├── code_indexer.py        # Main logic for incremental and full indexing
│   ├── fast_mcp_server.py     # The MCP server exposing the tools
│   └── vector_db.py           # Vector database manager (ChromaDB wrapper)
├── LICENSE
├── README_zh.md
└── README.md
```

# ⚙️ Prerequisites

- Python 3.8+
- An OpenAI-compatible API for generating embeddings. You need to set the following environment variables:
  ```bash
  export OPENAI_API_KEY="your_api_key"
  export OPENAI_BASE_URL="your_api_base_url"
  export OPENAI_MODEL_NAME="your_embedding_model_name"
  ```

# 📦 Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/zishengwu/semantic-context-mcp
    cd semantic-context-mcp
    ```

# 🚀 Usage

1.  config `MCP JSON file` in IDE:


```json
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

Enjoy it！👏
