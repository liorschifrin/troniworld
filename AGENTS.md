Source the virtual environment at venv/ before running flask commands

Don't run the flask server, I already have one running

If you change of the below information, or add significantly to the page, update this file accordingly.

## Project documentation (2026-10-24)

- `README.md` is the canonical GitHub overview, usage guide, and local setup reference. Keep its existing uppercase filename.
- `ProductSpec.md` documents current architecture, data contracts, routes, onboarding, and verified limitations against the reviewed baseline.
- `FEATUREROADMAP_workplan.md` tracks proposed work with stable task IDs, dependencies, acceptance criteria, decision notes, and resumable regeneration/execution prompts. Roadmap items are not implemented features.
- `FILM_AUTH_SETUP.md` is historical and superseded for current setup/authentication. Some older notes below also describe removed fields/routes or earlier behavior; confirm source and ProductSpec before acting.
- Update current-state documentation when behavior changes; record proposals and task checkpoints in the roadmap. Documentation does not imply permission to run the roadmap automatically or deploy.

## Regression harness (T01)

- Run `python -m pip install -r requirements-dev.txt` and `python -m pytest` in an isolated Python 3.12 venv; no server or real database is needed.
- `tests/conftest.py` must configure synthetic environment values before importing `flask_app`; it rejects prior imports, disables dotenv, asserts the in-memory engine before schema operations, and redirects filesystem writes to temporary storage.
- `pytest.ini` makes expected failures strict; `known_failure` cases identify roadmap defects and must not hide unrelated errors. CI runs passing gates and known defects separately. Coverage boundaries are in `tests/README.md`.

## Typed API inputs (T04, 2026-10-25)

- `flask_app/input_validation.py` provides scoped JSON errors/authentication and input validators for film/article comments, point PATCH, and player-sheet writes. These APIs return JSON 400/401/403/404; article GET stays public. Other page/report redirects are unchanged.
- Comment text has no length cap. Timestamps are finite numbers in 0–86400, or null for absent/cleared timestamps. Reply parents must be visible, same game/post, and top-level; reply-to-reply is 400. `private_to` requires a list of strings or null. Point references must belong to the URL game, and player-sheet edits accept existing `Player` names listed in `player_order_data['players']`, on the roster, or on the game's points (adds join the roster) and validate the whole batch before writing. Point labels are trimmed before the 50-character check.
- Point booleans and `in_point` are actual JSON booleans. `is_hidden` is still an HTML form checkbox. Stored legacy data is preserved; invalid timestamps are suppressed on rendering and stored strings are excluded from handler source. No migration or T09 beacon change.
- Regression gates also need Node 22 for isolated JavaScript renderer tests (no server/browser). See `tests/README.md` and `docs/orchestration/tasks/T04.md` for exact counts and baseline comparison.

## CSRF tokens (T05 slice 1, 2026-10-25)

- `flask_app/csrf.py` checks a per-session token on every routed POST/PUT/PATCH/DELETE before the view runs. JSON routes return 403 `{"error": "CSRF token missing or invalid"}`. HTML form routes (`FORM_ENDPOINTS`) return 403 with a flashed message.
- Every new write client must send the token. POST forms need `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. `fetch` writes need `headers: { 'X-CSRFToken': CSRF_TOKEN }`; both base templates define `CSRF_TOKEN`. jQuery writes in `articles/base.html` get the header from `jQuery.ajaxPrefilter`. The watch-time `sendBeacon` payload includes `csrf_token: CSRF_TOKEN`.
- `tests/test_csrf.py` pins the exact inventory (20 fetch writes, 14 POST forms, 1 beacon, 3 jQuery posts) and the list of write routes. Update both when adding a client or route. Shared test clients in `tests/conftest.py` send their session token by default.

## Active work: game_player.html

Primary file: `flask_app/templates/film_room/pages/game_player.html` (~4930 lines)

## Template layout (as of reorganization)
- `flask_app/templates/articles/` — articles section: base.html, index.html, post.html, new_post.html, edit_post.html, login_articles.html, register.html, editor.html
- `flask_app/templates/film_room/film_base.html` — film room base template
- `flask_app/templates/film_room/pages/` — user-facing film room pages: games_list, game_player, my_games, tron_data, analytics_dashboard, film_room_app, login
- `flask_app/templates/film_room/forms/` — film room DB edit forms: new_game, edit_game, new_tournament, upload_game_csv, manage_users
- `flask_app/templates/unused/` — templates with no active routes: film_login, film_setup, manage_film_users, player

### Video player
- Uses YouTube IFrame API. Key globals: `player` (YT.Player instance), `playerReady` (bool).
- Single polling interval (`controlsUpdateInterval`, 100ms) lives in `startVideoControlsUpdate()`. All per-tick work goes here: `updateVideoControls()`, `updateScoreboard()`, `syncPlaybackRateIndicator()`, `syncMuteIndicator()`, `syncPlayPauseIndicator()`.
- Video controls bar: `#videoControls` div below the video. Buttons use `.vc-btn`; speed buttons have `data-speed-group`. The `vc-always-icon` class shows icon+label on all sizes; `vc-icon-mobile` shows icon-only on mobile and text-only on desktop.
- Keyboard shortcuts: `k`=play/pause, `j`=−10s, `l`=+10s, `m`=mute, `f`=fullscreen, `<`/`>`=speed ±0.25×.
- Speed highlight: `syncPlaybackRateIndicator()` injects a dashed `.vc-speed-custom#vc-custom-rate` badge at the correct sort position when the active rate doesn't match 0.5/1/2×.

### Layout & responsive breakpoints
- Desktop: 2-column grid (`.main` + `.sidebar`, sidebar 320px). Narrows at 1300px (250px), collapses to single column at ≤1100px.
- Mobile (≤767px): `.main` becomes flex-column with explicit `order` values. Scoreboard and timestamp live in `.player-meta-bar` (shown as a flex bar above the video on mobile; `display:contents` on desktop so they remain absolute overlays). Point-info-section is ordered above the video.

### Comments
- Sidebar panel. Input box is always visible on desktop; on mobile it's hidden by default and revealed by a `+ Comment` button (`toggleCommentInput()`). Auto-hides after a successful post.
- `scrollCommentIntoView(el, opts)` — scrolls within `#commentsList` only. Pass `{ toTop: true }` to also nudge the page scroll on single-column layouts (shows 250px of the list from the bottom of the viewport).
- Comment type UI removed — `comment_type` is hardcoded to `'Comment'` everywhere.
- Author styling: own name → `.comment-author-self` (purple `#C45AB3`); leadership → `.comment-author-leadership` (blue `#4A9EDB`, ★ prefix). Both get a border-bottom.

### Private comments
- `Comment.private_to` DB column (Text, nullable) stores a JSON list of allowed usernames (e.g. `["alice","bob"]`). `null` = public.
- Server-side filtering uses `can_view_comment()` in `flask_app/visibility.py`: a comment is returned only if `private_to` is NULL, or the viewer is the author, or the viewer's username is in the list; replies also require every ancestor to be visible. Q1 option A (2026-10-25) removes the leadership exception. Admin reports apply the same author/recipient rule, and dashboard comment/tag counts match the viewing admin’s visible detail lists. Every ancestor’s game must also be visible. Leadership-group audiences are proposed only in T03a. Notifications are created and served only for comments the recipient may view. See `docs/visibility-policy.md`.
- Comment edits preserve notification IDs and read history for still-entitled recipients, create unread rows for newly targeted recipients, and remove rows for recipients who lost access. Descendant notification rows are checked against ancestor visibility on read.
- `create_comment` / `update_comment` accept `private_to` (list or null) in the request body.
- Frontend globals: `isPrivateComment` (bool), `privateToUsers` (array), `editIsPrivate`, `editPrivateToUsers`.
- UI: 🔒 lock button (`.privacy-toggle-btn`) in `.comment-controls`. When active (yellow border), a chip-input section (`.private-to-wrap`) appears. Users type a username and press Enter/comma to add a chip; click × to remove.
- Helper JS: `togglePrivacy()`, `renderPrivateChips()`, `addPrivateUser()`, `removePrivateUser()` (and `Edit` variants for the edit form).
- Rendered private comments/replies show a 🔒 badge next to the author name. If you're the author, a "visible to: you, alice, bob" line appears below the comment text (`.comment-private-recipients`).
- Edit form includes the same lock toggle + chips, pre-populated from existing `private_to` data.

### Notifications
- `CommentNotification` DB model (`comment_notifications` table). Fields: `recipient_username`, `comment_id` (FK → comments), `game_id` (FK → games), `notification_type` ('mention' | 'private' | 'everyone'), `is_read` (bool), `created_at`, `read_at` (nullable — analytics timestamp).
- `_create_notifications_for_comment(comment, game_id, author_username, author_is_leadership)` in `film_routes.py` — called in `create_comment` after `db.session.flush()`. Parses `@mentions` and `private_to` list; creates rows for each recipient.
- `@everyone` mention: only allowed for leadership users. Notifies **all `is_film_user=True` users** except the author. Reflected in the mention autocomplete dropdown (visually distinct with 📢 icon + orange styling via `.mention-dropdown-item-everyone`).
- API endpoints in `film_routes.py`:
  - `GET /film/api/notifications` → `{notifications: [...], unread_count: N}` (last 50, newest first).
  - `POST /film/api/notifications/<id>/read` → marks one notification read, records `read_at`.
  - `POST /film/api/notifications/read-all` → bulk-marks all unread for current user.
- Nav bell: lives in `.film-nav__logout` in `film_base.html`. Bell 🔔 button with orange `.notif-bell-badge` (hides when count=0). Clicking opens `.notif-dropdown` which fetches/renders notifications. Auto-polls every 60 s (`fetchNotifications()`).
- Clicking a notification calls `handleNotifClick(el)` → marks read via API → navigates to `/film/games/<game_id>?comment=<comment_id>`.
- `scrollToCommentById(id)` in `game_player.html` — called after `loadComments()` resolves if `?comment=` URL param is present. If the target is a reply, expands the parent thread first by adding parent ID to `expandedThreads` and calling `renderComments()`. Adds `.notif-highlight` CSS flash animation and calls `scrollCommentIntoView`. Reply items get `data-comment-id` attribute so they are findable after expansion.
- Mobile: `.film-nav__wrapper` uses `1fr auto auto` grid columns on ≤900px so bell stays visible between username and hamburger; only the logout link text is hidden.

### Analytics dashboard (`analytics_dashboard.html`)
- Admin-only page at `/film/analytics`.
- Table columns: User, Logins, Watch Time, Comments, Led Tags, Games Watched.
- **Comments column**: `<button class="comment-list-btn">` calls `openCommentModal(username, count)` — fetches `GET /film/api/user/<username>/comments` (admin-only), renders list of clickable `<a target="_blank">` links to `/film/games/<id>?comment=<id>`.
- **Led Tags column**: `<button class="ldr-notif">` (read/total display) calls `openTagsModal(username, total)` — fetches `GET /film/api/user/<username>/leadership-tags` (admin-only), renders list with read/unread badges and author attribution. Links open in new tab. Only includes comments from leadership users (not admin-only users).
- Two modals: `#commentModal` and `#tagsModal`, both use `.modal-overlay` / `.modal-box` structure. Backdrop click closes via `document.addEventListener('click', ...)`.
- New API endpoints in `film_routes.py`:
  - `GET /film/api/user/<username>/comments` → comments by user visible to the viewing admin (newest first), fields: id, content, timestamp, created_at_iso, game_id, is_reply, game_title, game_opponent.
  - `GET /film/api/user/<username>/leadership-tags` → notifications for user from leadership authors whose comments the viewing admin may read (excludes admin-only authors), fields: notif_id, is_read, notification_type, comment_id, content, timestamp, created_at_iso, author_name, game_id, is_reply, game_title, game_opponent.

### Article comment notifications (`routes.py` + `articles/base.html`)
- `ArticleCommentNotification` DB model (`article_comment_notifications` table). Fields: `recipient_username`, `comment_id` (FK → article_comments), `post_id` (FK → post), `notification_type` ('reply' | 'thread'), `is_read` (bool), `created_at`, `read_at` (nullable).
- `_create_article_notifs(comment, post_id, author_username)` in `routes.py` — called in `create_article_comment` after `db.session.commit()`. Only fires for replies (skips top-level). Parent author → `reply`; other users who replied in same thread → `thread`.
- API endpoints in `routes.py`:
  - `GET /api/article-notifications` → `{notifications: [...], unread_count: N}` (last 50, newest first). Each item includes: `id`, `notification_type`, `is_read`, `created_at`, `post_id`, `comment_id`, `comment_parent_id`, `comment_content` (120-char), `author_name`, `post_title`.
  - `POST /api/article-notifications/<id>/read` → marks one notification read.
  - `POST /api/article-notifications/read-all` → bulk-marks all unread for current user.
- Nav bell: lives in `articles/base.html`. 🔔 button in its own `<li class="art-notif-wrap">` before `.js-user-menu` in the desktop nav; also in mobile alt-menu. Orange `.art-notif-badge` (hides when count=0). Clicking opens `.art-notif-dropdown` which fetches/renders notifications. Auto-polls every 60s (`fetchArtNotifications()`). Both desktop and mobile badges update together via `.art-notif-badge, .art-notif-badge-mobile` selector.
- Clicking a notification (`handleArtNotifClick`) marks it + thread siblings read → navigates to `/post/<post_id>?comment=<comment_id>`.
- Migration: `g2h3i4j5k6l7` (down_revision: prior head).

### Not-filmed points
- `Point.not_filmed` DB column (Boolean, default False). Set `True` for points not captured on video.
- Server: `update_point` PATCH route accepts `not_filmed` (bool) in the request body.
- Points bar: `not-filmed` class is added to `.point-item` when `not_filmed=True`. These cards are dimmed (`opacity: 0.45`), render a `.not-filmed-badge` ("NO FILM") inside the header, and suppress `data-timestamp`/`onclick` even if a timestamp exists. The `+ Time` button is hidden.
- Admins see a `+ Time` button (`.point-timestamp-add` inside `.point-add-menu-wrap`, positioned `absolute; top:8px; right:8px` on the card). Clicking opens a mini-popup that appears **above** the card (`bottom: calc(100%+4px)`) with two options: "⏱ Set time" → `setPointTimestamp()` and "✕ No film" → `markAsNotFilmed()`. The `+ Time` button itself is `position: static` inside the wrap (the wrap handles absolute placement).
- Not-filmed points: the `.not-filmed-badge` ("NO FILM") in the header contains a hover-reveal `.not-filmed-delete` ✕ span. Clicking it calls `markAsFilmed()`, which removes the badge and inserts the `+ Time` menu back before the header. There is no separate restore button.
- Player sheet: `th` and all `td` cells for a not-filmed column receive the `not-filmed` CSS class (diagonal stripe pattern, text dimmed, pointer-events none). The `clickable` class and `onclick`/`data-timestamp` are omitted for not-filmed columns at render time.
- Migration: `h3i4j5k6l7m8` (down_revision: `g2h3i4j5k6l7`).

### Injury timeout substitutions
- `Point.injury_subs` DB column (JSON, nullable). Stores `{"off": [player_names], "on": [player_names]}` where `off` = players subbed off, `on` = players subbed on during an injury timeout. `null` = no injury sub on this point.
- Migration: `i4j5k6l7m8n9` (down_revision: `h3i4j5k6l7m8`).
- **CSV notation**: player cell value ending with `/` (e.g. `3/`) = subbed off; value starting with `/` (e.g. `/2`) = subbed on. The numeric part is the sequential point count.
- **Player sheet rendering**: subbed-off cells show `N/` in orange (`.ps-sub-off`); subbed-on cells show `/N` in teal (`.ps-sub-on`). Each `<td>` for player rows carries `data-sub-status="off|on|"`.
- **On-field indicator** (`updateCurrentPlayers`): subbed-off badges get `↓` prefix + `.player-badge-suboff` (orange); subbed-on get `↑` prefix + `.player-badge-subon` (teal). Title attribute describes the sub type on hover.
- **Edit mode cycling** (`togglePlayerSheetCell`): 4-state click cycle per cell: off → normal (✓) → sub-off (✓/) → sub-on (/✓) → off. Visual feedback via `.ps-cell-suboff` (orange) and `.ps-cell-subon` (teal) classes.
- `psChanges` now stores `{in_point: bool, sub: null|"off"|"on"}` objects instead of a plain boolean.
- `savePlayerSheetChanges` includes `sub_status` in each change object POSTed to `update_player_sheet`.
- Backend `update_player_sheet` accepts `sub_status` per change and rebuilds `point.injury_subs` accordingly.
- `pointPlayersData` JS global changed from `{idx: [name]}` to `{idx: [{name, sub}]}` (served via `player_sheet_data['point_players_js']`).

### Hidden games
- `Game.is_hidden` DB column (Boolean, default False, `NOT NULL`). When `True`, the game is invisible to all non-admin users.
- **Filtering**: `games_list`, `my_games`, and `tron_data` routes in `film_routes.py` all skip hidden games for non-admins (`[g for g in games if not g.is_hidden]`). Every game-scoped film route uses `get_visible_game_or_404()` from `flask_app/visibility.py`, so non-admins get the same 404 as for a missing game. Policy matrix: `docs/visibility-policy.md`.
- **Forms**: a "Hide this game" checkbox (`name="is_hidden"`) is present in both `new_game.html` and `edit_game.html`. In the edit form the checkbox is pre-checked when `game.is_hidden` is True.
- **Visual indicator**: on the games list (admin view only), hidden cards receive the `.game-card--hidden` class (dashed orange border, reduced opacity) and a 🚫 Hidden `.hidden-badge` in the meta row.
- Migration: `j5k6l7m8n9o0` (down_revision: `i4j5k6l7m8n9`).

### Player sheet inline editing
- Admins see a **"✎ Edit Roster"** button (`#psEditBtn`, `.ps-edit-btn`) in the player sheet toggle header. Clicking enters edit mode without affecting the DB.
- Edit mode (`enterPlayerSheetEdit()`): adds `.ps-edit-mode` class to the table, reveals the `.ps-edit-bar` save/cancel bar, hides the edit button. All player data-cells become toggleable.
- Each player row `<td>` has `data-point-id`, `data-player`, and `data-in-point` (1/0) attributes. The unified `onclick` calls `handlePsCellClick(td, event, timestamp)`—edit mode intercepts, view mode delegates to `seekToPointTimestamp`.
- Toggling (`togglePlayerSheetCell(td)`): original innerHTML is cached in `td.dataset.origContent`. Active cells show `<span class="ps-check">✓</span>` with `.ps-cell-on` styling (lime); removed cells become empty with `.ps-cell-off` styling (red tint). Re-clicking reverts to original state and removes the pending change.
- Changes are tracked in `psChanges` map (`"pointId::playerName"` → bool). `savePlayerSheetChanges()` POSTs `{changes:[{point_id, player_name, in_point}]}` to `POST /film/api/games/<game_id>/update_player_sheet`, then reloads the page on success.
- Cancel (`exitPlayerSheetEdit()`) reverts all visual changes and restores the edit button.
- Not-filmed cells remain unresponsive in edit mode (`pointer-events: none` from existing CSS).
- Backend: `update_player_sheet` in `film_routes.py` — validates every change first, requires each point in the URL game and each player to be an existing `Player` named in `player_order_data['players']`, `game.roster`, or the game's points, then appends/removes the player from `point.players` atomically (adding also appends to `game.roster`).

### Mark game as watched
- `GameWatched` DB model (`game_watched` table). Fields: `user_id` (FK → user.id, CASCADE), `game_id` (FK → games.id, CASCADE), `watched_at` (DateTime, default utcnow). `UniqueConstraint('user_id', 'game_id', name='uq_game_watched_user_game')`. One row per user/game pair = user has explicitly marked that game watched.
- **Toggle API**: `POST /film/api/games/<game_id>/toggle-watched` — if a row exists for `(current_user.id, game_id)`, deletes it (unwatch); otherwise creates it (watch). Returns `{"watched": bool, "game_id": int}`.
- **Admin data API**: `GET /film/api/user/<username>/watched-games` (admin-only) — returns `{username, watched_games: [{game_id, title, opponent, game_date, watched_at_iso}]}`, ordered newest first.
- **Game player page**: A `<button id="watchedToggleBtn" class="watched-toggle-btn">` in `.game-info-header`. Shows `✓ Watched` (green, `.is-watched`) or `○ Mark Watched` (muted). JS global `let isWatched` (initialized from Jinja `is_watched`), `const gameId`. `toggleWatched()` POSTs to toggle endpoint and updates button state in-place (no reload).
- **Games list**: `view_game()` route passes `is_watched` (bool) to the template. `games_list()` route queries all `GameWatched` rows for the current user, passes `watched_game_ids` (set of game IDs) to `games_list.html`. Cards show a green `✓ Watched` `.watched-badge` when `game.id in watched_game_ids`.
- **Analytics dashboard**: `analytics_dashboard()` route adds `watched_count` (int) per user. New 7th table column "Marked Watched" — `<button class="comment-list-btn">` calls `toggleInlineDetail(..., 'watched', count)`. Inline detail panel (`watched-detail-{id}`) lazy-fetches `GET /film/api/user/<username>/watched-games` via `_fetchWatchedDetail()`. All `colspan` values updated from 6 to 7.
- Migration: `k6l7m8n9o0p1` (down_revision: `j5k6l7m8n9o0`).
