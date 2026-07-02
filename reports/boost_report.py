"""PCS Platform - Boost Loss Analysis PDF Report (refactored)"""
from io import BytesIO
from reportlab.platypus import Paragraph
from reports.base_report import BaseReportGenerator
from core.Boost_calculator import BoostCalculator


class BoostReportGenerator(BaseReportGenerator):
    """Boost loss analysis PDF report"""

    def __init__(self):
        super().__init__(title="Boost损耗分析计算书", author="PCS计算平台 v1.0.5")

    def generate(self, filepath, params, results, sweep_data, chart_images):
        story = []
        self.cover(story,
            title="Boost DC/DC 损耗分析计算书",
            subtitle="Boost Converter Loss Analysis Report",
            extra_info=f"器件型号: {params.device_model} | 厂家: {params.device_mfr} | 器件类型: {params.device_type.value}")
        # §1 Input
        story.append(self.h1("1. 设计输入参数"))
        input_data = [
            ["参数", "数值", "单位"],
            ["器件类型", params.device_type.value, ""],
            ["输入电压 Vin", f"{params.Vin:.1f}", "V"],
            ["输出电压 Vout", f"{params.Vout:.1f}", "V"],
            ["输入电流 Iin", f"{params.Iin:.2f}", "A"],
            ["开关频率 fsw", f"{params.fsw/1000:.1f}", "kHz"],
            ["结温 Tj", f"{params.Tj:.0f}", "℃"],
        ]
        if params.I_array:
            input_data.append(["I_array (A)", str(params.I_array), ""])
            input_data.append(["Eon_array (uJ)", str([f"{v*1e6:.1f}" for v in params.Eon_array]), ""])
            input_data.append(["Eoff_array (uJ)", str([f"{v*1e6:.1f}" for v in params.Eoff_array]), ""])
        story.append(self.table(input_data))
        story.append(self.body(""))
        # §2 Calculation steps
        story.append(self.h1("2. 详细计算过程"))
        steps = BoostCalculator.get_calculation_steps(params, results)
        self.render_steps(story, steps)
        # §3 Results
        story.append(self.h1("3. 结果汇总"))
        summary = [
            ["参数", "数值", "单位"],
            ["占空比 D", f"{results.D:.4f}", "-"],
            ["电感电流 I_L (=Iin)", f"{results.I_L:.2f}", "A"],
            ["输出电流 Iout", f"{results.Iout:.2f}", "A"],
            ["输入功率 Pin", f"{results.Pin:.2f}", "W"],
            ["输出功率 Pout", f"{results.Pout:.2f}", "W"],
            ["导通损耗 P_cond", f"{results.P_cond:.4f}", "W"],
            ["开关损耗 P_sw", f"{results.P_sw:.4f}", "W"],
            ["二极管导通损耗", f"{results.P_diode_cond:.4f}", "W"],
            ["二极管恢复损耗", f"{results.P_rr:.4f}", "W"],
            ["驱动芯片供电损耗", f"{results.P_drv:.4f}", "W"],
            ["总损耗 P_total", f"{results.P_total:.4f}", "W"],
            ["转换效率 eta", f"{results.efficiency:.2f}", "%"],
        ]
        story.append(self.table(summary))
        # §4 Loss ratios
        story.append(self.h1("4. 损耗占比分析"))
        ratio_data = [
            ["损耗分量", "占比", ""],
            ["导通损耗", f"{results.ratio_cond:.2f}%", ""],
            ["开关损耗", f"{results.ratio_sw:.2f}%", ""],
            ["二极管导通损耗", f"{results.ratio_diode_cond:.2f}%", ""],
            ["二极管恢复损耗", f"{results.ratio_rr:.2f}%", ""],
            ["驱动芯片供电", f"{results.ratio_drv:.2f}%", ""],
            ["总损耗占比", f"{results.ratio_total:.2f}%", ""],
        ]
        story.append(self.table(ratio_data))
        # §5 Charts
        if chart_images:
            story.append(self.h1("5. 图表分析"))
            names = [('bar','5.1 损耗柱状图'),('pie','5.2 损耗占比饼图'),
                     ('temp','5.3 温度扫描曲线'),('current','5.4 电流扫描曲线')]
            for key, title in names:
                if chart_images.get(key):
                    story.append(self.h2(title))
                    story.append(self.embed_image(chart_images[key]))
        # §6 Conclusion
        story.append(self.h1("6. 设计结论"))
        if results.is_valid:
            story.append(self.body(
                f"Vin={params.Vin:.0f}V Vout={params.Vout:.0f}V Iin={params.Iin:.1f}A "

                f"fsw={params.fsw/1000:.0f}kHz Tj={params.Tj:.0f}℃下, "

                f"总损耗{results.P_total:.2f}W, 效率{results.efficiency:.2f}%。"

                f"导通占{results.ratio_cond:.1f}%, 开关占{results.ratio_sw:.1f}%。"))
        else:
            for w in results.warnings: story.append(self.warn(w))
        self.footer(story)
        self.build(filepath, story)
