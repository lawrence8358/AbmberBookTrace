from __future__ import annotations

import json
import urllib.error
import urllib.request

from .core import BOOKTRACE_SITE, UserInputError

# 寫入 BookTrace（新增、補齊資料、上傳封面）使用和網站相同的帳號與密碼。
# 保存工具與 MCP 客戶端從這兩個環境變數讀取。
ACCOUNT_ENV = "BOOKTRACE_USERNAME"
PASSWORD_ENV = "BOOKTRACE_PASSWORD"
LOGIN_URL = BOOKTRACE_SITE + "api/auth/login"


def _server_message(error: urllib.error.HTTPError) -> str:
    try:
        return str(json.loads(error.read().decode("utf-8")).get("message", ""))
    except (ValueError, OSError, AttributeError):
        return ""


def verify_login(account: str, password: str, url: str = LOGIN_URL) -> None:
    """Log in to BookTrace the same way the website does, so a wrong password is caught when it is entered."""
    request = urllib.request.Request(
        url,
        data=json.dumps({"userName": account, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "booktrace-assistant/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
    except urllib.error.HTTPError as error:
        message = _server_message(error)
        if error.code in (401, 429):
            raise UserInputError(message or "BookTrace 不接受這組帳號與密碼。") from error
        raise UserInputError(f"BookTrace 回應異常（{error.code}），請稍後再試。") from error
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise UserInputError("無法連線到 BookTrace 確認登入，請檢查網路後再試。") from error
