"""Synthetic export fixtures (no real user data)."""

import io
import json
import zipfile

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000100e221bc330000000049454e44ae426082"
)


def chatgpt_conversations():
    mapping = {
        "root": {"id": "root", "message": None, "parent": None, "children": ["sys"]},
        "sys": {"id": "sys", "parent": "root", "children": ["u1"], "message": {"author": {"role": "system"}, "content": {"content_type": "text", "parts": [""]}, "metadata": {"is_visually_hidden_from_conversation": True}}},
        "u1": {"id": "u1", "parent": "sys", "children": ["a1", "a1b"], "message": {"author": {"role": "user"}, "create_time": 1700000000.0, "content": {"content_type": "multimodal_text", "parts": [{"content_type": "image_asset_pointer", "asset_pointer": "file-service://file-ABC123", "width": 1, "height": 1}, "What is in this chart?"]}, "metadata": {}}},
        "a1": {"id": "a1", "parent": "u1", "children": [], "message": {"author": {"role": "assistant"}, "create_time": 1700000005.0, "content": {"content_type": "text", "parts": ["OLD BRANCH answer"]}, "metadata": {}}},
        "a1b": {"id": "a1b", "parent": "u1", "children": ["t1"], "message": {"author": {"role": "assistant"}, "create_time": 1700000010.0, "content": {"content_type": "code", "language": "python", "text": "print('hi')"}, "metadata": {}}},
        "t1": {"id": "t1", "parent": "a1b", "children": ["a2"], "message": {"author": {"role": "tool"}, "create_time": 1700000011.0, "content": {"content_type": "execution_output", "text": "hi"}, "metadata": {}}},
        "a2": {"id": "a2", "parent": "t1", "children": [], "message": {"author": {"role": "assistant"}, "create_time": 1700000012.0, "content": {"content_type": "text", "parts": ["The chart shows growth."]}, "metadata": {}}},
    }
    broken = {"title": None, "create_time": None, "mapping": {"x": {"id": "x", "parent": None, "children": [], "message": {"author": None, "content": {"content_type": "mystery_type"}, "metadata": None}}}, "current_node": "x"}
    return [
        {"title": "Chart: Q3 / Q4?", "create_time": 1700000000.0, "update_time": 1700000100.0, "mapping": mapping, "current_node": "a2", "conversation_id": "c-1", "default_model_slug": "gpt-4o", "conversation_template_id": "g-p-project123"},
        {"title": "CON", "create_time": 1690000000.0, "mapping": {"n": {"id": "n", "parent": None, "children": [], "message": {"author": {"role": "user"}, "content": {"content_type": "text", "parts": ["hello"]}, "metadata": {}}}}, "current_node": "n", "conversation_id": "c-2"},
        broken,
    ]


def chatgpt_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("conversations.json", json.dumps(chatgpt_conversations()))
        archive.writestr("file-ABC123-chart.png", PNG)
        archive.writestr("user.json", "{}")
    return buffer.getvalue()


def claude_conversations():
    return [
        {
            "uuid": "cl-1", "name": "Refactor plan", "created_at": "2026-09-20T10:00:00.000000Z", "updated_at": "2026-09-20T11:00:00Z", "project_uuid": "p-1",
            "chat_messages": [
                {"sender": "human", "text": "Please review", "created_at": "2026-09-20T10:00:00Z", "attachments": [{"file_name": "notes.txt", "extracted_content": "line one"}], "files": [{"file_name": "diagram.png"}]},
                {"sender": "assistant", "created_at": "2026-09-20T10:01:00Z", "text": "fallback text", "content": [{"type": "thinking", "thinking": "consider tests"}, {"type": "text", "text": "Here is the plan."}, {"type": "tool_use", "name": "search"}]},
                {"sender": "assistant", "content": [], "text": ""},
            ],
        },
    ]


def claude_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("data-2026/conversations.json", json.dumps(claude_conversations()))
        archive.writestr("data-2026/projects.json", json.dumps([{"uuid": "p-1", "name": "Website rebuild"}]))
    return buffer.getvalue()
