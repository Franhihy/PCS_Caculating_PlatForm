"""
PCS Platform - SOGI Parameter Calculator Model

Second-Order Generalized Integrator (SOGI).
Three discretization methods: Forward Euler, Backward Euler, Bilinear/Tustin.
References: Ciobotaru et al. (2006), Ogata "Discrete-Time Control Systems"
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import sympy as sp
from core.base_calculator import CalculationStep, format_frequency, format_time


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class DiscreteMethod:
    """Discretization result for one method"""
    name: str = ""
    name_en: str = ""
    a11: float = 0.0; a12: float = 0.0; a21: float = 0.0; a22: float = 0.0
    b1: float = 0.0; b2: float = 0.0
    eig1_mag: float = 0.0; eig2_mag: float = 0.0
    stable: bool = False
    stability_factor: float = 0.0


@dataclass
class SOGIInputParams:
    """SOGI input parameters"""
    V_amplitude: float = 311.0
    f_grid: float = 50.0
    bandwidth: float = 5.0
    fs: float = 10000.0

    def validate(self):
        errors = []
        if self.V_amplitude <= 0: errors.append("电网电压幅值必须大于0")
        if self.f_grid <= 0: errors.append("电网频率必须大于0")
        if self.bandwidth <= 0: errors.append("滤波器带宽必须大于0 (建议3~10Hz)")
        if self.bandwidth > self.f_grid: errors.append(f"带宽({self.bandwidth}Hz)应小于电网频率({self.f_grid}Hz)")
        if self.fs <= 2 * self.f_grid: errors.append(f"采样频率({self.fs}Hz)应远大于2倍电网频率({2*self.f_grid}Hz)")
        return errors


@dataclass
class SOGIResults:
    """SOGI calculation results"""
    w0: float = 0.0; k: float = 0.0; wc: float = 0.0; Q: float = 0.0; Ts: float = 0.0
    forward_euler: DiscreteMethod | None = None
    backward_euler: DiscreteMethod | None = None
    bilinear: DiscreteMethod | None = None
    settling_time_4t: float = 0.0; settling_cycles: float = 0.0
    warnings: List[str] = field(default_factory=list)
    is_valid: bool = False

    def get_all_methods(self):
        methods = []
        for m in [self.forward_euler, self.backward_euler, self.bilinear]:
            if m is not None: methods.append(m)
        return methods


# ============================================================================
# Calculator
# ============================================================================


class SOGICalculator:

    @staticmethod
    def _build_method(name, name_en, Ad, Bd, Ts, k, w0):
        eigvals = np.linalg.eigvals(Ad)
        eig_mags = np.abs(eigvals)
        return DiscreteMethod(
            name=name, name_en=name_en,
            a11=float(Ad[0,0]), a12=float(Ad[0,1]),
            a21=float(Ad[1,0]), a22=float(Ad[1,1]),
            b1=float(Bd[0,0]), b2=float(Bd[1,0]),
            eig1_mag=float(eig_mags[0]), eig2_mag=float(eig_mags[1]),
            stable=bool(np.all(eig_mags < 1.0)),
            stability_factor=float(Ts * w0 * k))

    @staticmethod
    def calculate(params):
        """Execute SOGI calculation with 3 discretization methods"""
        res = SOGIResults()
        warnings = []
        f_grid = params.f_grid; BW = params.bandwidth; fs = params.fs

        w0 = 2.0 * np.pi * f_grid; res.w0 = w0
        k = BW / f_grid; res.k = k
        res.wc = k * w0
        res.Q = 1.0 / k if k > 0 else float("inf")
        Ts = 1.0 / fs; res.Ts = Ts

        A = np.array([[-k*w0, -w0], [w0, 0.0]])
        B = np.array([[k*w0], [0.0]])
        I = np.eye(2)

        # Forward Euler: Ad = I + Ts*A, Bd = Ts*B
        res.forward_euler = SOGICalculator._build_method(
            "前向欧拉 (Forward Euler)", "Forward Euler",
            I + Ts * A, Ts * B, Ts, k, w0)

        # Backward Euler: Ad = inv(I - Ts*A), Bd = inv(I - Ts*A) * Ts * B
        M_be = I - Ts * A
        M_be_inv = np.linalg.inv(M_be)
        res.backward_euler = SOGICalculator._build_method(
            "后向欧拉 (Backward Euler)", "Backward Euler",
            M_be_inv, M_be_inv @ (Ts * B), Ts, k, w0)

        # Bilinear: Ad = inv(I - Ts/2*A) * (I + Ts/2*A), Bd = inv(I - Ts/2*A) * Ts * B
        M_bl = I - (Ts/2.0) * A
        M_bl_inv = np.linalg.inv(M_bl)
        res.bilinear = SOGICalculator._build_method(
            "双线性变换 (Bilinear/Tustin)", "Bilinear/Tustin",
            M_bl_inv @ (I + (Ts/2.0) * A), M_bl_inv @ (Ts * B), Ts, k, w0)

        # Settling time
        if k > 0:
            tau = 2.0 / (k * w0)
            res.settling_time_4t = 4.0 * tau
            res.settling_cycles = res.settling_time_4t * f_grid

        # Warnings
        sf = Ts * w0 * k
        if k > 2.0: warnings.append(f"k={k:.2f}偏大, 建议减小带宽")
        if k < 0.1: warnings.append(f"k={k:.3f}偏小, 动态响应可能过慢")
        if sf > 0.1: warnings.append(f"稳定因子 Ts*w0*k={sf:.4f}, 前向欧拉可能精度不足, 建议双线性变换")
        for m in res.get_all_methods():
            if not m.stable:
                warnings.append(f"{m.name}: 不稳定! |eig|_max={max(m.eig1_mag,m.eig2_mag):.4f} > 1")
        res.warnings = warnings
        res.is_valid = (len(warnings) == 0)
        return res

    @staticmethod
    def get_calculation_steps(params, res):
        steps = []
        step = 0
        f_grid = params.f_grid; BW = params.bandwidth; fs = params.fs

        step += 1
        steps.append(CalculationStep(step_num=step, title="谐振角频率计算",
            formula_text="w0 = 2*pi * f_grid",
            formula_latex=r"\omega_0 = 2\pi \cdot f_{grid}",
            substitution=f"w0 = 2*pi * {f_grid:.0f}Hz",
            result=f"{res.w0:.4f} rad/s", unit="rad/s"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="SOGI增益 (k)",
            formula_text="k = BW / f_grid",
            formula_latex=r"k = rac{BW}{f_{grid}}",
            substitution=f"k = {BW:.1f}Hz / {f_grid:.0f}Hz",
            result=f"{res.k:.4f}", unit="-"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="带宽参数 (wc)",
            formula_text="wc = k * w0 = 2*pi * BW",
            formula_latex=r"\omega_c = k \cdot \omega_0",
            substitution=f"wc = {res.k:.4f} * {res.w0:.2f}",
            result=f"{res.wc:.4f} rad/s", unit="rad/s"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="品质因数 (Q)",
            formula_text="Q = 1 / k", formula_latex=r"Q = rac{1}{k}",
            substitution=f"Q = 1 / {res.k:.4f}", result=f"{res.Q:.2f}", unit="-"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="采样周期 (Ts)",
            formula_text="Ts = 1 / fs", formula_latex=r"T_s = rac{1}{f_s}",
            substitution=f"Ts = 1 / {fs:.0f}Hz",
            result=f"{res.Ts*1e6:.1f} us", unit="s"))

        step += 1
        method_lines = []
        for m in res.get_all_methods():
            method_lines.append(
                f"{m.name}:\n"
                f"  Ad=[[{m.a11:.4f},{m.a12:.4f}],[{m.a21:.4f},{m.a22:.4f}]]\n"
                f"  Bd=[{m.b1:.4f},{m.b2:.4f}]\n"
                f"  |eig|=[{m.eig1_mag:.4f},{m.eig2_mag:.4f}], stable={m.stable}"
            )
        steps.append(CalculationStep(step_num=step, title="离散化 (三种方法对比)",
            formula_text="x[n+1]=Ad*x[n]+Bd*vin[n]",
            formula_latex=r"x[n+1]=A_d x[n]+B_d v_{in}[n]",
            substitution=f"Ts={res.Ts*1e6:.1f}us, k={res.k:.4f}, w0={res.w0:.2f}",
            result="\n".join(method_lines), unit="-"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="稳定时间 (4*tau)",
            formula_text="tau = 2/(k*w0), t_settle = 4*tau",
            formula_latex=r"	au = rac{2}{k\omega_0}",
            substitution=f"tau = 2/({res.k:.4f}*{res.w0:.2f})",
            result=f"{res.settling_time_4t*1e3:.1f} ms ({res.settling_cycles:.1f} 个周期)",
            unit="s"))
        return steps

    @staticmethod
    def get_transfer_function_sympy():
        s, k_sym, w0_sym = sp.symbols("s k w0", positive=True)
        den = s**2 + k_sym * w0_sym * s + w0_sym**2
        H_d = (k_sym * w0_sym * s) / den
        H_q = (k_sym * w0_sym**2) / den
        return H_d, H_q, s, k_sym, w0_sym

    @staticmethod
    def get_discrete_matrices_sympy():
        Ts_sym, k_sym, w0_sym = sp.symbols("Ts k w0", positive=True)
        A = sp.Matrix([[-k_sym*w0_sym, -w0_sym], [w0_sym, 0]])
        B = sp.Matrix([[k_sym*w0_sym], [0]])
        I = sp.eye(2)
        Ad_fe = I + Ts_sym * A
        Bd_fe = Ts_sym * B
        M_be = I - Ts_sym * A
        Ad_be = M_be.inv()
        Bd_be = M_be.inv() * Ts_sym * B
        M_bl = I - (Ts_sym/2) * A
        Ad_bl = M_bl.inv() * (I + (Ts_sym/2) * A)
        Bd_bl = M_bl.inv() * Ts_sym * B
        return Ad_fe, Bd_fe, Ad_be, Bd_be, Ad_bl, Bd_bl, A, B

    @staticmethod
    def compute_frequency_response(k, w0, f_min=0.1, f_max=1000.0, num_points=1000):
        f = np.logspace(np.log10(f_min), np.log10(f_max), num_points)
        s = 1j * 2.0 * np.pi * f
        den = s**2 + k * w0 * s + w0**2
        H_d = (k * w0 * s) / den
        H_q = (k * w0**2) / den
        return {"f": f, "mag_d": 20*np.log10(np.abs(H_d)), "phase_d": np.angle(H_d,deg=True),
                "mag_q": 20*np.log10(np.abs(H_q)), "phase_q": np.angle(H_q,deg=True)}

    @staticmethod
    def format_frequency(f):
        if f >= 1e6: return f"{f/1e6:.2f} MHz"
        if f >= 1e3: return f"{f/1e3:.2f} kHz"
        return f"{f:.2f} Hz"

    @staticmethod
    def format_time(t):
        if t >= 1.0: return f"{t:.4f} s"
        if t >= 1e-3: return f"{t*1e3:.2f} ms"
        if t >= 1e-6: return f"{t*1e6:.1f} us"
        return f"{t*1e9:.1f} ns"