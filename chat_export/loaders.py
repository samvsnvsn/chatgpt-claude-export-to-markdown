"""Read official ChatGPT and Claude data exports (ZIP or conversations.json).

Everything runs locally: no network access, no login, no browser extension.
Parsing is defensive: a missing or unexpected field never crashes the run; the
content is kept as a clearly marked note instead of being silently dropped.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any, Optional

from .model import Attachment, Conversation, Message, from_epoch, from_iso


# Since mid-2026 ChatGPT exports split conversations into conversations-000.json,
# conversations-001.json, ... and large exports into several ...-part-0001.zip files.
_CONVERSATION_PART = re.compile(r"^conversations-\d+\.json$", re.IGNORECASE)
_ZIP_PART = re.compile(r"^(?P<stem>.+)-part-\d+\.zip$", re.IGNORECASE)


def _zip_parts(path: Path) -> list[Path]:
    """All parts of a split export (sibling ...-part-NNNN.zip files), or just `path`."""
    match = _ZIP_PART.match(path.name)
    if not match:
        return [path]
    prefix = match.group("stem").lower() + "-part-"
    parts = [p for p in path.parent.iterdir() if p.is_file() and _ZIP_PART.match(p.name) and p.name.lower().startswith(prefix)]
    return sorted(parts, key=lambda p: p.name.lower()) or [path]


class ExportSource:
    """Uniform access to a .zip export (or all parts of a split export) or a loose conversations.json (+ sibling files)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._zips: list[zipfile.ZipFile] = []
        self._zip_of: dict[str, zipfile.ZipFile] = {}
        if self.path.is_file() and zipfile.is_zipfile(self.path):
            for part in _zip_parts(self.path):
                archive = zipfile.ZipFile(part)
                self._zips.append(archive)
                for name in archive.namelist():
                    if not name.endswith("/"):
                        self._zip_of.setdefault(name, archive)
            self.names = list(self._zip_of)
        elif self.path.is_file():
            self.names = [p.name for p in self.path.parent.iterdir() if p.is_file()]
        elif self.path.is_dir():
            self.names = [str(p.relative_to(self.path)).replace("\\", "/") for p in self.path.rglob("*") if p.is_file()]
        else:
            raise FileNotFoundError(f"No export found at {self.path}")

    def _base(self) -> Path:
        return self.path if self.path.is_dir() else self.path.parent

    def find(self, basename: str) -> Optional[str]:
        """Shortest archive path whose file name is `basename` (handles a top-level folder in the ZIP)."""
        hits = [n for n in self.names if n.rsplit("/", 1)[-1] == basename]
        return min(hits, key=len) if hits else None

    def read_bytes(self, name: str) -> bytes:
        if self._zips:
            return self._zip_of[name].read(name)
        if self.path.is_file() and self.path.name == name:
            return self.path.read_bytes()
        return (self._base() / name).read_bytes()

    def read_json(self, name: str) -> Any:
        return json.loads(self.read_bytes(name).decode("utf-8-sig"))

    def find_containing(self, token: str) -> Optional[str]:
        token = token.strip()
        if not token:
            return None
        hits = [n for n in self.names if token in n.rsplit("/", 1)[-1]]
        return min(hits, key=len) if hits else None

    def close(self) -> None:
        for archive in self._zips:
            archive.close()


def load_export(path: str | Path) -> tuple[list[Conversation], ExportSource]:
    """Load conversations from a ChatGPT or Claude export. Returns (conversations, source)."""
    source = ExportSource(path)
    try:
        data = _read_conversations(source)
    except Exception:
        source.close()
        raise
    kind = detect_kind(data)
    if kind == "chatgpt":
        conversations = [c for c in (parse_chatgpt(item, source) for item in data) if c is not None]
    elif kind == "claude":
        projects = _claude_project_names(source)
        conversations = [c for c in (parse_claude(item, projects) for item in data) if c is not None]
    else:
        conversations = []
    return conversations, source


def _read_conversations(source: ExportSource) -> list[Any]:
    if source.path.is_file() and not zipfile.is_zipfile(source.path) and source.path.suffix.lower() == ".json":
        names = [source.path.name]
    elif source.find("conversations.json"):
        names = [source.find("conversations.json")]
    else:
        names = sorted((n for n in source.names if _CONVERSATION_PART.match(n.rsplit("/", 1)[-1])), key=lambda n: n.rsplit("/", 1)[-1].lower())
    if not names:
        raise ValueError(
            "No conversations found (conversations.json or conversations-000.json). Choose the ZIP you downloaded from "
            "ChatGPT or Claude (Settings → Data export). If your export came as several ...-part-0001.zip files, keep them in the same folder."
        )
    data: list[Any] = []
    for name in names:
        chunk = source.read_json(name)
        if not isinstance(chunk, list):
            raise ValueError(f"{name.rsplit('/', 1)[-1]} is not a list of conversations.")
        data.extend(chunk)
    return data


_IMAGE_SIGNATURES = ((b"\x89PNG\r\n\x1a\n", ".png"), (b"\xff\xd8\xff", ".jpg"), (b"GIF87a", ".gif"), (b"GIF89a", ".gif"))


def asset_file_name(archive_path: str, data: bytes) -> str:
    """File name for a copied asset. Newer ChatGPT exports store images as .dat files; give them their real extension."""
    name = archive_path.rsplit("/", 1)[-1]
    stem, dot, suffix = name.rpartition(".")
    if dot and suffix.lower() not in ("dat", "bin"):
        return name
    base = stem if dot else name
    for signature, extension in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return base + extension
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return base + ".webp"
    return name


def detect_kind(data: list[Any]) -> str:
    for item in data[:50]:
        if isinstance(item, dict):
            if "mapping" in item:
                return "chatgpt"
            if "chat_messages" in item:
                return "claude"
    return "unknown"


# ---------------------------------------------------------------------------
# ChatGPT
# ---------------------------------------------------------------------------

_SKIP_CONTENT = {"user_editable_context", "model_editable_context"}


def _chatgpt_branch(mapping: dict[str, Any], current: Optional[str]) -> list[dict[str, Any]]:
    """Messages on the branch the user last saw (current_node → root), in order."""
    if not current or current not in mapping:
        # Fallback: follow first children from the root.
        roots = [k for k, v in mapping.items() if isinstance(v, dict) and not v.get("parent")]
        chain, node, seen = [], roots[0] if roots else None, set()
        while node and node in mapping and node not in seen:
            seen.add(node)
            chain.append(mapping[node])
            children = mapping[node].get("children") or []
            node = children[0] if children else None
        return chain
    chain, node, seen = [], current, set()
    while node and node in mapping and node not in seen:
        seen.add(node)
        chain.append(mapping[node])
        node = mapping[node].get("parent")
    chain.reverse()
    return chain


def _chatgpt_parts(content: dict[str, Any], source: ExportSource) -> tuple[str, list[Attachment]]:
    ctype = content.get("content_type")
    attachments: list[Attachment] = []
    if ctype == "code":
        language = content.get("language") or ""
        if language == "unknown":
            language = ""
        return f"```{language}\n{content.get('text') or ''}\n```", attachments
    if ctype == "execution_output":
        return f"```text\n{content.get('text') or ''}\n```", attachments
    if ctype == "tether_quote":
        quote = (content.get("text") or "").strip()
        title = content.get("title") or content.get("domain") or "source"
        url = content.get("url") or ""
        body = "\n".join(f"> {line}" for line in quote.splitlines()) if quote else ""
        return f"{body}\n>\n> — [{title}]({url})" if url else body, attachments
    if ctype == "tether_browsing_display":
        return (content.get("result") or content.get("summary") or "").strip(), attachments
    if ctype == "thoughts":
        items = content.get("thoughts") or []
        lines = [f"- {t.get('summary') or ''}: {t.get('content') or ''}".rstrip(": ") for t in items if isinstance(t, dict)]
        return ("*Reasoning:*\n" + "\n".join(lines)) if lines else "", attachments
    if ctype == "reasoning_recap":
        recap = content.get("content") or ""
        return f"*{recap}*" if recap else "", attachments
    texts: list[str] = []
    for part in content.get("parts") or []:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, dict):
            ptype = part.get("content_type")
            if ptype == "image_asset_pointer":
                pointer = str(part.get("asset_pointer") or "")
                token = pointer.split("://", 1)[-1]
                archive_path = source.find_containing(token) if token else None
                attachments.append(Attachment(name=(archive_path or token or "image").rsplit("/", 1)[-1], archive_path=archive_path, kind="image"))
            elif ptype == "audio_transcription":
                texts.append(str(part.get("text") or ""))
            elif "text" in part and isinstance(part.get("text"), str):
                texts.append(part["text"])
            elif ptype:
                texts.append(f"*[{ptype} not shown]*")
    if not texts and not attachments and ctype not in (None, "text", "multimodal_text"):
        texts.append(f"*[{ctype} content not shown]*")
    return "\n\n".join(t for t in texts if t is not None).strip(), attachments


def parse_chatgpt(item: Any, source: ExportSource) -> Optional[Conversation]:
    if not isinstance(item, dict):
        return None
    mapping = item.get("mapping") or {}
    if not isinstance(mapping, dict):
        mapping = {}
    conversation = Conversation(
        id=str(item.get("conversation_id") or item.get("id") or ""),
        title=str(item.get("title") or "Untitled"),
        source="chatgpt",
        created=from_epoch(item.get("create_time")),
        updated=from_epoch(item.get("update_time")),
        project=_chatgpt_project(item),
        model=item.get("default_model_slug"),
    )
    for node in _chatgpt_branch(mapping, item.get("current_node")):
        message = node.get("message") if isinstance(node, dict) else None
        if not isinstance(message, dict):
            continue
        metadata = message.get("metadata") or {}
        if metadata.get("is_visually_hidden_from_conversation"):
            continue
        content = message.get("content") or {}
        if not isinstance(content, dict) or content.get("content_type") in _SKIP_CONTENT:
            continue
        role = str((message.get("author") or {}).get("role") or "assistant")
        text, attachments = _chatgpt_parts(content, source)
        if role == "system" and not text:
            continue
        if not text and not attachments:
            continue
        conversation.messages.append(Message(role=role, text=text, time=from_epoch(message.get("create_time")), attachments=attachments))
    return conversation


def _chatgpt_project(item: dict[str, Any]) -> Optional[str]:
    # Conversations inside a ChatGPT Project carry a project ("g-p-…") gizmo id.
    gizmo = item.get("conversation_template_id") or item.get("gizmo_id")
    if isinstance(gizmo, str) and gizmo.startswith("g-p-"):
        return gizmo
    return None


# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------


def _claude_project_names(source: ExportSource) -> dict[str, str]:
    name = source.find("projects.json")
    if not name:
        return {}
    try:
        data = source.read_json(name)
    except (ValueError, KeyError, OSError):
        return {}
    return {str(p.get("uuid")): str(p.get("name") or p.get("uuid")) for p in data if isinstance(p, dict) and p.get("uuid")}


def _claude_text(message: dict[str, Any]) -> str:
    blocks = message.get("content")
    if isinstance(blocks, list) and blocks:
        parts: list[str] = []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                parts.append(str(block.get("text") or ""))
            elif btype == "thinking":
                thinking = str(block.get("thinking") or "").strip()
                if thinking:
                    parts.append("*Thinking:*\n" + "\n".join(f"> {line}" for line in thinking.splitlines()))
            elif btype == "tool_use":
                parts.append(f"*[tool call: {block.get('name') or 'tool'}]*")
            elif btype == "tool_result":
                parts.append("*[tool result]*")
            elif btype:
                parts.append(f"*[{btype} not shown]*")
        text = "\n\n".join(p for p in parts if p).strip()
        if text:
            return text
    return str(message.get("text") or "").strip()


def parse_claude(item: Any, projects: dict[str, str]) -> Optional[Conversation]:
    if not isinstance(item, dict):
        return None
    project_field = item.get("project")
    project_id = item.get("project_uuid") or (project_field.get("uuid") if isinstance(project_field, dict) else None)
    conversation = Conversation(
        id=str(item.get("uuid") or ""),
        title=str(item.get("name") or "Untitled"),
        source="claude",
        created=from_iso(item.get("created_at")),
        updated=from_iso(item.get("updated_at")),
        project=projects.get(str(project_id), str(project_id)) if project_id else None,
        model=item.get("model"),
    )
    for message in item.get("chat_messages") or []:
        if not isinstance(message, dict):
            continue
        sender = str(message.get("sender") or "assistant")
        role = "user" if sender == "human" else sender
        attachments = [
            Attachment(name=str(a.get("file_name") or "attachment"), kind="file", extracted_text=a.get("extracted_content"))
            for a in (message.get("attachments") or []) if isinstance(a, dict)
        ] + [
            Attachment(name=str(f.get("file_name") or "file"), kind="file")
            for f in (message.get("files") or []) if isinstance(f, dict)
        ]
        text = _claude_text(message)
        if not text and not attachments:
            continue
        conversation.messages.append(Message(role=role, text=text, time=from_iso(message.get("created_at")), attachments=attachments))
    return conversation
