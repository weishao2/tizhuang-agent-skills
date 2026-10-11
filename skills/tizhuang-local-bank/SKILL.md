---
name: tizhuang-local-bank
description: "Manage a teacher's independent local question bank compatible with Obsidian: browse knowledge trees and native tags, import PDF questions with diagrams and traceable page regions, organize a dashboard, use a persistent visual paper basket with ordered questions and per-paper scores, and assemble editable DOCX and printable papers. Use for 本地题库、Obsidian 题库、PDF 试卷入库、本地分类、标签检索、老师组卷、Word试卷、Agent组卷. Online-only retrieval belongs to the optional existing question-bank skill."
---

# 题庄 · 我的本地题库（教师版）

An independent teacher tool. Obsidian is an optional editor; no plugin or website account is required for local workflows. Do not create student accounts, learning clients, online answering, or assignments. Paper outputs serve teacher printing and preparation.

## Setup

For installation, upgrades, repair, or “装过就更新/跳过”, read [Agent installation](references/install.md) and use the version-aware installer from the verified starter package. Check the current Agent and the user's vault, then install only missing/older components; preserve current/newer versions, user data, settings and the old question-bank skill. Ordinary bank operations do not trigger upgrades.

Resolve `scripts/local_bank.py` relative to this SKILL.md as `<cli>`; never use a fixed developer machine path. Python 3.10+ is required. Create a dedicated virtual environment and install `scripts/requirements.txt` if needed. Run commands with its Python as `<python>`. Do not install into another skill's environment.

If `.tizhuang-install.json` exists in this skill directory, prefer its verified `runtime.python`; otherwise use the existing dedicated environment. Missing setup can be completed with the installation workflow above.

Obtain a user-selected vault path. If absent, propose a new `题庄本地题库` directory under the current workspace. Do not guess an existing vault or scan the entire disk. Initialize only that directory:

```text
<python> <cli> --vault <vault> init
<python> <cli> --vault <vault> organize
```

Read JSON responses. Nonzero exit / `ok:false` means failure: fix the cause. Never silently discard requested filters. V1 is Unicode substring + structured search; do not claim vector/semantic search.

## Teacher workspace and PDF import

Read [teacher workspace](references/teacher-workspace.md) for directory cleanup, native tags, the dashboard, and classification changes. `organize` creates a full backup before migrating an existing Chinese vault; it preserves IDs, content blocks, teacher additions, and source records. Never implement ad hoc folder moves instead. A question has one physical note and may belong to multiple knowledge nodes and tags.

For any PDF import, read [PDF workflow](references/pdf-import.md). Prepare original pages and candidate regions with `pdf-prepare`; all papers require checked v2 editable Markdown/LaTeX and isolated figures before `pdf-import`. Inspect every original page; keep source regions for provenance, not question-body screenshots. Remove original paper question numbers from the body and figure captions; retain source numbers only in provenance and preserve logical subquestion/figure references. Use original answers only; flag uncertain recognition. Legacy image drafts need an explicit request and `--image-draft`; upgrading old drafts uses the backed-up `--upgrade-to-editable` path described in the PDF workflow. When a local subject/phase knowledge tree is available, also classify each question using actual tree IDs based on its assessed content; tags alone are not a knowledge-tree link. Preserve multiple relevant nodes for compound questions. Use `classify --file <checked-plan.json> --plan` then `classify --file <checked-plan.json>` for existing notes as documented in the teacher workspace; do not reimport or overwrite question bodies. Unknown textbook stays unknown, and a knowledge-only request must leave textbook/chapter fields unchanged. Do not label a batch successful just because the PDF was copied, and do not mark imported questions reviewed on the teacher's behalf.

The plugin’s 自动分类 button runs conservative exact-tag matching with `auto-classify`, then produces an Agent handoff for unresolved questions. This is not embedded model inference; when receiving that handoff, read its listed questions and apply a checked `classify` plan. PDF commit attempts this matching automatically. See the teacher workspace reference for batch and paper-link repair commands.

The Obsidian plugin offers the same local dashboard, tree/tag filters, and PDF draft workflow. Its bundled helper is independent of installed skills. A teacher vault may already use `teacher/v2`; read `.bank/config.json` before referring to paths. In that layout, knowledge notes live in `资料/知识目录`, textbook notes in `资料/教材目录`, pictures in `资料/附件`, and personal notes in `教学笔记`. The legacy paths below apply before organization.

## Website knowledge tree

Resolve website subject/phase IDs from public metadata (`https://tizhuang.qcscience.cc/api/v1/meta/subjects`, `/v1/meta/phases`) or explicit user-supplied IDs:

```text
<python> <cli> --vault <vault> tree --subject 2 --phase 2
<python> <cli> --vault <vault> tree-search --subject 2 --phase 2 --query 一次函数
```

Direct public metadata; no existing skill dependency or paid question query. Offline mode: `--file <tree.json>`. `知识库/标准知识点/<学段·学科>` is generated; teacher notes go in `知识库/我的教学笔记`, which refresh never edits. Download supplies hierarchy and IDs, not questions or complete teaching explanations. `knowledge_tree_ids` (tree nodes) and `knowledge_ids` (exact linked points) are distinct; never invent equivalence.

## Textbook editions and chapters

Knowledge trees are not textbook tables of contents. For textbook-specific work, first resolve the teacher's actual edition (including 2024/revision and 五四/六三 distinctions), grade and semester. Do not default to 人教版 or treat similarly named editions as equivalent:

```text
<python> <cli> --vault <vault> editions --subject 2 --phase 2
<python> <cli> --vault <vault> chapters --subject 2 --phase 2 --edition <edition-id>
<python> <cli> --vault <vault> chapter-search --subject 2 --phase 2 --edition <edition-id> --query 一次函数
```

Downloads all chapters for exactly that edition, preserves each node's source grade ID, writes `教材目录/<学段·学科·教材版本>` separately. Grade IDs may denote semester/book in source metadata; resolve names, never guess arithmetic conversions. Use `--file <chapters.json>` offline. In textbook-specific import, explicitly pass `--edition <id> --chapter <id1> <id2>` only when the teacher or original query establishes membership. Existing website response may not carry edition; do not infer it from a knowledge-point name. Unknown edition stays unknown and is excluded from edition-filtered results. Chapter filter requires subject+phase+edition and includes descendants.

## Store questions

Read [question contract](references/question-contract.md) when constructing JSON. Preserve teacher content, website options order and compound questions. Do not present AI-generated answers as original website answers. Label AI material `source.kind: ai`, draft pending review.

```text
<python> <cli> --vault <vault> import --file <questions.json>
<python> <cli> --vault <vault> import --file <website-result.json> --website --subject 2 --phase 2 --download-images
<python> <cli> --vault <vault> import --file <question-package.zip>
```

Website import adapts existing question-bank output without invoking it. Raw per-question JSON is preserved in provenance sidecars. Never import account responses, keys, cookies or tokens. HTTPS pictures download only with `--download-images`; unresolved pictures prevent review/printing. Obsidian edits retain YAML, ID and three section markers. Markdown is primary; SQLite rebuilds automatically.

Default draft status. Mark reviewed only after the teacher explicitly confirms the content, answers and pictures:

```text
<python> <cli> --vault <vault> review --ids <id1> <id2> --confirm
```

An import request alone is not proof of answer review. Draft storage and search still work.

## Search and assemble

```text
<python> <cli> --vault <vault> search --subject 2 --phase 2 --knowledge <tree-node-id> --query 一次函数
<python> <cli> --vault <vault> paper --subject 2 --phase 2 --knowledge <tree-node-id> --count 10 --title 一次函数练习 --plan
<python> <cli> --vault <vault> paper --ids <id1> <id2> --title 一次函数练习
```

Filters: `--subject --phase --grade --edition --chapter --type --tag --status --knowledge --query --unused`. Preserve selected textbook version during search/paper generation. Tree filter includes descendants, requires subject+phase. Selection is deterministic; explicit IDs give teacher ordering. Check supply with `--plan`; shortage fails without broadening. Formal papers accept reviewed records; the teacher may explicitly confirm pending questions in the plugin. For visual selection, ordering and paper-only scores, read [paper basket](references/paper-basket.md). `paper --basket <basket.json>` shares the plugin engine and generates separate question-only and teacher DOCX plus HTML copies without changing source scores. For Agent assembly, search and inspect actual local records, resolve the requested textbook/chapter, run a supply plan, then write an ordered basket JSON with explicit per-paper scores when required. Use a new request JSON under `.bank/paper-requests` or a user-chosen output path; never edit an existing frozen request or overwrite the visual basket while the plugin is generating. CLI selection without a basket keeps using the original question scores. Do not add `--confirm-reviewed` unless the teacher has explicitly confirmed those questions.

Return paths to `试卷/<试卷名称>/试卷.md`, `打印稿/试卷.html` (no-answer print copy), `教师稿/试卷.html` (teacher reference). The print copy is a teacher deliverable; there is no student application. Share only the no-answer DOCX or print directory when delivering to students; parent contains teacher answers and manifest. Both HTML copies contain frozen content, local images and offline MathML for supported LaTeX. Inspect output before claiming print readiness. Complex formulas/layouts can need manual correction. Browser printing can produce PDF; DOCX is generated natively with editable text, ordinary tables and supported TeX converted to Word equations. Existing image formulas and PDF crops remain embedded images, not OCR text. Unsupported Word formulas or merged cells fail explicitly. Return the `student_docx` and `teacher_docx` paths. Never describe an image-based PDF import as fully editable. Word edits do not sync back to the question bank; use a new paper request for another version. Native PDF export remains browser printing.

## Optional family handoffs

Read [family relationships](references/family.md) when relevant. Recommend a family member only when useful; never require installation.

```text
<python> <cli> --vault <vault> export --ids <id1> --output <question-package.zip>
<python> <cli> --vault <vault> export --ids <id1> --output <teacher-package.zip> --include-solutions
```

Default exports omit solutions and their unused assets. A video explanation generally needs teacher-authorized solutions export. Future video skill receives a package, not private index paths or another skill's Python module. Do not claim that future skill exists already.

Local storage does not guarantee local model inference: honestly describe data sent to the agent. Never upload a whole vault automatically. Do not edit or install over existing question-bank. V1 single writer only: serialize mutations.


## Chinese presentation and existing-vault migration

Before the first tree/textbook download, run `catalog --subject <id> --phase <id>` to cache real subject, phase and edition names. Visible folders: `题目库`, `知识库/标准知识点`, `知识库/我的教学笔记`, `教材目录`, `附件`, `试卷`, `待整理`. Knowledge and chapter notes show names and at most two ancestor folder levels; IDs live in Chinese-labelled properties and hidden mappings. Question files show titles and can be renamed without changing their IDs.

For an old English-directory vault, use `migrate-cn --catalog-labels <names.json>`. Obtain the label JSON from public subjects/phases/editions metadata with keys subjects/phases/editions, each mapping string IDs to real names. Migration creates a full ZIP backup beside the vault, preserves extra teacher note sections, updates links, and hides legacy machine directories. Do not independently rename folders or remove legacy copies. Local presentation does not change portable JSON keys or packet `Assets/` paths. Obsidian's application language is a separate user setting; do not imply that renaming vault files changes the application's own menu language.
