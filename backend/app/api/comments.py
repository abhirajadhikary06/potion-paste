from flask import request, jsonify, abort
from flask_login import login_required, current_user
from uuid import uuid4
from .. import db, socketio
from ..models import Snippet, Comment, ShareLink
from . import api_bp
import bleach

def clean_body(text: str) -> str:
    return bleach.clean(text or "", tags=["code", "pre", "em", "strong", "a"], strip=True)[:5000]


def share_link_for(snippet):
    token = request.headers.get("X-Share-Token") or request.args.get("token")
    if not token:
        return None
    link = ShareLink.query.filter_by(token=token, snippet_id=snippet.id).first()
    return link if link and link.is_valid() else None

@api_bp.route("/snippets/<public_id>/comments", methods=["GET"])
def list_comments(public_id):
    snippet = Snippet.query.filter_by(public_id=public_id).first_or_404()
    is_owner = current_user.is_authenticated and current_user.id == snippet.owner_id
    link = share_link_for(snippet) if not is_owner else None
    if snippet.is_private and not is_owner and not link:
        abort(403)

    comments = (
        Comment.query.filter_by(snippet_id=snippet.id, parent_id=None, is_deleted=False)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return jsonify({"comments": [c.to_dict() for c in comments]})

@api_bp.route("/snippets/<public_id>/comments", methods=["POST"])
@login_required
def create_comment(public_id):
    snippet = Snippet.query.filter_by(public_id=public_id).first_or_404()
    # Owner or public can comment (simplified; share links can extend later)
    is_owner = current_user.id == snippet.owner_id
    link = share_link_for(snippet) if not is_owner else None
    if snippet.is_private and not is_owner and not link:
        abort(403)
    if link and not link.can_comment:
        abort(403)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid_json", "message": "A JSON object is required"}), 400
    if not isinstance(data.get("body", ""), str):
        return jsonify({"error": "invalid_body"}), 400
    if data.get("parent_id") is not None and not isinstance(data["parent_id"], str):
        return jsonify({"error": "invalid_parent"}), 400
    body = clean_body(data.get("body") or "")
    if not body:
        return jsonify({"error": "empty_comment", "message": "Comment cannot be empty"}), 400

    parent_id = data.get("parent_id")
    parent = None
    if parent_id:
        parent = Comment.query.filter_by(public_id=parent_id, snippet_id=snippet.id).first()
        if not parent:
            return jsonify({"error": "invalid_parent"}), 400

    comment = Comment(
        public_id=str(uuid4()),
        snippet_id=snippet.id,
        author_id=current_user.id,
        parent_id=parent.id if parent else None,
        body=body,
    )
    db.session.add(comment)
    db.session.commit()

    payload = comment.to_dict()
    socketio.emit("comment:created", payload, room=f"snippet:{snippet.public_id}")

    return jsonify({"comment": payload}), 201

@api_bp.route("/comments/<public_id>", methods=["DELETE"])
@login_required
def delete_comment(public_id):
    comment = Comment.query.filter_by(public_id=public_id).first_or_404()
    if comment.author_id != current_user.id and comment.snippet.owner_id != current_user.id:
        abort(403)
    comment.is_deleted = True
    comment.body = ""
    db.session.commit()
    socketio.emit(
        "comment:deleted",
        {"id": comment.public_id},
        room=f"snippet:{comment.snippet.public_id}",
    )
    return jsonify({"message": "Deleted"})
