@echo off
setlocal
set "KIT=%~dp0"
python -c "import sys,struct;sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 else 1)" >nul 2>nul
if errorlevel 1 (
  echo LHSORT_PYTHON_REQUIRED: Python 3.12 64-bit must be installed and on PATH.
  pause
  exit /b 1
)
python "%KIT%check_kit.py"
if errorlevel 1 goto failed
if not exist "%KIT%.venv\Scripts\python.exe" (
  python -m venv "%KIT%.venv"
  if errorlevel 1 goto failed
)
"%KIT%.venv\Scripts\python.exe" -m pip --isolated install --force-reinstall --no-index --only-binary=:all: --find-links "%KIT%wheels" academicos==0.1.0 wasmtime==36.0.0
if errorlevel 1 goto failed
"%KIT%.venv\Scripts\python.exe" -X utf8 "%KIT%menu.py"
if errorlevel 1 goto failed
exit /b 0
:failed
 echo LHSORT_START_FAILED: copy the error code, not private data.
pause
exit /b 1
