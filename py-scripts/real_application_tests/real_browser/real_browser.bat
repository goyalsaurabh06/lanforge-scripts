@echo off
:: Initialize variables
echo Batch started
set "url="
set "server="
set "duration="
set "args="
set "skip_precleanup=false"
set "skip_postcleanup=false"

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
if "%~1"=="--no_precleanup" (
    set "skip_precleanup=true"
    shift
    goto parseArgs
)
if "%~1"=="--no_postcleanup" (
    set "skip_postcleanup=true"
    shift
    goto parseArgs
)

shift
goto parseArgs

:argsParsed
:: Perform pre-cleanup unless skipped
if "%skip_precleanup%"=="false" (
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

:: Perform post-cleanup unless skipped
if "%skip_postcleanup%"=="false" (
    echo Performing POST cleanup of browser processes...
    taskkill /F /IM chrome.exe /T >nul 2>&1
    taskkill /F /IM chromedriver.exe /T >nul 2>&1
    echo Browser processes terminated.
)
