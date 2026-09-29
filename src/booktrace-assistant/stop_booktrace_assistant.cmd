@echo off
rem Keep this file ASCII-only with CRLF line endings (see start_booktrace_assistant.cmd).
cd /d "%~dp0"

where py.exe >nul 2>nul
if not errorlevel 1 goto use_py
where python.exe >nul 2>nul
if not errorlevel 1 goto use_python
echo Python 3 was not found.
pause
exit /b 1

:use_py
py.exe -3 -m booktrace_assistant --stop
goto done

:use_python
python.exe -m booktrace_assistant --stop

:done
"%SystemRoot%\System32\timeout.exe" /t 3 >nul
exit /b 0
