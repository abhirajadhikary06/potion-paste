import os
from app import create_app, socketio

app = create_app(os.getenv("FLASK_ENV", "production"))
application = app
