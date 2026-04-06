"""
Universal text extraction from various file formats.
Supports: .md, .txt, .docx, .pdf, .csv, .tsv, .rtf, .epub, .html, .htm,
.json, .py, .js, .ts, .yaml, .yml, .log, .sh, .sql, .xml, .vtt, .srt
"""

import sys
import csv
import json
import re
from pathlib import Path
from typing import List


def extract_text(filepath: Path) -> str:
    """
    Extract text content from a file.

    Supports:
    - .md, .txt: read as UTF-8 text
    - .docx: extract paragraphs via python-docx
    - .pdf: extract text from all pages via PyMuPDF
    - .csv, .tsv: read rows as text
    - .rtf: strip RTF formatting

    Args:
        filepath: Path to file

    Returns:
        Extracted text as string. Empty string if format not supported.
    """
    filepath = Path(filepath)
    suffix = filepath.suffix.lower()

    try:
        if suffix in ['.md', '.txt']:
            return filepath.read_text(encoding='utf-8')

        elif suffix == '.epub':
            try:
                from ebooklib import epub
                from bs4 import BeautifulSoup
            except ImportError:
                print(f"Warning: ebooklib or beautifulsoup4 not installed, skipping {filepath.name}", file=sys.stderr)
                return ""

            try:
                book = epub.read_epub(filepath)
                chapters = []
                for item in book.get_items():
                    if item.get_type() == epub.ITEM_DOCUMENT:
                        content = item.get_content()
                        soup = BeautifulSoup(content, 'html.parser')
                        text = soup.get_text()
                        if text.strip():
                            chapters.append(text.strip())
                return '\n\n'.join(chapters)
            except Exception as e:
                print(f"Warning: Error reading {filepath.name}: {e}", file=sys.stderr)
                return ""

        elif suffix in ['.html', '.htm']:
            try:
                from bs4 import BeautifulSoup
            except ImportError:
                print(f"Warning: beautifulsoup4 not installed, skipping {filepath.name}", file=sys.stderr)
                return ""

            try:
                text = filepath.read_text(encoding='utf-8')
                soup = BeautifulSoup(text, 'html.parser')
                return soup.get_text(separator='\n')
            except Exception as e:
                print(f"Warning: Error reading {filepath.name}: {e}", file=sys.stderr)
                return ""

        elif suffix == '.json':
            try:
                text = filepath.read_text(encoding='utf-8')
                data = json.loads(text)
                if isinstance(data, str):
                    return data
                else:
                    return json.dumps(data, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Warning: Error reading {filepath.name}: {e}", file=sys.stderr)
                return ""

        elif suffix in ['.py', '.js', '.ts', '.yaml', '.yml', '.log', '.sh', '.sql', '.xml']:
            return filepath.read_text(encoding='utf-8')

        elif suffix == '.vtt':
            try:
                text = filepath.read_text(encoding='utf-8')
                # Remove WEBVTT header
                lines = text.split('\n')
                if lines and lines[0].strip() == 'WEBVTT':
                    lines = lines[1:]
                # Remove timecode lines (HH:MM:SS.mmm --> HH:MM:SS.mmm)
                pattern = r'\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}'
                filtered = [line for line in lines if not re.match(pattern, line.strip())]
                # Remove empty lines
                text = '\n'.join(filtered).strip()
                # Clean up multiple newlines
                text = re.sub(r'\n\s*\n', '\n', text)
                return text
            except Exception as e:
                print(f"Warning: Error reading {filepath.name}: {e}", file=sys.stderr)
                return ""

        elif suffix == '.srt':
            try:
                text = filepath.read_text(encoding='utf-8')
                lines = text.split('\n')
                # Remove sequence numbers (lines with only digits)
                # Remove timecode lines (HH:MM:SS,mmm --> HH:MM:SS,mmm)
                pattern = r'\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}'
                filtered = []
                for line in lines:
                    stripped = line.strip()
                    # Skip empty lines
                    if not stripped:
                        continue
                    # Skip sequence numbers (pure digits)
                    if stripped.isdigit():
                        continue
                    # Skip timecode lines
                    if re.match(pattern, stripped):
                        continue
                    filtered.append(line)
                text = '\n'.join(filtered).strip()
                # Clean up multiple newlines
                text = re.sub(r'\n\s*\n', '\n', text)
                return text
            except Exception as e:
                print(f"Warning: Error reading {filepath.name}: {e}", file=sys.stderr)
                return ""

        elif suffix == '.docx':
            try:
                from docx import Document
            except ImportError:
                print(f"Warning: python-docx not installed, skipping {filepath.name}", file=sys.stderr)
                return ""

            doc = Document(filepath)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return '\n\n'.join(paragraphs)

        elif suffix == '.pdf':
            try:
                import fitz  # PyMuPDF
            except ImportError:
                print(f"Warning: PyMuPDF not installed, skipping {filepath.name}", file=sys.stderr)
                return ""

            doc = fitz.open(filepath)
            text_parts = []
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
            return '\n\n'.join(text_parts)

        elif suffix in ['.csv', '.tsv']:
            delimiter = '\t' if suffix == '.tsv' else ','
            rows = []
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    for row in reader:
                        if row:
                            rows.append(' | '.join(str(cell).strip() for cell in row))
                return '\n'.join(rows)
            except Exception as e:
                print(f"Warning: Error reading {filepath.name}: {e}", file=sys.stderr)
                return ""

        elif suffix == '.rtf':
            try:
                from striprtf.rtf import rtf_to_text
            except ImportError:
                print(f"Warning: striprtf not installed, skipping {filepath.name}", file=sys.stderr)
                return ""

            try:
                text = filepath.read_text(encoding='utf-8')
                return rtf_to_text(text)
            except Exception as e:
                print(f"Warning: Error reading {filepath.name}: {e}", file=sys.stderr)
                return ""

        else:
            print(f"Warning: Unsupported format {suffix} for {filepath.name}", file=sys.stderr)
            return ""

    except Exception as e:
        print(f"Warning: Error reading {filepath.name}: {e}", file=sys.stderr)
        return ""


def list_supported_files(folder: Path) -> List[Path]:
    """
    Recursively find all files with supported formats in a folder.

    Supported formats:
    - Documents: .md, .txt, .docx, .pdf, .rtf
    - Books: .epub
    - Data: .csv, .tsv, .json
    - Web: .html, .htm
    - Code & configs: .py, .js, .ts, .yaml, .yml, .log, .sh, .sql, .xml
    - Subtitles: .vtt, .srt

    Args:
        folder: Root folder to scan

    Returns:
        List of Path objects, sorted by name
    """
    folder = Path(folder)
    supported = {'.md', '.txt', '.docx', '.pdf', '.csv', '.tsv', '.rtf',
                 '.epub', '.html', '.htm', '.json', '.py', '.js', '.ts',
                 '.yaml', '.yml', '.log', '.sh', '.sql', '.xml', '.vtt', '.srt'}

    files = []
    for f in folder.rglob('*'):
        if f.is_file() and f.suffix.lower() in supported:
            files.append(f)

    return sorted(files)


if __name__ == "__main__":
    # Test
    import sys
    test_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    files = list_supported_files(test_path)
    print(f"Found {len(files)} supported files")

    for f in files[:5]:
        text = extract_text(f)
        print(f"  {f.name}: {len(text)} chars")
