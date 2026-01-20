@echo off
REM -----------------------------------------
REM Instagram Reels Automation Launcher (Windows)
REM -----------------------------------------

REM Use system Python (adjust only if needed)
set PYTHON=python

REM Selenium script location (CONFIRMED)
set SCRIPT="C:\Program Files (x86)\LANforge-Server\instagram.py"

REM Forward all arguments from LANforge
%PYTHON% %SCRIPT% %*

