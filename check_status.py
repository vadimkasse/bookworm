#!/usr/bin/env python3
"""
Bookworm Setup Diagnostics
Checks that everything is configured and ready to work.
"""

import sys
from pathlib import Path


def check_python():
    """Check Python version >= 3.10."""
    v = sys.version_info
    print(f"Python: {v.major}.{v.minor}.{v.micro}", end="")
    if v >= (3, 10):
        print(" ✅")
        return True
    else:
        print(" ❌ (required: 3.10+)")
        return False


def check_packages():
    """Check required Python packages."""
    packages = {
        "sentence_transformers": "sentence-transformers",
        "qdrant_client": "qdrant-client",
        "yaml": "PyYAML",
        "tqdm": "tqdm",
        "mcp": "mcp",
        "docx": "python-docx",
        "fitz": "PyMuPDF",
        "striprtf": "striprtf",
        "ebooklib": "EbookLib",
        "bs4": "beautifulsoup4",
    }
    ok = True
    for module, pip_name in packages.items():
        try:
            __import__(module)
            print(f"  ✅ {pip_name}")
        except ImportError:
            print(f"  ❌ {pip_name}")
            ok = False
    if not ok:
        print(f"\n  Install: pip install -r requirements.txt")
    return ok


def check_config():
    """Check config.yaml exists and vault path is set."""
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        print(f"❌ config.yaml not found at {config_path}")
        return False

    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f)

    vault_path = Path(config.get("vault", {}).get("path", ""))
    placeholder = "/path/to/your/documents"

    if str(vault_path) == placeholder or not vault_path.exists():
        print(f"⚠️  Vault path not configured")
        print(f"   → Edit config.yaml and set 'vault.path' to your document folder")
        return False

    # Count supported files
    supported = {'.md', '.txt', '.docx', '.pdf', '.csv', '.tsv', '.rtf',
                 '.epub', '.html', '.htm', '.json', '.py', '.js', '.ts',
                 '.yaml', '.yml', '.log', '.sh', '.sql', '.xml', '.vtt', '.srt'}
    file_count = 0
    for f in vault_path.rglob('*'):
        if f.is_file() and f.suffix.lower() in supported:
            file_count += 1

    if file_count == 0:
        print(f"⚠️  Vault: {vault_path}")
        print(f"   → No supported files found")
        return False

    print(f"✅ Vault: {vault_path} ({file_count} files)")
    return True


def check_qdrant():
    """Check Qdrant database status."""
    try:
        from qdrant_client import QdrantClient
        import yaml

        config_path = Path(__file__).parent / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        qdrant_path = Path(__file__).parent / config["qdrant"]["path"]
        collection = config["qdrant"]["collection"]

        if not qdrant_path.exists():
            print(f"⚠️  Qdrant database not created yet")
            print(f"   → Run: python3 index.py")
            return False

        client = QdrantClient(path=str(qdrant_path))
        collections = [c.name for c in client.get_collections().collections]

        if collection not in collections:
            print(f"⚠️  Collection '{collection}' not found")
            print(f"   → Run: python3 index.py")
            return False

        count = client.count(collection_name=collection).count
        print(f"✅ Qdrant: {count} chunks indexed")
        return True

    except Exception as e:
        print(f"❌ Qdrant error: {e}")
        return False


def check_model():
    """Check embedding model is cached."""
    try:
        import yaml
        config_path = Path(__file__).parent / "config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        model_name = config["embedding"]["model"]

        # Check if model is cached
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        model_dir_name = "models--" + model_name.replace("/", "--")

        if (cache_dir / model_dir_name).exists():
            print(f"✅ Embedding model cached: {model_name}")
            return True
        else:
            print(f"⚠️  Embedding model not cached yet: {model_name}")
            print(f"   → Will download ~2GB on first indexing run")
            return True  # Not blocking

    except Exception as e:
        print(f"⚠️  Could not check embedding model: {e}")
        return True


def main():
    print("=" * 50)
    print("Bookworm — Setup Diagnostics")
    print("=" * 50)

    checks = [
        ("Python", check_python),
        ("Packages", check_packages),
        ("Config", check_config),
        ("Qdrant", check_qdrant),
        ("Embedding Model", check_model),
    ]

    all_ok = True
    for name, fn in checks:
        print(f"\n{name}:")
        if not fn():
            all_ok = False

    print(f"\n{'=' * 50}")
    if all_ok:
        print("✅ Everything ready!")
        print("\nStart the MCP server:")
        print("  python3 search_mcp.py")
    else:
        print("⚠️  Some issues found — fix and try again")
    print("=" * 50)


if __name__ == "__main__":
    main()
