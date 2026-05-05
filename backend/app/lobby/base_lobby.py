from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import socketio

from .models import ChatMessage, LobbyStatus, Player

if TYPE_CHECKING:
    from ..games.base_game import BaseGame


class BaseLobby:
    """
    Generic lobby that handles player management, chat, and game lifecycle.

    A game handler (BaseGame subclass) is attached after construction by
    LobbyManager. The lobby transitions:
        waiting → in_progress (when all players ready)
        in_progress → finished (when game ends or a player leaves)
    """

    def __init__(
        self,
        lobby_id: str,
        game_type: str,
        invite_code: str,
        max_players: int,
        sio: socketio.AsyncServer,
    ) -> None:
        self.id = lobby_id
        self.game_type = game_type
        self.invite_code = invite_code
        self.max_players = max_players
        self.sio = sio
        self.status = LobbyStatus.WAITING
        self.players: dict[str, Player] = {}   # user_id → Player
        self._sid_index: dict[str, str] = {}   # sid → user_id
        self.chat_history: list[ChatMessage] = []
        self.game: Optional[BaseGame] = None   # attached by LobbyManager

    # ── Player management ──────────────────────────────────────────────────

    async def add_player(self, sid: str, user_id: str, display_name: str) -> Player:
        is_host = len(self.players) == 0
        player = Player(sid=sid, user_id=user_id, display_name=display_name, is_host=is_host)
        self.players[user_id] = player
        self._sid_index[sid] = user_id
        await self.sio.enter_room(sid, self.id)
        await self._system_message(f"{display_name} joined the lobby.")
        await self.broadcast_state()
        return player

    async def remove_player(self, sid: str) -> Optional[Player]:
        user_id = self._sid_index.pop(sid, None)
        if not user_id:
            return None
        player = self.players.pop(user_id, None)
        if not player:
            return None

        await self.sio.leave_room(sid, self.id)

        # Mid-game disconnect — delegate entirely to the game handler
        if self.status == LobbyStatus.IN_PROGRESS and self.game:
            await self.game.on_player_left(user_id, player.display_name)
            return player

        await self._system_message(f"{player.display_name} left the lobby.")

        if player.is_host and self.players:
            new_host = next(iter(self.players.values()))
            new_host.is_host = True
            await self._system_message(f"{new_host.display_name} is now the host.")

        if self.players:
            await self.broadcast_state()

        return player

    def get_player_by_sid(self, sid: str) -> Optional[Player]:
        uid = self._sid_index.get(sid)
        return self.players.get(uid) if uid else None

    def is_full(self) -> bool:
        return len(self.players) >= self.max_players

    # ── Ready system ───────────────────────────────────────────────────────

    async def set_ready(self, sid: str, ready: bool) -> None:
        player = self.get_player_by_sid(sid)
        if not player:
            return
        player.is_ready = ready
        await self.broadcast_state()

        if self._all_ready() and self.status == LobbyStatus.WAITING:
            await self._start_game()

    def _all_ready(self) -> bool:
        return len(self.players) >= 2 and all(p.is_ready for p in self.players.values())

    async def _start_game(self) -> None:
        if not self.game:
            return
        self.status = LobbyStatus.IN_PROGRESS
        await self.broadcast_state()
        await self.game.on_game_start()

    # ── Chat ───────────────────────────────────────────────────────────────

    async def send_chat(self, sid: str, content: str) -> None:
        player = self.get_player_by_sid(sid)
        if not player:
            return
        content = content.strip()
        if not content or len(content) > 300:
            return
        msg = ChatMessage(
            sender_id=player.user_id,
            sender_name=player.display_name,
            content=content,
        )
        self.chat_history.append(msg)
        await self.sio.emit("chat:message", msg.to_dict(), room=self.id)

    async def announce(self, content: str) -> None:
        """Broadcast a system announcement. Called by game logic."""
        await self._system_message(content)

    async def _system_message(self, content: str) -> ChatMessage:
        msg = ChatMessage(sender_id="system", sender_name="System", content=content, is_system=True)
        self.chat_history.append(msg)
        await self.sio.emit("chat:message", msg.to_dict(), room=self.id)
        return msg

    # ── State broadcasting ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        game_state = None
        if self.game and self.status == LobbyStatus.IN_PROGRESS:
            game_state = self.game.get_game_state()
        return {
            "id": self.id,
            "game_type": self.game_type,
            "invite_code": self.invite_code,
            "status": self.status.value,
            "max_players": self.max_players,
            "players": [p.to_dict() for p in self.players.values()],
            "game_state": game_state,
        }

    async def broadcast_state(self) -> None:
        await self.sio.emit("lobby:state", self.to_dict(), room=self.id)

    async def emit_to_player(self, user_id: str, event: str, data: dict) -> None:
        """Send a targeted event to one player (e.g. private card dealt)."""
        player = self.players.get(user_id)
        if player:
            await self.sio.emit(event, data, to=player.sid)
