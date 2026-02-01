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
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['ALLOWED_IMAGE_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate(app, db)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')

db.init_app(app)

from .models import *

with app.app_context():
    db.create_all()

from . import routes

# Context processor to make current_user available in all templates
@app.context_processor
def inject_current_user():
    from .routes import get_current_user
    return dict(current_user=get_current_user())