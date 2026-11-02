from datetime import datetime, timezone
import secrets
from .. import db

def generate_token() -> str:
    return secrets.token_urlsafe(24)

class ShareLink(db.Model):
    __tablename__ = "share_links"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(48), unique=True, nullable=False, index=True, default=generate_token)
    snippet_id = db.Column(
        db.Integer, db.ForeignKey("snippets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    can_comment = db.Column(db.Boolean, default=True, nullable=False)
    can_edit = db.Column(db.Boolean, default=False, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True))
    max_views = db.Column(db.Integer)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    snippet = db.relationship("Snippet", back_populates="share_links")
    created_by = db.relationship("User")

    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at:
            expires_at = self.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                return False
        if self.max_views is not None and self.view_count >= self.max_views:
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "token": self.token,
            "can_comment": self.can_comment,
            "can_edit": self.can_edit,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "max_views": self.max_views,
            "view_count": self.view_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
