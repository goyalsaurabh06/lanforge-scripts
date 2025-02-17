@echo off

:: Initialize variables
echo Batch started
set "ip="
set "type="

:: Cleanup browser processes before execution
echo Cleaning up browser processes...
taskkill /F /IM chrome.exe /T >nul 2>&1
taskkill /F /IM chromedriver.exe /T >nul 2>&1
echo Browser processes terminated.

:: Parse command line arguments
:parseArgs
if "%~1"=="" goto argsParsed
if "%~1"=="--ip" (
    set "ip=%~2"
    shift
    shift
    goto parseArgs
)
if "%~1"=="--type" (
    set "type=%~2"
    shift
    shift
    goto parseArgs
)

echo Invalid argument: %~1
echo Usage: zoom_launcher.bat --ip <IP_ADDRESS> --type <host|client>
exit /b 1

:argsParsed
:: Check if required arguments are provided
if not defined ip (
    echo Error: --ip argument is required.
    echo Usage: zoom_launcher.bat --ip <IP_ADDRESS> --type <host|client>
    exit /b 1
)
if not defined type (
    echo Error: --type argument is required.
    echo Usage: zoom_launcher.bat --ip <IP_ADDRESS> --type <host|client>
    exit /b 1
)

:: Validate type argument
if not "%type%"=="host" if not "%type%"=="client" (
    echo Error: Invalid value for --type: %type%
    echo Usage: zoom_launcher.bat --ip <IP_ADDRESS> --type <host|client>
    exit /b 1
)

:: Execute the corresponding script
if "%type%"=="host" (
    echo Executing zoom_host.py with IP: %ip%
    py zoom_host.py --ip %ip%
) else if "%type%"=="client" (
    echo Executing zoom_client.py with IP: %ip%
    py zoom_client.py --ip %ip%
)

:: Cleanup browser processes after execution
echo Cleaning up browser processes...
taskkill /F /IM chrome.exe /T >nul 2>&1
taskkill /F /IM chromedriver.exe /T >nul 2>&1
echo Browser processes terminated.
