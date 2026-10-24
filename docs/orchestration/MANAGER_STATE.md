# Sequential development manager

- Updated: 2026-10-24T16:30:00Z.
- Authority: existing roadmap scope through sequential implementation/review; only one worker active. No production operations or new Flask server. Merge requires user approval after all gates pass.
- Durable root: `/Users/liorschifrin/Desktop/Desktop/code/troniworld/docs/orchestration/` (outside worker worktrees). Manager owns this file; task detail: `tasks/T01.md`.

## Standing rules (survive resumes)

1. **Explicit task selection only.** Implement only tasks the user explicitly selects. Never auto-select or start another task. After the selected task completes: save checkpoint and wait. If a task the user did not select is running, pause it safely and preserve its work. (Overrides the earlier "select next dependency-ready task" step.)
2. **Failover/model choice never authorizes** starting an unselected task or merging without approval. One worker at a time.
3. **Model tiering.** Call `orchestrator_capabilities` at the start of each task; use only listed models; pick the cheapest likely to meet acceptance criteria; record choice + reason below. No max/ultra effort unless the user asks. Manager runs on standard-or-lower.
   - Light (docs, test scaffolding, small isolated edits, simple reviews): `claude-haiku-5-5` or `gpt-6-luna`/`gpt-5.6-luna`, low–medium effort.
   - Standard (typical feature/bug work, normal reviews): `claude-sonnet-5-5` or `gpt-6-sol`/`gpt-5.6-terra`, medium effort.
   - Heavy (migrations, auth/permissions, data integrity, cross-cutting refactors, repairs after failed review): `claude-opus-5-5` or `gpt-6-astra`, high effort.
   - Start at lowest fitting tier; escalate one tier only on substantive review findings or clear implementer struggle.
4. **Provider roles.** Prefer a different provider for review than implementation; same-provider fresh-thread review is acceptable if cross-provider would force a higher tier. Never review in the implementation thread.
5. **Failover on usage exhaustion** (usage limit, quota, rate limit, subscription limit, 429, "try again after reset"). 401/token-expired is an auth problem: tell the user to re-authenticate; no silent failover.
   a. Record provider, model, thread ID, time, error text, reset time (if given) here.
   b. Ensure child work is committed or recorded in its task checkpoint; never discard uncommitted work.
   c. Retry once on the other provider at the equivalent tier as a continuation (new delegated task with original brief, checkpoint, git state, progress); reuse same branch/worktree where possible.
   d. Mark exhausted provider `UNAVAILABLE_UNTIL <reset or +1h>`; route new work to the other provider; re-check after that time with a cheap probe.
   e. If BOTH exhausted: full checkpoint, phase `PAUSED_USAGE_LIMIT` with next action + earliest retry time, then stop. No looping/polling. Tell the user what to resume with.

## Provider availability

| Provider | Status | Detail |
|---|---|---|
| codex | UNAVAILABLE_UNTIL 2026-10-24T17:10:00Z (assumed +1h; no reset time given) | Manager run (thread `30def5f5-…`, Codex) hit "ChatGPT user has reached their Subscription Sharing usage limit" on runs 2 and 3, observed before 2026-10-24T16:09Z. Child impl thread was unaffected (completed 15:40Z). Cheap probe needed after the retry time. |
| claudeAgent | AVAILABLE | Manager now runs here (`claude-sonnet-5-5`, run 4). Last checked 2026-10-24T16:09Z via `orchestrator_capabilities`. |

## Model-tier choice per thread

| Thread | Provider / model | Tier | Reason |
|---|---|---|---|
| Manager `30def5f5-1990-4660-9167-72520a4b71f3` | claudeAgent / `claude-sonnet-5-5` (was Codex) | Standard | Coordination only; switched after Codex usage limit. |
| T01 impl `mcp:86180843-89e3-405d-b2e2-021dc69d4a70` | codex / `gpt-6-astra` | Heavy | Chosen before tiering rules existed; completed. Not re-evaluated. |
| T01 review round 1 `mcp:13d9b7a0-6575-4f37-8974-58c7c8c72610` | claudeAgent / `claude-sonnet-5-5`, effort medium | Standard | Cross-provider vs. Codex implementer; test-harness review is not heavy-tier. Launched 2026-10-24 ~16:14Z. |

## Current task

- Task/phase: T01 / READY_TO_MERGE (pending user approval). Review round 1 completed: APPROVE, zero blocking findings; reviewer idle; implementer idle.
- Threads: manager above; implementation `mcp:86180843-89e3-405d-b2e2-021dc69d4a70` (completed); review round 1: `mcp:13d9b7a0-6575-4f37-8974-58c7c8c72610` (run ordinal 1, bound to task worktree/branch, read-only, preparing at launch). Reconciled 16:09Z: T3 lists no other active workers.
- Branch `task/t01-regression-harness`; worktree `/Users/liorschifrin/.t3/worktrees/troniworld/task-t01-regression-harness` (verified clean).
- Base: main/origin/main `c5c37a332a82d34909f822d5941b46248f2adccc`; latest head (verified): `01b2ad17561d166f66a6306f8c9b51e692f46f35`.
- PR: https://github.com/liorschifrin/troniworld/pull/5 (draft/open, MERGEABLE; overall BLOCKED); registered to manager and implementer threads. Merge approval absent. Review round: 1 (APPROVE for head 01b2ad1; head moved to 647e8da by user-approved one-line trigger change, not re-reviewed; findings minor/nit only, details in `tasks/T01.md`). Hosted CI: both "Regression tests / tests" runs (push + PR) SUCCESS on head `01b2ad1`. main unchanged at c5c37a3 (compatible). At 16:30Z GitHub shows PR no longer draft, mergeStateStatus CLEAN, head 647e8da (manager did not change draft state; source not verified).
- Tests/evidence: worker checkpoints in `tasks/T01.md`; 16 pass / 7 strict xfail; hosted checks SUCCESS observed, exact-head policy pending.
- Blocking questions: none for T01. Later product decisions Q1–Q5 remain open.
- Next action: ask user for (a) merge approval for PR #5 (squash) and (b) permission to mark the draft PR ready for review; GitHub requires a review approval per branch protection, which the user must supply. Optional minor fix (push trigger limited to main) only if user wants it; any new commit invalidates review evidence. After merge: verify PR + main commit, mark T01 done in roadmap, update local main, remove worktree only if no unique work, then STOP and wait for explicit next-task selection.

Phases: SELECT → IMPLEMENT → REVIEW → REPAIR → READY_TO_MERGE → MERGED; also PAUSED, BLOCKED, PAUSED_USAGE_LIMIT. Maximum three unsuccessful repair/review rounds. Review must cover exact current PR head; never merge without approval.
