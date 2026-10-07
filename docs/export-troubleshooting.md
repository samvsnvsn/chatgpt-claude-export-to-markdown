# Read a ChatGPT export when conversations.json is missing

Keep an untouched backup of the original export. Work locally on a copy; do not upload private chat history to an online converter.

## Check the files before converting

1. If your export contains conversations-000.json, conversations-001.json and further numbered files, it is split into chunks. Joining their raw text does not produce valid JSON: each file needs to be parsed before merging the conversation lists.
2. If the download arrived as several part-NNNN.zip files, keep all the parts together. Text and attachments can be in different parts.
3. A converter cannot recover conversations or attachments that are absent from the export. An account or desktop-app problem needs help from the provider.

## A free local route

The [open-source converter](https://github.com/samvsnvsn/chatgpt-claude-export-to-markdown) supports ChatGPT and Claude official exports and writes Markdown for tools such as Obsidian. Read the current README for installation, supported formats and limitations.

The [walkthrough](https://samvsnvsn.github.io/chatgpt-claude-export-to-markdown/) includes free ways to search the converted Markdown.

For Windows users who prefer a packaged app, [Chat Export Pro](https://samverse8.gumroad.com/l/chat-export-pro?utm_source=github&utm_medium=owned_guide&utm_campaign=owned-export-guide) adds the offline archive interface and CSV output. Check the product page for the current price and version.

Disclosure: this guide and the linked free and paid tools are maintained by the same creator. No affiliation with OpenAI or Anthropic is claimed.
