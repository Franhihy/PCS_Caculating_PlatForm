"""
PCS计算平台 - SOGI参数计算页面

继承 BasePage，仅实现 SOGI 特有的输入、计算、显示和导出逻辑。
"""

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QFormLayout, QVBoxLayout,
    QDoubleSpinBox, QPushButton, QTabWidget,
    QTextBrowser, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

from core.SOGI_calculator import SOGIInputParams, SOGIResults, SOGICalculator
from plots.bode_plot import BodeCanvas
from gui.base_page import BasePage


CSS_SPIN_CUSTOM = (
    "QDoubleSpinBox{padding:4px 8px;font-size:13px;"
    "border:1px solid #ccc;border-radius:3px}"
    "QDoubleSpinBox:focus{border-color:#0078d4}"
)


class SOGIPage(BasePage):
    """SOGI参数计算页面"""

    module_name = "SOGI"
    BTN_PDF_TEXT = "生成SOGI计算书PDF"
    STEPS_TITLE = "SOGI参数计算过程"
    PDF_TITLE = "保存SOGI计算书"
    PDF_DEFAULT_NAME = "SOGI_Parameter_Report.pdf"

    def _setup_inputs(self) -> QWidget:
        """构建左侧输入面板."""
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        input_group = QGroupBox("SOGI输入参数")
        form = QFormLayout(input_group)
        form.setSpacing(8)

        self.spin_Vamp = self._spin(10, 1000, 311, 1, "V",
                                    width=150, style=CSS_SPIN_CUSTOM)
        self.spin_fgrid = self._spin(1, 400, 50, 1, "Hz",
                                     width=150, style=CSS_SPIN_CUSTOM)
        self.spin_bw = self._spin(0.1, 50, 5, 1, "Hz",
                                  width=150, style=CSS_SPIN_CUSTOM)
        self.spin_fs = self._spin(500, 100000, 10000, 0, "Hz",
                                  width=150, style=CSS_SPIN_CUSTOM)

        form.addRow("电网电压幅值:", self.spin_Vamp)
        form.addRow("电网频率:", self.spin_fgrid)
        form.addRow("滤波器带宽:", self.spin_bw)
        form.addRow("采样频率:", self.spin_fs)

        left_layout.addWidget(input_group)

        self.btn_calc = self._create_calc_button(left_layout)
        self.btn_pdf = self._create_pdf_button(left_layout)
        left_layout.addStretch()
        return left

    # ========================================================================
    # 额外选项卡和图表区
    # ========================================================================

    def _setup_extra_tabs(self, tabs: QTabWidget):
        """添加传递函数选项卡."""
        self.text_tf = QTextBrowser()
        self.text_tf.setStyleSheet("font-size:13px;padding:8px;background-color:#fafafa")
        tabs.addTab(self.text_tf, "传递函数")

    def _setup_plot_area(self, layout):
        """添加 Bode 图."""
        self.bode = BodeCanvas()
        layout.addWidget(self.bode, stretch=4)

    # ========================================================================
    # 计算核心
    # ========================================================================

    def _get_calculator_class(self):
        return SOGICalculator

    def _do_calculate(self):
        """执行SOGI参数计算."""
        params = SOGIInputParams(
            V_amplitude=self.spin_Vamp.value(),
            f_grid=self.spin_fgrid.value(),
            bandwidth=self.spin_bw.value(),
            fs=self.spin_fs.value(),
        )
        errors = params.validate()
        if errors:
            QMessageBox.warning(self, "SOGI输入参数警告",
                                "\n".join(f"  - {e}" for e in errors))

        results = SOGICalculator.calculate(params)
        self.STEPS_SUBTITLE = (
            f"电网频率={params.f_grid:.0f}Hz | 带宽={params.bandwidth:.1f}Hz"
            f" | 采样率={params.fs:.0f}Hz | 电压幅值={params.V_amplitude:.0f}V"
        )
        return params, results

    def _status_message(self, results) -> str:
        return f"[SOGI] k={results.k:.4f}, Q={results.Q:.2f}"

    # ========================================================================
    # 结果表格
    # ========================================================================

    def _get_table_rows(self, params, results) -> list:
        rows = [
            ("--- 输入参数 ---", "", ""),
            ("电网电压幅值", f"{params.V_amplitude:.1f}", "V"),
            ("电网频率", f"{params.f_grid:.1f}", "Hz"),
            ("滤波器带宽", f"{params.bandwidth:.1f}", "Hz"),
            ("采样频率", f"{params.fs:.0f}", "Hz"),
            ("--- 基本参数 ---", "", ""),
            ("谐振角频率 w0", f"{results.w0:.4f}", "rad/s"),
            ("SOGI增益 k", f"{results.k:.4f}", "-"),
            ("带宽参数 wc", f"{results.wc:.4f}", "rad/s"),
            ("品质因数 Q", f"{results.Q:.2f}", "-"),
            ("采样周期 Ts", f"{results.Ts*1e6:.1f} us", "s"),
        ]
        for m in results.get_all_methods():
            rows.append((f"--- {m.name} ---", "", ""))
            rows.extend([
                ("a11", f"{m.a11:.6f}", "Ad[0,0]"),
                ("a12", f"{m.a12:.6f}", "Ad[0,1]"),
                ("a21", f"{m.a21:.6f}", "Ad[1,0]"),
                ("a22", f"{m.a22:.6f}", "Ad[1,1]"),
                ("b1", f"{m.b1:.6f}", "Bd[0]"),
                ("b2", f"{m.b2:.6f}", "Bd[1]"),
                ("|eig|", f"[{m.eig1_mag:.4f},{m.eig2_mag:.4f}]", "-"),
                ("稳定", "是" if m.stable else "否", ""),
            ])
        rows.extend([
            ("--- 动态响应 ---", "", ""),
            ("稳定时间 (4*tau)", f"{results.settling_time_4t*1e3:.1f} ms", "s"),
            ("稳定周期数", f"{results.settling_cycles:.1f}", "个电网周期"),
            ("--- 设计状态 ---", "", ""),
            ("结论", "合格" if results.is_valid else "需优化", ""),
        ])
        return rows

    # ========================================================================
    # 传递函数 + Bode图
    # ========================================================================

    def _show_extra_displays(self):
        self._show_transfer_function()

    def _show_transfer_function(self):
        import sympy as sp
        H_d, H_q, s, k_sym, w0_sym = SOGICalculator.get_transfer_function_sympy()
        results = self._current_results

        html = (
            '<html><head><style>'
            "body{font-family:'Segoe UI',Consolas,monospace}"
            'h2{color:#333;border-bottom:2px solid #0078d4}'
            'h3{color:#0078d4;margin-top:16px}'
            'h4{color:#333;margin-top:12px}'
            'pre{background:#f0f0f0;padding:12px;border-radius:4px;'
            'font-size:13px;overflow-x:auto}'
            '</style></head><body>'
            '<h2>SOGI传递函数推导</h2>'
            f"<h3>连续域带通: H_d(s) = v'(s)/v_in(s)</h3>"
            f'<pre>{sp.pretty(H_d, use_unicode=True)}</pre>'
            f"<h3>连续域低通: H_q(s) = qv'(s)/v_in(s)</h3>"
            f'<pre>{sp.pretty(H_q, use_unicode=True)}</pre>'
            '<h3>三种离散化方法对比</h3>'
        )
        for m in results.get_all_methods():
            html += (
                f'<h4>{m.name}</h4><pre>'
                f'Ad=[[{m.a11:.6f},{m.a12:.6f}],[{m.a21:.6f},{m.a22:.6f}]]\n'
                f'Bd=[{m.b1:.6f},{m.b2:.6f}]\n'
                f'|eig|=[{m.eig1_mag:.6f},{m.eig2_mag:.6f}]'
                f" stable={'Y' if m.stable else 'N'}</pre>"
            )

        html += '<h3>C代码实现</h3>'
        for m in results.get_all_methods():
            html += (
                f'<h4>{m.name}</h4><pre>'
                f'// SOGI - {m.name_en}\n'
                f'float a11={m.a11:.6f}f,a12={m.a12:.6f}f,'
                f'a21={m.a21:.6f}f,a22={m.a22:.6f}f;\n'
                f'float b1={m.b1:.6f}f,b2={m.b2:.6f}f;\n'
                'float x1_new=a11*x1+a12*x2+b1*vin;\n'
                'float x2_new=a21*x1+a22*x2+b2*vin;\nx1=x1_new;x2=x2_new;\n</pre>'
            )
        html += '</body></html>'
        self.text_tf.setHtml(html)

    def _show_charts(self, results):
        """更新 Bode 图."""
        freq = SOGICalculator.compute_frequency_response(
            results.k, results.w0,
            f_min=max(0.1, results.w0 / (2 * np.pi) / 100),
            f_max=min(results.w0 / (2 * np.pi) * 20, 5000))
        self.bode.plot_sogi(freq, results.w0 / (2 * np.pi))

    # ========================================================================
    # PDF导出
    # ========================================================================

    def _export_pdf_impl(self) -> bool:
        filepath, _ = QFileDialog.getSaveFileName(
            self, self.PDF_TITLE, self.PDF_DEFAULT_NAME, "PDF Files (*.pdf)")
        if not filepath:
            return False
        from reports.sogi_pdf import SOGIPDFGenerator
        SOGIPDFGenerator().generate(
            filepath, self._current_params, self._current_results,
            bode_image=self.bode.get_image())
        self.status_changed.emit(f"SOGI PDF已保存: {filepath}", False)
        self._ask_open(filepath)
        return True
