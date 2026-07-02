"""PCS Platform - SOGI Parameter Calculation PDF Report (refactored)"""
from io import BytesIO
from reportlab.platypus import Paragraph
from reports.base_report import BaseReportGenerator
from core.SOGI_calculator import SOGICalculator


class SOGIPDFGenerator(BaseReportGenerator):
    """SOGI parameter calculation PDF report"""

    def __init__(self):
        super().__init__(title="SOGI参数计算书", author="PCS计算平台 v1.0.5")

    def generate(self, filepath, params, results, bode_image=None):
        story = []
        self.cover(story,
            title="SOGI参数计算书",
            subtitle="二阶广义积分器参数设计报告",
            extra_info="参考文献: Ciobotaru, Teodorescu & Blaabjerg (2006)")
        # §1 Input
        story.append(self.h1("1. 设计输入参数"))
        input_data = [
            ["参数名称", "符号", "数值", "单位"],
            ["电网电压幅值", "V_amplitude", f"{params.V_amplitude:.1f}", "V"],
            ["电网频率", "f_grid", f"{params.f_grid:.1f}", "Hz"],
            ["滤波器带宽", "BW", f"{params.bandwidth:.1f}", "Hz"],
            ["采样频率", "fs", f"{params.fs:.0f}", "Hz"],
        ]
        story.append(self.table(input_data))
        story.append(self.body(""))
        # §2 Calculation steps
        story.append(self.h1("2. 详细计算过程"))
        steps = SOGICalculator.get_calculation_steps(params, results)
        self.render_steps(story, steps)
        # §3 Results
        story.append(self.h1("3. 结果汇总"))
        story.append(self.h2("3.1 基本参数"))
        summary = [
            ["参数", "符号", "数值", "单位"],
            ["谐振角频率", "w0", f"{results.w0:.4f}", "rad/s"],
            ["SOGI增益", "k", f"{results.k:.4f}", "-"],
            ["带宽参数", "wc", f"{results.wc:.4f}", "rad/s"],
            ["品质因数", "Q", f"{results.Q:.2f}", "-"],
            ["采样周期", "Ts", f"{results.Ts*1e6:.1f} us", "s"],
        ]
        story.append(self.table(summary))
        story.append(self.h2("3.2 离散状态空间矩阵 (三种方法对比)"))
        for method in results.get_all_methods():
            story.append(self.body(f"<b>{method.name}</b>"))
            dss = [
                ["系数", "数值", "说明"],
                ["a11", f"{method.a11:.6f}", "Ad[0,0]"],
                ["a12", f"{method.a12:.6f}", "Ad[0,1]"],
                ["a21", f"{method.a21:.6f}", "Ad[1,0]"],
                ["a22", f"{method.a22:.6f}", "Ad[1,1]"],
                ["b1", f"{method.b1:.6f}", "Bd[0]"],
                ["b2", f"{method.b2:.6f}", "Bd[1]"],
                ["|eig1|", f"{method.eig1_mag:.6f}", ""],
                ["|eig2|", f"{method.eig2_mag:.6f}", ""],
                ["稳定", "是" if method.stable else "否", ""],
            ]
            story.append(self.table(dss))
        story.append(self.h2("3.3 动态响应"))
        dyn = [
            ["参数", "数值", "单位"],
            ["稳定时间 (4*tau)", f"{results.settling_time_4t*1e3:.1f} ms", "s"],
            ["稳定周期数", f"{results.settling_cycles:.1f}", "个电网周期"],
        ]
        story.append(self.table(dyn))
        # §4 Verification
        story.append(self.h1("4. 设计验证"))
        vf = [
            f"SOGI增益 k={results.k:.4f} (推荐 0.1~2.0)",
            f"带宽 BW={params.bandwidth:.1f}Hz (推荐 3~10Hz)",
            f"采样比 fs/f_grid={params.fs/params.f_grid:.0f} (>10)",
            f"稳定因子 Ts*w0*k={results.Ts*results.w0*results.k:.4f} (<0.5 for FE)",
        ]
        for v in vf: story.append(self.body(v))
        if results.is_valid:
            story.append(self.result("所有设计约束满足, SOGI参数设计合格。"))
        else:
            for w in results.warnings: story.append(self.warn(w))
        # §5 Transfer functions + C code
        story.append(self.h1("5. 传递函数"))
        story.append(self.h2("5.1 连续域传递函数"))
        story.append(self.formula("H_d(s)=k*w0*s/(s^2+k*w0*s+w0^2)   [Band-Pass: v']"))
        story.append(self.formula("H_q(s)=k*w0^2/(s^2+k*w0*s+w0^2)   [Low-Pass: qv']"))
        story.append(self.h2("5.2 离散状态方程"))
        story.append(self.formula("x1[n+1]=a11*x1[n]+a12*x2[n]+b1*vin[n]"))
        story.append(self.formula("x2[n+1]=a21*x1[n]+a22*x2[n]+b2*vin[n]"))
        story.append(self.body("输出: v'(带通滤波)=x1[n], qv'(正交信号)=x2[n]"))
        # C code
        story.append(self.h2("5.3 C语言实现 (三种方法)"))
        for method in results.get_all_methods():
            story.append(self.body(f"<b>{method.name}</b>"))
            cc = (f"// SOGI - {method.name_en}\n"
                  f"float a11={method.a11:.6f}f,a12={method.a12:.6f}f;\n"
                  f"float a21={method.a21:.6f}f,a22={method.a22:.6f}f;\n"
                  f"float b1={method.b1:.6f}f,b2={method.b2:.6f}f;\n"
                  f"float x1_new=a11*x1+a12*x2+b1*vin;\n"
                  f"float x2_new=a21*x1+a22*x2+b2*vin;\n"
                  f"x1=x1_new;x2=x2_new;")
            story.append(self.formula(cc.replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;")))
        # Bode
        if bode_image:
            story.append(self.h2("5.4 频率响应 (Bode图)"))
            story.append(self.embed_image(bode_image))
            story.append(Paragraph("图1: SOGI频率响应Bode图 (蓝=H_d带通, 红虚线=H_q低通)", self.s["footer"]))
        # Footer
        self.footer(story)
        self.build(filepath, story)
