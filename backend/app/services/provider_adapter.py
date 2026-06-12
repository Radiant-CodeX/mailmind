"""
MailMind v3 — ProviderAdapter ABC and concrete adapters.

ProviderAdapter is a stateless ABC: each instance wraps a set of decrypted
OAuth tokens (access + refresh) rather than reading from any global cache.
AccountService is responsible for decrypting tokens and constructing adapters.

GmailAdapter  → wraps GmailClient, passes tokens at construction
OutlookAdapter → wraps GraphClient, passes tokens at construction

Both adapters expose the same interface so all route handlers are provider-agnostic.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Abstract Base
# ─────────────────────────────────────────────────────────────────────────────


class ProviderAdapter(ABC):
    """
    Abstract mail-provider adapter.

    Concrete subclasses receive tokens at construction and must not read
    from any global state or process-level cache.
    """

    def __init__(self, access_token: str, refresh_token: str | None = None) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token

    # ── Profile ───────────────────────────────────────────────────────────────

    @abstractmethod
    def get_user_profile(self) -> dict[str, str | None]:
        """Return { email, display_name, photo_url }."""

    # ── Inbox operations ──────────────────────────────────────────────────────

    @abstractmethod
    def list_emails(
        self,
        folder: str = "inbox",
        limit: int = 50,
        page_token: str | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        """Return { emails: [...], page_token: str|None, has_next: bool }."""

    @abstractmethod
    def get_inbox_emails(self, limit: int = 10) -> list[dict[str, Any]]:
        """Simplified inbox fetch (used by /emails route)."""

    @abstractmethod
    def get_attachment(self, message_id: str, attachment_id: str) -> dict[str, Any] | None:
        """Return raw attachment data dict or None."""

    @abstractmethod
    def mark_read(self, email_id: str, read: bool = True) -> None: ...

    @abstractmethod
    def archive(self, email_id: str) -> None: ...

    @abstractmethod
    def move_to_trash(self, email_id: str) -> None: ...

    @abstractmethod
    def restore_from_trash(self, email_id: str) -> None: ...

    @abstractmethod
    def report_spam(self, email_id: str) -> None: ...

    @abstractmethod
    def send_reply(self, email_id: str, comment: str) -> None: ...

    @abstractmethod
    def reply_all(self, email_id: str, comment: str) -> None: ...

    @abstractmethod
    def forward_email(self, email_id: str, to: str, comment: str = "") -> None: ...

    @abstractmethod
    def send_new_email(
        self, to: str, subject: str, body: str,
        cc: str | None = None, bcc: str | None = None,
    ) -> None: ...

    # ── Sent / folder listing ─────────────────────────────────────────────────

    @abstractmethod
    def fetch_sent_emails(self, days: int = 30) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_draft_emails(self, limit: int = 10) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_spam_emails(self, limit: int = 10) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_trash_emails(self, limit: int = 10) -> list[dict[str, Any]]: ...

    # ── Calendar ──────────────────────────────────────────────────────────────

    @abstractmethod
    def fetch_calendar(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def create_calendar_event(
        self, email_id: str, commitment: str, deadline: datetime | None = None,
    ) -> str: ...

    # ── Tasks ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]: ...

    @abstractmethod
    def create_todo(self, email_id: str, commitment: str) -> str: ...


# ─────────────────────────────────────────────────────────────────────────────
# Gmail Adapter
# ─────────────────────────────────────────────────────────────────────────────


class GmailAdapter(ProviderAdapter):
    """
    Wraps GmailClient with token injection.
    The underlying GmailClient is constructed lazily on first use.
    """

    def __init__(self, access_token: str, refresh_token: str | None = None) -> None:
        super().__init__(access_token, refresh_token)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from app.services.gmail import GmailClient
            self._client = GmailClient(
                access_token=self.access_token,
                refresh_token=self.refresh_token,
            )
        return self._client

    def get_user_profile(self) -> dict[str, str | None]:
        return self._get_client().get_user_profile()

    def list_emails(self, folder="inbox", limit=50, page_token=None, query=None) -> dict[str, Any]:
        return self._get_client().list_emails(folder=folder, limit=limit, page_token=page_token, query=query)

    def get_inbox_emails(self, limit=10) -> list[dict[str, Any]]:
        return self._get_client().get_inbox_emails(limit=limit)

    def get_attachment(self, message_id, attachment_id) -> dict[str, Any] | None:
        return self._get_client().get_attachment(message_id, attachment_id)

    def mark_read(self, email_id, read=True) -> None:
        self._get_client().mark_read(email_id, read)

    def archive(self, email_id) -> None:
        self._get_client().archive(email_id)

    def move_to_trash(self, email_id) -> None:
        self._get_client().move_to_trash(email_id)

    def restore_from_trash(self, email_id) -> None:
        self._get_client().restore_from_trash(email_id)

    def report_spam(self, email_id) -> None:
        self._get_client().report_spam(email_id)

    def send_reply(self, email_id, comment) -> None:
        self._get_client().send_reply(email_id, comment)

    def reply_all(self, email_id, comment) -> None:
        self._get_client().reply_all(email_id, comment)

    def forward_email(self, email_id, to, comment="") -> None:
        self._get_client().forward_email(email_id, to, comment)

    def send_new_email(self, to, subject, body, cc=None, bcc=None) -> None:
        self._get_client().send_new_email(to=to, subject=subject, body=body, cc=cc, bcc=bcc)

    def fetch_sent_emails(self, days=30) -> list[dict[str, Any]]:
        return self._get_client().fetch_sent_emails(days=days)

    def get_draft_emails(self, limit=10) -> list[dict[str, Any]]:
        return self._get_client().get_draft_emails(limit=limit)

    def get_spam_emails(self, limit=10) -> list[dict[str, Any]]:
        return self._get_client().get_spam_emails(limit=limit)

    def get_trash_emails(self, limit=10) -> list[dict[str, Any]]:
        return self._get_client().get_trash_emails(limit=limit)

    def fetch_calendar(self) -> list[dict[str, Any]]:
        return self._get_client().fetch_calendar()

    def create_calendar_event(self, email_id, commitment, deadline=None) -> str:
        return self._get_client().create_calendar_event(email_id, commitment, deadline)

    def list_tasks(self, limit=20) -> list[dict[str, Any]]:
        return self._get_client().list_tasks(limit=limit)

    def create_todo(self, email_id, commitment) -> str:
        return self._get_client().create_todo(email_id, commitment)


# ─────────────────────────────────────────────────────────────────────────────
# Outlook Adapter
# ─────────────────────────────────────────────────────────────────────────────


class OutlookAdapter(ProviderAdapter):
    """
    Wraps GraphClient with token injection.
    """

    def __init__(self, access_token: str, refresh_token: str | None = None) -> None:
        super().__init__(access_token, refresh_token)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from app.services.graph import GraphClient
            self._client = GraphClient(
                access_token=self.access_token,
                refresh_token=self.refresh_token,
            )
        return self._client

    def get_user_profile(self) -> dict[str, str | None]:
        return self._get_client().get_user_profile()

    def list_emails(self, folder="inbox", limit=50, page_token=None, query=None) -> dict[str, Any]:
        return self._get_client().list_emails(folder=folder, limit=limit, page_token=page_token, query=query)

    def get_inbox_emails(self, limit=10) -> list[dict[str, Any]]:
        return self._get_client().get_inbox_emails(limit=limit)

    def get_attachment(self, message_id, attachment_id) -> dict[str, Any] | None:
        return self._get_client().get_attachment(message_id, attachment_id)

    def mark_read(self, email_id, read=True) -> None:
        self._get_client().mark_read(email_id, read)

    def archive(self, email_id) -> None:
        self._get_client().archive(email_id)

    def move_to_trash(self, email_id) -> None:
        self._get_client().move_to_trash(email_id)

    def restore_from_trash(self, email_id) -> None:
        self._get_client().restore_from_trash(email_id)

    def report_spam(self, email_id) -> None:
        self._get_client().report_spam(email_id)

    def send_reply(self, email_id, comment) -> None:
        self._get_client().send_reply(email_id, comment)

    def reply_all(self, email_id, comment) -> None:
        self._get_client().reply_all(email_id, comment)

    def forward_email(self, email_id, to, comment="") -> None:
        self._get_client().forward_email(email_id, to, comment)

    def send_new_email(self, to, subject, body, cc=None, bcc=None) -> None:
        self._get_client().send_new_email(to=to, subject=subject, body=body, cc=cc, bcc=bcc)

    def fetch_sent_emails(self, days=30) -> list[dict[str, Any]]:
        return self._get_client().fetch_sent_emails(days=days)

    def get_draft_emails(self, limit=10) -> list[dict[str, Any]]:
        return self._get_client().get_draft_emails(limit=limit)

    def get_spam_emails(self, limit=10) -> list[dict[str, Any]]:
        return self._get_client().get_spam_emails(limit=limit)

    def get_trash_emails(self, limit=10) -> list[dict[str, Any]]:
        return self._get_client().get_trash_emails(limit=limit)

    def fetch_calendar(self) -> list[dict[str, Any]]:
        return self._get_client().fetch_calendar()

    def create_calendar_event(self, email_id, commitment, deadline=None) -> str:
        return self._get_client().create_calendar_event(email_id, commitment, deadline)

    def list_tasks(self, limit=20) -> list[dict[str, Any]]:
        return self._get_client().list_tasks(limit=limit)

    def create_todo(self, email_id, commitment) -> str:
        return self._get_client().create_todo(email_id, commitment)


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────


def build_adapter(
    provider: str,
    access_token: str,
    refresh_token: str | None = None,
) -> ProviderAdapter:
    """Return the correct ProviderAdapter subclass for a given provider string."""
    if provider == "google":
        return GmailAdapter(access_token=access_token, refresh_token=refresh_token)
    if provider == "microsoft":
        return OutlookAdapter(access_token=access_token, refresh_token=refresh_token)
    raise ValueError(f"Unknown provider: {provider!r}. Expected 'google' or 'microsoft'.")
