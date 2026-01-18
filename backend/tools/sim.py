"""
Simulation and math tools for circuit analysis.
Provides ngspice AC sweep execution with math fallback and bode plot generation.
"""

import os
import subprocess
import tempfile
import math
from pathlib import Path
from typing import Tuple
import numpy as np
import matplotlib.pyplot as plt


def compute_rc_values(fc_hz: float, fixed_component: str, fixed_value: str) -> Tuple[float, float]:
    """
    Calculate R and C values for an RC circuit given cutoff frequency.
    
    Args:
        fc_hz: Cutoff frequency in Hz
        fixed_component: "R" or "C" - which component is fixed
        fixed_value: Value of fixed component (e.g., "10nF", "20k", "1M")
    
    Returns:
        (R_ohm, C_farad): Tuple of resistance and capacitance values
    
    Raises:
        ValueError: If parameters are invalid
    """
    # Parse fixed_value (handle units: k, M, n, u, p, etc.)
    multipliers = {
        'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3,
        'k': 1e3, 'M': 1e6, 'G': 1e9
    }
    
    value_str = str(fixed_value).strip().upper()
    numeric_part = ""
    unit_part = ""
    
    for i, char in enumerate(value_str):
        if char.isdigit() or char == '.':
            numeric_part += char
        else:
            unit_part = value_str[i:]
            break
    
    try:
        numeric_val = float(numeric_part)
    except ValueError:
        raise ValueError(f"Cannot parse numeric value from '{fixed_value}'")
    
    # Apply multiplier
    multiplier = 1.0
    if unit_part:
        unit_char = unit_part[0].lower()
        if unit_char in multipliers:
            multiplier = multipliers[unit_char]
        else:
            raise ValueError(f"Unknown unit in '{fixed_value}'")
    
    fixed_value_base = numeric_val * multiplier
    
    # RC low-pass cutoff: fc = 1 / (2 * pi * R * C)
    # So: R * C = 1 / (2 * pi * fc)
    rc_product = 1.0 / (2.0 * math.pi * fc_hz)
    
    fixed_component = fixed_component.upper().strip()
    
    if fixed_component == 'C':
        C_farad = fixed_value_base
        R_ohm = rc_product / C_farad
    elif fixed_component == 'R':
        R_ohm = fixed_value_base
        C_farad = rc_product / R_ohm
    else:
        raise ValueError(f"fixed_component must be 'R' or 'C', got '{fixed_component}'")
    
    return R_ohm, C_farad


def run_ngspice_ac(netlist_text: str, workdir: str = None, R_ohm: float = None, C_farad: float = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Run AC sweep in ngspice and extract frequency, magnitude, phase.
    Falls back to analytic RC transfer function if ngspice fails.
    
    Args:
        netlist_text: SPICE netlist as string
        workdir: Working directory for simulation (temp if None)
        R_ohm: Optional resistance for fallback calculation (extracted from netlist if not provided)
        C_farad: Optional capacitance for fallback calculation (extracted from netlist if not provided)
    
    Returns:
        (freqs, mag_db, phase_deg): Numpy arrays of frequency, magnitude in dB, phase in degrees
    """
    
    if workdir is None:
        workdir = tempfile.mkdtemp(prefix="ngspice_")
    
    os.makedirs(workdir, exist_ok=True)
    
    # Save netlist to file
    netlist_path = os.path.join(workdir, "circuit.cir")
    output_log = os.path.join(workdir, "output.log")
    
    with open(netlist_path, 'w') as f:
        f.write(netlist_text)
    
    # Try to run ngspice
    try:
        result = subprocess.run(
            ['ngspice', '-b', '-o', output_log, netlist_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and os.path.exists(output_log):
            # Attempt to parse output
            freqs, mag_db, phase_deg = _parse_ngspice_output(output_log)
            if freqs is not None:
                return freqs, mag_db, phase_deg
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    except Exception as e:
        print(f"ngspice error: {e}")
    
    # Fallback: analytic RC transfer function
    print("ngspice unavailable or failed; using analytic RC transfer function")
    
    # Extract R and C from netlist if not provided
    if R_ohm is None or C_farad is None:
        R_ohm, C_farad = _extract_rc_from_netlist(netlist_text, R_ohm, C_farad)
    
    return _analytic_rc_bode(R_ohm, C_farad)


def _parse_ngspice_output(log_path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Parse ngspice AC sweep output from log file.
    Looks for frequency, magnitude, and phase columns.
    
    Returns:
        (freqs, mag_db, phase_deg) or (None, None, None) if parsing fails
    """
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
        
        # Look for data section (typically starts with Index or frequency header)
        freqs = []
        mag = []
        phase = []
        
        in_data = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for markers or data lines
            if 'Index' in line or 'frequency' in line.lower():
                in_data = True
                continue
            
            if in_data:
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        # Assuming format: Index freq mag phase (or similar)
                        freq = float(parts[1]) if len(parts) > 1 else None
                        magnitude = float(parts[2]) if len(parts) > 2 else None
                        phase_val = float(parts[3]) if len(parts) > 3 else None
                        
                        if freq and magnitude is not None:
                            freqs.append(freq)
                            mag.append(magnitude)
                            if phase_val is not None:
                                phase.append(phase_val)
                    except (ValueError, IndexError):
                        continue
        
        if freqs:
            freqs = np.array(freqs)
            mag_db = np.array(mag)
            phase_deg = np.array(phase) if phase else np.zeros_like(mag_db)
            return freqs, mag_db, phase_deg
    
    except Exception as e:
        print(f"Failed to parse ngspice output: {e}")
    
    return None, None, None


def _extract_rc_from_netlist(netlist_text: str, R_ohm: float = None, C_farad: float = None) -> Tuple[float, float]:
    """
    Extract R and C values from SPICE netlist.
    Looks for lines like "R1 node1 node2 15915.5" and "C1 node 0 1e-08"
    
    Returns:
        (R_ohm, C_farad): Extracted or default values
    """
    import re
    
    # Default fallback values
    if R_ohm is None:
        R_ohm = 1000.0
    if C_farad is None:
        C_farad = 100e-9
    
    try:
        lines = netlist_text.split('\n')
        for line in lines:
            # Look for resistor definition: R<name> <nodes> <value>
            r_match = re.search(r'^\s*R\d*\s+\S+\s+\S+\s+([\d.eE+-]+)\s*$', line, re.IGNORECASE)
            if r_match:
                R_ohm = float(r_match.group(1))
            
            # Look for capacitor definition: C<name> <nodes> <value>
            c_match = re.search(r'^\s*C\d*\s+\S+\s+\S+\s+([\d.eE+-]+)\s*$', line, re.IGNORECASE)
            if c_match:
                C_farad = float(c_match.group(1))
    except Exception as e:
        print(f"Could not extract RC values from netlist: {e}")
    
    return R_ohm, C_farad


def _analytic_rc_bode(R_ohm: float = None, C_farad: float = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate analytical bode plot for RC low-pass filter using the provided R and C values.
    
    Args:
        R_ohm: Resistance in ohms (default 1k)
        C_farad: Capacitance in farads (default 100nF)
    
    Returns:
        (freqs, mag_db, phase_deg): Arrays for bode plot
    """
    # Use defaults if not provided
    if R_ohm is None:
        R_ohm = 1000.0
    if C_farad is None:
        C_farad = 100e-9
    
    # Frequency range: 1 Hz to 100 kHz (log scale)
    freqs = np.logspace(0, 5, 200)  # 1 Hz to 100 kHz
    
    # RC low-pass transfer function: H(jw) = 1 / (1 + j*w*R*C)
    w = 2 * np.pi * freqs
    H = 1.0 / (1.0 + 1j * w * R_ohm * C_farad)
    
    # Magnitude in dB and phase in degrees
    mag_db = 20 * np.log10(np.abs(H))
    phase_deg = np.angle(H, deg=True)
    
    return freqs, mag_db, phase_deg


def generate_bode_plot(freqs: np.ndarray, mag_db: np.ndarray, phase_deg: np.ndarray, out_path: str) -> str:
    """
    Generate and save a bode plot (magnitude and phase vs frequency).
    
    Args:
        freqs: Frequency array (Hz)
        mag_db: Magnitude array (dB)
        phase_deg: Phase array (degrees)
        out_path: Output file path (e.g., '/path/to/plot.png')
    
    Returns:
        out_path: Path to saved PNG file
    """
    # Ensure output directory exists
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    # Magnitude plot
    ax1.semilogx(freqs, mag_db, 'b-', linewidth=2)
    ax1.set_xlabel('Frequency (Hz)')
    ax1.set_ylabel('Magnitude (dB)')
    ax1.set_title('Bode Plot - Magnitude')
    ax1.grid(True, which='both', alpha=0.3)
    
    # Phase plot
    ax2.semilogx(freqs, phase_deg, 'r-', linewidth=2)
    ax2.set_xlabel('Frequency (Hz)')
    ax2.set_ylabel('Phase (degrees)')
    ax2.set_title('Bode Plot - Phase')
    ax2.grid(True, which='both', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    return out_path


# Example usage for testing
if __name__ == "__main__":
    # Test compute_rc_values
    print("Testing compute_rc_values:")
    R, C = compute_rc_values(fc_hz=1000, fixed_component="C", fixed_value="10nF")
    print(f"  fc=1kHz, C=10nF => R={R:.1f}Ω, C={C:.2e}F")
    
    # Test run_ngspice_ac (will fallback to analytic)
    print("\nTesting run_ngspice_ac (analytic fallback):")
    freqs, mag_db, phase_deg = run_ngspice_ac("* dummy", workdir="/tmp/test_spice")
    print(f"  Freq range: {freqs[0]:.1f} Hz to {freqs[-1]:.1f} Hz")
    print(f"  Mag range: {mag_db.min():.2f} to {mag_db.max():.2f} dB")
    
    # Test generate_bode_plot
    print("\nTesting generate_bode_plot:")
    plot_path = generate_bode_plot(freqs, mag_db, phase_deg, "/tmp/bode_test.png")
    print(f"  Plot saved to: {plot_path}")
