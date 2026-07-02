# CLAUDE.md — PCS Platform (PCS计算平台)

> **PCS Platform** — Power Conversion System design toolkit.
> Three calculation modules: LCL filter, SOGI, Boost DC/DC loss analysis.
> Read this before working on this project — it saves everyone tokens.

## Overview

Desktop GUI app (PySide6) for power electronics converter design.
Three self-contained calculation modules, each with its own page + calculator + PDF report.
Pages inherit from `BasePage` for shared UI infrastructure (splitter, tabs, steps, table, PDF export).
Generates PDF engineering calculation reports with embedded plots (Bode, bar, pie, sweep).

- **Version:** 1.0.4
- **Target:** Windows standalone EXE (PyInstaller)
- **Language:** Python 3.12, all UI labels and PDF in Chinese

## Architecture

Each module page inherits from `BasePage` and only implements what's unique:
inputs, calculation, table rows, charts, and PDF export.

```
main.py                              # Entry point: QApplication + MainWindow + signal dispatch
├── core/
│   ├── base_calculator.py           # Shared: CalculationStep dataclass, formatters, interpolation
│   ├── LCL_calculator.py            # LCL filter design engine (8-step procedure)
│   ├── SOGI_calculator.py           # SOGI parameter calculator (3 discretization methods)
│   ├── Boost_calculator.py          # Boost DC/DC loss analysis (MOSFET/IGBT, 5 loss types)
│   └── update_checker.py            # Async update checker (QNetworkAccessManager, version comparison)
├── gui/
│   ├── base_page.py                 # BasePage(QWidget): shared UI skeleton — splitter, tabs, spin factory,
│   │                                #   button factory, run_calculation(), _show_steps(), _show_table(),
│   │                                #   export_pdf(), hooks for subclass overrides
│   ├── LCL_page.py                  # LCLPage(BasePage): 6 spinboxes + topology combo, 3 tabs + Bode
│   ├── SOGI_page.py                 # SOGIPage(BasePage): 4 spinboxes, 3 tabs + Bode + C code
│   └── Boost_page.py                # BoostPage(BasePage): ~20 inputs, MOSFET/IGBT toggle, 2 tabs + 4 charts
├── plots/
│   ├── bode_plot.py                 # BodeCanvas: dual-subplot Bode (mag+phase), shared by LCL & SOGI
│   └── boost_plot.py                # BoostPlotWidget: bar, pie, temperature sweep, current sweep
├── reports/
│   ├── base_report.py               # BaseReportGenerator: fonts, styles, cover, table, render_steps
│   ├── lcl_pdf.py                   # LCL PDF report (6 sections, Bode embed)
│   ├── sogi_pdf.py                  # SOGI PDF report (discrete matrices, C code embed)
│   └── boost_report.py              # Boost PDF report (4 chart embeds, sweep data)
```

**Signal flow (all modules):**
```
main.py dispatch:
  window.calculate_requested / window.pdf_export_requested
    → get_active_page() → page.run_calculation() / page.export_pdf()

Page.run_calculation()  (inherited from BasePage):
  → _do_calculate()                           → (params, results)   [subclass override]
  → _show_steps() + _show_table()             → update tabs          [BasePage provides]
  → _show_charts() + _show_extra_displays()   → update plots/TF     [subclass override]
  → status_changed.emit(msg, warn)            → MainWindow status bar

Page.export_pdf()  (inherited from BasePage):
  → _export_pdf_impl()                        → file dialog + generate [subclass override]
```

## Key Files & Responsibilities

| File | Lines | Role |
|------|-------|------|
| `main.py` | 258 | `QApplication` setup, Fusion style, `MainWindow` (QTabWidget + menu + status bar), thin dispatch controller, PAGES registry, auto-calculate on startup, `UpdateChecker` wiring |
| `core/LCL_calculator.py` | 528 | `PhaseType` enum, `LCLInputParams`, `LCLResults`, `LCLCalculator` with `calculate()`, `get_calculation_steps()`, `get_transfer_function_sympy()`, `compute_frequency_response()` |
| `core/SOGI_calculator.py` | 212 | `DiscreteMethod`, `SOGIInputParams`, `SOGIResults`, `SOGICalculator` with `calculate()`, 3 discretization methods (Forward/Backward Euler, Bilinear), eigenvalue stability check |
| `core/Boost_calculator.py` | 429 | `BoostDeviceType` enum, `BoostInputParams`, `BoostResults`, `BoostCalculator` with `calculate()` (5 loss components), `compute_temperature_sweep()`, `compute_current_sweep()` |
| `core/base_calculator.py` | 86 | `CalculationStep` dataclass, `linear_interp()`, SI formatters (`format_inductance`, `format_capacitance`, `format_resistance`, `format_frequency`, `format_power`, `format_time`) |
| `core/update_checker.py` | 41 | `UpdateChecker(QObject)`: async GET `version.json`, semantic version comparison, `update_available` Signal, silent fail on network error |
| `gui/base_page.py` | ~320 | `BasePage(QWidget)`: shared QSplitter+tabs skeleton, `_spin()`/`_spin_si()` factory, `_create_calc_button()`/`_create_pdf_button()`, `run_calculation()` skeleton, `_show_steps()` HTML rendering, `_show_table()`, `export_pdf()`, `_ask_open()`. **All three pages inherit from this.** |
| `gui/LCL_page.py` | ~280 | `LCLPage(BasePage)`: 6 spinboxes + phase-type QComboBox, 3rd tab (transfer function), BodeCanvas, phase-aware voltage defaults |
| `gui/SOGI_page.py` | ~250 | `SOGIPage(BasePage)`: 4 spinboxes, 3rd tab (transfer function + discrete matrices + C code), BodeCanvas |
| `gui/Boost_page.py` | ~400 | `BoostPage(BasePage)`: most complex page, ~20 inputs, MOSFET/IGBT toggle, QLineEdit arrays for Eon/Eoff, BoostPlotWidget with 4 chart types, sweep computation |
| `plots/bode_plot.py` | 104 | `BodeCanvas(QWidget)`: Matplotlib FigureCanvas + NavigationToolbar, dual subplot (mag+phase), `plot_lcl()` and `plot_sogi()`, `get_image()` → PNG bytes |
| `plots/boost_plot.py` | 186 | `BoostPlotWidget(QWidget)`: 4 independent Figures in internal QTabWidget (bar, pie, temp sweep, current sweep), `get_bar_image()` etc. → PNG bytes each |
| `reports/base_report.py` | 193 | `BaseReportGenerator`: Chinese font auto-detection (msyh.ttc → SimHei → SimSun), predefined ParagraphStyles, `cover()`, `table()`, `render_steps()`, `embed_image()`, `footer()`, `build()` |
| `reports/lcl_pdf.py` | 94 | `PDFGenerator(BaseReportGenerator)`: 6-section LCL report, Bode plot embed |
| `reports/sogi_pdf.py` | 107 | `SOGIPDFGenerator(BaseReportGenerator)`: SOGI report with discrete matrices, C code, Bode embed |
| `reports/boost_report.py` | 87 | `BoostReportGenerator(BaseReportGenerator)`: Boost report with 4 chart embeds, sweep data tables |

## BasePage Subclass Contract

Each page inherits from `BasePage` and implements these methods:

| Method | Required | Purpose |
|--------|----------|---------|
| `_setup_inputs()` | **Yes** | Return QWidget for the left input panel |
| `_do_calculate()` | **Yes** | Validate inputs, call calculator, return `(params, results)` |
| `_get_table_rows(p, r)` | **Yes** | Return `list[(name, value, unit)]` for the results table |
| `_get_calculator_class()` | **Yes** | Return the calculator class (for step generation) |
| `_export_pdf_impl()` | **Yes** | File dialog + PDF generation + ask_open, return `bool` |
| `_setup_extra_tabs(tabs)` | Optional | Add 3rd+ tab (e.g., transfer function) |
| `_setup_plot_area(layout)` | Optional | Add chart/plot widget below tabs |
| `_show_charts(results)` | Optional | Update plots after calculation |
| `_show_extra_displays()` | Optional | Update extra tabs after calculation |
| `_status_message(results)` | Optional | Custom status bar message |

**Class-level constants** for customization:
- `module_name` (str) — used in status messages
- `BTN_CALC_TEXT`, `BTN_PDF_TEXT` — button labels
- `STEPS_TITLE`, `STEPS_SUBTITLE` — HTML display titles
- `PDF_TITLE`, `PDF_DEFAULT_NAME` — file dialog

## LCL Calculation Engine Design

### PhaseType enum
```python
PhaseType.THREE_PHASE              # V_ph = V_line/sqrt(3), I = P/(sqrt(3)*V_line)
PhaseType.SINGLE_PHASE_BIPOLAR     # V_ph = V_grid,   I = P/V_grid
PhaseType.SINGLE_PHASE_UNIPOLAR    # Same as bipolar but L1 halved (effective fsw doubles)
```

### Core formulas (in `LCLCalculator.calculate()`)

| Step | Formula | Notes |
|------|---------|-------|
| L1 | `Vdc/(4*fsw*Delta_I_max)` or `Vdc/(8*fsw*Delta_I_max)` | Unipolar: effective fsw doubles → L1 halved |
| Cf | `Qc*P/(3*2pi*f*Vph^2)` or `Qc*P/(2pi*f*Vph^2)` | Qc=0.05pu, 3ph divides by 3 |
| L2 | `r * L1` | r=0.6 default, verified via attenuation |
| fr | `(1/2pi)*sqrt[(L1+L2)/(L1*L2*Cf)]` | Constraint: 10fg < fr < 0.5fsw |
| Rd | `1/(2pi*fr*Cf)` | → zeta=0.5 (critical damping) |
| TF | `(1+s*Rd*Cf)/(s^3*L1*L2*Cf + s^2*Rd*Cf*(L1+L2) + s*(L1+L2))` | Sympy symbolic + NumPy numeric |

### Design constraints (warnings trigger)
- `10*f_grid < fr < 0.5*f_sw`
- `A_sw < -40 dB` at switching frequency
- `Vdc > sqrt(2)*V_nominal` (3ph: line voltage; 1ph: grid voltage)

## SOGI Calculation Engine

### Parameters
- `V_amplitude`: grid voltage amplitude (V), default 311V
- `f_grid`: grid frequency (Hz), default 50Hz
- `bandwidth`: filter bandwidth (Hz), default 5Hz (recommended 3~10Hz)
- `fs`: sampling frequency (Hz), default 10kHz

### Key outputs
- Continuous-domain transfer functions: H_d(s) (bandpass), H_q(s) (lowpass)
- Three discretization methods compared: Forward Euler, Backward Euler, Bilinear/Tustin
- Each method: state-space matrices (A 2x2, B 2x1), eigenvalues, stability check
- Settling time estimation (95% criterion)
- C code generation for embedded implementation

## Boost DC/DC Loss Analysis Engine

### Device types: MOSFET / IGBT
### Loss components (MOSFET)
1. Conduction loss: `P_cond = Iin^2 * Rds_on(Tj) * D` where `D = 1 - Vin/Vout`
2. Switching loss (turn-on): `P_sw_on = 0.5 * Vout * Iin * tr * fsw` (or Eon interpolation)
3. Switching loss (turn-off): `P_sw_off = 0.5 * Vout * Iin * tf * fsw` (or Eoff interpolation)
4. Diode conduction: `P_diode = Vf * Iin * (1 - D)`
5. Reverse recovery: `P_rr = Qrr * Vout * fsw`
6. Gate drive: `P_gate = Qg * (Von - Voff) * fsw`

### Sweep analysis
- Temperature sweep: recalculate for Tj in [25, 150] deg C (20 points)
- Current sweep: recalculate for Iin in [0.1*Iin, 2.0*Iin] (20 points)

## Tech Stack

```
PySide6          # GUI (Qt for Python)
matplotlib       # Bode plot, bar/pie/sweep charts (backend_qtagg for Qt embedding)
sympy            # Symbolic transfer function derivation (LCL, SOGI)
reportlab        # PDF generation (needs TTF Chinese font)
numpy            # Numerical frequency response, eigenvalue computation
pyinstaller      # EXE packaging
```

## Build & Run

```bash
# Dev
pip install -r requirements.txt
python main.py

# Package EXE (use the .spec file — output: dist/PCS_Platform.exe)
pyinstaller PCS_Platform.spec

# Or command-line equivalent:
pyinstaller --name="PCS_Platform" --onefile --windowed   --add-data="core;core" --add-data="gui;gui"   --add-data="reports;reports" --add-data="plots;plots"   --hidden-import=matplotlib.backends.backend_qtagg   --hidden-import=numpy --hidden-import=sympy --hidden-import=reportlab   --hidden-import=reportlab.pdfbase.ttfonts   --clean main.py
```

## Known Patterns & Gotchas

### 1. File encoding (CRITICAL)
**The Write tool corrupts non-ASCII characters on Windows.** Chinese strings in `.py` files written via Write tool will be garbled at runtime even though Read displays them correctly.

**Fix:** Use Python to write files with explicit `encoding='utf-8'`:
```bash
.venv/Scripts/python -c "
with open('target.py', 'w', encoding='utf-8') as f:
    f.write(content)
"
```

### 2. Architecture: BasePage inheritance pattern
All module pages inherit from `BasePage` (`gui/base_page.py`). BasePage provides:
- QSplitter layout (scrollable left inputs + right tabs + optional plot area)
- `_spin()` / `_spin_si()` / `_si_value()` factory methods
- `_create_calc_button()` / `_create_pdf_button()` factory methods
- `run_calculation()` skeleton: calls `_do_calculate()` → `_show_steps()` → `_show_table()` → `_show_charts()` → `_show_extra_displays()`
- `export_pdf()` skeleton: calls `_export_pdf_impl()` → `_ask_open()`
- Subclass only needs to implement ~6 methods (see BasePage Subclass Contract above)

### 3. PAGES registry in main.py
New modules are registered by adding one import + one line to the `PAGES` list in `main.py`.
The tab name is determined by `isinstance()` checks (LCLPage → "LCL滤波器设计", etc.).

### 4. Naming conventions
- Calculator class fields use SI units internally (H, F, Ohm, s); display layer converts via `format_*()` helpers
- All UI labels in Chinese; core calculation code uses English variable names
- `PhaseType` enum maps combo-box index 0/1/2 → THREE_PHASE / SINGLE_PHASE_BIPOLAR / SINGLE_PHASE_UNIPOLAR

### 5. PDF Chinese font
`BaseReportGenerator._register_fonts()` probes `C:/Windows/Fonts/msyh.ttc` → `SimHei` → `SimSun`.
Falls back to Helvetica (no Chinese) if none found.

### 6. Matplotlib in PyInstaller
Must include `--hidden-import=matplotlib.backends.backend_qtagg` and `--hidden-import=reportlab.pdfbase.ttfonts` or the EXE crashes on launch.

### 7. Adding a new calculation module
1. Create `core/New_calculator.py`: InputParams dataclass, Results dataclass, Calculator class with `calculate()` and `get_calculation_steps()`
2. Create `gui/New_page.py`: inherit `BasePage`, implement the 6 required methods
3. Create `reports/new_pdf.py`: inherit `BaseReportGenerator`, implement `generate()`
4. Register in `main.py` PAGES list
5. Add to `PCS_Platform.spec` datas if needed

### 8. Test without GUI
```python
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
# Then create QApplication + pages, call run_calculation() programmatically
```

### 9. Known technical debt
- **No unit tests**: core calculators are pure functions and easily testable
- **`build_exe.bat` and `LCL_Filter_Designer.spec` are outdated** — they reference the old `models/`/`views/`/`controllers/`/`utils/` directories removed in v1.0.2. Use `PCS_Platform.spec` instead.
- **MainWindow is an inner class** in main.py, preventing external reuse

### 10. Auto-update system
`core/update_checker.py` uses `QNetworkAccessManager` to async-GET a remote `version.json` on startup:
- Compares `remote.version` with `QApplication.applicationVersion()` using semantic versioning
- Network errors/timeouts fail silently — no impact on normal usage
- `force_update: true` → mandatory upgrade dialog; `false` → optional with Yes/No
- `UPDATE_URL` constant in `main.py` near the top of `main()` — change this when deploying

### 11. Release workflow (轻发布)
```bash
# 1. Build EXE
pyinstaller PCS_Platform.spec --clean --noconfirm
# 2. Copy to release
mkdir -p release/<version>
cp dist/PCS_Platform.exe release/<version>/PCS_Tool.exe
# 3. Update & copy version.json + changelog.txt to release/<version>/
# 4. Upload PCS_Tool.exe + version.json to server, update UPDATE_URL in main.py
```
