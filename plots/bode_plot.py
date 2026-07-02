"""
PCS计算平台 - 通用Bode图绘制组件

可复用于LCL和SOGI等模块的频率响应曲线绘制。
"""

from io import BytesIO
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar
)
from matplotlib.figure import Figure
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False


class BodeCanvas(QWidget):
    """通用Bode图组件: 幅频+相频双子图 + Matplotlib工具栏"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.figure = Figure(figsize=(8, 4), dpi=100)
        self.figure.set_layout_engine('tight')
        self.ax_mag = self.figure.add_subplot(2, 1, 1)
        self.ax_phase = self.figure.add_subplot(2, 1, 2, sharex=self.ax_mag)

        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

    # ========================================================================
    # LCL滤波器Bode图
    # ========================================================================

    def plot_lcl(self, freq_resp: dict, fr: float, f_sw: float, f_grid: float):
        """绘制LCL滤波器Bode图(含阻尼/无阻尼对比)"""
        f = freq_resp['f']

        self.ax_mag.clear(); self.ax_phase.clear()
        self.ax_mag.set_xscale('linear'); self.ax_phase.set_xscale('linear')

        # 幅频
        self.ax_mag.semilogx(f, freq_resp['mag_damped'], 'b-', linewidth=1.5, label='含阻尼')
        self.ax_mag.semilogx(f, freq_resp['mag_undamped'], 'r--', linewidth=1.0, label='无阻尼', alpha=0.6)

        if fr > 0:
            idx = np.argmin(np.abs(f - fr))
            self.ax_mag.axvline(x=fr, color='orange', linestyle=':', linewidth=1.2)
            self.ax_mag.annotate(f'fr={fr:.0f}Hz', xy=(fr, freq_resp['mag_damped'][idx]),
                                  xytext=(fr*1.5, freq_resp['mag_damped'][idx]+5),
                                  fontsize=9, color='orange',
                                  arrowprops=dict(arrowstyle='->', color='orange', alpha=0.7))

        idx_sw = np.argmin(np.abs(f - f_sw))
        self.ax_mag.axvline(x=f_sw, color='gray', linestyle=':', linewidth=1.2)
        self.ax_mag.annotate(f'fsw={f_sw:.0f}Hz', xy=(f_sw, freq_resp['mag_damped'][idx_sw]),
                              xytext=(f_sw*0.5, freq_resp['mag_damped'][idx_sw]+10),
                              fontsize=9, color='gray',
                              arrowprops=dict(arrowstyle='->', color='gray', alpha=0.7))

        self.ax_mag.set_ylabel('幅值 (dB)', fontsize=11)
        self.ax_mag.set_title('LCL滤波器频率响应 (Bode图)', fontsize=13, fontweight='bold')
        self.ax_mag.grid(True, which='both', linestyle='--', alpha=0.3)
        self.ax_mag.legend(loc='upper right', fontsize=9)

        # 相频
        self.ax_phase.semilogx(f, freq_resp['phase_damped'], 'b-', linewidth=1.5, label='含阻尼')
        self.ax_phase.semilogx(f, freq_resp['phase_undamped'], 'r--', linewidth=1.0, label='无阻尼', alpha=0.6)
        if fr > 0: self.ax_phase.axvline(x=fr, color='orange', linestyle=':', linewidth=1.2)
        self.ax_phase.axvline(x=f_sw, color='gray', linestyle=':', linewidth=1.2)
        for y in [-90, -180, -270]:
            self.ax_phase.axhline(y=y, color='gray', linestyle='--', linewidth=0.5, alpha=0.4)
        self.ax_phase.set_xlabel('频率 (Hz)', fontsize=11)
        self.ax_phase.set_ylabel('相位 (deg)', fontsize=11)
        self.ax_phase.grid(True, which='both', linestyle='--', alpha=0.3)
        self.ax_phase.legend(loc='upper right', fontsize=9)
        self.ax_phase.set_ylim(-270, 0)

        self.canvas.draw()

    # ========================================================================
    # SOGI Bode图
    # ========================================================================

    def plot_sogi(self, freq_resp: dict, f0: float):
        """绘制SOGI频率响应Bode图(H_d带通 + H_q低通)"""
        f = freq_resp['f']

        self.ax_mag.clear(); self.ax_phase.clear()
        self.ax_mag.set_xscale('linear'); self.ax_phase.set_xscale('linear')

        # 幅频
        self.ax_mag.semilogx(f, freq_resp['mag_d'], 'b-', linewidth=1.5, label="H_d(s) 带通 (v')")
        self.ax_mag.semilogx(f, freq_resp['mag_q'], 'r--', linewidth=1.2, label="H_q(s) 低通 (qv')")
        self.ax_mag.axvline(x=f0, color='orange', linestyle=':', linewidth=1.0, alpha=0.7)
        self.ax_mag.annotate(f'f0={f0:.0f}Hz', xy=(f0, 0), xytext=(f0*1.5, 5),
                              fontsize=8, color='orange', arrowprops=dict(arrowstyle='->', color='orange', alpha=0.7))
        self.ax_mag.set_ylabel('幅值 (dB)', fontsize=10)
        self.ax_mag.set_title('SOGI频率响应 (Bode图)', fontsize=12, fontweight='bold')
        self.ax_mag.grid(True, which='both', linestyle='--', alpha=0.3)
        self.ax_mag.legend(loc='upper right', fontsize=8)

        # 相频
        self.ax_phase.semilogx(f, freq_resp['phase_d'], 'b-', linewidth=1.5, label='H_d(s) 相位')
        self.ax_phase.semilogx(f, freq_resp['phase_q'], 'r--', linewidth=1.2, label='H_q(s) 相位')
        self.ax_phase.axvline(x=f0, color='orange', linestyle=':', linewidth=1.0, alpha=0.7)
        self.ax_phase.axhline(y=0, color='gray', linestyle='--', linewidth=0.5, alpha=0.4)
        self.ax_phase.axhline(y=-90, color='gray', linestyle='--', linewidth=0.5, alpha=0.4)
        self.ax_phase.set_xlabel('频率 (Hz)', fontsize=10)
        self.ax_phase.set_ylabel('相位 (deg)', fontsize=10)
        self.ax_phase.grid(True, which='both', linestyle='--', alpha=0.3)
        self.ax_phase.legend(loc='upper right', fontsize=8)
        self.ax_phase.set_ylim(-180, 90)

        self.canvas.draw()

    def get_image(self) -> bytes:
        """导出当前图为PNG字节流"""
        buf = BytesIO()
        self.figure.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        return buf.read()
