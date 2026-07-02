"""
PCS计算平台 - Boost损耗分析图表组件

包含4种图表:
  1. 损耗柱状图 (bar chart)
  2. 损耗占比饼图 (pie chart)
  3. 温度扫描曲线
  4. 电流扫描曲线
"""

from io import BytesIO
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar
)
from matplotlib.figure import Figure
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 损耗分量配色
COLORS = {
    'P_cond': '#2196F3',         # 蓝色 导通
    'P_sw': '#FF9800',           # 橙色 开关
    'P_diode_cond': '#4CAF50',   # 绿色 二极管导通
    'P_rr': '#9C27B0',           # 紫色 恢复
    'P_drv': '#F44336',          # 红色 驱动
}


class BoostPlotWidget(QWidget):
    """Boost损耗分析图表组件: 4种图表+工具栏"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bar_buf = BytesIO()
        self._pie_buf = BytesIO()
        self._temp_buf = BytesIO()
        self._current_buf = BytesIO()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab{padding:4px 12px;font-size:12px}")

        # Tab 0: 柱状图
        self.fig_bar = Figure(figsize=(6, 4), dpi=100)
        self.fig_bar.set_layout_engine('tight')
        self.ax_bar = self.fig_bar.add_subplot(1, 1, 1)
        self.canvas_bar = FigureCanvas(self.fig_bar)
        self.toolbar_bar = NavigationToolbar(self.canvas_bar, self)
        bar_w = QWidget(); bl = QVBoxLayout(bar_w); bl.setContentsMargins(0,0,0,0); bl.setSpacing(0)
        bl.addWidget(self.toolbar_bar); bl.addWidget(self.canvas_bar)
        self.tabs.addTab(bar_w, "损耗柱状图")

        # Tab 1: 饼图
        self.fig_pie = Figure(figsize=(5, 4), dpi=100)
        self.fig_pie.set_layout_engine('tight')
        self.ax_pie = self.fig_pie.add_subplot(1, 1, 1)
        self.canvas_pie = FigureCanvas(self.fig_pie)
        self.toolbar_pie = NavigationToolbar(self.canvas_pie, self)
        pie_w = QWidget(); pl = QVBoxLayout(pie_w); pl.setContentsMargins(0,0,0,0); pl.setSpacing(0)
        pl.addWidget(self.toolbar_pie); pl.addWidget(self.canvas_pie)
        self.tabs.addTab(pie_w, "损耗占比饼图")

        # Tab 2: 温度扫描
        self.fig_temp = Figure(figsize=(6, 4), dpi=100)
        self.fig_temp.set_layout_engine('tight')
        self.ax_temp = self.fig_temp.add_subplot(1, 1, 1)
        self.canvas_temp = FigureCanvas(self.fig_temp)
        self.toolbar_temp = NavigationToolbar(self.canvas_temp, self)
        temp_w = QWidget(); tl = QVBoxLayout(temp_w); tl.setContentsMargins(0,0,0,0); tl.setSpacing(0)
        tl.addWidget(self.toolbar_temp); tl.addWidget(self.canvas_temp)
        self.tabs.addTab(temp_w, "温度扫描")

        # Tab 3: 电流扫描
        self.fig_current = Figure(figsize=(6, 4), dpi=100)
        self.fig_current.set_layout_engine('tight')
        self.ax_current = self.fig_current.add_subplot(1, 1, 1)
        self.canvas_current = FigureCanvas(self.fig_current)
        self.toolbar_current = NavigationToolbar(self.canvas_current, self)
        cur_w = QWidget(); cl = QVBoxLayout(cur_w); cl.setContentsMargins(0,0,0,0); cl.setSpacing(0)
        cl.addWidget(self.toolbar_current); cl.addWidget(self.canvas_current)
        self.tabs.addTab(cur_w, "电流扫描")

        layout.addWidget(self.tabs)

    # ========================================================================
    # 柱状图
    # ========================================================================

    def plot_bar(self, results):
        """绘制各损耗分量柱状图"""
        self.ax_bar.clear()
        labels = ['导通\n损耗', '开关\n损耗', '二极管\n导通', '二极管\n恢复', '驱动芯片\n供电']
        values = [results.P_cond, results.P_sw, results.P_diode_cond,
                   results.P_rr, results.P_drv]
        colors = [COLORS['P_cond'], COLORS['P_sw'], COLORS['P_diode_cond'],
                  COLORS['P_rr'], COLORS['P_drv']]

        bars = self.ax_bar.bar(labels, values, color=colors, edgecolor='white', linewidth=0.5)
        self.ax_bar.set_ylabel('损耗 (W)', fontsize=10)
        self.ax_bar.set_title(f'Boost损耗分布 (总损耗={results.P_total:.2f}W)', fontsize=12, fontweight='bold')
        self.ax_bar.grid(axis='y', linestyle='--', alpha=0.3)

        # 数值标注
        for bar, val in zip(bars, values):
            if val > 0:
                self.ax_bar.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.02,
                                  f'{val:.2f}W', ha='center', va='bottom', fontsize=8)
        self.canvas_bar.draw()

    # ========================================================================
    # 饼图
    # ========================================================================

    def plot_pie(self, results):
        """绘制损耗占比饼图"""
        self.ax_pie.clear()
        labels = ['导通损耗', '开关损耗', '二极管导通', '恢复损耗', '驱动芯片供电']
        values = [results.P_cond, results.P_sw, results.P_diode_cond,
                   results.P_rr, results.P_drv]
        colors = [COLORS['P_cond'], COLORS['P_sw'], COLORS['P_diode_cond'],
                  COLORS['P_rr'], COLORS['P_drv']]

        # 过滤0值
        non_zero = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0.001]
        if non_zero:
            l, v, c = zip(*non_zero)
            pcts = [f'{val/results.P_total*100:.1f}%' for val in v]
            self.ax_pie.pie(v, labels=l, colors=c, autopct='%1.1f%%',
                             startangle=90, pctdistance=0.6, labeldistance=1.1)
        self.ax_pie.set_title(f'损耗占比分布 (总损耗={results.P_total:.2f}W)', fontsize=12, fontweight='bold')
        self.canvas_pie.draw()

    # ========================================================================
    # 温度扫描
    # ========================================================================

    def plot_temp_sweep(self, temps, sweep):
        """绘制温度扫描曲线"""
        self.ax_temp.clear()
        # 移除旧的twinx避免重复叠加
        for ax in list(self.fig_temp.axes):
            if ax is not self.ax_temp: ax.remove()
        self.ax_temp.plot(temps, sweep['P_cond'], 'o-', color=COLORS['P_cond'],
                           linewidth=1.5, markersize=3, label='导通损耗')
        self.ax_temp.plot(temps, sweep['P_sw'], 's-', color=COLORS['P_sw'],
                           linewidth=1.5, markersize=3, label='开关损耗')
        self.ax_temp.plot(temps, sweep['P_total'], 'D-', color='black',
                           linewidth=2, markersize=4, label='总损耗')
        self.ax_temp.set_xlabel('结温 Tj (℃)', fontsize=10)
        self.ax_temp.set_ylabel('损耗 (W)', fontsize=10)
        self.ax_temp.set_title('温度扫描: 损耗 vs 结温', fontsize=12, fontweight='bold')
        self.ax_temp.grid(True, linestyle='--', alpha=0.3)
        self.ax_temp.legend(loc='upper left', fontsize=8)

        # 第二y轴: 效率
        ax2 = self.ax_temp.twinx()
        ax2.plot(temps, sweep['efficiency'], '^-', color='green',
                  linewidth=1, markersize=3, alpha=0.7, label='效率')
        ax2.set_ylabel('效率 (%)', fontsize=9, color='green')
        ax2.legend(loc='upper right', fontsize=8)
        self.canvas_temp.draw()

    # ========================================================================
    # 电流扫描
    # ========================================================================

    def plot_current_sweep(self, currents, sweep):
        """绘制电流扫描曲线"""
        self.ax_current.clear()
        # 移除旧的twinx避免重复叠加
        for ax in list(self.fig_current.axes):
            if ax is not self.ax_current: ax.remove()
        self.ax_current.plot(currents, sweep['P_cond'], 'o-', color=COLORS['P_cond'],
                              linewidth=1.5, markersize=3, label='导通损耗')
        self.ax_current.plot(currents, sweep['P_sw'], 's-', color=COLORS['P_sw'],
                              linewidth=1.5, markersize=3, label='开关损耗')
        self.ax_current.plot(currents, sweep['P_total'], 'D-', color='black',
                              linewidth=2, markersize=4, label='总损耗')
        self.ax_current.set_xlabel('输出电流 Iout (A)', fontsize=10)
        self.ax_current.set_ylabel('损耗 (W)', fontsize=10)
        self.ax_current.set_title('电流扫描: 损耗 vs 输出电流', fontsize=12, fontweight='bold')
        self.ax_current.grid(True, linestyle='--', alpha=0.3)
        self.ax_current.legend(loc='upper left', fontsize=8)

        ax2 = self.ax_current.twinx()
        ax2.plot(currents, sweep['efficiency'], '^-', color='green',
                  linewidth=1, markersize=3, alpha=0.7, label='效率')
        ax2.set_ylabel('效率 (%)', fontsize=9, color='green')
        ax2.legend(loc='upper right', fontsize=8)
        self.canvas_current.draw()

    # ========================================================================
    # 图像导出 (用于PDF)
    # ========================================================================

    def get_bar_image(self) -> bytes:
        buf = BytesIO(); self.fig_bar.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0); return buf.read()

    def get_pie_image(self) -> bytes:
        buf = BytesIO(); self.fig_pie.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0); return buf.read()

    def get_temp_image(self) -> bytes:
        buf = BytesIO(); self.fig_temp.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0); return buf.read()

    def get_current_image(self) -> bytes:
        buf = BytesIO(); self.fig_current.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0); return buf.read()
