from __future__ import annotations

import argparse
import base64
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, urlparse

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "question-bank"
    / "scripts"
    / "question_bank.py"
)


def _load_skill_script():
    spec = importlib.util.spec_from_file_location("question_bank_skill_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("extra,expected_error", [
    ([], None),
    (["--grade-id", "140"], "filter_resolution_failed"),
    (["--edition-id", "1"], "filter_resolution_failed"),
    (["--edition", "人教"], "filter_resolution_failed"),
])
def test_name_resolution_blocks_wrong_grade_and_edition(monkeypatch, capsys, extra, expected_error):
    skill = _load_skill_script()
    calls = []
    def metadata(path, params=None, **kwargs):
        calls.append(path)
        assert kwargs.get("public") is True
        return {
            "/v1/meta/subjects": [{"id": 2, "name": "数学"}],
            "/v1/meta/grades": [{"id": 140, "name": "四年级"}, {"id": 300, "name": "八年级"}],
            "/v1/meta/editions": [{"id": 59, "name": "人教新版"}, {"id": 142, "name": "人教版2024"}],
            "/v1/meta/knowledge-points": [{"id": 1489, "name": "一次函数", "knowledge_id": 20183}],
        }[path]
    monkeypatch.setattr(skill, "request", metadata)
    monkeypatch.setattr(sys, "argv", ["qb", "resolve", "--subject", "数学", "--grade", "八年级", "--knowledge", "一次函数"] + extra)
    if expected_error:
        with pytest.raises(SystemExit, match=expected_error):
            skill.main()
    else:
        skill.main()
        result = json.loads(capsys.readouterr().out)["resolved_filters"]
        assert result["grade"] == {"id": 300, "name": "八年级"}
        assert result["knowledge"]["tree_id"] == 1489
    assert all(path.startswith("/v1/meta/") for path in calls)


@pytest.mark.parametrize("scope", ["branch", "exact"])
def test_named_knowledge_keeps_scope_in_real_request(monkeypatch, capsys, scope):
    skill = _load_skill_script()
    def request(path, params=None, **kwargs):
        if path == "/v1/meta/subjects":
            return [{"id": 2, "name": "数学"}]
        if path == "/v1/meta/knowledge-points":
            return [{"id": 1495, "name": "一次函数的图象", "knowledge_id": 20197}]
        assert path == "/v1/questions"
        assert params["knowledge_id"] == (20197 if scope == "exact" else None)
        assert params["knowledge_tree_ids"] == ([1495] if scope == "branch" else None)
        return {"items": [], "count": 0}
    monkeypatch.setattr(skill, "request", request)
    monkeypatch.setattr(sys, "argv", ["qb", "questions", "--subject", "数学", "--knowledge", "一次函数的图象", "--knowledge-scope", scope])
    skill.main()
    assert json.loads(capsys.readouterr().out)["count"] == 0
