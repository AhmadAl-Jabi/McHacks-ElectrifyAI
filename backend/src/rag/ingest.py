"""
RAG Corpus Ingestion: Load PDFs, chunk, embed, and store in Chroma.

CLI Usage:
    python -m backend.src.rag.ingest
    python backend/src/rag/ingest.py --rebuild --limit 1 --verbose

Ingests PDFs from rag_corpus/, tracks doc state via SHA256, and skips
re-embedding unchanged documents on subsequent runs.
"""

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

from .config import (
    REPO_ROOT,
    RAG_CORPUS_DIR,
    CHROMA_PERSIST_DIR,
    INGEST_STATE_FILE,
    CHROMA_COLLECTION,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    TOPIC_FOLDERS,
    GOOGLE_EMBEDDING_MODEL,
    GOOGLE_API_KEY,
    validate_config,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[RAG] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_manifest(manifest_path: Path) -> dict:
    """
    Load rag_corpus/_manifest.json if present.
    
    Returns a dict keyed by filename or relative path with fields:
    {doc_id, title, vendor, tags, source_url, sha256, ...}
    """
    if not manifest_path.exists():
        logger.warning(f"No manifest found at {manifest_path}. Using defaults.")
        return {}
    
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        logger.info(f"Loaded manifest with {len(manifest)} entries")
        return manifest
    except Exception as e:
        logger.warning(f"Failed to load manifest: {e}. Continuing without it.")
        return {}


def load_ingest_state(state_file: Path) -> dict:
    """Load previously ingested docs state {doc_id -> {sha256, num_chunks, timestamp}}."""
    if not state_file.exists():
        return {}
    
    try:
        with open(state_file) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load ingest state: {e}. Starting fresh.")
        return {}


def save_ingest_state(state: dict, state_file: Path) -> None:
    """Save ingestion state for change tracking."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def get_topic_from_path(pdf_path: Path) -> str:
    """Extract topic folder name from PDF path."""
    for folder in TOPIC_FOLDERS:
        if f"/{folder}/" in str(pdf_path).replace("\\", "/"):
            return folder
    return "general"


def discover_pdfs(corpus_dir: Path, limit: int | None = None) -> list[Path]:
    """
    Discover all PDFs under corpus_dir.
    
    Args:
        corpus_dir: Root of rag_corpus
        limit: Max number of PDFs (for testing)
        
    Returns:
        List of Path objects to PDFs
    """
    pdfs = list(corpus_dir.rglob("*.pdf"))
    pdfs.sort()
    
    if limit:
        pdfs = pdfs[:limit]
    
    logger.info(f"Found {len(pdfs)} PDF(s)")
    return pdfs


def load_and_chunk_pdfs(
    pdf_paths: list[Path],
    manifest: dict,
    state: dict,
    corpus_dir: Path,
) -> tuple[list[Any], dict]:
    """
    Load PDFs, split into chunks, and return documents + updated state.
    
    Skips documents that haven't changed (by SHA256).
    
    Returns:
        (documents, updated_state) where documents are LangChain Document objects
    """
    documents = []
    updated_state = dict(state)  # Copy existing state
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    
    pages_loaded = 0
    chunks_created = 0
    docs_skipped = 0
    
    for pdf_path in pdf_paths:
        relative_path = pdf_path.relative_to(corpus_dir)
        doc_id = relative_path.stem  # filename without .pdf
        
        # Compute SHA256
        sha256 = compute_file_sha256(pdf_path)
        
        # Check if already ingested and unchanged
        if doc_id in updated_state and updated_state[doc_id].get("sha256") == sha256:
            logger.debug(f"Skipping unchanged doc: {doc_id}")
            docs_skipped += 1
            continue
        
        # Load PDF
        logger.info(f"Loading: {relative_path}")
        try:
            loader = PyPDFLoader(str(pdf_path))
            pdf_docs = loader.load()
        except Exception as e:
            logger.error(f"Failed to load {pdf_path}: {e}")
            continue
        
        pages_loaded += len(pdf_docs)
        
        # Gather metadata from manifest if available
        manifest_entry = manifest.get(doc_id, {})
        title = manifest_entry.get("title", doc_id)
        vendor = manifest_entry.get("vendor", "")
        tags = ",".join(manifest_entry.get("tags", []))  # Convert list to string
        
        topic = get_topic_from_path(pdf_path)
        
        # Process each page
        chunk_index = 0
        doc_chunks = 0
        
        for page_doc in pdf_docs:
            page_num = page_doc.metadata.get("page", 0)
            
            # Split page into chunks
            page_chunks = splitter.split_text(page_doc.page_content)
            
            for chunk_text in page_chunks:
                chunk_id = f"{doc_id}__p{page_num}__c{chunk_index}"
                
                chunk_doc = type(page_doc)(
                    page_content=chunk_text,
                    metadata={
                        "source_path": str(relative_path),
                        "doc_id": doc_id,
                        "title": title,
                        "vendor": vendor,
                        "tags": tags,
                        "topic": topic,
                        "page_number": page_num,
                        "chunk_index": chunk_index,
                        "chunk_id": chunk_id,
                        "sha256": sha256,
                    },
                )
                documents.append(chunk_doc)
                chunk_index += 1
                doc_chunks += 1
                chunks_created += 1
        
        # Update state for this doc
        updated_state[doc_id] = {
            "sha256": sha256,
            "num_chunks": doc_chunks,
            "file_path": str(relative_path),
        }
        
        logger.debug(f"  Created {doc_chunks} chunks from {len(pdf_docs)} pages")
    
    logger.info(
        f"Processed {len(pdf_paths)} PDFs: "
        f"{pages_loaded} pages, {chunks_created} chunks, {docs_skipped} skipped"
    )
    
    return documents, updated_state


def ingest(
    corpus_dir: Path | None = None,
    persist_dir: Path | None = None,
    rebuild: bool = False,
    limit: int | None = None,
) -> None:
    """
    Main ingestion workflow.
    
    Args:
        corpus_dir: Override corpus directory
        persist_dir: Override Chroma persist directory
        rebuild: Delete existing collection and rebuild from scratch
        limit: Max PDFs to process (for testing)
    """
    # Validate environment
    validate_config()
    
    corpus_dir = corpus_dir or RAG_CORPUS_DIR
    persist_dir = persist_dir or CHROMA_PERSIST_DIR
    
    logger.info(f"RAG Ingestion starting")
    logger.info(f"Corpus: {corpus_dir}")
    logger.info(f"Index: {persist_dir}")
    
    # Load manifest
    manifest_path = corpus_dir / "_manifest.json"
    manifest = load_manifest(manifest_path)
    
    # Discover PDFs
    pdf_paths = discover_pdfs(corpus_dir, limit=limit)
    
    if not pdf_paths:
        logger.error(f"No PDFs found in {corpus_dir}")
        return
    
    # Load state
    state = load_ingest_state(INGEST_STATE_FILE)
    
    # Handle rebuild
    if rebuild:
        logger.warning("Rebuild requested: deleting existing collection")
        if persist_dir.exists():
            import shutil
            shutil.rmtree(persist_dir)
        if INGEST_STATE_FILE.exists():
            INGEST_STATE_FILE.unlink()
        state = {}
    
    # Load and chunk PDFs
    documents, updated_state = load_and_chunk_pdfs(
        pdf_paths, manifest, state, corpus_dir
    )
    
    if not documents:
        logger.error("No documents to ingest")
        return
    
    # Initialize embeddings
    logger.info(f"Initializing Google embeddings: {GOOGLE_EMBEDDING_MODEL}")
    embeddings = GoogleGenerativeAIEmbeddings(
        model=GOOGLE_EMBEDDING_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )
    
    # Store in Chroma
    logger.info(f"Storing {len(documents)} chunks in Chroma...")
    vector_store = Chroma.from_documents(
        documents,
        embeddings,
        collection_name=CHROMA_COLLECTION,
        persist_directory=str(persist_dir),
    )
    
    # Save state
    save_ingest_state(updated_state, INGEST_STATE_FILE)
    
    logger.info(f"✓ Ingestion complete")
    logger.info(f"  Total chunks stored: {len(documents)}")
    logger.info(f"  Index persisted at: {persist_dir}")
    logger.info(f"  State file: {INGEST_STATE_FILE}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest rag_corpus PDFs into Chroma vector store"
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        help="Override corpus directory",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Override output/persist directory",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete existing collection and rebuild from scratch",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of PDFs to process (for testing)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        ingest(
            corpus_dir=args.corpus,
            persist_dir=args.out,
            rebuild=args.rebuild,
            limit=args.limit,
        )
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
