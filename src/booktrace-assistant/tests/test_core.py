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


if __name__ == "__main__":
    unittest.main()
