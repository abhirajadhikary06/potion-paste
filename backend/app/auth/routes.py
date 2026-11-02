from flask import request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import func
from .. import db
from ..models import User
from . import auth_bp
import re

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,30}$")

def validate_password(password: str) -> str | None:
    if len(password) > 1024:
        return "Password must be no more than 1024 characters"
    if len(password) < 10:
        return "Password must be at least 10 characters"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one digit"
    return None

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid_json", "message": "A JSON object is required"}), 400
    if any(not isinstance(data.get(key, ""), str) for key in ("email", "username", "password", "display_name")):
        return jsonify({"error": "invalid_fields", "message": "All fields must be strings"}), 400
    email = (data.get("email") or "").strip().lower()
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip() or username

    if not EMAIL_RE.match(email):
        return jsonify({"error": "invalid_email", "message": "Invalid email address"}), 400
    if not USERNAME_RE.match(username):
        return jsonify({
            "error": "invalid_username",
            "message": "Username must be 3-30 characters (letters, numbers, underscore)",
        }), 400
    pw_err = validate_password(password)
    if pw_err:
        return jsonify({"error": "weak_password", "message": pw_err}), 400

    if User.query.filter(func.lower(User.email) == email).first():
        return jsonify({"error": "email_taken", "message": "Email already registered"}), 409
    if User.query.filter(func.lower(User.username) == username).first():
        return jsonify({"error": "username_taken", "message": "Username already taken"}), 409

    user = User(
        public_id=str(uuid4()),
        email=email,
        username=username,
        display_name=display_name,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user, remember=True)
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({"user": user.to_dict(include_email=True)}), 201

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid_json", "message": "A JSON object is required"}), 400
    if any(not isinstance(data.get(key, ""), str) for key in ("email", "username", "password")):
        return jsonify({"error": "invalid_fields", "message": "Credentials must be strings"}), 400
    identifier = (data.get("email") or data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    if len(password) > 1024:
        return jsonify({"error": "invalid_fields", "message": "Password is too long"}), 400
    remember = bool(data.get("remember", True))

    if not identifier or not password:
        return jsonify({"error": "missing_fields", "message": "Email/username and password required"}), 400

    user = User.query.filter(
        (func.lower(User.email) == identifier) | (func.lower(User.username) == identifier)
    ).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "invalid_credentials", "message": "Invalid email or password"}), 401
    if not user.is_active:
        return jsonify({"error": "account_disabled", "message": "Account is disabled"}), 403

    login_user(user, remember=remember)
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({"user": user.to_dict(include_email=True)})

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    return jsonify({"message": "Logged out"})

@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({"user": current_user.to_dict(include_email=True)})

@auth_bp.route("/me", methods=["PATCH"])
@login_required
def update_profile():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid_json", "message": "A JSON object is required"}), 400
    if any(key in data and not isinstance(data[key], str) for key in ("display_name", "bio", "avatar_url")):
        return jsonify({"error": "invalid_fields", "message": "Profile fields must be strings"}), 400
    if "display_name" in data:
        current_user.display_name = (data["display_name"] or "").strip()[:120] or current_user.username
    if "bio" in data:
        current_user.bio = (data["bio"] or "")[:500]
    if "avatar_url" in data:
        current_user.avatar_url = (data["avatar_url"] or "")[:512]
    db.session.commit()
    return jsonify({"user": current_user.to_dict(include_email=True)})

@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "invalid_json", "message": "A JSON object is required"}), 400
    if any(not isinstance(data.get(key, ""), str) for key in ("current_password", "new_password")):
        return jsonify({"error": "invalid_fields", "message": "Passwords must be strings"}), 400
    current = data.get("current_password") or ""
    new_pw = data.get("new_password") or ""

    if not current_user.check_password(current):
        return jsonify({"error": "wrong_password", "message": "Current password is incorrect"}), 400
    pw_err = validate_password(new_pw)
    if pw_err:
        return jsonify({"error": "weak_password", "message": pw_err}), 400

    current_user.set_password(new_pw)
    db.session.commit()
    return jsonify({"message": "Password updated"})
