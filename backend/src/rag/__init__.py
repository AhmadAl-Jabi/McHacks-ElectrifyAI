"""
RAG (Retrieval-Augmented Generation) module for corpus ingestion and retrieval.

Submodules:
- config: Central configuration and env var handling
- ingest: PDF ingestion pipeline with Chroma vector store
"""

from .config import (
    RAG_CORPUS_DIR,
    RAG_INDEX_DIR,
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION,
)

__all__ = [
    "RAG_CORPUS_DIR",
    "RAG_INDEX_DIR",
    "CHROMA_PERSIST_DIR",
    "CHROMA_COLLECTION",
]
