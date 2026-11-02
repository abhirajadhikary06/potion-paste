from flask import request, jsonify, abort
from flask_login import login_required, current_user
from uuid import uuid4
from datetime import datetime, timezone
from slugify import slugify
from .. import db, socketio
from ..models import Snippet, SnippetRevision, Tag, SnippetTag
from . import api_bp
import bleach

ALLOWED_LANGUAGES = {
    "plaintext", "python", "javascript", "typescript", "html", "css", "json",
    "sql", "go", "rust", "java", "c", "cpp", "csharp", "php", "ruby", "swift",
    "kotlin", "shell", "bash", "yaml", "markdown", "dockerfile", "graphql",
    "r", "scala", "perl", "lua", "haskell", "elixir", "clojure", "dart",
}

def clean_text(text: str, max_len: int = 10000) -> str:
    if not text:
        return ""
    return bleach.clean(text, tags=[], strip=True)[:max_len]


def request_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def apply_tags(snippet, tags, replace=False):
    if replace:
        SnippetTag.query.filter_by(snippet_id=snippet.id).delete()
    seen = set()
    for raw_name in tags[:10]:
        name = clean_text(str(raw_name), 64).lower()
        slug = slugify(name)[:64]
        if not name or not slug or slug in seen:
            continue
        seen.add(slug)
        tag = Tag.query.filter_by(slug=slug).first()
        if not tag:
            tag = Tag(name=name, slug=slug)
            db.session.add(tag)
            db.session.flush()
        db.session.add(SnippetTag(snippet_id=snippet.id, tag_id=tag.id))

@api_bp.route("/snippets", methods=["GET"])
@login_required
def list_snippets():
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    language = request.args.get("language", "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(50, max(1, int(request.args.get("per_page", 20))))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_pagination"}), 400

    query = Snippet.query.filter_by(owner_id=current_user.id)

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Snippet.title.ilike(like)) | (Snippet.description.ilike(like))
        )
    if language and language in ALLOWED_LANGUAGES:
        query = query.filter_by(language=language)
    if tag:
        query = query.join(SnippetTag).join(Tag).filter(Tag.slug == slugify(tag))

    query = query.order_by(Snippet.updated_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "snippets": [s.to_dict(include_code=False) for s in pagination.items],
        "total": pagination.total,
        "page": page,
        "per_page": per_page,
        "pages": pagination.pages,
    })

@api_bp.route("/snippets", methods=["POST"])
@login_required
def create_snippet():
    data = request_object()
    if data is None:
        return jsonify({"error": "invalid_json", "message": "A JSON object is required"}), 400
    if any(not isinstance(data.get(key, ""), str) for key in ("title", "description", "language", "code")):
        return jsonify({"error": "invalid_fields", "message": "Text fields must be strings"}), 400
    if "tags" in data and not isinstance(data["tags"], list):
        return jsonify({"error": "invalid_tags", "message": "Tags must be a list"}), 400
    if "is_private" in data and not isinstance(data["is_private"], bool):
        return jsonify({"error": "invalid_visibility"}), 400
    title = clean_text(data.get("title") or "Untitled", 255)
    description = clean_text(data.get("description") or "", 2000)
    language = (data.get("language") or "plaintext").lower()
    if language not in ALLOWED_LANGUAGES:
        return jsonify({"error": "invalid_language"}), 400
    code = data.get("code") or ""
    if len(code) > 500_000:
        return jsonify({"error": "code_too_large", "message": "Code exceeds 500KB limit"}), 400
    is_private = bool(data.get("is_private", True))
    tags = data.get("tags") or []

    snippet = Snippet(
        public_id=str(uuid4()),
        owner_id=current_user.id,
        title=title,
        description=description,
        language=language,
        code=code,
        is_private=is_private,
        version=1,
    )
    db.session.add(snippet)
    db.session.flush()

    apply_tags(snippet, tags)

    snippet.create_revision(current_user.id)
    db.session.commit()

    if not is_private:
        socketio.emit("snippet:created", snippet.to_dict(), room=f"user:{current_user.public_id}")

    return jsonify({"snippet": snippet.to_dict()}), 201

@api_bp.route("/snippets/<public_id>", methods=["GET"])
def get_snippet(public_id):
    snippet = Snippet.query.filter_by(public_id=public_id).first_or_404()

    # Access control
    if snippet.is_private:
        if not current_user.is_authenticated or current_user.id != snippet.owner_id:
            # Check share token in header or query
            token = request.headers.get("X-Share-Token") or request.args.get("token")
            if not token:
                abort(403)
            from ..models import ShareLink
            link = ShareLink.query.filter_by(token=token, snippet_id=snippet.id).first()
            if not link or not link.is_valid():
                abort(403)
            link.view_count += 1
            db.session.commit()

    return jsonify({"snippet": snippet.to_dict()})

@api_bp.route("/snippets/<public_id>", methods=["PATCH"])
@login_required
def update_snippet(public_id):
    snippet = Snippet.query.filter_by(public_id=public_id).first_or_404()
    if snippet.owner_id != current_user.id:
        abort(403)

    data = request_object()
    if data is None:
        return jsonify({"error": "invalid_json", "message": "A JSON object is required"}), 400
    if any(key in data and not isinstance(data[key], str) for key in ("title", "description", "language", "code")):
        return jsonify({"error": "invalid_fields", "message": "Text fields must be strings"}), 400
    if "tags" in data and not isinstance(data["tags"], list):
        return jsonify({"error": "invalid_tags", "message": "Tags must be a list"}), 400
    if "is_private" in data and not isinstance(data["is_private"], bool):
        return jsonify({"error": "invalid_visibility"}), 400
    changed = False

    if "title" in data:
        snippet.title = clean_text(data["title"] or "Untitled", 255)
        changed = True
    if "description" in data:
        snippet.description = clean_text(data["description"] or "", 2000)
        changed = True
    if "language" in data:
        lang = (data["language"] or "plaintext").lower()
        if lang not in ALLOWED_LANGUAGES:
            return jsonify({"error": "invalid_language"}), 400
        snippet.language = lang
        changed = True
    if "code" in data:
        code = data["code"] or ""
        if len(code) > 500_000:
            return jsonify({"error": "code_too_large"}), 400
        snippet.code = code
        changed = True
    if "is_private" in data:
        snippet.is_private = bool(data["is_private"])
        changed = True
    if "tags" in data:
        apply_tags(snippet, data["tags"], replace=True)
        changed = True

    if changed:
        snippet.version += 1
        snippet.updated_at = datetime.now(timezone.utc)
        snippet.create_revision(current_user.id)
        db.session.commit()

        # Real-time notify
        room = f"snippet:{snippet.public_id}"
        socketio.emit("snippet:updated", snippet.to_dict(), room=room)

    return jsonify({"snippet": snippet.to_dict()})

@api_bp.route("/snippets/<public_id>", methods=["DELETE"])
@login_required
def delete_snippet(public_id):
    snippet = Snippet.query.filter_by(public_id=public_id).first_or_404()
    if snippet.owner_id != current_user.id:
        abort(403)
    db.session.delete(snippet)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200

@api_bp.route("/snippets/<public_id>/revisions", methods=["GET"])
@login_required
def list_revisions(public_id):
    snippet = Snippet.query.filter_by(public_id=public_id).first_or_404()
    if snippet.owner_id != current_user.id and snippet.is_private:
        abort(403)
    revs = SnippetRevision.query.filter_by(snippet_id=snippet.id).order_by(
        SnippetRevision.version.desc()
    ).limit(50).all()
    return jsonify({"revisions": [r.to_dict() for r in revs]})

@api_bp.route("/share/<share_id>", methods=["GET"])
def get_by_share_id(share_id):
    snippet = Snippet.query.filter_by(share_id=share_id).first_or_404()
    link = None
    token = request.headers.get("X-Share-Token") or request.args.get("token")
    if snippet.is_private and not token:
        abort(403)
    if token:
        from ..models import ShareLink
        link = ShareLink.query.filter_by(token=token, snippet_id=snippet.id).first()
        if not link or not link.is_valid():
            abort(403)
        link.view_count += 1
        db.session.commit()
    return jsonify({
        "snippet": snippet.to_dict(),
        "permissions": {
            "can_comment": bool(link.can_comment if link else not snippet.is_private),
            "can_edit": bool(link and link.can_edit),
        },
    })
