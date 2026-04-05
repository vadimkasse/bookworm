#!/usr/bin/env python3
"""
Bookworm MCP Server
Semantic search over any document collection via Claude Desktop.
Provides 5 tools: search, fulltext, get_note, list_notes, stats.
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional

import yaml
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio


# === Search Engine ===

class VaultSearch:
    """Search engine backed by local embeddings + Qdrant."""

    def __init__(self, config_path: Path = None):
        """Initialize with config file and connect to Qdrant."""
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        # Load embedding model
        print("Loading embedding model...", file=sys.stderr)
        model_name = self.config["embedding"]["model"]
        self.model = SentenceTransformer(model_name, device="cpu")
        print(f"✅ Model loaded: {model_name}", file=sys.stderr)

        # Connect to Qdrant
        qdrant_path = Path(__file__).parent / self.config["qdrant"]["path"]
        self.client = QdrantClient(path=str(qdrant_path))
        self.collection = self.config["qdrant"]["collection"]

        try:
            count = self.client.count(collection_name=self.collection).count
            print(f"✅ Qdrant connected: {count} chunks indexed", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  Qdrant collection not ready: {e}", file=sys.stderr)

    def embed_query(self, query: str) -> list:
        """Create embedding for a search query."""
        return self.model.encode(
            query,
            normalize_embeddings=True,
        ).tolist()

    def search(self, query: str, limit: int = 10, min_score: float = 0.3) -> List[Dict]:
        """
        Semantic search: finds chunks by meaning/similarity.

        Args:
            query: Search query string
            limit: Maximum results to return
            min_score: Minimum similarity score (0-1)

        Returns:
            List of dicts with title, text, filename, filepath, folder, score, block_index
        """
        try:
            query_vector = self.embed_query(query)

            results = self.client.query_points(
                collection_name=self.collection,
                query=query_vector,
                limit=limit,
                score_threshold=min_score,
            ).points

            return [
                {
                    "title": r.payload.get("title", ""),
                    "text": r.payload.get("text", ""),
                    "filename": r.payload.get("filename", ""),
                    "filepath": r.payload.get("filepath", ""),
                    "folder": r.payload.get("folder", ""),
                    "score": round(r.score, 3),
                    "block_index": r.payload.get("block_index", 0),
                }
                for r in results
            ]
        except Exception as e:
            print(f"Error in search: {e}", file=sys.stderr)
            return []

    def fulltext(self, keyword: str, search_in: str = "both", limit: int = 100) -> List[Dict]:
        """
        Full-text search: finds ALL mentions of a substring (case-insensitive).

        Args:
            keyword: Search substring
            search_in: "both" (title + text), "title", or "text"
            limit: Maximum results

        Returns:
            List of dicts with title, text, filename, filepath, folder, block_index
        """
        try:
            keyword_lower = keyword.lower()
            matches = []
            offset = None

            while len(matches) < limit:
                results, next_offset = self.client.scroll(
                    collection_name=self.collection,
                    limit=500,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                for p in results:
                    if len(matches) >= limit:
                        break

                    title = p.payload.get("title", "").lower()
                    text = p.payload.get("text", "").lower()
                    filename = p.payload.get("filename", "").lower()

                    found = False
                    if search_in in ["both", "title"] and keyword_lower in title:
                        found = True
                    if search_in in ["both", "text"] and keyword_lower in text:
                        found = True
                    if search_in in ["both"] and keyword_lower in filename:
                        found = True

                    if found:
                        matches.append({
                            "title": p.payload.get("title", ""),
                            "text": p.payload.get("text", ""),
                            "filename": p.payload.get("filename", ""),
                            "filepath": p.payload.get("filepath", ""),
                            "folder": p.payload.get("folder", ""),
                            "block_index": p.payload.get("block_index", 0),
                        })

                if next_offset is None:
                    break
                offset = next_offset

            # Sort by filename
            matches.sort(key=lambda x: x["filename"])
            return matches[:limit]

        except Exception as e:
            print(f"Error in fulltext: {e}", file=sys.stderr)
            return []

    def get_note(self, filename: str) -> Optional[Dict]:
        """
        Get the full text of a file by combining all its blocks.

        Args:
            filename: Name of file to retrieve

        Returns:
            Dict with filename, filepath, folder, blocks (count), text (combined)
        """
        try:
            search_filter = Filter(
                must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
            )

            chunks = []
            offset = None

            while True:
                results, next_offset = self.client.scroll(
                    collection_name=self.collection,
                    scroll_filter=search_filter,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                for p in results:
                    chunks.append({
                        "block_index": p.payload.get("block_index", 0),
                        "text": p.payload.get("text", ""),
                        "title": p.payload.get("title", ""),
                    })

                if next_offset is None:
                    break
                offset = next_offset

            if not chunks:
                return None

            # Sort by block_index
            chunks.sort(key=lambda x: x["block_index"])

            # Get metadata from first chunk
            first = chunks[0]
            # Use first result payload
            p = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=search_filter,
                limit=1,
                with_payload=True,
                with_vectors=False,
            )[0][0]

            combined_text = "\n\n---\n\n".join(c["text"] for c in chunks)

            return {
                "filename": filename,
                "filepath": p.payload.get("filepath", ""),
                "folder": p.payload.get("folder", ""),
                "blocks": len(chunks),
                "text": combined_text,
            }

        except Exception as e:
            print(f"Error in get_note: {e}", file=sys.stderr)
            return None

    def list_notes(self, folder: str = None, limit: int = 50) -> List[Dict]:
        """
        List unique files in the knowledge base.

        Args:
            folder: Optional folder filter (substring, case-insensitive)
            limit: Maximum files to return

        Returns:
            List of dicts with filename, filepath, folder
        """
        try:
            seen_files = {}  # filename -> (filepath, folder)
            offset = None

            while len(seen_files) < limit * 2:  # Overfetch to account for filtering
                results, next_offset = self.client.scroll(
                    collection_name=self.collection,
                    limit=500,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                for p in results:
                    filename = p.payload.get("filename", "")
                    filepath = p.payload.get("filepath", "")
                    file_folder = p.payload.get("folder", "")

                    if filename and filename not in seen_files:
                        # Filter by folder if specified
                        if folder:
                            if folder.lower() in file_folder.lower():
                                seen_files[filename] = (filepath, file_folder)
                        else:
                            seen_files[filename] = (filepath, file_folder)

                if next_offset is None:
                    break
                offset = next_offset

            # Convert to list and sort by filepath
            results_list = [
                {
                    "filename": filename,
                    "filepath": filepath,
                    "folder": file_folder,
                }
                for filename, (filepath, file_folder) in seen_files.items()
            ]
            results_list.sort(key=lambda x: x["filepath"])

            return results_list[:limit]

        except Exception as e:
            print(f"Error in list_notes: {e}", file=sys.stderr)
            return []

    def stats(self) -> Dict:
        """
        Get database statistics.

        Returns:
            Dict with total_chunks, unique_files, folders (list of first 20)
        """
        try:
            total_chunks = self.client.count(collection_name=self.collection).count

            # Count unique files and folders
            seen_files = set()
            seen_folders = set()
            offset = None
            MAX_FOLDERS = 20

            while True:
                results, next_offset = self.client.scroll(
                    collection_name=self.collection,
                    limit=500,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                for p in results:
                    filename = p.payload.get("filename", "")
                    folder = p.payload.get("folder", "")

                    if filename:
                        seen_files.add(filename)
                    if folder and len(seen_folders) < MAX_FOLDERS:
                        seen_folders.add(folder)

                if next_offset is None:
                    break
                offset = next_offset

            return {
                "total_chunks": total_chunks,
                "unique_files": len(seen_files),
                "folders": sorted(list(seen_folders))[:MAX_FOLDERS],
            }

        except Exception as e:
            print(f"Error in stats: {e}", file=sys.stderr)
            return {"total_chunks": 0, "unique_files": 0, "folders": []}


# === Result Formatting ===

def format_results(results: List[Dict], query: str = "", show_text: bool = True) -> str:
    """Format results for display (detailed format for ≤30 results)."""
    if not results:
        return "No results found."

    lines = []
    lines.append(f"Found {len(results)} result{'s' if len(results) != 1 else ''}{'':s}" + (f" for \"{query}\"" if query else ""))
    lines.append("")

    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', '(no title)')}")
        lines.append(f"   File: [[{Path(r.get('filename', '')).stem}]]")
        lines.append(f"   Folder: {r.get('folder', '.')}")

        if "score" in r:
            lines.append(f"   Relevance: {r['score']}")

        if show_text:
            text = r.get("text", "")
            preview = text[:300] + "..." if len(text) > 300 else text
            lines.append(f"   Preview: {preview}")

        lines.append("")

    return "\n".join(lines)


def format_results_compact(results: List[Dict]) -> str:
    """Format results for display (compact format for >30 results)."""
    if not results:
        return "No results found."

    lines = []
    lines.append(f"Found {len(results)} result{'s' if len(results) != 1 else ''}:")
    lines.append("")

    for i, r in enumerate(results, 1):
        folder = r.get("folder", ".")
        filename = r.get("filename", "")
        title = r.get("title", filename)
        lines.append(f"{i}. {title} — {folder}/{filename}")

    return "\n".join(lines)


# === MCP Server ===

server = Server("bookworm")
vault_search = None


@server.list_tools()
async def list_tools():
    """List all available search tools."""
    return [
        Tool(
            name="search",
            description="Semantic search across all indexed documents. Use when asked about a topic — returns the most relevant chunks by meaning.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (topic or question)"},
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="fulltext",
            description="Full-text substring search across the entire database. Case-insensitive. Use for finding ALL mentions of a specific word, name, or phrase.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Substring to search for"},
                    "search_in": {"type": "string", "description": "Search in: 'both', 'title', or 'text' (default 'both')", "default": "both"},
                    "limit": {"type": "integer", "description": "Max results (default 100)", "default": 100},
                },
                "required": ["keyword"],
            },
        ),
        Tool(
            name="get_note",
            description="Get the full text of a specific file by filename. Use when you found an interesting chunk and want to read the whole document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename to retrieve"},
                },
                "required": ["filename"],
            },
        ),
        Tool(
            name="list_notes",
            description="List files in the knowledge base, optionally filtered by folder. Use to explore what's available.",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Optional folder filter (substring)"},
                    "limit": {"type": "integer", "description": "Max files (default 50)", "default": 50},
                },
            },
        ),
        Tool(
            name="stats",
            description="Database statistics: total chunks, unique files, folder structure.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Execute a tool."""
    global vault_search
    if vault_search is None:
        vault_search = VaultSearch()

    if name == "search":
        query = arguments.get("query", "")
        limit = arguments.get("limit", 10)
        results = vault_search.search(query, limit=limit)
        formatted = format_results(results, query=query, show_text=len(results) <= 30)
        return [TextContent(type="text", text=formatted)]

    elif name == "fulltext":
        keyword = arguments.get("keyword", "")
        search_in = arguments.get("search_in", "both")
        limit = arguments.get("limit", 100)
        results = vault_search.fulltext(keyword, search_in=search_in, limit=limit)
        if len(results) > 30:
            formatted = format_results_compact(results)
        else:
            formatted = format_results(results, query=keyword, show_text=True)
        return [TextContent(type="text", text=formatted)]

    elif name == "get_note":
        filename = arguments.get("filename", "")
        result = vault_search.get_note(filename)
        if result:
            text = f"File: {result['filename']}\nFolder: {result['folder']}\nBlocks: {result['blocks']}\n\n{result['text']}"
            return [TextContent(type="text", text=text)]
        else:
            return [TextContent(type="text", text=f"File not found: {filename}")]

    elif name == "list_notes":
        folder = arguments.get("folder")
        limit = arguments.get("limit", 50)
        results = vault_search.list_notes(folder=folder, limit=limit)
        if not results:
            return [TextContent(type="text", text="No files found.")]
        lines = [f"Found {len(results)} file{'s' if len(results) != 1 else ''}:"]
        for r in results:
            lines.append(f"  • {r['filepath']} ({r['folder']})")
        return [TextContent(type="text", text="\n".join(lines))]

    elif name == "stats":
        result = vault_search.stats()
        text = f"""Database Statistics:
  Total chunks: {result['total_chunks']}
  Unique files: {result['unique_files']}
  Folders: {', '.join(result['folders']) if result['folders'] else '(none)'}"""
        return [TextContent(type="text", text=text)]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
