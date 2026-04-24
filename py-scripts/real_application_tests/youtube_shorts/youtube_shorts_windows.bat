@echo off
REM =========================================================
REM  YOUTUBE SHORTS AUTOMATION - WINDOWS


SETLOCAL ENABLEDELAYEDEXPANSION

REM Always run from this BAT file's directory
cd /d "%~dp0"

REM ---------------------------------------------------------
REM Debug log (only change: logs dir + timestamp)

set LOG_DIR=%~dp0logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set TS=%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
set TS=%TS: =0%

set LOGFILE=%LOG_DIR%\yt_shorts_%TS%.log

echo ==== START %DATE% %TIME% ==== >> "%LOGFILE%"
echo Current Dir: %CD% >> "%LOGFILE%"

REM ---------------------------------------------------------
REM Verify Python availability
REM ---------------------------------------------------------
where py >> "%LOGFILE%" 2>&1
where python >> "%LOGFILE%" 2>&1

REM ---------------------------------------------------------
REM Parse command-line arguments

set scroll=
set duration=
set host=
set device_name=

:parseArgs
if "%~1"=="" goto afterArgs

if "%~1"=="--scroll"       set scroll=%~2
if "%~1"=="--duration"     set duration=%~2
if "%~1"=="--host"         set host=%~2
if "%~1"=="--device_name"  set device_name=%~2

shift
shift
goto parseArgs

:afterArgs

REM ---------------------------------------------------------
REM Log parsed values
echo Scroll=%scroll% >> "%LOGFILE%"
echo Duration=%duration% >> "%LOGFILE%"
echo Host=%host% >> "%LOGFILE%"
echo Device=%device_name% >> "%LOGFILE%"

REM ---------------------------------------------------------
REM Validate required args

if "%scroll%"=="" (
    echo ERROR: scroll is empty >> "%LOGFILE%"
    goto end
)

if "%duration%"=="" (
    echo ERROR: duration is empty >> "%LOGFILE%"
    goto end
)

REM ---------------------------------------------------------
REM Kill existing Chrome sessions
taskkill /F /IM chrome.exe >nul 2>&1
taskkill /F /IM chromedriver.exe >nul 2>&1

REM ---------------------------------------------------------
REM Run YouTube Shorts Selenium script

echo Launching youtube_shorts.py >> "%LOGFILE%"

py youtube_shorts.py ^
    --scroll "%scroll%" ^
    --duration "%duration%" ^
    --host "%host%" ^
    --device_name "%device_name%" >> "%LOGFILE%" 2>&1

REM ---------------------------------------------------------
REM End

:end
echo ==== END %DATE% %TIME% ==== >> "%LOGFILE%"
ENDLOCAL
