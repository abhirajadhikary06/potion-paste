from flask import request, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime, timezone, timedelta
from .. import db
from ..models import Snippet, ShareLink
from . import api_bp

@api_bp.route("/snippets/<public_id>/share", methods=["POST"])
@login_required
def create_share_link(public_id):
    snippet = Snippet.query.filter_by(public_id=public_id).first_or_404()
    if snippet.owner_id != current_user.id:
        abort(403)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid_json", "message": "A JSON object is required"}), 400
    can_comment = data.get("can_comment", True)
    can_edit = data.get("can_edit", False)
    expires_in_hours = data.get("expires_in_hours")
    max_views = data.get("max_views")

    expires_at = None
    if expires_in_hours is not None:
        try:
            expires_in_hours = int(expires_in_hours)
            if expires_in_hours < 1 or expires_in_hours > 24 * 365:
                raise ValueError
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_expiry", "message": "Expiry must be 1 hour to 1 year"}), 400

    if max_views is not None:
        try:
            max_views = int(max_views)
            if max_views < 1:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_max_views", "message": "Maximum views must be positive"}), 400

    if "can_comment" in data and not isinstance(data["can_comment"], bool):
        return jsonify({"error": "invalid_can_comment"}), 400
    if "can_edit" in data and not isinstance(data["can_edit"], bool):
        return jsonify({"error": "invalid_can_edit"}), 400
    if can_edit:
        return jsonify({"error": "can_edit_not_supported", "message": "Share links are read-only"}), 400

    link = ShareLink(
        snippet_id=snippet.id,
        created_by_id=current_user.id,
        can_comment=can_comment,
        can_edit=can_edit,
        expires_at=expires_at,
        max_views=max_views,
    )
    db.session.add(link)
    # Also make the snippet accessible via share_id
    if snippet.is_private:
        # keep private but shareable via token/share_id
        pass
    db.session.commit()

    return jsonify({
        "share": link.to_dict(),
        "url": f"/share/{snippet.share_id}#token={link.token}",
        "share_id": snippet.share_id,
    }), 201

@api_bp.route("/snippets/<public_id>/share", methods=["GET"])
@login_required
def list_share_links(public_id):
    snippet = Snippet.query.filter_by(public_id=public_id).first_or_404()
    if snippet.owner_id != current_user.id:
        abort(403)
    links = ShareLink.query.filter_by(snippet_id=snippet.id, is_active=True).all()
    return jsonify({"links": [l.to_dict() for l in links]})
