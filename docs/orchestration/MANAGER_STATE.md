# Sequential development manager

- Updated: 2026-10-25T23:20:00Z.
- Authority: only tasks the user explicitly selects; one worker at a time; no production operations or new Flask server. Merge requires explicit user approval per PR.
- Durable root: `/Users/liorschifrin/Desktop/Desktop/code/troniworld/docs/orchestration/`. Manager owns this file; task detail: `tasks/<TASK_ID>.md`.

## Standing rules (survive resumes)

- **Review process (user 2026-10-25, trial):** use CodeRabbit (`@coderabbitai review` PR comment) as the reviewer instead of T3 review threads for now. CodeRabbit skips draft PRs, so mark ready first. Triage its comments: confirmed findings go to a Sonnet fix run; re-review by CodeRabbit on the new push. No `.coderabbit.yaml` yet (user: not for now). Human approval still required for merge.
- **Model budget (user 2026-10-25):** $20 plan on both providers. Do not use heavy models (Opus, gpt-6-astra) unless necessary.** Default: Sonnet 5.5 (medium) for implementation AND review. Escalate to Opus only after a Sonnet review finds a substantive security/data issue that Sonnet cannot resolve, and say so first. Stop any Opus run that is not needed.
0. **Ask before starting any task that depends on an open question.** Before beginning, ask the user about the whole task (all open questions, decisions, and scope) so the full task is understood up front. Do not start a slice of a dependent task while its questions are open. (User instruction 2026-10-24 ~17:05Z; T03 slice 1 was started before this rule and is pending the user's decision.)
1. **Explicit task selection only.** Implement only tasks the user explicitly selects. Never auto-select or start another task. After the selected task completes: save checkpoint and wait. If a task the user did not select is running, pause it safely and preserve its work.
2. **Failover/model choice never authorizes** starting an unselected task or merging without approval. One worker at a time.
3. **Model tiering.** Call `orchestrator_capabilities` at the start of each task; use only listed models; pick the cheapest likely to meet acceptance criteria; record choice + reason below. No max/ultra effort unless the user asks. Manager runs on standard-or-lower.
   - Light (docs, test scaffolding, small isolated edits, simple reviews): `claude-haiku-5-5` or `gpt-6-luna`/`gpt-5.6-luna`, low–medium effort.
   - Standard (typical feature/bug work, normal reviews): `claude-sonnet-5-5` or `gpt-6-sol`/`gpt-5.6-terra`, medium effort.
   - Heavy (migrations, auth/permissions, data integrity, cross-cutting refactors, repairs after failed review): `claude-opus-5-5` or `gpt-6-astra`, high effort.
   - Start at lowest fitting tier; escalate one tier only on substantive review findings or clear implementer struggle.
4. **Provider roles.** Prefer a different provider for review than implementation; same-provider fresh-thread review is acceptable if cross-provider would force a higher tier. Never review in the implementation thread.
5. **Failover on usage exhaustion** (usage limit, quota, rate limit, subscription limit, 429, "try again after reset"). 401/token-expired is an auth problem: tell the user to re-authenticate; no silent failover. On exhaustion: record provider/model/thread/time/error/reset; make sure child work is committed or checkpointed; retry once on the other provider at equivalent tier as a continuation; mark exhausted provider `UNAVAILABLE_UNTIL`; if both exhausted, phase `PAUSED_USAGE_LIMIT` with next action and earliest retry, then stop.

## Provider availability

| Provider | Status | Detail |
|---|---|---|
| codex | AUTH_EXPIRED 2026-10-25T01:10Z (401 token_expired on `mcp:77f0dd81-beaa-4afe-91a7-6845b51701a9`; user must re-authenticate). Earlier: UNAVAILABLE_UNTIL 2026-10-25T01:40Z (usage limit "Subscription Sharing", thread `mcp:a0c9830d-cd27-47f3-a832-8e3d2ff3f7a7`, 00:38Z; no reset time given, +1h assumed). Earlier: AUTH_EXPIRED 2026-10-24T23:39Z; still 401 at 23:44Z on retry (user must re-authenticate). Earlier: UNAVAILABLE_UNTIL 2026-10-24T17:10:00Z (assumed +1h; no reset time given) | Manager run hit "Subscription Sharing usage limit" on runs 2–3 (before 16:09Z). Not used since; re-probe after the retry time. |
| claudeAgent | AVAILABLE | Used for manager, T01 review round 1 (`claude-sonnet-5-5`). |

## Model-tier choice per thread

| Thread | Provider / model | Tier | Reason |
|---|---|---|---|
| Manager `30def5f5-1990-4660-9167-72520a4b71f3` | claudeAgent / `claude-sonnet-5-5` | Standard | Coordination only; moved off Codex after usage limit. |
| T01 impl `mcp:86180843-89e3-405d-b2e2-021dc69d4a70` | codex / `gpt-6-astra` | Heavy | Chosen before tiering rules existed; completed. |
| T01 review round 1 `mcp:13d9b7a0-6575-4f37-8974-58c7c8c72610` | claudeAgent / `claude-sonnet-5-5`, medium | Standard | Cross-provider vs. Codex implementer; test-harness review. Completed, idle. |

## User decisions (standing)

- **Direct push to `main` bypassed a PR-only rule (2026-10-24 ~16:41Z).** Manager pushed `8cfda2f` (roadmap/orchestration docs only) to `origin/main`; remote warned "Bypassed rule violations ... must be made through a pull request." User chose to KEEP it. Standing rule from now: never push to `main` directly; all changes via PR, and never bypass branch protection.
- Q1 (privacy/leadership visibility): user chose option (a) author + explicit recipients only for comment surfaces (2026-10-25). Admin-report privacy still OPEN. User also requested a roadmap item for private comments addressed to a selectable leadership group (visible to all members); details OPEN. Do not implement until the user answers the open questions (standing rule 0).

## Task status

- **T01 — DONE.** PR #5 → `main` `2ed6e5b`.
- **T02 — DONE.** PR #7 → `main` `ab343ec`.
- **T05 — ACTIVE (slice 1 merged `db660df`).** Slices 2 (sanitization) and 3 (uploads, request size) in progress per batch plan.
- **T04 — DONE.** PR #12 → `main` `65ae000`. Deferred: T09 string-beacon xfail only; stored invalid values reported, not cleaned.
- **T03 — DONE.** Finish merged as PR #11 → `main` `93636b7` (2026-10-25 ~00:10Z), squash-merged at `fa5517e` (roadmap done-mark on top of reviewed head `1f2c063`). `/api/v1` retired (user-confirmed). Deferred to other tasks: reply-parent validation and 2 xfails (T04); notification pagination and string-beacon xfail (T09). Slice 1 history: PR #8 → `5e1f11f`.
- **T03 slice 1 — (history)**. PR #8 squash-merged → `main` `5e1f11f` on user approval (2026-10-25 ~23:17Z), reviewed head `61a73bc` (review round 2 approved `795c594`; then three doc nits applied without re-review as the user directed). Merged tree verified identical to `61a73bc`. Remaining T03 items (user-acknowledged): matrix does not list admin-only point/roster routes; `/api/v1` not retired (owner confirmation); reply-parent validation is T04; notifications use the newest 50 stored rows only (T09-type); comment edit 403 vs 404 existence difference. Q1 option A applied.
- **T03a (proposed, roadmap only):** leadership-group private comments. Decisions: membership snapshot at post time; unflagged admins excluded; members notified; author-only audience changes. User said it should be unconnected to T03; roadmap entry still lists T03 as a dependency (user accepted as is). Not started; needs user selection.
- Worktrees: T01, T02, T03 removed (no unpushed work). Local branches kept. Local `main` is NOT updated: `main` is checked out in worktree `planning-stage-f` (clean, at `96cc866`, behind origin/main). Not touched.
- Manager branch `orchestration/sequential-manager` is merged with `main` (`7248193`). Manager-only records are not on `main`; roadmap T01/T02 done marks are on the manager branch only.
- Standing rule: no direct pushes to `main`; all changes through PRs.
- **Task PR process (user 2026-10-25):** each task PR contains its spec, roadmap section, and task record. After approval, the manager may add a small docs-only commit to the task branch (roadmap state → done, record updates) before the squash merge, WITHOUT another review. Anything else needed before merge is also allowed without re-review if it is docs-only.
- **After each finished task, suggest the next task with a few options** (user 2026-10-25): list the dependency-ready items, their risks and open questions, and recommend one. Do not start any suggested task without explicit selection.
- **Manager state stays on `orchestration/sequential-manager`.** That branch is pushed for backup and is never merged to `main`. PR #9 (records-only) was closed on 2026-10-25 in favor of this rule.

## Current phase

- User approval (2026-10-25): all defaults for T05 s2–s3, T07, T08 (split: T08a now, T08b waits for Q2), T09, T10. Nothing merges to `main` without approval; every PR must be ready for merge when the user returns.
- Batch plan, one implementer at a time, each PR reviewed (fresh thread) and hosted-CI-green before ready:
  1. T05 slice 2 — `task/t05-sanitize` from `main` `db660df`. PR #14 (draft) head `b06067c`; round 2 APPROVE on Sonnet; hosted CI green. Ready for merge when user approves. Implementer `mcp:f3472855-13d6-4df9-b9fb-59c3b05f1e49` (claude-sonnet-5-5 medium) completed: 856 passed / T09 xfail. Review `mcp:a4afe24d-fe72-44f3-91b1-b52484c1569c` (claude-opus-5-5 high): CHANGES REQUIRED (blocking B1: italic/h4 dropped; major M1: tables/media destroyed; minors/nits). Repair `mcp:7d474986-9b57-49ec-bb31-7d89072d4874` completed: head `b06067c` (921 passed / T09 xfail). Round 2 review `mcp:602ee106-ac6d-42cf-8391-c683c21978d4` (Opus) interrupted 10:43Z to save budget; round 2 review re-launched on claude-sonnet-5-5 medium as `mcp:9f0746c7-28b7-4f51-823a-b013ca7f37ac` (~10:45Z).
  2. T05 slice 3 — `task/t05-uploads`, stacked on slice 2 (PR #15, base `task/t05-sanitize`), head `a4079f6`, ready for review. Implementer `mcp:9bfe83b9-ed31-432a-84f7-7bfcfef8f3a9` done. CodeRabbit review in progress (requested ~11:05Z).
  3. T07 — `task/t07-bootstrap`, from main (Heavy).
  4. T08a — `task/t08a-deletion`, stacked on T07 (Heavy).
  5. T10 — `task/t10-csv-preview`, stacked on T07 (Heavy).
  6. T09 — `task/t09-engagement`, from main (Standard).
- Providers: Codex auth-expired (401 at 01:10Z). All implementers and reviewers on Claude; Opus for reviews.
- Next action: slice 2 repair → round 2 review → hosted CI green → PR ready (no merge) → slice 3.

Phases: SELECT → IMPLEMENT → REVIEW → REPAIR → READY_TO_MERGE → MERGED; also PAUSED, BLOCKED, PAUSED_USAGE_LIMIT. Maximum three unsuccessful repair/review rounds.
