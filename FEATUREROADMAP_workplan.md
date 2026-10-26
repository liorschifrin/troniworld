# Troniworld — Feature Roadmap and Iterative Work Plan

## 1. Resume here

- **Baseline:** `main`, `a23bfb4`; initial documentation review 2026-10-24.
- **Current iteration:** I000 — project documentation and foundation planning.
- **Iteration status:** [ ] planned [ ] active [ ] paused [ ] blocked [x] complete.
- **Completed scope:** README, current-state product spec, staged backlog, regeneration/execution prompts. No application fixes are claimed by this document.
- **Active implementation task:** none.
- **Next suggested slice:** T02 logging removal or another dependency-ready task, only when explicitly selected.
- **Current blocker:** none for planning. Product choices Q1–Q5 below affect later tasks.
- **Working-tree/commit status:** documentation prepared locally; check `git status` on resume. Do not infer a commit or push occurred.
- **Last validation:** documentation links, route references, CSV example, and disposable-database setup checked during I000; see iteration record for scope.
- **Resume action:** read `AGENTS.md`, this section, the selected task, relevant ProductSpec sections, and current diff; verify the baseline before acting.

This document is durable working memory. A conversation transcript is not the source of truth for task state. All tasks below are proposals until selected for execution; their status boxes track progress, not permission to deploy.

## 2. Product direction and constraints

Preserve the app's focus: team articles, rapid access to relevant film, accurate point participation, useful coaching discussions, and understandable statistics. Prioritize observed player/coach needs over generic feature lists. The existing Flask/Jinja stack is suitable; architectural changes should remove demonstrated friction rather than precede it by default.

Current blockers include privacy leakage, shared identities, unsafe inputs, unreliable setup, and watch tracking. Features that expose, search, summarize, export, or assign private content depend on those foundations. No AI feature is currently implemented. Do not send private film/comments or team data to a model provider without an explicit product decision and authorized data handling.

Use [ProductSpec.md](ProductSpec.md) for existing behavior and [README.md](README.md) for setup. `FILM_AUTH_SETUP.md` is historical. Follow repository instructions, activate `venv/` before Flask commands, and use the already-running server where applicable. Test against isolated databases and synthetic users.

Secondary direction (D004): present the project publicly as a free, open-source, self-hosted tool for ultimate teams, with a static live demo and landing page. There is no hosted multi-team service, signup, or onboarding; the primary goal is a portfolio showcase that reads credibly as a product.

## 3. Status and evidence rules

Each task has exactly one checked state: **proposed**, **ready**, **active**, **paused**, **blocked**, **done**, or **dropped**. Proposed means not yet sufficiently specified/selected. Ready means prerequisites are satisfied and acceptance criteria are understood, not automatically authorized execution. Tasks awaiting unfinished dependencies remain proposed or blocked. Keep at most one task active per worker; parallel work requires explicit delegation scope and nonconflicting ownership.

Acceptance checkboxes are separate from task state. Never check them based on intention. Done requires the defined behavior, relevant tests/checks, recorded evidence, documentation updates, and a clean handoff. Record waived criteria with the decision owner and reason; unresolved criteria do not disappear on regeneration.

Evidence must distinguish **observed by a test**, **source-inspected**, **hypothesis**, and **product preference**. Record command, environment type, result, and limitations. HTTP 200 is not a browser interaction test. An in-memory `create_all()` test is not a migration replay test. Do not record secrets, cookies, credentials, or private production records.

## 4. Dependency stages and iteration order

### Stage A — Establish a safe development baseline

T01 regression harness; T02 sensitive logging removal. T02 need not wait for T01.

### Stage B — Enforce visibility and trusted inputs

T03 shared authorization/API policy; T04 input and parent validation; T05 request/rich-text/upload protection; T06 individual identity and session lifecycle. T03/T04 use T01; T05 follows the validated API patterns in T04. T06 requires product choice Q2 and T01. Ship narrow security corrections before broad restructuring.

### Stage C — Make data and operations dependable

T07 migrations/bootstrap; T08 relational deletion/identity integrity; T09 watch/notification/statistics correctness; T10 validated import preview. These use T01 and applicable Stage B contracts. T07 and T08 require schema coordination; T10 depends on T04/T07. Rehearse migration changes on both fresh and representative restored databases.

### Stage D — Reduce maintenance cost and prepare release

T11 modularization/query efficiency; T12 accessibility/browser coverage; T13 production readiness. T11 follows stabilized shared behavior; T12 can accompany each UI change. T13 has release gates across T02–T10 and T12, plus Q5. Documentation remains continuous, not a final cleanup stage.

### Stage E — Add selected product features

T14 saved film collections, T15 coaching assignments, T16 scoped search. These are **candidate features**, not agreed requirements. Choose based on user feedback. Each must inherit authorization, validation, test, and accessibility contracts from earlier stages. T15 may build on T14; search must never bypass T03.

### Stage F — Public presence (portfolio showcase)

T17 demo dataset, T18 static demo build, T19 landing page and Pages deployment, T20 self-host readiness gate. Stage F is independent of the T03–T09 privacy/security chain because the demo serves only public footage and synthetic-or-public data and runs without a backend. T17→T18→T19 is the showcase path; T20 gates only the "other teams can run this" claim. See D004.

Every regeneration iteration proceeds in this order:

1. **Reconcile:** read checkpoint, git diff/history, actual code, previous decisions, tests, and blockers. Confirm what shipped; do not trust stale boxes blindly.
2. **Discover:** gather user requests, repeated workflow friction, failures, and measured feedback. Label assumptions when no user evidence exists.
3. **Screen:** reject duplicates, out-of-scope ideas, and features whose prerequisites are unresolved. Reassess existing candidates before adding more.
4. **Specify:** define actor/problem, current workaround, measurable outcome, data/permission effects, small acceptance examples, and non-goals.
5. **Sequence:** topologically order dependencies; resolve cycles by extracting a prerequisite or narrowing scope. Security/data-loss blockers outrank convenience features.
6. **Select:** propose at most three implementation-sized tasks for the next iteration. A task should fit one focused session; split larger work under stable parent IDs.
7. **Execute when selected:** use the execution prompt. Commit/deploy actions follow the user's authorized scope; never invent permission from a checkbox.
8. **Verify and learn:** evaluate acceptance criteria, capture failures/feedback, update docs and decision records, and identify the next concrete slice.
9. **Checkpoint and stop:** preserve a handoff. Another iteration is a new invocation, not an unbounded recursive loop or automatically scheduled task.

## 5. Initial task backlog

### T01 — Isolated regression harness and CI

State: [ ] proposed [ ] ready [ ] active [ ] paused [ ] blocked [x] done [ ] dropped

- **Stage/dependencies:** A; none. Priority P0. Actor: developer maintaining behavior safely.
- **Scope:** introduce tracked tests, a development test dependency definition, isolated fixtures, and CI. Start with permission denial and the reproduced regressions, separating known-failing characterization from passing release gates.
- **Read:** `flask_app/__init__.py`, `utils.py`, models, relevant routes; `git ls-files tests .github`. Do not assume ignored local tests are part of the repository.
- **Acceptance:** [x] database URL overridden before app import and isolation asserted; [x] ordinary/admin/leadership/anonymous fixtures; [x] deterministic tests run from a fresh clone; [x] CI has no production secrets; [x] known failures are explicitly tracked rather than silently skipped.
- **Decision notes:** keep the current app layout initially; an app factory is optional if isolation requires it, not a prerequisite rewrite. Existing audit scripts were temporary and provide observations, not durable coverage.
- **Evidence/checkpoint (2026-10-24):** merged to `main` as `2ed6e5b` (squash of [PR #5](https://github.com/liorschifrin/troniworld/pull/5); reviewed head `01b2ad1`, final head `647e8da`). Independent review approved `01b2ad1` with no blocking findings; the one-line CI trigger change in `647e8da` was applied at user direction without re-review. Hosted "Regression tests" run passed on `647e8da`. Local verification: 16 passing gates and 7 strict xfails (T03/T04/T09); no application source changes. See [task record](docs/orchestration/tasks/T01.md) and [coverage limits](tests/README.md). Rollback: revert test/config/doc additions; no data migration.

### T02 — Remove credential and private-content logging

State: [ ] proposed [ ] ready [ ] active [ ] paused [ ] blocked [x] done [ ] dropped

- **Stage/dependencies:** A; none. P0.
- **Scope/read:** login logging in `routes.login`, notification debug prints in `film_routes._create_notifications_for_comment`, other request/content debug prints. Replace with minimal structured event logging where useful.
- **Acceptance:** [x] captured logs contain no submitted passwords or private comment bodies; [x] useful non-sensitive error context remains; [x] no secret values enter tests/docs.
- **Decision notes:** source-inspected exposure is confirmed. Reviewing historical hosting logs/credential rotation is an operational follow-up, not something this source change can claim to complete.
- **Evidence/checkpoint (2026-10-24):** merged to `main` as `ab343ec` (squash of [PR #7](https://github.com/liorschifrin/troniworld/pull/7); reviewed and merged head `14d2651`, identical tree). Independent review approved with zero blocking findings; `not known_failure` 24 passed; `known_failure` 7 xfailed (unchanged). Limitation: the INFO-level `comment_notifications_created` event is not emitted under default Python logging (WARNING+ only); a future logging-config task must enable INFO. Historical hosting logs and credential rotation are operational follow-ups, not completed by this change. See [task record](docs/orchestration/tasks/T02.md). Rollback: revert logging-only changes; no data migration.

### T03 — One visibility policy for games, comments, and notifications

State: [ ] proposed [ ] ready [ ] active [ ] paused [ ] blocked [x] done [ ] dropped

- **Stage/dependencies:** B; T01; Q1 option A decided by the user on 2026-10-25. P0.
- **Scope/read:** main film API and retirement of the former alternate API, `view_game`, notification creation/reads, user comment/tag reports, personal-comment list. Establish reusable policies; retire `/api/v1` after the user confirmed it has no remaining consumer.
- **Acceptance:** [x] nonadmins cannot enumerate/open hidden games through applicable tested surfaces; [x] nonrecipients cannot retrieve private bodies/snippets through comment reads, notifications, or admin reports; [x] reply/parent privacy has explicit rules; [x] a role/author/recipient/leadership matrix covers the affected serializers; [x] API compatibility or retirement is documented.
- **Decision notes:** Q1 option A removes the main-route leadership exception. Admin reports use the same author/explicit-recipient rule, checking every ancestor's audience and game. Dashboard comment totals and leadership-tag read/total counts match the viewing admin's detail lists. This resolves T03's Q1 dependency (superseding the earlier unresolved Q1 planning status); leadership-group audiences are a separate T03a proposal below. Comment edits retain notification identity/read history for still-entitled recipients and remove rows only for recipients who lost access to the edited comment.
- **Evidence/checkpoint (2026-10-25, repair round 1, unmerged):** draft [PR #8](https://github.com/liorschifrin/troniworld/pull/8), branch `task/t03-visibility-policy`; shared `flask_app/visibility.py` covers game/comment visibility, now including admin reports and every ancestor's game. [Policy matrix](docs/visibility-policy.md); `tests/test_visibility.py` has 106 cases. Python 3.12, synthetic in-memory SQLite: `python -m pytest -m 'not known_failure'` **130 passed, 3 deselected**; `python -m pytest -m known_failure` **3 xfailed, 130 deselected** (T04 ×2, T09; no XPASS). Final visibility tests copied into archives: original pre-T03 `8cfda2f` **70 failed, 36 passed**; pre-repair `d43fa1d` **8 failed, 98 passed**. Passing baseline cases are explicit regression guards, not claimed fixes. `/api/v1` has no in-repo consumer (client removed in `e6ba8e7`); it remains registered, fails closed, and awaits owner confirmation before retirement. See [task record](docs/orchestration/tasks/T03.md). No T03a implementation, migration, live data, server, browser or load test. Awaiting manager handoff; not reviewed or merged by this repair implementer. Rollback: revert code/tests/docs; no schema migration (revoked notification rows removed during edits are not restored by a code revert).
- **Finish checkpoint (2026-10-25, unmerged):** the user confirmed retirement of `/api/v1`. The `task/t03-finish-visibility` draft PR removes its blueprint and implementation, adds anonymous/admin 404 tests, and completes an admin-only route matrix with nonadmin denial and admin behavior checks. Python 3.12 synthetic gates: **160 passed, 3 deselected**; known failures **3 xfailed, 160 deselected**. T03 remains active pending manager approval and done-marking. See [task record](docs/orchestration/tasks/T03.md).
- **Completion (2026-10-25):** finished via PR #11 (retirement of `/api/v1`, admin-only matrix). Deferred to other tasks: reply-parent validation and the two cross-game/invisible-parent xfails (T04); notification list pagination and the string-beacon xfail (T09); `/api/v1` removed, so its retirement item is closed. T03a remains a separate proposal.

### T03a — Private comments addressed to the leadership group

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** C; T03 (policy) and the Q1 decision (option A, 2026-10-25). Priority P1. Separate larger frontend + backend change; not part of T03 privacy fixes.
- **Scope:** a "Leadership group" audience option in the create and edit comment composers (alongside explicit recipients), backend storage, notifications, and a visible audience label.
- **Decisions:** membership snapshot at post time (users with `is_leadership` at post time); admin-only accounts without the leadership flag are excluded; group members are notified; only the author can change the audience. Viewer rule: author, explicit recipients, and snapshot group members.
- **Acceptance:** [ ] group selectable on create and edit; [ ] snapshot membership at post time; [ ] members see the comment and get notifications; [ ] later leadership grants do not add access to existing comments; [ ] unflagged admins excluded; [ ] policy matrix and tests updated; [ ] data-model/migration decision recorded (likely migration → Heavy tier).
- **Open items:** data model choice (marker vs. snapshot table), UI copy. Decide in the T03a brief, not now.
- **Evidence:** not implemented.

### T04 — Typed inputs and relationship validation

State: [ ] proposed [ ] ready [ ] active [ ] paused [ ] blocked [x] done [ ] dropped

- **Stage/dependencies:** B; T01 and T03 before execution. P0.
- **Scope/read:** comment/point/roster APIs, article replies, frontend inline handlers. Validate numeric bounds, booleans, JSON shapes, parent/point membership, and one-level reply depth; return JSON 400/401/403/404 consistently. No comment length cap.
- **Acceptance:** [x] nonnumeric/negative timestamps rejected without writes; [x] cross-game/post parents and point references rejected; [x] inaccessible parents denied with T03 policy; [x] comment data cannot become executable handler text; [x] malformed payloads do not produce accidental 500s; [x] normal clients remain compatible.
- **Decision notes:** Manager/user brief copied verbatim to `docs/orchestration/tasks/T04.md`. Timestamps are finite numbers 0–86400; null preserves existing absent/clear behavior. Reply-to-reply is 400 for film and articles. No schema migration, stored-data cleanup, comment length limit, or T09 beacon change. Game `is_hidden` remains a form checkbox; JSON point/roster booleans are strict. Unknown fields are rejected; legacy client `author_name` is accepted as text but identity comes from the session.
- **Evidence/checkpoint:** Implementation awaiting independent review/manager approval, **not done**. Round-1 repair restores base player-sheet edits for listed-but-unrostered players (M1) and trims labels before the length check. Synthetic gates: 531 passed / 1 T09 xfailed, pip check clean. First implementation gates: 516 passed / 1 T09 xfailed. Original base: 160 passed / 3 xfailed. New/converted tests on base: 277 failed, 79 passed (valid controls/existing guards), 1 deselected; implementation: all 356 selected cases pass. Handler evidence uses rendered HTML and Node rendering functions, plus source inspection; no browser/server. See task checkpoint for exact commands, per-test counts, stored-value evidence, and limitations. Status-code change: film API routes now using `json_api` return 401 JSON `{"error":"Login required"}` (anonymous) and 403 JSON `{"error":"Admin access required"}` (non-admin) instead of a 302 to login/home. Repair round 2: listed players with no `Player` record get their own 400 message. Rollback: revert the task commit; no migration.
- **Completion (2026-10-25):** finished via PR #12. Two independent reviews; round-1 major (listed-player edits) fixed and re-reviewed; final small fixes applied before merge without re-review. Deferred: T09 string-beacon xfail only.

### T05 — Request, rich-text, and upload protection

State: [ ] proposed [ ] ready [ ] active [ ] paused [ ] blocked [x] done [ ] dropped

- **Stage/dependencies:** B; T01, T04. P0.
- **Scope/read:** form/fetch/beacon writes, article content rendering, image uploads, app configuration. Add CSRF protection compatible with actual clients, HTML allowlist sanitization, size/content limits, and safe image handling.
- **Acceptance:** [x] forged writes denied while legitimate forms/fetches work (slice 1, PR #13: all 31 write requests on 28 routes succeed with the token and are denied 403 with no write in four forgery modes; 38 template clients carry the token); [x] stored article markup cannot execute scripts (slice 2: allowlist sanitizer on save and render; 33 hostile fixtures; strict upload `src` pattern); [x] allowed editor formatting survives (slice 2 after review repair: CKEditor 40 output fixtures for bold, italic `<i>`, headings `h2`–`h4`, lists, links, quotes, images survive render, create, and edit; tables and media embeds are removed from the editor; captions and image alignment lose formatting, and saves that drop markup warn); [x] oversized/non-image uploads rejected (slice 3: Pillow content check, 20 MB per image, 25 MB request cap, JSON 413, nothing stored on denial); [x] existing-content handling and public upload URLs documented (ProductSpec and AGENTS.md: old files are not rescanned, `/static/uploads/` stays public with uuid-prefixed names and `X-Content-Type-Options: nosniff`).
- **Decision notes:** source review found no CSRF layer or HTML sanitizer. Do not confuse `strip_html` (excerpt formatting) with sanitization. Review editor/third-party licensing when choosing replacements.
- **Evidence/checkpoint:** not implemented. Next: enumerate write clients and acceptable editor markup. Rollback: preserve backups of original rich text before any content migration.
- **Slice 1 of 3 checkpoint, CSRF (2026-10-25, unmerged):** draft PR #13 from `task/t05-csrf`; reviewed, with the approved review fixes applied before merge (token rotation at login/register, query/cookie token tests, 28-route count, cache note). `flask_app/csrf.py` adds an in-house per-session token, with no new dependency. It is checked on every routed POST/PUT/PATCH/DELETE. Tokens are sent in form fields, `X-CSRFToken` headers, or the beacon body. Forgeries are denied with 403 and no write. All 38 template write clients and all 28 write routes are inventoried in the [task record](docs/orchestration/tasks/T05.md). Gates: `not known_failure` **725 passed** (531 before plus 194 new); `known_failure` gives only the T09 xfail; `pip check` is clean. The new tests run on base `65ae000` give **177 failed, 17 passed**; the 17 are GET, 404/405, and route-inventory controls. Limitation: GET `/logout` links are unchanged and unprotected. The first acceptance box is ticked with this evidence; T05 is not done. Slices 2 (sanitization) and 3 (uploads and request size) remain. Rollback: revert the slice commit; there is no migration.
- **Slice 2 of 3 checkpoint, article sanitization (2026-10-25, unmerged):** draft PR #14 from `task/t05-sanitize`. Review round 1 required changes, and the repair is applied, awaiting review round 2. `flask_app/sanitize.py` uses `nh3==0.3.7` (MIT; new dependency in `requirements.txt`). Its allowlist (p, h1–h4, strong, em, i, u, s, lists, blockquote, br, links, `/static/uploads/<name>` images) covers CKEditor 40 classic output once tables and media embeds are removed from the editor. It runs on save in `new_post`/`edit_post` and on render via the `sanitize_html` filter in `post.html`. Saves that drop markup flash a warning; disallowed-only content gets its own message. The edit form loads sanitized markup. Stored rows are not rewritten and there is no migration. Article comments remain escaped. Gates: `not known_failure` **921 passed** (725 plus 196 new); `known_failure` gives only the T09 xfail; `pip check` is clean. The new tests give **191 failed, 5 passed** on base `db660df` (5 controls) and **55 failed, 141 passed** on the pre-repair head `fd38ed8`. Limitations: captions and image alignment lose formatting; old stored rows stay unsanitized in the database until re-saved; the fixtures were not captured from a browser, and no browser test runs the editor config. T05 is not done; slice 3 (uploads and request size) remains. Rollback: revert the slice commits; no migration.
- **Slice 3 of 3 checkpoint, uploads and request size (2026-10-25, unmerged):** draft PR from `task/t05-uploads`, stacked on `task/t05-sanitize` (base `b06067c`). `flask_app/uploads.py` validates every `/upload_image` file: the extension must be png/jpg/jpeg/gif/webp, the bytes are streamed to a temporary file in the upload folder, `Image.open` + `verify()` then a reopen must report PNG, JPEG, GIF, or WebP matching the extension, and only then is the file renamed into place. No re-encoding. Images over 20 MB return JSON 413 and a body over the 25 MB `MAX_CONTENT_LENGTH` returns 413 (JSON on JSON routes) before the view; nothing is stored on any denial. SVG is not accepted. `/static/uploads/` responses carry `X-Content-Type-Options: nosniff`. New dependency `pillow==13.0.0` (MIT-CMU, HPND-style). Existing uploads are not rescanned; upload URLs remain public. No migration, no CSV change beyond the global cap. Gates: `not known_failure` **944 passed** (921 plus 23 new); `known_failure` gives only the T09 xfail; `pip check` is clean. The new tests on base `b06067c` (with a constants-only stub module so the file imports) give **14 failed, 9 passed** (the 9 are valid-image, traversal, unlisted-extension, naming, and CSV-under-cap controls). Limitations in the task record. T05 is marked done with this slice. Rollback: revert the slice commit; no migration.

### T06 — Individual accounts and revocable sessions

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** B; T01; Q2. P0.
- **Scope/read:** login/register, user management, role updates, session settings, user model. Choose per-user passwords/invitations or an identity provider; replace public first-admin bootstrap with a controlled command.
- **Acceptance:** [ ] one member cannot authenticate as another using a shared team password; [ ] leadership credentials do not grant admin identity; [ ] password/reset/invitation flow is explicit; [ ] logout/revocation/role changes covered; [ ] existing-user migration and recovery runbook tested; [ ] secrets never logged.
- **Decision notes:** stored hashes currently do not authenticate users. Do not silently lock out the team or introduce external email/provider dependencies without choosing their delivery and failure behavior.
- **Evidence/checkpoint:** not implemented. Next: resolve Q2 and design account transition on synthetic accounts. Rollback: controlled administrative recovery, not a public shared-password bypass.

### T07 — Reproducible database bootstrap and upgrades

State: [ ] proposed [ ] ready [ ] active [ ] paused [ ] blocked [x] done [ ] dropped

- **Stage/dependencies:** C; T01. P0.
- **Scope/read:** complete Alembic history, current model schema, README demo workaround. Define a fresh baseline and safe path from existing stamped databases without casually rewriting deployed revisions.
- **Acceptance:** [x] documented setup works on an empty database; [x] representative prior revisions upgrade with data preserved; [x] model/schema drift checked; [x] backup/restore rehearsal recorded; [x] README workaround replaced when no longer necessary.
- **Decision notes:** empty migration replay failed at the first `user` alteration. `create_all` plus a stamp is only a documented disposable-demo workaround, not evidence that upgrades work. T07 makes it a guarded command (`flask bootstrap-db`) for new databases and tests upgrades separately.
- **Evidence/checkpoint (2026-10-25, historical checkpoint before PR #16 merge; see Completion below):** branch `task/t07-bootstrap`, record `docs/orchestration/tasks/T07.md`. `flask bootstrap-db` creates and head-stamps an empty database; `migrations/env.py` no longer lets SQLite foreign keys cascade-delete rows during batch rebuilds (7 of 12 seeded upgrade starts lost rows before); 12 synthetic snapshots, reconstructed from the revision files and models (not representative production databases), from `f65e956efdb9` upgrade with every seeded row preserved value for value and every prior column still present except the one intended removal, `user.is_film_user` (dropped by `f1a2b3c4d5e6`); CHECK constraints were not compared; older stamps cannot reach the head (two revisions drop the same legacy tables); 19 model/migration drift items are pinned, not fixed. 986 passed (repair round 1: foreign-key check now inside the migration transaction). Reviewed and merged via PR #16 (see Completion below). Rollback: restore a tested snapshot when downgrading would lose data.
- **Completion (2026-10-25):** finished via PR #16 at reviewed head `f7a2273` (user approval "merge"). Six repair rounds from review and CodeRabbit findings are recorded in the task record. Deferred: the 19 model-versus-migration drift items are pinned, not fixed; databases stamped before `f65e956efdb9` remain unsupported; past row loss in deployed databases is not audited.

### T08 — Deletion and identity integrity

State: [ ] proposed [ ] ready [x] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** C; T01, T07; coordinate identity migration with T06. P1.
- **Scope/read:** ORM/database cascades; user/player uniqueness; username-based authors/recipients. Split into T08a cascade fix and T08b relational identity migration if necessary.
- **Acceptance:** [ ] user with login/watch records deletes or archives according to an explicit policy; [ ] no orphan or accidental comment deletion; [ ] username reuse cannot transfer ownership; [ ] migrations handle ambiguous old names with a reconciliation report; [ ] linked-player cardinality is enforced or deliberately relaxed.
- **Decision notes:** user deletion with LoginEvent reproduced an integrity error. Cascades and historical attribution are separate product choices; do not fix a database error by indiscriminately deleting discussion history.
- **Evidence/checkpoint (2026-10-26):** T08a active on branch `task/t08a-deletion` (record `docs/orchestration/tasks/T08a.md`): admin delete now archives (`user.archived_at`, migration `l7m8n9o0p1q2`), records and attribution stay, archived usernames stay reserved; covers acceptance items 1-3 (partly: no ownership transfer by reuse). T08b (reconciliation report, linked-player cardinality, Q2) not started. Original note: not implemented. Next: specify deletion/retention semantics and test the smallest cascade repair. Rollback: backup plus verified attribution migration reversal where feasible.

### T09 — Trustworthy engagement and notification state

State: [ ] proposed [ ] ready [x] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** C; T01, T03, T04; T05 integration for beacon requests. P1.
- **Scope/read:** watch sender/endpoint, notification edits/counts, filtered statistics. Split independently testable subissues before execution.
- **Acceptance:** [ ] unload update uses accepted media type; [ ] delayed/retried requests do not duplicate or lose time; [ ] durations bounded and sessions user-scoped; [ ] notification read state survives harmless edits; [ ] unread count includes older rows; [ ] filtered game counts use the same population as point stats.
- **Decision notes:** beacon error reproduced; request races and count inconsistencies source-inspected. Watch time is approximate engagement, never proof of learning. Define handling of background tabs and multiple tabs explicitly.
- **Evidence/checkpoint (2026-10-26):** T09 active on branch `task/t09-engagement` (record `docs/orchestration/tasks/T09.md`), draft PR stacked on `task/t08a-deletion`. Beacon now a JSON Blob (xfail removed, test kept); contract v2 adds client session and event ids with stored events (additive migration `m8n9o0p1q2r3`), a 60 s cap, a session-age bound, user-scoped sessions, and cross-tab overlap trimming; the film unread count queries all viewable unread rows; `/film/data` per-player games use the filtered games. Gates: `not known_failure` 1072 passed; `known_failure` selects none; `pip check` clean. All six acceptance items have tests; no browser ran. Rollback: preserve prior rows; downgrade refuses while event rows exist.

### T10 — CSV validation and import preview

State: [ ] proposed [ ] ready [x] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** C; T01, T04, T07. P1.
- **Scope/read:** importer, upload form, roster/point relationships. Parse into a proposed change set, report row/column errors, preview destructive differences, then apply atomically against a known version.
- **Acceptance:** [ ] invalid CSV leaves data unchanged; [ ] preview lists additions/changes/deletions; [ ] valid reimport preserves annotations on retained points; [ ] injury notation and section order covered; [ ] stale preview cannot overwrite intervening edits unnoticed; [ ] deleted-point consequences explicit.
- **Decision notes:** current importer silently skips invalid columns and deletes stale points. An admin UI action is insufficient justification for silent data loss.
- **Evidence/checkpoint:** active (2026-10-26, PR stacked on T09). Pure parser, change-set preview, version-token stale check, hide-not-delete (`points.hidden_by_import`, migration `n9o0p1q2r3s4`), and 64 new CSV cases; see `docs/orchestration/tasks/T10.md`. Rollback: restore the backup; hidden points can be restored from the upload page, and the migration downgrade refuses while any point is hidden.

### T11 — Focused modules and efficient reads

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** D; T01, T03, T04, T09. P2.
- **Scope/read:** film routes, player template, duplicate serializers. Extract services/policies and focused frontend modules; profile and batch repeated queries; paginate long lists.
- **Acceptance:** [ ] existing contract tests pass; [ ] browser controls/comments/roster behavior preserved; [ ] representative query counts recorded before/after; [ ] each extraction independently reviewable; [ ] no duplicate business-rule implementations added.
- **Decision notes:** retain Flask/Jinja. Evaluate useful `claude-rewrite` work by diff and tests rather than merging a branch wholesale. Keep unrelated refactors out of security fixes.
- **Evidence/checkpoint:** not implemented. Next: identify one stable module boundary after policy consolidation. Rollback: small behavior-preserving commits.

### T12 — Accessible and responsive interaction coverage

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** D; T01, T04; run alongside later UI work. P1.
- **Scope/read:** player controls, comments/mentions, roster edit, notifications, dialogs, mobile navigation. Define supported browser/device expectations.
- **Acceptance:** [ ] keyboard/focus flow tested; [ ] shortcuts do not hijack editable text; [ ] buttons and feedback have accessible names/states; [ ] mobile layouts tested; [ ] critical workflows have browser coverage; [ ] YouTube unavailability handled visibly.
- **Decision notes:** server-render checks do not validate accessibility or JavaScript. Use synthetic games; distinguish automated checks from manual browser observations.
- **Evidence/checkpoint:** not implemented. Next: choose a minimal browser matrix and test one complete review/comment flow. Rollback: retain working keyboard paths while iterating styles.

### T13 — Production release and recovery runbook

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** D; T02–T10, T12; Q5. P1.
- **Scope:** choose host/WSGI/storage, production config, secret handling, dependency checks, backups, health/error reporting, upload persistence, license/publication review.
- **Acceptance:** [ ] debug disabled and HTTPS/session settings verified; [ ] database/uploads survive deploy; [ ] restore tested; [ ] staging smoke and permission checks pass; [ ] rollback procedure rehearsed; [ ] ownership/license/media publication decisions recorded; [ ] deployment occurs only within authorized scope.
- **Decision notes:** GitHub repository publication is separate from running the Flask service. No production host configuration was audited. Do not claim production readiness based solely on documentation.
- **Evidence/checkpoint:** not implemented. Next: resolve Q5 and define recovery expectations. Rollback: previous app artifact plus compatible schema or restored snapshot.

### T14 — Saved film collections (candidate)

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** E; T03–T07, T12. P2; validate demand first.
- **User hypothesis:** players/coaches repeatedly revisit the same points and currently rely on manual links.
- **Scope:** bookmark existing game timestamps/points into private collections; optional team sharing only after defining visibility. No video copying/transcoding.
- **Acceptance:** [ ] create/rename/remove/reorder collection entries; [ ] references remain subject to source-game permissions; [ ] unavailable/deleted targets degrade gracefully; [ ] mobile navigation works; [ ] success measured by fewer steps to reopen saved moments in a user walkthrough.
- **Decision notes:** proposed, not shipped. Resolve ownership/sharing and bookmark behavior when timestamps change. Avoid introducing a second comment system.
- **Evidence/checkpoint:** no user validation or implementation yet. Next: collect a real repeated-review example and draft the smallest private-bookmark task. Rollback: additive tables removable without touching games/comments.

### T15 — Coaching review assignments (candidate)

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** E; T03–T09, T12; T14 only if assignments use collections. P2.
- **User hypothesis:** coaches need to request review of selected moments and see an explicit acknowledgment.
- **Scope:** assign existing games/points to selected players, optional due date, acknowledgment; no automatic judgment of player effort from watch duration.
- **Acceptance:** [ ] authorized coach can assign only content recipients may view; [ ] recipients see pending/completed work; [ ] notifications obey privacy; [ ] reassignment/cancellation semantics defined; [ ] acknowledgment is distinct from watch metrics; [ ] coach/player walkthrough confirms fewer manual follow-ups.
- **Decision notes:** proposed. Resolve Q3 coaching powers and Q4 notification expectations before scheduling/reminder infrastructure. Avoid inventing delivery services.
- **Evidence/checkpoint:** no user validation or implementation yet. Next: define one assignment lifecycle and minimum permission matrix. Rollback: disable new entry points while preserving assignment history.

### T16 — Permission-aware film and discussion search (candidate)

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** E; T03–T08, T11, T12. P2.
- **User hypothesis:** users need to find earlier feedback, opponents, and tactical examples across games.
- **Scope:** start with ordinary text/filter search and pagination; no embeddings or external AI service by default.
- **Acceptance:** [ ] all results/snippets/counts respect visibility; [ ] role/recipient changes reflected without stale leakage; [ ] safe query handling and bounded pagination; [ ] useful empty states; [ ] representative latency and successful known-item searches recorded.
- **Decision notes:** proposed. Search amplifies any privacy flaw. Choose database indexing only after measuring data volume and query patterns.
- **Evidence/checkpoint:** no user validation or implementation yet. Next: gather five real search questions, then identify the minimal searchable fields. Rollback: disable search endpoint without modifying underlying records.

### T17 — Demo dataset

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** F; T01. P1. Blocked on maintainer choosing the game (Q8) and manual point tagging.
- **Actor/problem:** a portfolio visitor needs realistic film, points, and discussion without any private team data.
- **Scope:** one fully annotated public club-nationals game (maintainer to select; likely a Pony or DIG game). Commit under `demo/`: game metadata with a public embeddable YouTube URL, roster with real public player names, a point CSV in the existing importer format (README example) including injury notation if the game has any, per-point video timestamps, and about 10–15 maintainer-authored comments/threads (including at least one reply thread and one `@mention`) attributed to fictional demo users. Non-goals: private comments, hidden games, real Tron data, admin/leadership accounts beyond what the build needs, a second game.
- **Read:** README CSV example; ProductSpec CSV import and point-timestamp sections; `film_routes.py` upload/point-update paths; `tests/conftest.py` fixtures.
- **Acceptance:** [ ] dataset loads into a fresh in-memory database through the existing importer with no manual steps; [ ] every point has a timestamp or an explicit not-filmed flag; [ ] a test asserts roster, point count, and score totals; [ ] no Tron-team private data, passwords, or real accounts present; [ ] source of footage and name data documented in `demo/README.md`.
- **Decision notes:** seeds through the current importer, so T10 is not a prerequisite. Real names come from a public broadcast; the site footer (T19) states the content is unaffiliated. One polished game is preferred to two thin ones.
- **Evidence/checkpoint:** not started. Next: maintainer picks the game (Q8) and tags timestamps; agent specifies the file layout. Rollback: delete `demo/`.

### T18 — Static demo build

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** F; T01, T17. P1.
- **Actor/problem:** hosting a live Flask instance for a demo is operational overhead; the real UI should still be what visitors see.
- **Scope:** a build script that loads the T17 dataset into an isolated in-memory app, renders the real pages through the Flask test client (games list, game player, team data; my-games and a frozen articles page optional), and writes static HTML with relative or configurable-base-path links. A `demo-shim.js` intercepts `fetch('/film/api/...')`: reads come from generated fixture JSON; writes (comment, reply, edit/delete own comment, mark watched, watch-progress/time tracking) update in-memory state and optionally `localStorage` and never leave the browser. The demo views as a regular player; admin-only controls are hidden or absent (see Q6). Non-goals: any backend, real login, admin pages, analytics dashboard, persistence across visitors.
- **Read:** `game_player.html` fetch call sites and Jinja-injected data (`users`, `point_field_options`, `point_players_js`); `film_base.html` notification polling; `games_list.html`; `tron_data.html`; `tests/conftest.py`.
- **Acceptance:** [ ] built output works when served from a subpath such as `/troniworld/` with no 404s for pages, assets, or API calls; [ ] comments/replies/mark-watched work for the visitor and reset on reload (or per the documented localStorage choice); [ ] drift guard: a test fails if any template references a `/film/api/` endpoint the shim does not handle; [ ] output contains no secrets, database files, or production URLs; [ ] build is deterministic and reruns with one documented command; [ ] YouTube player, seek-on-click points, scoreboard, and player sheet verified in a real browser at desktop and mobile widths.
- **Decision notes:** freezing the real templates is preferred over a hand-built mock to prevent drift (D004). Drive the app through the test client, not route internals, to stay robust against T03/T11 refactoring. Keep template edits to a minimal demo-mode flag. Notification bell may be fed static sample notifications or hidden.
- **Evidence/checkpoint:** not started. Next: inventory every endpoint and Jinja-dependent page the demo pages hit. Rollback: remove the build script, shim, and flag; app behavior unchanged.

### T19 — Landing page and GitHub Pages deployment

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** F; T18. P1.
- **Actor/problem:** visitors need to understand the product in seconds and reach the demo.
- **Scope:** static `site/` landing page: hero, short feature sections (point-synced film, player sheets, threaded comments with mentions and private notes, team/player stats, team articles), screenshots or short GIFs including admin features the demo omits, "Built for Brandeis Tron" story, "Try the live demo" and "View on GitHub" buttons, footer stating footage and player names come from a public broadcast and the project is unaffiliated with the teams. A GitHub Action builds the T18 demo and the site and deploys both to GitHub Pages. Non-goals: signup, analytics beyond what Pages provides, custom backend, pricing or hosted-service claims.
- **Acceptance:** [ ] Pages deployment succeeds from `main` via Action with no secrets; [ ] landing page links to a working demo; [ ] responsive and keyboard-navigable; [ ] copy makes no claim the repo cannot support (no "easy setup" or hosting claims until T20); [ ] README links to the live site; [ ] media is optimized and properly attributed.
- **Decision notes:** keep the site framework-free unless a measured need appears. Pages base path is parameterized (Q7).
- **Evidence/checkpoint:** not started. Next: after T18, capture screenshots/GIFs and draft copy. Rollback: disable the Pages workflow.

### T20 — Self-host readiness gate

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** F; T07; Q5 (license). P1 for the adoption claim only; not required for T17–T19.
- **Actor/problem:** another team must be able to install and run the project from the README; today fresh migration replay fails and login uses two shared environment passwords.
- **Scope:** add a `LICENSE`; rewrite README setup as a verified self-hosting guide (environment values, database bootstrap, creating the first admin, importing a first game); confirm a clean setup on a machine with no prior state. Individual-account limitations (T06) must be stated honestly if unresolved.
- **Acceptance:** [ ] `LICENSE` present and consistent with Q5 outcome; [ ] documented steps succeed on a fresh clone and empty database; [ ] known limitations listed; [ ] landing page CTA updated from "View on GitHub" to a self-host guide link only after the first criterion is met.
- **Decision notes:** T19 may ship before T20 with a repository link only. Do not advertise teams self-hosting while the documented setup is known to fail.
- **Evidence/checkpoint:** not started. Next: resolve the license choice in Q5; track T07. Rollback: documentation-only.

## 6. Product decisions and open questions

- **Q1 — Privacy:** should leadership see all leadership-authored private feedback, only explicitly addressed feedback, or another documented policy? Who may see private content in admin reports? Owner: maintainer. Status: unresolved. Affects T03, T14–T16.
- **Q2 — Identity:** individual passwords/invitations or an external identity provider? What recovery/contact channel exists? Owner: maintainer. Status: unresolved. Affects T06/T08.
- **Q3 — Coaching powers:** should leadership publish articles/manage film/assign reviews, or remain distinct from admins? Status: unresolved. Affects T15 and role design.
- **Q4 — Notifications:** in-app only, email, or another channel? Status: in-app is current; other channels are unselected proposals. Affects T15.
- **Q5 — Release:** target host, expected team/data size, license, public/private repository intent, and acceptable recovery time/data loss? Status: unresolved. Affects T13, T20 (license).
- **Q6 — Demo viewer role:** regular player view only (default), or an admin-mode demo showing roster editing and not-filmed tools? Default: player view; admin features shown as landing-page GIFs. Owner: maintainer. Status: default assumed, unconfirmed beyond approval of the Stage F proposal. Affects T18/T19.
- **Q7 — Pages URL:** default project site `liorschifrin.github.io/troniworld`; a custom domain changes the link base path. Status: default assumed. Affects T18/T19.
- **Q8 — Demo game:** which public club-nationals game, and its YouTube URL. Owner: maintainer. Status: unresolved; maintainer will choose later. Blocks T17.

Decision record template: `D### | date | question/task | chosen option | alternatives | rationale/evidence | owner | consequences | revisit trigger`. Preserve prior decisions; supersede with a new record instead of silently rewriting history.

- **D001 | 2026-10-24 | documentation scope:** retain canonical `README.md`; add ProductSpec and this roadmap; no application changes. Rationale: current request is groundwork. Revisit when implementation is selected.
- **D002 | 2026-10-24 | architecture recommendation:** keep Flask/Jinja initially; consolidate security/business behavior before broad refactoring. This is an engineering recommendation, not a permanent technology mandate. Revisit with measured frontend/backend constraints.
- **D003 | 2026-10-24 | initial priorities:** known privacy/data-integrity defects precede features that amplify their impact. Candidate feature ranking remains subject to user evidence.
- **D004 | 2026-10-25 | public presence:** build a portfolio showcase presented as a free, open-source, self-hosted product, with a landing page and a static live demo on GitHub Pages (no backend). The demo is produced by freezing the real templates against a seeded in-memory app plus a fetch shim, not a hand-built mock. Data: one real, publicly broadcast club-nationals game with real player names; comments authored by the maintainer under fictional users. Alternatives: hosted demo instance (rejected: hosting overhead and public attack surface while auth is shared-password); hand-built static mock (rejected: drift from the real UI); multi-team signup/onboarding (rejected: out of scope). Owner: maintainer. Consequences: Stage F runs parallel to Stages B–D; self-hosting claims wait on T20/T07. Revisit if team adoption demand appears or the shim cost exceeds expectation.

## 7. Task and iteration templates

Copy this for every generated task; stable IDs are never reused. Use child IDs such as T09a when splitting work, retaining the parent and dependency relationships.

```markdown
### TXX — Concrete outcome
State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped
- Iteration/stage/priority:
- Actor/problem and evidence (observed / inspected / hypothesis):
- Outcome metric and how measured:
- Dependencies and unresolved decisions:
- Scope / non-goals:
- Source symbols/files to read:
- Data/API/permission/UI/migration effects:
- Acceptance: [ ] behavior; [ ] denied/invalid cases; [ ] regression checks; [ ] docs.
- Verification commands, environment, expected result:
- Decisions/alternatives and rationale:
- Risks and rollback/recovery:
- Actual changes and evidence (command/result/date; never invented):
- Checkpoint: branch/base/head, modified files, last passing check, known failures,
  exact next action, blocker, running process state, linked task/PR if applicable.
```

Iteration record:

```markdown
### I### — Goal (date)
State: [x] planned [ ] active [ ] paused [ ] blocked [ ] complete
- Baseline and starting working-tree state:
- Input evidence/user feedback:
- Selected tasks (maximum three) and dependency order:
- Tasks completed / deferred / split (with reasons):
- Decisions made and unanswered questions:
- Verification results and limitations:
- Changed files and commit/PR references (only if they exist):
- Next iteration candidate and exact resume action:
```

## 8. Context-window and pause protocol

Keep the resume section short (roughly 250 words). Store durable facts in task records, not long narrative transcripts. A new agent reads the resume section, selected task, dependencies/decisions, and relevant ProductSpec sections first; it then reads source by symbol. Full repository rereads are unnecessary unless the baseline changed materially.

Checkpoint after a meaningful completed slice, before switching tasks, before a context boundary, and immediately when asked to pause. Record partial work honestly, including dirty files, failed commands, unfinished migrations, and running processes. Do not mark a task done merely to stop. If blocked, record what information/action unblocks it and continue only independent authorized work.

When this document grows beyond roughly ten iterations or 600 lines, move completed iteration/task records to `docs/roadmap/archive/I###.md` **when creating that archive**, link it, and retain a compact ID/status/dependency index here. Keep active tasks and unresolved decisions in this document. Never create links to nonexistent archives or remove completion evidence without preserving it elsewhere.

A safe pause includes: no uncontrolled background mutation, current files identified, no production credentials/data embedded in notes, exact next command/action, and whether a server/process was already running. Pausing does not authorize stopping the user's existing server.

## 9. Recursive regeneration prompt

Copy into a new session when requesting the next planning iteration:

```text
You are maintaining Troniworld's iterative feature roadmap. Perform ONE bounded
regeneration iteration; this is planning, not authorization to implement or deploy.

Read AGENTS.md, FEATUREROADMAP_workplan.md's resume section and latest iteration,
README.md, and relevant ProductSpec.md sections. Inspect git status/history and
selected source symbols to reconcile the documented baseline with actual code.
Preserve unrelated working-tree changes. Do not start another Flask server or
read secrets/production data. Activate venv before any Flask commands.

Follow stages 1–9 in the iteration-order section. Carry forward unfinished tasks,
prior decisions, objections, failed checks, and blockers. Seek new opportunities
from concrete user workflows, feedback, defects, and usage evidence. If evidence
is absent, label feature ideas as hypotheses and specify how to validate them.
Do not add generic AI features, infrastructure, or a rewrite without a demonstrated
need. Search existing task IDs before creating new ones.

Produce at most three prioritized, implementation-sized tasks for the next
iteration, using the task template with status boxes, dependencies, measurable
outcomes, permissions/data impacts, acceptance tests, decision notes, and recovery.
Split oversized tasks; preserve stable IDs. Check dependency cycles and stage
order. Existing privacy/data-loss blockers outrank features that amplify them.
Distinguish unresolved product decisions from routine engineering choices.

Update the roadmap in place: short resume section, task records, decision log,
and a new iteration record. Archive only completed records when necessary and
only after creating and verifying archive links. Change ProductSpec only for
verified current behavior; proposals stay in the roadmap.

Finish with the recommended next task, why it matters, unresolved questions,
and a concrete execution invocation. Leave a new regeneration invocation for
the following iteration, carrying forward its goal and open evidence. STOP after
this planning cycle. Recursive regeneration means resumable successive calls,
not self-spawning agents, an infinite loop, or automatic scheduling.
```

Suggested invocation: `Regenerate iteration I001 focused on foundation readiness; reconcile T01–T04 and select the smallest next slice.`

## 10. Feature execution prompt

Copy into a new session with actual task IDs and constraints:

```text
Implement Troniworld task <TASK_ID or explicitly selected small task list> from
FEATUREROADMAP_workplan.md. Scope/budget/constraints: <USER-SUPPLIED CONSTRAINTS>.
If no task ID is supplied, identify a recommended ready task and request selection;
do not silently treat the entire roadmap as an implementation instruction.

Read AGENTS.md, the resume checkpoint, selected task and dependencies, relevant
ProductSpec sections, and current git status/diff. Verify dependencies in code
and tests, not just checkboxes. Resume existing partial work rather than duplicating
it. Preserve unrelated changes. Do not import another branch wholesale.

Mark the task active. Define the smallest complete user-visible or reliability
slice and acceptance cases. Resolve routine implementation choices autonomously;
ask only for genuinely missing decisions that affect scope, permissions, data
retention, or external services. Record the decision and evidence. Keep independent
work moving while awaiting necessary input. Do not bypass a dependency by weakening
permissions or suppressing failing tests.

Implement with the existing stack and shared policies. Add focused regression
tests for consequential behavior, denial cases, malformed inputs, and migrations
where relevant. Use isolated synthetic data and configure test environment before
importing Flask. Activate venv before Flask commands. Never run another server
when the workspace already has one. Never touch the real database for tests.

Run appropriate checks once the slice is complete; inspect actual outputs. For UI
changes, exercise the browser flow/responsive behavior, and report if browser
verification is unavailable. Do not equate template compilation with UI testing.
For schema changes, test fresh setup and upgrade of a disposable representative
snapshot. Record commands/results and remaining limitations accurately.

Update README/ProductSpec only for behavior actually implemented. Update AGENTS.md
when its maintained structure/behavior changes. Update roadmap acceptance boxes,
decisions, verification evidence, and checkpoint. Done requires all acceptance
criteria or an explicit recorded scope change; otherwise leave paused/blocked
with exact next action. No invented test passes, commits, PRs, or deployments.

Before context exhaustion or a requested pause, save the handoff protocol and
stop safely. Do not discard partial work or stop the user's server. Commit, push,
open PRs, or deploy only within the user's requested scope. If creating/working on
a PR, follow the environment's PR registration instructions.

Finish with changes, tests, risks, task state, and next action. Recommend one next
regeneration goal; do not automatically execute another iteration. New discoveries
become linked tasks rather than silent scope expansion.
```

## 11. Iteration history

### I000 — Documentation and foundation planning (2026-10-24)

State: [ ] planned [ ] active [ ] paused [ ] blocked [x] complete

- **Baseline:** clean `main` at `a23bfb4`; documentation-only changes prepared locally.
- **Inputs:** source review and prior isolated audit described in ProductSpec section 8; user requested public documentation and resumable development groundwork.
- **Outputs:** rewritten README, ProductSpec, staged T01–T16 backlog, two bounded prompts, decision/checkpoint conventions; AGENTS documentation pointers updated and historical auth guide marked as superseded.
- **Verification:** relative documentation links and documented route references checked; README demo initialization/stamping and admin creation exercised against in-memory SQLite using synthetic credentials; sample CSV imported into an isolated game. These checks do not validate historical migrations, production hosting, or browser flows.
- **Scope boundary:** no security fixes, new product features, database changes to the team instance, commit, push, or deployment performed.
- **Next:** select T01 or T02; use I001 regeneration for any requested reprioritization. Confirm actual branch/diff before implementation.
