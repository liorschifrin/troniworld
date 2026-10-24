# Sequential development manager

- Updated: 2026-10-24T16:36:00Z.
- Authority: only tasks the user explicitly selects; one worker at a time; no production operations or new Flask server. Merge requires explicit user approval per PR.
- Durable root: `/Users/liorschifrin/Desktop/Desktop/code/troniworld/docs/orchestration/`. Manager owns this file; task detail: `tasks/<TASK_ID>.md`.

## Standing rules (survive resumes)

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
| codex | UNAVAILABLE_UNTIL 2026-10-24T17:10:00Z (assumed +1h; no reset time given) | Manager run hit "Subscription Sharing usage limit" on runs 2–3 (before 16:09Z). Not used since; re-probe after the retry time. |
| claudeAgent | AVAILABLE | Used for manager, T01 review round 1 (`claude-sonnet-5-5`). |

## Model-tier choice per thread

| Thread | Provider / model | Tier | Reason |
|---|---|---|---|
| Manager `30def5f5-1990-4660-9167-72520a4b71f3` | claudeAgent / `claude-sonnet-5-5` | Standard | Coordination only; moved off Codex after usage limit. |
| T01 impl `mcp:86180843-89e3-405d-b2e2-021dc69d4a70` | codex / `gpt-6-astra` | Heavy | Chosen before tiering rules existed; completed. |
| T01 review round 1 `mcp:13d9b7a0-6575-4f37-8974-58c7c8c72610` | claudeAgent / `claude-sonnet-5-5`, medium | Standard | Cross-provider vs. Codex implementer; test-harness review. Completed, idle. |

## Task status

- **T01 — DONE.** Merged to `main` as `2ed6e5b` (squash of PR #5, https://github.com/liorschifrin/troniworld/pull/5). Reviewed head `01b2ad1` (APPROVE, no blocking findings); CI trigger change `647e8da` applied at user direction without re-review; hosted "Regression tests" passed on `647e8da`. Merge approved by user 2026-10-24 ~16:20Z. Task record: `tasks/T01.md`.
- Task worktree `task-t01-regression-harness` removed (tree identical to merged main; nothing unpushed). Local branch `task/t01-regression-harness` kept.
- Roadmap T01 marked done on manager branch `orchestration/sequential-manager` (commit `afe7eaa`). **Not yet on `main`** — needs your decision: push to `main` directly or via a small PR.
- Local `main` fast-forwarded to `origin/main` `2ed6e5b`. Manager branch `orchestration/sequential-manager` has merged `main` (commit `6f558f1`).

## Current phase

- Current task: T02 (user-selected 2026-10-24) — phase IMPLEMENT. Implementer thread `mcp:62d6af13-ef43-406d-bb68-16cc0e7178d4` (claudeAgent `claude-sonnet-5-5`, medium), run `run:thread:mcp%3A62d6af13-ef43-406d-bb68-16cc0e7178d4:ordinal:1`, status preparing at launch (~16:37Z). Worktree/branch: new worktree from `origin/main` `f3a3091`, branch `task/t02-credential-logging`; path to be confirmed via t3_worktree_list.
- Base: `origin/main` `f3a3091` (PR #6 README restore landed after T01; local `main` still at `2ed6e5b` until fetched).
- Model choice: claudeAgent `claude-sonnet-5-5`, medium — Standard tier; codex UNAVAILABLE_UNTIL 17:10Z (Heavy tier codex not available). Review: fresh same-provider thread (Claude) acceptable while Codex unavailable.
- Phase before this: MERGED (T01).
- Blocking questions: how to land the roadmap/state update on `main` (see above). Product decisions Q1–Q5 remain open for later tasks.
- Next action: wait for implementer completion (t3_thread_wait once, bounded). Then confirm worktree path, head SHA, and PR; launch a fresh review thread bound to that worktree (not the implementer thread).

Phases: SELECT → IMPLEMENT → REVIEW → REPAIR → READY_TO_MERGE → MERGED; also PAUSED, BLOCKED, PAUSED_USAGE_LIMIT. Maximum three unsuccessful repair/review rounds.
