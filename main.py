"""
PCS计算平台 - 主入口

架构:
  gui/LCL_page.py  + core/LCL_calculator.py   = LCL滤波器设计单元
  gui/SOGI_page.py + core/SOGI_calculator.py  = SOGI参数计算单元
  reports/          = PDF生成器
  plots/            = 通用绘图组件

新增计算单元只需:
  1. 创建 gui/Xxx_page.py (继承QWidget,实现run_calculation/export_pdf)
  2. 创建 core/Xxx_calculator.py (纯计算引擎)
  3. 在本文件的 PAGES 列表中注册一行
"""

import sys
import os

from core.update_checker import UpdateChecker

# PyInstaller support
if getattr(sys, 'frozen', False):
    _basedir = sys._MEIPASS
else:
    _basedir = os.path.dirname(os.path.abspath(__file__))
if _basedir not in sys.path:
    sys.path.insert(0, _basedir)


def main():
    # 检查依赖
    try:
        from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget,
                                        QVBoxLayout, QTabWidget, QStatusBar,
                                        QLabel, QPushButton, QMessageBox)
        from PySide6.QtCore import Qt, Signal
        from PySide6.QtGui import QAction, QKeySequence, QFont
    except ImportError as e:
        print(f"Error: PySide6 not found. Run: pip install -r requirements.txt\n{e}")
        sys.exit(1)

    # ========================================================================
    # Qt Application
    # ========================================================================
    app = QApplication(sys.argv)
    app.setApplicationName("PCS计算平台")
    app.setApplicationVersion("1.0.3")
    app.setOrganizationName("Power Electronics Lab")

    # 远程更新检查地址 (部署时修改为实际服务器地址)
    UPDATE_URL = "https://myserver.com/version.json"
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei", 10))
    app.setStyleSheet("""
        QMainWindow{background-color:#fff}
        QGroupBox{font-weight:bold;border:1px solid #ddd;border-radius:6px;margin-top:8px;padding-top:16px}
        QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 6px;color:#0078d4}
    """)

    # ========================================================================
    # 注册计算单元页面 (新增模块只需在此添加一行)
    # ========================================================================
    from gui.LCL_page import LCLPage
    from gui.SOGI_page import SOGIPage
    from gui.Boost_page import BoostPage

    PAGES = [
        LCLPage(),
        SOGIPage(),
        BoostPage(),
    ]

    # ========================================================================
    # Main Window
    # ========================================================================
    class MainWindow(QMainWindow):
        calculate_requested = Signal()
        pdf_export_requested = Signal()

        def __init__(self):
            super().__init__()
            self.setWindowTitle("PCS计算平台 v1.0.3 - PCS Computing Platform")
            self.resize(1280, 900); self.setMinimumSize(1024, 680)
            self._center()
            self._setup_menu()
            self._setup_ui()
            self._setup_statusbar()

        def _center(self):
            s = self.screen().availableGeometry()
            self.move((s.width()-self.width())//2, (s.height()-self.height())//2)

        def _setup_menu(self):
            mb = self.menuBar()
            fm = mb.addMenu("文件(&F)")
            a = fm.addAction("导出计算书PDF...(&E)")
            a.setShortcut(QKeySequence("Ctrl+P"))
            a.triggered.connect(self.pdf_export_requested.emit)
            fm.addSeparator()
            a = fm.addAction("退出(&Q)")
            a.setShortcut(QKeySequence("Ctrl+Q"))
            a.triggered.connect(self.close)

            cm = mb.addMenu("计算(&C)")
            a = cm.addAction("开始计算(&S)")
            a.setShortcut(QKeySequence("Ctrl+Return"))
            a.triggered.connect(self.calculate_requested.emit)

            hm = mb.addMenu("帮助(&H)")
            a = hm.addAction("关于 PCS计算平台(&A)")
            a.triggered.connect(self._show_about)

        def _setup_ui(self):
            cw = QWidget(); self.setCentralWidget(cw)
            lo = QVBoxLayout(cw); lo.setContentsMargins(4,4,4,4); lo.setSpacing(4)

            self.module_tabs = QTabWidget()
            self.module_tabs.setStyleSheet("""
                QTabWidget::pane{border:1px solid #ddd;border-radius:4px}
                QTabBar::tab{padding:8px 20px;font-size:14px;font-weight:bold}
                QTabBar::tab:selected{color:#0078d4;border-bottom:3px solid #0078d4}
            """)
            for page in PAGES:
                if isinstance(page, LCLPage): name = "LCL滤波器设计"
                elif isinstance(page, SOGIPage): name = "SOGI计算"
                elif isinstance(page, BoostPage): name = "Boost损耗分析"
                else: name = page.__class__.__name__
                self.module_tabs.addTab(page, name)
            lo.addWidget(self.module_tabs)

        def _setup_statusbar(self):
            self.sb = QStatusBar()
            self.sb.setStyleSheet("QStatusBar{background-color:#f0f0f0;border-top:1px solid #ddd;padding:4px}")
            self.setStatusBar(self.sb)
            self.status_label = QLabel('就绪 - 请点击"开始计算"或按 Ctrl+Enter')
            self.status_label.setStyleSheet("color:#333;font-size:12px")
            self.sb.addWidget(self.status_label, 1)
            self.design_label = QLabel("")
            self.sb.addPermanentWidget(self.design_label)
            self.btn_export = QPushButton("生成计算书PDF")
            self.btn_export.setStyleSheet("QPushButton{background-color:#d83b01;color:white;font-weight:bold;font-size:12px;padding:6px 20px;border-radius:4px;margin:2px 8px}QPushButton:hover{background-color:#e85d2a}QPushButton:disabled{background-color:#ccc;color:#888}")
            self.btn_export.clicked.connect(self.pdf_export_requested.emit)
            self.btn_export.setEnabled(False)
            self.sb.addPermanentWidget(self.btn_export)

        def set_status(self, msg, is_warning=False):
            self.status_label.setText(msg)
            self.status_label.setStyleSheet(f"color:{'#d83b01' if is_warning else '#333'};font-size:12px;{'font-weight:bold' if is_warning else ''}")

        def set_design_status(self, ok):
            if ok:
                self.design_label.setText("● 设计合格")
                self.design_label.setStyleSheet("color:#107c10;font-size:13px;font-weight:bold;padding:0 12px")
            else:
                self.design_label.setText("● 需优化")
                self.design_label.setStyleSheet("color:#d83b01;font-size:13px;font-weight:bold;padding:0 12px")

        def set_export_enabled(self, en): self.btn_export.setEnabled(en)

        def _show_about(self):
            QMessageBox.about(self, "关于 PCS计算平台", """
            <h2>PCS计算平台 v1.0.3</h2>
            <p><b>PCS Computing Platform</b></p>
            <p>电力电子变换器设计计算平台</p>
            <hr><p><b>版本更新记录:</b></p>
            <p><b>v1.0.3</b> (2026-06-10)</p>
            <ul>
                <li>新增Boost DC/DC损耗分析模块 (MOSFET/IGBT)</li>
                <li>损耗柱状图/饼图/温度扫描/电流扫描 4种图表</li>
                <li>Boost损耗计算书PDF导出 (含图表嵌入)</li>
                <li>修正损耗公式: 以输入电流Iin为基准, Pin=Vin*Iin</li>
            </ul>
            <p><b>v1.0.2</b> (2026-06-04)</p>
            <ul>
                <li>新增SOGI参数计算单元(二阶广义积分器)</li>
                <li>三种离散化方法: 前向欧拉/后向欧拉/双线性变换</li>
                <li>多计算单元模块化架构: gui/X_page + core/X_calculator</li>
                <li>SOGI Bode图 + C代码PDF导出</li>
            </ul>
            <p><b>v1.0.1</b> (2026-05-31)</p>
            <ul>
                <li>新增单相逆变器支持(双极性/单极性调制)</li>
                <li>单极性调制L1自动减半(等效开关频率翻倍)</li>
            </ul>
            <p><b>v1.0.0</b> (2026-05-31)</p>
            <ul><li>三相LCL滤波器自动设计</li><li>Bode图+PDF导出</li></ul>
            <hr><p><b>参考标准:</b> IEEE 519-2014, Liserre et al. (2005)</p>
            """)

        def _on_update_available(self, info):
            """Show update notification dialog."""
            ver = info.get("version", "")
            url = info.get("url", "")
            changelog = info.get("changelog", "")
            force = info.get("force_update", False)

            if force:
                msg = f"检测到新版本 v{ver}（强制更新）:\n\n{changelog}\n\n点击确定下载新版本。"
                btns = QMessageBox.StandardButton.Ok
            else:
                msg = f"检测到新版本 v{ver}:\n\n{changelog}\n\n是否前往下载？"
                btns = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No

            ret = QMessageBox.information(self, "软件更新", msg, btns)

            if ret in (QMessageBox.StandardButton.Ok, QMessageBox.StandardButton.Yes):
                import webbrowser
                webbrowser.open(url)
            if force:
                self.close()

    # ========================================================================
    # Controller (thin dispatch)
    # ========================================================================
    window = MainWindow()

    def get_active_page():
        idx = window.module_tabs.currentIndex()
        return PAGES[idx] if 0 <= idx < len(PAGES) else None

    def on_calculate():
        page = get_active_page()
        if page: page.run_calculation()

    def on_export_pdf():
        page = get_active_page()
        if page: page.export_pdf()

    def on_status(msg, warn=False):
        window.set_status(msg, warn)
        window.set_design_status(not warn)
        window.set_export_enabled(True)

    # Wire signals
    window.calculate_requested.connect(on_calculate)
    window.pdf_export_requested.connect(on_export_pdf)
    for page in PAGES:
        page.status_changed.connect(on_status)

    # Auto-calculate all modules on startup
    for page in PAGES:
        try: page.auto_calculate()
        except Exception: pass

    # ========================================================================
    # Run
    # ========================================================================
    window.show()

    # 启动时检查更新 (异步, 网络错误静默忽略)
    checker = UpdateChecker(window)
    checker.update_available.connect(window._on_update_available)
    checker.check(UPDATE_URL, app.applicationVersion())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
