# Troniworld — Product Specification and Developer Onboarding

## 1. Baseline and document contract

Reviewed 2026-10-24 against `main` at `a23bfb4`. This describes current implementation unless explicitly labeled **proposed**. It does not incorporate the separate `claude-rewrite` branch or untracked local test files. Recheck source after switching branches.

- [README.md](README.md): audience, usage, environment, and local setup.
- This document: current architecture, behavior, data, and engineering constraints.
- [FEATUREROADMAP_workplan.md](FEATUREROADMAP_workplan.md): proposed work, dependencies, decisions, and handoffs.
- [AGENTS.md](AGENTS.md): repository working instructions. Source `venv/` before Flask commands; do not start a second server in the existing workspace.

The source is authoritative when documentation disagrees. Update documentation alongside changes. Do not describe roadmap items as shipped features.

## 2. Product purpose and boundaries

Troniworld helps Tron players and coaches connect discussion and team statistics to specific points in game footage. It also provides a public home for team articles. Lior Schifrin built it for the Brandeis Men's Ultimate Frisbee team, with Claude Code assistance.

Primary users:

- **Public reader:** reads articles and article discussions.
- **Team member:** signs in, reviews film, comments, checks personal participation and team data.
- **Leadership member:** team-member capabilities plus leadership attribution, Everyone mentions, and special comment visibility rules.
- **Administrator:** manages users, articles, games, tournaments, roster imports, point metadata, and engagement analytics.

The product currently serves one team. It is not a multi-tenant platform, a video storage/transcoding service, or an AI coaching system. There is no model inference, agent runtime, vector database, task queue, email delivery, or scheduled background worker in the application. Agent prompts in the roadmap are development workflows, not runtime product features.

Success means players can reach relevant film quickly, coaches can communicate feedback with clear visibility, and administrators can maintain accurate rosters and game data. Numeric product targets have not been established; future feature tasks must define a measurable outcome rather than inventing historical usage metrics.

## 3. Runtime and source map

`app.py` imports the global app from `flask_app/__init__.py`. Initialization loads dotenv configuration, creates the Flask app, initializes SQLAlchemy and Flask-Migrate, registers routes, and installs Jinja helpers. The application is not currently an application factory.

`routes.py` and `film_routes.py` register directly on the global app. Python imports therefore configure the application and database engine immediately; tests must override environment variables **before importing** the package.

Core modules:

- `flask_app/__init__.py`: environment, session/caching/upload configuration, SQLite foreign-key hook, template filters, current-user context.
- `flask_app/models.py`: ORM schema and relationships.
- `flask_app/utils.py`: current user lookup and login/admin/leadership decorators.
- `flask_app/csrf.py`: per-session CSRF token and the app-wide check on every state-changing request (T05 slice 1).
- `flask_app/routes.py`: public articles, authentication, editor uploads, article comment APIs and notifications.
- `flask_app/film_routes.py`: film pages, admin operations, imports, statistics, comments, notifications, watch tracking.
- `migrations/`: Alembic history. Current documented head is `k6l7m8n9o0p1`.

Frontend:

- `templates/articles/base.html`: shared article navigation, notification UI, layout.
- `templates/articles/{index,post,new_post,edit_post,editor,login_articles,register}.html`: public reading, admin editing, authentication.
- `templates/film_room/film_base.html`: shared film layout, responsive navigation, notification polling.
- `templates/film_room/pages/`: games list, game player, personal games, team data, admin analytics, themed login.
- `templates/film_room/forms/`: new/edit game, new tournament, CSV upload, user management.
- `static/css/`: shared article/header/icon CSS; much film CSS remains inline.
- `static/images/`: branding; `static/uploads/`: publicly served article uploads.

At this baseline, the game player is roughly 5,464 lines and film routes roughly 1,966 lines. These counts identify concentration of responsibilities, not permanent interfaces. No frontend package manager/build process is required.

Local-only directories such as `venv/`, `instance/`, caches, and `.env` are environment/runtime state, not distributable source. Local `tests/` may contain ignored leftovers from another branch; `git ls-files tests` is the authority for what a fresh clone receives. Do not read or publish secrets or team database contents merely to inventory a workspace.

## 4. Data model and invariants

### Identity and articles

- `User`: unique username, stored password hash, admin/leadership booleans, optional `player_id`. Login currently compares shared environment passwords instead of the stored hash.
- `Player`: unique name, jersey number, active flag. Accounts and players are separate so coaches need not be players. The ORM exposes a one-to-one-style backref, but `User.player_id` is not uniquely constrained.
- `Post`: title, author display string, rich HTML content, creation date.
- `ArticleComment`: post, optional parent, author username string, plain content, creation date.

### Competition and film

- `Tournament`: name/start date; associated games.
- `Game`: title, opponent, YouTube ID, date, tournament/game number, optional final scores, stored player display order, hidden flag.
- `Point`: game and unique point index, starting timestamp, offense/scoring booleans, tactical labels, missing-film flag, injury-substitution JSON.
- `game_roster`: many-to-many game/player membership.
- `point_players`: many-to-many point/player participation.
- `Event`: goal/turnover/timeout-style records with game, optional point, team, timestamp. Limited active product integration today.

`player_order_data` is shaped like `{"players": ["Alice", "Bob"], "separator_index": 1}`. Injury substitutions are `{"off": ["Alice"], "on": ["Bob"]}` or null. Participation and injury status are separate: both substituted players may participate in a point.

Dates on games/tournaments are ISO-format strings, not database date types. Nullable offense/scoring fields require care: some current statistics treat falsy values as defense/not scored rather than distinguishing unknown values.

### Film discussions and engagement

- `Comment`: game, optional point and parent, author username, content, optional video timestamp, type, private recipient JSON stored as text.
- `CommentNotification`: recipient username, comment/game foreign keys, notification type, created/read timestamps.
- `ArticleCommentNotification`: equivalent article notification links; reply/thread types.
- `LoginEvent`: user and login time.
- `VideoWatchSession`: user/game, accumulated duration, last position, session start/update times; multiple visits may create multiple rows.
- `GameWatched`: explicit user/game completion mark with a unique pair constraint.

Film privacy representation: SQL null means public; JSON `[]` (or any malformed value) means author-only; a populated JSON list names recipients. Replies inherit their parent chain's audience. `flask_app/visibility.py` holds the shared game/comment policy; see [docs/visibility-policy.md](docs/visibility-policy.md) for the role × surface matrix. Q1 option A (2026-10-25) applies on every comment-reading surface and admin report: leadership and admin status grant no private access; only authors and explicit recipients may read, with every ancestor's audience and game checked. Admin report lists and dashboard comment/tag counts use the viewing admin's entitlement. Leadership-group audiences are proposed separately as T03a, not implemented.

Ownership and recipients use usernames instead of user foreign keys. Renaming/reusing usernames can break identity continuity. Foreign keys and unique association keys are valuable existing safeguards, but they do not establish same-game parent/point membership. SQLite foreign keys are explicitly enabled per connection. ORM cascade behavior must also agree with database cascades.

## 5. Route and permission inventory

### Public/articles/authentication (`routes.py`)

- `GET /`: newest articles; `GET /post/<post_id>`: article.
- `GET/POST /login`: shared login; relative `next` destination chooses article or film styling.
- `GET/POST /register`: permitted without an existing admin, otherwise admin-only through manual checks.
- `GET/POST /logout`: removes the user session. The navigation links use GET, which is not CSRF-protected (see below).
- `GET/POST /new_post`, `GET/POST /post/<id>/edit`, `POST /post/<id>/delete`: admin article administration.
- `POST /upload_image`: admin multipart upload using the `upload` field; returns `{url}`.
- `GET/POST /post/<id>/comments`: public reads, authenticated writes.
- `PATCH/DELETE /post/<id>/comments/<comment_id>`: owner editing; owner/admin deletion.
- `GET /api/article-notifications`: current user's notifications and total unread count.
- `POST /api/article-notifications/<id>/read` and `/read-all`: user-scoped read state.

### Film pages and administrative forms (`film_routes.py`)

- `GET /film/games`: authenticated game list, hides hidden games from non-admins.
- `GET /film/games/<id>`: authenticated player; hidden games return the same 404 as missing games for non-admins.
- `GET /film/my-games`: linked-player participation and own comments (hidden games and comments on them omitted for non-admins).
- `GET /film/data`: team/player/tactical statistics, optional repeated `game_ids` query values (hidden ids behave as missing for non-admins).
- `GET /film/analytics`: admin engagement dashboard.
- `GET/POST /admin/users`: admin account creation, deletion, role changes.
- `POST /admin/users/create_all_players`: admin bulk account creation.
- `GET/POST /film/tournaments/new`: admin tournament creation.
- `GET/POST /film/games/new` and `/film/games/<id>/edit`: admin game metadata.
- `GET/POST /film/games/<id>/upload_csv`: admin roster/point import.
- `POST /film/games/<id>/delete_player_sheet`: clears roster associations/display order, preserving point records and timestamps. No game-deletion route is currently registered.

### Main film JSON API (`film_routes.py`)

All require login; point and roster edits require admin. Every game-scoped route returns the missing-game 404 for hidden games to non-admins, and notifications are created and served only for comments the recipient may view:

- `GET/POST /film/api/games/<id>/comments`; `PATCH/DELETE .../comments/<comment_id>`.
- `PATCH /film/api/games/<id>/points/<point_id>`: tactical labels, timestamp, not-filmed flag.
- `POST /film/api/games/<id>/update_player_sheet`: `{changes: [{point_id, player_name, in_point, sub_status}]}`; sub status is null, `off`, or `on`.
- `POST /film/api/games/<id>/track-watch-time`: `{seconds_watched, session_id, playback_position}`; returns session ID and cumulative duration.
- `GET /film/api/games/<id>/watch-progress`: returns `{last_position}`; positions at/below 30 seconds are not offered as resume points.
- `POST /film/api/games/<id>/toggle-watched`: returns `{watched, game_id}`.
- `GET /film/api/notifications`; `POST /film/api/notifications/<id>/read` and `/read-all`.
- Admin-only `GET /film/api/user/<username>/comments`, `/leadership-tags`, `/watched-games`.

A film comment create body uses `content`, optional `timestamp`, `parent_id`, `point_id`, `private_to`, and `comment_type`. The UI uses `Comment`; the backend also accepts `Question`, `Highlight`, and `Event`. An optional legacy `author_name` string is accepted but ignored: the session determines the author. Film PATCH accepts `content`, optional `comment_type`, and optional `private_to`; article POST accepts `content` and optional `parent_id`, and article PATCH accepts only `content`. PATCH cannot reassign a parent, game/post, point, or timestamp. API shape is not currently a formally versioned compatibility guarantee.

T04 input contracts (no schema change):

- Comment, point, and player-sheet writes require a JSON object; unsupported fields, malformed JSON/media types, wrong types, and missing required values return JSON 400. Scoped errors use `{"error": "message"}`: 400 validation, 401 anonymous, 403 forbidden, 404 missing/invisible. Film comment GET also requires login with JSON 401; article comment GET remains public. Other page/analytics authentication redirects are unchanged.
- Content must be valid Unicode text and nonblank after trimming, with **no comment length cap**. Legacy film `Event` comments allow empty text. `private_to` is null (public) or a list of strings; whitespace is trimmed and empty names removed. An empty list means author-only. Omitted privacy on PATCH preserves the audience. Invalid legacy stored audiences still follow T03 fail-closed reads.
- Comment `timestamp` and point `timestamp_start` accept finite JSON numbers from **0 through 86400**, including fractions; booleans, strings, negative/nonfinite/out-of-range values are rejected. Null means no timestamp and clears a point timestamp, as the existing client requires. Omitted point fields remain unchanged.
- Reference IDs must be positive 32-bit integers (not booleans or strings); optional create references may be null. Parents must exist, belong to the same game/post, and be top-level comments. Invisible/missing film parents return 404 before relationship checks; visible wrong-game/post parents and reply-to-reply attempts return 400. Article comments have no private audience. Stored deeper replies are preserved.
- Comment point references and point PATCH URLs must identify a point in the URL's game (404 otherwise). Point tactical labels are strings or null, trimmed and then limited to 50 characters (stored trimmed). `not_filmed` and roster `in_point` require actual JSON booleans. `is_hidden` remains an HTML form checkbox; these APIs do not accept that field.
- Player-sheet `changes` must be a list of objects with `point_id`, `player_name`, and boolean `in_point`; optional `sub_status` is null, `off`, or `on`, and nonnull substitutions require `in_point: true`. Each player name must appear on the game's player sheet — in `player_order_data['players']`, on the roster, or on one of the game's points — and must already exist as a `Player` row; unknown names are 400 and no player is created. Adding a player to a point (`in_point: true`) also adds them to the game roster, as before T04. The whole batch is validated before any write; invalid/foreign references never result in a partial update. Empty batches and empty point PATCH objects remain valid no-ops.
- Rendering guards suppress invalid legacy timestamps from executable handlers without changing the stored values. Comment text remains escaped; username handlers in mention/privacy/login autocomplete, analytics, and user deletion read escaped data attributes. Article rich HTML sanitization remains T05 scope.

### Retired alternate API

The user confirmed on 2026-10-25 that the removed React client was the only consumer of `/api/v1`. Its blueprint and routes were removed; `/api/v1/games` returns 404. Use the main film routes above. See [docs/visibility-policy.md](docs/visibility-policy.md).

Authentication decorators generally redirect to HTML for unauthenticated/unauthorized requests, including JSON endpoints. Exception (T04): film API routes using `json_api` return 401 JSON `{"error": "Login required"}` for anonymous callers and 403 JSON `{"error": "Admin access required"}` for non-admins on admin routes, instead of the former 302 redirect to login/home. Some article endpoints instead return JSON 401/403. Normalize this when introducing API contracts.

CSRF (T05 slice 1): `flask_app/csrf.py` runs before every request. A POST, PUT, PATCH, or DELETE that matches a route must carry the session's token; GET/HEAD/OPTIONS and unrouted 404/405 requests are not checked. The token is a random value stored in the signed session the first time a page calls `csrf_token()`. It lasts for the session and is kept at logout. Login and register remove it before setting the user id, so the next page mints a new token and the pre-login token is denied. Clients send it as follows. HTML forms send a hidden `csrf_token` field. `fetch` and jQuery writes send an `X-CSRFToken` header: both base templates define `CSRF_TOKEN`, and `articles/base.html` adds the header to same-origin jQuery writes. The `navigator.sendBeacon` watch-time payload carries a `csrf_token` field, because beacons cannot set headers. Only `track-watch-time` reads a token from the request body. A missing, wrong, or other-session token is denied before the view runs, with no write. JSON routes return 403 `{"error": "CSRF token missing or invalid"}`. HTML form routes return 403 with the base page and a flashed reload message; the `manage_users` AJAX role toggle gets the JSON form. The check is in-house (standard library `secrets`/`hmac`), so no dependency was added. Limitations: GET `/logout` stays a link and is unprotected, so a forged request can log a user out. Pages open from before the deploy have no token and must be reloaded. Script running on the site's own pages can read the token, so this check does not protect against injected script. Because every page renders the token, anonymous page views now set a session cookie and send `Vary: Cookie`, so shared caches will not cache public pages; this matters for a public deployment. Article HTML sanitization is slice 2. Upload and request-size limits are slice 3.

## 6. Main workflows

### Login and permissions

Login finds usernames case-insensitively and compares a lowercased password to `FILM_ADMIN_PASSWORD` for admins/leadership, otherwise `FILM_USER_PASSWORD`. It records a login event and stores `user_id` in a signed Flask session. Sessions may persist for 365 days. No film-specific session or `is_film_user` field remains.

These shared credentials make impersonation possible within a password group. Leadership/admin credential sharing is particularly significant. Existing password hashes should not be mistaken for per-user authentication. Roles govern requests after the selected identity has been established.

### Importing rosters

CSV parsing reads all UTF-8 rows, interprets O/X and scoring columns, collects player rows and section order, reuses points by index, rebuilds associations and injury status, creates/links users for newly created players when configured, removes stale points, then commits. Exceptions roll back, but semantically invalid columns can be skipped and then treated as deletions. See the README example. A future importer needs parse/validate/preview/apply separation.

### Watching a game

Flask supplies game/point/roster data through Jinja, including JSON initialization. YouTube's IFrame API supplies playback. A shared 100 ms controls interval updates UI and related playback state. Point timestamps drive seeking, scoring, active players, and active comments. Missing-film points suppress video seeking. Injury substitutions display distinct on/off styles.

Watch tracking accumulates playback time and posts increments around ten seconds, also trying to flush on pause/unload. Resume position is separate from the explicit watched toggle. Current async request races and beacon media type issues mean measured engagement is approximate and can be wrong.

### Comments and notifications

Comment bodies use mention tokens such as `@[Alice]`; Everyone is `@[Everyone]`. The main create endpoint flushes the comment, creates notification rows, then commits. Notification priority is private > everyone > mention > reply > thread. Film comment edits preserve notification identity and read timestamps for recipients who remain entitled, add newly targeted recipients as unread, and delete rows for recipients who lost access; descendant rows are filtered on read if an ancestor changes. See the visibility policy for details. Navigation polls approximately every 60 seconds and links to `?comment=<id>`; the player expands the target reply thread and scrolls it into view.

Editing a film comment deletes and recreates notification rows, resetting read history. Article comment creation commits the comment before separately creating notifications, so those operations are not atomic. Thread depth and cross-parent association checks need improvement.

### Statistics

Hold percentage = Tron scores on offense / offense points. Break percentage = Tron scores on defense / defense points. Personal statistics use player membership; team data supports selected games. Final-score win/loss counts are based on game metadata, which can diverge from point totals. Engagement metrics measure logins, client-reported watch time, comments, notification reads, and explicit watched marks; they are not proof of attention or comprehension.

## 7. Environment, storage, and operations

Required settings: `SECRET_KEY`, `DATABASE_URI`, `FILM_USER_PASSWORD`, `FILM_ADMIN_PASSWORD`. `.env` is loaded at import time; preexisting environment variables take precedence. Do not log their values.

SQLite is the demonstrated setup. SQLAlchemy supports other engines, but drivers, migrations, and behavior on another database have not been qualified. Files in `instance/` and uploaded images require separate backup/persistence. Uploads currently live under public static assets; extension filtering and secure filenames exist, but robust content checks and size limits do not.

External browser services: YouTube embeds, CKEditor CDN, and Google Fonts. Playback depends on video availability/embedding permissions and browser policies. No YouTube Data API key is required by the current player integration.

Fresh migration replay fails because the first revision assumes `user` already exists. README documents a guarded disposable-demo bootstrap; production requires the roadmap's migration work. Development settings disable normal static caching and enable template reload. Production hosting, WSGI server, monitoring, secure cookie policy, backup schedule, and restoration objectives remain to be specified.

## 8. Verified gaps and evidence boundaries

The 2026-10-24 audit used synthetic records and in-memory SQLite with Flask's test client, not the running server or team database. Observed:

- Nonrecipient private content returned from the former alternate API game/detail comments (fixed by T03 slice 1; API retired in the T03 finish checkpoint).
- Hidden game player returned 200 to a regular user (fixed by T03 slice 1).
- Private reply content appeared in a nonrecipient parent's notifications (fixed by T03 slice 1).
- Leadership nonrecipients and admin reports had separate private-content exceptions (removed by T03 round 1 under Q1 option A); admin comment/tag counts now match the viewing admin’s detail lists.
- Cross-game parent references and nonnumeric timestamps were accepted (fixed for new writes by T04; existing data is not cleaned up).
- JSON text sent with a string-beacon media type failed with HTTP 500.
- User deletion with login history raised a non-null foreign-key integrity error.
- Migration replay on an empty database failed with `no such table: user`.
- Thirteen major page reads returned 200; twenty HTML templates compiled.

Source inspection also found login-form/password logging, private comment logging, unsafe timestamp interpolation into inline JavaScript, no application-level CSRF protection (T05 slice 1 adds a per-session token check), unsanitized article HTML rendered with `safe`, inconsistent visibility rules, unbounded client watch increments, query-per-user/comment patterns, and no tracked CI/tests on the original audit baseline. Browser execution of the injection path, real YouTube controls, deployment security, dependency vulnerability scanning, accessibility, and load behavior were not tested. Temporary diagnostic scripts were not committed. T01 now supplies a tracked pytest harness and secret-free CI using Python 3.12, synthetic users, fresh in-memory schemas, pre-import environment overrides, and temporary filesystem storage. The global application architecture is unchanged. Passing permission/isolation/visibility/input/handler checks and the single strict T09 beacon expected failure are separated in CI; T04 converts its two original defects to ordinary passing regressions. Node 22 runs isolated JavaScript rendering functions for handler tests; no browser/server is started; see [tests/README.md](tests/README.md) for the precise coverage boundary. Migration replay, deletion integrity, and browser behavior remain outside this initial suite.

Release priorities and acceptance criteria live in the roadmap. Do not silently reinterpret these observations as fixes already made.

## 9. Engineering approach and onboarding checklist

Preserve Flask/Jinja unless evidence supports a larger change. Extract domain services and permission policies before adding parallel API implementations. Split the large player into focused templates/static modules incrementally, preserving event ordering and global dependencies. Prefer durable relational IDs for identity; add migrations and compatibility handling for existing data.

For a new contributor:

1. Read repository instructions and inspect branch, status, tracked tests, and migration head.
2. Follow README local setup with synthetic data; never run destructive tests on the team database.
3. Trace one vertical feature from template → route → model → response/render.
4. Select one ready roadmap task; inspect only its source/dependencies after the initial map.
5. Add behavioral regression tests for consequential changes, including denied access and malformed inputs.
6. Exercise affected UI and responsive layouts when changing browser behavior.
7. Record actual commands/results, update changed contracts, and leave a precise checkpoint.

No agent should infer that writing these documents authorizes automatic feature implementation, external publication, or deployment. Future execution follows the task scope selected by the maintainer.
