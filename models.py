from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone

db = SQLAlchemy()


def get_utc_now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'user' или 'admin'
    is_blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_utc_now)

    notes = db.relationship('Note', backref='author', lazy=True, cascade="all, delete-orphan")


class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)


class Note(db.Model):
    __tablename__ = 'notes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)  # Тема конспекта
    description = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(300), nullable=False)
    file_original_name = db.Column(db.String(300), nullable=False)

    status = db.Column(db.String(20), default='pending')
    reject_reason = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=get_utc_now)
    updated_at = db.Column(db.DateTime, nullable=True)

    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    subject = db.relationship('Subject')
    views = db.relationship('NoteView', backref='note', lazy=True, cascade="all, delete-orphan")

class NoteView(db.Model):
    __tablename__ = 'note_views'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('notes.id'), primary_key=True)
    viewed_at = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)