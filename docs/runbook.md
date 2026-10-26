# Production release and recovery runbook (T13)

Status: **a procedure and a set of rehearsals on temporary data, not a deployment.** No host, domain, DNS, secret store or production database was configured, read or touched. Every host-specific value below is a placeholder. Nothing here claims the app is production-ready: the open decisions in section 11 (Q5) are unresolved, and individual accounts (T06) are not built.

The Flask service (this runbook) and the GitHub repository (source publication, section 10) are separate things. Publishing or changing the repository does not run, deploy or expose the service.

## 1. Shape of a deployment

A generic Flask WSGI app, one SQLite file, and a local directory of uploaded images:

```
/srv/troniworld/                 placeholder root; any layout works if the rules below hold
  releases/<release-id>/         the code tree (one directory per release; replaced on deploy)
  current -> releases/<id>       symlink the WSGI server runs from
  data/                          NOT part of any release; survives deploys
    app.db                       SQLite database (DATABASE_URI)
    uploads/                     uploaded images (UPLOAD_DIR), served at /static/uploads/<name>
  backups/<timestamp>/           app.db, uploads/, uploads.sha256.json
  env                            environment file, mode 0600, owned by the service user (never in git)
```

Rules that make data survive a deploy (the startup check can only see the running code tree, so the operator must also keep `data/` out of `releases/` and out of any other directory a deploy replaces or prunes): the database file and the upload directory are outside the code tree; a release only ever replaces `releases/` and the `current` link. The production profile (section 3) refuses to start if either lives inside the code tree.

## 2. Host and WSGI server: OPTIONS (not a decision)

The WSGI entry point is `app:app` (`app.py` imports the global `flask_app.app`). **Never run `python app.py` in production**: it starts the Flask development server with `debug=True` on `0.0.0.0`. Q5 asks which host to use; until it is answered, these are options only:

| Choice | Options | Notes |
|---|---|---|
| WSGI server | gunicorn, waitress, uWSGI, mod_wsgi | Not in `requirements.txt`; adding one is a release decision (pin it, run `pip check`). |
| Front end / TLS | reverse proxy (nginx, Caddy, Apache) terminating HTTPS, or a platform router | Session cookies are `Secure`, so the site must be served over HTTPS end to end as the browser sees it. Forward `X-Forwarded-Proto` and configure the server/proxy to trust it. |
| Host | a VPS or VM, an on-premises machine, a platform service with a persistent volume | The host must give the service a persistent local disk for `data/`. A host with an ephemeral filesystem is not suitable for SQLite plus local uploads. |
| Concurrency | one process with threads, or a few workers | SQLite allows one writer at a time and the CSV import relies on that write lock (ProductSpec T10). Keep the worker count small; load behaviour was never measured. |
| Process manager | systemd unit, supervisor, container restart policy | Must restart the service and capture stdout/stderr. |
| Static files | served by the app (default) or by the proxy | `/static/` and `/static/uploads/` are public. Responses under `/static/uploads/` carry `X-Content-Type-Options: nosniff`. A proxy that serves uploads directly must keep that header. |

Every page sets a session cookie and `Vary: Cookie`, so shared caches will not cache public pages (ProductSpec, CSRF section).

## 3. Production configuration

Set these in the service environment (the `env` file above). Values are placeholders; generate real ones on the host.

| Variable | Required | Meaning |
|---|---|---|
| `APP_ENV` | yes | `production` switches on the production profile. Any other value keeps development behaviour. |
| `SECRET_KEY` | yes | Signs session cookies and CSRF tokens. At least 32 random characters, not a placeholder. Example generator (run on the host, store the output only in the env file): `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `DATABASE_URI` | yes | `sqlite:////srv/troniworld/data/app.db` (four slashes = absolute path). Must be absolute, not in-memory, and outside the code tree. |
| `UPLOAD_DIR` | yes | Absolute directory outside the code tree, not containing it, not containing the database file, and holding nothing but uploads (everything in it is public at `/static/uploads/`; keep the environment file and backups elsewhere), for example `/srv/troniworld/data/uploads`. Created at start if missing. |
| `FILM_USER_PASSWORD`, `FILM_ADMIN_PASSWORD` | yes | The shared login passwords (known limitation until T06). Compared case-insensitively. Treat as secrets. |

What `APP_ENV=production` does (`flask_app/config.py`, tested in `tests/test_release.py`): `DEBUG` and `TESTING` off; template auto-reload off; one-hour static cache instead of none; `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY` and `SESSION_COOKIE_SAMESITE=Lax` set; HTTPS URL scheme; and **startup is refused** (`ConfigError`, process exits) when `SECRET_KEY` is missing, short or a known placeholder, when `DATABASE_URI` is missing, in-memory, relative, or inside the code tree, or when `UPLOAD_DIR` is missing, relative, inside the code tree, an ancestor of it, or a directory that contains the database file. Development (no `APP_ENV`) is unchanged, including the upload folder `flask_app/static/uploads`.

The app also calls `load_dotenv()`; on a host prefer real environment variables and do not leave a `.env` file in the code tree. Existing environment variables win over `.env`.

Not covered by this profile: HTTP security headers other than `nosniff` on uploads, rate limiting, request logging format, HSTS (set at the proxy). Flask's `PERMANENT_SESSION_LIFETIME` stays at 365 days.

## 4. Secret handling

- Secrets (`SECRET_KEY`, the two passwords) live only in the service environment or whatever secret store the owner chooses (open, section 11). Never commit them; `.env` and `instance/` are git-ignored.
- Rotating `SECRET_KEY` signs everyone out and invalidates open CSRF tokens (users reload). Rotating the shared passwords takes effect at the next login attempt; existing sessions continue.
- Log files must not receive secrets or passwords (T02 removed password and private-comment logging; `tests/test_logging_privacy.py`). Keep it that way when adding log lines.
- Back-ups contain user names, comments and private comments. Protect them like the live database (section 6).

## 5. Dependency checks

Before each release, from a clean venv with the release's `requirements.txt` (and `requirements-dev.txt` on a build machine):

```bash
python -m pip install -r requirements.txt
python -m pip check                        # must report no broken requirements
python -m pytest -m 'not known_failure'    # on the build machine
```

Dependencies are pinned. A vulnerability scan (for example `pip-audit`) was **not** run for this task and is not a gate yet (open: choose a scanner and cadence). Third-party browser dependencies are loaded from CDNs at run time (CKEditor 40.2.0, Google Fonts, the YouTube IFrame API); the site depends on their availability.

## 6. Backups

Back up while the service is running or stopped; use SQLite's online backup, not `cp`, for a live database:

```bash
set -euo pipefail; umask 077
DB_PATH=/srv/troniworld/data/app.db      # the file named in DATABASE_URI
STAMP=$(date -u +%Y%m%dT%H%M%SZ); DEST=/srv/troniworld/backups/$STAMP; mkdir -p "$(dirname "$DEST")"; mkdir "$DEST"   # fails if the stamp exists
[ -s "$DB_PATH" ]                                       # a missing source must fail, not become an empty database
sqlite3 -readonly "$DB_PATH" ".backup $DEST/app.db"
cp -a /srv/troniworld/data/uploads "$DEST/uploads"     # uploads write a temp file and rename it: copy off-peak, or from a filesystem snapshot
chmod -R go-rwx "$DEST"                                 # backups hold private comments
(cd "$DEST/uploads" && find . -type f -exec sha256sum {} + > ../uploads.sha256)   # empty file if there are no uploads
sqlite3 "$DEST/app.db" "PRAGMA integrity_check;"        # must print ok
sqlite3 "$DEST/app.db" "SELECT version_num FROM alembic_version;"   # must print the stamp of the live database
sqlite3 "$DEST/app.db" "SELECT count(*) FROM games; SELECT count(*) FROM user;"   # compare with the live counts
```

Always take one immediately before any schema upgrade (section 8). Copy backups off the host (destination, schedule, retention and who holds them are open: section 11). The recovery-time and data-loss objectives are **not defined**; the backup frequency cannot be chosen until they are.

`tests/test_release.py::test_restore_rehearsal_brings_back_the_database_and_the_uploads` rehearses this (online backup plus upload copy with checksums (a JSON manifest in the test, `sha256sum` in the commands above), destroy the original, restore into a clean directory, compare every row, integrity check, foreign-key check, Alembic stamp, upload bytes).

## 7. Restore

On a clean host or directory, with the service stopped:

```bash
set -euo pipefail; umask 077
STAMP=20261026T120000Z                                  # placeholder: the selected backup
BACKUP="/srv/troniworld/backups/$STAMP"; SERVICE_USER=troniworld    # placeholder service account
mkdir -p /srv/troniworld/data
cp "$BACKUP/app.db" /srv/troniworld/data/app.db
cp -a "$BACKUP/uploads" /srv/troniworld/data/uploads    # on an existing uploads/ this would nest uploads/uploads: move the old one aside first
[ -e "$BACKUP/uploads.sha256" ]                           # a missing manifest must stop the restore
if [ -s "$BACKUP/uploads.sha256" ]; then (cd /srv/troniworld/data/uploads && sha256sum -c "$BACKUP/uploads.sha256"); else [ -z "$(find "$BACKUP/uploads" -type f -print -quit)" ]; fi   # an empty manifest is valid only for a backup with no files
chown -R "$SERVICE_USER" /srv/troniworld/data           # the service must own data/ (SQLite creates journal files beside app.db)
chmod 700 /srv/troniworld/data; chmod 600 /srv/troniworld/data/app.db
sudo -u "$SERVICE_USER" test -w /srv/troniworld/data/app.db -a -w /srv/troniworld/data/uploads   # access check as the service user
sqlite3 -readonly /srv/troniworld/data/app.db "PRAGMA integrity_check; PRAGMA foreign_key_check;"   # ok, then nothing
flask --app app db current        # with the production environment; shows the stamp the backup was taken at
```

Then start the service and run the smoke checks (section 9). If the restored stamp is older than the code, run the upgrade procedure (section 8).

## 8. Upgrade and rollback

Upgrade (with the service stopped or in maintenance, after a section 6 backup, using the new release's code):

1. Back up (section 6; on the very first deploy use section 8.1 instead) and note `flask --app app db current` (the "before" stamp).
2. **First production deploy of this configuration only:** follow section 8.1 now, before anything below, instead of step 1's backup.
3. Unpack the new release beside the old one; install its pinned requirements in its own venv; run `pip check`.
4. `flask --app app db upgrade` with the production environment. Supported from `f65e956efdb9` or later; it is transactional on SQLite and rolls back on a foreign-key violation (T07). Do not apply `--sql` output to SQLite. A brand-new empty database uses `flask --app app bootstrap-db` instead.
5. Switch `current` to the new release and restart the service.
6. Run the smoke checks (section 9).

### 8.1 First deployment from the old layout (database in `instance/`, images in the old tree)

Existing installations keep the database under `instance/` and article images in `flask_app/static/uploads` inside the old tree, and production serves `/static/uploads/<name>` only from `UPLOAD_DIR`; until the images are copied across every stored image URL returns 404. With the service stopped, set the paths in your shell (the service environment is not inherited):

```bash
set -euo pipefail; umask 077
OLD_RELEASE=/absolute/path/to/old-release         # placeholder
OLD_DB=/absolute/path/to/old/instance/app.db      # the file the old DATABASE_URI resolved to
UPLOAD_DIR=/srv/troniworld/data/uploads; NEW_DB=/srv/troniworld/data/app.db
OLD_BACKUP=/srv/troniworld/backups/pre-migration; mkdir -p "$(dirname "$OLD_BACKUP")"; mkdir "$OLD_BACKUP"
[ -s "$OLD_DB" ]
sqlite3 -readonly "$OLD_DB" ".backup $OLD_BACKUP/app.db"                 # backup of the OLD locations first
cp -a "$OLD_RELEASE/flask_app/static/uploads" "$OLD_BACKUP/uploads"
mkdir -p "$UPLOAD_DIR"
cp "$OLD_BACKUP/app.db" "$NEW_DB"                                         # the migrated copy; the old file stays as it is
cp -a "$OLD_RELEASE"/flask_app/static/uploads/. "$UPLOAD_DIR"/
sqlite3 "$NEW_DB" "PRAGMA integrity_check;"                               # ok
(cd "$OLD_BACKUP/uploads" && find . -type f -exec sha256sum {} + > ../uploads.sha256)   # the manifest rollback path B needs
if [ -s "$OLD_BACKUP/uploads.sha256" ]; then (cd "$UPLOAD_DIR" && sha256sum -c "$OLD_BACKUP/uploads.sha256"); fi
sqlite3 -readonly "$OLD_DB" "SELECT version_num FROM alembic_version;"     # this is BEFORE_STAMP: write it down for rollback path A
SERVICE_USER=troniworld                                                    # placeholder service account
chown -R "$SERVICE_USER" /srv/troniworld/data; chmod 700 /srv/troniworld/data; chmod 600 "$NEW_DB"
sudo -u "$SERVICE_USER" test -w "$NEW_DB" -a -w "$UPLOAD_DIR"              # access check as the service user
```

The old backup in `$OLD_BACKUP` has the same layout as a section 6 backup (`app.db`, `uploads/`, `uploads.sha256`), so rollback path B can use it. Then continue at step 3 below (the new database is upgraded, not the old one). Keep the old release and database untouched until the smoke checks pass.

Rollback (decide quickly; each step is reversible until data is written under the new version):

- **A. Nothing written since the upgrade (or the loss is acceptable): previous artifact plus compatible schema.** Stop the service; from the new release run `flask --app app db downgrade "$BEFORE_STAMP"` (the stamp noted in upgrade step 1, saved as `BEFORE_STAMP=<stamp>`); point `current` at the previous release; start. Only valid while every downgrade in between is possible: a downgrade refuses (and leaves the data alone) when it would discard data, for example `m8n9o0p1q2r3` while watch-event rows exist, `l7m8n9o0p1q2` while a user is archived, `n9o0p1q2r3s4` while points are hidden by import.
- **B. Anything else: restore the snapshot.** Stop the service; move the live `data/app.db` (and `data/uploads` if you restore it) aside (`mv data/app.db data/app.db.rolled-back`, and move the SQLite sidecars `app.db-wal`, `app.db-shm` and `app.db-journal` aside too if they exist, otherwise post-snapshot state can be replayed into the restored file; copying a directory onto an existing one would nest `uploads/uploads`), then restore the pre-upgrade `app.db` (and, if uploads changed meanwhile, the uploads copy; extra newer upload files are harmless) as in section 7; point `current` at the previous release; start. Data written after the backup is lost (including comments and watch time); the size of that loss depends on the time between backup and rollback.
- After either path, check `flask --app app db current` equals the before stamp, then run the smoke checks.

Rehearsal: `tests/test_release.py::test_rollback_rehearsal_restores_the_pre_upgrade_snapshot_and_the_app_starts` builds a temporary database at the previous revision with seeded rows, snapshots it, upgrades to the head, starts the current application against the upgraded copy, then (A) downgrades a copy one revision and compares every row, and (B) restores the snapshot, compares every row, checks the integrity and stamp, starts the application against the restored copy, and upgrades it again. Limit: the rehearsal runs the *current* code against the old schema only for the upgrade direction; running the *previous* application artifact against the restored database is part of the manual checks below because the repository holds only one code version.

## 9. Smoke and permission checks

**Automated part** (`tests/test_release.py::test_smoke_login_view_game_and_admin_route_refuses_non_admin`, Flask test client with synthetic users; no server, no network): the login page loads; an anonymous visitor is redirected from a game page and from `/admin/users` to login; a member signs in through the login form with the shared password, lists games, opens a visible game, is refused `/admin/users`, and gets 404 for a hidden game; a wrong password does not sign in; an admin signs in and opens `/admin/users`. The broader permission matrix is `tests/test_permissions.py` and `tests/test_visibility.py`.

**Manual part (not automated)**: on the staging or production host after every deploy and restore, with a real browser over HTTPS:

1. `https://<host>/login` loads over HTTPS; the browser shows a valid certificate. HTTP redirects to HTTPS (proxy setting).
2. In the browser developer tools, the session cookie has `Secure`, `HttpOnly` and `SameSite=Lax`.
3. Sign in as a member (real account on the host); the games list loads; open a game; the video embed loads (needs outbound access to YouTube); play/pause works.
4. As the member, open `/admin/users`: refused (redirected with a message). Open a game marked hidden (if one exists): 404.
5. Sign in as an admin: `/admin/users` opens. Do not change data on production while testing.
6. Upload a test image in the article editor on staging; reload; it renders from `/static/uploads/...`; the file exists in `UPLOAD_DIR`, not in the release tree. Delete the test article afterwards.
7. After a restore or rollback: open a game with known comments and compare a few counts with what was recorded before.
8. After a deploy, confirm that images uploaded before the deploy still load (proof that uploads survive a release).
9. Confirm the service log shows no stack traces and contains no passwords.

None of the manual steps has been performed: there is no host.

## 10. Health, error reporting and logs

- There is **no health endpoint** in the app (adding one would be a feature change). A liveness probe can request `GET /login` and expect 200; it does not query the database. Deeper checks are open.
- Error reporting today is the process log: unhandled exceptions go to stderr via Flask's logger; the process manager should capture it and rotate it. A hosted error tracker, uptime monitor and alert destination are open decisions (section 11); none is configured.
- Disk: monitor free space on `data/` and `backups/`. Uploads are limited to 20 MB each and 25 MB per request; there is no quota.

## 11. License, ownership and publication: OPEN (Q5)

The following are recorded as **open**. None was decided in T13; the options are listed so the owner can choose.

| Open item | Options | Notes |
|---|---|---|
| Target host | VPS/VM; on-premises machine; platform with persistent disk; (not a static host: the service needs a backend) | Constrains WSGI/proxy choice (section 2). |
| Expected team and data size | owner to state (people, games, video-hours of metadata, images) | SQLite and a single host are only assumed to fit a small team; unqualified for load. |
| Recovery objectives (time to restore, acceptable data loss) | for example nightly backup vs. hourly vs. continuous replication (Litestream-style) | Sets backup frequency, off-host copy and retention. Not chosen. |
| Backup destination and retention | second disk; object storage; another machine | Backups contain private comments. |
| Secret store | environment file with 0600 permissions; the host/platform secret facility; a managed secret service | Section 4. |
| Error reporting and uptime monitoring | process log only; a hosted error tracker; an uptime pinger | Section 10. |
| Repository visibility | public; private; public later | No `LICENSE` file exists in the repository. |
| License | permissive (for example MIT or Apache-2.0); copyleft (GPL/AGPL); all rights reserved | Needed before T20 claims others may run the project. Check compatibility with dependencies (nh3 MIT, Pillow MIT-CMU) and with the CKEditor 5 v40.2.0 terms (the editor is loaded from the CKEditor CDN; its GPL/commercial licence terms and any attribution/licence key requirement for this use have not been reviewed). |
| Code and content ownership | owner to state: the maintainer, the club, contributors | Affects who may license the code and who owns articles, comments and uploaded images. |
| Media publication | keep videos as unlisted/linked YouTube embeds only; publish nothing from the film room; publish only public footage with permission | The repo holds no videos; the database holds YouTube URLs, player names, comments and stats. Publishing the repository must not include the database, `instance/`, `data/`, uploads or any `.env`. Players' names, images and private comments are personal data; consent and retention rules are not defined. |
| Domain and DNS | owner to choose | No domain is configured. |
| Number of admins/operators with host access | owner to state | Needed for access control to the host and backups. |

## 12. Pre-release checklist

- [ ] Q5 items in section 11 are decided by the owner (or explicitly accepted as unresolved for a limited trial).
- [ ] `pip check` clean; test gates green on the release commit.
- [ ] Backup taken and verified; restore rehearsed on the current data size (not just the synthetic rehearsal).
- [ ] `data/` is not under `releases/` or any directory the deploy tooling replaces or prunes.
- [ ] Section 3 environment set on the host; the service starts (it refuses to start on an unsafe config).
- [ ] Smoke checklist (section 9) done, automated part green and manual part completed on the real host.
- [ ] Rollback path chosen and previous release kept on disk.
- [ ] Deployment performed only by someone authorised by the owner.
