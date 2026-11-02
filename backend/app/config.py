import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql://potion:potion@localhost:5432/potion_paste"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Session / cookies
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.getenv("PERMANENT_SESSION_LIFETIME", 86400))
    )
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    # CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_SSL_STRICT = SESSION_COOKIE_SECURE

    # Argon2id parameters
    ARGON2_TIME_COST = int(os.getenv("ARGON2_TIME_COST", 3))
    ARGON2_MEMORY_COST = int(os.getenv("ARGON2_MEMORY_COST", 65536))
    ARGON2_PARALLELISM = int(os.getenv("ARGON2_PARALLELISM", 4))

    # CORS
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5000")
    ALLOWED_ORIGINS = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", FRONTEND_ORIGIN).split(",")
        if o.strip()
    ]

    # Feature flags
    ENABLE_WEBSOCKETS = os.getenv("ENABLE_WEBSOCKETS", "True").lower() == "true"
    ENABLE_OFFLINE_SYNC = os.getenv("ENABLE_OFFLINE_SYNC", "True").lower() == "true"

    # Redis (for SocketIO message queue in multi-worker setups)
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # AWS
    AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
    S3_BUCKET = os.getenv("S3_BUCKET", "")
    CLOUDFRONT_DOMAIN = os.getenv("CLOUDFRONT_DOMAIN", "")

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me-immediately")

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    WTF_CSRF_SSL_STRICT = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "testing-secret"

config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
