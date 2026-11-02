from datetime import datetime, timezone
import secrets
from .. import db

def generate_share_id() -> str:
    return secrets.token_urlsafe(12)

class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    snippets = db.relationship(
        "SnippetTag", back_populates="tag", cascade="all, delete-orphan"
    )

class SnippetTag(db.Model):
    __tablename__ = "snippet_tags"

    snippet_id = db.Column(
        db.Integer, db.ForeignKey("snippets.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id = db.Column(
        db.Integer, db.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    snippet = db.relationship("Snippet", back_populates="tags")
    tag = db.relationship("Tag", back_populates="snippets")

class Snippet(db.Model):
    __tablename__ = "snippets"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    share_id = db.Column(
        db.String(24), unique=True, nullable=False, index=True, default=generate_share_id
    )
    owner_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = db.Column(db.String(255), nullable=False, default="Untitled")
    description = db.Column(db.Text)
    language = db.Column(db.String(64), nullable=False, default="plaintext")
    code = db.Column(db.Text, nullable=False, default="")
    is_private = db.Column(db.Boolean, default=True, nullable=False)
    version = db.Column(db.Integer, default=1, nullable=False)
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

    owner = db.relationship("User", back_populates="snippets")
    revisions = db.relationship(
        "SnippetRevision",
        back_populates="snippet",
        cascade="all, delete-orphan",
        order_by="SnippetRevision.version.desc()",
    )
    tags = db.relationship(
        "SnippetTag", back_populates="snippet", cascade="all, delete-orphan"
    )
    comments = db.relationship(
        "Comment", back_populates="snippet", cascade="all, delete-orphan", lazy="dynamic"
    )
    share_links = db.relationship(
        "ShareLink", back_populates="snippet", cascade="all, delete-orphan"
    )

    def to_dict(self, include_code: bool = True, include_owner: bool = True) -> dict:
        data = {
            "id": self.public_id,
            "share_id": self.share_id,
            "title": self.title,
            "description": self.description,
            "language": self.language,
            "is_private": self.is_private,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "tags": [st.tag.name for st in self.tags],
        }
        if include_code:
            data["code"] = self.code
        if include_owner and self.owner:
            data["owner"] = self.owner.to_dict()
        return data

    def create_revision(self, user_id: int | None = None) -> "SnippetRevision":
        rev = SnippetRevision(
            snippet_id=self.id,
            version=self.version,
            title=self.title,
            description=self.description,
            language=self.language,
            code=self.code,
            created_by_id=user_id or self.owner_id,
        )
        db.session.add(rev)
        return rev

class SnippetRevision(db.Model):
    __tablename__ = "snippet_revisions"

    id = db.Column(db.Integer, primary_key=True)
    snippet_id = db.Column(
        db.Integer, db.ForeignKey("snippets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    language = db.Column(db.String(64), nullable=False)
    code = db.Column(db.Text, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    snippet = db.relationship("Snippet", back_populates="revisions")
    created_by = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "language": self.language,
            "code": self.code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by.to_dict() if self.created_by else None,
        }
