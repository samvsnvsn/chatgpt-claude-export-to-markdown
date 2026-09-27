# ChatGPT & Claude export to Markdown

Convert your **official ChatGPT or Claude data export** (the ZIP you download from *Settings → Data controls → Export data*) into clean, readable **Markdown files**: one file per conversation, with images, dates and project folders.

- **Offline and private.** It reads the ZIP on your computer. No login, no browser extension, no uploads.
- **ChatGPT and Claude** exports, auto-detected.
- **Follows the branch you actually saw.** Edited or regenerated messages don't duplicate the conversation.
- **Keeps what matters:** code blocks (with language), tool/code output, quotes, uploaded and generated **images** (copied into `assets/`), Claude attachments' extracted text, and Claude "thinking" blocks.
- **Project folders:** ChatGPT Projects and Claude Projects each get their own folder (`--flat` to disable).
- **Obsidian-friendly YAML front-matter:** title, source, id, created, updated, project, model, message count.
- **Windows-safe file names** (`2026-09-20 Refactor plan.md`), plus an `index.md` table of every conversation.
- **Robust:** unexpected or new content types are kept as a visible note, never a crash.

Python 3.9+ standard library only; no dependencies.

## Usage

```bash
pip install git+https://github.com/samvsnvsn/chatgpt-claude-export-to-markdown
chat-export ~/Downloads/chatgpt-export.zip -o my-chats
```

or, without installing:

```bash
python -m chat_export export.zip -o my-chats
```

Options:

| Option | Meaning |
|---|---|
| `-o, --out FOLDER` | output folder (default `chat-export-markdown`) |
| `--since YYYY-MM-DD` | only conversations created on/after this date |
| `--flat` | don't group project conversations into folders |

It also accepts a loose `conversations.json` or an unzipped export folder.

### Example output

```
my-chats/
  index.md
  2026-09-18 Trip planning.md
  projects/
    Website rebuild/
      2026-09-20 Refactor plan.md
  assets/
    file-AbC123-chart.png
```

```markdown
---
title: "Refactor plan"
source: claude
created: 2026-09-20T10:00:00+00:00
project: "Website rebuild"
messages: 2
---

# Refactor plan

## You · 2026-09-20 10:00 UTC

Please review
```

## Getting your export

- **ChatGPT:** Settings → Data controls → Export data. You'll get an email with a ZIP.
- **Claude:** Settings → Privacy → Export data. You'll get an email with a ZIP.

## Want it without Python?

**[Chat Export Pro for Windows](https://samverse8.gumroad.com/l/chat-export-pro)** is the same engine as a double-click app (no Python needed). It adds:

- a **single-file searchable offline archive** (`archive.html`) with instant search, source/project filters and dark mode;
- a **`conversations.csv`** index that opens in Excel;
- a simple window for choosing the ZIP and output folder.

It costs a few dollars and supports development. This free tool stays fully functional.

## Limitations

- Exports contain only what the provider includes. Claude exports don't include the bytes of uploaded files; their names and extracted text are kept.
- ChatGPT Project folders are named by project id, because the export doesn't include project names.
- Voice audio isn't included; transcriptions are.

## License

MIT. See [LICENSE](LICENSE). Not affiliated with OpenAI or Anthropic; "ChatGPT" and "Claude" are trademarks of their respective owners.
