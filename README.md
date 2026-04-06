# Bookworm

Your AI reading companion. Point Bookworm at any folder — Obsidian vault, research papers, book collection, work docs — and Claude Desktop will read, remember, and discuss everything in it.

Like NotebookLM, but local, open-source, and through Claude Desktop.

## How it works

Your documents (books, notes, articles, code, data) ↓ Index locally (free, no API costs) ↓ Claude Desktop reads it all via MCP ↓ Ask anything → get expert answers

Bookworm uses local embeddings (BGE-M3) and a local vector database (Qdrant) to index your documents. Claude Desktop connects to this index via MCP (Model Context Protocol) and uses it as memory — not as a search engine, but as knowledge it has "read."

## Supported formats

**Documents & notes:** .md, .txt, .pdf, .docx, .rtf

**Books:** .epub

**Data:** .csv, .tsv, .json

**Web:** .html, .htm

**Code & configs:** .py, .js, .ts, .yaml, .yml, .sh, .sql, .xml, .log

**Subtitles:** .vtt, .srt



## Quick Start

### Step 1. Clone and install

```bash
git clone https://github.com/vadimkasse/bookworm.git
cd bookworm
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The first run will download the embedding model (~2GB). This only happens once.

### Step 2. Point to your documents

Edit `config.yaml` and set the path to your folder:

```yaml
vault:
  path: "/Users/yourname/Documents/my-notes"
```

This can be any folder: an Obsidian vault, a folder with PDFs, a mix of books and notes — anything.

### Step 3. Check that everything is ready

```bash
python3 check_status.py
```

You should see all green checkmarks. If something is missing, the script will tell you what to fix.

### Step 4. Index your documents

```bash
python3 index.py
```

This scans your folder, extracts text from all supported files, splits it into chunks, and creates embeddings. Performance: ~1 minute per 1000 files on Apple Silicon. Cost: $0 (everything runs locally).

Indexing is incremental — when you add new files, just run `python3 index.py` again. Only new files will be processed.

### Step 5. Connect to Claude Desktop

Open Claude Desktop → click your profile icon (bottom-left) → Settings → Developer → Edit Config.

This opens `claude_desktop_config.json`. Add bookworm to `mcpServers`:

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

**Important:** Use full absolute paths. `~` and relative paths do not work.

Example for macOS:

```json
{
  "mcpServers": {
    "bookworm": {
      "command": "/Users/yourname/Projects/bookworm/venv/bin/python3",
      "args": ["/Users/yourname/Projects/bookworm/search_mcp.py"]
    }
  }
}
```

Save the file.

### Step 6. Restart Claude Desktop

Fully quit Claude Desktop (Cmd+Q on macOS, not just close the window) and reopen it.

### Step 7. Verify the connection

Open Claude Desktop → Settings → Developer. You should see bookworm with a green "running" status.

Then open a new chat, click the + button next to the message input, and look for bookworm in the tools list — it should be toggled on.

**Recommended model:** Use Claude Sonnet 4.6 or Opus for best results. Haiku may struggle with complex search strategies.

### Step 8. (Optional) Set up a system prompt

For the best experience, create a Project in Claude Desktop:

1. Open the sidebar → Projects → New Project
2. In project settings, paste the contents of `system_prompt.md` as the system prompt
3. Replace the placeholders (`{SOURCE_NAME}`, `{TOTAL_ITEMS}`, `{DOMAIN}`) with your values
4. Start chats inside this project

The system prompt makes Claude behave as an expert who has read your entire collection, rather than a search engine that returns results.



## Usage

Just talk to Claude naturally:

- "What do you know about typography in the collection?"
- "Find all mentions of Edward Tufte"
- "What's in the Books folder?"
- "Summarize the key ideas from design_principles.pdf"
- "How many documents are in the database?"
- "What books in my library discuss systems thinking?"

Claude picks the right search tool automatically — semantic search for topics, full-text search for specific names and phrases, and full document retrieval when needed.

## Tools

Bookworm gives Claude 5 tools to work with your knowledge base:

| Tool | What it does |
|------|-------------|
| `search` | Semantic search — finds relevant chunks by meaning |
| `fulltext` | Substring search — scans the entire database for exact matches |
| `get_note` | Retrieves the full text of a specific file |
| `list_notes` | Lists files in the knowledge base, with optional folder filter |
| `stats` | Shows database statistics: total chunks, files, folders |

## Updating your index

When you add new documents to your folder:

```bash
cd /path/to/bookworm
source venv/bin/activate
python3 index.py
```

Only new files are indexed — existing ones are skipped.

## Troubleshooting

**"bookworm" not showing in Claude Desktop tools:**

- Check Settings → Developer — is bookworm "running"?
- Verify paths in `claude_desktop_config.json` are absolute
- Fully restart Claude Desktop (Cmd+Q, not just close)
- Check MCP logs: `cat ~/Library/Logs/Claude/mcp*.log | tail -20`

**Claude doesn't use the tools:**

- Click + next to message input → make sure bookworm toggle is ON
- Try asking directly: "Use your search tools to find..."
- Switch to Sonnet or Opus (Haiku may not use tools effectively)

**Indexing is slow:**

- Normal speed: ~1 min per 1000 files on Apple Silicon
- First run downloads the model (~2GB) — subsequent runs are faster
- Use `python3 index.py --test` to index only 100 files for testing

## Stack

- Python 3.10+
- BGE-M3 — local multilingual embeddings
- Qdrant — local vector database
- MCP — Model Context Protocol
- Claude Desktop

## Project structure

```
bookworm/
├── config.yaml        — settings (paths, model, chunking)
├── parser.py          — text extraction from 20+ file formats
├── chunker.py         — smart chunking (headings → paragraphs → sliding window)
├── index.py           — indexing pipeline: parse → chunk → embed → store
├── search_mcp.py      — MCP server with 5 tools
├── check_status.py    — setup diagnostics
├── system_prompt.md   — Claude Desktop prompt template
├── requirements.txt   — dependencies
└── qdrant_data/       — vector database (created on first index)
```

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
