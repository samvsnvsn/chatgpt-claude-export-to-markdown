"""Normalized conversation model shared by every exporter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Attachment:
    """A file referenced by a message. `archive_path` is set when the file exists in the export."""

    name: str
    archive_path: Optional[str] = None
    kind: str = "file"  # "image" or "file"
    extracted_text: Optional[str] = None


@dataclass
class Message:
    role: str  # "user", "assistant", "tool", "system"
    text: str
    time: Optional[datetime] = None
    attachments: list[Attachment] = field(default_factory=list)


@dataclass
class Conversation:
    id: str
    title: str
    source: str  # "chatgpt" or "claude"
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    project: Optional[str] = None
    model: Optional[str] = None
    messages: list[Message] = field(default_factory=list)


def from_epoch(value: object) -> Optional[datetime]:
    try:
        if value is None or value == "":
            return None
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def from_iso(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
