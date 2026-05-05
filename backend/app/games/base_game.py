from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..lobby.models import LobbyStatus

if TYPE_CHECKING:
    from ..lobby.base_lobby import BaseLobby


class BaseGame(ABC):
    """
    Base class for all versus games.

    Subclass this and implement the three abstract methods to create a game.
    The lobby calls into the game at key lifecycle points; the game calls back
    into the lobby to broadcast state or send targeted events.

    Useful lobby hooks available to subclasses:
        await self.lobby.announce(msg)              — system chat message to all
        await self.lobby.broadcast_state()          — push lobby+game state to all
        await self.lobby.emit_to_player(uid, event, data)  — private event
        self.lobby.sio.emit(event, data, room=...)  — raw socket.io emit
    """

    def __init__(self, lobby: BaseLobby) -> None:
        self.lobby = lobby

    @abstractmethod
    async def on_game_start(self) -> None:
        """
        Called when all players have readied up and the lobby enters in_progress.
        Initialise game state here and broadcast the first game:state.
        """

    @abstractmethod
    async def on_game_action(self, user_id: str, action: dict) -> None:
        """
        Called for every 'game:action' socket event while the game is in progress.

        The action dict always contains at minimum {"type": str, ...payload}.
        Validate turn order, legality, and mutate state here, then broadcast.
        """

    @abstractmethod
    def get_game_state(self) -> dict | None:
        """
        Return serialisable game state that will be embedded in every
        lobby:state broadcast under the key 'game_state'.
        Return None before the game has started.
        """

    async def on_player_left(self, user_id: str, display_name: str) -> None:
        """
        Called mid-game when a player disconnects.

        Default behaviour: announce the disconnect and end the game.
        Override in subclasses to implement forfeits, AI takeover, pause, etc.
        """
        await self.lobby.announce(f"{display_name} disconnected. Game over.")
        self.lobby.status = LobbyStatus.FINISHED
        await self.lobby.broadcast_state()
