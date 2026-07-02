"""
PCS计算平台 - Boost DC/DC 损耗分析页面

继承 BasePage，仅实现 Boost 特有的输入、计算、显示和导出逻辑。
支持 MOSFET / IGBT 器件类型切换。
"""

from PySide6.QtWidgets import (
    QWidget, QGroupBox, QFormLayout, QVBoxLayout,
    QDoubleSpinBox, QPushButton, QLabel, QTabWidget,
    QTextBrowser, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QComboBox, QLineEdit, QMessageBox, QFileDialog,
    QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from core.Boost_calculator import (
    BoostInputParams, BoostResults, BoostCalculator, BoostDeviceType
)
from plots.boost_plot import BoostPlotWidget
from gui.base_page import BasePage


CSS_SPIN_CUSTOM = (
    "QDoubleSpinBox{padding:3px 6px;font-size:12px;"
    "border:1px solid #ccc;border-radius:3px}"
    "QDoubleSpinBox:focus{border-color:#0078d4}"
)

CSS_COMBO = (
    "QComboBox{padding:4px 8px;font-size:13px;"
    "border:1px solid #ccc;border-radius:3px}"
)


class BoostPage(BasePage):
    """Boost损耗分析页面"""

    module_name = "Boost"
    BTN_PDF_TEXT = "生成Boost损耗计算书PDF"
    STEPS_TITLE = "Boost损耗分析计算过程"
    PDF_TITLE = "保存Boost损耗计算书"
    PDF_DEFAULT_NAME = "Boost_Loss_Report.pdf"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sweep_data = None  # (temps, temp_sweep, currents, current_sweep)

    # ========================================================================
    # 输入面板 (Boost 输入最复杂)
    # ========================================================================

    def _setup_inputs(self) -> QWidget:
        """构建左侧输入面板: 器件类型 + 基础参数 + MOSFET/IGBT + 二极管 + 按钮."""
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # ---- 器件类型 ----
        type_group = QGroupBox("器件类型")
        type_layout = QVBoxLayout(type_group)
        self.combo_type = QComboBox()
        self.combo_type.addItems(["MOSFET", "IGBT"])
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        self.combo_type.setStyleSheet(CSS_COMBO)
        type_layout.addWidget(self.combo_type)
        left_layout.addWidget(type_group)

        # ---- 基础参数 ----
        basic_group = QGroupBox("基础参数")
        bf = QFormLayout(basic_group); bf.setSpacing(6)
        self.spin_Vin = self._spin(1, 1000, 100, 1, "V", style=CSS_SPIN_CUSTOM)
        self.spin_Vout = self._spin(1, 2000, 200, 1, "V", style=CSS_SPIN_CUSTOM)
        self.spin_Iin = self._spin(0.1, 100, 10, 2, "A", style=CSS_SPIN_CUSTOM)
        self.spin_fsw = self._spin(1000, 500000, 50000, 0, "Hz", style=CSS_SPIN_CUSTOM)
        self.spin_Tj = self._spin(-40, 175, 100, 1, "℃", style=CSS_SPIN_CUSTOM)
        bf.addRow("输入电压 Vin:", self.spin_Vin)
        bf.addRow("输出电压 Vout:", self.spin_Vout)
        bf.addRow("输入电流 Iin:", self.spin_Iin)
        bf.addRow("开关频率 fsw:", self.spin_fsw)
        bf.addRow("结温 Tj:", self.spin_Tj)
        left_layout.addWidget(basic_group)

        # ---- MOSFET参数 ----
        self.group_mos = QGroupBox("MOSFET参数")
        mf = QFormLayout(self.group_mos); mf.setSpacing(6)
        self.spin_Rds = self._spin(0.001, 10, 0.1, 4, "Ohm", style=CSS_SPIN_CUSTOM)
        self.spin_Qg = self._spin_si(1, 1000, 60, 0, "nC", 1e-9, style=CSS_SPIN_CUSTOM)
        self.spin_Von = self._spin(1, 30, 15, 1, "V", style=CSS_SPIN_CUSTOM)
        self.spin_Voff = self._spin(-30, 0, -5, 1, "V", style=CSS_SPIN_CUSTOM)
        self.spin_alpha = self._spin(0.001, 0.01, 0.004, 4, "/℃", style=CSS_SPIN_CUSTOM)
        mf.addRow("Rds_on(25℃):", self.spin_Rds)
        mf.addRow("栅极电荷 Qg:", self.spin_Qg)
        mf.addRow("驱动正压 Von:", self.spin_Von)
        mf.addRow("驱动负压 Voff:", self.spin_Voff)
        mf.addRow("温度系数 alpha:", self.spin_alpha)

        hint_label = QLabel(
            "Eon/Eoff数组输入 (逗号分隔, 单位μJ, 留空则用tr/tf近似):")
        hint_label.setStyleSheet("color:#666;font-size:10px;margin-top:4px")
        mf.addRow(hint_label)

        self.edit_Iarr = QLineEdit("")
        self.edit_Iarr.setPlaceholderText("例: 2,5,8,10,15 (A)")
        self.edit_Iarr.setStyleSheet(
            "QLineEdit{padding:3px 6px;font-size:12px;border:1px solid #ccc;border-radius:3px}")
        mf.addRow("I_array (A):", self.edit_Iarr)

        self.edit_Eon = QLineEdit("")
        self.edit_Eon.setPlaceholderText("例: 100,300,500,700,1000 (μJ)")
        self.edit_Eon.setStyleSheet(
            "QLineEdit{padding:3px 6px;font-size:12px;border:1px solid #ccc;border-radius:3px}")
        mf.addRow("Eon_array (μJ):", self.edit_Eon)

        self.edit_Eoff = QLineEdit("")
        self.edit_Eoff.setPlaceholderText("例: 50,150,250,350,500 (μJ)")
        self.edit_Eoff.setStyleSheet(
            "QLineEdit{padding:3px 6px;font-size:12px;border:1px solid #ccc;border-radius:3px}")
        mf.addRow("Eoff_array (μJ):", self.edit_Eoff)

        left_layout.addWidget(self.group_mos)

        # ---- IGBT参数 ----
        self.group_igbt = QGroupBox("IGBT参数")
        inf = QFormLayout(self.group_igbt); inf.setSpacing(6)
        self.spin_Vcesat = self._spin(0.1, 10, 1.5, 2, "V", style=CSS_SPIN_CUSTOM)
        self.spin_Eon = self._spin_si(0.01, 100, 0.5, 2, "mJ", 1e-3, style=CSS_SPIN_CUSTOM)
        self.spin_Eoff = self._spin_si(0.01, 100, 0.3, 2, "mJ", 1e-3, style=CSS_SPIN_CUSTOM)
        self.spin_Qg_i = self._spin_si(1, 1000, 60, 0, "nC", 1e-9, style=CSS_SPIN_CUSTOM)
        inf.addRow("Vce_sat:", self.spin_Vcesat)
        inf.addRow("Eon:", self.spin_Eon)
        inf.addRow("Eoff:", self.spin_Eoff)
        inf.addRow("栅极电荷 Qg:", self.spin_Qg_i)
        self.group_igbt.setVisible(False)
        left_layout.addWidget(self.group_igbt)

        # ---- 二极管参数 ----
        diode_group = QGroupBox("续流二极管参数")
        df = QFormLayout(diode_group); df.setSpacing(6)
        self.spin_Vf = self._spin(0.1, 5, 1.0, 2, "V", style=CSS_SPIN_CUSTOM)
        self.spin_Qrr = self._spin_si(1, 1000, 50, 0, "nC", 1e-9, style=CSS_SPIN_CUSTOM)
        df.addRow("正向压降 Vf:", self.spin_Vf)
        df.addRow("反向恢复电荷 Qrr:", self.spin_Qrr)
        left_layout.addWidget(diode_group)

        # ---- 器件信息 ----
        info_group = QGroupBox("器件信息")
        inf2 = QFormLayout(info_group); inf2.setSpacing(6)
        self.edit_model = QLineEdit("SiHx100N060")
        self.edit_mfr = QLineEdit("Vishay")
        inf2.addRow("型号:", self.edit_model)
        inf2.addRow("厂家:", self.edit_mfr)
        left_layout.addWidget(info_group)

        # ---- 按钮 ----
        self.btn_calc = self._create_calc_button(left_layout)
        self.btn_pdf = self._create_pdf_button(left_layout)
        left_layout.addStretch()
        return left

    def _on_type_changed(self, idx):
        """切换器件类型, 显示/隐藏对应参数组."""
        is_mos = (idx == 0)
        self.group_mos.setVisible(is_mos)
        self.group_igbt.setVisible(not is_mos)

    # ========================================================================
    # 图表区 (boost 用多图表替代 Bode)
    # ========================================================================

    def _setup_plot_area(self, layout):
        """添加4种损耗图表."""
        self.charts = BoostPlotWidget()
        layout.addWidget(self.charts, stretch=3)

    # ========================================================================
    # 输入解析
    # ========================================================================

    def _parse_array(self, text: str) -> list:
        """解析逗号分隔的数组字符串, 返回float列表."""
        text = text.strip()
        if not text:
            return []
        try:
            return [float(x.strip()) for x in text.split(",") if x.strip()]
        except ValueError:
            return []

    def _get_params(self) -> BoostInputParams:
        """从输入控件收集所有参数."""
        is_mos = (self.combo_type.currentIndex() == 0)
        return BoostInputParams(
            Vin=self.spin_Vin.value(), Vout=self.spin_Vout.value(),
            Iin=self.spin_Iin.value(), fsw=self.spin_fsw.value(),
            Tj=self.spin_Tj.value(),
            device_type=BoostDeviceType.MOSFET if is_mos else BoostDeviceType.IGBT,
            Rds_on_25=self.spin_Rds.value(),
            Qg=self._si_value(self.spin_Qg),
            Von=self.spin_Von.value(), Voff=self.spin_Voff.value(),
            alpha=self.spin_alpha.value(),
            I_array=self._parse_array(self.edit_Iarr.text()),
            Eon_array=[v * 1e-6 for v in self._parse_array(self.edit_Eon.text())],
            Eoff_array=[v * 1e-6 for v in self._parse_array(self.edit_Eoff.text())],
            Vce_sat=self.spin_Vcesat.value(),
            Eon=self._si_value(self.spin_Eon),
            Eoff=self._si_value(self.spin_Eoff),
            Vf=self.spin_Vf.value(), Qrr=self._si_value(self.spin_Qrr),
            device_model=self.edit_model.text(), device_mfr=self.edit_mfr.text(),
        )

    # ========================================================================
    # 计算核心
    # ========================================================================

    def _get_calculator_class(self):
        return BoostCalculator

    def _do_calculate(self):
        """执行Boost损耗计算 + 温度/电流扫描."""
        params = self._get_params()
        errors = params.validate()
        if errors:
            QMessageBox.warning(self, "输入参数警告",
                                "\n".join(f"  - {e}" for e in errors))

        results = BoostCalculator.calculate(params)

        # 温度/电流扫描
        try:
            temps, temp_sweep = BoostCalculator.compute_temperature_sweep(params)
            currents, cur_sweep = BoostCalculator.compute_current_sweep(params)
            self._sweep_data = (temps, temp_sweep, currents, cur_sweep)
        except Exception:
            self._sweep_data = None

        self.STEPS_SUBTITLE = (
            f"{params.device_type.value} | Vin={params.Vin:.0f}V"
            f" Vout={params.Vout:.0f}V Iout={params.Iin:.1f}A"
            f" fsw={params.fsw/1000:.0f}kHz"
        )
        return params, results

    def _status_message(self, results) -> str:
        return f"[Boost] eta={results.efficiency:.2f}%, P_total={results.P_total:.2f}W"

    # ========================================================================
    # 结果表格
    # ========================================================================

    def _get_table_rows(self, params, results) -> list:
        rows = [
            ("--- 输入参数 ---", "", ""),
            ("器件类型", params.device_type.value, ""),
            ("输入电压 Vin", f"{params.Vin:.1f}", "V"),
            ("输出电压 Vout", f"{params.Vout:.1f}", "V"),
            ("输入电流 Iin", f"{params.Iin:.2f}", "A"),
            ("开关频率 fsw", f"{params.fsw/1000:.1f}", "kHz"),
            ("结温 Tj", f"{params.Tj:.0f}", "℃"),
            ("器件型号", params.device_model, ""),
            ("器件厂家", params.device_mfr, ""),
            ("--- 计算结果 ---", "", ""),
            ("占空比 D", f"{results.D:.4f}", "-"),
            ("电感电流 I_L", f"{results.I_L:.2f}", "A"),
            ("输出电流 Iout", f"{results.Iout:.2f}", "A"),
            ("输入功率 Pin", f"{results.Pin:.2f}", "W"),
            ("输出功率 Pout", f"{results.Pout:.2f}", "W"),
            ("--- 损耗分析 ---", "", ""),
            ("导通损耗 P_cond", f"{results.P_cond:.4f}", "W"),
            ("开关损耗 P_sw", f"{results.P_sw:.4f}", "W"),
        ]
        if results._Eon_interp:
            rows.append(("  Eon_interp", f"{results._Eon_interp*1e6:.2f} uJ", ""))
        else:
            rows.append(("  Eon_interp", "N/A (tr/tf)", ""))
        if results._Eoff_interp:
            rows.append(("  Eoff_interp", f"{results._Eoff_interp*1e6:.2f} uJ", ""))
        else:
            rows.append(("  Eoff_interp", "N/A (tr/tf)", ""))

        rows.extend([
            ("二极管导通损耗 P_diode", f"{results.P_diode_cond:.4f}", "W"),
            ("二极管恢复损耗 P_rr", f"{results.P_rr:.4f}", "W"),
            ("驱动损耗 P_gate", f"{results.P_drv:.4f}", "W"),
            ("总损耗 P_total", f"{results.P_total:.4f}", "W"),
            ("--- 效率 ---", "", ""),
            ("转换效率 eta", f"{results.efficiency:.2f}", "%"),
            ("--- 损耗占比 ---", "", ""),
            ("导通损耗占比", f"{results.ratio_cond:.2f}", "%"),
            ("开关损耗占比", f"{results.ratio_sw:.2f}", "%"),
            ("二极管导通占比", f"{results.ratio_diode_cond:.2f}", "%"),
            ("恢复损耗占比", f"{results.ratio_rr:.2f}", "%"),
            ("驱动损耗占比", f"{results.ratio_drv:.2f}", "%"),
            ("总损耗占比", f"{results.ratio_total:.2f}", "%"),
            ("--- 设计状态 ---", "", ""),
            ("结论", "合格" if results.is_valid else "需优化", ""),
        ])
        return rows

    # ========================================================================
    # 图表更新
    # ========================================================================

    def _show_charts(self, results):
        """更新4个图表."""
        self.charts.plot_bar(results)
        self.charts.plot_pie(results)
        if self._sweep_data:
            temps, temp_sweep, currents, cur_sweep = self._sweep_data
            self.charts.plot_temp_sweep(temps, temp_sweep)
            self.charts.plot_current_sweep(currents, cur_sweep)

    # ========================================================================
    # PDF导出
    # ========================================================================

    def _get_chart_images(self) -> dict:
        """导出4种图表为PNG字节."""
        return {
            "bar": self.charts.get_bar_image(),
            "pie": self.charts.get_pie_image(),
            "temp": self.charts.get_temp_image(),
            "current": self.charts.get_current_image(),
        }

    def _export_pdf_impl(self) -> bool:
        filepath, _ = QFileDialog.getSaveFileName(
            self, self.PDF_TITLE, self.PDF_DEFAULT_NAME, "PDF Files (*.pdf)")
        if not filepath:
            return False
        from reports.boost_report import BoostReportGenerator
        charts = self._get_chart_images()
        BoostReportGenerator().generate(
            filepath, self._current_params, self._current_results,
            self._sweep_data, charts)
        self.status_changed.emit(f"Boost PDF已保存: {filepath}", False)
        self._ask_open(filepath)
        return True
