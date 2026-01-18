"""
Test export_snapshot_json.ulp exists and has correct structure.

Note: Cannot actually run ULP outside Fusion, but can verify file structure.
"""
import sys
from pathlib import Path

# Get project root
project_root = Path(__file__).parent.parent
ulp_path = project_root / "fusion_addin" / "ulp" / "export_snapshot_json.ulp"


def test_ulp_file_exists():
    """Verify ULP file exists."""
    print("=" * 60)
    print("Test: ULP File Exists")
    print("=" * 60)
    
    assert ulp_path.exists(), f"ULP file not found: {ulp_path}"
    print(f"✓ ULP file exists: {ulp_path.name}")
    
    # Check file size
    size = ulp_path.stat().st_size
    assert size > 0, "ULP file is empty"
    print(f"✓ File size: {size} bytes")
    
    print()


def test_ulp_has_usage_header():
    """Verify ULP has proper usage header."""
    print("=" * 60)
    print("Test: ULP Usage Header")
    print("=" * 60)
    
    with open(ulp_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check for usage directive
    assert "#usage" in content, "Missing #usage directive"
    print("✓ Has #usage directive")
    
    # Check for header comment
    assert "export_snapshot_json.ulp" in content, "Missing file name in header"
    print("✓ Has file name in header")
    
    # Check for usage instructions
    assert "RUN" in content, "Missing RUN command example"
    print("✓ Has RUN command example")
    
    print()


def test_ulp_has_required_functions():
    """Verify ULP has required helper functions."""
    print("=" * 60)
    print("Test: ULP Required Functions")
    print("=" * 60)
    
    with open(ulp_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check for JSON escape function
    assert "escapeJson" in content, "Missing escapeJson function"
    print("✓ Has escapeJson function")
    
    # Check for timestamp function
    assert "getTimestamp" in content or "t2year" in content, "Missing timestamp generation"
    print("✓ Has timestamp generation")
    
    print()


def test_ulp_has_json_structure():
    """Verify ULP generates required JSON structure."""
    print("=" * 60)
    print("Test: ULP JSON Structure")
    print("=" * 60)
    
    with open(ulp_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check for required JSON keys (just check the word exists, not exact quoting)
    required_keys = [
        "components",
        "nets",
        "generated_at",
        "source",
        "refdes",
        "value",
        "placement",
        "net_name",
        "connections"
    ]
    
    for key in required_keys:
        assert key in content, f"Missing JSON key: {key}"
        print(f"✓ Has '{key}' key")
    
    print()


def test_ulp_has_schematic_context():
    """Verify ULP checks for schematic context."""
    print("=" * 60)
    print("Test: ULP Schematic Context")
    print("=" * 60)
    
    with open(ulp_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check for schematic context check
    assert "schematic" in content.lower(), "Missing schematic context"
    print("✓ Has schematic context check")
    
    # Check for parts iteration
    assert ".parts(" in content or "SH.parts" in content, "Missing parts iteration"
    print("✓ Has parts iteration")
    
    # Check for nets iteration
    assert ".nets(" in content or "SH.nets" in content, "Missing nets iteration"
    print("✓ Has nets iteration")
    
    print()


def test_ulp_has_argument_parsing():
    """Verify ULP parses output path argument."""
    print("=" * 60)
    print("Test: ULP Argument Parsing")
    print("=" * 60)
    
    with open(ulp_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check for argument parsing
    assert "argv[1]" in content, "Missing argv[1] argument parsing"
    print("✓ Parses argv[1] for output path")
    
    # Check for default path
    assert "bridge" in content.lower() or "outputPath" in content, "Missing default path logic"
    print("✓ Has default path logic")
    
    print()


def test_ulp_has_error_handling():
    """Verify ULP has error handling."""
    print("=" * 60)
    print("Test: ULP Error Handling")
    print("=" * 60)
    
    with open(ulp_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check for dialog messages
    assert "dlgMessageBox" in content, "Missing error/success dialogs"
    print("✓ Has dialog messages")
    
    # Check for error case
    assert "Error" in content or "error" in content, "Missing error handling"
    print("✓ Has error handling")
    
    print()


def test_integration_example():
    """Show example integration code."""
    print("=" * 60)
    print("Integration Example")
    print("=" * 60)
    
    example = f"""
# From Fusion Python Console:
from config_bridge import SNAPSHOT_PATH
from fusion_executor import test_ulp_execution

result = test_ulp_execution(
    "{ulp_path}",
    args=str(SNAPSHOT_PATH)
)

if result['success']:
    print("✓ Snapshot exported to bridge")
    
    # Backend can now read the snapshot
    import json
    with open(SNAPSHOT_PATH) as f:
        snapshot = json.load(f)
    
    print(f"Components: {{snapshot['component_count']}}")
    print(f"Nets: {{snapshot['net_count']}}")
"""
    
    print(example)


if __name__ == "__main__":
    try:
        test_ulp_file_exists()
        test_ulp_has_usage_header()
        test_ulp_has_required_functions()
        test_ulp_has_json_structure()
        test_ulp_has_schematic_context()
        test_ulp_has_argument_parsing()
        test_ulp_has_error_handling()
        test_integration_example()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print(f"\nULP ready: {ulp_path}")
        print("\nTo test in Fusion 360:")
        print("  1. Open a schematic")
        print("  2. Run: RUN \"<path-to-ulp>\" \"<output.json>\"")
        print("  3. Verify JSON output")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
