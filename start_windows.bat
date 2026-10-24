@echo off
cd /d "%~dp0"
echo Starting Ragasaan Purchase Order...
py -m streamlit run app.py
if errorlevel 1 (
 echo Streamlit could not start. Run install_windows.bat first.
)
pause
