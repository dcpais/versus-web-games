from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class LobbyStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


@dataclass
class Player:
    sid: str            # socket session ID (changes on reconnect)
    user_id: str        # stable client-provided identifier
    display_name: str
    is_ready: bool = False
    is_host: bool = False
    joined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "is_ready": self.is_ready,
            "is_host": self.is_host,
        }


@dataclass
class ChatMessage:
    sender_id: str
    sender_name: str
    content: str
    is_system: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "content": self.content,
            "is_system": self.is_system,
            "timestamp": self.timestamp.isoformat(),
        }
