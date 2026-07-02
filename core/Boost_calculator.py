"""
PCS计算平台 - Boost DC/DC 损耗分析计算引擎

支持 MOSFET Boost 和 IGBT Boost 两种器件类型。
包含: 占空比/输出功率计算、五种损耗分析、效率计算、
      温度扫描、电流扫描、损耗占比统计。

参考公式: 需求文档 §3-§5
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple
from enum import Enum
from core.base_calculator import CalculationStep, linear_interp, format_power, format_time


# ============================================================================
# 枚举与数据类
# ============================================================================

class BoostDeviceType(Enum):
    """Boost器件类型枚举"""
    MOSFET = "MOSFET"
    IGBT = "IGBT"

    def label_cn(self) -> str:
        return "MOSFET" if self == BoostDeviceType.MOSFET else "IGBT"


@dataclass
class BoostInputParams:
    """Boost损耗分析输入参数"""
    # === 基础参数 ===
    Vin: float = 100.0              # 输入电压 (V)
    Vout: float = 200.0             # 输出电压 (V)
    Iin: float = 10.0               # 输入电流 (A)
    fsw: float = 50000.0            # 开关频率 (Hz)
    Tj: float = 100.0               # 结温 (℃)
    device_type: BoostDeviceType = BoostDeviceType.MOSFET

    # === MOSFET 参数 ===
    Rds_on_25: float = 0.1          # 25℃导通电阻 (Ohm)
    tr: float = 50e-9               # 上升时间 (s)
    tf: float = 30e-9               # 下降时间 (s)
    Qg: float = 6e-8                # 栅极电荷 (C)
    Von: float = 15.0               # 驱动正压 (V)
    Voff: float = -5.0              # 驱动负压 (V)
    alpha: float = 0.004            # Rds_on温度系数 (1/℃)

    # === MOSFET Eon/Eoff 电流相关数组 (用于精确插值) ===
    I_array: List[float] = field(default_factory=list)     # 电流数组 (A)
    Eon_array: List[float] = field(default_factory=list)   # 开通能量数组 (J)
    Eoff_array: List[float] = field(default_factory=list)  # 关断能量数组 (J)

    # === IGBT 参数 ===
    Vce_sat: float = 1.5            # 饱和压降 (V)
    Eon: float = 0.5e-3             # 开通能量 (J)
    Eoff: float = 0.3e-3            # 关断能量 (J)
    Vf: float = 1.0                 # 正向压降 (V)
    Qrr: float = 5e-8               # 反向恢复电荷 (C)

    # === 器件信息 ===
    device_model: str = "SiHx100N060"  # 器件型号
    device_mfr: str = "Vishay"          # 器件厂家

    def validate(self) -> List[str]:
        """验证输入参数"""
        errors = []
        if self.Vin <= 0: errors.append("输入电压必须大于0")
        if self.Vout <= 0: errors.append("输出电压必须大于0")
        if self.Vin >= self.Vout: errors.append(f"Boost电路要求Vin({self.Vin}V) < Vout({self.Vout}V)")
        if self.Iin <= 0: errors.append("输入电流必须大于0")
        if self.fsw <= 0: errors.append("开关频率必须大于0")
        if self.Tj < -40 or self.Tj > 175: errors.append("结温应在-40~175℃范围内")
        if self.device_type == BoostDeviceType.MOSFET:
            if self.Rds_on_25 <= 0: errors.append("Rds_on_25必须大于0")
        else:
            if self.Vce_sat <= 0: errors.append("Vce_sat必须大于0")

        # Eon/Eoff数组验证 (仅MOSFET且有数组输入时)
        if self.device_type == BoostDeviceType.MOSFET and self.I_array:
            n = len(self.I_array)
            arrays_ok = True
            if n < 2:
                errors.append("I_array至少需要2个数据点用于插值")
                arrays_ok = False
            if len(self.Eon_array) != n:
                errors.append(f"Eon_array长度({len(self.Eon_array)})与I_array长度({n})不一致")
                arrays_ok = False
            if len(self.Eoff_array) != n:
                errors.append(f"Eoff_array长度({len(self.Eoff_array)})与I_array长度({n})不一致")
                arrays_ok = False
            if arrays_ok:
                if self.Iin < min(self.I_array) or self.Iin > max(self.I_array):
                    errors.append(
                        f"输入电流Iin={self.Iin:.2f}A超出Eon/Eoff定义范围"
                        f"[{min(self.I_array):.1f}~{max(self.I_array):.1f}]A, 无法插值")
        return errors


@dataclass
class BoostResults:
    """Boost损耗分析计算结果 (单位: W, 效率除外)"""
    # === 基本参数 ===
    D: float = 0.0                  # 占空比
    I_L: float = 0.0                # 电感平均电流 (=Iin, A)
    Iout: float = 0.0               # 输出电流 (A)
    Pin: float = 0.0                # 输入功率 (W)
    Pout: float = 0.0               # 输出功率 (W)

    # === 损耗分量 (W) ===
    P_cond: float = 0.0             # 导通损耗
    P_sw: float = 0.0               # 开关损耗
    P_diode_cond: float = 0.0       # 二极管导通损耗
    P_rr: float = 0.0               # 二极管反向恢复损耗
    P_drv: float = 0.0              # 驱动芯片供电损耗
    P_total: float = 0.0            # 总损耗

    # === 效率 ===
    efficiency: float = 0.0         # 转换效率 (0~100%)

    # === 损耗占比 (%) ===
    ratio_cond: float = 0.0
    ratio_sw: float = 0.0
    ratio_diode_cond: float = 0.0
    ratio_rr: float = 0.0
    ratio_drv: float = 0.0
    ratio_total: float = 0.0

    # === 中间计算量 ===
    Rds_on_T: float = 0.0           # 温度修正后的导通电阻 (仅MOSFET)
    _Eon_interp: float | None = None  # 插值得到的Eon (使用数组时)
    _Eoff_interp: float | None = None # 插值得到的Eoff (使用数组时)

    # === 状态 ===
    device_type: BoostDeviceType = BoostDeviceType.MOSFET
    warnings: List[str] = field(default_factory=list)
    is_valid: bool = False


# ============================================================================
# 计算引擎
# ============================================================================

class BoostCalculator:
    """Boost损耗分析计算引擎"""

    # ========================================================================
    # 线性插值工具 (可复用到其他拓扑)
    # ========================================================================


    @staticmethod
    def calculate(params: BoostInputParams) -> BoostResults:
        """执行完整Boost损耗计算"""
        res = BoostResults(device_type=params.device_type)
        warnings = []

        Vin = params.Vin; Vout = params.Vout; Iin = params.Iin
        fsw = params.fsw; Tj = params.Tj

        # ================================================================
        # 1. 占空比
        # ================================================================
        D = 1.0 - Vin / Vout
        res.D = D

        # CCM Boost: 电感平均电流 = 输入电流 Iin
        # 输出电流: Iout = Iin * (1-D)  (功率平衡: Vin*Iin = Vout*Iout)
        I_L = Iin
        res.I_L = I_L
        Iout = Iin * (1.0 - D)
        res.Iout = Iout

        # ================================================================
        # 2. 输入/输出功率
        # ================================================================
        Pin = Vin * Iin
        Pout = Vout * Iout
        res.Pin = Pin
        res.Pout = Pout

        # ================================================================
        # 3-7. 器件损耗计算 (按器件类型分支, 均使用I_L=Iin)
        # ================================================================
        if params.device_type == BoostDeviceType.MOSFET:
            # 3a. 温度修正导通电阻
            Rds_on_T = params.Rds_on_25 * (1.0 + params.alpha * (Tj - 25.0))
            res.Rds_on_T = Rds_on_T

            # 3b. MOSFET导通损耗: P_cond = Iin^2 * Rds_on_T * D
            P_cond = Iin**2 * Rds_on_T * D

            # 3c. MOSFET开关损耗
            #     优先使用Eon/Eoff数组插值, 否则用tr/tf线性近似
            if params.I_array and len(params.I_array) >= 2:
                Eon_i = linear_interp(
                    Iin, params.I_array, params.Eon_array)
                Eoff_i = linear_interp(
                    Iin, params.I_array, params.Eoff_array)
                P_sw = fsw * (Eon_i + Eoff_i)
                res._Eon_interp = Eon_i
                res._Eoff_interp = Eoff_i
            else:
                P_sw = 0.5 * Vout * Iin * (params.tr + params.tf) * fsw
                res._Eon_interp = None
                res._Eoff_interp = None
        else:
            # IGBT导通损耗: P_cond = Vce_sat * Iin * D
            P_cond = params.Vce_sat * Iin * D

            # IGBT开关损耗: P_sw = (Eon + Eoff) * fsw
            P_sw = (params.Eon + params.Eoff) * fsw

        res.P_cond = P_cond
        res.P_sw = P_sw

        # ================================================================
        # 4. 二极管导通损耗: P_diode_cond = Vf * Iin * (1-D)
        # ================================================================
        P_diode_cond = params.Vf * Iin * (1.0 - D)
        res.P_diode_cond = P_diode_cond

        # ================================================================
        # 5. 二极管反向恢复损耗: P_rr = Qrr * Vout * fsw
        # ================================================================
        P_rr = params.Qrr * Vout * fsw
        res.P_rr = P_rr

        # ================================================================
        # 6. 驱动芯片供电损耗: P_drv = Qg * (Von - Voff) * fsw
        # ================================================================
        P_drv = params.Qg * (params.Von - params.Voff) * fsw
        res.P_drv = P_drv

        # ================================================================
        # 7. 总损耗
        # ================================================================
        P_total = P_cond + P_sw + P_diode_cond + P_rr + P_drv
        res.P_total = P_total

        # ================================================================
        # 8. 效率
        # ================================================================
        if Pout + P_total > 0:
            res.efficiency = Pout / (Pout + P_total) * 100.0
        else:
            res.efficiency = 0.0

        # ================================================================
        # 9. 损耗占输出功率百分比
        # ================================================================
        if Pout > 0:
            res.ratio_cond = P_cond / Pout * 100.0
            res.ratio_sw = P_sw / Pout * 100.0
            res.ratio_diode_cond = P_diode_cond / Pout * 100.0
            res.ratio_rr = P_rr / Pout * 100.0
            res.ratio_drv = P_drv / Pout * 100.0
            res.ratio_total = P_total / Pout * 100.0

        # ================================================================
        # 验证警告
        # ================================================================
        if D < 0 or D > 1: warnings.append(f"占空比D={D:.3f}异常(Vin不能大于Vout)")
        if res.efficiency < 90: warnings.append(f"效率{res.efficiency:.1f}%偏低,请检查参数")
        if res.ratio_total > 20: warnings.append(f"总损耗占比{res.ratio_total:.1f}%偏高(>20%)")
        if P_total > Pout * 0.5: warnings.append(f"总损耗超过输出功率50%,设计不合理")

        res.warnings = warnings
        res.is_valid = (len(warnings) == 0)
        return res

    # ========================================================================
    # 逐步计算过程
    # ========================================================================

    @staticmethod
    def get_calculation_steps(params: BoostInputParams,
                               res: BoostResults) -> List[CalculationStep]:
        """生成逐步计算过程"""
        steps = []; step = 0

        step += 1
        steps.append(CalculationStep(step_num=step, title="占空比计算",
            formula_text="D = 1 - Vin / Vout",
            formula_latex=r"D = 1 - \frac{V_{in}}{V_{out}}",
            substitution=f"D = 1 - {params.Vin:.1f}V / {params.Vout:.1f}V",
            result=f"{res.D:.4f}", unit="-",
            note="CCM Boost电路占空比"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="电感/输入电流确认",
            formula_text="I_L = Iin (CCM电感电流=输入电流)",
            formula_latex=r"I_L = I_{in}",
            substitution=f"I_L = {params.Iin:.2f}A",
            result=f"{params.Iin:.2f}", unit="A",
            note="Boost CCM模式下电感串联在输入端"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="输出电流计算",
            formula_text="Iout = Iin * (1 - D)",
            formula_latex=r"I_{out} = I_{in} \cdot (1-D)",
            substitution=f"Iout = {params.Iin:.2f}A * (1-{res.D:.4f})",
            result=f"{res.Iout:.2f}", unit="A",
            note="功率平衡: Vin*Iin = Vout*Iout"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="输入功率计算",
            formula_text="Pin = Vin * Iin",
            formula_latex=r"P_{in} = V_{in} \cdot I_{in}",
            substitution=f"Pin = {params.Vin:.1f}V * {params.Iin:.2f}A",
            result=f"{res.Pin:.2f}", unit="W",
            note="Boost输入功率"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="输出功率计算",
            formula_text="Pout = Vout * Iout",
            formula_latex=r"P_{out} = V_{out} \cdot I_{out}",
            substitution=f"Pout = {params.Vout:.1f}V * {res.Iout:.2f}A",
            result=f"{res.Pout:.2f}", unit="W",
            note="Boost输出功率"))

        if params.device_type == BoostDeviceType.MOSFET:
            step += 1
            steps.append(CalculationStep(step_num=step, title="温度修正导通电阻",
                formula_text="Rds_on_T = Rds_on_25 * [1 + alpha * (Tj - 25)]",
                formula_latex=r"R_{ds(on)}(T) = R_{ds(on)25} \cdot [1 + \alpha(T_j - 25)]",
                substitution=f"Rds_on_T = {params.Rds_on_25:.3f} * [1 + {params.alpha:.4f}*({params.Tj:.0f}-25)]",
                result=f"{res.Rds_on_T:.4f}", unit="Ohm",
                note="MOSFET导通电阻随温度升高而增大"))

            step += 1
            steps.append(CalculationStep(step_num=step, title="MOSFET导通损耗",
                formula_text="P_cond = Iin^2 * Rds_on_T * D",
                formula_latex=r"P_{cond} = I_{in}^2 \cdot R_{ds(on)}(T) \cdot D",
                substitution=f"P_cond = {params.Iin:.2f}^2 * {res.Rds_on_T:.4f} * {res.D:.4f}",
                result=f"{res.P_cond:.4f}", unit="W",
                note="开关导通时流过Iin=电感电流, 占空比D"))

            step += 1
            if params.I_array and len(params.I_array) >= 2 and res._Eon_interp is not None:
                # 数组插值模式
                steps.append(CalculationStep(step_num=step, title="MOSFET开关损耗 (Eon/Eoff插值)",
                    formula_text="Eon_interp=interp(Iin,I_array,Eon_array)\nEoff_interp=interp(Iin,I_array,Eoff_array)\nP_sw=fsw*(Eon+Eoff)",
                    formula_latex=r"P_{sw} = f_{sw} \cdot (E_{on}(I_{in}) + E_{off}(I_{in}))",
                    substitution=(f"Iin={params.Iin:.1f}A, 插值区间I_array=[{min(params.I_array):.1f}~{max(params.I_array):.1f}]A\n"
                                 f"Eon_interp={res._Eon_interp*1e6:.2f}uJ, Eoff_interp={res._Eoff_interp*1e6:.2f}uJ"),
                    result=f"{res.P_sw:.4f}", unit="W",
                    note=f"线性插值: Eon/Eoff从{len(params.I_array)}个数据点插值得到"))
            else:
                # tr/tf线性近似模式
                steps.append(CalculationStep(step_num=step, title="MOSFET开关损耗 (tr/tf近似)",
                    formula_text="P_sw = 0.5 * Vout * Iin * (tr+tf) * fsw",
                    formula_latex=r"P_{sw} = 0.5 \cdot V_{out} \cdot I_{in} \cdot (t_r+t_f) \cdot f_{sw}",
                    substitution=f"P_sw = 0.5*{params.Vout:.0f}*{params.Iin:.1f}*({params.tr*1e9:.0f}+{params.tf*1e9:.0f})ns*{params.fsw/1000:.0f}kHz",
                    result=f"{res.P_sw:.4f}", unit="W",
                    note="关断瞬间电流为Iin, 基于开关波形线性近似"))
        else:
            step += 1
            steps.append(CalculationStep(step_num=step, title="IGBT导通损耗",
                formula_text="P_cond = Vce_sat * Iin * D",
                formula_latex=r"P_{cond} = V_{ce(sat)} \cdot I_{in} \cdot D",
                substitution=f"P_cond = {params.Vce_sat:.2f}V * {params.Iin:.2f}A * {res.D:.4f}",
                result=f"{res.P_cond:.4f}", unit="W",
                note="IGBT导通时流过Iin=电感电流"))

            step += 1
            steps.append(CalculationStep(step_num=step, title="IGBT开关损耗",
                formula_text="P_sw = (Eon + Eoff) * fsw",
                formula_latex=r"P_{sw} = (E_{on} + E_{off}) \cdot f_{sw}",
                substitution=f"P_sw = ({params.Eon*1e3:.2f}+{params.Eoff*1e3:.2f})mJ * {params.fsw/1000:.0f}kHz",
                result=f"{res.P_sw:.4f}", unit="W",
                note="IGBT开通+关断能量损耗"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="二极管导通损耗",
            formula_text="P_diode_cond = Vf * Iin * (1-D)",
            formula_latex=r"P_{diode,cond} = V_f \cdot I_{in} \cdot (1-D)",
            substitution=f"P_diode_cond = {params.Vf:.1f}V * {params.Iin:.2f}A * (1-{res.D:.4f})",
            result=f"{res.P_diode_cond:.4f}", unit="W",
            note="二极管导通(1-D)期间流过Iin"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="二极管反向恢复损耗",
            formula_text="P_rr = Qrr * Vout * fsw",
            formula_latex=r"P_{rr} = Q_{rr} \cdot V_{out} \cdot f_{sw}",
            substitution=f"P_rr = {params.Qrr*1e9:.1f}nC * {params.Vout:.0f}V * {params.fsw/1000:.0f}kHz",
            result=f"{res.P_rr:.4f}", unit="W",
            note="二极管反向恢复电荷损耗"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="驱动芯片供电损耗",
            formula_text="P_drv = Qg * (Von - Voff) * fsw",
            formula_latex=r"P_{drv} = Q_g \cdot (V_{on} - V_{off}) \cdot f_{sw}",
            substitution=f"P_drv = {params.Qg*1e9:.1f}nC * ({params.Von:.0f}V-({params.Voff:.0f}V)) * {params.fsw/1000:.0f}kHz",
            result=f"{res.P_drv:.4f}", unit="W",
            note="驱动芯片供电损耗(Von正压-Voff负压)"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="总损耗",
            formula_text="P_total = P_cond + P_sw + P_diode_cond + P_rr + P_drv",
            formula_latex=r"P_{total} = \sum P_i",
            substitution=f"P_total = {res.P_cond:.3f}+{res.P_sw:.3f}+{res.P_diode_cond:.3f}+{res.P_rr:.3f}+{res.P_drv:.3f}",
            result=f"{res.P_total:.4f}", unit="W",
            note="全部损耗分量之和"))

        step += 1
        steps.append(CalculationStep(step_num=step, title="转换效率",
            formula_text="eta = Pout / (Pout + P_total) * 100%",
            formula_latex=r"\eta = \frac{P_{out}}{P_{out} + P_{total}} \times 100\%",
            substitution=f"eta = {res.Pout:.1f}W / ({res.Pout:.1f}+{res.P_total:.4f})W",
            result=f"{res.efficiency:.2f}%", unit="%",
            note="Boost DC/DC转换效率"))

        # 损耗占比
        step += 1
        steps.append(CalculationStep(step_num=step, title="损耗占比汇总",
            formula_text="ratio_i = P_i / Pout * 100%",
            formula_latex=r"ratio_i = \frac{P_i}{P_{out}} \times 100\%",
            substitution="各项损耗 / 输出功率",
            result=(f"导通:{res.ratio_cond:.2f}% 开关:{res.ratio_sw:.2f}% "
                     f"二极管:{res.ratio_diode_cond:.2f}% 恢复:{res.ratio_rr:.2f}% "
                     f"驱动:{res.ratio_drv:.2f}% 总:{res.ratio_total:.2f}%"),
            unit="%",
            note="各损耗占总输出功率百分比"))

        return steps

    # ========================================================================
    # 温度/电流扫描
    # ========================================================================

    @staticmethod
    def compute_temperature_sweep(params: BoostInputParams,
                                    Tj_min: float = 25.0,
                                    Tj_max: float = 150.0,
                                    num_points: int = 20) -> Tuple[np.ndarray, dict]:
        """
        温度扫描: 改变结温Tj, 重新计算损耗

        Returns:
            temps: 温度数组
            sweep: {'P_cond':[], 'P_sw':[], 'P_total':[], 'efficiency':[]}
        """
        temps = np.linspace(Tj_min, Tj_max, num_points)
        sweep = {'P_cond': [], 'P_sw': [], 'P_total': [], 'efficiency': []}

        for Tj in temps:
            p = BoostInputParams(
                Vin=params.Vin, Vout=params.Vout, Iin=params.Iin,
                fsw=params.fsw, Tj=Tj, device_type=params.device_type,
                Rds_on_25=params.Rds_on_25, tr=params.tr, tf=params.tf,
                Qg=params.Qg, Von=params.Von, Voff=params.Voff, alpha=params.alpha,
                Vce_sat=params.Vce_sat, Eon=params.Eon, Eoff=params.Eoff,
                Vf=params.Vf, Qrr=params.Qrr,
            )
            r = BoostCalculator.calculate(p)
            sweep['P_cond'].append(r.P_cond)
            sweep['P_sw'].append(r.P_sw)
            sweep['P_total'].append(r.P_total)
            sweep['efficiency'].append(r.efficiency)

        for k in sweep:
            sweep[k] = np.array(sweep[k])
        return temps, sweep

    @staticmethod
    def compute_current_sweep(params: BoostInputParams,
                                Iin_min_ratio: float = 0.1,
                                Iin_max_ratio: float = 2.0,
                                num_points: int = 20) -> Tuple[np.ndarray, dict]:
        """
        电流扫描: 改变输入电流Iin, 重新计算损耗

        Returns:
            currents: 电流数组
            sweep: 同温度扫描
        """
        currents = np.linspace(params.Iin * Iin_min_ratio,
                                params.Iin * Iin_max_ratio, num_points)
        sweep = {'P_cond': [], 'P_sw': [], 'P_total': [], 'efficiency': []}

        for I in currents:
            p = BoostInputParams(
                Vin=params.Vin, Vout=params.Vout, Iin=I,
                fsw=params.fsw, Tj=params.Tj, device_type=params.device_type,
                Rds_on_25=params.Rds_on_25, tr=params.tr, tf=params.tf,
                Qg=params.Qg, Von=params.Von, Voff=params.Voff, alpha=params.alpha,
                Vce_sat=params.Vce_sat, Eon=params.Eon, Eoff=params.Eoff,
                Vf=params.Vf, Qrr=params.Qrr,
            )
            r = BoostCalculator.calculate(p)
            sweep['P_cond'].append(r.P_cond)
            sweep['P_sw'].append(r.P_sw)
            sweep['P_total'].append(r.P_total)
            sweep['efficiency'].append(r.efficiency)

        for k in sweep:
            sweep[k] = np.array(sweep[k])
        return currents, sweep
