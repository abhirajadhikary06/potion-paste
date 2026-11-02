from flask import request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timezone
from uuid import uuid4
from .. import db
from ..models import SyncOperation, Snippet
from .snippets import ALLOWED_LANGUAGES, clean_text
from . import api_bp

@api_bp.route("/sync/push", methods=["POST"])
@login_required
def push_operations():
    """Client pushes offline operations. Server applies or reports conflicts."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid_json", "message": "A JSON object is required"}), 400
    ops = data.get("operations")
    if not isinstance(ops, list) or len(ops) > 100:
        return jsonify({"error": "invalid_operations", "message": "Send between 0 and 100 operations"}), 400
    results = []

    for op in ops:
        if not isinstance(op, dict):
            return jsonify({"error": "invalid_operation"}), 400
        op_id = op.get("op_id") or str(uuid4())
        entity_type = op.get("entity_type")
        entity_id = op.get("entity_id")
        operation = op.get("operation")
        client_version = op.get("client_version")
        payload = op.get("payload", {})
        if (
            not isinstance(op_id, str) or len(op_id) > 64
            or not isinstance(entity_type, str) or len(entity_type) > 32
            or not isinstance(operation, str) or len(operation) > 16
            or not isinstance(entity_id, str) or not entity_id or len(entity_id) > 36
            or not isinstance(payload, dict)
            or (client_version is not None and (type(client_version) is not int or client_version < 0))
        ):
            return jsonify({"error": "invalid_operation"}), 400

        existing = SyncOperation.query.filter_by(op_id=op_id, user_id=current_user.id).first()
        if existing:
            results.append(existing.to_dict())
            continue

        # Operation IDs are globally unique. Never disclose another user's record on collision.
        if SyncOperation.query.filter_by(op_id=op_id).first():
            results.append({"op_id": op_id, "status": "rejected", "conflict_reason": "Operation ID already in use"})
            continue

        record = SyncOperation(
            op_id=op_id,
            user_id=current_user.id,
            entity_type=entity_type,
            entity_id=entity_id,
            operation=operation,
            client_version=client_version,
            payload=payload,
            status="pending",
        )
        db.session.add(record)

        # Simple conflict detection for snippets
        if entity_type == "snippet" and operation in ("update", "delete"):
            snippet = Snippet.query.filter_by(public_id=entity_id, owner_id=current_user.id).first()
            if not snippet:
                record.status = "rejected"
                record.conflict_reason = "Snippet not found or not owned"
            elif client_version is None or snippet.version != client_version:
                record.status = "conflict"
                record.server_version = snippet.version
                record.conflict_reason = (
                    f"Client version {client_version} does not match server version {snippet.version}"
                )
            else:
                # Apply update
                if operation == "update":
                    string_fields = ("title", "description", "language", "code")
                    valid_fields = all(key not in payload or isinstance(payload[key], str) for key in string_fields)
                    valid_fields = valid_fields and ("is_private" not in payload or isinstance(payload["is_private"], bool))
                    valid_fields = valid_fields and len(payload.get("code", "")) <= 500_000
                    valid_fields = valid_fields and (
                        "language" not in payload or payload["language"] in ALLOWED_LANGUAGES
                    )
                    if not valid_fields:
                        record.status = "rejected"
                        record.conflict_reason = "Invalid snippet payload"
                    else:
                        if "title" in payload:
                            snippet.title = clean_text(payload["title"], 255) or "Untitled"
                        if "code" in payload:
                            snippet.code = payload["code"]
                        if "language" in payload:
                            snippet.language = payload["language"][:64] or "plaintext"
                        if "description" in payload:
                            snippet.description = clean_text(payload["description"], 2000)
                        if "is_private" in payload:
                            snippet.is_private = payload["is_private"]
                        snippet.version += 1
                        snippet.updated_at = datetime.now(timezone.utc)
                        snippet.create_revision(current_user.id)
                        record.server_version = snippet.version
                        record.status = "applied"
                        record.applied_at = datetime.now(timezone.utc)
                elif operation == "delete":
                    db.session.delete(snippet)
                    record.status = "applied"
                    record.applied_at = datetime.now(timezone.utc)
        elif entity_type == "snippet" and operation == "create":
            # Client-created offline snippet
            if Snippet.query.filter_by(public_id=entity_id).first():
                record.status = "rejected"
                record.conflict_reason = "Snippet ID already exists"
                results.append(record.to_dict())
                continue
            title = payload.get("title", "Untitled")
            code = payload.get("code", "")
            language = payload.get("language", "plaintext")
            description = payload.get("description")
            is_private = payload.get("is_private", True)
            if (
                not isinstance(title, str) or not isinstance(code, str) or len(code) > 500_000
                or not isinstance(language, str) or not isinstance(is_private, bool)
                or language not in ALLOWED_LANGUAGES
                or (description is not None and not isinstance(description, str))
            ):
                record.status = "rejected"
                record.conflict_reason = "Invalid snippet payload"
                results.append(record.to_dict())
                continue
            sn = Snippet(
                public_id=entity_id,
                owner_id=current_user.id,
                title=clean_text(title, 255) or "Untitled",
                description=clean_text(description, 2000) if description else None,
                language=language,
                code=code,
                is_private=is_private,
                version=1,
            )
            db.session.add(sn)
            db.session.flush()
            sn.create_revision(current_user.id)
            record.status = "applied"
            record.server_version = 1
            record.applied_at = datetime.now(timezone.utc)
        else:
            record.status = "rejected"
            record.conflict_reason = "Unsupported operation"

        results.append(record.to_dict())

    db.session.commit()
    return jsonify({"results": results})

@api_bp.route("/sync/pull", methods=["GET"])
@login_required
def pull_changes():
    """Client pulls recent changes since a timestamp or version."""
    since = request.args.get("since")
    # Simplified: return recent owned snippets
    query = Snippet.query.filter_by(owner_id=current_user.id)
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            query = query.filter(Snippet.updated_at > since_dt)
        except ValueError:
            pass
    snippets = query.order_by(Snippet.updated_at.desc()).limit(100).all()
    return jsonify({
        "snippets": [s.to_dict() for s in snippets],
        "server_time": datetime.now(timezone.utc).isoformat(),
    })
