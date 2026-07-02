"""
PCS Platform - Base Calculation Page

All module GUI pages inherit from this class.
Provides: signal, spin factory, button creation, run_calculation skeleton,
          HTML steps/table rendering, PDF export, shared styling.

Subclass implements:
  1. _setup_inputs()        -> QWidget (left panel content)
  2. _do_calculate()        -> (params, results)  — validate + calculate
  3. _get_table_rows(p, r)  -> list of (name, value, unit) tuples
  4. _get_calculator_class() -> calculator class with get_calculation_steps()
  5. _export_pdf_impl(filepath, params, results) -> bool
Optional overrides:
  - _setup_extra_tabs(tabs) — add 3rd+ tab (e.g., transfer function)
  - _show_charts(results)   — update plots/charts
  - _setup_plot_area(layout) — add plot widget below tabs
  - _show_extra_displays()  — called after steps/table/charts
  - _status_message(results) -> str
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QDoubleSpinBox, QPushButton,
    QLabel, QTabWidget, QTextBrowser, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QMessageBox,
    QFileDialog, QScrollArea
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor


# ============================================================================
# Shared styling constants
# ============================================================================

CSS_BTN_CALC = """
    QPushButton{background-color:#0078d4;color:white;font-size:14px;
    font-weight:bold;border-radius:4px;padding:8px 16px}
    QPushButton:hover{background-color:#106ebe}"""

CSS_BTN_PDF = """
    QPushButton{background-color:#d83b01;color:white;font-weight:bold;
    font-size:12px;border-radius:4px;padding:6px 16px}
    QPushButton:hover{background-color:#e85d2a}
    QPushButton:disabled{background-color:#ccc;color:#888}"""

CSS_SPIN = """
    QDoubleSpinBox{padding:3px 6px;font-size:12px;border:1px solid #ccc;
    border-radius:3px}QDoubleSpinBox:focus{border-color:#0078d4}"""

CSS_STEPS = """
    body{font-family:'Segoe UI','Microsoft YaHei',sans-serif}
    h2{color:#333;border-bottom:2px solid #0078d4;padding-bottom:6px}
    h3{color:#0078d4;margin-top:24px}
    .step-box{background:#fff;border-left:4px solid #0078d4;
    margin:12px 0;padding:12px 16px;border-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
    .step-title{font-weight:bold;font-size:14px;color:#333}
    .formula{background:#f0f0f0;padding:6px 12px;border-radius:3px;
    font-family:Consolas,monospace;font-size:13px;margin:8px 0}
    .substitution{color:#666;font-size:12px;margin:4px 0}
    .result{font-weight:bold;color:#107c10;font-size:14px}
    .note{color:#888;font-size:11px;font-style:italic}
    .warning{color:#d83b01;font-weight:bold}
    .ok{color:#107c10;font-weight:bold}"""

CSS_TABLE = """
    QTableWidget{font-size:13px;gridline-color:#e0e0e0}
    QHeaderView::section{background-color:#e8e8e8;font-weight:bold;padding:4px}"""


class BasePage(QWidget):
    """
    Base page for all calculation modules.

    Subclass requirements:
      1. _setup_inputs()          -> QWidget (left panel content)
      2. _do_calculate()          -> (params, results)  — validate + calc
      3. _get_table_rows(p, r)    -> list of (name, value, unit)
      4. _get_calculator_class()  -> calculator class with get_calculation_steps()
      5. _export_pdf_impl(filepath, params, results) -> bool
    """

    module_name: str = "Base"
    status_changed = Signal(str, bool)

    # --- subclass-configurable constants ---
    BTN_CALC_TEXT: str = "开始计算"
    BTN_PDF_TEXT: str = "生成计算书PDF"
    STEPS_TITLE: str = "计算过程"
    STEPS_SUBTITLE: str = ""
    PDF_TITLE: str = "保存计算书"
    PDF_DEFAULT_NAME: str = "Report.pdf"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_params = None
        self._current_results = None
        self._setup_ui()

    # ========================================================================
    # UI framework (shared layout structure)
    # ========================================================================

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle{background-color:#ddd;width:3px}")

        # --- Left: inputs (subclass provides widget via _setup_inputs) ---
        left_content = self._setup_inputs()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left_content)
        scroll.setMinimumWidth(280)
        scroll.setMaximumWidth(420)
        scroll.setStyleSheet("QScrollArea{border:none}")
        splitter.addWidget(scroll)

        # --- Right: tabs + plot ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        self.tabs = QTabWidget()
        self.text_steps = QTextBrowser()
        self.text_steps.setStyleSheet("font-size:13px;padding:8px;background:#fafafa")
        self.tabs.addTab(self.text_steps, "计算过程")

        self.table_results = QTableWidget()
        self.table_results.setColumnCount(3)
        self.table_results.setHorizontalHeaderLabels(["参数", "数值", "单位"])
        self.table_results.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.table_results.setAlternatingRowColors(True)
        self.table_results.setStyleSheet(CSS_TABLE)
        self.tabs.addTab(self.table_results, "结果汇总")

        # Subclass hook: add extra tabs (e.g., transfer function)
        self._setup_extra_tabs(self.tabs)

        right_layout.addWidget(self.tabs, stretch=2)

        # Subclass hook: add plot/chart area
        self._setup_plot_area(right_layout)

        splitter.addWidget(right)
        splitter.setSizes([300, 900])
        layout.addWidget(splitter)

    def _setup_extra_tabs(self, tabs: QTabWidget):
        """Override to add extra tabs beyond the default 2 (steps, results)."""
        pass

    def _setup_plot_area(self, layout):
        """Override to add chart/plot widgets below tabs."""
        pass

    # ========================================================================
    # Spin factory (shared)
    # ========================================================================

    def _spin(self, min_v, max_v, default, decimals, suffix,
              width=130, style=None):
        s = QDoubleSpinBox()
        s.setRange(min_v, max_v); s.setDecimals(decimals); s.setValue(default)
        s.setSuffix(f" {suffix}"); s.setMinimumWidth(width)
        s.setStyleSheet(style or CSS_SPIN)
        return s

    def _spin_si(self, min_v, max_v, default, decimals, suffix, scale,
                 width=130, style=None):
        """Spinbox with display-to-SI scaling (e.g., nC->C via 1e-9)."""
        s = self._spin(min_v, max_v, default, decimals, suffix, width, style)
        s._scale = scale
        return s

    def _si_value(self, spin) -> float:
        return spin.value() * getattr(spin, '_scale', 1.0)

    # ========================================================================
    # Button factory (shared)
    # ========================================================================

    def _create_calc_button(self, parent_layout):
        """Create and add the 'calculate' button to parent_layout."""
        btn = QPushButton(self.BTN_CALC_TEXT)
        btn.setMinimumHeight(40)
        btn.setStyleSheet(CSS_BTN_CALC)
        btn.clicked.connect(self.run_calculation)
        parent_layout.addWidget(btn)
        return btn

    def _create_pdf_button(self, parent_layout):
        """Create and add the 'export PDF' button (disabled initially)."""
        btn = QPushButton(self.BTN_PDF_TEXT)
        btn.setMinimumHeight(36)
        btn.setEnabled(False)
        btn.setStyleSheet(CSS_BTN_PDF)
        btn.clicked.connect(self.export_pdf)
        parent_layout.addWidget(btn)
        return btn

    # ========================================================================
    # Calculation flow (shared skeleton)
    # ========================================================================

    def run_calculation(self):
        """Execute calculation: subclass provides _do_calculate()."""
        try:
            params, results = self._do_calculate()
        except Exception as e:
            QMessageBox.critical(self, "计算错误", str(e))
            self.status_changed.emit(f"{self.module_name}计算失败", True)
            return

        self._current_params = params
        self._current_results = results

        self._show_steps(params, results)
        self._show_table(params, results)
        self._show_charts(results)
        self._show_extra_displays()

        self._enable_pdf(True)
        self.tabs.setCurrentIndex(0)

        self.status_changed.emit(
            self._status_message(results),
            not getattr(results, 'is_valid', True))

    def _do_calculate(self):
        """Subclass implements: validate -> calculate -> return (params, results)."""
        raise NotImplementedError

    def _status_message(self, results) -> str:
        """Override for module-specific status text."""
        return f"[{self.module_name}] 计算完成"

    # ========================================================================
    # Steps display (shared HTML template)
    # ========================================================================

    def _get_calculator_class(self):
        """Override: return the calculator class with get_calculation_steps()."""
        return None

    def _show_steps(self, params, results):
        """Render calculation steps in HTML using subclass's calculator class."""
        calc_cls = self._get_calculator_class()
        if calc_cls is None:
            self.text_steps.setHtml("<p>暂无计算步骤</p>")
            return

        steps = calc_cls.get_calculation_steps(params, results)

        html = f"<html><head><style>{CSS_STEPS}</style></head><body>"
        html += f"<h2>{self.STEPS_TITLE}</h2>"
        if self.STEPS_SUBTITLE:
            html += f"<p style='color:#666'>{self.STEPS_SUBTITLE}</p>"

        for s in steps:
            html += "<div class='step-box'>"
            html += f"<div class='step-title'>第{s.step_num}步: {s.title}</div>"
            html += f"<div class='formula'>{s.formula_text}</div>"
            html += f"<div class='substitution'>{s.substitution}</div>"
            html += f"<div class='result'>结果: {s.result} {s.unit}</div>"
            if s.note:
                html += f"<div class='note'>说明: {s.note}</div>"
            html += "</div>"

        if results.warnings:
            html += "<h3>设计警告</h3>"
            for w in results.warnings:
                html += f"<div class='warning'>{w}</div><br>"
        elif results.is_valid:
            html += "<div class='ok' style='font-size:16px'>所有约束满足, 设计合格。</div>"

        html += "</body></html>"
        self.text_steps.setHtml(html)

    # ========================================================================
    # Results table (shared rendering)
    # ========================================================================

    def _get_table_rows(self, params, results) -> list:
        """Override: return list of (name, value, unit) tuples for the table."""
        return []

    def _show_table(self, params, results):
        """Populate results table from _get_table_rows()."""
        rows = self._get_table_rows(params, results)
        self.table_results.setRowCount(len(rows))
        for i, (name, value, unit) in enumerate(rows):
            for j, txt in enumerate([name, value, unit]):
                item = QTableWidgetItem(txt)
                if name.startswith("---"):
                    item.setBackground(QColor("#e8e8e8"))
                    if j == 0:
                        item.setText(name.replace("---", "").strip())
                if "需优化" in str(value) or "NG" in str(value):
                    item.setForeground(QColor("#d83b01"))
                elif value in ("合格", "OK"):
                    item.setForeground(QColor("#107c10"))
                self.table_results.setItem(i, j, item)

    # ========================================================================
    # Charts / Extra displays (subclass hooks)
    # ========================================================================

    def _show_charts(self, results):
        """Override to update plots/charts."""
        pass

    def _show_extra_displays(self):
        """Override for any extra display updates (e.g., transfer function tab)."""
        pass

    # ========================================================================
    # PDF export (shared dialog + lazy import pattern)
    # ========================================================================

    def _enable_pdf(self, enabled: bool):
        """Enable/disable the PDF export button."""
        if hasattr(self, 'btn_pdf'):
            self.btn_pdf.setEnabled(enabled)

    def export_pdf(self) -> bool:
        """Export PDF: subclass provides _export_pdf_impl()."""
        if self._current_results is None:
            QMessageBox.warning(self, "无法导出", "请先执行计算")
            return False
        try:
            ok = self._export_pdf_impl()
            if ok:
                self.status_changed.emit("PDF已保存", False)
            return ok
        except Exception as e:
            QMessageBox.critical(self, "PDF生成失败", str(e))
            return False

    def _export_pdf_impl(self) -> bool:
        """Subclass implements: show dialog -> generate PDF -> ask open."""
        raise NotImplementedError

    def _ask_open(self, filepath):
        if QMessageBox.question(
            self, "导出成功",
            f"PDF已保存至:\n{filepath}\n\n是否打开?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes:
            import os
            os.startfile(filepath)

    def auto_calculate(self):
        self.run_calculation()
