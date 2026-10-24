# Regression coverage

Run the README commands from the repository root with Python 3.12. Tests use Flask's test client, never the running server. Authentication fixtures place synthetic user IDs in signed sessions; they test authorization, not the shared-password login flow. Admin and leadership are separate roles.

Passing gates cover anonymous login redirects on film pages and both APIs; ordinary/leadership point-edit and nonowner-delete denial without mutation; admin point editing; main comment API author/recipient/nonrecipient visibility; hidden-game list filtering; fresh schemas/SQLite foreign keys; temporary upload storage; and configuration isolation guards.

`test_visibility.py` (T03 slice 1) covers the reachable rows of the [visibility policy matrix](../docs/visibility-policy.md): role × comment-surface visibility on both APIs (including inherited reply privacy, author-only and malformed `private_to`), hidden-game responses byte-identical to missing-game responses with no writes on every game-scoped film and `/api/v1` route, hidden-game exclusion from lists/my-games/team data/option lists, notification creation and read isolation (including stored rows from pre-T03 code, which are omitted but not deleted), anonymous redirects, and admin-report denial for non-admins. Cells marked pending Q1 assert the current behavior (main film API keeps its leadership exception; all other surfaces apply the baseline).

Strict expected failures reproduce these audit observations:

- T04: nonnumeric timestamps and cross-game parents accepted (two cases).
- T09: JSON string beacon sent as text/plain returns 500. The invariant allows a deliberate 4xx rejection or successful handling; it does not choose a future client/server contract.

Each expected failure accepts only `AuditRegression` from the specific invariant after ordinary setup/response assertions. Unexpected success fails CI. Do not broaden markers to cover arbitrary assertions or exceptions. `python -m pytest --runxfail -m known_failure` exposes the three actual failures for diagnosis and intentionally exits nonzero on the current baseline.

The former T03 strict cases now pass and live in `test_visibility.py`.

Not covered yet: T02 sensitive logging; the unresolved leadership privacy policy (Q1) and admin-report private-content rules; other T04 malformed bodies/relationships; T05 CSRF, rich HTML and upload content validation; T06 login/identity; T07 migration replay; T08 user deletion with history; T09 browser races/read-state/counts; CSV import; the audit's thirteen-page/twenty-template smoke sweep; browser/YouTube interactions, accessibility, load, deployment, or other database engines. Current-schema `create_all()` is not evidence of successful migrations. The synthetic image upload checks storage routing only, not image validity.

No application defects are fixed by this harness. Existing SQLAlchemy legacy API and naive UTC deprecation warnings remain visible. CI uses Ubuntu/Python 3.12; local clean-clone verification uses macOS/Python 3.12.
