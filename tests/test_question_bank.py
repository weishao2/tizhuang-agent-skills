from __future__ import annotations

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from types import SimpleNamespace


SCRIPT = (
    Path(__file__).parents[1]
    / "skills"
    / "question-bank"
    / "scripts"
    / "question_bank.py"
)
SPEC = importlib.util.spec_from_file_location("question_bank", SCRIPT)
assert SPEC and SPEC.loader
QUESTION_BANK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUESTION_BANK)


class PracticePagePayloadTests(unittest.TestCase):
    def test_omits_optional_null_filters(self) -> None:
        captured = {}

        def fake_request(path, *args, **kwargs):
            captured["path"] = path
            captured["kwargs"] = kwargs
            return {"page_url": "https://example.test/practice/demo"}

        original_parse_args = QUESTION_BANK.parse_args
        original_request = QUESTION_BANK.request
        QUESTION_BANK.parse_args = lambda: SimpleNamespace(
            command="practice-page",
            title="Smoke test",
            subject_id=8,
            grade_id=None,
            question_type=None,
            difficulty_min=None,
            difficulty_max=None,
            year=None,
            keyword=None,
            knowledge_id=None,
            knowledge_tree_ids=None,
            edition_id=None,
            chapter_id=None,
            with_images=False,
            limit=1,
            random=True,
        )
        QUESTION_BANK.request = fake_request
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                QUESTION_BANK.main()
        finally:
            QUESTION_BANK.parse_args = original_parse_args
            QUESTION_BANK.request = original_request

        self.assertEqual(captured["path"], "/v1/practice-pages")
        body = captured["kwargs"]["json_body"]
        self.assertNotIn("knowledge_tree_ids", body)
        self.assertNotIn("has_images", body)
        self.assertEqual(body["subject_id"], 8)
        self.assertEqual(body["limit"], 1)
        self.assertTrue(body["random_order"])


if __name__ == "__main__":
    unittest.main()
