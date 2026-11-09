@echo off
setlocal
set "practiceExecutable=%LOCALAPPDATA%\Programs\MobileDesk\MobileDesk.exe"
if not exist "%practiceExecutable%" set "practiceExecutable=%~dp0..\dist\MobileDesk\MobileDesk.exe"
if not exist "%practiceExecutable%" (
  echo Install Mobile Desk 1.6.0 first, then run this practice launcher again.
  pause
  exit /b 1
)
start "" "%practiceExecutable%" --data-dir "%~dp0shop-data"
