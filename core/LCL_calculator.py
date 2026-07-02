"""
PCS Computing Platform - Core Calculation Model

Supports:
  - Three-phase SPWM inverter
  - Single-phase full-bridge (bipolar / unipolar modulation)

References:
  - IEEE 519-2014
  - Liserre, Blaabjerg & Hansen (2005)
  - Mohan, Undeland & Robbins. Power Electronics (3rd Ed.)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum
import sympy as sp
from core.base_calculator import CalculationStep, format_inductance, format_capacitance, format_resistance


# ============================================================================
# Enums
# ============================================================================


class PhaseType(Enum):
    """Inverter phase count / modulation type"""
    THREE_PHASE = "Three-Phase"
    SINGLE_PHASE_BIPOLAR = "Single-Phase Bipolar"
    SINGLE_PHASE_UNIPOLAR = "Single-Phase Unipolar"

    def is_single_phase(self) -> bool:
        return self in (PhaseType.SINGLE_PHASE_BIPOLAR,
                        PhaseType.SINGLE_PHASE_UNIPOLAR)

    def label_cn(self) -> str:
        """Chinese display label"""
        labels = {
            PhaseType.THREE_PHASE: "\u4e09\u76f8",
            PhaseType.SINGLE_PHASE_BIPOLAR: "\u5355\u76f8-\u53cc\u6781\u6027\u8c03\u5236",
            PhaseType.SINGLE_PHASE_UNIPOLAR: "\u5355\u76f8-\u5355\u6781\u6027\u8c03\u5236",
        }
        return labels.get(self, self.value)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class LCLInputParams:
    """LCL filter input parameters"""
    P_nominal: float = 10.0
    V_nominal: float = 380.0
    f_grid: float = 50.0
    f_sw: float = 10000.0
    V_dc: float = 700.0
    ripple_rate: float = 20.0
    phase_type: PhaseType = PhaseType.THREE_PHASE

    def validate(self) -> List[str]:
        errors = []
        if self.P_nominal <= 0:
            errors.append("Rated power must be > 0")
        if self.V_nominal <= 0:
            errors.append("Grid voltage must be > 0")
        if self.f_grid <= 0:
            errors.append("Grid frequency must be > 0")
        if self.f_sw <= 0:
            errors.append("Switching frequency must be > 0")
        if self.f_sw <= 2 * self.f_grid:
            errors.append(
                f"f_sw ({self.f_sw}Hz) should be >> 2*f_grid ({2*self.f_grid}Hz)")
        if self.V_dc <= 0:
            errors.append("DC bus voltage must be > 0")
        min_vdc = np.sqrt(2) * self.V_nominal
        if self.phase_type == PhaseType.THREE_PHASE:
            if self.V_dc < min_vdc:
                errors.append(
                    f"Vdc ({self.V_dc}V) should > line voltage peak ({min_vdc:.1f}V)")
        else:
            if self.V_dc < min_vdc:
                errors.append(
                    f"Vdc ({self.V_dc}V) should > grid voltage peak ({min_vdc:.1f}V)")
        if self.ripple_rate <= 0 or self.ripple_rate >= 100:
            errors.append("Ripple rate should be 0~100% (recommend 15~40%)")
        return errors


@dataclass
class LCLResults:
    """LCL filter calculation results (SI units)"""
    # Basic electrical
    V_ph: float = 0.0
    I_rated: float = 0.0
    I_peak: float = 0.0
    Z_base: float = 0.0
    phase_label: str = ""
    # Ripple current
    Delta_I_max: float = 0.0
    # Filter components (H, F, Ohm)
    L1: float = 0.0
    Cf: float = 0.0
    L2: float = 0.0
    r: float = 0.0
    Rd: float = 0.0
    Qc_pu: float = 0.0
    # Resonance
    fr: float = 0.0
    fr_min: float = 0.0
    fr_max: float = 0.0
    fr_valid: bool = False
    damping_ratio: float = 0.0
    # Filtering performance
    attenuation_sw_db: float = 0.0
    attenuation_sw_times: float = 0.0
    attenuation_valid: bool = False
    # Design status
    warnings: List[str] = field(default_factory=list)
    is_valid: bool = False


# ============================================================================
# LCL Calculator Engine
# ============================================================================


class LCLCalculator:
    """LCL filter calculation engine"""

    # Design constants
    RATIO_DEFAULT = 0.6
    QC_MAX_PU = 0.05
    FREQ_CONSTRAINT_LOW = 10.0
    FREQ_CONSTRAINT_HIGH = 0.5
    ATTENUATION_TARGET_DB = -40

    # ========================================================================
    # Main calculation
    # ========================================================================

    @staticmethod
    def calculate(params: LCLInputParams) -> LCLResults:
        """Execute full LCL filter design calculation"""
        res = LCLResults()
        warnings = []

        # Unpack params (SI units)
        P = params.P_nominal * 1e3
        V_nominal = params.V_nominal
        f_grid = params.f_grid
        f_sw = params.f_sw
        V_dc = params.V_dc
        ripple_pct = params.ripple_rate
        phase_type = params.phase_type
        res.phase_label = phase_type.label_cn()

        # ================================================================
        # Step 1: Basic electrical parameters
        # ================================================================
        if phase_type == PhaseType.THREE_PHASE:
            V_ph = V_nominal / np.sqrt(3)
            I_rated = P / (np.sqrt(3) * V_nominal)
            Z_base = V_ph**2 / (P / 3)
        else:
            V_ph = V_nominal
            I_rated = P / V_nominal
            Z_base = V_ph**2 / P
        res.V_ph = V_ph
        res.I_rated = I_rated
        res.Z_base = Z_base

        I_peak = np.sqrt(2) * I_rated
        res.I_peak = I_peak

        # ================================================================
        # Step 2: Ripple current
        # ================================================================
        Delta_I_max = (ripple_pct / 100.0) * I_peak
        res.Delta_I_max = Delta_I_max

        # ================================================================
        # Step 3: Inverter-side inductor L1
        # ================================================================
        # 3-phase SPWM / 1-phase bipolar: worst ripple at m ~ 0.5
        #   Delta_I_pp = Vdc / (2 * f_sw * L1)
        #   Delta_I_max(peak) = Vdc / (4 * f_sw * L1)
        #   => L1 = Vdc / (4 * f_sw * Delta_I_max)
        # 1-phase unipolar: effective f_sw doubles, ripple halves
        #   => L1 = Vdc / (8 * f_sw * Delta_I_max)
        if phase_type == PhaseType.SINGLE_PHASE_UNIPOLAR:
            L1 = V_dc / (8.0 * f_sw * Delta_I_max)
        else:
            L1 = V_dc / (4.0 * f_sw * Delta_I_max)
        res.L1 = L1

        # ================================================================
        # Step 4: Filter capacitor Cf
        # ================================================================
        Qc_pu = LCLCalculator.QC_MAX_PU
        if phase_type == PhaseType.THREE_PHASE:
            Qc_ref = Qc_pu * P / 3.0
        else:
            Qc_ref = Qc_pu * P
        Cf = Qc_ref / (2.0 * np.pi * f_grid * V_ph**2)
        res.Cf = Cf
        res.Qc_pu = Qc_pu

        # ================================================================
        # Step 5: Grid-side inductor L2
        # ================================================================
        r = LCLCalculator.RATIO_DEFAULT
        L2 = r * L1
        res.L2 = L2
        res.r = r

        # ================================================================
        # Step 6: Resonant frequency & constraint check
        # ================================================================
        if L1 > 0 and L2 > 0 and Cf > 0:
            omega_r = np.sqrt((L1 + L2) / (L1 * L2 * Cf))
            fr = omega_r / (2.0 * np.pi)
        else:
            omega_r = 0.0
            fr = 0.0
        res.fr = fr

        fr_min = LCLCalculator.FREQ_CONSTRAINT_LOW * f_grid
        fr_max = LCLCalculator.FREQ_CONSTRAINT_HIGH * f_sw
        res.fr_min = fr_min
        res.fr_max = fr_max
        res.fr_valid = (fr_min < fr < fr_max)

        if not res.fr_valid:
            if fr <= fr_min:
                warnings.append(
                    f"fr ({fr:.1f}Hz) too low, should > {fr_min:.0f}Hz. "
                    f"Suggest: increase L1 or Cf.")
            elif fr >= fr_max:
                warnings.append(
                    f"fr ({fr:.1f}Hz) too high, should < {fr_max:.0f}Hz. "
                    f"Suggest: decrease L1 or increase Cf.")
        
        # ================================================================
        # Step 7: Damping resistor Rd
        # ================================================================
        if omega_r > 0 and Cf > 0:
            Rd = 1.0 / (omega_r * Cf)
        else:
            Rd = 0.0
        res.Rd = Rd

        if Rd > 0:
            damping_ratio = Rd * Cf * omega_r / 2.0
        else:
            damping_ratio = 0.0
        res.damping_ratio = damping_ratio

        # ================================================================
        # Step 8: Switching frequency attenuation
        # ================================================================
        omega_sw = 2.0 * np.pi * f_sw
        s = 1j * omega_sw
        num_sw = 1.0 + s * Rd * Cf
        den_sw = (s**3 * L1 * L2 * Cf +
                  s**2 * Rd * Cf * (L1 + L2) +
                  s * (L1 + L2))
        G_sw = num_sw / den_sw
        attenuation_sw_db = 20.0 * np.log10(np.abs(G_sw))
        attenuation_sw_times = 1.0 / np.abs(G_sw)
        res.attenuation_sw_db = attenuation_sw_db
        res.attenuation_sw_times = attenuation_sw_times
        res.attenuation_valid = (
            attenuation_sw_db <= LCLCalculator.ATTENUATION_TARGET_DB)

        if not res.attenuation_valid:
            warnings.append(
                f"Attenuation at f_sw ({attenuation_sw_db:.1f}dB) insufficient, "
                f"target < {LCLCalculator.ATTENUATION_TARGET_DB}dB. "
                f"Suggest: increase L2 or Cf.")

        # Summary
        res.warnings = warnings
        res.is_valid = (len(warnings) == 0)
        return res


    # ========================================================================
    # Calculation steps (for GUI display and PDF report)
    # ========================================================================

    @staticmethod
    def get_calculation_steps(params, res):
        """Generate step-by-step calculation process"""
        steps = []
        step = 0

        P = params.P_nominal * 1e3
        V_nominal = params.V_nominal
        f_grid = params.f_grid
        f_sw = params.f_sw
        V_dc = params.V_dc
        ripple_pct = params.ripple_rate
        phase_type = params.phase_type

        # --- Step 1: Basic electrical parameters ---
        is_3ph = (phase_type == PhaseType.THREE_PHASE)

        if is_3ph:
            step += 1
            steps.append(CalculationStep(
                step_num=step,
                title="Phase voltage (3-phase)",
                formula_text="V_ph = V_line / sqrt(3)",
                formula_latex=r"V_{ph} = \frac{V_{line}}{\sqrt{3}}",
                substitution=f"V_ph = {V_nominal:.1f} / sqrt(3)",
                result=f"{res.V_ph:.2f}",
                unit="V (RMS)",
                note="Line-to-line -> phase voltage"
            ))
            step += 1
            steps.append(CalculationStep(
                step_num=step,
                title="Rated current (3-phase)",
                formula_text="I_rated = P / (sqrt(3) * V_line)",
                formula_latex=r"I_{rated} = \frac{P}{\sqrt{3} \cdot V_{line}}",
                substitution=f"I_rated = {P/1000:.1f}kW / (sqrt(3) * {V_nominal:.0f}V)",
                result=f"{res.I_rated:.2f}",
                unit="A (RMS)",
                note="3-phase rated line current"
            ))
        else:
            step += 1
            steps.append(CalculationStep(
                step_num=step,
                title="Grid voltage (1-phase)",
                formula_text="V_grid = V_nominal",
                formula_latex=r"V_{grid} = V_{nominal}",
                substitution=f"V_grid = {V_nominal:.0f}V",
                result=f"{res.V_ph:.2f}",
                unit="V (RMS)",
                note="Single-phase: direct grid voltage"
            ))
            step += 1
            steps.append(CalculationStep(
                step_num=step,
                title="Rated current (1-phase)",
                formula_text="I_rated = P / V_grid",
                formula_latex=r"I_{rated} = \frac{P}{V_{grid}}",
                substitution=f"I_rated = {P/1000:.1f}kW / {V_nominal:.0f}V",
                result=f"{res.I_rated:.2f}",
                unit="A (RMS)",
                note="Single-phase rated current"
            ))

        step += 1
        steps.append(CalculationStep(
            step_num=step,
            title="Peak current",
            formula_text="I_peak = sqrt(2) * I_rated",
            formula_latex=r"I_{peak} = \sqrt{2} \cdot I_{rated}",
            substitution=f"I_peak = sqrt(2) * {res.I_rated:.2f}",
            result=f"{res.I_peak:.2f}",
            unit="A",
            note="Peak current reference for ripple"
        ))

        step += 1
        if is_3ph:
            z_sub = f"Z_base = {res.V_ph:.1f}^2 / ({P/1000:.1f}kW / 3)"
            z_note = "Per-phase base impedance"
        else:
            z_sub = f"Z_base = {res.V_ph:.1f}^2 / {P/1000:.1f}kW"
            z_note = "Base impedance"
        steps.append(CalculationStep(
            step_num=step,
            title="Base impedance",
            formula_text="Z_base = V_ph^2 / P_ref",
            formula_latex=r"Z_{base} = \frac{V_{ph}^2}{P_{ref}}",
            substitution=z_sub,
            result=f"{res.Z_base:.2f}",
            unit="Ohm",
            note=z_note
        ))

        # --- Step 2: Ripple current ---
        step += 1
        steps.append(CalculationStep(
            step_num=step,
            title="Max ripple current",
            formula_text="Delta_I_max = (ripple_rate/100) * I_peak",
            formula_latex=r"\Delta I_{max} = \frac{r_{ripple}}{100} \cdot I_{peak}",
            substitution=f"Delta_I_max = ({ripple_pct:.0f}/100) * {res.I_peak:.2f}",
            result=f"{res.Delta_I_max:.3f}",
            unit="A",
            note="Peak ripple (not peak-to-peak), Delta_I_pp = 2 * Delta_I_max"
        ))

        # --- Step 3: L1 calculation ---
        step += 1
        if phase_type == PhaseType.SINGLE_PHASE_UNIPOLAR:
            l1_formula = "L1 = Vdc / (8 * f_sw * Delta_I_max)"
            l1_latex = r"L_1 = \frac{V_{dc}}{8 \cdot f_{sw} \cdot \Delta I_{max}}"
            l1_sub = f"L1 = {V_dc:.0f}V / (8 * {f_sw:.0f}Hz * {res.Delta_I_max:.3f}A)"
            l1_note = "Unipolar: effective f_sw doubles, L1 can be halved"
        else:
            l1_formula = "L1 = Vdc / (4 * f_sw * Delta_I_max)"
            l1_latex = r"L_1 = \frac{V_{dc}}{4 \cdot f_{sw} \cdot \Delta I_{max}}"
            l1_sub = f"L1 = {V_dc:.0f}V / (4 * {f_sw:.0f}Hz * {res.Delta_I_max:.3f}A)"
            l1_note = "Worst-case ripple at modulation index ~ 0.5"
        steps.append(CalculationStep(
            step_num=step,
            title="Inverter-side inductor L1",
            formula_text=l1_formula,
            formula_latex=l1_latex,
            substitution=l1_sub,
            result=f"{res.L1*1e6:.1f} uH = {res.L1*1e3:.3f} mH",
            unit="H",
            note=l1_note
        ))

        # --- Step 4: Cf calculation ---
        step += 1
        if is_3ph:
            cf_formula = "Cf = (Qc_pu * P / 3) / (2*pi * f_grid * V_ph^2)"
            cf_latex = r"C_f = \frac{Q_{c,pu} \cdot P / 3}{2\pi \cdot f_{grid} \cdot V_{ph}^2}"
            cf_sub = f"Cf = (0.05 * {P/1000:.1f}kW / 3) / (2*pi * {f_grid:.0f}Hz * {res.V_ph:.1f}V^2)"
            cf_note = f"Per-phase cap, total Qc = {res.Qc_pu*100:.0f}% * P_nominal"
        else:
            cf_formula = "Cf = (Qc_pu * P) / (2*pi * f_grid * V_grid^2)"
            cf_latex = r"C_f = \frac{Q_{c,pu} \cdot P}{2\pi \cdot f_{grid} \cdot V_{grid}^2}"
            cf_sub = f"Cf = (0.05 * {P/1000:.1f}kW) / (2*pi * {f_grid:.0f}Hz * {res.V_ph:.1f}V^2)"
            cf_note = f"Total cap, Qc = {res.Qc_pu*100:.0f}% * P_nominal"
        steps.append(CalculationStep(
            step_num=step,
            title="Filter capacitor Cf",
            formula_text=cf_formula,
            formula_latex=cf_latex,
            substitution=cf_sub,
            result=f"{res.Cf*1e6:.2f} uF",
            unit="F",
            note=cf_note
        ))

        # --- Step 5: L2 calculation ---
        step += 1
        steps.append(CalculationStep(
            step_num=step,
            title="Grid-side inductor L2",
            formula_text="L2 = r * L1  (r = 0.6 default ratio)",
            formula_latex=r"L_2 = r \cdot L_1",
            substitution=f"L2 = 0.6 * {res.L1*1e6:.1f}uH",
            result=f"{res.L2*1e6:.1f} uH = {res.L2*1e3:.3f} mH",
            unit="H",
            note=f"Inductance ratio r = L2/L1 = {res.r:.1f}"
        ))

        # --- Step 6: Resonant frequency ---
        step += 1
        steps.append(CalculationStep(
            step_num=step,
            title="Resonant frequency",
            formula_text="fr = (1/(2*pi)) * sqrt[(L1+L2) / (L1*L2*Cf)]",
            formula_latex=r"f_r = \frac{1}{2\pi}\sqrt{\frac{L_1+L_2}{L_1 L_2 C_f}}",
            substitution=(f"fr = (1/(2*pi)) * sqrt[({res.L1*1e6:.1f}+{res.L2*1e6:.1f})uH / "
                          f"({res.L1*1e6:.1f}*{res.L2*1e6:.1f}uH*{res.Cf*1e6:.2f}uF)]"),
            result=f"{res.fr:.1f} Hz",
            unit="Hz",
            note=""
        ))

        step += 1
        constraint_status = "OK" if res.fr_valid else "FAIL"
        steps.append(CalculationStep(
            step_num=step,
            title="Resonant frequency constraint check",
            formula_text=f"{res.fr_min:.0f}Hz < fr < {res.fr_max:.0f}Hz",
            formula_latex=r"10f_{grid} < f_r < 0.5f_{sw}",
            substitution=f"{res.fr_min:.0f}Hz < {res.fr:.1f}Hz < {res.fr_max:.0f}Hz",
            result=constraint_status,
            unit="",
            note=f"Constraint: 10*f_grid ~ 0.5*f_sw = {res.fr_min:.0f} ~ {res.fr_max:.0f} Hz"
        ))

        # --- Step 7: Rd calculation ---
        step += 1
        steps.append(CalculationStep(
            step_num=step,
            title="Damping resistor Rd",
            formula_text="Rd = 1 / (2*pi * fr * Cf)",
            formula_latex=r"R_d = \frac{1}{2\pi f_r C_f}",
            substitution=f"Rd = 1 / (2*pi * {res.fr:.1f}Hz * {res.Cf*1e6:.2f}uF)",
            result=f"{res.Rd:.2f} Ohm",
            unit="Ohm",
            note=f"Damping ratio zeta = {res.damping_ratio:.2f}"
        ))

        # --- Step 8: Attenuation verification ---
        step += 1
        steps.append(CalculationStep(
            step_num=step,
            title="Switching frequency attenuation",
            formula_text="A_sw = 20*log10|G(j*2*pi*f_sw)|",
            formula_latex=r"A_{sw} = 20\log_{10}|G(j\omega_{sw})|",
            substitution=f"f_sw = {f_sw:.0f}Hz, damped transfer function",
            result=f"{res.attenuation_sw_db:.1f} dB (attenuation {res.attenuation_sw_times:.0f}x)",
            unit="dB",
            note=f"Target: < {LCLCalculator.ATTENUATION_TARGET_DB}dB"
        ))

        return steps

    # ========================================================================
    # Symbolic transfer function derivation (Sympy)
    # ========================================================================

    @staticmethod
    def get_transfer_function_sympy() -> Tuple[sp.Expr, sp.Expr]:
        """Derive LCL filter transfer function symbolically using Sympy

        Returns:
            Tuple[sp.Expr, sp.Expr]: (undamped TF, damped TF)
        """
        s, L1, L2, Cf, Rd = sp.symbols('s L1 L2 Cf Rd', positive=True)

        # Undamped: G(s) = 1 / [s^3*L1*L2*Cf + s*(L1+L2)]
        G_undamped = 1 / (s**3 * L1 * L2 * Cf + s * (L1 + L2))

        # Damped: G(s) = (1+s*Rd*Cf) / [s^3*L1*L2*Cf + s^2*Rd*Cf*(L1+L2) + s*(L1+L2)]
        G_damped = (1 + s * Rd * Cf) / (
            s**3 * L1 * L2 * Cf +
            s**2 * Rd * Cf * (L1 + L2) +
            s * (L1 + L2)
        )

        return G_undamped, G_damped

    @staticmethod
    def get_resonant_freq_sympy() -> sp.Expr:
        """Symbolic resonant angular frequency expression

        From undamped characteristic equation:
          s*(s^2*L1*L2*Cf + L1 + L2) = 0
          s^2 = -(L1+L2)/(L1*L2*Cf)
          omega_r = sqrt((L1+L2)/(L1*L2*Cf))
        """
        L1, L2, Cf = sp.symbols('L1 L2 Cf', positive=True)
        omega_r = sp.sqrt((L1 + L2) / (L1 * L2 * Cf))
        return omega_r

    # ========================================================================
    # Numerical frequency response (for Bode plot)
    # ========================================================================

    @staticmethod
    def compute_frequency_response(
        L1: float, L2: float, Cf: float, Rd: float,
        f_min: float = 1.0,
        f_max: float = 100000.0,
        num_points: int = 1000
    ) -> dict:
        """Compute LCL filter frequency response (Bode plot data)

        Returns:
            dict with keys: f, mag_damped, phase_damped, mag_undamped, phase_undamped
        """
        f = np.logspace(np.log10(f_min), np.log10(f_max), num_points)
        omega = 2.0 * np.pi * f
        s = 1j * omega

        # Damped response
        num_damped = 1.0 + s * Rd * Cf
        den_damped = (s**3 * L1 * L2 * Cf +
                      s**2 * Rd * Cf * (L1 + L2) +
                      s * (L1 + L2))
        G_damped = num_damped / den_damped
        mag_damped = 20.0 * np.log10(np.abs(G_damped))
        phase_damped = np.angle(G_damped, deg=True)

        # Undamped response
        den_undamped = s**3 * L1 * L2 * Cf + s * (L1 + L2)
        G_undamped = 1.0 / den_undamped
        mag_undamped = 20.0 * np.log10(np.abs(G_undamped))
        phase_undamped = np.angle(G_undamped, deg=True)

        return {
            'f': f,
            'mag_damped': mag_damped,
            'phase_damped': phase_damped,
            'mag_undamped': mag_undamped,
            'phase_undamped': phase_undamped,
        }

    # ========================================================================
    # Utility methods
