"""
Action runner: executes scripts via Fusion Electronics command line.

Writes .scr files and runs them using the SCRIPT command.
"""
import os
import json
import tempfile
import time
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass
from .script_builder import build_script_file_content
from .action_types import validate_actions_structure


@dataclass
class ExecutionResult:
    """Result from script execution."""
    success: bool
    script_path: str
    warnings: List[str]
    errors: List[str]
    actions_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "script_path": self.script_path,
            "warnings": self.warnings,
            "errors": self.errors,
            "actions_count": self.actions_count
        }


def _execute_script_in_fusion(script_path: str) -> tuple[bool, List[str]]:
    """
    Execute .scr file in Fusion Electronics via SCRIPT command.
    
    This function should be called from within Fusion 360's Python environment
    where the 'adsk.core' and 'adsk.fusion' modules are available.
    
    Args:
        script_path: Absolute path to .scr file
        
    Returns:
        (success, errors) tuple
    """
    errors = []
    
    try:
        # Import Fusion 360 API (only available when running inside Fusion)
        import adsk.core
        import adsk.fusion
        
        app = adsk.core.Application.get()
        
        # Convert to forward slashes for EAGLE command
        script_path_escaped = script_path.replace("\\", "/")
        
        # Execute SCRIPT command via Electronics command line
        cmd = f'SCRIPT "{script_path_escaped}"'
        result = app.executeTextCommand(f'Electron.run "{cmd}"')
        
        # Check for errors in result
        if result:
            result_lower = result.lower()
            if any(err in result_lower for err in ["error", "failed", "cannot", "invalid"]):
                errors.append(f"Script execution error: {result}")
                return False, errors
        
        return True, []
        
    except ImportError:
        # Not running inside Fusion 360
        errors.append("Cannot execute: Not running inside Fusion 360 environment")
        return False, errors
    except Exception as e:
        errors.append(f"Script execution failed: {str(e)}")
        return False, errors


def _execute_ulp_in_fusion(ulp_path: str, args: str = None) -> tuple[bool, List[str]]:
    """
    Execute ULP (User Language Program) in Fusion Electronics via RUN command.
    
    ULPs are EAGLE-compatible automation scripts that can perform complex
    operations not easily achieved with simple command scripts.
    
    This function should be called from within Fusion 360's Python environment
    where the 'adsk.core' and 'adsk.fusion' modules are available.
    
    Args:
        ulp_path: Absolute path to .ulp file
        args: Optional arguments to pass to the ULP (space-separated string)
        
    Returns:
        (success, errors) tuple
        
    Examples:
        # Run ULP without arguments
        success, errors = _execute_ulp_in_fusion("/path/to/export.ulp")
        
        # Run ULP with arguments
        success, errors = _execute_ulp_in_fusion(
            "/path/to/export.ulp",
            args="output.txt format=json"
        )
    """
    errors = []
    
    try:
        # Import Fusion 360 API (only available when running inside Fusion)
        import adsk.core
        import adsk.fusion
        
        app = adsk.core.Application.get()
        
        # Convert to forward slashes for EAGLE command
        ulp_path_escaped = ulp_path.replace("\\", "/")
        
        # Build RUN command with optional arguments
        if args:
            cmd = f'RUN "{ulp_path_escaped}" {args}'
        else:
            cmd = f'RUN "{ulp_path_escaped}"'
        
        # Execute RUN command via Electronics command line
        result = app.executeTextCommand(f'Electron.run "{cmd}"')
        
        # Check for errors in result
        if result:
            result_lower = result.lower()
            if any(err in result_lower for err in ["error", "failed", "cannot", "invalid"]):
                errors.append(f"ULP execution error: {result}")
                return False, errors
        
        return True, []
        
    except ImportError:
        # Not running inside Fusion 360
        errors.append("Cannot execute: Not running inside Fusion 360 environment")
        return False, errors
    except Exception as e:
        errors.append(f"ULP execution failed: {str(e)}")
        return False, errors


def run_actions(
    actions_json_path: str,
    grid_unit: str = "MM",
    grid_size: float = 1.0,
    max_retries: int = 1
) -> ExecutionResult:
    """
    Load actions from JSON and execute them in Fusion Electronics.
    
    This is the single public function for the runner module.
    
    Process:
    1. Load actions from JSON file
    2. Generate .scr script using script_builder
    3. Write script to temp file with timestamp
    4. Execute script via Fusion Electronics SCRIPT command
    5. Retry once on transient failures
    
    Args:
        actions_json_path: Path to actions JSON file
        grid_unit: Grid unit - "MM" or "MIL" (default: MM)
        grid_size: Grid spacing size (default: 1.0)
        max_retries: Number of retries for transient failures (default: 1)
        
    Returns:
        ExecutionResult with success status, script path, warnings, and errors
        
    Raises:
        None - all errors are captured in ExecutionResult.errors
    """
    warnings: List[str] = []
    errors: List[str] = []
    script_path = ""
    actions_count = 0
    
    try:
        # Load actions JSON
        with open(actions_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Extract actions array
        if isinstance(data, dict) and "actions" in data:
            actions = data["actions"]
        elif isinstance(data, list):
            actions = data
        else:
            errors.append("Invalid JSON format: expected {actions: [...]} or [...]")
            return ExecutionResult(
                success=False,
                script_path="",
                warnings=warnings,
                errors=errors,
                actions_count=0
            )
        
        actions_count = len(actions)
        
        if actions_count == 0:
            warnings.append("No actions to execute")
            return ExecutionResult(
                success=True,
                script_path="",
                warnings=warnings,
                errors=[],
                actions_count=0
            )
        
        # Validate structure
        try:
            validate_actions_structure(actions)
        except Exception as e:
            errors.append(f"Action validation failed: {str(e)}")
            return ExecutionResult(
                success=False,
                script_path="",
                warnings=warnings,
                errors=errors,
                actions_count=actions_count
            )
        
        # Build script content
        script_content, script_warnings = build_script_file_content(
            actions,
            header_comment=f"Electrify Copilot - {actions_count} actions",
            grid_unit=grid_unit,
            grid_size=grid_size
        )
        
        warnings.extend(script_warnings)
        
        # Write to temp file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = tempfile.gettempdir()
        script_path = os.path.join(temp_dir, f"electrify_exec_{timestamp}.scr")
        
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        
        # Execute script with retry logic
        attempt = 0
        max_attempts = max_retries + 1
        last_errors = []
        
        while attempt < max_attempts:
            attempt += 1
            
            success, exec_errors = _execute_script_in_fusion(script_path)
            
            if success:
                return ExecutionResult(
                    success=True,
                    script_path=script_path,
                    warnings=warnings,
                    errors=[],
                    actions_count=actions_count
                )
            
            # Store errors from this attempt
            last_errors = exec_errors
            
            # Retry on transient failures
            if attempt < max_attempts:
                time.sleep(0.5)  # Brief delay before retry
        
        # All retries exhausted
        errors.extend(last_errors)
        errors.append(f"Execution failed after {attempt} attempts")
        
        return ExecutionResult(
            success=False,
            script_path=script_path,
            warnings=warnings,
            errors=errors,
            actions_count=actions_count
        )
        
    except FileNotFoundError:
        errors.append(f"Actions file not found: {actions_json_path}")
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {str(e)}")
    except Exception as e:
        errors.append(f"Unexpected error: {str(e)}")
    
    return ExecutionResult(
        success=False,
        script_path=script_path,
        warnings=warnings,
        errors=errors,
        actions_count=actions_count
    )


# -----------------------------------------------------------------------------
# Test Functions (for Fusion Console)
# -----------------------------------------------------------------------------
def test_ulp_execution(ulp_path: str, args: str = None) -> Dict[str, Any]:
    """
    Test ULP execution from Fusion Python console.
    
    This function can be called directly from Fusion 360's Python console
    to test ULP execution capabilities.
    
    Args:
        ulp_path: Absolute path to .ulp file to test
        args: Optional arguments to pass to the ULP
        
    Returns:
        dict with:
            - success: bool
            - ulp_path: str
            - args: str or None
            - errors: list[str]
            - message: str (human-readable summary)
            
    Example usage in Fusion Python console:
        >>> from fusion_executor.runner import test_ulp_execution
        >>> result = test_ulp_execution("C:/path/to/export.ulp")
        >>> print(result['message'])
        
        >>> # With arguments
        >>> result = test_ulp_execution(
        ...     "C:/path/to/export.ulp",
        ...     args="output.txt format=json"
        ... )
    """
    import os
    
    # Check if file exists
    if not os.path.exists(ulp_path):
        return {
            "success": False,
            "ulp_path": ulp_path,
            "args": args,
            "errors": [f"ULP file not found: {ulp_path}"],
            "message": f"✗ ULP file not found: {ulp_path}"
        }
    
    # Execute ULP
    success, errors = _execute_ulp_in_fusion(ulp_path, args)
    
    # Build result message
    if success:
        msg = f"✓ ULP executed successfully\n"
        msg += f"  Path: {ulp_path}\n"
        if args:
            msg += f"  Args: {args}\n"
    else:
        msg = f"✗ ULP execution failed\n"
        msg += f"  Path: {ulp_path}\n"
        if args:
            msg += f"  Args: {args}\n"
        msg += f"  Errors: {len(errors)}\n"
        for err in errors:
            msg += f"    • {err}\n"
    
    return {
        "success": success,
        "ulp_path": ulp_path,
        "args": args,
        "errors": errors,
        "message": msg
    }


def test_script_execution(script_path: str) -> Dict[str, Any]:
    """
    Test script execution from Fusion Python console.
    
    Companion function to test_ulp_execution for testing .scr files.
    
    Args:
        script_path: Absolute path to .scr file to test
        
    Returns:
        dict with:
            - success: bool
            - script_path: str
            - errors: list[str]
            - message: str (human-readable summary)
            
    Example usage in Fusion Python console:
        >>> from fusion_executor.runner import test_script_execution
        >>> result = test_script_execution("C:/Temp/test.scr")
        >>> print(result['message'])
    """
    import os
    
    # Check if file exists
    if not os.path.exists(script_path):
        return {
            "success": False,
            "script_path": script_path,
            "errors": [f"Script file not found: {script_path}"],
            "message": f"✗ Script file not found: {script_path}"
        }
    
    # Execute script
    success, errors = _execute_script_in_fusion(script_path)
    
    # Build result message
    if success:
        msg = f"✓ Script executed successfully\n"
        msg += f"  Path: {script_path}\n"
    else:
        msg = f"✗ Script execution failed\n"
        msg += f"  Path: {script_path}\n"
        msg += f"  Errors: {len(errors)}\n"
        for err in errors:
            msg += f"    • {err}\n"
    
    return {
        "success": success,
        "script_path": script_path,
        "errors": errors,
        "message": msg
    }
