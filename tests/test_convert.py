import tempfile
import unittest
import zipfile
from pathlib import Path

from chat_export.cli import main
from chat_export.loaders import load_export
from chat_export.markdown import safe_filename
from tests.fixtures import chatgpt_split_zips, chatgpt_zip, claude_zip


class ChatGPTExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.zip = self.root / "chatgpt-export.zip"
        self.zip.write_bytes(chatgpt_zip())

    def tearDown(self):
        self.tmp.cleanup()

    def test_follows_the_current_branch_and_keeps_code_tool_output_and_images(self):
        conversations, source = load_export(self.zip)
        chart = next(c for c in conversations if c.id == "c-1")
        texts = [m.text for m in chart.messages]
        self.assertNotIn("OLD BRANCH answer", "\n".join(texts))
        self.assertEqual([m.role for m in chart.messages], ["user", "assistant", "tool", "assistant"])
        self.assertIn("```python\nprint('hi')\n```", texts[1])
        self.assertEqual(chart.messages[0].attachments[0].archive_path, "file-ABC123-chart.png")
        self.assertEqual(chart.project, "g-p-project123")
        source.close()

    def test_broken_or_unknown_content_never_crashes_and_is_marked(self):
        conversations, source = load_export(self.zip)
        broken = next(c for c in conversations if c.title == "Untitled")
        self.assertIn("mystery_type", broken.messages[0].text)
        source.close()

    def test_cli_writes_markdown_images_frontmatter_and_index(self):
        out = self.root / "out"
        self.assertEqual(main([str(self.zip), "-o", str(out)]), 0)
        chart = next((out / "projects").rglob("*Chart*.md"))
        text = chart.read_text(encoding="utf-8")
        self.assertTrue(text.startswith('---\ntitle: "Chart: Q3 / Q4?"\nsource: chatgpt'))
        self.assertIn("![file-ABC123-chart.png](../../assets/file-ABC123-chart.png)", text)
        self.assertTrue((out / "assets" / "file-ABC123-chart.png").exists())
        self.assertIn("2023-11-14 Chart Q3 Q4", chart.name)
        index = (out / "index.md").read_text(encoding="utf-8")
        self.assertIn("3 conversations.", index)
        self.assertTrue(any(p.name.startswith("2023-07-22 _CON") for p in out.glob("*.md")))

    def test_since_filter_and_flat_layout(self):
        out = self.root / "flat"
        self.assertEqual(main([str(self.zip), "-o", str(out), "--flat", "--since", "2023-11-01"]), 0)
        self.assertFalse((out / "projects").exists())
        self.assertEqual(len([p for p in out.glob("*.md") if p.name != "index.md"]), 1)

    def test_loose_conversations_json_is_accepted(self):
        folder = self.root / "unzipped"
        folder.mkdir()
        with zipfile.ZipFile(self.zip) as archive:
            archive.extractall(folder)
        conversations, source = load_export(folder / "conversations.json")
        self.assertEqual(len(conversations), 3)
        first = next(c for c in conversations if c.id == "c-1")
        self.assertEqual(first.messages[0].attachments[0].archive_path, "file-ABC123-chart.png")
        source.close()


class ClaudeExportTests(unittest.TestCase):
    def test_claude_zip_with_top_level_folder_projects_attachments_and_thinking(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claude.zip"
            path.write_bytes(claude_zip())
            conversations, source = load_export(path)
            conversation = conversations[0]
            self.assertEqual(conversation.source, "claude")
            self.assertEqual(conversation.project, "Website rebuild")
            self.assertEqual(len(conversation.messages), 2)  # empty message dropped
            self.assertEqual(conversation.messages[0].role, "user")
            self.assertEqual([a.name for a in conversation.messages[0].attachments], ["notes.txt", "diagram.png"])
            self.assertIn("Here is the plan.", conversation.messages[1].text)
            self.assertIn("*Thinking:*", conversation.messages[1].text)
            source.close()
            out = Path(tmp) / "out"
            self.assertEqual(main([str(path), "-o", str(out)]), 0)
            md = next((out / "projects" / "Website rebuild").glob("*.md")).read_text(encoding="utf-8")
            self.assertIn("line one", md)
            self.assertIn("diagram.png *(not included in the export)*", md)


class FilenameTests(unittest.TestCase):
    def test_windows_safe_unique_names(self):
        used: set[str] = set()
        self.assertEqual(safe_filename('a<b>:"c"/d\\e|f?g*', None, used), "a b c d e f g")
        self.assertEqual(safe_filename("NUL", None, used), "_NUL")
        self.assertEqual(safe_filename("same", None, used), "same")
        self.assertEqual(safe_filename("same", None, used), "same (2)")

    def test_missing_export_gives_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main([str(Path(tmp) / "nope.zip")]), 2)


class SplitChatGPTExportTests(unittest.TestCase):
    """Current (2026) ChatGPT exports: conversations-NNN.json, .dat images, several -part-NNNN.zip files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        part1, part2 = chatgpt_split_zips()
        (self.root / "Conversations_abc-chatgpt-0001-part-0001.zip").write_bytes(part1)
        (self.root / "Conversations_abc-chatgpt-0001-part-0002.zip").write_bytes(part2)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_all_conversation_chunks_and_images_from_other_parts(self):
        for chosen in ("part-0001", "part-0002"):  # either part may be chosen
            conversations, source = load_export(self.root / f"Conversations_abc-chatgpt-0001-{chosen}.zip")
            try:
                self.assertEqual(sorted(c.title for c in conversations), ["First chunk", "Second chunk with image"])
                image = next(c for c in conversations if c.id == "n2").messages[0].attachments[0]
                self.assertEqual(image.archive_path, "file_00000000aa11bb22.dat")
            finally:
                source.close()

    def test_dat_images_get_their_real_extension_in_markdown(self):
        out = self.root / "out"
        self.assertEqual(main([str(self.root / "Conversations_abc-chatgpt-0001-part-0001.zip"), "-o", str(out)]), 0)
        self.assertTrue((out / "assets" / "file_00000000aa11bb22.png").exists())
        note = next(out.glob("*Second chunk with image.md")).read_text(encoding="utf-8")
        self.assertIn("assets/file_00000000aa11bb22.png", note)

    def test_single_part_zip_with_chunks(self):
        part1, _ = chatgpt_split_zips()
        single = self.root / "export.zip"
        single.write_bytes(part1)
        conversations, source = load_export(single)
        source.close()
        self.assertEqual(len(conversations), 2)


if __name__ == "__main__":
    unittest.main()
