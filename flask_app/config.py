"""Environment-driven runtime configuration (T13).

Development behaviour is unchanged. Setting ``APP_ENV=production`` switches on
the production profile: debug and template reload off, secure session cookies,
and a refusal to start unless the secret, database and upload directory are
supplied by the environment and the data lives outside the code tree.
Nothing here reads a secret store or contacts a host; values are plain
environment variables.
"""
import os
from datetime import timedelta
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

PLACEHOLDER_SECRETS = {
    'changeme', 'change-me', 'secret', 'dev', 'development', 'test', 'default',
    'your-secret-key', 'replace-me', 'synthetic-test-session-key',
}
MIN_SECRET_LENGTH = 32


class ConfigError(RuntimeError):
    """The production profile was requested with missing or unsafe settings."""


def is_production(environ=os.environ):
    return environ.get('APP_ENV', '').strip().lower() == 'production'


def default_upload_folder(app):
    return os.path.join(app.root_path, 'static', 'uploads')


def _inside(path, parent):
    return Path(os.path.realpath(path)).is_relative_to(os.path.realpath(parent))


def _database_file(uri):
    """Return the file of a SQLite URL (any driver), or None for in-memory / other engines."""
    try:
        url = make_url(uri)
    except ArgumentError:
        return None
    if (not url.drivername.startswith('sqlite') or url.database in (None, '', ':memory:')
            or url.query.get('mode') == 'memory'):
        return None
    return url.database


def apply_config(app, environ=os.environ):
    """Apply environment configuration to ``app``; raise ConfigError if production is unsafe."""
    upload_dir = environ.get('UPLOAD_DIR', '').strip()
    if upload_dir:
        app.config['UPLOAD_FOLDER'] = os.path.abspath(upload_dir)
    else:
        app.config['UPLOAD_FOLDER'] = default_upload_folder(app)
    if not is_production(environ):
        return app

    problems = []
    secret = environ.get('SECRET_KEY', '')
    if len(secret) < MIN_SECRET_LENGTH or secret.strip().lower() in PLACEHOLDER_SECRETS:
        problems.append(f'SECRET_KEY must be set in the environment to a random value of at least '
                        f'{MIN_SECRET_LENGTH} characters (not a placeholder)')
    uri = environ.get('DATABASE_URI', '').strip()
    database_file = _database_file(uri)
    if not uri:
        problems.append('DATABASE_URI must be set')
    elif uri.lower().startswith('sqlite') and database_file is None:
        problems.append('DATABASE_URI must not be an in-memory SQLite database')
    elif database_file is not None:
        # A relative path resolves against the instance folder, inside the code tree.
        if not os.path.isabs(database_file):
            problems.append('DATABASE_URI must use an absolute path (sqlite:////abs/path.db)')
        elif _inside(database_file, app.root_path) or _inside(database_file, os.path.dirname(app.root_path)):
            problems.append('the database file must live outside the code tree')
    if not upload_dir:
        problems.append('UPLOAD_DIR must be set to an absolute directory outside the code tree')
    elif not os.path.isabs(upload_dir):
        problems.append('UPLOAD_DIR must be an absolute path')
    elif _inside(upload_dir, os.path.dirname(app.root_path)):
        problems.append('UPLOAD_DIR must live outside the code tree')
    elif database_file is not None and _inside(database_file, upload_dir):
        # The upload folder is public at /static/uploads/, so it must not hold the database.
        problems.append('UPLOAD_DIR must not contain the database file')
    if problems:
        raise ConfigError('Production configuration refused: ' + '; '.join(problems))

    app.secret_key = secret
    app.config.update(
        DEBUG=False,
        TESTING=False,
        TEMPLATES_AUTO_RELOAD=False,
        SEND_FILE_MAX_AGE_DEFAULT=timedelta(hours=1),
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PREFERRED_URL_SCHEME='https',
    )
    return app
