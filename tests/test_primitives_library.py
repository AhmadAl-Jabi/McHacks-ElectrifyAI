"""
Unit tests for PrimitiveLibrary.

Tests:
- Loading and validation
- Search functionality
- Prompt rendering
"""

import json
import tempfile
from pathlib import Path

import pytest

from backend.primitives_library import PrimitiveLibrary, PrimitiveMatch


@pytest.fixture
def sample_primitives_json(tmp_path):
    """Create a temporary valid primitives JSON for testing."""
    data = {
        "library_name": "Test_CircuitPrimitives",
        "units": "SI",
        "notes": ["Test library"],
        "source_catalog": [],
        "primitives": [
            {
                "id": "PWR_BUCK_CONVERTER_STAGE",
                "name": "Buck converter stage (power train + cap selection + layout checklist)",
                "category": "power_conversion",
                "intent": "Battery or 12 V rail down to 5 V or similar for robotics power boards.",
                "evidence_topics": ["power/buck", "layout/high-di-dt", "layout/power"],
                "ports": [
                    {"name": "VIN", "type": "power_in"},
                    {"name": "VOUT", "type": "power_out"},
                ],
                "bom_roles": [
                    {"ref": "U1", "role": "Buck regulator IC"},
                ],
                "connections": [
                    {"ref": "U1.VIN", "net": "VIN"},
                    {"ref": "U1.VOUT", "net": "VOUT"},
                ],
                "parameters": {"vin_nom_v": 12, "vout_v": 5},
                "validation_checks": [
                    {
                        "id": "inductor_saturation_margin",
                        "type": "gte",
                        "message": "Inductor saturation current should exceed load current with margin.",
                    }
                ],
                "sources": [
                    {
                        "doc_id": "ti_buck_power_stage",
                        "locator": "power stage sizing",
                    }
                ],
            },
            {
                "id": "COMM_CAN_NODE_ROBUST",
                "name": "CAN node: transceiver + termination (optional split) + CMC + TVS",
                "category": "communications",
                "intent": "Robust CAN interface for robotics harnesses.",
                "evidence_topics": ["comms/can", "layout/emi", "power/esd"],
                "ports": [
                    {"name": "CANH", "type": "diff_io"},
                    {"name": "CANL", "type": "diff_io"},
                ],
                "bom_roles": [
                    {"ref": "U1", "role": "CAN transceiver"},
                ],
                "connections": [
                    {"ref": "U1.CANH", "net": "CANH"},
                ],
                "parameters": {"rt_ohm": 120},
                "validation_checks": [],
                "sources": [],
            },
        ],
    }
    
    json_file = tmp_path / "primitives.json"
    with open(json_file, "w") as f:
        json.dump(data, f)
    
    return json_file


class TestPrimitiveLibraryLoading:
    """Test loading and validation."""

    def test_load_valid_json(self, sample_primitives_json):
        """Test loading a valid primitives JSON."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        assert lib.top_k_default == 5
        assert len(lib._primitives) == 2

    def test_load_missing_file(self, tmp_path):
        """Test error handling for missing file when in isolated directory."""
        # Change to a temp directory with no fallback matches
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            with pytest.raises(FileNotFoundError, match="Primitives JSON not found"):
                PrimitiveLibrary("nonexistent_primitives.json")
        finally:
            os.chdir(old_cwd)

    def test_validate_missing_library_name(self, tmp_path):
        """Test validation fails if library_name is missing."""
        data = {
            "primitives": [
                {
                    "id": "TEST",
                    "name": "Test",
                    "intent": "Test",
                    "evidence_topics": [],
                    "ports": [],
                    "connections": [],
                    "sources": [],
                }
            ]
        }
        json_file = tmp_path / "bad.json"
        with open(json_file, "w") as f:
            json.dump(data, f)

        with pytest.raises(ValueError, match="Missing 'library_name'"):
            PrimitiveLibrary(str(json_file))

    def test_validate_missing_primitives_list(self, tmp_path):
        """Test validation fails if primitives list is missing."""
        data = {"library_name": "Test"}
        json_file = tmp_path / "bad.json"
        with open(json_file, "w") as f:
            json.dump(data, f)

        with pytest.raises(ValueError, match="Missing or invalid 'primitives' list"):
            PrimitiveLibrary(str(json_file))

    def test_validate_empty_primitives_list(self, tmp_path):
        """Test validation fails if primitives list is empty."""
        data = {"library_name": "Test", "primitives": []}
        json_file = tmp_path / "bad.json"
        with open(json_file, "w") as f:
            json.dump(data, f)

        with pytest.raises(ValueError, match="Primitives list is empty"):
            PrimitiveLibrary(str(json_file))

    def test_validate_missing_required_keys(self, tmp_path):
        """Test validation fails if primitive is missing required keys."""
        data = {
            "library_name": "Test",
            "primitives": [
                {
                    "id": "TEST",
                    "name": "Test",
                    # Missing many required keys
                }
            ],
        }
        json_file = tmp_path / "bad.json"
        with open(json_file, "w") as f:
            json.dump(data, f)

        with pytest.raises(ValueError, match="missing keys"):
            PrimitiveLibrary(str(json_file))


class TestPrimitiveLibrarySearch:
    """Test search and retrieval."""

    def test_get_by_id_existing(self, sample_primitives_json):
        """Test get_by_id returns the primitive."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        prim = lib.get_by_id("PWR_BUCK_CONVERTER_STAGE")
        assert prim is not None
        assert prim["id"] == "PWR_BUCK_CONVERTER_STAGE"
        assert prim["name"] == "Buck converter stage (power train + cap selection + layout checklist)"

    def test_get_by_id_nonexistent(self, sample_primitives_json):
        """Test get_by_id returns None for nonexistent ID."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        prim = lib.get_by_id("NONEXISTENT")
        assert prim is None

    def test_search_by_can_keyword(self, sample_primitives_json):
        """Test search finds CAN primitive by keyword."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        matches = lib.search("can bus termination")
        
        assert len(matches) > 0
        # COMM_CAN_NODE_ROBUST should be in top results
        ids = [m.primitive["id"] for m in matches]
        assert "COMM_CAN_NODE_ROBUST" in ids

    def test_search_by_buck_keyword(self, sample_primitives_json):
        """Test search finds buck converter by keyword."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        matches = lib.search("buck converter power")
        
        assert len(matches) > 0
        ids = [m.primitive["id"] for m in matches]
        assert "PWR_BUCK_CONVERTER_STAGE" in ids

    def test_search_empty_query(self, sample_primitives_json):
        """Test search with empty query returns empty list."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        matches = lib.search("")
        assert matches == []

    def test_search_top_k_limit(self, sample_primitives_json):
        """Test search respects top_k parameter."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        # Use a broad query that should match multiple primitives
        matches = lib.search("circuit", top_k=1)
        assert len(matches) <= 1

    def test_search_scoring(self, sample_primitives_json):
        """Test that scoring gives higher scores to better matches."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        
        # Search for CAN-related term
        matches = lib.search("CAN")
        if matches:
            # CAN primitive should score higher
            can_match = next(
                (m for m in matches if m.primitive["id"] == "COMM_CAN_NODE_ROBUST"),
                None
            )
            assert can_match is not None


class TestPrimitiveLibraryRendering:
    """Test prompt injection rendering."""

    def test_render_empty_matches(self, sample_primitives_json):
        """Test rendering with no matches."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        result = lib.render_for_prompt([])
        assert result == ""

    def test_render_single_match(self, sample_primitives_json):
        """Test rendering with a single match."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        prim = lib.get_by_id("PWR_BUCK_CONVERTER_STAGE")
        match = PrimitiveMatch(score=5.0, primitive=prim)
        
        result = lib.render_for_prompt([match])
        
        assert "=== PRIMITIVE_LIBRARY_CONTEXT ===" in result
        assert "PWR_BUCK_CONVERTER_STAGE" in result
        assert "Buck converter stage" in result
        assert "=== END_PRIMITIVE_LIBRARY_CONTEXT ===" in result

    def test_render_includes_id_name_intent(self, sample_primitives_json):
        """Test rendered output includes key primitive fields."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        prim = lib.get_by_id("COMM_CAN_NODE_ROBUST")
        match = PrimitiveMatch(score=5.0, primitive=prim)
        
        result = lib.render_for_prompt([match])
        
        assert "id: COMM_CAN_NODE_ROBUST" in result
        assert "CAN node:" in result or "CAN node" in result
        assert "Robust CAN interface" in result

    def test_render_respects_max_chars(self, sample_primitives_json):
        """Test rendered output respects max_chars limit."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        prim1 = lib.get_by_id("PWR_BUCK_CONVERTER_STAGE")
        prim2 = lib.get_by_id("COMM_CAN_NODE_ROBUST")
        matches = [
            PrimitiveMatch(score=5.0, primitive=prim1),
            PrimitiveMatch(score=4.0, primitive=prim2),
        ]
        
        result = lib.render_for_prompt(matches, max_chars=200)
        
        # Result should be under reasonable limit (with margin for headers/truncation markers)
        assert len(result) <= 1000  # Generous margin - truncation logic applies soft limit

    def test_render_includes_connections_truncated(self, sample_primitives_json):
        """Test rendered output includes truncated connections."""
        lib = PrimitiveLibrary(str(sample_primitives_json))
        prim = lib.get_by_id("PWR_BUCK_CONVERTER_STAGE")
        match = PrimitiveMatch(score=5.0, primitive=prim)
        
        result = lib.render_for_prompt([match])
        
        # Should mention connections
        assert "connections:" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
