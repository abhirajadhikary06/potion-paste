from datetime import datetime, timezone
from .. import db

class SyncOperation(db.Model):
    """Tracks client-side operations for offline sync conflict detection."""
    __tablename__ = "sync_operations"

    id = db.Column(db.Integer, primary_key=True)
    op_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type = db.Column(db.String(32), nullable=False)  # snippet, comment, etc.
    entity_id = db.Column(db.String(36), nullable=False, index=True)
    operation = db.Column(db.String(16), nullable=False)  # create, update, delete
    client_version = db.Column(db.Integer)
    server_version = db.Column(db.Integer)
    payload = db.Column(db.JSON)
    status = db.Column(db.String(16), default="pending", nullable=False)  # pending, applied, conflict, rejected
    conflict_reason = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    applied_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "op_id": self.op_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "operation": self.operation,
            "client_version": self.client_version,
            "server_version": self.server_version,
            "status": self.status,
            "conflict_reason": self.conflict_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }
