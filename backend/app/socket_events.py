"""
All Socket.IO event handlers.

Import this module for its side effects (the @sio.on decorators register
handlers against the shared sio instance in core.py).

Client → Server events
──────────────────────
  lobby:create   {game_type, user_id, display_name}
  lobby:join     {invite_code, user_id, display_name}
  lobby:leave    {}
  lobby:ready    {ready: bool}
  lobby:kick     {user_id}            — host only
  chat:send      {message: str}
  game:action    {type: str, ...}     — forwarded to active game handler

Server → Client events
──────────────────────
  lobby:created  {invite_code, state}
  lobby:joined   {state}
  lobby:state    {id, game_type, invite_code, status, max_players, players, game_state}
  lobby:error    {code, message}
  chat:message   {sender_id, sender_name, content, is_system, timestamp}
"""

from .core import lobby_manager, sio
from .lobby.models import LobbyStatus


# ── Connection lifecycle ───────────────────────────────────────────────────

@sio.event
async def connect(sid, environ, auth):
    pass  # authentication / token validation can go here


@sio.event
async def disconnect(sid):
    await lobby_manager.remove_player(sid)


# ── Lobby events ───────────────────────────────────────────────────────────

@sio.on("lobby:create")
async def on_lobby_create(sid, data: dict):
    game_type = data.get("game_type", "")
    user_id = data.get("user_id") or sid
    display_name = (data.get("display_name") or "Player").strip()[:32]

    lobby, err = await lobby_manager.create_lobby(sio, game_type, sid, user_id, display_name)
    if err:
        await sio.emit("lobby:error", {"code": "create_failed", "message": err}, to=sid)
        return

    await sio.emit("lobby:created", {"invite_code": lobby.invite_code, "state": lobby.to_dict()}, to=sid)


@sio.on("lobby:join")
async def on_lobby_join(sid, data: dict):
    invite_code = data.get("invite_code", "")
    user_id = data.get("user_id") or sid
    display_name = (data.get("display_name") or "Player").strip()[:32]

    lobby, err = await lobby_manager.join_lobby(sio, invite_code, sid, user_id, display_name)
    if err:
        await sio.emit("lobby:error", {"code": "join_failed", "message": err}, to=sid)
        return

    await sio.emit("lobby:joined", {"state": lobby.to_dict()}, to=sid)


@sio.on("lobby:leave")
async def on_lobby_leave(sid, _data=None):
    await lobby_manager.remove_player(sid)


@sio.on("lobby:ready")
async def on_lobby_ready(sid, data: dict):
    lobby = lobby_manager.get_lobby_by_sid(sid)
    if not lobby:
        return
    if lobby.status != LobbyStatus.WAITING:
        await sio.emit("lobby:error", {"code": "already_started", "message": "Game already started."}, to=sid)
        return
    await lobby.set_ready(sid, bool(data.get("ready", True)))


@sio.on("lobby:kick")
async def on_lobby_kick(sid, data: dict):
    lobby = lobby_manager.get_lobby_by_sid(sid)
    if not lobby:
        return

    kicker = lobby.get_player_by_sid(sid)
    if not kicker or not kicker.is_host:
        await sio.emit("lobby:error", {"code": "not_host", "message": "Only the host can kick players."}, to=sid)
        return

    target_id = data.get("user_id")
    target = lobby.players.get(target_id)
    if not target:
        return
    if target.is_host:
        await sio.emit("lobby:error", {"code": "cannot_kick_host", "message": "Cannot kick the host."}, to=sid)
        return

    await lobby_manager.remove_player(target.sid)
    await sio.emit("lobby:error", {"code": "kicked", "message": "You were kicked from the lobby."}, to=target.sid)


# ── Chat ───────────────────────────────────────────────────────────────────

@sio.on("chat:send")
async def on_chat_send(sid, data: dict):
    lobby = lobby_manager.get_lobby_by_sid(sid)
    if not lobby:
        return
    await lobby.send_chat(sid, data.get("message", ""))


# ── Game actions ───────────────────────────────────────────────────────────

@sio.on("game:action")
async def on_game_action(sid, data: dict):
    """
    Generic game action — routed to the active game's on_game_action().
    The game is responsible for all validation (turn order, legality, etc).
    """
    lobby = lobby_manager.get_lobby_by_sid(sid)
    if not lobby or not lobby.game:
        return

    if lobby.status != LobbyStatus.IN_PROGRESS:
        await sio.emit("lobby:error", {"code": "not_in_game", "message": "No game in progress."}, to=sid)
        return

    player = lobby.get_player_by_sid(sid)
    if not player:
        return

    await lobby.game.on_game_action(player.user_id, data)
