"""PCS Platform - LCL Filter Design PDF Report (refactored with BaseReportGenerator)"""
from reportlab.platypus import Paragraph
from reports.base_report import BaseReportGenerator
from core.LCL_calculator import LCLCalculator


class PDFGenerator(BaseReportGenerator):
    """LCL filter design PDF report"""

    def __init__(self):
        super().__init__(title="LCL滤波器设计计算书", author="PCS Platform v1.0.5")

    def generate(self, filepath, params, results, bode_image=None):
        story = []
        # Cover
        self.cover(story,
            title="LCL滤波器设计计算书",
            subtitle="Grid-Connected Inverter LCL Filter Design Report",
            extra_info="参考标准: IEEE 519-2014 | Liserre, Blaabjerg & Hansen (2005)")
        # §1 Input
        story.append(self.h1("1. 设计输入参数"))
        input_data = [
            ["参数名称", "符号", "数值", "单位"],
            ["拓扑类型", "-", params.phase_type.label_cn(), "-"],
            ["额定功率", "P_nominal", f"{params.P_nominal:.1f}", "kW"],
            ["电网电压", "V_nominal", f"{params.V_nominal:.0f}", "V (RMS)"],
            ["电网频率", "f_grid", f"{params.f_grid:.1f}", "Hz"],
            ["开关频率", "f_sw", f"{params.f_sw:.0f}", "Hz"],
            ["直流母线电压", "V_dc", f"{params.V_dc:.0f}", "V"],
            ["电流纹波率", "r_ripple", f"{params.ripple_rate:.1f}", "%"],
        ]
        story.append(self.table(input_data))
        story.append(self.body(""))
        # §2 Design constraints
        story.append(self.h1("2. 设计约束条件"))
        constraints = [
            f"- 电流纹波率: = {params.ripple_rate:.0f}% x I_rated_peak",
            f"- 电容无功功率: Qc <= 5% x P_nominal",
            f"- 谐振频率: 10xf_grid < fr < 0.5xf_sw",
            f"- 开关频率衰减: A_sw < -40dB",
            f"- 电感比: r = L2/L1 = 0.6",
        ]
        for c in constraints: story.append(self.body(c))
        story.append(self.body(""))
        # §3 Calculation steps
        story.append(self.h1("3. 详细计算过程"))
        steps = LCLCalculator.get_calculation_steps(params, results)
        self.render_steps(story, steps)
        # §4 Results summary
        story.append(self.h1("4. 设计结果汇总"))
        story.append(self.h2("4.1 滤波器元件参数"))
        summary = [
            ["参数", "符号", "计算值", "单位"],
            ["逆变器侧电感", "L1", f"{results.L1*1e6:.1f} uH", "H"],
            ["电网侧电感", "L2", f"{results.L2*1e6:.1f} uH", "H"],
            ["滤波电容", "Cf", f"{results.Cf*1e6:.2f} uF", "F"],
            ["阻尼电阻", "Rd", f"{results.Rd:.2f}", "Ohm"],
            ["电感比", "r", f"{results.r:.2f}", "-"],
        ]
        story.append(self.table(summary))
        story.append(self.h2("4.2 谐振特性与滤波性能"))
        perf = [
            ["参数", "符号", "数值", "单位", "状态"],
            ["谐振频率", "fr", f"{results.fr:.1f}", "Hz", "OK" if results.fr_valid else "NG"],
            ["谐振频率下限", "fr_min", f"{results.fr_min:.0f}", "Hz", "-"],
            ["谐振频率上限", "fr_max", f"{results.fr_max:.0f}", "Hz", "-"],
            ["阻尼比", "zeta", f"{results.damping_ratio:.2f}", "-", "-"],
            ["开关频率衰减", "A_sw", f"{results.attenuation_sw_db:.1f}", "dB", "OK" if results.attenuation_valid else "NG"],
            ["纹波衰减倍数", "-", f"{results.attenuation_sw_times:.0f}", "倍", "-"],
        ]
        story.append(self.table(perf))
        # §5 Design verification
        story.append(self.h1("5. 设计验证与结论"))
        story.append(self.h2("5.1 约束条件验证"))
        vf = [
            f"谐振频率约束: 10xf_grid={results.fr_min:.0f}Hz < fr={results.fr:.1f}Hz < 0.5xf_sw={results.fr_max:.0f}Hz -> {'OK' if results.fr_valid else 'NG'}",
            f"开关频率衰减: A_sw={results.attenuation_sw_db:.1f}dB {'<-40dB OK' if results.attenuation_valid else '>= -40dB NG'}",
            f"阻尼比: zeta={results.damping_ratio:.2f} (0.3~0.7)",
        ]
        for v in vf: story.append(self.body(v))
        story.append(self.h2("5.2 设计结论"))
        if results.is_valid:
            story.append(self.body(f"滤波器设计合格。fr={results.fr:.1f}Hz, A_sw={results.attenuation_sw_db:.1f}dB。"))
        else:
            for w in results.warnings: story.append(self.warn(w))
        # §6 Transfer function
        story.append(self.h1("6. 传递函数与频率响应"))
        story.append(self.h2("6.1 LCL滤波器传递函数"))
        story.append(self.formula("G(s)=(1+s*Rd*Cf)/[s^3*L1*L2*Cf+s^2*Rd*Cf*(L1+L2)+s*(L1+L2)]"))
        story.append(self.formula("fr=(1/2pi)*sqrt[(L1+L2)/(L1*L2*Cf)]"))
        # Bode plot
        if bode_image:
            story.append(self.h2("6.2 频率响应曲线 (Bode图)"))
            story.append(self.embed_image(bode_image))
            story.append(Paragraph("图1: LCL滤波器频率响应Bode图", self.s["footer"]))
        # Footer
        self.footer(story)
        self.build(filepath, story)
