"""
PCS Platform - Base Calculator & Shared Utilities

Provides:
  - CalculationStep dataclass (unified across all modules)
  - linear_interp() utility (reusable across all calculators)
  - Common format_*() helpers
"""

from dataclasses import dataclass
from typing import List


# ============================================================================
# Unified CalculationStep — used by ALL calculation modules
# ============================================================================

@dataclass
class CalculationStep:
    """Single calculation step for display in GUI and PDF"""
    step_num: int
    title: str
    formula_text: str
    formula_latex: str
    substitution: str
    result: str
    unit: str
    note: str = ""


# ============================================================================
# Reusable interpolation utility
# ============================================================================

def linear_interp(x: float, x_array: List[float], y_array: List[float]) -> float:
    """
    一维线性插值: 在(x_array, y_array)中查找x对应的y。
    可复用于Eon/Eoff插值、损耗曲线查表、效率查表等。

    Args:
        x: 待插值点
        x_array: 自变量数组 (单调递增)
        y_array: 因变量数组 (与x_array等长)

    Returns:
        插值结果 y = y1 + (y2-y1)*(x-x1)/(x2-x1)

    Raises:
        ValueError: x超出范围
    """
    if x < x_array[0] or x > x_array[-1]:
        raise ValueError(
            f"插值点 x={x:.3f} 超出范围 [{x_array[0]:.3f}, {x_array[-1]:.3f}]")

    for i in range(len(x_array) - 1):
        if x_array[i] <= x <= x_array[i + 1]:
            x1, x2 = x_array[i], x_array[i + 1]
            y1, y2 = y_array[i], y_array[i + 1]
            if x2 == x1:
                return y1
            return y1 + (y2 - y1) * (x - x1) / (x2 - x1)

    return y_array[-1]  # fallback


# ============================================================================
# Common unit format helpers
# ============================================================================

def format_power(p: float) -> str:
    """Format power value with auto unit"""
    if abs(p) >= 1e3: return f"{p/1e3:.3f} kW"
    if abs(p) >= 1.0: return f"{p:.4f} W"
    if abs(p) >= 1e-3: return f"{p*1e3:.2f} mW"
    return f"{p*1e6:.1f} uW"


def format_time(t: float) -> str:
    """Format time value with auto unit"""
    if t >= 1.0: return f"{t:.4f} s"
    if t >= 1e-3: return f"{t*1e3:.2f} ms"
    if t >= 1e-6: return f"{t*1e6:.1f} us"
    return f"{t*1e9:.1f} ns"


def format_frequency(f: float) -> str:
    """Format frequency value with auto unit"""
    if f >= 1e6: return f"{f/1e6:.2f} MHz"
    if f >= 1e3: return f"{f/1e3:.2f} kHz"
    return f"{f:.2f} Hz"


def format_inductance(L: float) -> str:
    """Format inductance with auto unit"""
    if abs(L) >= 1.0: return f"{L:.4f} H"
    if abs(L) >= 1e-3: return f"{L*1e3:.3f} mH"
    return f"{L*1e6:.1f} uH"


def format_capacitance(C: float) -> str:
    """Format capacitance with auto unit"""
    if abs(C) >= 1.0: return f"{C:.4f} F"
    if abs(C) >= 1e-3: return f"{C*1e3:.3f} mF"
    if abs(C) >= 1e-6: return f"{C*1e6:.2f} uF"
    return f"{C*1e9:.1f} nF"


def format_resistance(R: float) -> str:
    """Format resistance with auto unit"""
    if abs(R) >= 1e6: return f"{R/1e6:.2f} MOhm"
    if abs(R) >= 1e3: return f"{R/1e3:.2f} kOhm"
    if abs(R) >= 1.0: return f"{R:.2f} Ohm"
    return f"{R*1e3:.1f} mOhm"
