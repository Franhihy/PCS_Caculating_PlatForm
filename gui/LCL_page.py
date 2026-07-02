"""
PCS计算平台 - LCL滤波器设计页面

继承 BasePage，仅实现 LCL 特有的输入、计算、显示和导出逻辑。
"""

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QFormLayout, QVBoxLayout,
    QDoubleSpinBox, QPushButton, QLabel, QTabWidget,
    QTextBrowser, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QComboBox, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from core.LCL_calculator import LCLInputParams, LCLResults, LCLCalculator, PhaseType
from plots.bode_plot import BodeCanvas
from gui.base_page import BasePage


CSS_SPIN_CUSTOM = (
    "QDoubleSpinBox{padding:4px 8px;font-size:13px;"
    "border:1px solid #ccc;border-radius:3px}"
    "QDoubleSpinBox:focus{border-color:#0078d4}"
)


class LCLPage(BasePage):
    """LCL滤波器设计页面"""

    module_name = "LCL"
    BTN_PDF_TEXT = "生成LCL计算书PDF"
    STEPS_TITLE = "LCL滤波器设计计算过程"
    PDF_TITLE = "保存LCL计算书"
    PDF_DEFAULT_NAME = "LCL_Filter_Design_Report.pdf"

    def _setup_inputs(self) -> QWidget:
        """构建左侧输入面板."""
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        input_group = QGroupBox("输入参数")
        form = QFormLayout(input_group)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.spin_P = self._spin(0.1, 10000, 10, 1, "kW", width=180, style=CSS_SPIN_CUSTOM)
        self.spin_V = self._spin(100, 1000, 380, 0, "V", width=180, style=CSS_SPIN_CUSTOM)
        self.spin_fg = self._spin(1, 400, 50, 1, "Hz", width=180, style=CSS_SPIN_CUSTOM)
        self.spin_fsw = self._spin(500, 50000, 10000, 0, "Hz", width=180, style=CSS_SPIN_CUSTOM)
        self.spin_Vdc = self._spin(100, 2000, 700, 0, "V", width=180, style=CSS_SPIN_CUSTOM)
        self.spin_rip = self._spin(5, 50, 20, 1, "%", width=180, style=CSS_SPIN_CUSTOM)

        self.combo_phase = QComboBox()
        self.combo_phase.addItems(["三相", "单相-双极性调制", "单相-单极性调制"])
        self.combo_phase.currentIndexChanged.connect(self._on_phase_changed)
        self.combo_phase.setStyleSheet(
            "QComboBox{padding:4px 8px;font-size:13px;border:1px solid #ccc;border-radius:3px}")

        form.addRow("额定功率:", self.spin_P)
        form.addRow("电网电压:", self.spin_V)
        form.addRow("电网频率:", self.spin_fg)
        form.addRow("开关频率:", self.spin_fsw)
        form.addRow("直流母线电压:", self.spin_Vdc)
        form.addRow("电流纹波率:", self.spin_rip)
        form.addRow("拓扑类型:", self.combo_phase)

        left_layout.addWidget(input_group)

        hint = QLabel('提示: 修改参数后点击"开始计算"刷新结果')
        hint.setStyleSheet("color:#666;font-size:11px"); hint.setWordWrap(True)
        left_layout.addWidget(hint)

        self.btn_calc = self._create_calc_button(left_layout)
        self.btn_pdf = self._create_pdf_button(left_layout)
        left_layout.addStretch()
        return left

    def _on_phase_changed(self, idx):
        """拓扑切换时更新默认电压和单位标签."""
        if idx == 0:  # 三相
            self.spin_V.setValue(380.0)
            self.spin_V.setSuffix(" V (线电压)")
        else:  # 单相
            self.spin_V.setValue(220.0)
            self.spin_V.setSuffix(" V (电网电压)")

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
        return LCLCalculator

    def _do_calculate(self):
        """执行LCL滤波器设计计算."""
        phase_map = {
            0: PhaseType.THREE_PHASE,
            1: PhaseType.SINGLE_PHASE_BIPOLAR,
            2: PhaseType.SINGLE_PHASE_UNIPOLAR,
        }
        params = LCLInputParams(
            P_nominal=self.spin_P.value(),
            V_nominal=self.spin_V.value(),
            f_grid=self.spin_fg.value(),
            f_sw=self.spin_fsw.value(),
            V_dc=self.spin_Vdc.value(),
            ripple_rate=self.spin_rip.value(),
            phase_type=phase_map.get(self.combo_phase.currentIndex(),
                                     PhaseType.THREE_PHASE),
        )

        errors = params.validate()
        if errors:
            QMessageBox.warning(self, "输入参数警告",
                                "\n".join(f"  - {e}" for e in errors))

        results = LCLCalculator.calculate(params)
        self.STEPS_SUBTITLE = (
            f"fsw={params.f_sw:.0f}Hz | fg={params.f_grid:.0f}Hz"
            f" | P={params.P_nominal:.1f}kW"
        )
        return params, results

    def _status_message(self, results) -> str:
        if results.is_valid:
            return f"[LCL] fr={results.fr:.1f}Hz, Atten={results.attenuation_sw_db:.1f}dB"
        return f"[LCL] {len(results.warnings)}个警告"

    # ========================================================================
    # 结果表格
    # ========================================================================

    def _get_table_rows(self, params, results) -> list:
        return [
            ("--- 输入参数 ---", "", ""),
            ("额定功率", f"{params.P_nominal:.1f}", "kW"),
            ("电网电压", f"{params.V_nominal:.0f}", "V RMS"),
            ("电网频率", f"{params.f_grid:.1f}", "Hz"),
            ("开关频率", f"{params.f_sw:.0f}", "Hz"),
            ("直流母线电压", f"{params.V_dc:.0f}", "V"),
            ("电流纹波率", f"{params.ripple_rate:.1f}", "%"),
            ("拓扑类型", params.phase_type.label_cn(), ""),
            ("--- 基本电气量 ---", "", ""),
            ("相电压 (RMS)", f"{results.V_ph:.2f}", "V"),
            ("额定电流 (RMS)", f"{results.I_rated:.2f}", "A"),
            ("额定电流峰值", f"{results.I_peak:.2f}", "A"),
            ("基准阻抗", f"{results.Z_base:.2f}", "Ohm"),
            ("--- 纹波电流 ---", "", ""),
            ("最大纹波电流(峰值)", f"{results.Delta_I_max:.3f}", "A"),
            ("--- 滤波器元件 ---", "", ""),
            ("逆变器侧电感 L1",
             f"{results.L1*1e6:.1f} uH ({results.L1*1e3:.3f} mH)", "H"),
            ("滤波电容 Cf", f"{results.Cf*1e6:.2f} uF", "F"),
            ("电网侧电感 L2",
             f"{results.L2*1e6:.1f} uH ({results.L2*1e3:.3f} mH)", "H"),
            ("电感比 r=L2/L1", f"{results.r:.2f}", "-"),
            ("阻尼电阻 Rd", f"{results.Rd:.2f}", "Ohm"),
            ("--- 谐振特性 ---", "", ""),
            ("谐振频率 fr", f"{results.fr:.1f}", "Hz"),
            ("谐振频率约束",
             f"{results.fr_min:.0f} < fr < {results.fr_max:.0f}", "Hz"),
            ("约束检查", "OK" if results.fr_valid else "NG", ""),
            ("阻尼比 zeta", f"{results.damping_ratio:.2f}", "-"),
            ("--- 滤波性能 ---", "", ""),
            ("开关频率衰减", f"{results.attenuation_sw_db:.1f}", "dB"),
            ("纹波衰减倍数", f"{results.attenuation_sw_times:.0f}", "倍"),
            ("衰减约束", "OK" if results.attenuation_valid else "NG", ""),
            ("--- 设计状态 ---", "", ""),
            ("设计结论", "合格" if results.is_valid else "需优化", ""),
        ]

    # ========================================================================
    # 传递函数 + Bode图
    # ========================================================================

    def _show_extra_displays(self):
        """更新传递函数显示."""
        self._show_transfer_function()

    def _show_transfer_function(self):
        import sympy as sp
        G_u, G_d = LCLCalculator.get_transfer_function_sympy()
        omega_r = LCLCalculator.get_resonant_freq_sympy()
        html = (
            '<html><head><style>'
            "body{font-family:'Segoe UI',Consolas,monospace}"
            'h2{color:#333;border-bottom:2px solid #0078d4}'
            'h3{color:#0078d4;margin-top:20px}'
            'pre{background:#f0f0f0;padding:12px;border-radius:4px;'
            'font-size:13px;overflow-x:auto}'
            '</style></head><body>'
            '<h2>LCL滤波器传递函数推导</h2>'
            '<h3>电路拓扑</h3>'
            '<pre>     L1         L2\n'
            'V_inv --mmmm--+--mmmm-- V_grid\n'
            '              |\n'
            '             Cf\n'
            '              |\n'
            '             Rd\n'
            '              |\n'
            '             GND</pre>'
            f'<h3>无阻尼传递函数 (Rd=0)</h3>'
            f'<pre>{sp.pretty(G_u, use_unicode=True)}</pre>'
            f'<h3>有阻尼传递函数 (含Rd)</h3>'
            f'<pre>{sp.pretty(G_d, use_unicode=True)}</pre>'
            f'<h3>谐振角频率</h3>'
            f'<pre>omega_r = {sp.pretty(omega_r, use_unicode=True)}</pre>'
            '</body></html>'
        )
        self.text_tf.setHtml(html)

    def _show_charts(self, results):
        """更新 Bode 图."""
        params = self._current_params
        f_min = max(0.1, params.f_grid / 10.0)
        f_max = min(params.f_sw * 2.0, 200000.0)
        freq = LCLCalculator.compute_frequency_response(
            results.L1, results.L2, results.Cf, results.Rd,
            f_min=f_min, f_max=f_max)
        self.bode.plot_lcl(freq, results.fr, params.f_sw, params.f_grid)

    # ========================================================================
    # PDF导出
    # ========================================================================

    def _export_pdf_impl(self) -> bool:
        filepath, _ = QFileDialog.getSaveFileName(
            self, self.PDF_TITLE, self.PDF_DEFAULT_NAME, "PDF Files (*.pdf)")
        if not filepath:
            return False
        from reports.lcl_pdf import PDFGenerator
        PDFGenerator().generate(
            filepath, self._current_params, self._current_results,
            bode_image=self.bode.get_image())
        self.status_changed.emit(f"LCL PDF已保存: {filepath}", False)
        self._ask_open(filepath)
        return True
