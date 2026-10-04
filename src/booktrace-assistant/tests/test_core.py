import json
import tempfile
import unittest
from pathlib import Path

from booktrace_assistant.core import (
    PersonalFields,
    ResearchBook,
    ResearchRequest,
    UserInputError,
    build_research_prompt,
    image_kind,
    parse_research_outcome,
    validate_iso_date,
    validate_personal_fields,
    validate_research_request,
)


READY_PAYLOAD = {
    "status": "ready",
    "summary": "已核對紙本版本。",
    "book": {
        "title": "測試書",
        "author": "作者",
        "isbn": "9781234567890",
        "publisher": "出版社",
        "category": "測試",
        "publicationDate": "2026-09-28",
        "coverUrl": "https://example.com/cover.jpg",
        "existingBookId": None,
        "sources": ["https://example.com/book"],
        "unknownFields": [],
    },
    "candidates": [],
    "questions": [],
    "userProvided": {
        "purchaseDate": "",
        "location": "",
        "detailedLocation": "",
        "notes": "",
    },
    "requestedActions": {
        "wantsToSave": False,
        "correctExisting": False,
        "replaceCover": False,
    },
}


class CoreTests(unittest.TestCase):
    def test_candidates_keep_their_cover_url(self):
        payload = dict(READY_PAYLOAD, status="needs_clarification")
        payload["candidates"] = [
            {"title": "甲", "isbn": "1", "publicationYear": "2020", "pages": "", "binding": "",
             "coverDescription": "", "coverUrl": "https://example.com/a.jpg"}
        ]
        outcome = parse_research_outcome(payload)
        self.assertEqual(outcome.candidates[0].cover_url, "https://example.com/a.jpg")

    def test_schema_and_both_skills_ask_candidates_for_cover_urls(self):
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "booktrace_assistant/research_schema.json").read_text(encoding="utf-8"))
        required = schema["properties"]["candidates"]["items"]["required"]
        self.assertIn("coverUrl", required)
        for rel in (
            "booktrace_assistant/rules.md",
            ".agents/skills/booktrace-enrich-skill/SKILL.md",
            ".claude/skills/booktrace-enrich-skill/SKILL.md",
        ):
            with self.subTest(rel=rel):
                text = (root / rel).read_text(encoding="utf-8")
                self.assertIn("`coverUrl`", text)
                self.assertIn("cdnec.sanmin.com.tw/product_images", text)
                self.assertIn("不得因此再次要求使用者確認", text)

    def test_codex_is_told_it_cannot_view_covers_but_claude_is_not(self):
        codex = build_research_prompt(ResearchRequest("書"), "codex")
        claude = build_research_prompt(ResearchRequest("書"), "claude")
        self.assertIn("無法下載或檢視網路圖片", codex)
        self.assertNotIn("無法下載或檢視網路圖片", claude)

    def test_requires_text_or_image(self):
        with self.assertRaises(UserInputError):
            validate_research_request(ResearchRequest(""))

    def test_date_must_be_full_and_valid(self):
        self.assertEqual(validate_iso_date("2026-09-28", "日期"), "2026-09-28")
        for invalid in ("2026", "2026-09", "2026-02-30"):
            with self.subTest(invalid=invalid), self.assertRaises(UserInputError):
                validate_iso_date(invalid, "日期")

    def test_personal_fields_are_trimmed(self):
        fields = validate_personal_fields(PersonalFields(location="  書房 ", notes="  已簽名 "))
        self.assertEqual(fields.location, "書房")
        self.assertEqual(fields.notes, "已簽名")

    def test_image_magic_not_only_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cover.jpg"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)
            self.assertEqual(image_kind(path), "png")

    def test_parse_ready_outcome(self):
        outcome = parse_research_outcome(json.dumps(READY_PAYLOAD, ensure_ascii=False))
        self.assertTrue(outcome.ready)
        self.assertEqual(outcome.book.title, "測試書")
        self.assertEqual(outcome.book.sources, ("https://example.com/book",))

    def test_ready_requires_source(self):
        payload = json.loads(json.dumps(READY_PAYLOAD))
        payload["book"]["sources"] = []
        with self.assertRaises(UserInputError):
            parse_research_outcome(payload)

    def test_metadata_only_contains_user_personal_values(self):
        book = parse_research_outcome(READY_PAYLOAD).book
        metadata = book.metadata(PersonalFields(location="客廳"))
        self.assertEqual(metadata["location"], "客廳")
        self.assertNotIn("purchaseDate", metadata)
        self.assertEqual(metadata["sources"], ["https://example.com/book"])

    def test_prompt_embeds_rules_and_read_only_gate(self):
        request = ResearchRequest("測試書")
        codex = build_research_prompt(request, "codex")
        claude = build_research_prompt(request, "claude")
        # rules.md is sent verbatim; editing it changes how the AI researches books.
        self.assertIn("三民網路書店", codex)
        self.assertIn("三民網路書店", claude)
        self.assertIn("<rules>", claude)
        self.assertIn("絕對不得新增", codex)
        self.assertIn("不得執行 enrich_book.py", claude)

    def test_prompt_stops_before_researching_multiple_books(self):
        prompt = build_research_prompt(ResearchRequest("妖怪托顧所 6、7、8 和 II 5"), "claude")
        self.assertIn("先不要搜尋網頁", prompt)
        self.assertIn("請使用者選定一本", prompt)

    def test_prompt_routes_around_known_blocked_bookstores(self):
        prompt = build_research_prompt(ResearchRequest("測試書"), "claude")
        self.assertIn("不得用 WebFetch 開啟博客來或誠品商品頁", prompt)
        self.assertIn("https://www.bookrepclub.com.tw/", prompt)
        self.assertIn("同一網域首次回應 403", prompt)

    def test_both_platform_skills_include_source_routing_rules(self):
        assistant_root = Path(__file__).resolve().parents[1]
        skill_paths = (
            assistant_root / ".agents/skills/booktrace-enrich-skill/SKILL.md",
            assistant_root / ".claude/skills/booktrace-enrich-skill/SKILL.md",
        )
        for path in skill_paths:
            with self.subTest(path=path):
                skill = path.read_text(encoding="utf-8")
                self.assertIn("先不要搜尋網頁", skill)
                self.assertIn("不得用 WebFetch 開啟博客來或誠品商品頁", skill)
                self.assertIn("https://www.bookrepclub.com.tw/", skill)
                self.assertIn("同一網域首次回應 403", skill)


if __name__ == "__main__":
    unittest.main()
