"""
Universal document chunking for semantic search indexing.
Splits documents into manageable blocks for embedding.
"""

import uuid
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from parser import extract_text, list_supported_files


# Namespace UUID for generating deterministic chunk IDs
NAMESPACE = uuid.UUID("b1c2d3e4-f5a6-7890-abcd-ef1234567890")


@dataclass
class Chunk:
    """A single searchable block from a document.

    Multiple blocks can come from a single file if the content is large.
    """
    id: str                      # Deterministic UUID5 from filename + block_index
    filename: str                # Original filename
    filepath: str                # Relative path from vault root (e.g., Books/design.pdf)
    block_index: int             # 0, 1, 2... within the file
    title: str                   # Block title (filename or heading for markdown)
    text: str                    # Text content for embedding
    folder: str                  # Folder path relative to vault root


def make_chunk_id(filename: str, block_index: int) -> str:
    """
    Create a deterministic UUID string from filename + block index.

    Args:
        filename: Original filename
        block_index: Block number within file

    Returns:
        Deterministic UUID string
    """
    key = f"{filename}::{block_index}"
    return str(uuid.uuid5(NAMESPACE, key))


def count_words(text: str) -> int:
    """Count words in text by splitting on whitespace."""
    return len(text.split())


def split_by_headings(text: str) -> List[tuple[str, str]]:
    """
    Split markdown text by H1 and H2 headings.

    Args:
        text: Markdown text

    Returns:
        List of (heading_text, section_content) tuples
    """
    sections = []
    current_heading = ""
    current_content = []

    lines = text.split('\n')
    for line in lines:
        # Match H1 or H2
        match = re.match(r'^(#+)\s+(.+)$', line)
        if match and match.group(1) in ['#', '##']:
            # Save previous section
            if current_heading or current_content:
                content = '\n'.join(current_content).strip()
                if content:
                    sections.append((current_heading, content))

            current_heading = match.group(2)
            current_content = []
        else:
            current_content.append(line)

    # Save last section
    if current_heading or current_content:
        content = '\n'.join(current_content).strip()
        if content:
            sections.append((current_heading, content))

    return sections


def sliding_window_chunks(text: str, window_size: int = 1000, overlap: int = 150) -> List[str]:
    """
    Split text using a sliding window approach.

    Args:
        text: Text to split
        window_size: Target words per chunk (~1000)
        overlap: Words to overlap between chunks (~150)

    Returns:
        List of text chunks
    """
    words = text.split()
    chunks = []

    step = window_size - overlap
    start = 0

    while start < len(words):
        end = min(start + window_size, len(words))
        chunk = ' '.join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start += step

    return chunks


def chunk_file(filepath: Path, vault_root: Path, text: str, chunk_size: int = 1500, overlap: int = 150) -> List[Chunk]:
    """
    Split a single file's text into chunks.

    Logic:
    - Empty file: no chunks
    - < chunk_size words: 1 chunk (whole file)
    - > chunk_size words, .md: split by H1/H2 headings, or by paragraphs if section too large
    - > chunk_size words, other: sliding window (chunk_size - overlap words per chunk)

    Args:
        filepath: Path to file
        vault_root: Root path of vault (for relative path calculation)
        text: Extracted text content
        chunk_size: Maximum words per chunk (default 1500)
        overlap: Word overlap for sliding window (default 150)

    Returns:
        List of Chunk objects
    """
    filepath = Path(filepath)
    vault_root = Path(vault_root)

    # Calculate relative paths
    try:
        rel_path = filepath.relative_to(vault_root)
    except ValueError:
        rel_path = filepath

    folder = str(rel_path.parent) if str(rel_path.parent) != '.' else '.'
    if folder == '.':
        folder = '.'
    filename = filepath.name

    # Empty file
    if not text or not text.strip():
        return []

    word_count = count_words(text)
    chunks = []

    # Small file: single chunk
    if word_count < chunk_size:
        chunk = Chunk(
            id=make_chunk_id(filename, 0),
            filename=filename,
            filepath=str(rel_path),
            block_index=0,
            title=filepath.stem,
            text=text.strip(),
            folder=folder,
        )
        chunks.append(chunk)
        return chunks

    # Large markdown: split by headings
    if filepath.suffix.lower() == '.md':
        sections = split_by_headings(text)

        block_index = 0
        for heading, content in sections:
            if not content.strip():
                continue

            section_words = count_words(content)

            # If section is small, keep as is
            if section_words < chunk_size:
                chunk = Chunk(
                    id=make_chunk_id(filename, block_index),
                    filename=filename,
                    filepath=str(rel_path),
                    block_index=block_index,
                    title=heading if heading else filepath.stem,
                    text=content.strip(),
                    folder=folder,
                )
                chunks.append(chunk)
                block_index += 1
            else:
                # Split large section by paragraphs or sliding window
                sub_chunks = sliding_window_chunks(content, window_size=chunk_size, overlap=overlap)
                for sub_text in sub_chunks:
                    chunk = Chunk(
                        id=make_chunk_id(filename, block_index),
                        filename=filename,
                        filepath=str(rel_path),
                        block_index=block_index,
                        title=f"{heading} (part {block_index})" if heading else f"{filepath.stem} (part {block_index})",
                        text=sub_text.strip(),
                        folder=folder,
                    )
                    chunks.append(chunk)
                    block_index += 1

        return chunks

    # Large non-markdown: sliding window
    else:
        sub_chunks = sliding_window_chunks(text, window_size=chunk_size, overlap=overlap)
        for block_index, sub_text in enumerate(sub_chunks):
            chunk = Chunk(
                id=make_chunk_id(filename, block_index),
                filename=filename,
                filepath=str(rel_path),
                block_index=block_index,
                title=f"{filepath.stem} (part {block_index + 1})",
                text=sub_text.strip(),
                folder=folder,
            )
            chunks.append(chunk)

        return chunks


def chunk_vault(vault_path: Path) -> List[Chunk]:
    """
    Process all supported files in a vault directory and return all chunks.

    Args:
        vault_path: Root path of vault

    Returns:
        List of all Chunk objects from all files
    """
    vault_path = Path(vault_path)
    all_chunks = []

    files = list_supported_files(vault_path)

    for filepath in files:
        try:
            text = extract_text(filepath)
            chunks = chunk_file(filepath, vault_path, text)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"Error processing {filepath.name}: {e}")

    return all_chunks


if __name__ == "__main__":
    # Test
    import sys
    vault_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    chunks = chunk_vault(vault_path)
    print(f"Total chunks: {len(chunks)}")

    for chunk in chunks[:5]:
        print(f"  [{chunk.block_index}] {chunk.title}: {len(chunk.text.split())} words")
