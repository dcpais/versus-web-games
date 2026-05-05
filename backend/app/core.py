import socketio

from .lobby.manager import LobbyManager

# Single shared Socket.IO server instance.
# All event handlers in socket_events.py register against this object.
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",  # tighten in production
    logger=False,
    engineio_logger=False,
)

# Single shared lobby manager.
# Game types are registered in app/main.py at startup.
lobby_manager = LobbyManager()
