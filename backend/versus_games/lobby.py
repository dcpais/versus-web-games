import uuid
from dataclasses import dataclass, field
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Lobby:
    lobby_id: str
    host: WebSocket
    is_private: bool = False
    members: dict = field(default_factory=dict)  # WebSocket -> username


class LobbyManager:
    def __init__(self):
        self.lobbies: dict[str, Lobby] = {}
        self._ws_to_lid: dict[int, str] = {}  # id(ws) -> lobby_id

    def create(self, host: WebSocket, username: str) -> Lobby:
        lobby_id = uuid.uuid4().hex[:6].upper()
        lobby = Lobby(lobby_id=lobby_id, host=host)
        lobby.members[host] = username
        self.lobbies[lobby_id] = lobby
        self._ws_to_lid[id(host)] = lobby_id
        return lobby

    def get(self, lobby_id: str) -> Optional[Lobby]:
        return self.lobbies.get(lobby_id)

    def get_by_ws(self, ws: WebSocket) -> Optional[Lobby]:
        lid = self._ws_to_lid.get(id(ws))
        return self.lobbies.get(lid) if lid else None

    def add_member(self, lobby: Lobby, ws: WebSocket, username: str):
        lobby.members[ws] = username
        self._ws_to_lid[id(ws)] = lobby.lobby_id

    def remove_member(self, ws: WebSocket) -> Optional[tuple[Lobby, str, bool]]:
        """Remove ws. Returns (lobby, username, host_transferred) or None."""
        lid = self._ws_to_lid.pop(id(ws), None)
        if not lid:
            return None
        lobby = self.lobbies.get(lid)
        if not lobby:
            return None

        username = lobby.members.pop(ws, "Someone")
        host_transferred = False

        if not lobby.members:
            del self.lobbies[lid]
        elif lobby.host is ws:
            lobby.host = next(iter(lobby.members))
            host_transferred = True

        return lobby, username, host_transferred

    def state(self, lobby: Lobby) -> dict:
        return {
            "lobby_id": lobby.lobby_id,
            "host": lobby.members.get(lobby.host, ""),
            "is_private": lobby.is_private,
            "members": list(lobby.members.values()),
            "member_count": len(lobby.members),
        }


manager = LobbyManager()


# ── Broadcast helpers ─────────────────────────────────────────────────────────

async def _send(ws: WebSocket, type_: str, data: dict):
    await ws.send_json({"type": type_, "data": data})


async def _broadcast(lobby: Lobby, type_: str, data: dict, exclude: WebSocket = None):
    for ws in list(lobby.members):
        if ws is not exclude:
            await _send(ws, type_, data)


async def _broadcast_state(lobby: Lobby):
    await _broadcast(lobby, "lobby_update", manager.state(lobby))


async def _system_announce(lobby: Lobby, message: str):
    await _broadcast(lobby, "announcement", {"from": "system", "message": message})


# ── Event handlers ────────────────────────────────────────────────────────────

async def handle_join(ws: WebSocket, data: dict):
    """
    Join an existing lobby or create a new one.

    Send:    { "type": "join_lobby", "data": { "username": str, "lobby_id"?: str } }
    Receive: { "type": "joined",       "data": { "lobby_id": str } }        → you only
             { "type": "lobby_update", "data": <state> }                    → whole room
             { "type": "announcement", "data": { "from": "system", ... } }  → whole room
    """
    username = (data.get("username") or "").strip()
    if not username:
        await _send(ws, "error", {"message": "username is required"})
        return

    if manager.get_by_ws(ws):
        await _send(ws, "error", {"message": "already in a lobby"})
        return

    lobby_id = (data.get("lobby_id") or "").strip().upper()
    if lobby_id:
        lobby = manager.get(lobby_id)
        if not lobby:
            await _send(ws, "error", {"message": "lobby not found"})
            return
        if lobby.is_private:
            await _send(ws, "error", {"message": "lobby is private"})
            return
        manager.add_member(lobby, ws, username)
    else:
        lobby = manager.create(host=ws, username=username)

    await _send(ws, "joined", {"lobby_id": lobby.lobby_id})
    await _broadcast_state(lobby)
    await _system_announce(lobby, f"{username} joined the lobby")


async def handle_leave(ws: WebSocket):
    """
    Leave the current lobby.

    Send:    { "type": "leave_lobby" }
    Receive: { "type": "left" }                                             → you only
             { "type": "lobby_update", "data": <state> }                    → remaining
             { "type": "announcement", "data": { "from": "system", ... } }  → remaining
    """
    result = manager.remove_member(ws)
    if not result:
        await _send(ws, "error", {"message": "not in a lobby"})
        return

    lobby, username, host_transferred = result
    await _send(ws, "left", {})

    if lobby.members:
        await _system_announce(lobby, f"{username} left the lobby")
        if host_transferred:
            await _system_announce(lobby, f"{lobby.members[lobby.host]} is now the host")
        await _broadcast_state(lobby)


async def handle_set_privacy(ws: WebSocket, data: dict):
    """
    Make the lobby public or private. Host only.

    Send:    { "type": "set_privacy", "data": { "is_private": bool } }
    Receive: { "type": "lobby_update", "data": <state> }                    → whole room
             { "type": "announcement", "data": { "from": "system", ... } }  → whole room
    """
    lobby = manager.get_by_ws(ws)
    if not lobby:
        await _send(ws, "error", {"message": "not in a lobby"})
        return
    if lobby.host is not ws:
        await _send(ws, "error", {"message": "only the host can change privacy"})
        return

    lobby.is_private = bool(data.get("is_private"))
    label = "private" if lobby.is_private else "public"
    await _broadcast_state(lobby)
    await _system_announce(lobby, f"Lobby is now {label}")


async def handle_chat(ws: WebSocket, data: dict):
    """
    Send a chat message to everyone in the lobby.

    Send:    { "type": "chat_message", "data": { "message": str } }
    Receive: { "type": "chat_message", "data": { "from": str, "message": str } } → whole room
    """
    lobby = manager.get_by_ws(ws)
    if not lobby:
        await _send(ws, "error", {"message": "not in a lobby"})
        return

    message = (data.get("message") or "").strip()
    if not message:
        return

    await _broadcast(lobby, "chat_message", {"from": lobby.members[ws], "message": message})


async def handle_announce(ws: WebSocket, data: dict):
    """
    Broadcast a host announcement to everyone. Host only.
    Displayed differently from chat (e.g. a banner in the UI).

    Send:    { "type": "announce", "data": { "message": str } }
    Receive: { "type": "announcement", "data": { "from": str, "message": str } } → whole room
    """
    lobby = manager.get_by_ws(ws)
    if not lobby:
        await _send(ws, "error", {"message": "not in a lobby"})
        return
    if lobby.host is not ws:
        await _send(ws, "error", {"message": "only the host can announce"})
        return

    message = (data.get("message") or "").strip()
    if not message:
        return

    await _broadcast(lobby, "announcement", {"from": lobby.members[ws], "message": message})


# ── Dispatch table ────────────────────────────────────────────────────────────

HANDLERS = {
    "join_lobby":   handle_join,
    "leave_lobby":  handle_leave,
    "set_privacy":  handle_set_privacy,
    "chat_message": handle_chat,
    "announce":     handle_announce,
}


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/lobby")
async def lobby_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            msg = await websocket.receive_json()
            event = msg.get("type")
            data = msg.get("data", {})

            handler = HANDLERS.get(event)
            if handler:
                if event == "leave_lobby":
                    await handler(websocket)
                else:
                    await handler(websocket, data)
            else:
                await _send(websocket, "error", {"message": f"unknown event: {event}"})

    except WebSocketDisconnect:
        result = manager.remove_member(websocket)
        if result and result[0].members:
            lobby, username, host_transferred = result
            await _system_announce(lobby, f"{username} disconnected")
            if host_transferred:
                await _system_announce(lobby, f"{lobby.members[lobby.host]} is now the host")
            await _broadcast_state(lobby)
