@echo off
REM ============================================================================
REM PCS计算平台 - PyInstaller打包脚本 (Windows)
REM
REM 使用方式: 双击运行或在终端中执行 build_exe.bat
REM 生成的可执行文件位于: .\dist\PCS_Platform.exe
REM ============================================================================

echo ========================================
echo   PCS计算平台 - EXE打包工具
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到Python,请先安装Python 3.12并添加到PATH
    pause
    exit /b 1
)

REM 检查并安装PyInstaller
echo [1/3] 检查PyInstaller...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo        正在安装 PyInstaller...
    pip install pyinstaller
)

REM 安装项目依赖
echo [2/3] 安装项目依赖...
pip install -r requirements.txt

REM 执行打包
echo [3/3] 开始打包...
echo.

pyinstaller ^
    --name="PCS_Platform" ^
    --onefile ^
    --windowed ^
    --icon=NONE ^
    --add-data="models;models" ^
    --add-data="views;views" ^
    --add-data="controllers;controllers" ^
    --add-data="utils;utils" ^
    --hidden-import=matplotlib.backends.backend_qtagg ^
    --hidden-import=matplotlib.backends.backend_svg ^
    --hidden-import=numpy ^
    --hidden-import=sympy ^
    --hidden-import=reportlab ^
    --hidden-import=reportlab.pdfbase.ttfonts ^
    --clean ^
    main.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   打包成功!
    echo   输出路径: .\dist\PCS_Platform.exe
    echo ========================================
) else (
    echo.
    echo [ERROR] 打包失败,请检查错误信息。
)

pause
