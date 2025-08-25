@echo off
:: Initialize variables
echo Batch started
set "url="
set "server="
set "duration="
set "args="
set "precleanup=false"
set "postcleanup=false"

:: Parse command line arguments
:parseArgs
if "%~1"=="" goto argsParsed
if "%~1"=="--url" (
    set "url=%~2"
    shift
    shift
    goto parseArgs
)
if "%~1"=="--server" (
    set "server=%~2"
    shift
    shift
    goto parseArgs
)


if "%~1"=="--duration" (
    set "duration=%~2"
    shift
    shift
    goto parseArgs
)
if "%~1"=="--precleanup" (
    set "precleanup=true"
    shift
    goto parseArgs
)
if "%~1"=="--postcleanup" (
    set "postcleanup=true"
    shift
    goto parseArgs
)

shift
goto parseArgs

:argsParsed
:: Perform pre-cleanup if requested
if "%precleanup%"=="true" (
    echo Performing PRE cleanup of browser processes...
    taskkill /F /IM chrome.exe /T >nul 2>&1
    taskkill /F /IM chromedriver.exe /T >nul 2>&1
    echo Browser processes terminated.
    timeout /t 5 /nobreak >nul
)

echo Batch started1
:: Build argument string for Python script
set "args="
if defined url set "args=%args% --url %url%"
if defined server set "args=%args% --server %server%"
if defined duration set "args=%args% --duration %duration%"

echo Running with arguments: %args%
py real_browser.py %args%

:: Perform post-cleanup if requested
if "%postcleanup%"=="true" (
    echo Performing POST cleanup of browser processes...
    taskkill /F /IM chrome.exe /T >nul 2>&1
    taskkill /F /IM chromedriver.exe /T >nul 2>&1
    echo Browser processes terminated.
)
