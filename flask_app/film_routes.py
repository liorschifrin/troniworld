from flask import flash, jsonify, redirect, render_template, request, session, url_for

from . import app, db
from .models import Player, Game, Point, point_players
from .utils import get_current_user

@app.route('/player')
def player():
    current_user = get_current_user()
    return render_template('player.html', current_user=current_user)