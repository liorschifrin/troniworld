"""Run flask_migrate.upgrade against a temp SQLite file and report the result as JSON.

Usage: migration_driver.py DATABASE MIGRATIONS_DIR INITIAL_FOREIGN_KEYS(0|1)
Run in a subprocess by tests/test_migrations.py; never imported by pytest.
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())
database, directory, initial = sys.argv[1], sys.argv[2], sys.argv[3]
os.environ.update(DATABASE_URI=f'sqlite:///{database}', SECRET_KEY='synthetic-migration-key',
                  PYTHON_DOTENV_DISABLED='1')

from flask_migrate import upgrade  # noqa: E402
from flask_app import app, db  # noqa: E402

with app.app_context():
    # Park a pooled connection with the requested pragma; the upgrade reuses it.
    with db.engine.connect() as connection:
        connection.exec_driver_sql(f'PRAGMA foreign_keys={initial}')
    error = None
    try:
        upgrade(directory=directory)
    except BaseException as exc:  # noqa: BLE001  (flask_migrate exits on failure)
        error = f'{type(exc).__name__}: {exc}'
    with db.engine.connect() as connection:
        pragma = connection.exec_driver_sql('PRAGMA foreign_keys').scalar()
        tables = [r[0] for r in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")]
print(json.dumps({'error': error, 'foreign_keys_after': pragma, 'tables': sorted(tables)}))
