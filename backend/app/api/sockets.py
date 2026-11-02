from flask_login import current_user
from flask_socketio import join_room, leave_room, emit
from .. import socketio
from ..models import Snippet

@socketio.on("connect")
def on_connect():
    if current_user.is_authenticated:
        join_room(f"user:{current_user.public_id}")
        emit("connected", {"user_id": current_user.public_id})

@socketio.on("disconnect")
def on_disconnect():
    pass

@socketio.on("join_snippet")
def on_join_snippet(data):
    if not isinstance(data, dict):
        return
    public_id = data.get("snippet_id")
    if not public_id:
        return
    snippet = Snippet.query.filter_by(public_id=public_id).first()
    if not snippet:
        emit("socket:error", {"error": "snippet_not_found"})
        return
    if snippet.is_private and (
        not current_user.is_authenticated or current_user.id != snippet.owner_id
    ):
        emit("socket:error", {"error": "forbidden"})
        return
    join_room(f"snippet:{public_id}")
    emit("joined", {"snippet_id": public_id})

@socketio.on("leave_snippet")
def on_leave_snippet(data):
    if not isinstance(data, dict):
        return
    public_id = data.get("snippet_id")
    if public_id:
        leave_room(f"snippet:{public_id}")
