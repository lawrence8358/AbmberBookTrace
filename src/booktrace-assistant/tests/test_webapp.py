import unittest

from booktrace_assistant.webapp import load_preferences

BOTH = {"codex": "codex.exe", "claude": "claude.exe"}


class PreferenceTests(unittest.TestCase):
    def test_first_launch_defaults_to_claude_sonnet(self):
        engine, models, auto_retry, _ = load_preferences({}, BOTH)
        self.assertEqual(engine, "claude")
        self.assertEqual(models["claude"], "claude-sonnet-5")
        self.assertTrue(auto_retry)

    def test_last_choice_is_restored(self):
        engine, models, auto_retry, _ = load_preferences(
            {"engine": "codex", "models": {"codex": "gpt-5.6-sol", "claude": "claude-opus-5-5"}, "auto_retry": False},
            BOTH,
        )
        self.assertEqual(engine, "codex")
        self.assertEqual(models["codex"], "gpt-5.6-sol")
        self.assertEqual(models["claude"], "claude-opus-5-5")
        self.assertFalse(auto_retry)

    def test_claude_5x_choice_is_restored_when_available(self):
        engines = {**BOTH, "claude-5x": "claude.exe"}
        engine, models, _, _ = load_preferences({"engine": "claude-5x", "models": {"claude-5x": "claude-opus-5-5"}}, engines)
        self.assertEqual(engine, "claude-5x")
        self.assertEqual(models["claude-5x"], "claude-opus-5-5")

    def test_cli_default_choice_is_remembered(self):
        _, models, _, _ = load_preferences({"engine": "claude", "models": {"claude": ""}}, BOTH)
        self.assertEqual(models["claude"], "")

    def test_missing_engine_falls_back_to_installed_one(self):
        engine, _, _, _ = load_preferences({"engine": "claude"}, {"codex": "codex.exe"})
        self.assertEqual(engine, "codex")


    def test_effort_is_remembered_and_validated(self):
        self.assertEqual(load_preferences({"effort": "high"}, BOTH)[3], "high")
        self.assertEqual(load_preferences({"effort": "bogus"}, BOTH)[3], "")
        self.assertEqual(load_preferences({}, BOTH)[3], "")


if __name__ == "__main__":
    unittest.main()
