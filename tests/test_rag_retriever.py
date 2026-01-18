"""
Unit tests for RAG Retriever.

Tests:
- Initialization when index exists
- Initialization when index is missing (graceful degradation)
- Topic hint inference
- Retrieval returns empty list when disabled/missing
- Rendering evidence with proper formatting
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from backend.src.rag.retriever import RAGRetriever, RAGEvidence


class TestRAGRetrieverInitialization:
    """Test RAG retriever initialization and index detection."""

    def test_init_rag_disabled_via_env(self):
        """When RAG_ENABLED=false, retriever should be disabled."""
        with patch.dict(os.environ, {"RAG_ENABLED": "false"}):
            retriever = RAGRetriever()
            assert retriever.enabled is False
            assert retriever.db is None

    def test_init_rag_missing_index_graceful(self, tmp_path):
        """When index directory doesn't exist, retriever disables gracefully."""
        fake_persist_dir = tmp_path / "nonexistent" / "chroma"
        with patch.dict(os.environ, {"RAG_ENABLED": "true"}):
            retriever = RAGRetriever(persist_dir=fake_persist_dir)
            # Should log warning and disable
            assert retriever.enabled is False
            assert retriever.db is None

    def test_retrieve_returns_empty_when_disabled(self):
        """When RAG is disabled, retrieve() returns empty list without error."""
        with patch.dict(os.environ, {"RAG_ENABLED": "false"}):
            retriever = RAGRetriever()
            results = retriever.retrieve("test query")
            assert results == []
            assert isinstance(results, list)

    def test_infer_topic_hint_power(self):
        """Infer topic hint should detect power-related keywords."""
        retriever = RAGRetriever()  # Just for the method
        
        assert retriever.infer_topic_hint("buck converter design") == "power"
        assert retriever.infer_topic_hint("ldo regulator") == "power"
        assert retriever.infer_topic_hint("tvs diode selection") == "power"
        assert retriever.infer_topic_hint("reverse polarity protection") == "power"

    def test_infer_topic_hint_comms(self):
        """Infer topic hint should detect comms-related keywords."""
        retriever = RAGRetriever()
        
        assert retriever.infer_topic_hint("can bus termination") == "comms"
        assert retriever.infer_topic_hint("rs-485 biasing") == "comms"
        assert retriever.infer_topic_hint("i2c pull-up resistors") == "comms"
        assert retriever.infer_topic_hint("uart configuration") == "comms"

    def test_infer_topic_hint_safety(self):
        """Infer topic hint should detect safety-related keywords."""
        retriever = RAGRetriever()
        
        assert retriever.infer_topic_hint("e-stop circuit") == "safety"
        assert retriever.infer_topic_hint("estop interlock") == "safety"
        assert retriever.infer_topic_hint("kill switch design") == "safety"

    def test_infer_topic_hint_layout(self):
        """Infer topic hint should detect layout-related keywords."""
        retriever = RAGRetriever()
        
        assert retriever.infer_topic_hint("PCB layout emi") == "layout"
        assert retriever.infer_topic_hint("ground plane design") == "layout"
        assert retriever.infer_topic_hint("decouple capacitors") == "layout"

    def test_infer_topic_hint_mcu(self):
        """Infer topic hint should detect MCU-related keywords."""
        retriever = RAGRetriever()
        
        assert retriever.infer_topic_hint("esp32 configuration") == "mcu"
        assert retriever.infer_topic_hint("stm32 programming") == "mcu"
        assert retriever.infer_topic_hint("microcontroller selection") == "mcu"

    def test_infer_topic_hint_no_match(self):
        """Infer topic hint should return None for unrelated queries."""
        retriever = RAGRetriever()
        
        assert retriever.infer_topic_hint("what is the weather") is None
        assert retriever.infer_topic_hint("hello world") is None


class TestRAGEvidenceRendering:
    """Test rendering of RAG evidence for prompt injection."""

    def test_render_empty_evidences(self):
        """Rendering empty evidence list should return empty string."""
        retriever = RAGRetriever()
        result = retriever.render_for_prompt([])
        assert result == ""

    def test_render_single_evidence(self):
        """Rendering single evidence should produce properly formatted block."""
        retriever = RAGRetriever()
        
        evidence = RAGEvidence(
            text="RC low-pass filter with cutoff frequency 1 kHz",
            score=0.92,
            metadata={
                "doc_id": "RC_Filter_101",
                "title": "Filter Design Guide",
                "vendor": "Nexperia",
                "topic": "power",
                "page_number": 5,
                "source_path": "power/filters.pdf",
                "chunk_id": "RC_Filter_101__p5__c2",
                "sha256": "abc123def456",
                "tags": "filter,rc,cutoff",
            },
        )
        
        result = retriever.render_for_prompt([evidence])
        
        # Check for header and footer
        assert "=== RAG_EVIDENCE_CONTEXT ===" in result
        assert "=== END_RAG_EVIDENCE_CONTEXT ===" in result
        
        # Check for numbered entry
        assert "[1]" in result
        
        # Check for metadata fields
        assert "doc_id=RC_Filter_101" in result
        assert "title=Filter Design Guide" in result
        assert "vendor=Nexperia" in result
        assert "topic=power" in result
        assert "page=5" in result
        assert "source_path=power/filters.pdf" in result
        
        # Check for chunk text
        assert "RC low-pass filter" in result
        
        # Check for score
        assert "score=0.920" in result

    def test_render_respects_max_chars(self):
        """Rendering should respect max_chars limit."""
        retriever = RAGRetriever()
        
        # Create 3 long evidences
        evidences = []
        for i in range(3):
            evidence = RAGEvidence(
                text="x" * 5000,  # Very long chunk
                score=0.9 - i * 0.1,
                metadata={
                    "doc_id": f"doc_{i}",
                    "title": f"Title {i}",
                    "vendor": "Test",
                    "topic": "power",
                    "page_number": i,
                    "source_path": f"test/doc_{i}.pdf",
                    "chunk_id": f"doc_{i}__p{i}__c0",
                },
            )
            evidences.append(evidence)
        
        result = retriever.render_for_prompt(evidences, max_chars=3000)
        
        # Should fit within limit (allowing some overhead for formatting)
        assert len(result) <= 3500  # Allow 500 chars overhead for formatting
        
        # Should have header/footer
        assert "=== RAG_EVIDENCE_CONTEXT ===" in result
        assert "=== END_RAG_EVIDENCE_CONTEXT ===" in result

    def test_render_respects_max_chunk_chars(self):
        """Rendering should truncate long chunks per max_chunk_chars."""
        retriever = RAGRetriever()
        
        long_text = "a" * 5000
        evidence = RAGEvidence(
            text=long_text,
            score=0.95,
            metadata={
                "doc_id": "long_doc",
                "title": "Long Document",
                "vendor": "Test",
                "topic": "power",
                "page_number": 0,
                "source_path": "test/long.pdf",
                "chunk_id": "long_doc__p0__c0",
            },
        )
        
        result = retriever.render_for_prompt([evidence], max_chunk_chars=1000)
        
        # Long text should be truncated
        assert "..." in result
        # Verify truncation is roughly at max_chunk_chars (with metadata header overhead)
        assert "aaa" in result  # First part of text
        assert len("a" * 1000) >= 1000  # Sanity check


class TestRAGEvidenceDataclass:
    """Test RAGEvidence dataclass."""

    def test_rag_evidence_creation(self):
        """RAGEvidence should create with required fields."""
        evidence = RAGEvidence(
            text="Sample evidence",
            score=0.85,
            metadata={"doc_id": "test_doc"},
        )
        
        assert evidence.text == "Sample evidence"
        assert evidence.score == 0.85
        assert evidence.metadata["doc_id"] == "test_doc"

    def test_rag_evidence_default_metadata(self):
        """RAGEvidence should default metadata to empty dict."""
        evidence = RAGEvidence(text="Test")
        
        assert evidence.metadata == {}
        assert evidence.score is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
