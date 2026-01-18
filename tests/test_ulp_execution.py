"""
Test ULP execution implementation (outside Fusion).

This tests the structure and logic of ULP execution functions,
but cannot actually execute ULPs (requires Fusion environment).
"""
import sys
from pathlib import Path

# Add fusion_addin to path
fusion_path = Path(__file__).parent.parent / "fusion_addin"
sys.path.insert(0, str(fusion_path))

from fusion_executor.runner import test_ulp_execution, test_script_execution


def test_ulp_function_signature():
    """Verify ULP test function has correct signature."""
    print("=" * 60)
    print("Test: ULP Function Signature")
    print("=" * 60)
    
    # Check function exists
    assert callable(test_ulp_execution), "test_ulp_execution should be callable"
    print("✓ test_ulp_execution is callable")
    
    # Check it can be imported
    from fusion_executor import test_ulp_execution as imported_func
    assert imported_func == test_ulp_execution
    print("✓ test_ulp_execution can be imported from fusion_executor")
    
    # Test with non-existent file (should fail gracefully)
    result = test_ulp_execution("C:/nonexistent/test.ulp")
    
    assert isinstance(result, dict), "Result should be a dict"
    assert "success" in result
    assert "ulp_path" in result
    assert "args" in result
    assert "errors" in result
    assert "message" in result
    print("✓ Result has correct structure")
    
    assert result["success"] is False, "Should fail for non-existent file"
    assert len(result["errors"]) > 0, "Should have errors"
    assert "not found" in result["message"].lower()
    print("✓ Correctly handles non-existent file")
    
    print("\n✓ ULP function signature test passed!\n")


def test_ulp_with_args():
    """Test ULP function with arguments."""
    print("=" * 60)
    print("Test: ULP with Arguments")
    print("=" * 60)
    
    # Test with args parameter
    result = test_ulp_execution(
        "C:/nonexistent/test.ulp",
        args="output.txt format=json"
    )
    
    assert result["args"] == "output.txt format=json"
    print("✓ Arguments are stored in result")
    
    # Args won't appear in message if file not found
    # (only appears on execution attempt)
    print("✓ Arguments parameter accepted")
    
    print("\n✓ ULP arguments test passed!\n")


def test_script_function_signature():
    """Verify script test function has correct signature."""
    print("=" * 60)
    print("Test: Script Function Signature")
    print("=" * 60)
    
    # Check function exists
    assert callable(test_script_execution), "test_script_execution should be callable"
    print("✓ test_script_execution is callable")
    
    # Check it can be imported
    from fusion_executor import test_script_execution as imported_func
    assert imported_func == test_script_execution
    print("✓ test_script_execution can be imported from fusion_executor")
    
    # Test with non-existent file
    result = test_script_execution("C:/nonexistent/test.scr")
    
    assert isinstance(result, dict), "Result should be a dict"
    assert "success" in result
    assert "script_path" in result
    assert "errors" in result
    assert "message" in result
    print("✓ Result has correct structure")
    
    assert result["success"] is False
    assert len(result["errors"]) > 0
    assert "not found" in result["message"].lower()
    print("✓ Correctly handles non-existent file")
    
    print("\n✓ Script function signature test passed!\n")


def test_ulp_with_existing_file():
    """Test ULP function with existing file (won't execute outside Fusion)."""
    print("=" * 60)
    print("Test: ULP with Existing File")
    print("=" * 60)
    
    # Create a dummy ULP file
    test_ulp_path = fusion_path / "test_ulps" / "test_export.ulp"
    
    if test_ulp_path.exists():
        result = test_ulp_execution(str(test_ulp_path))
        
        # File exists, but execution will fail (not in Fusion)
        assert result["ulp_path"] == str(test_ulp_path)
        print(f"✓ ULP path stored: {test_ulp_path.name}")
        
        # Should fail with "Not running inside Fusion" error
        if not result["success"]:
            assert any("Fusion 360" in err for err in result["errors"])
            print("✓ Correctly reports not running in Fusion 360")
        
        print("\n✓ Existing file test passed!\n")
    else:
        print(f"⚠ Test ULP not found at: {test_ulp_path}")
        print("  (This is expected if test_export.ulp wasn't created)")


def test_exports():
    """Test that functions are properly exported."""
    print("=" * 60)
    print("Test: Module Exports")
    print("=" * 60)
    
    import fusion_executor
    
    # Check __all__ exports
    expected_exports = [
        "run_actions",
        "ExecutionResult",
        "test_ulp_execution",
        "test_script_execution"
    ]
    
    for export in expected_exports:
        assert hasattr(fusion_executor, export), f"{export} should be exported"
        print(f"✓ {export} is exported")
    
    print("\n✓ Module exports test passed!\n")


if __name__ == "__main__":
    try:
        test_ulp_function_signature()
        test_ulp_with_args()
        test_script_function_signature()
        test_ulp_with_existing_file()
        test_exports()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nNote: These tests verify structure and logic.")
        print("Actual ULP/script execution requires Fusion 360 environment.")
        print("\nTo test execution in Fusion Python console:")
        print("  >>> from fusion_executor import test_ulp_execution")
        print("  >>> result = test_ulp_execution('C:/path/to/test.ulp')")
        print("  >>> print(result['message'])")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
