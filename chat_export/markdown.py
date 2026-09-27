"""Write conversations as Markdown files (one per conversation) plus an index."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .loaders import ExportSource, asset_file_name
from .model import Conversation

ROLE_LABEL = {"user": "You", "assistant": "Assistant", "tool": "Tool", "system": "System"}
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_filename(title: str, when: Optional[datetime], used: set[str], max_len: int = 80) -> str:
    """Windows-safe, readable, unique file stem: 'YYYY-MM-DD Title'."""
    stem = _INVALID.sub(" ", title).strip().strip(".") or "Untitled"
    stem = re.sub(r"\s+", " ", stem)[:max_len].rstrip(" .")
    if stem.upper() in _RESERVED:
        stem = f"_{stem}"
    if when:
        stem = f"{when:%Y-%m-%d} {stem}"
    candidate, counter = stem, 2
    while candidate.lower() in used:
        candidate = f"{stem} ({counter})"
        counter += 1
    used.add(candidate.lower())
    return candidate


def _yaml(value: object) -> str:
    text = "" if value is None else str(value)
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_markdown(conversation: Conversation, asset_links: dict[str, str]) -> str:
    lines = [
        "---",
        f"title: {_yaml(conversation.title)}",
        f"source: {conversation.source}",
        f"id: {_yaml(conversation.id)}",
        f"created: {conversation.created.isoformat() if conversation.created else ''}",
        f"updated: {conversation.updated.isoformat() if conversation.updated else ''}",
    ]
    if conversation.project:
        lines.append(f"project: {_yaml(conversation.project)}")
    if conversation.model:
        lines.append(f"model: {_yaml(conversation.model)}")
    lines += [f"messages: {len(conversation.messages)}", "---", "", f"# {conversation.title}", ""]
    for message in conversation.messages:
        label = ROLE_LABEL.get(message.role, message.role.title())
        stamp = f" · {message.time:%Y-%m-%d %H:%M} UTC" if message.time else ""
        lines += [f"## {label}{stamp}", ""]
        if message.text:
            lines += [message.text, ""]
        for attachment in message.attachments:
            link = asset_links.get(attachment.archive_path or "")
            if attachment.kind == "image" and link:
                lines += [f"![{attachment.name}]({link})", ""]
            elif link:
                lines += [f"📎 [{attachment.name}]({link})", ""]
            else:
                lines += [f"📎 {attachment.name} *(not included in the export)*", ""]
            if attachment.extracted_text:
                lines += ["<details><summary>Attached text</summary>", "", "```", attachment.extracted_text.strip(), "```", "", "</details>", ""]
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(conversations: list[Conversation], source: ExportSource, out_dir: str | Path, by_project: bool = True) -> list[Path]:
    """Write one .md per conversation (grouped in project folders) plus index.md. Returns written paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    assets_dir = out / "assets"
    written: list[Path] = []
    used_by_folder: dict[str, set[str]] = {}
    index_rows: list[tuple[str, str, str, str]] = []
    for conversation in sorted(conversations, key=lambda c: c.created.isoformat() if c.created else "", reverse=True):
        folder = out
        if by_project and conversation.project:
            folder = out / "projects" / safe_filename(conversation.project, None, set(), 60)
        folder.mkdir(parents=True, exist_ok=True)
        used = used_by_folder.setdefault(str(folder), set())
        stem = safe_filename(conversation.title, conversation.created, used)
        asset_links: dict[str, str] = {}
        for message in conversation.messages:
            for attachment in message.attachments:
                if attachment.archive_path and attachment.archive_path not in asset_links:
                    data = source.read_bytes(attachment.archive_path)
                    target = assets_dir / asset_file_name(attachment.archive_path, data)
                    if not target.exists():
                        assets_dir.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                    asset_links[attachment.archive_path] = Path("../" * (len(folder.relative_to(out).parts)) + "assets/" + target.name).as_posix()
        path = folder / f"{stem}.md"
        path.write_text(render_markdown(conversation, asset_links), encoding="utf-8")
        written.append(path)
        index_rows.append((conversation.created.strftime("%Y-%m-%d") if conversation.created else "", conversation.source, conversation.project or "", path.relative_to(out).as_posix()))
    index = ["# Conversation index", "", f"{len(index_rows)} conversations.", "", "| Date | Source | Project | Conversation |", "|---|---|---|---|"]
    for date, src, project, rel in index_rows:
        name = rel.rsplit("/", 1)[-1][:-3]
        index.append(f"| {date} | {src} | {project} | [{name}](<{rel}>) |")
    (out / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    written.append(out / "index.md")
    return written
