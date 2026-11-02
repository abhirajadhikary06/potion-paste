from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_cors import CORS
from flask_socketio import SocketIO
from .config import config_by_name
import os

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
socketio = SocketIO()

def create_app(config_name: str | None = None) -> Flask:
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(
        __name__,
        static_folder="../../frontend",
        static_url_path="",
        template_folder="templates",
    )
    if config_name not in config_by_name:
        raise ValueError(f"Unknown configuration: {config_name}")
    app.config.from_object(config_by_name[config_name])
    if config_name == "production":
        secret_key = app.config.get("SECRET_KEY")
        if not secret_key or len(secret_key) < 32 or secret_key.startswith("change-me"):
            raise RuntimeError("Production requires SECRET_KEY with at least 32 non-placeholder characters")

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    CORS(
        app,
        origins=app.config["ALLOWED_ORIGINS"],
        supports_credentials=True,
        expose_headers=["X-CSRFToken"],
    )

    # SocketIO
    if app.config.get("ENABLE_WEBSOCKETS"):
        socketio.init_app(
            app,
            cors_allowed_origins=app.config["ALLOWED_ORIGINS"],
            async_mode="eventlet",
            logger=False,
            engineio_logger=False,
            message_queue=app.config.get("REDIS_URL") if not app.debug else None,
        )

    login_manager.login_view = None  # API style
    login_manager.session_protection = "strong"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    # Blueprints
    from .api import api_bp
    from .auth import auth_bp

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    # Serve frontend
    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    @app.route("/app")
    @app.route("/app/<path:path>")
    def app_shell(path=None):
        return app.send_static_file("app.html")

    @app.route("/share/<share_id>")
    def share_view(share_id):
        return app.send_static_file("app.html")

    # Health
    @app.route("/api/health")
    def health():
        return {"status": "ok", "service": "potion-paste"}

    # CSRF token endpoint for SPA
    @app.route("/api/csrf-token")
    def csrf_token():
        from flask_wtf.csrf import generate_csrf
        return {"csrf_token": generate_csrf()}

    # Error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return {"error": "bad_request", "message": str(e.description)}, 400

    @app.errorhandler(401)
    def unauthorized(e):
        return {"error": "unauthorized", "message": "Authentication required"}, 401

    @app.errorhandler(403)
    def forbidden(e):
        return {"error": "forbidden", "message": "You do not have permission"}, 403

    @app.errorhandler(404)
    def not_found(e):
        return {"error": "not_found", "message": "Resource not found"}, 404

    @app.errorhandler(413)
    def request_too_large(e):
        return {"error": "request_too_large", "message": "Request body exceeds the 4 MB limit"}, 413

    @app.errorhandler(500)
    def internal_error(e):
        return {"error": "internal_error", "message": "An unexpected error occurred"}, 500

    return app

from .api import sockets  # noqa: F401

