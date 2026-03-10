from . import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    hashed_password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_leadership = db.Column(db.Boolean, nullable=False, default=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id', ondelete='SET NULL'), nullable=True)
    
    # Relationship
    player = db.relationship('Player', backref=db.backref('user', uselist=False), foreign_keys=[player_id])

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
    db.Column('player_id', db.Integer, db.ForeignKey('players.id', ondelete='CASCADE'), primary_key=True, index=True),
    db.Index('idx_point_players_player_id', 'player_id')
)

# Association table for Game <-> Player roster (many-to-many)
game_roster = db.Table('game_roster',
    db.Column('game_id', db.Integer, db.ForeignKey('games.id', ondelete='CASCADE'), primary_key=True),
    db.Column('player_id', db.Integer, db.ForeignKey('players.id', ondelete='CASCADE'), primary_key=True, index=True),
    db.Index('idx_game_roster_player_id', 'player_id')
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
    games = db.relationship('Game', secondary='game_roster', backref='roster')
    # user relationship defined in User model via backref

    def __repr__(self) -> str:
        return f"<Player {self.name}>"


class Game(db.Model):
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    opponent = db.Column(db.String(100), nullable=False)
    youtube_id = db.Column(db.String(20))
    game_date = db.Column(db.String(10))  # ISO format: YYYY-MM-DD
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.id', ondelete='SET NULL'), index=True)
    tournament_game_number = db.Column(db.Integer)
    final_score_tron = db.Column(db.Integer)
    final_score_opponent = db.Column(db.Integer)
    player_order_data = db.Column(db.JSON)  # Stores player order and section info: {"players": [names], "separator_index": int}
    
    # Relationships
    # roster is defined as backref in Player model (many-to-many through game_roster table)
    points = db.relationship('Point', backref='game', lazy='dynamic', cascade='all, delete-orphan')
    events = db.relationship('Event', backref='game', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='game', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return f"<Game {self.title} vs {self.opponent}>"


class Tournament(db.Model):
    __tablename__ = 'tournaments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    start_date = db.Column(db.String(10))  # ISO format: YYYY-MM-DD

    games = db.relationship('Game', backref='tournament', lazy='dynamic')

    def __repr__(self) -> str:
        return f"<Tournament {self.name}>"


class Point(db.Model):
    __tablename__ = 'points'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id', ondelete='CASCADE'), nullable=False, index=True)
    point_index = db.Column(db.Integer, nullable=False)  # 1, 2, 3...
    timestamp_start = db.Column(db.Integer)  # seconds in video (nullable)
    tron_o = db.Column(db.Boolean)  # True if Tron is on offense
    tron_point = db.Column(db.Boolean)  # True if Tron scored the point
    not_filmed = db.Column(db.Boolean, default=False, nullable=False, server_default='0')  # True if this point was not captured on video
    injury_subs = db.Column(db.JSON, nullable=True)  # {"off": [player_names], "on": [player_names]} — injury timeout subs
    pull_play = db.Column(db.String(50))
    defense_type = db.Column(db.String(50))
    offense_faced = db.Column(db.String(50))
    
    # Relationships
    events = db.relationship('Event', backref='point', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='point', lazy='dynamic', cascade='all, delete-orphan')
    
    # Ensure unique point_index per game
    __table_args__ = (
        db.UniqueConstraint('game_id', 'point_index', name='_game_point_uc'),
        db.Index('idx_points_game_id', 'game_id'),
    )

    def __repr__(self) -> str:
        return f"<Point {self.point_index} in Game {self.game_id}>"


class Event(db.Model):
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id', ondelete='CASCADE'), nullable=False, index=True)
    point_id = db.Column(db.Integer, db.ForeignKey('points.id', ondelete='CASCADE'))  # nullable for global events
    
    event_type = db.Column(db.String(20), nullable=False)  # 'Turnover', 'Goal', 'Timeout'
    team = db.Column(db.String(20))  # 'Tron', 'Opponent' (nullable for neutral events)
    timestamp = db.Column(db.Integer)  # seconds in video (nullable)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_events_game_id', 'game_id'),
    )

    def __repr__(self) -> str:
        return f"<Event {self.event_type} in Game {self.game_id}>"


class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id', ondelete='CASCADE'), nullable=False, index=True)
    point_id = db.Column(db.Integer, db.ForeignKey('points.id', ondelete='SET NULL'))  # nullable if general game comment
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id', ondelete='CASCADE'), index=True)  # self-reference for threading
    
    comment_type = db.Column(db.String(20), nullable=False)  # 'Comment', 'Question', 'Highlight', 'Event'
    author_name = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.Integer)  # seconds in video (nullable)
    content = db.Column(db.Text, nullable=False)
    private_to = db.Column(db.Text, nullable=True)  # JSON array of usernames; NULL means public
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.CheckConstraint("comment_type IN ('Comment', 'Question', 'Highlight', 'Event')", name='comment_type_check'),
        db.Index('idx_comments_game_id', 'game_id'),
        db.Index('idx_comments_parent_id', 'parent_id'),
    )

    def __repr__(self) -> str:
        return f"<Comment by {self.author_name} on Game {self.game_id}>"


# =========================
# ANALYTICS/TRACKING MODELS
# =========================

class ArticleComment(db.Model):
    __tablename__ = 'article_comments'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('article_comments.id', ondelete='CASCADE'), index=True)

    author_name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    replies = db.relationship(
        'ArticleComment',
        backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    __table_args__ = (
        db.Index('idx_article_comments_post_id', 'post_id'),
        db.Index('idx_article_comments_parent_id', 'parent_id'),
    )

    def __repr__(self) -> str:
        return f"<ArticleComment by {self.author_name} on Post {self.post_id}>"


class LoginEvent(db.Model):
    __tablename__ = 'login_events'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    login_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = db.relationship('User', backref='login_events')
    
    __table_args__ = (
        db.Index('idx_login_events_user_id', 'user_id'),
        db.Index('idx_login_events_login_time', 'login_time'),
    )

    def __repr__(self) -> str:
        return f"<LoginEvent user_id={self.user_id} at {self.login_time}>"


class VideoWatchSession(db.Model):
    __tablename__ = 'video_watch_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id', ondelete='CASCADE'), nullable=False, index=True)
    watch_duration_seconds = db.Column(db.Integer, nullable=False, default=0)  # Total seconds watched
    last_position_seconds = db.Column(db.Float, nullable=True)  # Last known playback position
    session_start = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = db.relationship('User', backref='watch_sessions')
    game = db.relationship('Game', backref='watch_sessions')
    
    __table_args__ = (
        db.Index('idx_watch_sessions_user_id', 'user_id'),
        db.Index('idx_watch_sessions_game_id', 'game_id'),
        db.Index('idx_watch_sessions_user_game', 'user_id', 'game_id'),
    )

    def __repr__(self) -> str:
        return f"<VideoWatchSession user_id={self.user_id} game_id={self.game_id} duration={self.watch_duration_seconds}s>"


class CommentNotification(db.Model):
    """Notification for a user when they are @mentioned or sent a private comment."""
    __tablename__ = 'comment_notifications'

    id = db.Column(db.Integer, primary_key=True)
    recipient_username = db.Column(db.String(100), nullable=False, index=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id', ondelete='CASCADE'), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id', ondelete='CASCADE'), nullable=False, index=True)
    # 'mention' | 'private' | 'everyone'
    notification_type = db.Column(db.String(20), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)  # analytics: when the user read it

    # Relationships
    comment = db.relationship('Comment', backref=db.backref('notifications', passive_deletes=True))
    game = db.relationship('Game', backref=db.backref('comment_notifications', passive_deletes=True))

    __table_args__ = (
        db.Index('idx_notifs_recipient', 'recipient_username'),
        db.Index('idx_notifs_recipient_unread', 'recipient_username', 'is_read'),
    )

    def __repr__(self) -> str:
        return f"<CommentNotification recipient={self.recipient_username} comment_id={self.comment_id} read={self.is_read}>"


class ArticleCommentNotification(db.Model):
    """Notification for a user when someone replies to their article comment or to a thread they're in."""
    __tablename__ = 'article_comment_notifications'

    id = db.Column(db.Integer, primary_key=True)
    recipient_username = db.Column(db.String(100), nullable=False, index=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('article_comments.id', ondelete='CASCADE'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False, index=True)
    # 'reply' | 'thread'
    notification_type = db.Column(db.String(20), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    comment = db.relationship('ArticleComment', backref=db.backref('notifications', passive_deletes=True))
    post = db.relationship('Post', backref=db.backref('article_comment_notifications', passive_deletes=True))

    __table_args__ = (
        db.Index('idx_art_notifs_recipient', 'recipient_username'),
        db.Index('idx_art_notifs_recipient_unread', 'recipient_username', 'is_read'),
    )

    def __repr__(self) -> str:
        return f"<ArticleCommentNotification recipient={self.recipient_username} comment_id={self.comment_id} read={self.is_read}>"
