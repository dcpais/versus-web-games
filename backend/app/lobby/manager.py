from __future__ import annotations

import random
import string
import uuid
from typing import Optional

import socketio

from .base_lobby import BaseLobby
from .models import LobbyStatus

_CODE_CHARS = string.ascii_uppercase + string.digits


def _gen_code(length: int = 6) -> str:
    return "".join(random.choices(_CODE_CHARS, k=length))


class LobbyManager:
    """
    Singleton-style registry of all active lobbies.

    Game types are registered at startup:
        manager.register_game("tictactoe", TicTacToeGame, max_players=2)

    All active-lobby state lives here; there is no database layer yet.
    """

    def __init__(self) -> None:
        self._lobbies: dict[str, BaseLobby] = {}        # lobby_id → BaseLobby
        self._invite_codes: dict[str, str] = {}         # invite_code → lobby_id
        self._sid_to_lobby: dict[str, str] = {}         # sid → lobby_id
        self._game_registry: dict[str, type] = {}       # game_type → GameClass
        self._game_max_players: dict[str, int] = {}     # game_type → max_players

    # ── Game type registration ─────────────────────────────────────────────

    def register_game(self, game_type: str, game_class: type, max_players: int = 2) -> None:
        self._game_registry[game_type] = game_class
        self._game_max_players[game_type] = max_players

    # ── Lobby lifecycle ────────────────────────────────────────────────────

    async def create_lobby(
        self,
        sio: socketio.AsyncServer,
        game_type: str,
        host_sid: str,
        host_user_id: str,
        host_display_name: str,
    ) -> tuple[Optional[BaseLobby], str]:
        if game_type not in self._game_registry:
            return None, f"Unknown game type: '{game_type}'."

        lobby_id = str(uuid.uuid4())
        invite_code = self._unique_code()
        max_players = self._game_max_players[game_type]

        lobby = BaseLobby(
            lobby_id=lobby_id,
            game_type=game_type,
            invite_code=invite_code,
            max_players=max_players,
            sio=sio,
        )

        game_class = self._game_registry[game_type]
        lobby.game = game_class(lobby)

        self._lobbies[lobby_id] = lobby
        self._invite_codes[invite_code] = lobby_id

        await lobby.add_player(host_sid, host_user_id, host_display_name)
        self._sid_to_lobby[host_sid] = lobby_id

        return lobby, ""

    async def join_lobby(
        self,
        sio: socketio.AsyncServer,
        invite_code: str,
        player_sid: str,
        player_user_id: str,
        player_display_name: str,
    ) -> tuple[Optional[BaseLobby], str]:
        invite_code = invite_code.strip().upper()
        lobby_id = self._invite_codes.get(invite_code)
        if not lobby_id:
            return None, "Invalid invite code."

        lobby = self._lobbies.get(lobby_id)
        if not lobby:
            return None, "Lobby no longer exists."
        if lobby.status != LobbyStatus.WAITING:
            return None, "Game already in progress."
        if lobby.is_full():
            return None, "Lobby is full."
        if player_user_id in lobby.players:
            return None, "You are already in this lobby."

        await lobby.add_player(player_sid, player_user_id, player_display_name)
        self._sid_to_lobby[player_sid] = lobby_id
        return lobby, ""

    async def remove_player(self, sid: str) -> Optional[BaseLobby]:
        lobby_id = self._sid_to_lobby.pop(sid, None)
        if not lobby_id:
            return None

        lobby = self._lobbies.get(lobby_id)
        if not lobby:
            return None

        await lobby.remove_player(sid)

        if not lobby.players:
            self._invite_codes.pop(lobby.invite_code, None)
            del self._lobbies[lobby_id]

        return lobby

    # ── Lookups ────────────────────────────────────────────────────────────

    def get_lobby_by_sid(self, sid: str) -> Optional[BaseLobby]:
        lid = self._sid_to_lobby.get(sid)
        return self._lobbies.get(lid) if lid else None

    # ── Helpers ────────────────────────────────────────────────────────────

    def _unique_code(self) -> str:
        while True:
            code = _gen_code()
            if code not in self._invite_codes:
                return code
