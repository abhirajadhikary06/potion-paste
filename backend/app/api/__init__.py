from flask import Blueprint

api_bp = Blueprint("api", __name__)

from . import snippets, comments, sync, share  # noqa: E402, F401
