"""Fresh-database bootstrap.

The Alembic history starts from a database that already held the original
tables (``user``, ``post``, ...), so it cannot build a database from nothing
(see docs/orchestration/tasks/T07.md). A new, empty database is therefore
created from the current models and stamped at the Alembic head. Existing
databases keep using ``flask db upgrade``.
"""
import os

import click
from flask_migrate import stamp
from sqlalchemy import inspect

from . import db

MIGRATIONS_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'migrations')


class BootstrapError(Exception):
    pass


def bootstrap_database(directory=MIGRATIONS_DIRECTORY):
    """Create every model table and stamp the Alembic head.

    Refuses to touch a database that already contains any table, so it cannot
    be mistaken for an upgrade of existing data. Call inside an app context.
    """
    existing = sorted(inspect(db.engine).get_table_names())
    if existing:
        raise BootstrapError(
            'Database is not empty (found: ' + ', '.join(existing[:5])
            + (', ...' if len(existing) > 5 else '')
            + '). Do not bootstrap an existing database. Check its Alembic stamp (flask db current): '
            + '"flask db upgrade" is supported only from f65e956efdb9 or later (see the README); '
            + 'older stamps need docs/orchestration/tasks/T07.md before any upgrade.'
        )
    db.create_all()
    try:
        stamp(directory=directory, revision='head')
    except BaseException:
        # The database was verified empty, so everything in it is ours: undo
        # the schema so a rerun is not refused as "not empty".
        db.drop_all()
        raise


def init_app(app):
    @app.cli.command('bootstrap-db')
    def bootstrap_db_command():
        """Create the schema in an empty database and stamp the Alembic head."""
        try:
            bootstrap_database()
        except BootstrapError as error:
            raise click.ClickException(str(error))
        click.echo('Created the schema from the current models and stamped the Alembic head.')
