from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Deque, List

from pydantic import BaseModel, Field


class QueueMessage(BaseModel):
    """Represents a single email event held in the in-memory queue."""

    email_id: str
    sender: str
    subject: str
    body: str
    received_at: datetime
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EmailQueue:
    def __init__(self) -> None:
        self._queue: Deque[QueueMessage] = deque()
        self._lock = Lock()

    def enqueue(self, message: QueueMessage) -> None:
        with self._lock:
            self._queue.append(message)

    def dequeue(self) -> QueueMessage | None:
        with self._lock:
            return self._queue.popleft() if self._queue else None

    def list(self) -> List[QueueMessage]:
        with self._lock:
            return list(self._queue)

    def size(self) -> int:
        with self._lock:
            return len(self._queue)
