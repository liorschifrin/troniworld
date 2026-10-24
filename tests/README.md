# Regression coverage

Run the README commands from the repository root with Python 3.12. Tests use Flask's test client, never the running server. Authentication fixtures place synthetic user IDs in signed sessions; they test authorization, not the shared-password login flow. Admin and leadership are separate roles.

Passing gates cover anonymous login redirects on film pages and both APIs; ordinary/leadership point-edit and nonowner-delete denial without mutation; admin point editing; main comment API author/recipient/nonrecipient visibility; hidden-game list filtering; fresh schemas/SQLite foreign keys; temporary upload storage; and configuration isolation guards.

Strict expected failures reproduce these audit observations:

- T03: private comments in alternate API game detail and comments (two cases).
- T03: direct hidden-game player access by an ordinary user.
- T03: private reply notification exposed to a nonrecipient parent author.
- T04: nonnumeric timestamps and cross-game parents accepted (two cases).
- T09: JSON string beacon sent as text/plain returns 500. The invariant allows a deliberate 4xx rejection or successful handling; it does not choose a future client/server contract.

Each expected failure accepts only `AuditRegression` from the specific invariant after ordinary setup/response assertions. Unexpected success fails CI. Do not broaden markers to cover arbitrary assertions or exceptions. `python -m pytest --runxfail -m known_failure` exposes the seven actual failures for diagnosis and intentionally exits nonzero on the current baseline.

Not covered yet: T02 sensitive logging; the full T03 role/serializer matrix and unresolved leadership privacy policy; other T04 malformed bodies/relationships; T05 CSRF, rich HTML and upload content validation; T06 login/identity; T07 migration replay; T08 user deletion with history; T09 browser races/read-state/counts; CSV import; the audit's thirteen-page/twenty-template smoke sweep; browser/YouTube interactions, accessibility, load, deployment, or other database engines. Current-schema `create_all()` is not evidence of successful migrations. The synthetic image upload checks storage routing only, not image validity.

No application defects are fixed by this harness. Existing SQLAlchemy legacy API and naive UTC deprecation warnings remain visible. CI uses Ubuntu/Python 3.12; local clean-clone verification uses macOS/Python 3.12.
