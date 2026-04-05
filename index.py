#!/usr/bin/env python3
"""
Bookworm Indexer
Universal semantic search indexing via local embeddings (free, runs on CPU).
"""

import sys
import time
import argparse
from pathlib import Path

import yaml
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from parser import list_supported_files, extract_text
from chunker import chunk_file


def load_config(path: Path) -> dict:
    """Load YAML config file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_existing_ids(client: QdrantClient, collection: str) -> set:
    """
    Get all existing point IDs with proper pagination.
    Handles collections of any size.
    """
    existing = set()
    offset = None
    while True:
        results, next_offset = client.scroll(
            collection_name=collection,
            limit=1000,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        for point in results:
            existing.add(str(point.id))
        if next_offset is None:
            break
        offset = next_offset
    return existing


def index(config_path: Path = None, vault_override: str = None, test_mode: bool = False):
    """Main indexing function."""
    # Resolve config path
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    config_path = Path(config_path)

    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)

    config = load_config(config_path)

    vault_path = Path(vault_override or config["vault"]["path"])
    if not vault_path.exists():
        print(f"❌ Vault path does not exist: {vault_path}")
        print(f"   Edit config.yaml and set your document folder path")
        sys.exit(1)

    collection = config["qdrant"]["collection"]
    dimensions = config["embedding"]["dimensions"]
    batch_size = config["indexing"]["batch_size"]
    chunk_size = config["indexing"].get("chunk_size", 1500)
    overlap = config["indexing"].get("overlap", 150)

    # === Step 1: Find and chunk files ===
    print(f"\n📁 Scanning documents from {vault_path}")
    files = list_supported_files(vault_path)
    print(f"   Found {len(files)} supported files")

    if not files:
        print("❌ No supported files found. Check your vault path.")
        print(f"   Supported formats: .md, .txt, .docx, .pdf, .csv, .tsv, .rtf")
        sys.exit(1)

    # Chunk all files
    all_chunks = []
    print(f"\n✂️  Chunking documents...")
    for filepath in tqdm(files, desc="Chunking"):
        try:
            text = extract_text(filepath)
            chunks = chunk_file(filepath, vault_path, text, chunk_size=chunk_size, overlap=overlap)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"⚠️  Error processing {filepath.name}: {e}")

    print(f"   Created {len(all_chunks)} chunks from {len(files)} files")

    if not all_chunks:
        print("❌ No chunks created. Check your documents.")
        sys.exit(1)

    if test_mode:
        all_chunks = all_chunks[:100]
        print(f"   🧪 Test mode: using first {len(all_chunks)} chunks")

    # === Step 2: Load embedding model ===
    model_name = config["embedding"]["model"]
    print(f"\n🧠 Loading embedding model: {model_name}")
    print(f"   (first run downloads ~2GB, then cached locally)")
    model = SentenceTransformer(model_name, device="cpu")
    print(f"   ✅ Model loaded")

    # === Step 3: Initialize Qdrant ===
    qdrant_path = Path(__file__).parent / config["qdrant"]["path"]
    print(f"\n💾 Initializing Qdrant at {qdrant_path}")
    client = QdrantClient(path=str(qdrant_path))

    # Create collection if needed
    collections = [c.name for c in client.get_collections().collections]
    if collection not in collections:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=dimensions,
                distance=Distance.COSINE,
            ),
        )
        print(f"   ✅ Created collection '{collection}'")
    else:
        print(f"   ✅ Collection '{collection}' exists")

    # Check existing IDs for incremental indexing
    existing_ids = get_existing_ids(client, collection)
    print(f"   Already indexed: {len(existing_ids)} chunks")

    # Filter out already indexed chunks
    new_chunks = [c for c in all_chunks if c.id not in existing_ids]
    print(f"   New chunks to index: {len(new_chunks)}")

    if not new_chunks:
        print("\n✅ Everything is already indexed. Nothing to do.")
        return

    # === Step 4: Embed and upload ===
    print(f"\n🚀 Indexing {len(new_chunks)} chunks...")
    start_time = time.time()

    # Process in batches
    for batch_start in tqdm(range(0, len(new_chunks), batch_size), desc="Indexing"):
        batch = new_chunks[batch_start : batch_start + batch_size]

        # Get texts for embedding
        texts = [chunk.text for chunk in batch]

        # Compute embeddings (local, free)
        embeddings = model.encode(
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        # Create Qdrant points
        points = []
        for chunk, embedding in zip(batch, embeddings):
            points.append(PointStruct(
                id=chunk.id,
                vector=embedding.tolist(),
                payload={
                    "title": chunk.title,
                    "text": chunk.text,
                    "filename": chunk.filename,
                    "filepath": chunk.filepath,
                    "folder": chunk.folder,
                    "block_index": chunk.block_index,
                },
            ))

        # Upload batch
        client.upsert(collection_name=collection, points=points)

    elapsed = time.time() - start_time

    # === Summary ===
    total = client.count(collection_name=collection).count
    print(f"\n{'='*50}")
    print(f"✅ Done!")
    print(f"   Indexed: {len(new_chunks)} new chunks")
    print(f"   Total in DB: {total} chunks")
    print(f"   Time: {elapsed:.1f}s")
    print(f"   Cost: $0.00 (local embeddings)")
    print(f"{'='*50}")
    print(f"\nNext: start the MCP server")
    print(f"   python3 search_mcp.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bookworm Indexer")
    parser.add_argument("--vault", type=str, help="Override vault path from config")
    parser.add_argument("--config", type=str, default="config.yaml", help="Config file path")
    parser.add_argument("--test", action="store_true", help="Test mode: index only first 100 chunks")
    args = parser.parse_args()

    index(config_path=Path(args.config), vault_override=args.vault, test_mode=args.test)
