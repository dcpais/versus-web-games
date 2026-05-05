import socketio
from fastapi import FastAPI

from .core import lobby_manager, sio
from . import socket_events  # noqa: F401 — registers all @sio.on() handlers
from .games.tictactoe import TicTacToeGame

app = FastAPI(title="Versus Games API", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Game type registration ─────────────────────────────────────────────────
# Add new game types here as they are implemented.
lobby_manager.register_game("tictactoe", TicTacToeGame, max_players=2)


# ── ASGI app ───────────────────────────────────────────────────────────────
# Socket.IO wraps FastAPI so both share the same port.
# Socket.IO requests hit /socket.io; everything else falls through to FastAPI.
app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="/socket.io")
