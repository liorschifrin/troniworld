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


# Association table for Video roster (many-to-many between Video and Player)
video_roster = db.Table('video_roster',
    db.Column('video_id', db.Integer, db.ForeignKey('video.id'), primary_key=True),
    db.Column('player_id', db.Integer, db.ForeignKey('player.id'), primary_key=True)
)

# Association table for Highlight players (many-to-many between Highlight and Player)
highlight_players = db.Table('highlight_players',
    db.Column('highlight_id', db.Integer, db.ForeignKey('highlight.id'), primary_key=True),
    db.Column('player_id', db.Integer, db.ForeignKey('player.id'), primary_key=True)
)

# Association table for Comment players (many-to-many between VideoComment and Player)
comment_players = db.Table('comment_players',
    db.Column('comment_id', db.Integer, db.ForeignKey('video_comment.id'), primary_key=True),
    db.Column('player_id', db.Integer, db.ForeignKey('player.id'), primary_key=True)
)


class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    jersey_number = db.Column(db.Integer)
    position = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Player {self.name}>"


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    youtube_video_id = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    game_date = db.Column(db.Date, nullable=False)
    is_visible = db.Column(db.Boolean, default=True, nullable=False)
    tron_win = db.Column(db.Boolean, nullable=False)
    tron_points = db.Column(db.Integer, nullable=False)
    opponent_points = db.Column(db.Integer, nullable=False)
    opponent_name = db.Column(db.String(100))
    video_length = db.Column(db.Integer)  # In seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    roster = db.relationship('Player', secondary=video_roster, backref='videos')
    highlights = db.relationship('Highlight', backref='video', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('VideoComment', backref='video', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return f"<Video {self.title}>"


class Highlight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    start_timestamp = db.Column(db.Integer, nullable=False)  # In seconds
    end_timestamp = db.Column(db.Integer)  # In seconds, nullable
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    players = db.relationship('Player', secondary=highlight_players, backref='highlights')
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<Highlight {self.title} on Video {self.video_id}>"


class VideoComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    written_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.Integer)  # Reference to video timestamp (optional)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    players = db.relationship('Player', secondary=comment_players, backref='video_comments')
    author = db.relationship('User', foreign_keys=[written_by])

    def __repr__(self) -> str:
        return f"<VideoComment by User {self.written_by} on Video {self.video_id}>"