"""
RAG Retrieval: Query embeddings, search Chroma, and format evidence for prompts.

Handles:
- Opening persisted Chroma vector store
- Embedding user queries with OpenAI embeddings
- Similarity search with optional topic filtering
- Rendering evidence as structured context blocks for LLM
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

from .config import (
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION,
    GOOGLE_EMBEDDING_MODEL,
    GOOGLE_API_KEY,
)

logger = logging.getLogger(__name__)


@dataclass
class RAGEvidence:
    """A single piece of evidence retrieved from the RAG index."""
    text: str
    score: Optional[float] = None
    metadata: Optional[dict] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RAGRetriever:
    """
    Retriever for RAG-augmented prompting.
    
    - Opens persisted Chroma store
    - Embeds queries and retrieves similar chunks
    - Formats evidence for injection into system prompts
    - Supports topic-based filtering (power, comms, safety, layout, components, mcu)
    """

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        collection_name: Optional[str] = None,
    ):
        """
        Initialize the RAG retriever.
        
        Args:
            persist_dir: Path to Chroma persistence directory. Defaults to config.
            collection_name: Chroma collection name. Defaults to config.
        """
        self.persist_dir = persist_dir or CHROMA_PERSIST_DIR
        self.collection_name = collection_name or CHROMA_COLLECTION
        self.enabled = True
        self.db = None

        # Check if RAG is enabled via env var
        rag_enabled_str = os.getenv("RAG_ENABLED", "true").lower()
        rag_enabled = rag_enabled_str in ("true", "1", "yes")

        if not rag_enabled:
            logger.info("RAG disabled via RAG_ENABLED=false")
            self.enabled = False
            return

        # Check if index exists
        if not self.persist_dir.exists():
            logger.warning(
                f"RAG index not found at {self.persist_dir}. "
                "Run ingestion first: python -m backend.src.rag.ingest"
            )
            self.enabled = False
            return

        # Initialize embeddings
        try:
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model=GOOGLE_EMBEDDING_MODEL,
                google_api_key=GOOGLE_API_KEY,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Google embeddings: {e}")
            self.enabled = False
            return

        # Open Chroma store
        try:
            self.db = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=str(self.persist_dir),
            )
            logger.info(
                f"RAG retriever initialized. "
                f"Collection: {self.collection_name}, "
                f"Persist dir: {self.persist_dir}"
            )
        except Exception as e:
            logger.error(f"Failed to open Chroma collection: {e}")
            self.enabled = False
            self.db = None

    def infer_topic_hint(self, query: str) -> Optional[str]:
        """
        Infer topic hint from query keywords.
        
        Simple heuristic routing:
        - power: "buck", "ldo", "efuse", "tvs", "reverse polarity", "power"
        - comms: "can", "canbus", "rs-485", "rs485", "i2c", "uart"
        - safety: "e-stop", "estop", "interlock", "contactor", "kill switch"
        - layout: "layout", "emi", "ground", "decouple", "di/dt"
        - mcu: "esp32", "stm32", "mcu", "microcontroller"
        
        Args:
            query: User's query string
            
        Returns:
            Topic name or None if no match
        """
        query_lower = query.lower()

        # Power domain keywords
        if any(kw in query_lower for kw in ["buck", "ldo", "efuse", "tvs", "reverse polarity", "power"]):
            return "power"

        # Communications keywords
        if any(kw in query_lower for kw in ["can", "canbus", "rs-485", "rs485", "i2c", "uart"]):
            return "comms"

        # Safety keywords
        if any(kw in query_lower for kw in ["e-stop", "estop", "interlock", "contactor", "kill switch"]):
            return "safety"

        # Layout/EMI keywords
        if any(kw in query_lower for kw in ["layout", "emi", "ground", "decouple", "di/dt"]):
            return "layout"

        # MCU keywords
        if any(kw in query_lower for kw in ["esp32", "stm32", "mcu", "microcontroller"]):
            return "mcu"

        return None

    def retrieve(
        self,
        query: str,
        top_k: int = 6,
        topic: Optional[str] = None,
        use_topic_hint: bool = True,
        relevance_threshold: float = 0.30,
    ) -> list[RAGEvidence]:
        """
        Retrieve top-K relevant chunks for a query, filtered by relevance threshold.
        
        Args:
            query: User query string
            top_k: Number of results to return
            topic: Optional topic filter ("power", "comms", "safety", "layout", "components", "mcu")
            use_topic_hint: If True, auto-detect topic from query keywords
            relevance_threshold: Minimum similarity score (0.0-1.0). Chunks below this are ignored.
            
        Returns:
            List of RAGEvidence objects with text, score, and metadata (may be empty if below threshold)
        """
        if not self.enabled or self.db is None:
            return []

        # Determine effective topic
        effective_topic = None
        if topic:
            effective_topic = topic
        elif use_topic_hint:
            effective_topic = self.infer_topic_hint(query)

        debug_mode = os.getenv("RAG_DEBUG", "false").lower() in ("true", "1", "yes")

        try:
            # Perform similarity search with scores
            # Chroma returns (Document, L2_distance) pairs where:
            # - L2 distance 0 = identical (best match)
            # - L2 distance ~2 = opposite (worst match)
            # We convert to normalized similarity score: similarity = 1 / (1 + distance)
            # This gives us a 0-1 range where 1 = best, 0 = worst
            results = self.db.similarity_search_with_score(
                query,
                k=top_k * 3,  # Retrieve extra results if we're filtering by topic
            )

            # Build evidence list with threshold filtering
            evidences = []
            top_scores = []  # Track top scores for debug logging
            
            for doc, distance in results:
                # Convert L2 distance to similarity score (0-1 range)
                # Formula: similarity = 1 / (1 + distance)
                # This maps: distance 0 -> similarity 1, distance ∞ -> similarity 0
                similarity_score = 1 / (1 + distance)
                
                # Track top 3 scores for logging
                if len(top_scores) < 3:
                    metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                    top_scores.append({
                        'score': similarity_score,
                        'distance': distance,
                        'doc_id': metadata.get('doc_id', 'unknown'),
                        'topic': metadata.get('topic', 'N/A'),
                        'page': metadata.get('page_number', 0),
                    })
                
                # Apply relevance threshold (on similarity score, 0-1 range)
                if similarity_score < relevance_threshold:
                    continue

                metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                text = doc.page_content if hasattr(doc, 'page_content') else str(doc)

                # Filter by topic if specified
                if effective_topic:
                    doc_topic = metadata.get('topic', '')
                    if doc_topic != effective_topic:
                        continue

                evidence = RAGEvidence(
                    text=text,
                    score=similarity_score,  # Store normalized similarity (0-1)
                    metadata=metadata,
                )
                evidences.append(evidence)

                # Stop when we have enough
                if len(evidences) >= top_k:
                    break

            # Debug logging
            if debug_mode:
                logger.info(f"[RAG] Query: {query[:80]}")
                logger.info(f"[RAG] Top scores (threshold={relevance_threshold}):")
                for score_info in top_scores:
                    logger.info(
                        f"      score={score_info['score']:.3f} | "
                        f"doc_id={score_info['doc_id']} | "
                        f"topic={score_info['topic']} | "
                        f"page={score_info['page']}"
                    )
                logger.info(f"[RAG] Returned {len(evidences)} evidence chunks (threshold-filtered)")

            return evidences[:top_k]

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []

    def render_for_prompt(
        self,
        evidences: list[RAGEvidence],
        max_chars: int = 10000,
        max_chunk_chars: int = 1400,
    ) -> str:
        """
        Format retrieved evidence as a structured context block for LLM injection.
        Always returns a block (even if empty) to signal to LLM that RAG was attempted.
        
        Args:
            evidences: List of RAGEvidence objects
            max_chars: Maximum total characters for the entire context block
            max_chunk_chars: Maximum characters per chunk text
            
        Returns:
            Formatted string with === RAG_EVIDENCE_CONTEXT === header/footer.
            Returns empty block if no evidences.
        """
        lines = ["=== RAG_EVIDENCE_CONTEXT ==="]
        
        if not evidences:
            lines.append("(empty)")
            lines.append("=== END_RAG_EVIDENCE_CONTEXT ===")
            return "\n".join(lines)

        current_chars = len(lines[0]) + 1  # Account for newline

        for idx, evidence in enumerate(evidences, start=1):
            # Build metadata line
            metadata = evidence.metadata or {}
            doc_id = metadata.get('doc_id', 'unknown')
            title = metadata.get('title', 'untitled')
            vendor = metadata.get('vendor', '')
            topic = metadata.get('topic', '')
            page = metadata.get('page_number', 0)
            source_path = metadata.get('source_path', '')
            chunk_id = metadata.get('chunk_id', '')
            score = evidence.score

            # Format score with precision
            score_str = f"{score:.3f}" if score is not None else "N/A"

            meta_line = (
                f"[{idx}] doc_id={doc_id}, title={title}, vendor={vendor}, "
                f"topic={topic}, page={page}, source_path={source_path}, "
                f"chunk_id={chunk_id}, score={score_str}"
            )

            # Truncate chunk text to max_chunk_chars
            chunk_text = evidence.text[:max_chunk_chars]
            if len(evidence.text) > max_chunk_chars:
                chunk_text += "..."

            # Check if adding this evidence would exceed max_chars
            entry_size = len(meta_line) + len(chunk_text) + 5  # +5 for newlines/spacing
            if current_chars + entry_size > max_chars:
                # Stop adding more evidence
                break

            lines.append(meta_line)
            lines.append(chunk_text)
            lines.append("")  # Blank line between entries
            current_chars += entry_size

        lines.append("=== END_RAG_EVIDENCE_CONTEXT ===")

        return "\n".join(lines)
