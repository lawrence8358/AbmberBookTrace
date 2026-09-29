from __future__ import annotations

import os
import subprocess
import sys
import traceback


def _kill_stray_instances() -> int:
    """End assistant processes that predate server.json (e.g. an older version still running)."""
    if os.name != "nt":
        return 0
    script = (
        "$me = " + str(os.getpid()) + "; "
        "$found = Get-CimInstance Win32_Process | Where-Object { "
        # Only Python interpreters: shells whose command line merely mentions the module must survive.
        "$_.ProcessId -ne $me -and $_.Name -match '^(python|pythonw|py|pyw)(\\d|\\.)*exe$' "
        "-and $_.CommandLine -match '-m\\s+booktrace_assistant(\\s|\"|$)' -and $_.CommandLine -notmatch '--stop' }; "
        "$found | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
        "@($found).Count"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return int((completed.stdout or "0").strip() or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def stop() -> None:
    from .webapp import stop_running_instance

    stopped = stop_running_instance()
    stopped = _kill_stray_instances() > 0 or stopped
    print("BookTrace 小幫手已關閉。" if stopped else "BookTrace 小幫手目前沒有在執行。")


def main() -> None:
    if "--stop" in sys.argv[1:]:
        stop()
        return
    try:
        from .webapp import launch_web_app

        launch_web_app()
    except Exception as error:  # Startup errors must remain visible when launched with pythonw.
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "BookTrace 小幫手無法啟動",
            f"{error}\n\n詳細資訊：\n{traceback.format_exc(limit=4)}",
        )
        root.destroy()


if __name__ == "__main__":
    main()
