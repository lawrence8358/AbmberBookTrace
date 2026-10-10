from __future__ import annotations

import base64
import json
import mimetypes
import os
import socket
import threading
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .access import ACCOUNT_ENV, PASSWORD_ENV, verify_login
from .core import (
    BOOKTRACE_SITE,
    Candidate,
    MAX_ATTACHMENTS,
    MAX_IMAGE_BYTES,
    SETTINGS_PATH,
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
from .cover import MIN_REAL_COVER_BYTES, download_cover, sanmin_cover_url
from .runner import DEFAULT_ENGINE, DEFAULT_MODELS, EFFORT_LEVELS, ENGINE_LABELS, ENGINE_NAMES, CliResearchRunner, RunResult, detect_engines
from .saver import BookSaver, SaveResult


WEB_ROOT = Path(__file__).with_name("web")
MAX_REQUEST_BYTES = 80 * 1024 * 1024
MAX_BATCH_BOOKS = 10
# Each book is its own CLI run and all books sent together run at once. The ceiling leaves room for
# a full batch plus an answer about each of its books, so nothing the user sends has to wait.
MAX_PARALLEL_RESEARCH = MAX_BATCH_BOOKS * 2
MAX_CANDIDATE_COVERS = 6
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
MODEL_OPTIONS["claude-5x"] = MODEL_OPTIONS["claude"]
EFFORT_OPTIONS = [
    {"value": "", "label": "自動（由模型決定）"},
    {"value": "low", "label": "低 · 最快、最省"},
    {"value": "medium", "label": "中 · 一般"},
    {"value": "high", "label": "高 · 較仔細"},
    {"value": "xhigh", "label": "很高 · 更仔細、較慢"},
    {"value": "max", "label": "最高 · 最慢、最貴"},
]
# 固定連接埠，網址才能分享給別人；被占用時可用環境變數 BOOKTRACE_PORT 換一個。
DEFAULT_PORT = 8765
PORT_ENV = "BOOKTRACE_PORT"


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
    for name in ENGINE_NAMES:
        saved = raw_models.get(name)
        models[name] = normalize_model_choice(saved) or "" if isinstance(saved, str) else DEFAULT_MODELS[name]
    effort = raw.get("effort") if raw.get("effort") in EFFORT_LEVELS else ""
    return engine, models, bool(raw.get("auto_retry", True)), effort


@dataclass
class BookItem:
    """One book in the chat: its request, the researched outcome, and whether it was saved."""

    id: str
    text: str = ""
    images: tuple[Path, ...] = ()
    cover_index: int = -1
    outcome: ResearchOutcome | None = None
    cover_path: Path | None = None
    saved: bool = False
    saving: bool = False
    previous_context: str = ""


@dataclass
class ResearchJob:
    """One book waiting for (or holding) a research slot. `batch` is the shared tally of its "查多本" run."""

    item: BookItem
    request: ResearchRequest
    batch: dict[str, Any] | None = None
    first: bool = False


def _safe_text(value: Any, limit: int = 10000) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


class ChatState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.engines = detect_engines()
        saved_settings = _read_settings()
        self.engine, self.models, self.auto_retry, self.effort = load_preferences(saved_settings, self.engines)
        # 「BookTrace 登入」：和網站相同的帳號與密碼。先用小幫手存下來的，沒有再用環境變數。
        self.account = _safe_text(saved_settings.get("booktrace_account"), 50)
        self.password = saved_settings.get("booktrace_password") if isinstance(saved_settings.get("booktrace_password"), str) else ""
        if not (self.account and self.password):
            self.account = os.environ.get(ACCOUNT_ENV, "").strip()
            self.password = os.environ.get(PASSWORD_ENV, "")
        self.verify_login = verify_login
        self.events: list[dict[str, Any]] = []
        self.next_event_id = 1
        # Research and saving are separate lanes: a lane is "active" (status text) while it has work,
        # so confirming a book never has to wait for the other books still being researched.
        self.active: dict[str, str] = {}
        self.status = "準備就緒"
        self.runner_factory = CliResearchRunner
        self.max_parallel = MAX_PARALLEL_RESEARCH
        self.saver = BookSaver(lambda: (self.account, self.password))
        self.workspace = create_workspace()
        self.items: dict[str, BookItem] = {}
        self.last_item_id = ""
        self.media: dict[str, Path] = {}
        self.generation = 0
        self.research_queue: list[ResearchJob] = []
        self.research_workers = 0
        self.research_done = 0
        self.runners: dict[str, Any] = {}
        self.cancel_requested = False
        self.last_idle = "準備就緒"
        self.batch: dict[str, Any] | None = None
        self.save_queue: list[BookItem] = []

    @property
    def signed_in(self) -> bool:
        return bool(self.account and self.password)

    @property
    def busy(self) -> bool:
        return bool(self.active)

    @property
    def busy_mode(self) -> str:
        return "research" if "research" in self.active else "save" if "save" in self.active else ""

    def settings_payload(self) -> dict[str, Any]:
        return {
            "engines": [
                {"value": name, "label": ENGINE_LABELS[name]}
                for name in ENGINE_NAMES
                if name in self.engines
            ],
            "engine": self.engine,
            "models": dict(self.models),
            "modelOptions": MODEL_OPTIONS,
            "effort": self.effort,
            "effortOptions": EFFORT_OPTIONS,
            "autoRetry": self.auto_retry,
            # 只告訴畫面「有沒有登入、用哪個帳號」，密碼本身不會離開這個程式。
            "signedIn": self.signed_in,
            "account": self.account if self.signed_in else "",
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "busy": self.busy,
                "busyMode": self.busy_mode,
                "status": self.status,
                "canSave": any(self._item_can_save(item) for item in self.items.values()),
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
            self._persist_settings()
            self.emit("settings", settings=self.settings_payload())

    def _persist_settings(self) -> None:
        saved: dict[str, Any] = {
            "engine": self.engine,
            "models": dict(self.models),
            "effort": self.effort,
            "auto_retry": self.auto_retry,
        }
        if self.signed_in:
            saved["booktrace_account"] = self.account
            saved["booktrace_password"] = self.password
        _write_settings(saved)

    def sign_in(self, payload: dict[str, Any]) -> None:
        """Remember the BookTrace login once BookTrace itself confirms the account and password."""
        account = _safe_text(payload.get("account"), 50)
        if not account:
            raise UserInputError("請輸入帳號。")
        password = payload.get("password")
        if not isinstance(password, str) or not password:
            raise UserInputError("請輸入密碼。")
        if len(password) > 128:
            raise UserInputError("密碼不能超過 128 個字。")
        self.verify_login(account, password)
        with self.lock:
            self.account = account
            self.password = password
            self._persist_settings()
            self.emit("settings", settings=self.settings_payload())

    def sign_out(self) -> None:
        with self.lock:
            self.account = self.password = ""
            self._persist_settings()
            self.emit("settings", settings=self.settings_payload())

    def _compose_status(self, idle_status: str = "準備就緒") -> str:
        research, saving = self.active.get("research"), self.active.get("save")
        if research is not None:
            return research + ("（同時加入書架中）" if saving is not None else "")
        return saving if saving is not None else idle_status

    def _lane_text(self, lane: str, text: str) -> None:
        """Change a running lane's status line; shown through the polled status only."""
        with self.lock:
            if lane in self.active:
                self.active[lane] = text
                self.status = self._compose_status()

    def _start_lane(self, lane: str, status: str) -> None:
        with self.lock:
            self.active[lane] = status
            self.status = self._compose_status()
            self.emit("busy", busy=True, mode=self.busy_mode, status=self.status)

    def _end_lane(self, lane: str, idle_status: str) -> None:
        with self.lock:
            self.active.pop(lane, None)
            self.status = self._compose_status(idle_status)
            self.emit("busy", busy=self.busy, mode=self.busy_mode, status=self.status)

    def _runner_event(self, item_id: str, kind: str, text: str, deadline: float | None) -> None:
        if kind == "retry":
            self.emit("retry", message=text, deadline=deadline)
        elif kind.startswith("step:"):
            self.emit("step", itemId=item_id, kind=kind.removeprefix("step:"), text=text)
        else:
            # Only one book running: its live status is the lane's status. With several, the lane
            # shows overall progress instead, so their messages must not fight over one status line.
            with self.lock:
                alone = len(self.runners) <= 1 and not self.research_queue
            if not alone:
                return
            self._lane_text("research", text)
            if kind != "thinking":
                # "thinking" is a frequent token-count update: shown through the polled status only.
                self.emit("status", message=text, kind=kind)

    def _save_event(self, kind: str, text: str, deadline: float | None) -> None:
        if kind == "retry":
            self.emit("retry", message=text, deadline=deadline)
        else:
            self._lane_text("save", text)

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
            urls.append(f"/media/{media_id}")
        return tuple(paths), urls

    def send_message(self, payload: dict[str, Any]) -> None:
        # While books are being researched only an answer about one of them (a picked candidate,
        # extra clues) may start; it joins the line instead of waiting for the whole run to end.
        context_id = _safe_text(payload.get("contextItemId"), 40)
        with self.lock:
            if "research" in self.active and context_id not in self.items:
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
        with self.lock:
            # A follow-up answers one earlier item (the clicked card, else the latest one).
            earlier = self.items.get(context_id) or self.items.get(self.last_item_id)
            if earlier and not images:
                images, cover_index = earlier.images, earlier.cover_index
                image_urls = [self._media_url(path) for path in images]
        request = ResearchRequest(
            query=text,
            image_paths=images,
            previous_context=earlier.previous_context if earlier else "",
            designated_cover_index=cover_index,
        )
        validate_research_request(request)
        with self.lock:
            if "research" in self.active and context_id not in self.items:
                raise UserInputError("上一則訊息仍在處理中，可以先按停止。")
            item = self._new_item(text, images, cover_index)
            if self.batch is None:
                self.last_item_id = item.id
            self.emit("user", itemId=item.id, text=text, images=image_urls, coverIndex=cover_index)
            # An answer given during a "查多本" run counts toward that run's summary.
            job = ResearchJob(item, request, self.batch)
            if self.batch is not None:
                self.batch["ids"].append(item.id)
                self.batch["pending"] += 1
            self._enqueue_research([job], first="research" in self.active)

    def send_batch(self, payload: dict[str, Any]) -> None:
        """Research several books at the same time (a few at once); each row is one book (text and/or one photo)."""
        with self.lock:
            if "research" in self.active:
                raise UserInputError("上一則訊息仍在處理中，可以先按停止。")
            if not self.engines:
                raise UserInputError("找不到 Codex 或 Claude CLI，請先安裝並登入。")
        rows = payload.get("items")
        if not isinstance(rows, list) or not rows:
            raise UserInputError("請至少加入一本書。")
        if len(rows) > MAX_BATCH_BOOKS:
            raise UserInputError(f"一次最多查 {MAX_BATCH_BOOKS} 本書。")
        prepared: list[tuple[str, list[str], int, ResearchRequest]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise UserInputError("書籍資料格式不正確。")
            text = _safe_text(row.get("text"), 2000)
            raw_image = row.get("image")
            images, urls = self._save_uploaded_images([raw_image] if raw_image else [])
            # One photo per book; the user says whether that photo is the front cover.
            cover_index = 0 if images and row.get("isCover") is True else -1
            request = ResearchRequest(query=text, image_paths=images, designated_cover_index=cover_index)
            validate_research_request(request)
            prepared.append((text, urls, cover_index, request))
        with self.lock:
            if "research" in self.active:
                raise UserInputError("上一則訊息仍在處理中，可以先按停止。")
            self.last_item_id = ""
            items = [
                self._new_item(text, request.image_paths, cover_index)
                for text, _, cover_index, request in prepared
            ]
            batch = {"total": len(items), "ids": [item.id for item in items], "pending": len(items)}
            self.batch = batch
            jobs = []
            for index, (item, (text, urls, cover_index, request)) in enumerate(zip(items, prepared), start=1):
                self.emit(
                    "user", itemId=item.id, text=text, images=urls, coverIndex=cover_index, index=index, total=len(items)
                )
                jobs.append(ResearchJob(item, request, batch))
            self._enqueue_research(jobs)

    def _new_item(self, text: str, images: tuple[Path, ...], cover_index: int) -> BookItem:
        item = BookItem(id=uuid.uuid4().hex[:12], text=text, images=images, cover_index=cover_index)
        self.items[item.id] = item
        return item

    @staticmethod
    def _item_ready(item: BookItem) -> bool:
        return bool(item.outcome and item.outcome.ready and item.cover_path)

    @classmethod
    def _item_can_save(cls, item: BookItem) -> bool:
        return cls._item_ready(item) and not item.saved and not item.saving

    def _media_url(self, path: Path) -> str:
        return f"/media/{self._media_id_for(path)}"

    def _enqueue_research(self, jobs: list[ResearchJob], first: bool = False) -> None:
        """Queue books for research and start workers up to the parallel limit. Call with the lock held.

        `first` puts them ahead of books that have not started (an answer about a book already shown),
        but behind earlier answers, so several answers run in the order they were given.
        """
        if first:
            position = 0
            while position < len(self.research_queue) and self.research_queue[position].first:
                position += 1
            for job in jobs:
                job.first = True
            self.research_queue[position:position] = jobs
        else:
            self.research_queue.extend(jobs)
        if "research" not in self.active:
            self.cancel_requested = False
            self.research_done = 0
            self._start_lane("research", self._research_status())
        for _ in range(min(self.max_parallel - self.research_workers, len(self.research_queue))):
            self.research_workers += 1
            threading.Thread(target=self._research_worker, args=(self.generation,), daemon=True).start()
        self._lane_text("research", self._research_status())

    def _research_status(self) -> str:
        if self.cancel_requested:
            return "正在停止…"
        running, waiting = len(self.runners), len(self.research_queue)
        total = self.research_done + running + waiting
        if total <= 1:
            return "正在辨識並查證這本書…"
        return f"已查完 {self.research_done} / {total} 本，正在同時查 {running} 本" + (
            f"，還有 {waiting} 本排隊" if waiting else ""
        )

    def _research_worker(self, generation: int) -> None:
        while True:
            with self.lock:
                if generation != self.generation or not self.research_queue:
                    self.research_workers -= 1
                    if self.research_workers == 0:
                        label = "已停止" if self.cancel_requested else self.last_idle
                        self.cancel_requested = False
                        self.batch = None
                        self._end_lane("research", label)
                    return
                job = self.research_queue.pop(0)
                runner = self.runner_factory()
                self.runners[job.item.id] = runner
                self._lane_text("research", self._research_status())
            try:
                idle = self._research_item(generation, job.item, job.request, runner)
            except Exception as error:  # an unexpected failure must not leave the lane stuck busy
                self.emit("assistant_error", itemId=job.item.id, message=f"查證時發生未預期的錯誤：{error}")
                idle = "查證未完成"
            with self.lock:
                self.runners.pop(job.item.id, None)
                self.research_done += 1
                if idle is not None:
                    self.last_idle = idle
                self._release_batch(job)
                self._lane_text("research", self._research_status())

    def _release_batch(self, job: ResearchJob) -> None:
        """One book of a "查多本" run is over; the run's summary goes out after the last one. Lock held."""
        batch = job.batch
        if batch is None:
            return
        batch["pending"] -= 1
        if batch["pending"] > 0:
            return
        ready = sum(1 for item_id in batch["ids"] if self._item_ready(self.items[item_id]))
        saveable = sum(1 for item_id in batch["ids"] if self._item_can_save(self.items[item_id]))
        self.emit("batch_finished", total=batch["total"], ready=ready, itemIds=batch["ids"])
        self.last_idle = f"已查完，{saveable} 本可以加入書架"
        if self.batch is batch:
            self.batch = None

    def _research_item(
        self, generation: int, item: BookItem, request: ResearchRequest, runner: Any
    ) -> str | None:
        """Run one book through the read-only research. Returns the idle label (None = stale)."""
        with self.lock:
            engine = self.engine
            model = self.models.get(engine) or None
            effort = self.effort or None
            executable = self.engines[engine]
            auto_retry = self.auto_retry
        self.emit(
            "run_started",
            itemId=item.id,
            engine=ENGINE_LABELS[engine],
            model=model_label(engine, model or ""),
            effort=effort_label(effort or ""),
            at=time.time(),
        )
        started = time.time()
        result = runner.run(
            engine=engine,
            executable=executable,
            model=model,
            request=request,
            auto_retry=auto_retry,
            callback=partial(self._runner_event, item.id),
            effort=effort,
        )
        self.emit(
            "run_finished",
            itemId=item.id,
            ok=result.ok,
            seconds=round(time.time() - started),
            usage=result.usage,
            attempts=result.attempts,
        )
        return self._finish_research(generation, item, result)

    def _finish_research(self, generation: int, item: BookItem, result: RunResult) -> str | None:
        """Record the result on the item and emit its card; returns the idle label (None = stale)."""
        with self.lock:
            if generation != self.generation:
                return None
        if result.cancelled:
            self.emit("assistant_error", itemId=item.id, message="已停止這次查證。")
            return "已停止"
        if not result.ok:
            self.emit("assistant_error", itemId=item.id, message=self._friendly_error(result.error))
            return "查證未完成"
        try:
            source = result.structured if result.structured is not None else result.final_text
            outcome = parse_research_outcome(source)
        except UserInputError as error:
            self.emit("assistant_error", itemId=item.id, message=str(error))
            return "結果需要重新查證"
        with self.lock:
            item.outcome = outcome
            item.previous_context = json.dumps(outcome.raw, ensure_ascii=False)
        covers = [] if outcome.ready else self._candidate_covers(outcome.candidates)
        self.emit(
            "assistant", itemId=item.id, outcome=self._outcome_payload(outcome, covers), attempts=result.attempts
        )
        if not outcome.ready:
            return "需要你補充一點資料" if outcome.status == "needs_clarification" else "尚未找到可確認的版本"
        try:
            if 0 <= item.cover_index < len(item.images):
                cover_path = item.images[item.cover_index]
            elif outcome.book.cover_url or sanmin_cover_url(outcome.book.isbn):
                self.emit("status", message="正在準備封面讓你確認…", kind="status")
                cover_path = self._download_cover_for_review(outcome.book.cover_url, outcome.book.isbn)
            else:
                raise UserInputError("找不到可信封面。你可以貼上正面封面照，再傳一句「這張是封面」。")
        except (UserInputError, OSError) as error:
            self.emit("cover_error", itemId=item.id, message=str(error))
            return "缺少可確認的封面"
        with self.lock:
            if generation != self.generation:
                return None
            item.cover_path = cover_path
            media_url = self._media_url(cover_path)
        self.emit("cover_ready", itemId=item.id, url=media_url, canSave=True)
        return "請看過封面，再決定是否加入書架"

    def _download_cover_for_review(self, cover_url: str, isbn: str) -> Path:
        """Download the AI's cover; if it gave none or it fails, use Sanmin's ISBN-based image. The user still confirms it by eye."""
        urls = [url for url in (cover_url, sanmin_cover_url(isbn)) if url]
        last_error: Exception | None = None
        for url in urls:
            try:
                path = download_cover(url, self.workspace / f"cover-{uuid.uuid4().hex}.img", self.workspace)
            except (UserInputError, OSError) as error:
                last_error = error
                continue
            if path.stat().st_size < MIN_REAL_COVER_BYTES:
                path.unlink(missing_ok=True)
                last_error = UserInputError("下載到的是無圖佔位圖。")
                continue
            return path
        raise last_error or UserInputError("找不到可信封面。")

    def _candidate_covers(self, candidates: tuple[Candidate, ...]) -> list[str]:
        """Fetch each candidate's cover so the browser (img-src 'self') can show it; "" when unavailable."""
        shown = candidates[:MAX_CANDIDATE_COVERS]

        def fetch(candidate: Candidate) -> str:
            # Prefer the cover the AI saw on the source page; else the one Sanmin's CDN keeps for the ISBN.
            url = candidate.cover_url or sanmin_cover_url(candidate.isbn)
            if not url:
                return ""
            try:
                path = download_cover(url, self.workspace / f"candidate-{uuid.uuid4().hex}.img", self.workspace)
                if path.stat().st_size < MIN_REAL_COVER_BYTES:
                    path.unlink(missing_ok=True)
                    return ""
            except (UserInputError, OSError):
                return ""
            with self.lock:
                return self._media_url(path)

        if not shown:
            return []
        with ThreadPoolExecutor(max_workers=len(shown)) as pool:
            return list(pool.map(fetch, shown))

    def _media_id_for(self, path: Path) -> str:
        for media_id, existing in self.media.items():
            if existing == path:
                return media_id
        media_id = uuid.uuid4().hex
        self.media[media_id] = path
        return media_id

    @staticmethod
    def _outcome_payload(outcome: ResearchOutcome, candidate_covers: list[str] | None = None) -> dict[str, Any]:
        book = outcome.book
        covers = candidate_covers or []
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
            "candidates": [
                {
                    **{key: value for key, value in asdict(candidate).items() if key != "cover_url"},
                    "cover_media": covers[index] if index < len(covers) else "",
                }
                for index, candidate in enumerate(outcome.candidates)
            ],
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
        if any(item in value for item in ("需要登入：", "帳號或密碼不正確", "嘗試的次數太多")):
            return f"BookTrace 沒有接受目前的登入（{value.strip()}）。請按右上角齒輪，在「BookTrace 登入」重新輸入帳號與密碼；剛在網站換過密碼的話，這裡也要更新。"
        if "out of credits" in lower:
            return "這個助理的帳號額度已用完，需要補充額度後才能繼續。也可以到右上角設定改用另一個助理。"
        return value[-5000:]

    def save_book(self, item_id: str = "", save_all: bool = False) -> None:
        """Queue confirmed books for saving. Saving runs beside research: it never waits for other books."""
        with self.lock:
            if not self.signed_in:
                raise UserInputError("尚未登入 BookTrace。請按右上角齒輪，在「BookTrace 登入」輸入帳號與密碼後，再加入書籍。")
            if save_all:
                targets = [item for item in self.items.values() if self._item_can_save(item)]
                if not targets:
                    raise UserInputError("目前沒有可以加入的書。")
            else:
                item = self.items.get(item_id or self.last_item_id)
                if not item or not self._item_ready(item):
                    raise UserInputError("這本書尚未完成版本與封面確認。")
                if item.saved:
                    raise UserInputError("這本書已經保存完成。")
                if item.saving:
                    raise UserInputError("這本書正在加入 BookTrace，請稍候。")
                targets = [item]
            for item in targets:
                item.saving = True
            self.save_queue.extend(targets)
            if "save" not in self.active:
                self._start_lane("save", "正在加入書架、上傳封面並讀回確認…")
                threading.Thread(target=self._save_worker, args=(self.generation,), daemon=True).start()

    def _save_worker(self, generation: int) -> None:
        """Save queued books one at a time (they share one metadata file), however long research takes."""
        done = failures = 0
        while True:
            with self.lock:
                if generation != self.generation or not self.save_queue:
                    self.save_queue.clear()
                    if done + failures > 1:
                        label = f"已加入 {done} 本" + (f"，{failures} 本未完成" if failures else "")
                    else:
                        label = "保存未完成，可以再試一次" if failures else "已加入 BookTrace"
                    self._end_lane("save", label)
                    return
                item = self.save_queue.pop(0)
                auto_retry = self.auto_retry
                workspace = self.workspace
                if done + failures or self.save_queue:
                    number = done + failures + 1
                    self._lane_text("save", f"正在加入第 {number} / {number + len(self.save_queue)} 本…")
            try:
                result = self.saver.save(
                    book=item.outcome.book,
                    personal=item.outcome.personal,
                    cover_path=item.cover_path,
                    workspace=workspace,
                    correct=item.outcome.correct_existing,
                    replace_cover=item.outcome.replace_cover,
                    auto_retry=auto_retry,
                    callback=self._save_event,
                )
            except (UserInputError, OSError) as error:
                result = SaveResult(False, error=str(error))
            if self._finish_save(generation, item, result):
                done += 1
            else:
                failures += 1
            with self.lock:
                item.saving = False

    def _finish_save(self, generation: int, item: BookItem, result: SaveResult) -> bool:
        with self.lock:
            if generation != self.generation:
                return False
        if not result.ok or not result.payload:
            self.emit("assistant_error", itemId=item.id, message=self._friendly_error(result.error))
            return False
        book = result.payload.get("book") if isinstance(result.payload.get("book"), dict) else {}
        with self.lock:
            item.saved = True
        self.emit(
            "saved",
            itemId=item.id,
            title=book.get("title", "這本書"),
            bookId=book.get("id"),
            created=bool(result.payload.get("created")),
            coverUploaded=bool(result.payload.get("coverUploaded")),
            attempts=result.attempts,
            site=BOOKTRACE_SITE,
        )
        return True

    def cancel(self) -> None:
        """Stop all research (running books and the ones still waiting); saving cannot be interrupted."""
        with self.lock:
            if "research" not in self.active:
                if "save" in self.active:
                    raise UserInputError("正在寫入並驗證 BookTrace，這個步驟不能中途停止。")
                return
            self.cancel_requested = True
            waiting, self.research_queue = self.research_queue, []
            for job in waiting:
                self.emit("assistant_error", itemId=job.item.id, message="已停止，這本沒有查。")
                self._release_batch(job)
            runners = list(self.runners.values())
            self._lane_text("research", "正在停止…")
        for runner in runners:
            runner.cancel()

    def cancel_all(self) -> None:
        """Stop every running research on the way out, so no CLI process is left behind."""
        with self.lock:
            self.research_queue = []
            runners = list(self.runners.values())
        for runner in runners:
            runner.cancel()

    def new_chat(self) -> None:
        with self.lock:
            if self.busy:
                raise UserInputError("請先停止目前的處理，再開始新對話。")
            old_workspace = self.workspace
            self.workspace = create_workspace()
            self.media = {}
            self.items = {}
            self.last_item_id = ""
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
        if parsed.path == "/":
            body = (WEB_ROOT / "index.html").read_bytes()
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
        try:
            if parsed.path == "/api/message":
                self.server.state.send_message(self._read_json())
                self._json({"ok": True}, 202)
                return
            if parsed.path == "/api/settings":
                self.server.state.update_settings(self._read_json())
                self._json({"ok": True, "settings": self.server.state.settings_payload()})
                return
            if parsed.path == "/api/login":
                self.server.state.sign_in(self._read_json())
                self._json({"ok": True, "settings": self.server.state.settings_payload()})
                return
            if parsed.path == "/api/logout":
                self.server.state.sign_out()
                self._json({"ok": True, "settings": self.server.state.settings_payload()})
                return
            if parsed.path == "/api/batch":
                self.server.state.send_batch(self._read_json())
                self._json({"ok": True}, 202)
                return
            if parsed.path == "/api/save":
                payload = self._read_json()
                if payload.get("confirmed") is not True:
                    raise UserInputError("請先確認要寫入 BookTrace。")
                self.server.state.save_book(_safe_text(payload.get("itemId"), 40), payload.get("all") is True)
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
            self._json({"error": "找不到操作"}, 404)
        except UserInputError as error:
            self._json({"error": str(error)}, 409)
        except (OSError, ValueError) as error:
            self._json({"error": str(error)}, 400)


def _lan_addresses() -> list[str]:
    """This computer's LAN IPv4 addresses, so the link can be shared with people on the same network."""
    found: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith(("127.", "169.254.")) and address not in found:
                found.append(address)
    except OSError:
        pass
    return found


def _port_from_env() -> int:
    raw = os.environ.get(PORT_ENV, "").strip()
    if not raw:
        return DEFAULT_PORT
    try:
        port = int(raw)
    except ValueError:
        port = 0
    if not 1 <= port <= 65535:
        raise UserInputError(f"環境變數 {PORT_ENV} 必須是 1 到 65535 的數字。")
    return port


def launch_web_app() -> None:
    """Serve in the foreground until this console window is closed (or Ctrl+C)."""
    port = _port_from_env()
    state = ChatState()
    try:
        server = BookTraceServer(("0.0.0.0", port), state)
    except OSError as error:
        raise UserInputError(
            f"連接埠 {port} 無法使用（可能小幫手已經開著，或被其他程式占用）。"
            f"請先關掉另一個小幫手視窗，或設定環境變數 {PORT_ENV} 換一個連接埠。"
        ) from error
    print("BookTrace 小幫手已啟動，可以把下面的網址分享給別人：")
    for address in _lan_addresses():
        print(f"  http://{address}:{port}/")
    print(f"  http://localhost:{port}/  （只有這台電腦）")
    print()
    print("關閉這個視窗就會結束小幫手。")
    try:
        server.serve_forever(poll_interval=0.4)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        state.cancel_all()
        try:
            cleanup_workspace(state.workspace)
        except (OSError, ValueError):
            pass
