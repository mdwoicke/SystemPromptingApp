from app import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
import json

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

message_tags = db.Table('message_tags',
    db.Column('message_id', db.Integer, db.ForeignKey('system_message.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class SystemMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.Text, nullable=False)
    voice_style = db.Column(db.Text, nullable=False)
    persona = db.Column(JSONB, nullable=False, default=lambda: {
        'age': '',
        'occupation': '',
        'attitude': '',
        'education': '',
        'personality': '',
        'communication_style': '',
        'skills': '',
        'knowledge': '',
        'customer_relationship': '',
        'representation': '',
        'contrast': ''
    })
    rules = db.Column(JSONB, nullable=False)
    instructions = db.Column(JSONB, nullable=False)
    example_dialogue = db.Column(JSONB, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published = db.Column(db.Boolean, default=False)
    published_at = db.Column(db.DateTime, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    category = db.relationship('Category', backref=db.backref('messages', lazy=True))
    tags = db.relationship('Tag', secondary=message_tags, lazy='subquery',
        backref=db.backref('messages', lazy=True))
    # Version tracking fields
    original_id = db.Column(db.Integer, db.ForeignKey('system_message.id'), nullable=True)
    version_number = db.Column(db.Integer, default=1)
    version_note = db.Column(db.String(200))
    # Relationship to track copies
    copies = db.relationship(
        'SystemMessage',
        backref=db.backref('original', remote_side=[id]),
        foreign_keys=[original_id]
    )

    def __init__(self, **kwargs):
        # Ensure JSON data is properly serialized
        if 'persona' in kwargs and isinstance(kwargs['persona'], str):
            kwargs['persona'] = json.loads(kwargs['persona'])
        if 'rules' in kwargs and isinstance(kwargs['rules'], list):
            kwargs['rules'] = json.dumps(kwargs['rules'])
        if 'instructions' in kwargs and isinstance(kwargs['instructions'], list):
            kwargs['instructions'] = json.dumps(kwargs['instructions'])
        if 'example_dialogue' in kwargs and isinstance(kwargs['example_dialogue'], list):
            kwargs['example_dialogue'] = json.dumps(kwargs['example_dialogue'])
        super().__init__(**kwargs)

    def get_version_history(self):
        """Get the complete version history of this message"""
        if self.original_id:
            # This is a copy, start from the original
            original = SystemMessage.query.get(self.original_id)
            return original.get_version_history()
        else:
            # This is an original, get all copies
            versions = [self]
            for copy in self.copies:
                versions.append(copy)
            return sorted(versions, key=lambda x: x.version_number)