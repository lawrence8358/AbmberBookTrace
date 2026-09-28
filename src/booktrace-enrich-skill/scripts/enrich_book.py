"""Save verified book metadata and an actual cover through BookTrace HTTP MCP."""
import argparse
import base64
import datetime
import json
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

MAX_IMAGE = 5 * 1024 * 1024
FIELDS = {"title", "author", "isbn", "publisher", "category", "location", "detailedLocation", "notes", "publicationDate", "purchaseDate"}


def isbn(value):
    return re.sub(r"[\s-]", "", value or "").upper()


def cover_bytes(path):
    if path.stat().st_size > MAX_IMAGE:
        raise ValueError("封面圖片不可超過 5 MB")
    data = path.read_bytes()
    if data.startswith(b"\xff\xd8\xff"):
        kind = "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = "image/png"
    elif data.startswith((b"GIF87a", b"GIF89a")):
        kind = "image/gif"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        kind = "image/webp"
    else:
        raise ValueError("封面不是支援的 JPG、PNG、GIF 或 WebP 圖片")
    return data, kind


class Mcp:
    def __init__(self, endpoint):
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("MCP 端點必須是 HTTP 或 HTTPS 網址")
        self.endpoint = endpoint
        self.headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"}
        self.counter = 0
        result = self.rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "booktrace-enrich", "version": "1.0"}})
        self.headers["MCP-Protocol-Version"] = result["protocolVersion"]
        self.rpc("notifications/initialized", {}, notification=True)
        available = {tool["name"] for tool in self.rpc("tools/list", {})["tools"]}
        required = {"find_book", "get_book", "add_book", "update_book", "upload_book_cover"}
        if not required <= available:
            raise ValueError("MCP 缺少技能需要的工具：" + ", ".join(sorted(required - available)))

    def rpc(self, method, params, notification=False):
        self.counter += 1
        body = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notification:
            body["id"] = self.counter
        request = urllib.request.Request(self.endpoint, json.dumps(body, ensure_ascii=False).encode("utf-8"), self.headers)
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
                data = "\n".join(line[5:].lstrip() for line in event.splitlines() if line.startswith("data:"))
                if data:
                    messages.append(json.loads(data))
            message = next((item for item in messages if item.get("id") == self.counter), None)
            if message is None:
                raise ValueError("MCP 沒有回傳對應的 JSON-RPC 結果")
        if "error" in message:
            raise ValueError(message["error"].get("message", "MCP 協定錯誤"))
        return message["result"]

    def call(self, name, arguments):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise ValueError("; ".join(item.get("text", "") for item in result.get("content", [])))
        text = next(item["text"] for item in result["content"] if item["type"] == "text")
        return json.loads(text)


def run(args):
    metadata = json.loads(args.metadata.read_text(encoding="utf-8-sig"))
    unexpected = set(metadata) - FIELDS - {"sources"}
    if unexpected:
        raise ValueError("未知欄位：" + ", ".join(sorted(unexpected)))
    if not isinstance(metadata.get("title"), str) or not metadata["title"].strip():
        raise ValueError("書名必填")
    sources = metadata.pop("sources", [])
    if not sources or not isinstance(sources, list) or not all(isinstance(url, str) and urllib.parse.urlparse(url).scheme in ("http", "https") for url in sources):
        raise ValueError("sources 必須包含實際查證過的商品頁網址")
    for field, value in metadata.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(field + " 必須是字串或 null")
    for field in ("publicationDate", "purchaseDate"):
        value = metadata.get(field)
        if value is not None and (not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) or datetime.date.fromisoformat(value).isoformat() != value):
            raise ValueError(field + " 必須是有效的 YYYY-MM-DD")
    content, content_type = cover_bytes(args.cover)
    if not metadata.get("notes"):
        metadata["notes"] = "資料來源：\n" + "\n".join(sources)
    client = Mcp(args.endpoint)
    if args.book_id:
        book = client.call("get_book", {"id": args.book_id})
    else:
        matches = client.call("find_book", {key: metadata[key] for key in ("isbn", "title", "author") if metadata.get(key)})["books"]
        if len(matches) > 1:
            raise ValueError("找到多本候選，請核對版本並以 --book-id 指定：" + ", ".join(str(book["id"]) for book in matches))
        book = matches[0] if matches else None
    created = False
    if book is None:
        result = client.call("add_book", metadata)
        book, created = result["book"], result["created"]
    book_id = book["id"]
    try:
        if isbn(metadata.get("isbn")) and isbn(book.get("isbn")) and isbn(metadata["isbn"]) != isbn(book["isbn"]):
            raise ValueError("既有 ISBN 與查到版本不同，停止更新")
        if not created:
            book = client.call("update_book", {**metadata, "id": book_id, "fillMissingOnly": True})
        upload = args.replace_cover or not book.get("coverUrl")
        if upload:
            book = client.call("upload_book_cover", {"id": book_id, "imageBase64": base64.b64encode(content).decode("ascii"), "contentType": content_type})
        verified = client.call("get_book", {"id": book_id})
        for field in FIELDS:
            if verified.get(field) != book.get(field):
                raise ValueError("讀回欄位與保存結果不同：" + field)
        cover_url = urllib.parse.urljoin(args.endpoint, verified["coverUrl"] or "")
        if urllib.parse.urlparse(cover_url).netloc != urllib.parse.urlparse(args.endpoint).netloc:
            raise ValueError("封面網址不屬於目前書蹤站台")
        with urllib.request.urlopen(cover_url, timeout=30) as response:
            if not response.headers.get("Content-Type", "").startswith("image/"):
                raise ValueError("封面網址未回傳圖片")
            downloaded = response.read(MAX_IMAGE + 1)
        if not downloaded or (upload and downloaded != content):
            raise ValueError("封面讀回驗證失敗")
        return {"created": created, "coverUploaded": upload, "book": verified, "sources": sources}
    except Exception as error:
        raise ValueError(f"書籍 ID {book_id} 已存在；未完成步驟：{error}。修正後使用 --book-id {book_id} 重試。") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--metadata", required=True, type=pathlib.Path)
    parser.add_argument("--cover", required=True, type=pathlib.Path)
    parser.add_argument("--book-id", type=int)
    parser.add_argument("--replace-cover", action="store_true")
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
