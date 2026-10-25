from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_migrate import Migrate

from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY')

# Initialize Flask application
app = Flask(__name__)
app.secret_key = SECRET_KEY

# # Add CORS headers for API access
# @app.after_request
# def after_request(response):
#     response.headers.add('Access-Control-Allow-Origin', '*')
#     response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
#     response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
#     return response

# Development settings to prevent browser caching and enable auto-reload
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Keep users logged in for up to 1 year
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate(app, db)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')

db.init_app(app)

# SQLite ignores foreign key constraints (and therefore CASCADE deletes) by
# default. Enable them per-connection so that deleting a comment also deletes
# its notifications, replies, etc. via the ON DELETE CASCADE rules on the FKs.
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

@event.listens_for(Engine, 'connect')
def set_sqlite_pragma(dbapi_conn, connection_record):
    if isinstance(dbapi_conn, sqlite3.Connection):
        cursor = dbapi_conn.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.close()

from .models import *

from . import csrf
csrf.init_app(app)

from . import uploads
uploads.init_app(app)

from . import bootstrap
bootstrap.init_app(app)

# with app.app_context():
#     db.create_all()

from . import routes
from . import film_routes

# Add custom Jinja2 filters
import re
from html import unescape

from .sanitize import sanitize_html_markup
app.add_template_filter(sanitize_html_markup, 'sanitize_html')

@app.template_filter('strip_html')
def strip_html_filter(text):
    """Remove HTML tags and decode entities from text"""
    if not text:
        return ''
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = unescape(text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Context processor to make current_user available in all templates
@app.context_processor
def inject_current_user():
    from .routes import get_current_user
    return dict(current_user=get_current_user())
