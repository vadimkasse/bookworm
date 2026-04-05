# Bookworm

Turn Claude Desktop into an expert on your documents.

Point Bookworm at any folder — Obsidian vault, research papers, book collection, work docs — and Claude will read, remember, and discuss everything in it. Like NotebookLM, but through Claude Desktop.

## How it works

```
Your documents (md, txt, pdf, docx, csv, rtf)
    ↓
Index (local embeddings, free)
    ↓
Search (semantic + full-text)
    ↓
Claude Desktop (MCP)
    ↓
Ask anything, get expert answers
```

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/yourusername/bookworm.git
cd bookworm
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

First run downloads the embedding model (~2GB).

### 2. Configure

Edit `config.yaml` — set the path to your document folder:

```yaml
vault:
  path: "/path/to/your/documents"
```

### 3. Check setup

```bash
python3 check_status.py
```

### 4. Index your documents

```bash
python3 index.py
```

This scans your folder, extracts text from all supported files, splits into chunks, and creates local embeddings. On Apple Silicon: ~1 minute per 1000 files. Cost: $0.

### 5. Connect to Claude Desktop

Open Claude Desktop settings → Edit Config (or edit the file directly):

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add to `mcpServers`:

```json
{
  "mcpServers": {
    "bookworm": {
      "command": "/full/path/to/bookworm/venv/bin/python3",
      "args": ["/full/path/to/bookworm/search_mcp.py"]
    }
  }
}
```

⚠️ Use absolute paths. `~` does not work.

### 6. Restart Claude Desktop

Close and reopen. You should see the 🔧 icon in a new chat — that's MCP.

### 7. (Optional) Set up the system prompt

Copy the template from `system_prompt.md` into your Claude Desktop project's system prompt. Replace the placeholders. This makes Claude behave as an expert rather than a search engine.

## Usage

Just talk to Claude:

- "What do you know about typography in the collection?"
- "Find all mentions of Edward Tufte"
- "What's in the Books folder?"
- "Summarize the key ideas from design_principles.pdf"
- "How many documents are in the database?"

Claude picks the right tool automatically.

## Tools

| Tool | What it does |
|------|-------------|
| `search` | Semantic search — finds relevant chunks by meaning |
| `fulltext` | Substring search — scans entire database, finds all matches |
| `get_note` | Full text of a specific file |
| `list_notes` | Browse files, filter by folder |
| `stats` | Database statistics |

## Supported formats

.md, .txt, .docx, .pdf, .csv, .tsv, .rtf

## Updating

When you add new documents to your folder:

```bash
cd /path/to/bookworm
source venv/bin/activate
python3 index.py
```

Indexing is incremental — only new files are processed.

## Stack

- Python 3.10+
- [BGE-M3](https://huggingface.co/BAAI/bge-m3) embeddings (local, multilingual)
- [Qdrant](https://qdrant.tech/) vector database (local, on disk)
- [MCP](https://modelcontextprotocol.io/) (Model Context Protocol)
- Claude Desktop

## Project structure

```
bookworm/
├── config.yaml        — settings (paths, model, chunking)
├── parser.py          — text extraction from 7 file formats
├── chunker.py         — smart chunking (by headings, separators, or sliding window)
├── index.py           — indexing: parse → chunk → embed → Qdrant
├── search_mcp.py      — MCP server (5 tools)
├── check_status.py    — setup diagnostics
├── system_prompt.md   — Claude Desktop prompt template
├── requirements.txt   — dependencies
└── qdrant_data/       — vector database (created on first index)
```

## License

MIT
