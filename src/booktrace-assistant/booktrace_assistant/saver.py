from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import BOOKTRACE_ENDPOINT, PROJECT_ROOT, PersonalFields, ResearchBook, UserInputError, validate_image
from .runner import EventCallback, classify_retry


@dataclass(frozen=True)
class SaveResult:
    ok: bool
    payload: dict[str, Any] | None = None
    error: str = ""
    cancelled: bool = False
    attempts: int = 1


class BookSaver:
    def __init__(self) -> None:
        self.cancel_event = threading.Event()
        self._process: subprocess.Popen[str] | None = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def save(
        self,
        book: ResearchBook,
        personal: PersonalFields,
        cover_path: Path,
        workspace: Path,
        correct: bool,
        replace_cover: bool,
        auto_retry: bool,
        callback: EventCallback,
    ) -> SaveResult:
        self.cancel_event.clear()
        validate_image(cover_path)
        metadata_path = workspace / "book.json"
        metadata_path.write_text(
            json.dumps(book.metadata(personal), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        current_book_id = book.existing_book_id
        attempt = 0
        while True:
            attempt += 1
            callback("attempt", f"寫入第 {attempt} 次嘗試", None)
            result = self._save_once(
                metadata_path,
                cover_path,
                current_book_id,
                correct,
                replace_cover,
            )
            result = SaveResult(**{**result.__dict__, "attempts": attempt})
            if result.ok or result.cancelled or not auto_retry:
                return result
            match = re.search(r"書籍 ID\s+(\d+)\s+已存在", result.error)
            if match:
                current_book_id = int(match.group(1))
            decision = classify_retry(result.error, attempt)
            if not decision.retry:
                return result
            callback("retry", decision.reason, time.time() + decision.delay_seconds)
            if self.cancel_event.wait(decision.delay_seconds):
                return SaveResult(False, error="已由使用者取消", cancelled=True, attempts=attempt)

    def _save_once(
        self,
        metadata_path: Path,
        cover_path: Path,
        book_id: int | None,
        correct: bool,
        replace_cover: bool,
    ) -> SaveResult:
        helper = Path(__file__).with_name("enrich_book.py")
        # The UI is normally launched with pythonw.exe; run the helper with the console
        # interpreter beside it so its stdout/stderr are always available.
        interpreter = Path(sys.executable)
        if interpreter.name.lower() == "pythonw.exe" and interpreter.with_name("python.exe").is_file():
            interpreter = interpreter.with_name("python.exe")
        command = [
            str(interpreter),
            str(helper),
            "--endpoint",
            BOOKTRACE_ENDPOINT,
            "--metadata",
            str(metadata_path),
            "--cover",
            str(cover_path),
        ]
        if book_id is not None:
            command.extend(["--book-id", str(book_id)])
        if correct:
            command.append("--correct")
        if replace_cover:
            command.append("--replace-cover")
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
                env=environment,
            )
            self._process = process
            stdout, stderr = process.communicate()
        except OSError as error:
            return SaveResult(False, error=f"無法啟動 BookTrace 保存工具：{error}")
        finally:
            self._process = None
        if self.cancel_event.is_set():
            return SaveResult(False, error="已由使用者取消", cancelled=True)
        if process.returncode != 0:
            return SaveResult(False, error=stderr.strip() or f"保存工具失敗（代碼 {process.returncode}）")
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as error:
            return SaveResult(False, error="BookTrace 已回應，但保存結果格式無法讀取。")
        if not isinstance(payload, dict) or not isinstance(payload.get("book"), dict):
            return SaveResult(False, error="BookTrace 保存結果缺少書籍資料。")
        return SaveResult(True, payload=payload)

