"""Command line: chat-export <export.zip | conversations.json> -o <output folder>."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from . import __version__
from .loaders import load_export
from .markdown import write_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chat-export",
        description="Convert your official ChatGPT or Claude data export (ZIP or conversations.json) into Markdown files. Runs offline.",
    )
    parser.add_argument("export", help="path to the export .zip (or conversations.json, or the unzipped folder)")
    parser.add_argument("-o", "--out", default="chat-export-markdown", help="output folder (default: chat-export-markdown)")
    parser.add_argument("--since", help="only conversations created on/after YYYY-MM-DD")
    parser.add_argument("--flat", action="store_true", help="do not group project conversations into folders")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    # Windows consoles default to legacy code pages: never crash on a character.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    try:
        conversations, source = load_export(args.export)
    except (FileNotFoundError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.since:
        try:
            since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print("error: --since must be YYYY-MM-DD", file=sys.stderr)
            return 2
        conversations = [c for c in conversations if c.created and c.created >= since]
    if not conversations:
        print("No conversations found in this export.", file=sys.stderr)
        source.close()
        return 1
    written = write_markdown(conversations, source, args.out, by_project=not args.flat)
    source.close()
    messages = sum(len(c.messages) for c in conversations)
    print(f"Converted {len(conversations)} conversations ({messages} messages) -> {args.out} ({len(written)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
