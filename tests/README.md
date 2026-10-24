# Regression coverage

Run the README commands from the repository root with Python 3.12. Tests use Flask's test client, never the running server. Authentication fixtures place synthetic user IDs in signed sessions; they test authorization, not the shared-password login flow. Admin and leadership are separate roles.

Passing gates cover anonymous login redirects on film pages and the main film API; ordinary/leadership point-edit and nonowner-delete denial without mutation; admin point editing; main comment API author/recipient/nonrecipient visibility; hidden-game list filtering; fresh schemas/SQLite foreign keys; temporary upload storage; and configuration isolation guards.

`test_visibility.py` (T03, 137 cases) covers the reachable rows of the [visibility policy matrix](../docs/visibility-policy.md): main film comment visibility (including inherited reply privacy, author-only and malformed `private_to`), hidden-game responses byte-identical to missing-game responses without writes, hidden-game exclusion from lists/my-games/team data/option lists, notification creation and read isolation, admin report counts, and admin-only route access for anonymous, ordinary, leadership, and admin callers. It also verifies the retired `/api/v1/games` route returns 404 for anonymous and admin callers. Q1 option A means leadership/admin flags grant no extra private access. Synthetic tests cover admin author/recipient/nonrecipient and leadership-author combinations, hidden-game ancestors, depth-two notification chains, notification edit history, and unchanged admin writes/watch behavior on visible and hidden games.

Current gates (Python 3.12, synthetic in-memory SQLite): **160 passed, 3 deselected** with `-m 'not known_failure'`; **3 xfailed, 160 deselected** with `-m known_failure`, no XPASS. The pre-retirement baseline had 106 visibility cases and 130 passing tests overall. Its archived original pre-T03 `8cfda2f` and pre-repair `d43fa1d` scratch results remain in the [T03 record](../docs/orchestration/tasks/T03.md). Baseline passes intentionally preserve already-correct behavior.

Strict expected failures reproduce these audit observations:

- T04: nonnumeric timestamps and cross-game parents accepted (two cases).
- T09: JSON string beacon sent as text/plain returns 500. The invariant allows a deliberate 4xx rejection or successful handling; it does not choose a future client/server contract.

Each expected failure accepts only `AuditRegression` from the specific invariant after ordinary setup/response assertions. Unexpected success fails CI. Do not broaden markers to cover arbitrary assertions or exceptions. `python -m pytest --runxfail -m known_failure` exposes the three actual failures for diagnosis and intentionally exits nonzero on the current baseline.

The former T03 strict cases now pass and live in `test_visibility.py`.

Not covered by the visibility suite: T03a leadership-group audiences (proposal only); other T04 malformed bodies/relationships; T05 CSRF, rich HTML and upload content validation; T06 login/identity; T07 migration replay; T08 user deletion with history; T09 browser races, general read-state/count semantics and pagination (retained edit history and admin report count consistency are covered here); CSV import; the audit's thirteen-page/twenty-template smoke sweep; browser/YouTube interactions, accessibility, load, deployment, or other database engines. Current-schema `create_all()` is not evidence of successful migrations. The synthetic image upload checks storage routing only, not image validity.

No application defects are fixed by this harness. Existing SQLAlchemy legacy API and naive UTC deprecation warnings remain visible. CI uses Ubuntu/Python 3.12; local clean-clone verification uses macOS/Python 3.12.
