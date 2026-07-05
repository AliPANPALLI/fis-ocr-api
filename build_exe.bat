@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" -m pip install -r requirements.txt
"%PYTHON_EXE%" -m pip install pyinstaller
"%PYTHON_EXE%" -m PyInstaller --clean --noconfirm FisOcrApi.spec

echo.
echo EXE hazir:
echo dist\fis-ocr-api.exe
pause
