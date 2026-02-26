from . import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    hashed_password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<User {self.username}>"

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Post {self.title}>"


# =========================
# ASSOCIATION TABLES
# =========================

# Association table for Point <-> Player link (many-to-many)
point_players = db.Table('point_players',
    db.Column('point_id', db.Integer, db.ForeignKey('points.id', ondelete='CASCADE'), primary_key=True),
    db.Column('player_id', db.Integer, db.ForeignKey('players.id', ondelete='CASCADE'), primary_key=True)
)


# =========================
# GAME TRACKING MODELS
# =========================

class Player(db.Model):
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    jersey_number = db.Column(db.Integer)
    active = db.Column(db.Boolean, default=True)
    
    # Relationships
    points = db.relationship('Point', secondary=point_players, backref='players')

    def __repr__(self) -> str:
        return f"<Player {self.name}>"


class Game(db.Model):
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    opponent = db.Column(db.String(100), nullable=False)
    youtube_id = db.Column(db.String(20))
    game_date = db.Column(db.String(10))  # ISO format: YYYY-MM-DD
    final_score_tron = db.Column(db.Integer)
    final_score_opponent = db.Column(db.Integer)
    
    # Relationships
    points = db.relationship('Point', backref='game', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return f"<Game {self.title} vs {self.opponent}>"


class Point(db.Model):
    __tablename__ = 'points'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    point_index = db.Column(db.Integer, nullable=False)  # 1, 2, 3...
    timestamp_start = db.Column(db.Integer)  # seconds in video (nullable)
    tron_o = db.Column(db.Boolean)  # True if Tron is on offense
    tron_point = db.Column(db.Boolean)  # True if Tron scored the point
    pull_play = db.Column(db.String(50))
    defense_type = db.Column(db.String(50))
    offense_faced = db.Column(db.String(50))
    
    # Ensure unique point_index per game
    __table_args__ = (
        db.UniqueConstraint('game_id', 'point_index', name='_game_point_uc'),
    )

    def __repr__(self) -> str:
        return f"<Point {self.point_index} in Game {self.game_id}>"