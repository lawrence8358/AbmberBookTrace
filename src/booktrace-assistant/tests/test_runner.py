import json
import unittest
from pathlib import Path

from booktrace_assistant.core import ResearchRequest
from booktrace_assistant.runner import (
    _claude_event,
    _codex_event,
    build_claude_command,
    build_codex_command,
    classify_retry,
)


def collect(parser, payloads):
    events, context = [], {}
    for payload in payloads:
        parser(payload, lambda kind, text, _deadline: events.append((kind, text)), context)
    return events, context


class RunnerTests(unittest.TestCase):
    def test_codex_command_is_read_only_and_limits_mcp_tools(self):
        command = build_codex_command(
            "codex",
            ResearchRequest("書", (Path("C:/tmp/book.jpg"),)),
            "gpt-5.6-luna",
            Path("C:/repo"),
        )
        joined = " ".join(command)
        self.assertIn("--sandbox read-only", joined)
        self.assertIn('enabled_tools=["find_book","get_book"]', joined)
        self.assertIn("--image C:\\tmp\\book.jpg", joined)
        self.assertIn("--model gpt-5.6-luna", joined)
        self.assertNotIn("danger-full-access", joined)

    def test_claude_command_denies_writes_and_uses_strict_mcp(self):
        command = build_claude_command("claude", "claude-haiku-4-5-20251001", Path("C:/repo"))
        joined = " ".join(command)
        self.assertIn("--restricted", command)
        self.assertIn("--strict-mcp-config", command)
        mcp = json.loads(command[command.index("--mcp-config") + 1])
        self.assertEqual(mcp["mcpServers"]["booktrace"]["url"], "https://booktrace.primeeagle.net/mcp")
        self.assertIn("mcp__booktrace__find_book", joined)
        self.assertIn("mcp__booktrace__add_book", joined)
        self.assertIn("Bash,PowerShell,Edit,Write", joined)
        self.assertIn("--model claude-haiku-4-5-20251001", joined)
        self.assertNotIn("dangerously-skip-permissions", joined)

    def test_five_hour_limit_uses_reported_delay(self):
        decision = classify_retry("Usage limit. Try again in 4h 59m", 1)
        self.assertTrue(decision.retry)
        self.assertGreaterEqual(decision.delay_seconds, 4 * 3600 + 59 * 60)

    def test_transient_backoff_is_bounded(self):
        self.assertEqual(classify_retry("503 Service unavailable", 1).delay_seconds, 15)
        self.assertEqual(classify_retry("503 Service unavailable", 3).delay_seconds, 60)
        self.assertLessEqual(classify_retry("503 Service unavailable", 99).delay_seconds, 300)

    def test_bad_model_is_not_retried(self):
        self.assertFalse(classify_retry("model not found", 1).retry)
        self.assertFalse(
            classify_retry("The 'gpt-6-luna' model is not supported when using Codex with a ChatGPT account.", 1).retry
        )

    def test_out_of_credits_is_not_retried(self):
        self.assertFalse(classify_retry("Your workspace is out of credits.", 1).retry)

    def test_codex_top_level_flags_precede_exec(self):
        command = build_codex_command("codex", ResearchRequest("書"), None, Path("C:/repo"))
        exec_index = command.index("exec")
        self.assertLess(command.index("--ask-for-approval"), exec_index)
        self.assertLess(command.index("--search"), exec_index)
        self.assertIn('mcp_servers.booktrace.url="https://booktrace.primeeagle.net/mcp"', command)
        self.assertIn("project_doc_max_bytes=0", command)

    def test_claude_reset_epoch_sets_delay(self):
        import time

        decision = classify_retry(f"Claude AI usage limit reached|{int(time.time()) + 3600}", 1)
        self.assertTrue(decision.retry)
        self.assertGreater(decision.delay_seconds, 3500)

    def test_five_hour_label_is_not_the_wait(self):
        decision = classify_retry("5 hour usage limit reached, try again in 10 minutes", 1)
        self.assertLess(decision.delay_seconds, 700)

    def test_status_codes_need_word_boundaries(self):
        self.assertFalse(classify_retry("ISBN 9789575031234 invalid", 1).retry)

    def test_effort_is_passed_to_both_clis(self):
        codex = build_codex_command("codex", ResearchRequest("書"), None, Path("C:/repo"), effort="high")
        self.assertIn('model_reasoning_effort="high"', codex)
        self.assertLess(codex.index('model_reasoning_effort="high"'), codex.index("-"))
        claude = build_claude_command("claude", None, Path("C:/repo"), effort="low")
        self.assertEqual(claude[claude.index("--effort") + 1], "low")
        self.assertNotIn("--effort", build_claude_command("claude", None, Path("C:/repo")))

    def test_claude_stream_becomes_progress_steps(self):
        events, context = collect(_claude_event, [
            {"type": "system", "subtype": "thinking_tokens", "estimated_tokens": 150},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "現在搜尋此 ISBN。"},
                {"type": "tool_use", "id": "t1", "name": "WebSearch", "input": {"query": "ISBN 9789863441373"}},
                {"type": "tool_use", "id": "t2", "name": "WebFetch", "input": {"url": "https://example.com/a"}},
                {"type": "tool_use", "id": "t3", "name": "mcp__booktrace__find_book", "input": {"isbn": "9789863441373"}},
            ]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t2", "content": "The server returned HTTP 404 Not Found."},
            ]}},
            {"type": "result", "subtype": "success", "total_cost_usd": 0.0523, "result": "{}"},
        ])
        steps = [(kind, text) for kind, text in events if kind.startswith("step:")]
        self.assertEqual([kind for kind, _ in steps], ["step:note", "step:search", "step:fetch", "step:booktrace", "step:error"])
        self.assertIn("ISBN 9789863441373", steps[1][1])
        self.assertIn("https://example.com/a", steps[2][1])
        self.assertIn("isbn=9789863441373", steps[3][1])
        self.assertEqual(steps[4][1], "網頁無法開啟（HTTP 404），改找其他來源")
        self.assertIn(("thinking", "正在思考…（約 150 tokens）"), events)
        self.assertEqual(context["summary"], "花費約 US$0.052")

    def test_codex_items_become_progress_steps(self):
        events, context = collect(_codex_event, [
            {"type": "item.completed", "item": {"type": "reasoning", "text": "先查 ISBN"}},
            {"type": "item.completed", "item": {"type": "web_search", "query": "三民 9789863441373"}},
            {"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "booktrace", "tool": "find_book", "arguments": {"isbn": "1"}}},
            {"type": "turn.completed", "usage": {"input_tokens": 1000, "output_tokens": 234}},
        ])
        kinds = [kind for kind, _ in events if kind.startswith("step:")]
        self.assertEqual(kinds, ["step:think", "step:search", "step:booktrace"])
        self.assertEqual(context["summary"], "共使用約 1,234 tokens")


if __name__ == "__main__":
    unittest.main()
