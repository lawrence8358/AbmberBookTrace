"""Save verified book metadata and an actual cover through BookTrace HTTP MCP."""
import argparse
import base64
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

MAX_IMAGE = 5 * 1024 * 1024
FIELDS = {
    "title",
    "author",
    "isbn",
    "publisher",
    "category",
    "location",
    "detailedLocation",
    "notes",
    "publicationDate",
    "purchaseDate",
}


def normalize_isbn(value):
    return re.sub(r"[\s-]", "", value or "").upper()


def read_cover(path):
    if path.stat().st_size > MAX_IMAGE:
        raise ValueError("封面圖片不可超過 5 MB")
    data = path.read_bytes()
    if data.startswith(b"\xff\xd8\xff"):
        content_type = "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        content_type = "image/png"
    elif data.startswith((b"GIF87a", b"GIF89a")):
        content_type = "image/gif"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        content_type = "image/webp"
    else:
        raise ValueError("封面不是支援的 JPG、PNG、GIF 或 WebP 圖片")
    return data, content_type


class McpClient:
    def __init__(self, endpoint):
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("MCP 端點必須是 HTTP 或 HTTPS 網址")
        self.endpoint = endpoint
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-11-25",
            "User-Agent": "booktrace-enrich/1.0",
        }
        # BookTrace 的新增與修改使用和網站相同的帳號密碼；從環境變數讀，不放在命令列參數。
        account = os.environ.get("BOOKTRACE_USERNAME", "").strip()
        password = os.environ.get("BOOKTRACE_PASSWORD", "")
        if account or password:
            if not (account and password):
                raise ValueError("寫入 BookTrace 需要同時設定 BOOKTRACE_USERNAME 與 BOOKTRACE_PASSWORD")
            local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
            if parsed.scheme != "https" and not local:
                raise ValueError("密碼只能透過 HTTPS 傳送（本機測試網址除外）")
            credentials = base64.b64encode((account + ":" + password).encode("utf-8")).decode("ascii")
            self.headers["Authorization"] = "Basic " + credentials
        self.counter = 0
        result = self.rpc(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "booktrace-enrich", "version": "1.0"},
            },
        )
        self.headers["MCP-Protocol-Version"] = result["protocolVersion"]
        self.rpc("notifications/initialized", {}, notification=True)
        available = {
            tool["name"] for tool in self.rpc("tools/list", {})["tools"]
        }
        required = {
            "find_book",
            "get_book",
            "add_book",
            "update_book",
            "upload_book_cover",
        }
        if not required <= available:
            missing = ", ".join(sorted(required - available))
            raise ValueError("MCP 缺少技能需要的工具：" + missing)

    def rpc(self, method, params, notification=False):
        self.counter += 1
        body = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notification:
            body["id"] = self.counter
        request = urllib.request.Request(
            self.endpoint,
            json.dumps(body, ensure_ascii=False).encode("utf-8"),
            self.headers,
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            session = response.headers.get("Mcp-Session-Id")
            if session:
                self.headers["Mcp-Session-Id"] = session
            raw = response.read().decode("utf-8")
        if notification:
            return None
        if raw.lstrip().startswith("{"):
            message = json.loads(raw)
        else:
            messages = []
            for event in raw.replace("\r\n", "\n").split("\n\n"):
                data = "\n".join(
                    line[5:].lstrip()
                    for line in event.splitlines()
                    if line.startswith("data:")
                )
                if data:
                    messages.append(json.loads(data))
            message = next(
                (item for item in messages if item.get("id") == self.counter),
                None,
            )
            if message is None:
                raise ValueError("MCP 沒有回傳對應的 JSON-RPC 結果")
        if "error" in message:
            raise ValueError(message["error"].get("message", "MCP 協定錯誤"))
        return message["result"]

    def call(self, name, arguments):
        result = self.rpc(
            "tools/call", {"name": name, "arguments": arguments}
        )
        if result.get("isError"):
            details = "; ".join(
                item.get("text", "") for item in result.get("content", [])
            )
            raise ValueError(details)
        payload = next(
            item["text"]
            for item in result["content"]
            if item["type"] == "text"
        )
        return json.loads(payload)


def load_metadata(path):
    metadata = json.loads(path.read_text(encoding="utf-8-sig"))
    unexpected = set(metadata) - FIELDS - {"sources"}
    if unexpected:
        raise ValueError("未知欄位：" + ", ".join(sorted(unexpected)))
    if not isinstance(metadata.get("title"), str) or not metadata["title"].strip():
        raise ValueError("書名必填")

    sources = metadata.pop("sources", [])
    valid_sources = (
        isinstance(sources, list)
        and sources
        and all(
            isinstance(url, str)
            and urllib.parse.urlparse(url).scheme in ("http", "https")
            for url in sources
        )
    )
    if not valid_sources:
        raise ValueError("sources 必須包含實際查證過的商品頁網址")

    for field, value in metadata.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(field + " 必須是字串或 null")
    for field in ("publicationDate", "purchaseDate"):
        value = metadata.get(field)
        valid_date = (
            value is None
            or (
                re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                and datetime.date.fromisoformat(value).isoformat() == value
            )
        )
        if not valid_date:
            raise ValueError(field + " 必須是有效的 YYYY-MM-DD")
    return metadata, sources


def run(args):
    if args.metadata:
        metadata, sources = load_metadata(args.metadata)
    elif args.book_id:
        metadata, sources = {}, []
    else:
        raise ValueError("未提供 --metadata 時必須以 --book-id 指定書籍")

    content, content_type = read_cover(args.cover)
    client = McpClient(args.endpoint)
    if args.book_id:
        book = client.call("get_book", {"id": args.book_id})
    else:
        query = {
            key: metadata[key]
            for key in ("isbn", "title", "author")
            if metadata.get(key)
        }
        matches = client.call("find_book", query)["books"]
        if len(matches) > 1:
            ids = ", ".join(str(book["id"]) for book in matches)
            raise ValueError("找到多本候選，請核對版本並以 --book-id 指定：" + ids)
        book = matches[0] if matches else None

    created = False
    if book is None:
        result = client.call("add_book", metadata)
        book, created = result["book"], result["created"]

    book_id = book["id"]
    try:
        expected_isbn = normalize_isbn(metadata.get("isbn"))
        current_isbn = normalize_isbn(book.get("isbn"))
        isbn_conflict = expected_isbn and current_isbn and expected_isbn != current_isbn
        if isbn_conflict and not args.correct:
            raise ValueError("既有 ISBN 與查到版本不同，停止更新")

        if not created and metadata:
            book = client.call(
                "update_book",
                {**metadata, "id": book_id, "fillMissingOnly": not args.correct},
            )

        upload = args.replace_cover or not book.get("coverUrl")
        if upload:
            book = client.call(
                "upload_book_cover",
                {
                    "id": book_id,
                    "imageBase64": base64.b64encode(content).decode("ascii"),
                    "contentType": content_type,
                },
            )

        verified = client.call("get_book", {"id": book_id})
        for field in FIELDS:
            if verified.get(field) != book.get(field):
                raise ValueError("讀回欄位與保存結果不同：" + field)

        cover_url = urllib.parse.urljoin(
            args.endpoint, verified.get("coverUrl") or ""
        )
        if (
            urllib.parse.urlparse(cover_url).netloc
            != urllib.parse.urlparse(args.endpoint).netloc
        ):
            raise ValueError("封面網址不屬於目前書蹤站台")
        request = urllib.request.Request(
            cover_url, headers={"User-Agent": "booktrace-enrich/1.0"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            if not response.headers.get("Content-Type", "").startswith("image/"):
                raise ValueError("封面網址未回傳圖片")
            downloaded = response.read(MAX_IMAGE + 1)
        if not downloaded or (upload and downloaded != content):
            raise ValueError("封面讀回驗證失敗")

        return {
            "created": created,
            "coverUploaded": upload,
            "book": verified,
            "sources": sources,
        }
    except Exception as error:
        message = (
            f"書籍 ID {book_id} 已存在；未完成步驟：{error}。"
            f"修正後使用 --book-id {book_id} 重試。"
        )
        raise ValueError(message) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--metadata", type=pathlib.Path)
    parser.add_argument("--cover", required=True, type=pathlib.Path)
    parser.add_argument("--book-id", type=int)
    parser.add_argument("--replace-cover", action="store_true")
    parser.add_argument(
        "--correct",
        action="store_true",
        help="使用者明確要求更正既有值：fillMissingOnly=false，允許更換 ISBN",
    )
    args = parser.parse_args()
    try:
        result = run(args)
    except (ValueError, OSError, KeyError, StopIteration) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())

