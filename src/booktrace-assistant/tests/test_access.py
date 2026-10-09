import base64
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from booktrace_assistant import enrich_book
from booktrace_assistant.access import ACCOUNT_ENV, PASSWORD_ENV, verify_login
from booktrace_assistant.core import UserInputError, cleanup_workspace
from booktrace_assistant.runner import classify_retry
from booktrace_assistant.saver import BookSaver
from booktrace_assistant.webapp import ChatState

ACCOUNT = "reader"
PASSWORD = "my site password"


class SignInTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.settings_path = Path(folder.name) / "settings.json"
        patcher = mock.patch("booktrace_assistant.webapp.SETTINGS_PATH", self.settings_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        environment = mock.patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop(PASSWORD_ENV, None)
        os.environ.pop(ACCOUNT_ENV, None)

    def make_state(self):
        state = ChatState()
        state.verify_login = mock.Mock()
        self.addCleanup(cleanup_workspace, state.workspace)
        return state

    def test_starts_signed_out_and_cannot_save(self):
        state = self.make_state()
        self.assertFalse(state.settings_payload()["signedIn"])
        with self.assertRaisesRegex(UserInputError, "尚未登入 BookTrace"):
            state.save_book(save_all=True)

    def test_sign_in_checks_with_booktrace_remembers_it_and_never_exposes_the_password(self):
        state = self.make_state()
        state.sign_in({"account": f" {ACCOUNT} ", "password": PASSWORD})
        state.verify_login.assert_called_once_with(ACCOUNT, PASSWORD)
        payload = state.settings_payload()
        self.assertTrue(payload["signedIn"])
        self.assertEqual(payload["account"], ACCOUNT)
        self.assertNotIn(PASSWORD, json.dumps(state.snapshot()))
        self.assertNotIn(PASSWORD, json.dumps(state.events_after(0)))
        saved = json.loads(self.settings_path.read_text(encoding="utf-8"))
        self.assertEqual((saved["booktrace_account"], saved["booktrace_password"]), (ACCOUNT, PASSWORD))
        again = self.make_state()
        self.assertEqual((again.account, again.password), (ACCOUNT, PASSWORD))

    def test_a_login_that_booktrace_rejects_is_not_remembered(self):
        state = self.make_state()
        state.verify_login.side_effect = UserInputError("帳號或密碼不正確。")
        with self.assertRaisesRegex(UserInputError, "不正確"):
            state.sign_in({"account": ACCOUNT, "password": "nope"})
        self.assertFalse(state.settings_payload()["signedIn"])
        self.assertFalse(self.settings_path.exists())

    def test_account_and_password_are_both_required_before_asking_booktrace(self):
        state = self.make_state()
        for payload in (
            {"account": "", "password": PASSWORD},
            {"account": "   ", "password": PASSWORD},
            {"account": ACCOUNT, "password": ""},
            {"account": ACCOUNT, "password": None},
            {"account": ACCOUNT, "password": 123},
            {"account": ACCOUNT, "password": "x" * 129},
        ):
            with self.assertRaises(UserInputError):
                state.sign_in(payload)
        state.verify_login.assert_not_called()

    def test_sign_out_forgets_the_account_and_password(self):
        state = self.make_state()
        state.sign_in({"account": ACCOUNT, "password": PASSWORD})
        state.sign_out()
        payload = state.settings_payload()
        self.assertFalse(payload["signedIn"])
        self.assertEqual(payload["account"], "")
        saved = json.loads(self.settings_path.read_text(encoding="utf-8"))
        self.assertNotIn("booktrace_password", saved)
        self.assertNotIn("booktrace_account", saved)

    def test_environment_variables_need_both_account_and_password(self):
        os.environ[PASSWORD_ENV] = PASSWORD
        self.assertFalse(self.make_state().signed_in)
        os.environ[ACCOUNT_ENV] = ACCOUNT
        state = self.make_state()
        self.assertEqual((state.account, state.password), (ACCOUNT, PASSWORD))
        self.assertTrue(state.signed_in)


class VerifyTests(unittest.TestCase):
    @staticmethod
    def response(payload):
        body = mock.MagicMock()
        body.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        return body

    def test_login_is_posted_like_the_website_does(self):
        with mock.patch("urllib.request.urlopen", return_value=self.response({"authenticated": True})) as opened:
            verify_login(ACCOUNT, PASSWORD)
        request = opened.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/api/auth/login"))
        self.assertEqual(json.loads(request.data), {"userName": ACCOUNT, "password": PASSWORD})

    def test_wrong_password_shows_the_server_message(self):
        body = io.BytesIO(json.dumps({"message": "帳號或密碼不正確。"}).encode("utf-8"))
        error = urllib.error.HTTPError("u", 401, "no", {}, body)
        self.addCleanup(error.close)
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(UserInputError, "不正確"):
                verify_login(ACCOUNT, "nope")

    def test_unreachable_site_is_reported_not_trusted(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with self.assertRaisesRegex(UserInputError, "無法連線"):
                verify_login(ACCOUNT, PASSWORD)


class SaverTests(unittest.TestCase):
    def run_save(self, credentials):
        saver = BookSaver(lambda: credentials)
        process = mock.Mock(returncode=0)
        process.communicate.return_value = (json.dumps({"book": {"id": 1}}), "")
        with tempfile.TemporaryDirectory() as folder, mock.patch(
            "booktrace_assistant.saver.subprocess.Popen", return_value=process
        ) as popen:
            files = Path(folder)
            (files / "book.json").write_text("{}", encoding="utf-8")
            (files / "cover.png").write_bytes(b"x")
            result = saver._save_once(files / "book.json", files / "cover.png", None, False, False)
        self.assertTrue(result.ok)
        return popen.call_args

    def test_login_reaches_the_helper_through_the_environment_only(self):
        call = self.run_save((ACCOUNT, PASSWORD))
        self.assertEqual(call.kwargs["env"][PASSWORD_ENV], PASSWORD)
        self.assertEqual(call.kwargs["env"][ACCOUNT_ENV], ACCOUNT)
        self.assertFalse(any(PASSWORD in part for part in call.args[0]))

    def test_not_signed_in_means_nothing_is_set(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(PASSWORD_ENV, None)
            call = self.run_save(("", ""))
        self.assertNotIn(PASSWORD_ENV, call.kwargs["env"])


class HelperTests(unittest.TestCase):
    TOOLS = {"tools": [{"name": name} for name in ("find_book", "get_book", "add_book", "update_book", "upload_book_cover")]}

    def make_client(self, endpoint):
        def rpc(self_, method, params, notification=False):
            if method == "initialize":
                return {"protocolVersion": "2025-11-25"}
            return self.TOOLS if method == "tools/list" else None

        with mock.patch.object(enrich_book.McpClient, "rpc", rpc):
            return enrich_book.McpClient(endpoint)

    @staticmethod
    def basic(account, password):
        return "Basic " + base64.b64encode(f"{account}:{password}".encode("utf-8")).decode("ascii")

    def environment(self, **values):
        patcher = mock.patch.dict(os.environ, values)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in (ACCOUNT_ENV, PASSWORD_ENV):
            if name not in values:
                os.environ.pop(name, None)

    def test_helper_logs_in_with_the_site_account(self):
        self.environment(**{ACCOUNT_ENV: ACCOUNT, PASSWORD_ENV: "密碼:含冒號"})
        client = self.make_client("https://booktrace.example/mcp")
        self.assertEqual(client.headers["Authorization"], self.basic(ACCOUNT, "密碼:含冒號"))

    def test_helper_needs_both_account_and_password(self):
        for values in ({PASSWORD_ENV: PASSWORD}, {ACCOUNT_ENV: ACCOUNT}):
            self.environment(**values)
            with self.assertRaisesRegex(ValueError, "同時設定"):
                self.make_client("https://booktrace.example/mcp")

    def test_helper_works_without_a_login_for_reads(self):
        self.environment()
        client = self.make_client("https://booktrace.example/mcp")
        self.assertNotIn("Authorization", client.headers)

    def test_helper_will_not_send_the_password_over_plain_http(self):
        self.environment(**{ACCOUNT_ENV: ACCOUNT, PASSWORD_ENV: PASSWORD})
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            self.make_client("http://booktrace.example/mcp")
        self.assertIn("Authorization", self.make_client("http://localhost:5000/mcp").headers)


class RetryTests(unittest.TestCase):
    def test_login_problems_are_not_retried(self):
        for text in (
            "需要登入：新增或修改書籍時，請在 MCP 客戶端帶上 BookTrace 的帳號與密碼（Authorization: Basic ...）。",
            "帳號或密碼不正確。",
            "嘗試的次數太多了，請約 5 分鐘後再試。",
        ):
            self.assertFalse(classify_retry(text, 1).retry, text)


if __name__ == "__main__":
    unittest.main()
