from __future__ import annotations

import json
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .core import (
    BOOKTRACE_ENDPOINT,
    PROJECT_ROOT,
    SCHEMA_PATH,
    ResearchRequest,
    build_research_prompt,
    compact_schema,
)


EventCallback = Callable[[str, str, float | None], None]


@dataclass(frozen=True)
class RunResult:
    ok: bool
    final_text: str = ""
    structured: dict[str, Any] | None = None
    error: str = ""
    exit_code: int | None = None
    cancelled: bool = False
    attempts: int = 1
    usage: str = ""


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    delay_seconds: float = 0
    reason: str = ""


# Shared by both CLIs: Claude `--effort`, Codex `model_reasoning_effort`. "" = model default.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

DEFAULT_ENGINE = "claude"
DEFAULT_MODELS = {
    "codex": "gpt-5.6-luna",
    # Haiku misidentified editions from cover photos in testing; Sonnet is the floor.
    "claude": "claude-sonnet-5",
    "claude-5x": "claude-sonnet-5",
}
# "claude-5x" is the same claude CLI run against a second account's config directory.
CLAUDE_5X_CONFIG_DIR = Path.home() / ".claude-5x"
ENGINE_NAMES = ("codex", "claude", "claude-5x")
ENGINE_LABELS = {"codex": "Codex", "claude": "Claude", "claude-5x": "Claude 5x"}


def detect_engines() -> dict[str, str]:
    found: dict[str, str] = {}
    for name in ("codex", "claude"):
        executable = shutil.which(name)
        if executable:
            found[name] = executable
    if "claude" in found and CLAUDE_5X_CONFIG_DIR.is_dir():
        found["claude-5x"] = found["claude"]
    return found


def _toml_string_array(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=True, separators=(",", ":"))


def build_codex_command(
    executable: str,
    request: ResearchRequest,
    model: str | None,
    project_root: Path = PROJECT_ROOT,
    effort: str | None = None,
) -> list[str]:
    # The MCP server is defined here rather than in a config file, so the assistant
    # needs no .codex/config.toml. project_doc_max_bytes=0 keeps the surrounding
    # repository's AGENTS.md (developer instructions) out of the research prompt.
    # --search and --ask-for-approval are top-level flags and must precede `exec`.
    # No --ignore-user-config: with it Codex 0.154 silently drops the -c mcp_servers.* definition,
    # so the model never sees find_book/get_book. Sandbox and approval are pinned by flags below.
    command = [
        executable,
        "--search",
        "--ask-for-approval",
        "never",
        "-c",
        "project_doc_max_bytes=0",
        "-c",
        f"mcp_servers.booktrace.url={json.dumps(BOOKTRACE_ENDPOINT)}",
        "-c",
        "mcp_servers.booktrace.tool_timeout_sec=120",
        "-c",
        f"mcp_servers.booktrace.enabled_tools={_toml_string_array(['find_book', 'get_book', 'list_books'])}",
        "-c",
        "mcp_servers.booktrace.required=true",
        "exec",
        "--json",
        "--ephemeral",
        "-C",
        str(project_root),
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "--output-schema",
        str(SCHEMA_PATH),
    ]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["-c", f"model_reasoning_effort={json.dumps(effort)}"])
    for path in request.image_paths:
        command.extend(["--image", str(path)])
    command.append("-")
    return command


def build_claude_command(
    executable: str,
    model: str | None,
    project_root: Path = PROJECT_ROOT,
    effort: str | None = None,
) -> list[str]:
    readable_tools = (
        "Read,WebSearch,WebFetch,mcp__booktrace__find_book,"
        "mcp__booktrace__get_book,mcp__booktrace__list_books"
    )
    denied_tools = (
        "Bash,PowerShell,Edit,Write,NotebookEdit,"
        "mcp__booktrace__add_book,mcp__booktrace__update_book,"
        "mcp__booktrace__upload_book_cover"
    )
    command = [
        executable,
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "dontAsk",
        "--permission-prompts",
        "none",
        "--strict-mcp-config",
        "--mcp-config",
        json.dumps({"mcpServers": {"booktrace": {"type": "http", "url": BOOKTRACE_ENDPOINT}}}),
        "--no-session-persistence",
        "--no-chrome",
        "--restricted",
        "--json-schema",
        compact_schema(),
        "--tools",
        readable_tools,
        "--allowedTools",
        readable_tools,
        "--disallowedTools",
        denied_tools,
    ]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["--effort", effort])
    return command


def _strip_ansi(value: str) -> str:
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value).strip()


def _parse_duration(text: str) -> float | None:
    text = text.lower()
    total = 0.0
    found = False
    units = {
        "h": 3600,
        "hr": 3600,
        "hrs": 3600,
        "hour": 3600,
        "hours": 3600,
        "小時": 3600,
        "m": 60,
        "min": 60,
        "mins": 60,
        "minute": 60,
        "minutes": 60,
        "分鐘": 60,
        "s": 1,
        "sec": 1,
        "secs": 1,
        "second": 1,
        "seconds": 1,
        "秒": 1,
    }
    for amount, unit in re.findall(
        r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|小時|minutes?|mins?|min|m|分鐘|seconds?|secs?|sec|s|秒)(?![a-z])",
        text,
    ):
        total += float(amount) * units[unit]
        found = True
    return total if found and total > 0 else None


def classify_retry(error_text: str, attempt: int) -> RetryDecision:
    text = error_text.lower()
    non_retryable = (
        "not logged in",
        "please login",
        "authentication",
        "unauthorized",
        "invalid api key",
        "model not found",
        "does not exist",
        "invalid model",
        "permission denied",
        "out of credits",
        "not supported",
        "mcp 缺少",
        "既有 isbn",
        "找到多本候選",
        "不是支援的",
        "sources 必須",
        "未知欄位",
    )
    if any(pattern in text for pattern in non_retryable):
        return RetryDecision(False)

    # "5-hour window" names the quota, not the wait; drop it before reading durations.
    duration = _parse_duration(re.sub(r"\b5[\s-]?hours?\b", " ", text))
    reset_epoch = re.search(r"\|(\d{10})\b", text)  # Claude: "usage limit reached|<unix time>"
    if reset_epoch:
        duration = max(0.0, int(reset_epoch.group(1)) - time.time())
    usage_limit = (
        "usage limit",
        "rate limit",
        "rate_limit",
        "hit your limit",
        "limit reached",
        "too many requests",
        "resets in",
        "try again in",
        "5-hour",
        "5 hour",
        "額度",
        "用量上限",
    )
    if any(pattern in text for pattern in usage_limit) or re.search(r"\b429\b", text):
        delay = duration if duration is not None else 300.0
        return RetryDecision(True, max(15.0, delay + 2.0), "目前額度或速率已達上限")

    transient = (
        "timed out",
        "timeout",
        "temporarily unavailable",
        "service unavailable",
        "overloaded",
        "connection reset",
        "connection aborted",
        "connection refused",
        "network error",
        "econnreset",
        "econnrefused",
        "暫時",
        "逾時",
        "連線中斷",
    )
    if any(pattern in text for pattern in transient) or re.search(r"\b50[234]\b", text):
        delay = min(300.0, 15.0 * (2 ** min(max(attempt - 1, 0), 5)))
        return RetryDecision(True, delay, "服務或網路暫時無法使用")
    return RetryDecision(False)


def _event_status(callback: EventCallback, text: str) -> None:
    if text:
        callback("status", text, None)


def _step(callback: EventCallback, kind: str, text: str) -> None:
    """Report one progress entry; kinds: note, think, search, fetch, booktrace, image, error, done."""
    text = " ".join(str(text).split())
    if text:
        callback(f"step:{kind}", text[:400], None)


BOOKTRACE_TOOL_LABELS = {
    "find_book": "在 BookTrace 書架查重",
    "get_book": "讀取 BookTrace 藏書",
    "list_books": "瀏覽 BookTrace 書架",
}


def _booktrace_step(callback: EventCallback, tool: str, arguments: Any) -> None:
    label = BOOKTRACE_TOOL_LABELS.get(tool, f"呼叫 BookTrace {tool}")
    details = ""
    if isinstance(arguments, dict):
        details = "、".join(f"{key}={value}" for key, value in arguments.items() if value not in (None, ""))
    _step(callback, "booktrace", f"{label}：{details}" if details else label)
    _event_status(callback, "正在比對 BookTrace 既有藏書…")


def _codex_event(
    payload: dict[str, Any], callback: EventCallback, context: dict[str, Any]
) -> tuple[str, dict[str, Any] | None, str]:
    event_type = payload.get("type")
    final = ""
    structured = None
    error = ""
    if event_type == "thread.started":
        _event_status(callback, "Codex 已開始查證")
    elif event_type == "turn.started":
        _event_status(callback, "正在比對版本與來源…")
    elif event_type in {"turn.failed", "error"}:
        details = payload.get("error") or payload.get("message") or payload
        error = details if isinstance(details, str) else json.dumps(details, ensure_ascii=False)
    elif event_type == "item.started":
        item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
        if item.get("type") == "reasoning":
            _event_status(callback, "正在思考…")
    elif event_type == "item.completed":
        item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
        item_type = item.get("type")
        if item_type in {"agent_message", "assistant_message"}:
            final = item.get("text", "") if isinstance(item.get("text"), str) else ""
        elif item_type == "reasoning":
            _step(callback, "think", item.get("text") or "思考了一下")
        elif item_type in {"web_search", "web_search_call"}:
            query = item.get("query") or ""
            _step(callback, "search", f"搜尋：{query}" if query else "搜尋網頁")
            _event_status(callback, "正在查閱網頁來源…")
        elif item_type in {"mcp_tool_call", "mcp_call"}:
            _booktrace_step(callback, str(item.get("tool", "")), item.get("arguments"))
            if item.get("error") or item.get("status") == "failed":
                _step(callback, "error", f"BookTrace 回應錯誤：{item.get('error') or '未知錯誤'}")
        elif item_type == "error":
            _step(callback, "error", item.get("message") or "發生錯誤")
    elif event_type == "turn.completed":
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        tokens = sum(value for value in usage.values() if isinstance(value, int))
        context["summary"] = f"共使用約 {tokens:,} tokens" if tokens else ""
        _event_status(callback, "已完成查證，正在整理結果…")
    return final, structured, error


def _tool_result_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text")
    return ""


def _claude_event(
    payload: dict[str, Any], callback: EventCallback, context: dict[str, Any]
) -> tuple[str, dict[str, Any] | None, str]:
    event_type = payload.get("type")
    final = ""
    structured = None
    error = ""
    tools: dict[str, str] = context.setdefault("tools", {})
    if event_type == "system" and payload.get("subtype") == "init":
        _event_status(callback, "Claude 已開始查證")
    elif event_type == "system" and payload.get("subtype") == "thinking_tokens":
        # Thinking text is not exposed by the CLI; only a running token estimate is.
        estimate = payload.get("estimated_tokens")
        callback("thinking", f"正在思考…（約 {estimate} tokens）" if estimate else "正在思考…", None)
    elif event_type == "assistant":
        message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
        for block in message.get("content", []):
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                _step(callback, "note", block.get("text", ""))
            elif block_type == "tool_use":
                name = str(block.get("name", ""))
                tools[str(block.get("id", ""))] = name
                arguments = block.get("input") if isinstance(block.get("input"), dict) else {}
                if name.startswith("mcp__booktrace__"):
                    _booktrace_step(callback, name.removeprefix("mcp__booktrace__"), arguments)
                elif name == "WebSearch":
                    _step(callback, "search", f"搜尋：{arguments.get('query', '')}")
                    _event_status(callback, "正在查閱網頁來源…")
                elif name == "WebFetch":
                    _step(callback, "fetch", f"開啟網頁：{arguments.get('url', '')}")
                    _event_status(callback, "正在閱讀網頁內容…")
                elif name == "Read":
                    _step(callback, "image", "檢視圖片")
                    _event_status(callback, "正在檢視圖片…")
                elif name == "StructuredOutput":
                    _step(callback, "note", "整理查證結果")
    elif event_type == "user":
        message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
        content = message.get("content") if isinstance(message.get("content"), list) else []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            text = _tool_result_text(block)
            http_error = re.match(r"The server returned HTTP ([45]\d\d)", text)
            if block.get("is_error") or http_error:
                name = tools.get(str(block.get("tool_use_id", "")), "")
                if http_error:
                    _step(callback, "error", f"網頁無法開啟（HTTP {http_error.group(1)}），改找其他來源")
                else:
                    label = "網頁無法開啟" if name == "WebFetch" else "工具執行失敗"
                    _step(callback, "error", f"{label}：{text[:160]}")
    elif event_type == "result":
        cost = payload.get("total_cost_usd")
        if isinstance(cost, (int, float)):
            context["summary"] = f"花費約 US${cost:.3f}"
        if payload.get("is_error") or payload.get("subtype") not in {None, "success"}:
            error = str(payload.get("result") or payload.get("error") or "Claude 執行失敗")
        else:
            final = payload.get("result", "") if isinstance(payload.get("result"), str) else ""
            possible = payload.get("structured_output")
            if isinstance(possible, dict):
                structured = possible
            _event_status(callback, "已完成查證，正在整理結果…")
    return final, structured, error


class CliResearchRunner:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self.cancel_event = threading.Event()

    def reset(self) -> None:
        self.cancel_event.clear()

    def cancel(self) -> None:
        self.cancel_event.set()
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            self._terminate(process)

    def run(
        self,
        engine: str,
        executable: str,
        model: str | None,
        request: ResearchRequest,
        auto_retry: bool,
        callback: EventCallback,
        effort: str | None = None,
    ) -> RunResult:
        self.reset()
        attempt = 0
        while True:
            attempt += 1
            callback("attempt", f"第 {attempt} 次嘗試", None)
            result = self._run_once(engine, executable, model, request, callback, effort)
            result = RunResult(**{**result.__dict__, "attempts": attempt})
            if result.ok or result.cancelled or not auto_retry:
                return result
            decision = classify_retry(result.error, attempt)
            if not decision.retry:
                return result
            callback("retry", decision.reason, time.time() + decision.delay_seconds)
            if self.cancel_event.wait(decision.delay_seconds):
                return RunResult(False, cancelled=True, error="已由使用者取消", attempts=attempt)

    def _run_once(
        self,
        engine: str,
        executable: str,
        model: str | None,
        request: ResearchRequest,
        callback: EventCallback,
        effort: str | None = None,
    ) -> RunResult:
        command = (
            build_codex_command(executable, request, model, effort=effort)
            if engine == "codex"
            else build_claude_command(executable, model, effort=effort)
        )
        prompt = build_research_prompt(request, engine)
        flags = 0
        kwargs: dict[str, Any] = {}
        if os.name == "nt":
            flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        environment["NO_COLOR"] = "1"
        if engine == "claude-5x":
            environment["CLAUDE_CONFIG_DIR"] = str(CLAUDE_5X_CONFIG_DIR)
        try:
            process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=flags,
                env=environment,
                **kwargs,
            )
        except OSError as error:
            return RunResult(False, error=f"無法啟動 {engine} CLI：{error}")
        with self._lock:
            self._process = process
        assert process.stdin is not None
        try:
            process.stdin.write(prompt)
            process.stdin.close()
        except OSError:
            self._terminate(process)
            return RunResult(False, error="無法把查證內容傳給 CLI。")

        lines: queue.Queue[tuple[str, str | None]] = queue.Queue()

        def pump(channel: str, stream: Any) -> None:
            try:
                for line in iter(stream.readline, ""):
                    lines.put((channel, line.rstrip("\r\n")))
            finally:
                lines.put((channel, None))

        assert process.stdout is not None and process.stderr is not None
        threading.Thread(target=pump, args=("stdout", process.stdout), daemon=True).start()
        threading.Thread(target=pump, args=("stderr", process.stderr), daemon=True).start()
        streams_done = 0
        stderr_lines: list[str] = []
        errors: list[str] = []
        final_messages: list[str] = []
        structured: dict[str, Any] | None = None
        parser = _codex_event if engine == "codex" else _claude_event
        context: dict[str, Any] = {}
        while streams_done < 2:
            if self.cancel_event.is_set() and process.poll() is None:
                self._terminate(process)
            try:
                channel, line = lines.get(timeout=0.2)
            except queue.Empty:
                continue
            if line is None:
                streams_done += 1
                continue
            if channel == "stderr":
                cleaned = _strip_ansi(line)
                if cleaned:
                    stderr_lines.append(cleaned)
                    stderr_lines = stderr_lines[-40:]
                continue
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            final, structured_value, error = parser(payload, callback, context)
            if final:
                final_messages.append(final)
            if structured_value is not None:
                structured = structured_value
            if error:
                errors.append(error)
        exit_code = process.wait()
        with self._lock:
            self._process = None
        if self.cancel_event.is_set():
            return RunResult(False, error="已由使用者取消", exit_code=exit_code, cancelled=True)
        final_text = final_messages[-1] if final_messages else ""
        if exit_code == 0 and (structured is not None or final_text):
            return RunResult(
                True,
                final_text=final_text,
                structured=structured,
                exit_code=exit_code,
                usage=context.get("summary", ""),
            )
        details = "\n".join(errors + stderr_lines[-12:]).strip()
        if not details:
            details = f"{engine} CLI 結束，但沒有回傳可讀取的結果（代碼 {exit_code}）。"
        return RunResult(False, final_text=final_text, structured=structured, error=details, exit_code=exit_code)

    @staticmethod
    def _terminate(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=10,
                    check=False,
                )
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except (OSError, subprocess.SubprocessError):
            try:
                process.kill()
            except OSError:
                pass
