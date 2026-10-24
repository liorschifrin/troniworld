# Troniworld

A team articles and game-film platform built for **Tron, the Brandeis Men's Ultimate Frisbee team**.

Built by **[Lior Schifrin](https://github.com/liorschifrin)**, with development assistance from Claude Code. Inspired by Ultiworld's team journalism, the project grew from a place for coaches to publish articles into a film-review tool designed around how ultimate players actually study games.

Troniworld connects YouTube game footage with point-by-point rosters, scoring, tactical notes, and team discussions. Players can jump to their points; coaches can attach feedback to moments in a game; administrators can organize games and understand film-room engagement.

## What you can do

- **Read and publish team articles.** Public articles, rich-text editing for admins, image uploads, threaded comments, and reply notifications.
- **Review game film.** YouTube playback, point navigation, score display, speed controls, keyboard shortcuts, and saved playback position.
- **See who played each point.** CSV roster import, offense/defense and scoring data, inline roster editing, injury substitutions, and missing-film markers.
- **Discuss specific moments.** Timestamped comments, replies, mentions, recipient controls, and notification links back to a comment.
- **Explore team data.** Personal game participation, hold/break percentages, tactical breakdowns, and game filters.
- **Track engagement.** Admin views of logins, watch time, comments, leadership notifications, and explicit watched marks.

**Current release status:** this is an existing application under active improvement, not a production-hardened starter template. Known access-control gaps affect private comments and hidden games, and shared-password login does not provide independent user identities. Use synthetic data for a new demonstration installation until the foundation work in the [roadmap](FEATUREROADMAP_workplan.md) is complete.

## Screenshots

These screenshots show an existing version; details may differ from the current checkout.

![Troniworld articles](https://github.com/user-attachments/assets/e872e6af-cd54-43e3-a83b-c5a7a3785d34)
![Game film viewer](https://github.com/user-attachments/assets/a3645b71-d9ea-442c-ae0f-a41f49b074e9)
![Team data](https://github.com/user-attachments/assets/893fa092-09ab-4144-bca3-d2b193499d10)

## Using the app

### Players and team members

1. Read articles at `/` or sign in at `/login?next=/film/games` using an account created by an administrator.
2. Open a game from **Games**, or use **My Games** if your account is linked to a player.
3. Select a point or player-sheet cell to seek to its timestamp. Points marked **NO FILM** cannot be used for video navigation.
4. Add a comment at a relevant moment, reply to a thread, or mention another user using autocomplete.
5. Use the notification bell to return to feedback. Select **Mark Watched** when you have finished reviewing a game.
6. Visit **Tron Data** to explore game and player statistics.

The recipient selector exists today, but known API/notification inconsistencies mean private comments must not yet be treated as a reliable confidentiality boundary.

Keyboard controls: `k` play/pause, `j` back 10 seconds, `l` forward 10 seconds, `m` mute, `f` fullscreen, and `<` / `>` adjust speed. The video remains hosted by YouTube; Troniworld does not upload, download, or transcode footage.

### Administrators and coaches

- Use `/admin/users` to create accounts, assign roles, and link players.
- Create a tournament at `/film/tournaments/new`, then a game at `/film/games/new`.
- Supply the YouTube video **ID** in the game form, plus opponent/date and optional tournament and final scores.
- Open a game and upload its player-sheet CSV. Set point timestamps and tactical fields in the player.
- Use **Edit Roster** for point-level participation and injury substitutions.
- Publish an article at `/new_post` and review engagement at `/film/analytics`.

Article publishing, game administration, and engagement analytics currently require the **admin** flag. Leadership is a separate flag used for comment styling, broader leadership visibility, and Everyone mentions; it does not automatically grant admin editing rights.

### Player-sheet CSV format

The importer expects UTF-8 CSV with one point per column after the first label column:

```csv
O/D,O,X,O
TRON,1,,2
Opponent,,1,
Alice,1,2,3/
Bob,1,,/2
END PLAYERS,,,
```

- Row 1: `O` means Tron starts on offense; `X` means defense.
- Rows 2–3: a nonempty cell identifies which team scored. Leave the other team's cell empty.
- Following rows: first cell is the player name; a nonempty point cell means participation. Numbers conventionally track that player's sequential point count.
- `N/` marks a player subbed off during an injury timeout; `/N` marks one subbed on.
- An optional blank row separates player sections; `END PLAYERS` terminates the player list.

Reimporting reuses matching point numbers and preserves their timestamps, but missing/invalid point columns can cause existing points and related data to be deleted. Back up data before replacements. The importer is being redesigned to validate and preview changes first.

## Local development setup

The regression harness and CI use Python 3.12. Other Python versions are not covered by a compatibility matrix. Dependencies are pinned in `requirements.txt`; there is no Node build step.

```bash
git clone https://github.com/liorschifrin/troniworld.git
cd troniworld
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

Create a local `.env` (never commit real values):

```dotenv
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URI=sqlite:///app.db
FILM_USER_PASSWORD=replace-with-a-local-demo-password
FILM_ADMIN_PASSWORD=replace-with-a-different-local-demo-password
```

Generate a session secret with `python -c 'import secrets; print(secrets.token_hex(32))'`. A relative SQLite URL stores the database under Flask's `instance/` directory. The user password is shared by regular accounts; the admin password is shared by both admin and leadership accounts. Login currently ignores individual stored password hashes.

### Initialize a brand-new local demo database

**The historical migration chain cannot currently create an empty database.** The following workaround creates the current model schema and records its corresponding migration revision. Use it only for a genuinely empty, disposable local database on this documented baseline. It is not an existing-database upgrade procedure.

```bash
source venv/bin/activate
python - <<'PY'
from sqlalchemy import inspect
from flask_migrate import stamp
from flask_app import app, db

with app.app_context():
    if inspect(db.engine).get_table_names():
        raise SystemExit("Database is not empty; refusing demo initialization.")
    db.create_all()
    stamp(revision="k6l7m8n9o0p1")
    print("Created current demo schema and recorded its migration revision.")
PY
```

Create the initial local admin without relying on public registration:

```bash
source venv/bin/activate
python - <<'PY'
import os
from werkzeug.security import generate_password_hash
from flask_app import app, db
from flask_app.models import User

with app.app_context():
    if User.query.filter_by(is_admin=True).first():
        raise SystemExit("An admin already exists; use the user-management page.")
    password = os.environ.get("FILM_ADMIN_PASSWORD")
    if not password:
        raise SystemExit("Configure FILM_ADMIN_PASSWORD first.")
    name = input("Initial admin username: ").strip().capitalize()
    if not name or User.query.filter(db.func.lower(User.username) == name.lower()).first():
        raise SystemExit("Username is empty or already exists.")
    db.session.add(User(username=name, hashed_password=generate_password_hash(password.lower()), is_admin=True))
    db.session.commit()
    print("Admin created. Sign in with the configured shared admin password.")
PY
```

### Run locally

If a server is already running in your workspace, use it instead of launching another. Otherwise, for local development:

```bash
source venv/bin/activate
flask --app app run --debug --host 127.0.0.1 --port 5001
```

Open `http://127.0.0.1:5001`. The alternate `python app.py` entry point enables debug mode on all interfaces; it is not a production deployment command.

### Existing databases

Back up the database and uploads, identify the recorded revision, and rehearse upgrades against a disposable restored copy before changing a live instance:

```bash
source venv/bin/activate
flask --app app db current
flask --app app db heads
```

After reviewing the applicable migrations, `flask --app app db upgrade` applies pending revisions. Do not use `db.create_all()` or `db stamp` to repair an unknown existing schema. The fresh-install workaround above does not validate the historical upgrade path.

## Development and verification

Read [ProductSpec.md](ProductSpec.md) for architecture, routes, data contracts, and known limitations. Read [FEATUREROADMAP_workplan.md](FEATUREROADMAP_workplan.md) for dependency-ordered work and resumable agent prompts. Follow [AGENTS.md](AGENTS.md) for repository-specific instructions.

Run the tracked regression harness from a fresh checkout (no `.env`, database bootstrap, secrets, or running server required):

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest
```

The harness overrides database and credential settings before importing the global app, disables dotenv loading, asserts an in-memory SQLite engine before schema creation/cleanup, and uses synthetic users with a fresh schema per test. Import-time directories and uploaded files are redirected to temporary storage. Never point mutation tests at the team database. Run tests in their own Python process; importing the application first is rejected.

CI runs passing gates (`python -m pytest -m 'not known_failure'`) separately from audited defects (`python -m pytest -m known_failure`). Known defects use narrow, strict expected failures tied to roadmap IDs: a fix produces an unexpected pass and requires updating its test marker; unrelated exceptions still fail. Expected failures do **not** mean the application is safe to release. See [test coverage and limitations](tests/README.md).

The first planned improvements address permissions, input validation, identity, migrations, and watch tracking before adding features that depend on them. Existing code uses Flask, SQLAlchemy, Jinja, vanilla JavaScript, the YouTube IFrame API, and CKEditor loaded from a CDN.

## GitHub publication and deployment

GitHub hosts this source repository; GitHub Pages cannot run the Python application. Deploying the live service requires a Python-capable host, a production WSGI server, HTTPS, persistent database/upload storage, environment configuration, and backup/restore procedures. A production server dependency and hosting configuration have not yet been selected in this repository.

Before publishing or deploying:

- Review tracked files and history for credentials and personal/team data. `.env`, `instance/`, and `venv/` are ignored; uploaded images under `flask_app/static/uploads/` are **not** generally ignored.
- Resolve the release-blocking security and integrity tasks in the roadmap. Debug logging currently includes submitted login forms and some comment contents.
- Configure secure cookies, session lifetime, request/upload limits, CSRF protection, and safe rich-text handling.
- Test database initialization/upgrades, backups, and recovery in staging.
- Keep database files and user uploads backed up separately from Git. Persistent storage must survive deploys.
- Verify licensing for the project, branding, media, and third-party assets. No project license file is currently included; publishing source does not automatically grant an open-source license.

## Project documentation

- [Product specification and developer onboarding](ProductSpec.md)
- [Feature roadmap and iterative work plan](FEATUREROADMAP_workplan.md)
- [Agent/repository instructions](AGENTS.md)

`FILM_AUTH_SETUP.md` is historical and describes removed routes and fields. Use this README and the product specification for current setup and authentication behavior.
