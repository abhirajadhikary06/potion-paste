from datetime import datetime, timezone
from flask_login import UserMixin
from flask import current_app
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from .. import db

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def get_password_hasher() -> PasswordHasher:
    try:
        config = current_app.config
    except RuntimeError:
        return ph
    return PasswordHasher(
        time_cost=config.get("ARGON2_TIME_COST", 3),
        memory_cost=config.get("ARGON2_MEMORY_COST", 65536),
        parallelism=config.get("ARGON2_PARALLELISM", 4),
        hash_len=32,
        salt_len=16,
    )

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120))
    avatar_url = db.Column(db.String(512))
    bio = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
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
    last_login_at = db.Column(db.DateTime(timezone=True))

    snippets = db.relationship("Snippet", back_populates="owner", lazy="dynamic")
    comments = db.relationship("Comment", back_populates="author", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = get_password_hasher().hash(password)

    def check_password(self, password: str) -> bool:
        hasher = get_password_hasher()
        try:
            verified = hasher.verify(self.password_hash, password)
            if verified and hasher.check_needs_rehash(self.password_hash):
                self.set_password(password)
            return verified
        except VerificationError:
            return False

    def to_dict(self, include_email: bool = False) -> dict:
        data = {
            "id": self.public_id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_email:
            data["email"] = self.email
        return data

    def __repr__(self) -> str:
        return f"<User {self.username}>"
