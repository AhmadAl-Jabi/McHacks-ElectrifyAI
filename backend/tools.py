"""
Legacy tools module - kept for backward compatibility.
Core tools are now integrated in agent_runtime.py for better orchestration.
"""

def list_supported_blocks() -> list[str]:
    """Return circuit blocks that the agent can generate."""
    return ["rc_lowpass", "rc_highpass", "voltage_divider"]


def propose_rc_block(block_type: str, fc_hz: float, fixed_component: str, fixed_value: str) -> dict:
    """Return a proposed action payload for inserting an RC block (stub for now)."""
    return {
        "type": "INSERT_BLOCK",
        "payload": {
            "block_type": block_type,
            "fc_hz": fc_hz,
            "fixed_component": fixed_component,
            "fixed_value": fixed_value,
        },
    }
