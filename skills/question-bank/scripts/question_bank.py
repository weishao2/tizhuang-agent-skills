from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.getenv(
    "QUESTION_SERVICE_URL", "https://tizhuang.qcscience.cc/api"
).rstrip("/")
CACHE_FILE = Path(
    os.getenv(
        "QUESTION_SERVICE_TRIAL_FILE",
        Path.home() / ".question-bank" / "trial.json",
    )
)

PRIVATE_SOLUTION_FIELDS = frozenset(
    {
        "answer",
        "answer_html",
        "analysis",
        "analysis_html",
        "solution",
        "solution_html",
        "explanation",
        "explanation_html",
    }
)

BUILDER_HANDOFF_MAX_ENCODED_LENGTH = 32_000


def _redact_solutions(value):
    """Remove solution material at every nesting level, including subquestions."""
    if isinstance(value, dict):
        return {
            key: _redact_solutions(item)
            for key, item in value.items()
            if key.lower() not in PRIVATE_SOLUTION_FIELDS
        }
    if isinstance(value, list):
        return [_redact_solutions(item) for item in value]
    return value


def _http_json(
    path: str,
    params: dict | None = None,
    *,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    json_body: dict | None = None,
):
    query = urllib.parse.urlencode(
        {key: value for key, value in (params or {}).items() if value is not None},
        doseq=True,
    )
    url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
    request_headers = dict(headers or {})
    body = None
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    api_request = urllib.request.Request(
        url, data=body, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(api_request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read().decode("utf-8"))
            detail = body.get("detail", body)
        except (ValueError, UnicodeDecodeError):
            detail = error.reason
        raise SystemExit(f"Question service returned HTTP {error.code}: {detail}") from None
    except urllib.error.URLError as error:
        raise SystemExit(f"Cannot reach question service: {error.reason}") from None


def _load_trial_token() -> str | None:
    try:
        cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(cached["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if cached["base_url"] == BASE_URL and expires_at > datetime.now(timezone.utc):
            return cached["trial_token"]
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return None


def _create_trial_token() -> str:
    try:
        cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        client_id = cached.get("anonymous_client_id")
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        client_id = None
    if not client_id:
        client_id = secrets.token_urlsafe(24)
    trial = _http_json(
        "/v1/trials",
        method="POST",
        headers={"X-Anonymous-Client-ID": client_id},
    )
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(
            {
                "base_url": BASE_URL,
                "trial_token": trial["trial_token"],
                "expires_at": trial["expires_at"],
                "anonymous_client_id": client_id,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return trial["trial_token"]


def request(
    registered_path: str,
    params: dict | None = None,
    *,
    trial_path: str | None = None,
    public: bool = False,
    method: str = "GET",
    json_body: dict | None = None,
):
    if public:
        return _http_json(registered_path, params, method=method, json_body=json_body)

    license_key = os.getenv("QUESTION_SERVICE_LICENSE")
    if license_key:
        return _http_json(
            registered_path,
            params,
            headers={"X-API-Key": license_key},
            method=method,
            json_body=json_body,
        )

    token = _load_trial_token() or _create_trial_token()
    return _http_json(
        trial_path or registered_path,
        params,
        headers={"X-Trial-Token": token},
        method=method,
        json_body=json_body,
    )


def account_request(
    path: str,
    *,
    method: str = "GET",
    json_body: dict | None = None,
):
    token = os.getenv("QUESTION_SERVICE_ACCOUNT_TOKEN")
    if not token:
        raise SystemExit(
            "This command needs a signed-in website account. Open the account URL "
            "from the onboarding command, then configure QUESTION_SERVICE_ACCOUNT_TOKEN "
            "locally. Never paste the token into chat."
        )
    return _http_json(
        path,
        headers={"Authorization": f"Bearer {token}"},
        method=method,
        json_body=json_body,
    )


def add_common_filters(
    parser: argparse.ArgumentParser, *, include_query_only: bool = True
) -> None:
    parser.add_argument("--subject-id", type=int)
    parser.add_argument("--grade-id", type=int)
    parser.add_argument("--question-type")
    parser.add_argument("--difficulty-min", type=float)
    parser.add_argument("--difficulty-max", type=float)
    parser.add_argument("--year", type=int)
    if include_query_only:
        parser.add_argument("--paper-type")
    parser.add_argument("--keyword")
    knowledge_filter = parser.add_mutually_exclusive_group()
    knowledge_filter.add_argument("--knowledge-id", type=int)
    knowledge_filter.add_argument(
        "--knowledge-tree-id",
        dest="knowledge_tree_ids",
        type=int,
        action="append",
        help="Select a knowledge-tree branch including descendants; repeat for multiple branches.",
    )
    parser.add_argument("--edition-id", type=int)
    parser.add_argument("--chapter-id", type=int)
    if include_query_only:
        parser.add_argument("--auto-gradable", choices=("true", "false"))
    parser.add_argument("--with-images", action="store_true")
    if include_query_only:
        parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--random", action="store_true")


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _share_expiry_days(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer from 1 to 365") from None
    if not 1 <= parsed <= 365:
        raise argparse.ArgumentTypeError("must be an integer from 1 to 365")
    return parsed


def _share_create_body(args: argparse.Namespace) -> dict | None:
    """Build an explicit share body while preserving the safe API defaults."""
    body = {}
    expires_in_days = getattr(args, "expires_in_days", None)
    if expires_in_days is not None:
        body["expires_in_days"] = expires_in_days
    if getattr(args, "include_answers", False):
        body["include_answers"] = True
    if getattr(args, "no_watermark", False):
        body["show_watermark"] = False
    return body or None


def _builder_handoff_payload(args: argparse.Namespace) -> dict | None:
    """Return a bounded, credential-free builder handoff payload."""
    fields = {
        "mode": getattr(args, "mode", None),
        "title": getattr(args, "title", None),
        "prompt": getattr(args, "prompt", None),
        "subject_id": getattr(args, "subject_id", None),
        "phase_id": getattr(args, "phase_id", None),
        "grade_id": getattr(args, "grade_id", None),
        "edition_id": getattr(args, "edition_id", None),
        "chapter_id": getattr(args, "chapter_id", None),
        "chapter_label": getattr(args, "chapter_label", None),
        "knowledge_tree_ids": getattr(args, "knowledge_tree_ids", None),
        "knowledge_labels": getattr(args, "knowledge_labels", None),
        "question_type": getattr(args, "question_type", None),
        "difficulty": getattr(args, "difficulty", None),
        "keyword": getattr(args, "keyword", None),
        "region": getattr(args, "region", None),
        "semester": getattr(args, "semester", None),
        "question_count": getattr(args, "question_count", None),
        "with_images": True if getattr(args, "with_images", False) else None,
    }
    if not any(value not in (None, [], "") for value in fields.values()):
        return None

    for key in (
        "subject_id",
        "phase_id",
        "grade_id",
        "edition_id",
        "chapter_id",
    ):
        value = fields[key]
        if value is not None and value <= 0:
            raise SystemExit(f"--{key.replace('_', '-')} must be a positive integer")

    knowledge_tree_ids = fields["knowledge_tree_ids"] or []
    knowledge_labels = fields["knowledge_labels"] or []
    if len(knowledge_tree_ids) > 20 or any(value <= 0 for value in knowledge_tree_ids):
        raise SystemExit(
            "--knowledge-tree-id accepts at most 20 positive IDs per handoff"
        )
    if knowledge_labels and len(knowledge_labels) != len(knowledge_tree_ids):
        raise SystemExit(
            "--knowledge-label must be omitted or repeated once for each --knowledge-tree-id"
        )
    kept_knowledge_indexes = []
    seen_knowledge_ids = set()
    for index, tree_id in enumerate(knowledge_tree_ids):
        if tree_id in seen_knowledge_ids:
            continue
        seen_knowledge_ids.add(tree_id)
        kept_knowledge_indexes.append(index)
    fields["knowledge_tree_ids"] = [
        knowledge_tree_ids[index] for index in kept_knowledge_indexes
    ] or None

    question_count = fields["question_count"]
    if question_count is not None and not 1 <= question_count <= 50:
        raise SystemExit("--question-count must be between 1 and 50")

    text_limits = {
        "title": 160,
        "prompt": 4000,
        "chapter_label": 120,
        "question_type": 120,
        "keyword": 100,
        "region": 120,
        "semester": 32,
    }
    for key, limit in text_limits.items():
        value = fields[key]
        if value is None:
            continue
        value = value.strip()
        if len(value) > limit:
            raise SystemExit(f"--{key.replace('_', '-')} exceeds {limit} characters")
        fields[key] = value or None

    labels = knowledge_labels
    if len(labels) > 20 or any(len(label.strip()) > 120 for label in labels):
        raise SystemExit(
            "--knowledge-label accepts at most 20 labels of 120 characters each"
        )
    if labels and any(not label.strip() for label in labels):
        raise SystemExit("--knowledge-label values cannot be blank")
    fields["knowledge_labels"] = [
        labels[index].strip() for index in kept_knowledge_indexes
    ] if labels else None

    return {
        "v": 1,
        "handoff_id": secrets.token_hex(16),
        **{key: value for key, value in fields.items() if value is not None},
    }


def _builder_handoff_url(builder_url: str, payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    if len(encoded) > BUILDER_HANDOFF_MAX_ENCODED_LENGTH:
        raise SystemExit(
            "Builder handoff is too large; shorten the prompt or knowledge labels"
        )
    parsed = urllib.parse.urlsplit(builder_url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if payload.get("mode") in {"manual", "ai"}:
        query = [(key, value) for key, value in query if key != "mode"]
        query.append(("mode", payload["mode"]))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), f"handoff={encoded}")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call the question-bank API with a License or a 100-question trial."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("onboarding")
    builder = subparsers.add_parser("builder")
    builder.add_argument("--mode", choices=("manual", "ai"))
    builder.add_argument("--title")
    builder.add_argument(
        "--prompt",
        help="Original natural-language paper request to prefill without auto-running AI.",
    )
    builder.add_argument("--subject-id", type=int)
    builder.add_argument("--phase-id", type=int)
    builder.add_argument("--grade-id", type=int)
    builder.add_argument("--edition-id", type=int)
    builder.add_argument("--chapter-id", type=int)
    builder.add_argument("--chapter-label")
    builder.add_argument(
        "--knowledge-tree-id",
        dest="knowledge_tree_ids",
        type=int,
        action="append",
    )
    builder.add_argument(
        "--knowledge-label",
        dest="knowledge_labels",
        action="append",
    )
    builder.add_argument("--question-type")
    builder.add_argument("--difficulty", choices=("easy", "medium", "hard"))
    builder.add_argument("--keyword")
    builder.add_argument("--region")
    builder.add_argument("--semester")
    builder.add_argument("--question-count", type=int)
    builder.add_argument("--with-images", action="store_true")
    subparsers.add_parser("quota")
    subparsers.add_parser("subjects")
    subparsers.add_parser("grades")

    editions = subparsers.add_parser("editions")
    editions.add_argument("--subject-id", type=int, required=True)
    editions.add_argument("--phase-id", type=int)
    editions.add_argument("--grade-id", type=int)

    types = subparsers.add_parser("question-types")
    types.add_argument("--subject-id", type=int)
    types.add_argument("--phase-id", type=int)

    chapters = subparsers.add_parser("chapters")
    chapters.add_argument("--subject-id", type=int, required=True)
    chapters.add_argument("--grade-id", type=int)
    chapters.add_argument("--edition-id", type=int)
    chapters.add_argument("--parent-id", type=int)
    chapters.add_argument("--limit", type=int, default=200)

    knowledge = subparsers.add_parser("knowledge-points")
    knowledge.add_argument("--subject-id", type=int, required=True)
    knowledge.add_argument("--phase-id", type=int)
    knowledge.add_argument("--parent-id", type=int)
    knowledge.add_argument("--keyword")
    knowledge.add_argument("--limit", type=int, default=200)

    questions = subparsers.add_parser("questions")
    add_common_filters(questions)
    questions.add_argument(
        "--include-solutions",
        action="store_true",
        help="Include answers and analyses for explicit answer-checking workflows.",
    )

    practice = subparsers.add_parser("practice-page")
    add_common_filters(practice, include_query_only=False)
    practice.add_argument("--title", default="我的临时练习")

    question = subparsers.add_parser("question")
    question.add_argument("question_id", type=int)
    question.add_argument("--include-solutions", action="store_true")

    subparsers.add_parser("papers")
    paper_shares = subparsers.add_parser("paper-shares")
    paper_shares.add_argument("--paper-id", type=_positive_int, required=True)
    share = subparsers.add_parser("share-paper")
    share.add_argument("--paper-id", type=_positive_int, required=True)
    share.add_argument("--expires-in-days", type=_share_expiry_days)
    share.add_argument(
        "--include-answers",
        action="store_true",
        help="Include standard answers in this public snapshot; analyses stay private.",
    )
    share.add_argument(
        "--no-watermark",
        action="store_true",
        help="Create this public snapshot without a visible watermark.",
    )
    rotate_share = subparsers.add_parser("rotate-share")
    rotate_share.add_argument("--paper-id", type=_positive_int, required=True)
    rotate_share.add_argument("--share-id", type=_positive_int, required=True)
    rotate_share.add_argument("--expires-in-days", type=_share_expiry_days)
    revoke_share = subparsers.add_parser("revoke-share")
    revoke_share.add_argument("--paper-id", type=_positive_int, required=True)
    revoke_share.add_argument("--share-id", type=_positive_int, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    values = vars(args)
    command = values.pop("command")

    if command == "onboarding":
        result = request("/v1/agent/onboarding", public=True)
    elif command == "builder":
        onboarding = request("/v1/agent/onboarding", public=True)
        handoff = _builder_handoff_payload(args)
        result = {
            "builder_url": (
                _builder_handoff_url(onboarding["urls"]["builder"], handoff)
                if handoff
                else onboarding["urls"]["builder"]
            ),
            "account_url": onboarding["urls"]["account"],
            "message": (
                "Open the builder and explicitly accept the transferred requirements. "
                "The link does not contain credentials and does not run AI or consume quota by itself."
                if handoff
                else "Open the builder to create and save a paper. Sharing is public with a watermark; printing requires a free account."
            ),
        }
    elif command == "quota":
        result = request("/v1/quota", trial_path="/v1/trial/quota")
    elif command == "subjects":
        result = request("/v1/meta/subjects", public=True)
    elif command == "grades":
        result = request("/v1/meta/grades", public=True)
    elif command == "editions":
        result = request(
            "/v1/meta/editions",
            {
                "subject_id": args.subject_id,
                "phase_id": args.phase_id,
                "grade_id": args.grade_id,
            },
            public=True,
        )
    elif command == "question-types":
        result = request(
            "/v1/meta/question-types",
            {"subject_id": args.subject_id, "phase_id": args.phase_id},
            public=True,
        )
    elif command == "chapters":
        result = request(
            "/v1/meta/chapters",
            {
                "subject_id": args.subject_id,
                "grade_id": args.grade_id,
                "edition_id": args.edition_id,
                "parent_id": args.parent_id,
                "limit": args.limit,
            },
            public=True,
        )
    elif command == "knowledge-points":
        result = request(
            "/v1/meta/knowledge-points",
            {
                "subject_id": args.subject_id,
                "phase_id": args.phase_id,
                "parent_id": args.parent_id,
                "keyword": args.keyword,
                "limit": args.limit,
            },
            public=True,
        )
    elif command == "questions":
        result = request(
            "/v1/questions",
            {
                "subject_id": args.subject_id,
                "grade_id": args.grade_id,
                "question_type": args.question_type,
                "difficulty_min": args.difficulty_min,
                "difficulty_max": args.difficulty_max,
                "year": args.year,
                "paper_type": args.paper_type,
                "keyword": args.keyword,
                "knowledge_id": args.knowledge_id,
                "knowledge_tree_ids": args.knowledge_tree_ids,
                "edition_id": args.edition_id,
                "chapter_id": args.chapter_id,
                "auto_gradable": args.auto_gradable,
                "has_images": "true" if args.with_images else None,
                "offset": args.offset,
                "limit": args.limit,
                "random_order": "true" if args.random else "false",
            },
            trial_path="/v1/trial/questions",
        )
    elif command == "practice-page":
        practice_body = {
            "title": args.title,
            "subject_id": args.subject_id,
            "grade_id": args.grade_id,
            "question_type": args.question_type,
            "difficulty_min": args.difficulty_min,
            "difficulty_max": args.difficulty_max,
            "year": args.year,
            "keyword": args.keyword,
            "knowledge_id": args.knowledge_id,
            "knowledge_tree_ids": args.knowledge_tree_ids,
            "edition_id": args.edition_id,
            "chapter_id": args.chapter_id,
            "has_images": True if args.with_images else None,
            "limit": args.limit,
            "random_order": args.random,
        }
        result = request(
            "/v1/practice-pages",
            trial_path="/v1/trial/practice-pages",
            method="POST",
            json_body={
                key: value for key, value in practice_body.items() if value is not None
            },
        )
    elif command == "question":
        result = request(
            f"/v1/questions/{args.question_id}",
            trial_path=f"/v1/trial/questions/{args.question_id}",
        )
    elif command == "papers":
        result = account_request("/v1/account/papers")
    elif command == "paper-shares":
        result = account_request(f"/v1/account/papers/{args.paper_id}/shares")
    elif command == "share-paper":
        result = account_request(
            f"/v1/account/papers/{args.paper_id}/shares",
            method="POST",
            json_body=_share_create_body(args),
        )
    elif command == "rotate-share":
        result = account_request(
            f"/v1/account/papers/{args.paper_id}/shares/{args.share_id}/rotate",
            method="POST",
            json_body=(
                {"expires_in_days": args.expires_in_days}
                if args.expires_in_days is not None
                else None
            ),
        )
    elif command == "revoke-share":
        result = account_request(
            f"/v1/account/papers/{args.paper_id}/shares/{args.share_id}",
            method="DELETE",
        )
    else:
        raise AssertionError(f"Unhandled command: {command}")

    if command in {"questions", "question"} and not args.include_solutions:
        result = _redact_solutions(result)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
