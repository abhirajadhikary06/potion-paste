from datetime import datetime, timezone
from .. import db

class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    snippet_id = db.Column(
        db.Integer, db.ForeignKey("snippets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id = db.Column(
        db.Integer, db.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )
    body = db.Column(db.Text, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    snippet = db.relationship("Snippet", back_populates="comments")
    author = db.relationship("User", back_populates="comments")
    parent = db.relationship("Comment", remote_side=[id], backref="replies")

    def to_dict(self) -> dict:
        return {
            "id": self.public_id,
            "body": self.body if not self.is_deleted else "[deleted]",
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "author": self.author.to_dict() if self.author else None,
            "parent_id": self.parent.public_id if self.parent else None,
            "replies": [r.to_dict() for r in self.replies if not r.is_deleted],
        }
