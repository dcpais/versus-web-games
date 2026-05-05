from __future__ import annotations

from ..lobby.models import LobbyStatus
from .base_game import BaseGame

Board = list[list[str | None]]

_WINS = [
    # rows
    [(0, 0), (0, 1), (0, 2)],
    [(1, 0), (1, 1), (1, 2)],
    [(2, 0), (2, 1), (2, 2)],
    # cols
    [(0, 0), (1, 0), (2, 0)],
    [(0, 1), (1, 1), (2, 1)],
    [(0, 2), (1, 2), (2, 2)],
    # diagonals
    [(0, 0), (1, 1), (2, 2)],
    [(0, 2), (1, 1), (2, 0)],
]


class TicTacToeGame(BaseGame):
    """
    Two-player Tic-Tac-Toe.

    game:action payloads accepted while in_progress:
        {"type": "place", "row": 0-2, "col": 0-2}
    """

    def __init__(self, lobby) -> None:
        super().__init__(lobby)
        self.board: Board = [[None] * 3 for _ in range(3)]
        self.markers: dict[str, str] = {}   # user_id → "X" | "O"
        self.current_turn: str | None = None
        self.winner: str | None = None
        self._started = False

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def on_game_start(self) -> None:
        players = list(self.lobby.players.values())
        # Host is always X and goes first
        self.markers[players[0].user_id] = "X"
        self.markers[players[1].user_id] = "O"
        self.current_turn = players[0].user_id
        self._started = True

        await self.lobby.announce(
            f"{players[0].display_name} plays X  ·  "
            f"{players[1].display_name} plays O  ·  "
            f"{players[0].display_name} goes first!"
        )
        await self.lobby.broadcast_state()

    async def on_game_action(self, user_id: str, action: dict) -> None:
        if action.get("type") != "place":
            return

        if user_id != self.current_turn:
            await self.lobby.emit_to_player(user_id, "lobby:error", {
                "code": "not_your_turn",
                "message": "It's not your turn.",
            })
            return

        row, col = action.get("row"), action.get("col")
        if not (isinstance(row, int) and isinstance(col, int) and 0 <= row <= 2 and 0 <= col <= 2):
            return
        if self.board[row][col] is not None:
            await self.lobby.emit_to_player(user_id, "lobby:error", {
                "code": "cell_taken",
                "message": "That cell is already taken.",
            })
            return

        marker = self.markers[user_id]
        self.board[row][col] = marker

        if self._check_winner(marker):
            self.winner = user_id
            name = self.lobby.players[user_id].display_name
            self.lobby.status = LobbyStatus.FINISHED
            await self.lobby.announce(f"{name} wins!")
        elif self._is_draw():
            self.lobby.status = LobbyStatus.FINISHED
            await self.lobby.announce("It's a draw!")
        else:
            # Swap turn
            player_ids = list(self.lobby.players.keys())
            self.current_turn = next(uid for uid in player_ids if uid != user_id)

        await self.lobby.broadcast_state()

    async def on_player_left(self, user_id: str, display_name: str) -> None:
        remaining = [uid for uid in self.lobby.players]
        if remaining:
            winner_name = self.lobby.players[remaining[0]].display_name
            await self.lobby.announce(
                f"{display_name} disconnected. {winner_name} wins by forfeit!"
            )
        else:
            await self.lobby.announce(f"{display_name} disconnected. Game over.")
        self.lobby.status = LobbyStatus.FINISHED
        await self.lobby.broadcast_state()

    # ── State ──────────────────────────────────────────────────────────────

    def get_game_state(self) -> dict | None:
        if not self._started:
            return None
        return {
            "board": self.board,
            "markers": self.markers,
            "current_turn": self.current_turn,
            "winner": self.winner,
        }

    # ── Helpers ────────────────────────────────────────────────────────────

    def _check_winner(self, marker: str) -> bool:
        return any(
            all(self.board[r][c] == marker for r, c in line)
            for line in _WINS
        )

    def _is_draw(self) -> bool:
        return all(cell is not None for row in self.board for cell in row)
