"""
RAG Configuration: Central settings for corpus ingestion and vector DB.

Reads environment variables and defines defaults. Paths are computed
relative to repo root for robustness.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file early
load_dotenv(override=True)


def resolve_repo_root() -> Path:
    """
    Resolve repository root by finding the 'backend' folder.
    
    Works when called from anywhere in the repo.
    """
    current = Path(__file__).resolve().parent
    while current != current.parent:  # Stop at filesystem root
        if (current / "backend").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find repo root (expected 'backend' folder)")


REPO_ROOT = resolve_repo_root()

# Default paths
RAG_CORPUS_DIR = Path(os.getenv("RAG_CORPUS_DIR", REPO_ROOT / "rag_corpus"))
RAG_INDEX_DIR = Path(os.getenv("RAG_INDEX_DIR", REPO_ROOT / "backend" / "rag_index"))
CHROMA_PERSIST_DIR = RAG_INDEX_DIR / "chroma"
INGEST_STATE_FILE = RAG_INDEX_DIR / "ingest_state.json"

# Chroma configuration
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "rag_corpus")

# Chunking configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))  # characters
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

# Topic folders (for metadata tagging)
TOPIC_FOLDERS = ["power", "comms", "safety", "layout", "components", "mcu"]

# Google embeddings
GOOGLE_EMBEDDING_MODEL = os.getenv(
    "GOOGLE_EMBEDDING_MODEL",
    "models/text-embedding-004",  # Fast, high quality
)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Logging
VERBOSE = os.getenv("VERBOSE", "false").lower() in ("true", "1", "yes")


def validate_config() -> None:
    """
    Validate that required config is present.
    
    Raises:
        RuntimeError: If GOOGLE_API_KEY is missing or corpus dir doesn't exist
    """
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY environment variable is not set. "
            "Please set it before running ingestion."
        )
    
    if not RAG_CORPUS_DIR.exists():
        raise RuntimeError(
            f"RAG corpus directory not found: {RAG_CORPUS_DIR}\n"
            f"Expected directory with PDFs. Please unpack rag_corpus/ first."
        )


if __name__ == "__main__":
    print(f"REPO_ROOT: {REPO_ROOT}")
    print(f"RAG_CORPUS_DIR: {RAG_CORPUS_DIR}")
    print(f"CHROMA_PERSIST_DIR: {CHROMA_PERSIST_DIR}")
    print(f"CHUNK_SIZE: {CHUNK_SIZE}")
    print(f"CHUNK_OVERLAP: {CHUNK_OVERLAP}")
    print(f"GOOGLE_EMBEDDING_MODEL: {GOOGLE_EMBEDDING_MODEL}")
