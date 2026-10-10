@echo off
rem Keep this file ASCII-only with CRLF line endings: cmd.exe misreads
rem batch files that mix UTF-8 text with "chcp 65001".
cd /d "%~dp0"
chcp 65001 >nul
title BookTrace Assistant

where py.exe >nul 2>nul
if not errorlevel 1 goto use_py
where python.exe >nul 2>nul
if not errorlevel 1 goto use_python
goto no_python

:use_py
py.exe -3 -m booktrace_assistant
goto done

:use_python
python.exe -m booktrace_assistant
goto done

:no_python
echo Python 3 was not found. Please install it from https://www.python.org/downloads/
echo Then double-click this file again.
start "" https://www.python.org/downloads/

:done
echo.
pause
