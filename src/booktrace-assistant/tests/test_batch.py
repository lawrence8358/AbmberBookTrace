import base64
import copy
import threading
import time
import unittest
from unittest import mock

from booktrace_assistant.core import UserInputError, cleanup_workspace
from booktrace_assistant.runner import RunResult
from booktrace_assistant.saver import SaveResult
from booktrace_assistant.webapp import MAX_BATCH_BOOKS, ChatState
from test_core import READY_PAYLOAD

PNG = base64.b64encode(
    bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")
).decode()


class FakeRunner:
    """Answers by query (a dict) or in call order (a list). An answer may be a function, to model a slow book."""

    def __init__(self, results):
        self.results = results if isinstance(results, dict) else list(results)
        self.queries = []

    def cancel(self):
        pass

    def run(self, engine, executable, model, request, auto_retry, callback, effort=None):
        self.queries.append(request)
        answer = self.results[request.query] if isinstance(self.results, dict) else self.results.pop(0)
        return answer() if callable(answer) else answer


class FakeSaver:
    def __init__(self, gate=None):
        self.saved = []
        self.gate = gate

    def save(self, book, **_kwargs):
        if self.gate:
            self.gate.wait(5)
        self.saved.append(book.title)
        return SaveResult(True, {"book": {"id": len(self.saved), "title": book.title}, "created": True})


def ready(title):
    payload = copy.deepcopy(READY_PAYLOAD)
    payload["book"]["title"] = title
    payload["book"]["coverUrl"] = ""
    return RunResult(True, structured=payload)


def wait_for(condition, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("condition was never met")


def wait_idle(state, timeout=5):
    wait_for(lambda: not state.busy, timeout)


def with_cover(text):
    return {"text": text, "image": {"data": PNG}, "isCover": True}


def needs_clarification():
    payload = copy.deepcopy(READY_PAYLOAD)
    payload["status"] = "needs_clarification"
    base = {"title": "甲", "isbn": "", "publicationYear": "2020", "pages": "", "binding": "", "coverDescription": "", "coverUrl": ""}
    payload["candidates"] = [{**base, "isbn": "9786267174142"}, {**base, "isbn": "9789863798361"}]
    return RunResult(True, structured=payload)


class BatchTests(unittest.TestCase):
    def setUp(self):
        # Never reach the network: a cover that is not an uploaded photo cannot be downloaded here.
        offline = mock.patch(
            "booktrace_assistant.webapp.download_cover", side_effect=UserInputError("offline")
        )
        offline.start()
        self.addCleanup(offline.stop)

    def make_state(self, results, parallel=1):
        # One book at a time by default so answers given in call order stay predictable.
        state = ChatState()
        state.engines = {"claude": "claude.exe"}
        state.engine = "claude"
        state.runner = FakeRunner(results)
        state.runner_factory = lambda: state.runner
        state.max_parallel = parallel
        state.saver = FakeSaver()
        self.addCleanup(cleanup_workspace, state.workspace)
        return state

    def test_each_row_is_researched_alone_and_in_order(self):
        state = self.make_state([ready("甲"), ready("乙")])
        state.send_batch({"items": [{"text": "甲書"}, {"text": "乙書", "image": {"data": PNG}, "isCover": True}]})
        wait_idle(state)
        self.assertEqual([request.query for request in state.runner.queries], ["甲書", "乙書"])
        self.assertEqual(len(state.runner.queries[0].image_paths), 0)
        self.assertEqual(state.runner.queries[1].designated_cover_index, 0)
        self.assertEqual(len(state.items), 2)
        events = state.events_after(0)
        finished = [event for event in events if event["type"] == "batch_finished"]
        self.assertEqual(finished[0]["total"], 2)
        # 甲 has no cover source (no image, empty coverUrl); only 乙 can be saved.
        self.assertEqual(finished[0]["ready"], 1)

    def test_one_failure_does_not_stop_the_other_books(self):
        state = self.make_state([RunResult(False, error="boom"), ready("乙")])
        state.send_batch({"items": [{"text": "甲書"}, {"text": "乙書", "image": {"data": PNG}, "isCover": True}]})
        wait_idle(state)
        kinds = [(event["type"], event.get("itemId")) for event in state.events_after(0)]
        first, second = list(state.items)
        self.assertIn(("assistant_error", first), kinds)
        self.assertIn(("cover_ready", second), kinds)

    def test_stop_cancels_the_running_book_and_drops_the_waiting_ones(self):
        started, release = threading.Event(), threading.Event()

        def blocked():
            started.set()
            release.wait(5)
            return RunResult(False, cancelled=True, error="stop")

        state = self.make_state({"甲書": blocked, "乙書": ready("乙"), "丙書": ready("丙")})
        state.send_batch({"items": [{"text": "甲書"}, {"text": "乙書"}, {"text": "丙書"}]})
        self.assertTrue(started.wait(5))
        state.cancel()
        release.set()
        wait_idle(state)
        self.assertEqual([request.query for request in state.runner.queries], ["甲書"])
        self.assertEqual(state.status, "已停止")
        events = state.events_after(0)
        self.assertEqual(len([event for event in events if event["type"] == "assistant_error"]), 3)
        self.assertEqual([event["total"] for event in events if event["type"] == "batch_finished"], [3])

    def test_books_are_researched_at_the_same_time(self):
        meeting = threading.Barrier(2, timeout=5)

        def meet(title):
            def answer():
                meeting.wait()  # only returns when the other book is being researched right now
                return ready(title)

            return answer

        state = self.make_state({"甲書": meet("甲"), "乙書": meet("乙")}, parallel=2)
        state.send_batch({"items": [{"text": "甲書"}, {"text": "乙書"}]})
        wait_idle(state)
        events = state.events_after(0)
        self.assertEqual([event for event in events if event["type"] == "assistant_error"], [])
        self.assertEqual(len([event for event in events if event["type"] == "assistant"]), 2)
        self.assertEqual([event["total"] for event in events if event["type"] == "batch_finished"], [2])

    def test_a_full_batch_is_researched_all_at_once_by_default(self):
        self.assertGreaterEqual(ChatState().max_parallel, MAX_BATCH_BOOKS)
        meeting = threading.Barrier(MAX_BATCH_BOOKS, timeout=5)

        def meet():
            meeting.wait()  # only returns when all ten books are being researched right now
            return ready("書")

        state = self.make_state({f"書{n}": meet for n in range(MAX_BATCH_BOOKS)}, parallel=ChatState().max_parallel)
        state.send_batch({"items": [{"text": f"書{n}"} for n in range(MAX_BATCH_BOOKS)]})
        wait_idle(state)
        events = state.events_after(0)
        self.assertEqual([event for event in events if event["type"] == "assistant_error"], [])
        self.assertEqual(len([event for event in events if event["type"] == "assistant"]), MAX_BATCH_BOOKS)

    def test_parallel_limit_keeps_the_rest_waiting(self):
        running, peak, lock = 0, 0, threading.Lock()

        def book():
            nonlocal running, peak
            with lock:
                running += 1
                peak = max(peak, running)
            time.sleep(0.05)
            with lock:
                running -= 1
            return ready("書")

        state = self.make_state({f"書{n}": book for n in range(5)}, parallel=2)
        state.send_batch({"items": [{"text": f"書{n}"} for n in range(5)]})
        wait_idle(state)
        self.assertEqual(peak, 2)
        self.assertEqual(len(state.runner.queries), 5)

    def test_a_confirmed_book_is_saved_while_other_books_are_still_being_researched(self):
        release = threading.Event()

        def slow():
            release.wait(5)
            return ready("乙")

        state = self.make_state({"甲書": ready("甲"), "乙書": slow}, parallel=2)
        state.send_batch({"items": [with_cover("甲書"), with_cover("乙書")]})
        first = list(state.items)[0]
        wait_for(lambda: state._item_can_save(state.items[first]))
        state.save_book(first)
        wait_for(lambda: state.items[first].saved)
        self.assertEqual(state.saver.saved, ["甲"])
        self.assertEqual(state.busy_mode, "research")  # 乙 is still being researched
        release.set()
        wait_idle(state)
        # The run's summary no longer offers the book that is already in.
        self.assertEqual([event["ready"] for event in state.events_after(0) if event["type"] == "batch_finished"], [2])
        self.assertEqual(state.status, "已查完，1 本可以加入書架")

    def test_saving_one_book_does_not_block_researching_more(self):
        gate = threading.Event()
        state = self.make_state([ready("甲"), ready("乙")])
        state.saver = FakeSaver(gate)
        state.send_message({"text": "甲書", "images": [{"data": PNG}], "coverIndex": 0})
        wait_idle(state)
        first = list(state.items)[0]
        state.save_book(first)
        self.assertEqual(state.busy_mode, "save")
        with self.assertRaises(UserInputError):  # the same book cannot be queued twice
            state.save_book(first)
        state.send_batch({"items": [{"text": "乙書"}]})
        wait_for(lambda: len(state.runner.queries) == 2)
        gate.set()
        wait_idle(state)
        self.assertEqual(state.saver.saved, ["甲"])

    def test_picking_a_candidate_starts_right_away_while_other_books_are_still_being_researched(self):
        release = threading.Event()
        pick = "請以這個版本為準：甲，ISBN 9786267174142"

        def slow():
            release.wait(5)
            return ready("乙")

        state = self.make_state({"甲書": needs_clarification(), "乙書": slow, pick: ready("甲")}, parallel=2)
        state.send_batch({"items": [{"text": "甲書"}, {"text": "乙書"}]})
        first = list(state.items)[0]
        wait_for(lambda: state.items[first].outcome is not None)
        state.send_message({"text": pick, "contextItemId": first})
        wait_for(lambda: any(item.outcome and item.outcome.ready for item in state.items.values()))
        self.assertIn(pick, [request.query for request in state.runner.queries])
        self.assertTrue(state.busy)  # 乙 has not finished
        with self.assertRaises(UserInputError):  # a brand-new message still has to wait for the run
            state.send_message({"text": "別的書"})
        release.set()
        wait_idle(state)
        finished = [event for event in state.events_after(0) if event["type"] == "batch_finished"]
        self.assertEqual(len(finished), 1)
        self.assertEqual(len(finished[0]["itemIds"]), 3)  # 甲, 乙 and the picked version of 甲

    def test_batch_limits_and_empty_rows_are_rejected(self):
        state = self.make_state([])
        with self.assertRaises(UserInputError):
            state.send_batch({"items": []})
        with self.assertRaises(UserInputError):
            state.send_batch({"items": [{"text": "書"}] * 11})
        with self.assertRaises(UserInputError):
            state.send_batch({"items": [{"text": ""}]})

    def test_save_all_saves_only_ready_books_with_covers(self):
        state = self.make_state([ready("甲"), ready("乙"), ready("丙")])
        state.send_batch(
            {
                "items": [
                    {"text": "甲書", "image": {"data": PNG}, "isCover": True},
                    {"text": "乙書"},
                    {"text": "丙書", "image": {"data": PNG}, "isCover": True},
                ]
            }
        )
        wait_idle(state)
        state.save_book(save_all=True)
        wait_idle(state)
        self.assertEqual(state.saver.saved, ["甲", "丙"])
        self.assertEqual([event["itemId"] for event in state.events_after(0) if event["type"] == "saved"], [
            item_id for item_id, item in state.items.items() if item.saved
        ])
        with self.assertRaises(UserInputError):
            state.save_book(save_all=True)

    def test_save_one_item_by_id(self):
        state = self.make_state([ready("甲"), ready("乙")])
        state.send_batch(
            {"items": [{"text": "甲書", "image": {"data": PNG}, "isCover": True}, {"text": "乙書", "image": {"data": PNG}, "isCover": True}]}
        )
        wait_idle(state)
        second = list(state.items)[1]
        state.save_book(second)
        wait_idle(state)
        self.assertEqual(state.saver.saved, ["乙"])

    def test_unconfirmed_book_shows_candidate_covers_it_could_download(self):
        payload = copy.deepcopy(READY_PAYLOAD)
        payload["status"] = "needs_clarification"
        base = {"title": "甲", "isbn": "", "publicationYear": "2020", "pages": "", "binding": "", "coverDescription": ""}
        payload["candidates"] = [
            {**base, "coverUrl": "https://example.com/a.jpg"},  # the AI's own cover URL wins
            {**base, "coverUrl": "https://example.com/broken.jpg"},  # download fails
            {**base, "isbn": "9786267174142", "coverUrl": ""},  # no URL: Sanmin CDN by ISBN
            {**base, "isbn": "9789863798361", "coverUrl": ""},  # Sanmin answers with a tiny placeholder
            {**base, "isbn": "not-an-isbn", "coverUrl": ""},  # nothing to try
        ]
        state = self.make_state([RunResult(True, structured=payload)])
        requested = []

        def fake_download(url, output, workspace):
            requested.append(url)
            if "broken" in url:
                raise UserInputError("下載封面失敗")
            size = 100 if "986379836" in url else 4000
            png = output.with_suffix(".png")
            png.write_bytes(base64.b64decode(PNG) + b"0" * size)
            return png

        with mock.patch("booktrace_assistant.webapp.download_cover", fake_download):
            state.send_message({"text": "甲"})
            wait_idle(state)
        outcome = next(event for event in state.events_after(0) if event["type"] == "assistant")["outcome"]
        covers = [candidate["cover_media"] for candidate in outcome["candidates"]]
        self.assertEqual([bool(cover) for cover in covers], [True, False, True, False, False])
        self.assertTrue(covers[0].startswith("/media/"))
        self.assertIn("https://cdnec.sanmin.com.tw/product_images/626/626717414.jpg", requested)
        self.assertEqual(len(requested), 4)
        self.assertNotIn("cover_url", outcome["candidates"][0])

    def test_ready_book_without_cover_url_falls_back_to_sanmin_by_isbn(self):
        state = self.make_state([ready("甲")])
        requested = []

        def fake_download(url, output, workspace):
            requested.append(url)
            png = output.with_suffix(".png")
            png.write_bytes(base64.b64decode(PNG) + b"0" * 4000)
            return png

        with mock.patch("booktrace_assistant.webapp.download_cover", fake_download):
            state.send_message({"text": "9781234567890"})
            wait_idle(state)
        self.assertEqual(requested, ["https://cdnec.sanmin.com.tw/product_images/123/123456789.jpg"])
        self.assertTrue(any(event["type"] == "cover_ready" for event in state.events_after(0)))

    def test_follow_up_reuses_that_items_context_and_photo(self):
        state = self.make_state([ready("甲"), ready("乙"), ready("甲")])
        state.send_batch(
            {"items": [{"text": "甲書", "image": {"data": PNG}, "isCover": True}, {"text": "乙書"}]}
        )
        wait_idle(state)
        first = list(state.items)[0]
        state.send_message({"text": "是精裝版", "contextItemId": first})
        wait_idle(state)
        request = state.runner.queries[-1]
        self.assertIn("甲", request.previous_context)
        self.assertEqual(len(request.image_paths), 1)
        self.assertEqual(request.designated_cover_index, 0)


if __name__ == "__main__":
    unittest.main()
