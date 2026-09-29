@echo off
rem Keep this file ASCII-only with CRLF line endings: cmd.exe misreads
rem batch files that mix UTF-8 text with "chcp 65001".
cd /d "%~dp0"

where pyw.exe >nul 2>nul
if not errorlevel 1 goto use_pyw
where pythonw.exe >nul 2>nul
if not errorlevel 1 goto use_pythonw
where python.exe >nul 2>nul
if not errorlevel 1 goto use_python
goto no_python

:use_pyw
start "" pyw.exe -3 -m booktrace_assistant
exit /b 0

:use_pythonw
start "" pythonw.exe -m booktrace_assistant
exit /b 0

:use_python
python.exe -m booktrace_assistant
exit /b %errorlevel%

:no_python
echo Python 3 was not found. Please install it from https://www.python.org/downloads/
echo Then double-click this file again.
start "" https://www.python.org/downloads/
pause
exit /b 1
