@echo off
cd /d "%~dp0"
echo Installing Ragasaan PO Python requirements...
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo Installation failed. Please check your Python installation and network connection.
  pause
  exit /b 1
)
echo Installation complete. Run start_windows.bat.
pause
