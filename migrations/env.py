import logging
import sys
from logging.config import fileConfig

from flask import current_app

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def sqlite_pragma(connection, statement):
    # Use the raw DBAPI cursor: PRAGMA foreign_keys is ignored inside a
    # transaction and must not open a SQLAlchemy transaction of its own.
    cursor = connection.connection.cursor()
    try:
        cursor.execute(statement)
        return cursor.fetchall()
    finally:
        cursor.close()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        # SQLite batch migrations rebuild a table by dropping it. The app turns
        # foreign keys ON for every connection, so dropping a parent table
        # (user, games, ...) would cascade-delete its child rows. The SQLite
        # recommendation is to disable enforcement while rebuilding, then check
        # that no violation remains. The whole upgrade runs in one explicit
        # SQLite transaction (SQLite DDL is transactional) and the check runs
        # before the commit, so a violation rolls everything back, including
        # the version stamp. (T07; see docs/orchestration/tasks/T07.md)
        sqlite = connection.dialect.name == 'sqlite'
        configure_args = dict(conf_args)
        if sqlite:
            restore_foreign_keys = sqlite_pragma(connection, 'PRAGMA foreign_keys')[0][0]
            # The pragma is ignored inside a transaction, so change it first.
            sqlite_pragma(connection, 'PRAGMA foreign_keys=OFF')
            sqlite_pragma(connection, 'BEGIN')
            configure_args['transactional_ddl'] = True
            # Keep every revision and the foreign-key check in one transaction.
            configure_args['transaction_per_migration'] = False
        try:
            context.configure(
                connection=connection,
                target_metadata=get_metadata(),
                **configure_args
            )

            with context.begin_transaction():
                context.run_migrations()
                if sqlite:
                    violations = sqlite_pragma(connection, 'PRAGMA foreign_key_check')
                    if violations:
                        raise RuntimeError(
                            'Foreign key violations (table, rowid, parent, fk): %r. '
                            'The upgrade was rolled back; the database is at its prior revision.'
                            % (violations[:10],))
        finally:
            if sqlite:
                failing = sys.exc_info()[0] is not None
                try:
                    # PRAGMA foreign_keys is ignored inside a transaction, so
                    # end any that is still open before restoring it.
                    if connection.in_transaction():
                        connection.rollback()
                    if connection.connection.in_transaction:
                        connection.connection.rollback()
                    sqlite_pragma(connection, 'PRAGMA foreign_keys=%d' % (1 if restore_foreign_keys else 0))
                except Exception:
                    # Do not replace an exception already in flight.
                    if not failing:
                        raise
                    logger.exception('Could not roll back or restore PRAGMA foreign_keys')


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
