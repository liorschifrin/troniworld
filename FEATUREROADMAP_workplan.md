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

State: [ ] proposed [x] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** A; none. P0.
- **Scope/read:** login logging in `routes.login`, notification debug prints in `film_routes._create_notifications_for_comment`, other request/content debug prints. Replace with minimal structured event logging where useful.
- **Acceptance:** [ ] captured logs contain no submitted passwords or private comment bodies; [ ] useful non-sensitive error context remains; [ ] no secret values enter tests/docs.
- **Decision notes:** source-inspected exposure is confirmed. Reviewing historical hosting logs/credential rotation is an operational follow-up, not something this source change can claim to complete.
- **Evidence/checkpoint:** implemented on branch `task/t02-credential-logging` (pending review/merge; acceptance boxes above left unchecked until then). Source-inspected: removed all `print` calls in `routes.login` (form dict, usernames), `routes.new_post` (title/author/content), and `film_routes._create_notifications_for_comment` (comment text, mention names); replaced with module-logger events (`login_failed reason=… [user_id]`, `comment_notifications_created comment_id game_id count private`). No other `print`/`logging` calls exist under `flask_app/` outside `templates/unused/`. Observed by test: `tests/test_logging_privacy.py` (8 cases; all fail on the prior source, pass now) asserts caplog/stdout contain no synthetic password, username, private body or post content. Not covered: historical hosting logs and credential rotation (operational follow-up). Rollback: preserve safe logging; never reintroduce raw credentials to debug a regression.

### T03 — One visibility policy for games, comments, and notifications

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** B; T01; Q1 for final policy. P0.
- **Scope/read:** both film APIs, `view_game`, notification creation/reads, user comment/tag reports, personal-comment list. Establish reusable policies; determine whether `/api/v1` has a real consumer before retirement.
- **Acceptance:** [ ] nonadmins cannot enumerate/open hidden games through any applicable surface; [ ] nonrecipients cannot retrieve private bodies/snippets; [ ] reply/parent privacy has explicit rules; [ ] a role/author/recipient/leadership matrix covers every serializer; [ ] API compatibility or retirement is documented.
- **Decision notes:** audit reproduced private content in `/api/v1`, direct hidden-game access, and private-reply notification leaks. Fix obvious leakage while preserving only explicitly chosen leadership exceptions; do not broaden access to make tests pass.
- **Evidence/checkpoint:** not implemented. Next: inventory all read paths and write the policy matrix. Rollback: changes must fail closed without destroying stored content.

### T04 — Typed inputs and relationship validation

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** B; T01 before execution. P0.
- **Scope/read:** comment/point/roster APIs, article replies, frontend inline handlers. Validate numeric bounds, booleans, JSON shapes, lengths, parent/point membership, and allowed reply depth; return JSON 400/401/403/404 consistently.
- **Acceptance:** [ ] nonnumeric/negative timestamps rejected without writes; [ ] cross-game/post parents and point references rejected; [ ] inaccessible parents denied with T03 policy; [ ] comment data cannot become executable handler text; [ ] malformed payloads do not produce accidental 500s; [ ] normal clients remain compatible.
- **Decision notes:** SQLite accepted a nonnumeric timestamp in the audit. Integer ORM declarations alone are insufficient. The browser execution path was source-inspected, not browser-executed.
- **Evidence/checkpoint:** not implemented. Next: define request schemas and invalid-payload cases. Rollback: no database migration expected for request validation; assess stored invalid values separately.

### T05 — Request, rich-text, and upload protection

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** B; T01, T04. P0.
- **Scope/read:** form/fetch/beacon writes, article content rendering, image uploads, app configuration. Add CSRF protection compatible with actual clients, HTML allowlist sanitization, size/content limits, and safe image handling.
- **Acceptance:** [ ] forged writes denied while legitimate forms/fetches work; [ ] stored article markup cannot execute scripts; [ ] allowed editor formatting survives; [ ] oversized/non-image uploads rejected; [ ] existing-content handling and public upload URLs documented.
- **Decision notes:** source review found no CSRF layer or HTML sanitizer. Do not confuse `strip_html` (excerpt formatting) with sanitization. Review editor/third-party licensing when choosing replacements.
- **Evidence/checkpoint:** not implemented. Next: enumerate write clients and acceptable editor markup. Rollback: preserve backups of original rich text before any content migration.

### T06 — Individual accounts and revocable sessions

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** B; T01; Q2. P0.
- **Scope/read:** login/register, user management, role updates, session settings, user model. Choose per-user passwords/invitations or an identity provider; replace public first-admin bootstrap with a controlled command.
- **Acceptance:** [ ] one member cannot authenticate as another using a shared team password; [ ] leadership credentials do not grant admin identity; [ ] password/reset/invitation flow is explicit; [ ] logout/revocation/role changes covered; [ ] existing-user migration and recovery runbook tested; [ ] secrets never logged.
- **Decision notes:** stored hashes currently do not authenticate users. Do not silently lock out the team or introduce external email/provider dependencies without choosing their delivery and failure behavior.
- **Evidence/checkpoint:** not implemented. Next: resolve Q2 and design account transition on synthetic accounts. Rollback: controlled administrative recovery, not a public shared-password bypass.

### T07 — Reproducible database bootstrap and upgrades

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** C; T01. P0.
- **Scope/read:** complete Alembic history, current model schema, README demo workaround. Define a fresh baseline and safe path from existing stamped databases without casually rewriting deployed revisions.
- **Acceptance:** [ ] documented setup works on an empty database; [ ] representative prior revisions upgrade with data preserved; [ ] model/schema drift checked; [ ] backup/restore rehearsal recorded; [ ] README workaround replaced when no longer necessary.
- **Decision notes:** empty migration replay failed at the first `user` alteration. `create_all` plus a stamp is only a documented disposable-demo workaround, not evidence that upgrades work.
- **Evidence/checkpoint:** not implemented. Next: build a migration graph and list historically assumed tables. Rollback: restore a tested snapshot when downgrading would lose data.

### T08 — Deletion and identity integrity

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** C; T01, T07; coordinate identity migration with T06. P1.
- **Scope/read:** ORM/database cascades; user/player uniqueness; username-based authors/recipients. Split into T08a cascade fix and T08b relational identity migration if necessary.
- **Acceptance:** [ ] user with login/watch records deletes or archives according to an explicit policy; [ ] no orphan or accidental comment deletion; [ ] username reuse cannot transfer ownership; [ ] migrations handle ambiguous old names with a reconciliation report; [ ] linked-player cardinality is enforced or deliberately relaxed.
- **Decision notes:** user deletion with LoginEvent reproduced an integrity error. Cascades and historical attribution are separate product choices; do not fix a database error by indiscriminately deleting discussion history.
- **Evidence/checkpoint:** not implemented. Next: specify deletion/retention semantics and test the smallest cascade repair. Rollback: backup plus verified attribution migration reversal where feasible.

### T09 — Trustworthy engagement and notification state

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** C; T01, T03, T04; T05 integration for beacon requests. P1.
- **Scope/read:** watch sender/endpoint, notification edits/counts, filtered statistics. Split independently testable subissues before execution.
- **Acceptance:** [ ] unload update uses accepted media type; [ ] delayed/retried requests do not duplicate or lose time; [ ] durations bounded and sessions user-scoped; [ ] notification read state survives harmless edits; [ ] unread count includes older rows; [ ] filtered game counts use the same population as point stats.
- **Decision notes:** beacon error reproduced; request races and count inconsistencies source-inspected. Watch time is approximate engagement, never proof of learning. Define handling of background tabs and multiple tabs explicitly.
- **Evidence/checkpoint:** not implemented. Next: isolate beacon fix and design idempotent increments. Rollback: preserve prior rows; version client/server contract if needed.

### T10 — CSV validation and import preview

State: [x] proposed [ ] ready [ ] active [ ] paused [ ] blocked [ ] done [ ] dropped

- **Stage/dependencies:** C; T01, T04, T07. P1.
- **Scope/read:** importer, upload form, roster/point relationships. Parse into a proposed change set, report row/column errors, preview destructive differences, then apply atomically against a known version.
- **Acceptance:** [ ] invalid CSV leaves data unchanged; [ ] preview lists additions/changes/deletions; [ ] valid reimport preserves annotations on retained points; [ ] injury notation and section order covered; [ ] stale preview cannot overwrite intervening edits unnoticed; [ ] deleted-point consequences explicit.
- **Decision notes:** current importer silently skips invalid columns and deletes stale points. An admin UI action is insufficient justification for silent data loss.
- **Evidence/checkpoint:** not implemented. Next: extract a pure parser with representative synthetic CSV fixtures. Rollback: import snapshot/change journal or documented database restore.

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

## 6. Product decisions and open questions

- **Q1 — Privacy:** should leadership see all leadership-authored private feedback, only explicitly addressed feedback, or another documented policy? Who may see private content in admin reports? Owner: maintainer. Status: unresolved. Affects T03, T14–T16.
- **Q2 — Identity:** individual passwords/invitations or an external identity provider? What recovery/contact channel exists? Owner: maintainer. Status: unresolved. Affects T06/T08.
- **Q3 — Coaching powers:** should leadership publish articles/manage film/assign reviews, or remain distinct from admins? Status: unresolved. Affects T15 and role design.
- **Q4 — Notifications:** in-app only, email, or another channel? Status: in-app is current; other channels are unselected proposals. Affects T15.
- **Q5 — Release:** target host, expected team/data size, license, public/private repository intent, and acceptable recovery time/data loss? Status: unresolved. Affects T13.

Decision record template: `D### | date | question/task | chosen option | alternatives | rationale/evidence | owner | consequences | revisit trigger`. Preserve prior decisions; supersede with a new record instead of silently rewriting history.

- **D001 | 2026-10-24 | documentation scope:** retain canonical `README.md`; add ProductSpec and this roadmap; no application changes. Rationale: current request is groundwork. Revisit when implementation is selected.
- **D002 | 2026-10-24 | architecture recommendation:** keep Flask/Jinja initially; consolidate security/business behavior before broad refactoring. This is an engineering recommendation, not a permanent technology mandate. Revisit with measured frontend/backend constraints.
- **D003 | 2026-10-24 | initial priorities:** known privacy/data-integrity defects precede features that amplify their impact. Candidate feature ranking remains subject to user evidence.

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
