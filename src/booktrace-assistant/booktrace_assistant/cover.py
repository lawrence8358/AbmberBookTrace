from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

from .core import (
    MAX_IMAGE_BYTES,
    SUPPORTED_SUFFIXES,
    UserInputError,
    ensure_public_host,
    image_kind,
    validate_public_url,
)


# Sanmin has no image for some ISBNs and answers 200 with a ~1 KB placeholder instead of a 404.
MIN_REAL_COVER_BYTES = 3000


def sanmin_cover_url(isbn: str) -> str:
    """Sanmin's CDN names covers by the first 9 digits of the ISBN-10 (ISBN-13 minus the 978 prefix)."""
    digits = isbn.replace("-", "").strip()
    if len(digits) != 13 or not digits.isdigit() or not digits.startswith("978"):
        return ""
    core = digits[3:12]
    return f"https://cdnec.sanmin.com.tw/product_images/{core[:3]}/{core}.jpg"


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        parsed = validate_public_url(newurl)
        ensure_public_host(parsed.hostname or "")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_cover(url: str, output_path: Path, workspace: Path) -> Path:
    parsed = validate_public_url(url)
    ensure_public_host(parsed.hostname or "")
    resolved_workspace = workspace.resolve()
    resolved_output = output_path.resolve()
    try:
        resolved_output.relative_to(resolved_workspace)
    except ValueError as error:
        raise UserInputError("封面只能下載到 BookTrace UI 的暫存資料夾。") from error
    opener = urllib.request.build_opener(SafeRedirectHandler())
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BookTrace-Assistant/1.0",
            "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif,*/*;q=0.5",
        },
    )
    try:
        with opener.open(request, timeout=45) as response:
            final = validate_public_url(response.geturl())
            ensure_public_host(final.hostname or "")
            content = response.read(MAX_IMAGE_BYTES + 1)
    except (urllib.error.URLError, OSError) as error:
        raise UserInputError(f"下載封面失敗：{error}") from error
    if not content:
        raise UserInputError("封面網址沒有回傳圖片內容。")
    if len(content) > MAX_IMAGE_BYTES:
        raise UserInputError("下載的封面超過 5 MB。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)
    try:
        kind = image_kind(output_path)
    except UserInputError:
        try:
            output_path.unlink()
        except OSError:
            pass
        raise UserInputError("封面網址回傳的內容不是支援的圖片。")
    if output_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        suffix = {"jpeg": ".jpg", "png": ".png", "gif": ".gif", "webp": ".webp"}[kind]
        renamed = output_path.with_suffix(suffix)
        output_path.replace(renamed)
        output_path = renamed
    return output_path

