# API Reference

## Authentication and metering

Send the License as `X-API-Key`, or an anonymous token as `X-Trial-Token` to the `/v1/trial/*` routes. Create an anonymous token with `POST /v1/trials`; it lasts 24 hours and serves at most 100 questions. Never put credentials in query parameters. Question list calls consume the number of parent questions returned; question detail consumes one. Metadata and quota calls are free.

Cloud agents should generate one stable URL-safe identifier and send it as
`X-Anonymous-Client-ID` when creating a trial. Cache and reuse both that ID and
the returned trial token. Do not rotate IDs to evade limits.

Account registration is completed only on the website. The legacy
`POST /v1/register` exchange is disabled; an Agent must never create standalone
registered Keys by rotating anonymous identities. The free registered plan
starts at 200 questions per day. Website accounts may increase this by successful referrals: +100 per
invite until 1000, +50 until 2000, then +20 until the configured hard limit
(currently 3000). After registration, the website presents the starting 200
questions as a “欢迎入庄” moment before offering referrals. Referrals are
voluntary: skipping them does not reduce the 200-question allowance or remove
account features. Copying or opening a link earns nothing; only a genuine new
account completing registration can add quota. Never describe the free plan as
unlimited or an invitation as required.

A website session does not implicitly authenticate the local CLI adapter. If the
registration flow reveals a first API Key, the user may store it locally as
`QUESTION_SERVICE_LICENSE` to make the Skill consume the registered account's
daily allowance. Never ask for that Key in chat. Until it is configured locally,
the adapter continues to use its cached anonymous trial independently of the
website's signed-in state.

## Temporary practice pages

Prefer `POST /v1/trial/practice-pages` for an anonymous learner and
`POST /v1/practice-pages` for a configured License. Both accept the usual
subject, grade, type, difficulty, year, textbook edition, chapter, knowledge,
keyword, and limit
filters in a JSON body. The response contains a 24-hour `page_url` for online
answering and a `paper_url` for paper-style viewing and printing. Recipients can
switch between both views without creating another practice page.
Set `has_images: true` when the learner explicitly requests illustrated questions.

The hosted page renders the source question and images without agent rewriting,
keeps answers hidden until submission, performs simple choice scoring, and offers
compact A4 printing with questions only, inline answers, or a separate answer key. Give
the URL to the learner instead of restating questions or answers in chat.
This temporary guest-page printing is distinct from printing a persistent public
shared paper: the latter requires a signed-in website account.

Never register during first use. Registration is appropriate only after the
anonymous quota is exhausted or when the learner asks for persistent account
features.

## Textbook editions, papers, and sharing

Use `GET /v1/meta/editions` to resolve textbook editions such as 人教版. Pass
`edition_id` directly to question or practice-page requests to filter the whole
textbook, and also pass it to `GET /v1/meta/chapters` when browsing that
textbook's chapter tree. Use
`GET /v1/meta/knowledge-points` and use `knowledge_id` for one exact linked
knowledge point, `knowledge_tree_id` for one selected branch and all of its
descendants, or `knowledge_tree_ids` for multiple branches. Exact and tree
knowledge modes should not be mixed. These dimensions may be combined with the
textbook or chapter filters.

The local `builder` command can transfer resolved context to the website with
`--mode`, `--title`, `--prompt`, subject/phase/grade/edition/chapter IDs,
repeatable `--knowledge-tree-id` plus display `--knowledge-label`, question
type, difficulty, keyword, region, semester, image preference, and a question
count from 1 to 50. It returns a URL whose fragment contains bounded context,
never credentials. Both the CLI encoder and website decoder enforce a 32,000
character encoded-fragment limit, so an oversized request fails before a dead
link is returned. The Builder removes that fragment, retains the request in
same-tab session storage through registration or sign-in, and requires an
explicit confirmation before creating a separate paper. It only prefills the
AI prompt; it does not send it or retrieve questions automatically. The
accepted paper stores the validated handoff as `builder_context` in its normal
paper settings, so a later paper GET or Builder reload restores the textbook,
chapter, knowledge branches, filters, image preference, question count, and
original prompt. When the Builder Agent retrieves or auto-fills questions, the
backend re-reads that account-owned context and applies edition, chapter,
knowledge-branch, keyword, difficulty, and image constraints to both retrieval
and supply estimates. A missing taxonomy record or a scope that conflicts with
the current paper returns `409 paper_builder_scope_invalid`; it is never treated
as an unfiltered request. The unaccepted fragment remains same-tab only and is
not an account authorization token.

Every new CLI-generated handoff also contains a fresh `handoff_id` matching
`^[a-f0-9]{32}$`. This is an account-scoped idempotency key, not authorization.
If the create-paper response is lost, retry the same URL and unchanged request:
the same account receives the existing paper, and the Builder reloads its
current paper and item state. Generating a new URL produces a new ID and is an
intentional new-paper request. The same ID with different creation content
returns `409`; clients should stop and create a fresh handoff only after the
changed request is confirmed.

The handoff accepts knowledge-tree node IDs, not exact linked `knowledge_id`
values. Use the `id` returned by `knowledge-points` only when that tree node is
the intended scope. Do not silently broaden an exact-point request. The AI
`prompt` should contain only the paper-building request, never unrelated share
or account mutations.

Persistent paper routes require an account session bearer token, not the Agent
License. Store it only in `QUESTION_SERVICE_ACCOUNT_TOKEN`; never ask the user
to paste it into chat or include it in output. `GET /v1/account/papers` lists
the account's papers. Share lifecycle routes are:

- `GET /v1/account/papers/{paper_id}/shares`: return at most 100 records, with
  every unexpired active link ordered before inactive history. An active v2
  record can include its recoverable `url`; old records may return `url: null`
  and `legacy_unrecoverable: true`.
- `POST /v1/account/papers/{paper_id}/shares`: create an immutable public
  snapshot. It accepts optional `expires_in_days` from 1 to 365,
  `include_answers` (default `false`), and `show_watermark` (default `true`).
  With `include_answers: true`, the snapshot may expose only the stored standard
  `answer`/`answer_html` values, recursively including compound subquestions;
  analyses, explanations, and solution fields remain private.
- `DELETE /v1/account/papers/{paper_id}/shares/{share_id}`: revoke a link.
- `POST /v1/account/papers/{paper_id}/shares/{share_id}/rotate`: invalidate the
  old token and create a recoverable token for the exact same immutable
  snapshot and the same answer/watermark settings. Rotation does not copy later
  edits from the paper; any content-setting values in a rotation request cannot
  override the original artifact. It accepts the same optional
  `expires_in_days`; an expired, revoked, or already rotated record cannot be
  rotated.

Snapshot JSON is limited to 8 MiB UTF-8. One paper can retain at most 20
unexpired active links and one account at most 200. New snapshots omit empty
sections; the public delivery path also filters empty sections from old stored
snapshots. The website Builder manages effective links. The bundled CLI exposes
`paper-shares`, `share-paper`, `rotate-share`, and `revoke-share`; list records
first and confirm the exact IDs before invalidating a URL.
Listing does not authorize creating a public snapshot: if no recoverable active
URL exists, `share-paper` requires a separate explicit user request. Rotation
or revocation requires both an explicit destructive request and a uniquely
matched `paper_id + share_id` after listing.

Anyone with a share URL may view the content selected for that link. The safe
default is questions only with a visible watermark. When the owner explicitly
chooses otherwise, `include_answers: true` exposes standard answers and
`show_watermark: false` removes the ordinary source mark from both public view
and print. Existing and legacy shares use the safe defaults. Changing either
choice requires creating a new immutable share; it never mutates an already
distributed URL.
`POST /v1/account/paper-shares/{token}/print-access` requires a signed-in
account for every answer/watermark setting and must explicitly return
`allowed: true`. The share page validates a
cached account session before presenting it as signed in; stale sessions fall
back to the same-page sign-in or registration dialog. The public payload's
registration URL includes `mode=register`, a safe `next` path back to the shared
paper, and the owner's signed referral code.

Registration reveals “欢迎入庄 / 200 题已到账” before the user continues to the
browser print dialog, so the page does not need to navigate away. It then offers
an optional action to copy the new account's own invitation link. Signed-in
accounts obtain that URL from `GET /v1/account/referral` in its `invite_url`
field. A malformed, signature-invalid, nonexistent, or inactive-owner referral
never blocks base registration and grants no referral reward. The external
link-and-return account route remains a compatible fallback. Only a genuine
referred registration can credit the owner; copying or opening a link cannot.
This is a product print gate, not copy protection.

For both public viewing and print authorization, `404` means the share is
unavailable, revoked, or its owner is inactive; `410` means it expired. A `401`
from print authorization means the account session must be refreshed, not that
an Agent License is required.

## Question filters

`GET /v1/questions` accepts:

- `subject_id`, `grade_id`
- `question_type`
- `difficulty_min`, `difficulty_max` from 0 to 5
- `year`, `paper_type`
- `keyword` against title and displayed knowledge names
- `knowledge_id`, using the accurate question-to-knowledge relation
- `knowledge_tree_id`, matching a knowledge-tree node and all descendants
- `knowledge_tree_ids`, matching any of several knowledge-tree branches
- `edition_id`, filtering questions linked to any chapter in that textbook edition
- `chapter_id`, supporting both ordinary subjects and the Chinese/English direct relation
- `auto_gradable`
- `has_images`: require or exclude questions containing source images
- `offset`, `limit` (maximum 100), `random_order`

## Important response fields

- `title`, `options`: rich question content and separated choices
- `answer`: clean machine-checkable answer when available
- `answer_html`: standard answer with rich text
- `analysis`: rich explanation
- `question_type`, `difficulty`, `subject_id`, `grade_id`
- `knowledges`, `area`, `year`, `paper_type`, `source`
- `is_auto_gradable`
- `content_hash`: stable source identifier
- `has_images`, `image_urls`: explicit media presence and directly usable absolute URLs
- `subquestions`: child questions for a compound parent

Formula and content fields contain legacy HTML. Prefer the normalized absolute
URLs in `image_urls` instead of deriving paths from that HTML.

## Release and verification boundaries

- The repository implementation supports textbook editions, chapters, exact
  knowledge points, descendant-inclusive knowledge trees, same-tab Builder
  handoff, registered-paper sharing, referrals, and account-gated print access.
- Do not infer production availability from repository source, a local build, or
  an older installed Skill. Verify the public `onboarding` response and the
  route needed for the current request.
- The sequential API contract can be exercised with FastAPI TestClient and
  SQLite. MySQL row-lock concurrency and the browser sequence from shared paper
  through the on-page sign-in/registration ceremony and `window.print()` require
  their own integration checks. The website's current build/source/SSR contract
  tests are not a real-browser end-to-end print test.
- Builder handoff is intentionally credential-free and same-tab. It is not a
  signed cross-device handoff and must not carry personal or secret data. Its
  `handoff_id` prevents duplicate first creation but does not grant access.
