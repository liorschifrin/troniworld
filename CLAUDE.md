# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Do not start the Flask server — one is already running.**

```bash
source venv/bin/activate   # always source first

python app.py              # runs on 0.0.0.0:5001 (if you do need to start it)

flask db migrate -m "message"   # after changing models.py
flask db upgrade

flask shell                # interactive DB access
```

**Required `.env` variables:**
```
SECRET_KEY=""
DATABASE_URI="sqlite:///app.db"
FILM_USER_PASSWORD=""
FILM_ADMIN_PASSWORD=""
```

## Architecture

### Two-section app
The app serves two distinct sections sharing one `User` model and session:
- **Articles** (`/`, `/post/...`, `/register`) — blog with comments
- **Film Room** (`/film/...`) — video analysis tool for an ultimate frisbee team

### Package layout (`flask_app/`)
| File | Purpose |
|---|---|
| `__init__.py` | App factory: DB, migrations, blueprint registration, SQLite pragma, Jinja filters |
| `models.py` | All SQLAlchemy models |
| `routes.py` | Articles + auth routes (registered on `app` directly) |
| `film_views.py` | Film room page-rendering routes (registered on `app` directly) |
| `film_api.py` | Film room JSON/AJAX endpoints (registered on `app` directly) |
| `admin.py` | User management routes at `/admin/users` (registered on `app` directly) |
| `film_helpers.py` | Shared `_EST` timezone + `fmt_dt_est()` helper |
| `utils.py` | `get_current_user()`, `login_required`, `admin_required`, `leadership_required` |
| `api_routes.py` | Separate REST API Blueprint at `/api/v1/` |

**Route registration pattern:** all film/admin/article routes import `from . import app` and use `@app.route` directly. Only `api_routes.py` uses a Blueprint. The `endpoint=` params on film/admin routes are harmless no-ops — bare names like `url_for('view_game')` work everywhere without change.

### Auth model
- Session-based: `user_id` stored in `session`
- `get_current_user()` returns the `User` or `None`
- `User.is_admin` → can create/edit games, manage users, access analytics
- `User.is_leadership` → can use `@Everyone` mentions; leadership comments visible to all leadership
- All film routes require `@login_required`; admin routes use `@admin_required`
- Shared passwords from env: regular users use `FILM_USER_PASSWORD`, admins use `FILM_ADMIN_PASSWORD`
- New users created via `/admin/users` or bulk-created from players at `/admin/users/create_all_players`

### Data model (film room)
- **Game** → has many **Point**s, a **Tournament**, a **roster** (many-to-many Players), and `player_order_data` (JSON storing player order + separator index for the player sheet)
- **Point** → has `tron_o` (bool), `tron_point` (bool), `timestamp_start` (seconds), `not_filmed` (bool), `injury_subs` (JSON: `{"off":[names],"on":[names]}`)
- **Comment** → threaded (self-referential `parent_id`), has `private_to` (JSON list of usernames, NULL = public), linked to a game and optionally a point
- **CommentNotification** → created by `_create_notifications_for_comment()` in `film_api.py`; types: `mention`, `private`, `everyone`, `reply`, `thread`
- **VideoWatchSession** — tracks per-user watch time and last playback position per game
- **GameWatched** — explicit per-user "I watched this" mark (unique constraint on user+game)

### Templates
- `templates/articles/` — blog section (base.html, index.html, post.html, etc.)
- `templates/film_room/film_base.html` — film room base with nav, notification bell, theater mode
- `templates/film_room/pages/` — full pages: `game_player.html`, `games_list.html`, `my_games.html`, `tron_data.html`, `analytics_dashboard.html`
- `templates/film_room/forms/` — DB edit forms: new/edit game, new tournament, upload CSV, manage users
- `templates/film_room/partials/game_player/` — the game player page split into 15 partials:
  - HTML: `_styles.html`, `_game_header.html`, `_player_sheet.html`, `_video_player.html`, `_comments_sidebar.html`
  - JS (all included inside a single `<script>` tag so they share scope): `_js_data_init.html`, `_js_mention_engine.html`, `_js_player_sheet.html`, `_js_watch_tracking.html`, `_js_video.html`, `_js_video_controls.html`, `_js_comments.html`, `_js_points.html`, `_js_scoring.html`
  - Outside script: `_js_global_dom.html` (`#pointAddMenuGlobal` div)

### CSV upload format
Player sheets are uploaded as CSV. Row 0 = O/D indicators (`O`/`X`), row 1 = TRON scores, row 2 = enemy scores, rows 3+ = player rows. An empty row between player rows sets `separator_index`. Cell value ending `/` = injury sub off; starting `/` = injury sub on. `END PLAYERS` row stops parsing.

## Detailed film room notes
`AGENTS.md` contains in-depth documentation on the game player page: video player internals, layout/breakpoints, comment system, private comments, notifications, analytics dashboard, not-filmed points, injury subs, hidden games, player sheet inline editing, and mark-watched feature. Read it before making changes to those areas.
