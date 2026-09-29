from __future__ import annotations

import base64
import json
import mimetypes
import os
import secrets
import threading
import time
import urllib.parse
import urllib.request
import uuid
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .core import (
    BOOKTRACE_SITE,
    MAX_ATTACHMENTS,
    MAX_IMAGE_BYTES,
    SETTINGS_PATH,
    WORK_ROOT,
    ResearchOutcome,
    ResearchRequest,
    UserInputError,
    cleanup_workspace,
    create_workspace,
    image_kind,
    normalize_model_choice,
    parse_research_outcome,
    validate_research_request,
)
from .cover import download_cover
from .runner import DEFAULT_ENGINE, DEFAULT_MODELS, EFFORT_LEVELS, CliResearchRunner, RunResult, detect_engines
from .saver import BookSaver, SaveResult


WEB_ROOT = Path(__file__).with_name("web")
MAX_REQUEST_BYTES = 30 * 1024 * 1024
MODEL_OPTIONS = {
    "codex": [
        {"value": "gpt-5.6-luna", "label": "Luna · 低費率（推薦）"},
        {"value": "gpt-5.6-terra", "label": "Terra · 平衡"},
        {"value": "gpt-5.6-sol", "label": "Sol · 較強"},
        {"value": "gpt-6-astra", "label": "Astra · 最高能力"},
        {"value": "", "label": "跟隨 Codex 預設"},
    ],
    "claude": [
        {"value": "claude-sonnet-5", "label": "Sonnet 5 · 平衡（推薦）"},
        {"value": "claude-haiku-4-5-20251001", "label": "Haiku 4.5 · 最省費用（較易認錯版本）"},
        {"value": "claude-opus-5-5", "label": "Opus 5.5 · 高能力"},
        {"value": "claude-fable-5-1", "label": "Fable 5.1 · 最高能力"},
        {"value": "", "label": "跟隨 Claude 預設"},
    ],
}
EFFORT_OPTIONS = [
    {"value": "", "label": "自動（由模型決定）"},
    {"value": "low", "label": "低 · 最快、最省"},
    {"value": "medium", "label": "中 · 一般"},
    {"value": "high", "label": "高 · 較仔細"},
    {"value": "xhigh", "label": "很高 · 更仔細、較慢"},
    {"value": "max", "label": "最高 · 最慢、最貴"},
]
# Closing the browser tab stops the polling; exit once nobody has polled for this long.
IDLE_SHUTDOWN_SECONDS = 5 * 60
SERVER_INFO_PATH = WORK_ROOT / "server.json"


def effort_label(effort: str) -> str:
    option = next((item for item in EFFORT_OPTIONS if item["value"] == effort), None)
    return option["label"].split("·")[0].strip() if option else effort


def model_label(engine: str, model: str) -> str:
    option = next((item for item in MODEL_OPTIONS.get(engine, []) if item["value"] == model), None)
    if option and model:
        return option["label"].split("·")[0].strip()
    return model or "CLI 預設模型"


def _read_settings() -> dict[str, Any]:
    try:
        payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_settings(payload: dict[str, Any]) -> None:
    try:
        SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_preferences(raw: dict[str, Any], engines: dict[str, str]) -> tuple[str, dict[str, str], bool, str]:
    """Restore the last engine/model/effort choices; "" means "follow the CLI default"."""
    requested = raw.get("engine")
    if requested in engines:
        engine = requested
    elif DEFAULT_ENGINE in engines:
        engine = DEFAULT_ENGINE
    else:
        engine = next(iter(engines), "")
    raw_models = raw.get("models") if isinstance(raw.get("models"), dict) else {}
    models = {}
    for name in ("codex", "claude"):
        saved = raw_models.get(name)
        models[name] = normalize_model_choice(saved) or "" if isinstance(saved, str) else DEFAULT_MODELS[name]
    effort = raw.get("effort") if raw.get("effort") in EFFORT_LEVELS else ""
    return engine, models, bool(raw.get("auto_retry", True)), effort


def _safe_text(value: Any, limit: int = 10000) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


class ChatState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.token = secrets.token_urlsafe(32)
        self.engines = detect_engines()
        self.engine, self.models, self.auto_retry, self.effort = load_preferences(_read_settings(), self.engines)
        self.events: list[dict[str, Any]] = []
        self.next_event_id = 1
        self.busy = False
        self.busy_mode = ""
        self.status = "準備就緒"
        self.runner = CliResearchRunner()
        self.saver = BookSaver()
        self.workspace = create_workspace()
        self.outcome: ResearchOutcome | None = None
        self.cover_path: Path | None = None
        self.cover_media_id = ""
        self.media: dict[str, Path] = {}
        self.previous_context = ""
        self.saved = False
        self.generation = 0
        self.last_activity = time.time()

    def touch(self) -> None:
        self.last_activity = time.time()

    def settings_payload(self) -> dict[str, Any]:
        return {
            "engines": [
                {"value": name, "label": "Codex" if name == "codex" else "Claude"}
                for name in ("codex", "claude")
                if name in self.engines
            ],
            "engine": self.engine,
            "models": dict(self.models),
            "modelOptions": MODEL_OPTIONS,
            "effort": self.effort,
            "effortOptions": EFFORT_OPTIONS,
            "autoRetry": self.auto_retry,
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "busy": self.busy,
                "busyMode": self.busy_mode,
                "status": self.status,
                "canSave": bool(self.outcome and self.outcome.ready and self.cover_path and not self.saved and not self.busy),
                "settings": self.settings_payload(),
                "lastEventId": self.next_event_id - 1,
                "booktraceSite": BOOKTRACE_SITE,
            }

    def emit(self, event_type: str, **payload: Any) -> int:
        with self.lock:
            event = {"id": self.next_event_id, "type": event_type, **payload}
            self.next_event_id += 1
            self.events.append(event)
            if len(self.events) > 600:
                self.events = self.events[-500:]
            return event["id"]

    def events_after(self, event_id: int) -> list[dict[str, Any]]:
        with self.lock:
            return [event for event in self.events if event["id"] > event_id]

    def update_settings(self, payload: dict[str, Any]) -> None:
        engine = _safe_text(payload.get("engine"), 20)
        model = _safe_text(payload.get("model"), 120)
        effort = _safe_text(payload.get("effort"), 20)
        if effort and effort not in EFFORT_LEVELS:
            raise UserInputError("思考深度的選項不正確。")
        if engine not in self.engines:
            raise UserInputError("選擇的助理尚未安裝。")
        if model and not all(character.isalnum() or character in "-_.:/" for character in model):
            raise UserInputError("模型 ID 含有不支援的字元。")
        with self.lock:
            if self.busy:
                raise UserInputError("助理正在處理訊息，請完成後再更換模型。")
            self.engine = engine
            self.models[engine] = model
            self.auto_retry = bool(payload.get("autoRetry", True))
            self.effort = effort
            _write_settings(
                {
                    "engine": self.engine,
                    "models": dict(self.models),
                    "effort": self.effort,
                    "auto_retry": self.auto_retry,
                }
            )
            self.emit("settings", settings=self.settings_payload())

    def _set_busy(self, mode: str, status: str) -> None:
        with self.lock:
            self.busy = True
            self.busy_mode = mode
            self.status = status
            self.emit("busy", busy=True, mode=mode, status=status)

    def _set_idle(self, status: str = "準備就緒") -> None:
        with self.lock:
            self.busy = False
            self.busy_mode = ""
            self.status = status
            self.emit("busy", busy=False, mode="", status=status)

    def _runner_event(self, kind: str, text: str, deadline: float | None) -> None:
        if kind == "retry":
            self.emit("retry", message=text, deadline=deadline)
        elif kind.startswith("step:"):
            self.emit("step", kind=kind.removeprefix("step:"), text=text)
        elif kind == "thinking":
            # Frequent token-count updates: shown through the polled status only.
            with self.lock:
                self.status = text
        else:
            with self.lock:
                self.status = text
            self.emit("status", message=text, kind=kind)

    def _save_uploaded_images(self, images: Any) -> tuple[tuple[Path, ...], list[str]]:
        if not isinstance(images, list):
            raise UserInputError("圖片資料格式不正確。")
        if len(images) > MAX_ATTACHMENTS:
            raise UserInputError(f"一次最多可加入 {MAX_ATTACHMENTS} 張圖片。")
        paths: list[Path] = []
        urls: list[str] = []
        suffixes = {"jpeg": ".jpg", "png": ".png", "gif": ".gif", "webp": ".webp"}
        for image in images:
            if not isinstance(image, dict):
                raise UserInputError("圖片資料格式不正確。")
            encoded = image.get("data")
            if not isinstance(encoded, str):
                raise UserInputError("圖片內容遺失。")
            try:
                raw = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError) as error:
                raise UserInputError("貼上的圖片內容無法讀取。") from error
            if not raw or len(raw) > MAX_IMAGE_BYTES:
                raise UserInputError("每張圖片必須小於 5 MB。")
            temporary = self.workspace / f"upload-{uuid.uuid4().hex}.img"
            temporary.write_bytes(raw)
            try:
                kind = image_kind(temporary)
            except UserInputError:
                temporary.unlink(missing_ok=True)
                raise
            path = temporary.with_suffix(suffixes[kind])
            temporary.rename(path)
            media_id = uuid.uuid4().hex
            self.media[media_id] = path
            paths.append(path)
            urls.append(f"/media/{media_id}?token={urllib.parse.quote(self.token)}")
        return tuple(paths), urls

    def send_message(self, payload: dict[str, Any]) -> None:
        with self.lock:
            if self.busy:
                raise UserInputError("上一則訊息仍在處理中，可以先按停止。")
            if not self.engines:
                raise UserInputError("找不到 Codex 或 Claude CLI，請先安裝並登入。")
        text = _safe_text(payload.get("text"), 12000)
        images, image_urls = self._save_uploaded_images(payload.get("images", []))
        cover_index = payload.get("coverIndex", -1)
        if not isinstance(cover_index, int) or isinstance(cover_index, bool):
            cover_index = -1
        if not (0 <= cover_index < len(images)):
            cover_index = -1
        request = ResearchRequest(
            query=text,
            image_paths=images,
            previous_context=self.previous_context,
            designated_cover_index=cover_index,
        )
        validate_research_request(request)
        with self.lock:
            self.generation += 1
            generation = self.generation
            self.outcome = None
            self.cover_path = None
            self.cover_media_id = ""
            self.saved = False
            engine = self.engine
            model = self.models.get(engine) or None
            effort = self.effort or None
            executable = self.engines[engine]
            auto_retry = self.auto_retry
            self.emit("user", text=text, images=image_urls, coverIndex=cover_index)
            self.emit(
                "run_started",
                engine="Codex" if engine == "codex" else "Claude",
                model=model_label(engine, model or ""),
                effort=effort_label(effort or ""),
                at=time.time(),
            )
            self._set_busy("research", "正在辨識並查證這本書…")

        def work() -> None:
            started = time.time()
            result = self.runner.run(
                engine=engine,
                executable=executable,
                model=model,
                request=request,
                auto_retry=auto_retry,
                callback=self._runner_event,
                effort=effort,
            )
            self.emit(
                "run_finished",
                ok=result.ok,
                seconds=round(time.time() - started),
                usage=result.usage,
                attempts=result.attempts,
            )
            self._finish_research(generation, result, images, cover_index)

        threading.Thread(target=work, daemon=True).start()

    def _finish_research(
        self,
        generation: int,
        result: RunResult,
        images: tuple[Path, ...],
        cover_index: int,
    ) -> None:
        with self.lock:
            if generation != self.generation:
                return
        if result.cancelled:
            self.emit("assistant_error", message="已停止這次查證。")
            self._set_idle("已停止")
            return
        if not result.ok:
            self.emit("assistant_error", message=self._friendly_error(result.error))
            self._set_idle("查證未完成")
            return
        try:
            source = result.structured if result.structured is not None else result.final_text
            outcome = parse_research_outcome(source)
        except UserInputError as error:
            self.emit("assistant_error", message=str(error))
            self._set_idle("結果需要重新查證")
            return
        with self.lock:
            self.outcome = outcome
            self.previous_context = json.dumps(outcome.raw, ensure_ascii=False)
        self.emit("assistant", outcome=self._outcome_payload(outcome), attempts=result.attempts)
        if not outcome.ready:
            label = "需要你補充一點資料" if outcome.status == "needs_clarification" else "尚未找到可確認的版本"
            self._set_idle(label)
            return
        try:
            if 0 <= cover_index < len(images):
                cover_path = images[cover_index]
            elif outcome.book.cover_url:
                self.emit("status", message="正在準備封面讓你確認…", kind="status")
                cover_path = download_cover(
                    outcome.book.cover_url,
                    self.workspace / f"cover-{uuid.uuid4().hex}.img",
                    self.workspace,
                )
            else:
                raise UserInputError("找不到可信封面。你可以貼上正面封面照，再傳一句「這張是封面」。")
        except (UserInputError, OSError) as error:
            self.emit("cover_error", message=str(error))
            self._set_idle("缺少可確認的封面")
            return
        with self.lock:
            if generation != self.generation:
                return
            self.cover_path = cover_path
            media_id = self._media_id_for(cover_path)
            self.cover_media_id = media_id
        self.emit(
            "cover_ready",
            url=f"/media/{media_id}?token={urllib.parse.quote(self.token)}",
            canSave=True,
        )
        self._set_idle("請看過封面，再決定是否加入書架")

    def _media_id_for(self, path: Path) -> str:
        for media_id, existing in self.media.items():
            if existing == path:
                return media_id
        media_id = uuid.uuid4().hex
        self.media[media_id] = path
        return media_id

    @staticmethod
    def _outcome_payload(outcome: ResearchOutcome) -> dict[str, Any]:
        book = outcome.book
        return {
            "status": outcome.status,
            "summary": outcome.summary,
            "ready": outcome.ready,
            "book": {
                "title": book.title,
                "author": book.author,
                "isbn": book.isbn,
                "publisher": book.publisher,
                "category": book.category,
                "publicationDate": book.publication_date,
                "existingBookId": book.existing_book_id,
                "sources": list(book.sources),
                "unknownFields": list(book.unknown_fields),
            },
            "candidates": [asdict(candidate) for candidate in outcome.candidates],
            "questions": list(outcome.questions),
            "userProvided": {
                "purchaseDate": outcome.personal.purchase_date,
                "location": outcome.personal.location,
                "detailedLocation": outcome.personal.detailed_location,
                "notes": outcome.personal.notes,
            },
            "requestedSave": outcome.wants_to_save,
        }

    @staticmethod
    def _friendly_error(value: str) -> str:
        lower = value.lower()
        if any(item in lower for item in ("not logged in", "please login", "authentication", "unauthorized")):
            return "助理還沒登入。請先完成 CLI 登入，再回來按一次送出。"
        if any(item in lower for item in ("model not found", "invalid model", "does not exist", "model is not supported")):
            return "這個帳號不能使用目前模型。請到右上角設定改選「跟隨 CLI 預設」或其他模型。"
        if "out of credits" in lower:
            return "這個助理的帳號額度已用完，需要補充額度後才能繼續。也可以到右上角設定改用另一個助理。"
        return value[-5000:]

    def save_book(self) -> None:
        with self.lock:
            if self.busy:
                raise UserInputError("目前仍在處理訊息。")
            if not self.outcome or not self.outcome.ready or not self.cover_path:
                raise UserInputError("這本書尚未完成版本與封面確認。")
            if self.saved:
                raise UserInputError("這本書已經保存完成。")
            generation = self.generation
            outcome = self.outcome
            cover_path = self.cover_path
            auto_retry = self.auto_retry
            self._set_busy("save", "正在加入書架、上傳封面並讀回確認…")

        def work() -> None:
            result = self.saver.save(
                book=outcome.book,
                personal=outcome.personal,
                cover_path=cover_path,
                workspace=self.workspace,
                correct=outcome.correct_existing,
                replace_cover=outcome.replace_cover,
                auto_retry=auto_retry,
                callback=self._runner_event,
            )
            self._finish_save(generation, result)

        threading.Thread(target=work, daemon=True).start()

    def _finish_save(self, generation: int, result: SaveResult) -> None:
        with self.lock:
            if generation != self.generation:
                return
        if not result.ok or not result.payload:
            self.emit("assistant_error", message=self._friendly_error(result.error))
            self._set_idle("保存未完成，可以再試一次")
            return
        book = result.payload.get("book") if isinstance(result.payload.get("book"), dict) else {}
        with self.lock:
            self.saved = True
        self.emit(
            "saved",
            title=book.get("title", "這本書"),
            bookId=book.get("id"),
            created=bool(result.payload.get("created")),
            coverUploaded=bool(result.payload.get("coverUploaded")),
            attempts=result.attempts,
            site=BOOKTRACE_SITE,
        )
        self._set_idle("已加入 BookTrace")

    def cancel(self) -> None:
        with self.lock:
            if not self.busy:
                return
            if self.busy_mode == "save":
                raise UserInputError("正在寫入並驗證 BookTrace，這個步驟不能中途停止。")
            self.status = "正在停止…"
        self.runner.cancel()

    def new_chat(self) -> None:
        with self.lock:
            if self.busy:
                raise UserInputError("請先停止目前的處理，再開始新對話。")
            old_workspace = self.workspace
            self.workspace = create_workspace()
            self.media = {}
            self.outcome = None
            self.cover_path = None
            self.cover_media_id = ""
            self.previous_context = ""
            self.saved = False
            self.generation += 1
            self.emit("reset")
        cleanup_workspace(old_workspace)

    def media_path(self, media_id: str) -> Path | None:
        with self.lock:
            path = self.media.get(media_id)
            if not path or not path.is_file():
                return None
            try:
                path.resolve().relative_to(self.workspace.resolve())
            except ValueError:
                return None
            return path


class BookTraceServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address: tuple[str, int], state: ChatState):
        self.state = state
        super().__init__(address, BookTraceHandler)


class BookTraceHandler(BaseHTTPRequestHandler):
    server: BookTraceServer

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _headers(self, content_type: str, length: int, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'",
        )
        self.end_headers()

    def _json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers("application/json; charset=utf-8", len(raw), status)
        self.wfile.write(raw)

    def _authorized(self, query: dict[str, list[str]]) -> bool:
        header = self.headers.get("X-BookTrace-Token", "")
        supplied = header or (query.get("token", [""])[0])
        return secrets.compare_digest(supplied, self.server.state.token)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise UserInputError("請求大小無效。") from error
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise UserInputError("訊息或圖片太大。")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UserInputError("訊息格式無法讀取。") from error
        if not isinstance(payload, dict):
            raise UserInputError("訊息格式無法讀取。")
        return payload

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.server.state.touch()
        if parsed.path == "/":
            if not self._authorized(query):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            template = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
            body = template.replace("__BOOKTRACE_TOKEN__", json.dumps(self.server.state.token)).encode("utf-8")
            self._headers("text/html; charset=utf-8", len(body))
            self.wfile.write(body)
            return
        if parsed.path in {"/app.css", "/app.js"}:
            filename = parsed.path.lstrip("/")
            path = WEB_ROOT / filename
            body = path.read_bytes()
            content_type = "text/css; charset=utf-8" if filename.endswith(".css") else "text/javascript; charset=utf-8"
            self._headers(content_type, len(body))
            self.wfile.write(body)
            return
        if not self._authorized(query):
            self._json({"error": "未授權"}, 403)
            return
        if parsed.path == "/api/state":
            self._json(self.server.state.snapshot())
            return
        if parsed.path == "/api/events":
            try:
                after = int(query.get("after", ["0"])[0])
            except ValueError:
                after = 0
            self._json({"events": self.server.state.events_after(max(0, after)), "state": self.server.state.snapshot()})
            return
        if parsed.path.startswith("/media/"):
            media_id = parsed.path.removeprefix("/media/")
            if not media_id.isalnum():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            path = self.server.state.media_path(media_id)
            if path is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            body = path.read_bytes()
            kind = image_kind(path)
            mime = {"jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}[kind]
            self._headers(mime, len(body))
            self.wfile.write(body)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.server.state.touch()
        if not self._authorized(query):
            self._json({"error": "未授權"}, 403)
            return
        try:
            if parsed.path == "/api/message":
                self.server.state.send_message(self._read_json())
                self._json({"ok": True}, 202)
                return
            if parsed.path == "/api/settings":
                self.server.state.update_settings(self._read_json())
                self._json({"ok": True, "settings": self.server.state.settings_payload()})
                return
            if parsed.path == "/api/save":
                payload = self._read_json()
                if payload.get("confirmed") is not True:
                    raise UserInputError("請先確認要寫入 BookTrace。")
                self.server.state.save_book()
                self._json({"ok": True}, 202)
                return
            if parsed.path == "/api/cancel":
                self.server.state.cancel()
                self._json({"ok": True})
                return
            if parsed.path == "/api/new":
                self.server.state.new_chat()
                self._json({"ok": True})
                return
            if parsed.path == "/api/shutdown":
                self._json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self._json({"error": "找不到操作"}, 404)
        except UserInputError as error:
            self._json({"error": str(error)}, 409)
        except (OSError, ValueError) as error:
            self._json({"error": str(error)}, 400)


def _running_instance() -> dict[str, Any] | None:
    """Return the server info of a live instance, or None."""
    try:
        info = json.loads(SERVER_INFO_PATH.read_text(encoding="utf-8"))
        request = urllib.request.Request(
            f"http://127.0.0.1:{int(info['port'])}/api/state",
            headers={"X-BookTrace-Token": str(info["token"])},
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            if response.status == 200:
                return info
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        pass
    return None


def _app_url(port: int, token: str) -> str:
    return f"http://127.0.0.1:{port}/?token={urllib.parse.quote(token)}"


def stop_running_instance() -> bool:
    """Ask a running instance to exit. Returns True when one was found."""
    info = _running_instance()
    if info is None:
        return False
    request = urllib.request.Request(
        f"http://127.0.0.1:{int(info['port'])}/api/shutdown",
        data=b"{}",
        headers={"X-BookTrace-Token": str(info["token"]), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5):
            pass
    except OSError:
        pass
    for _ in range(20):
        if _running_instance() is None:
            return True
        time.sleep(0.5)
    return True


def launch_web_app() -> None:
    existing = _running_instance()
    if existing is not None:
        # Double-clicking the launcher again just reopens the running assistant.
        webbrowser.open(_app_url(int(existing["port"]), str(existing["token"])), new=1)
        return
    state = ChatState()
    server = BookTraceServer(("127.0.0.1", 0), state)
    port = server.server_address[1]
    url = _app_url(port, state.token)
    SERVER_INFO_PATH.write_text(
        json.dumps({"pid": os.getpid(), "port": port, "token": state.token}), encoding="utf-8"
    )

    def idle_shutdown() -> None:
        while True:
            time.sleep(20)
            with state.lock:
                expired = not state.busy and time.time() - state.last_activity > IDLE_SHUTDOWN_SECONDS
            if expired:
                server.shutdown()
                return

    threading.Thread(target=idle_shutdown, daemon=True).start()
    webbrowser.open(url, new=1)
    try:
        server.serve_forever(poll_interval=0.4)
    finally:
        server.server_close()
        state.runner.cancel()
        try:
            info = json.loads(SERVER_INFO_PATH.read_text(encoding="utf-8"))
            if info.get("pid") == os.getpid():
                SERVER_INFO_PATH.unlink()
        except (OSError, ValueError):
            pass
        try:
            cleanup_workspace(state.workspace)
        except (OSError, ValueError):
            pass

