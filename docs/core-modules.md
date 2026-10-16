# Core Modules

The core package provides safe Markdown writes, comment-preserving YAML frontmatter updates, three-version topic notes, and local application configuration.

## Markdown notes

`file_writer.create_note(path, text)` creates a note atomically and refuses to replace an existing file. `update_note(path, body)` replaces the body while keeping a YAML frontmatter block. Passing a callable instead transforms the complete document and enables structured updates. `append_to_note(path, block)` appends a block once and returns whether it changed the file. Updates detect changes made after the original read and raise `NoteConflictError`; inspect the current document before retrying. File, permissions, disk-full, encoding and conflict failures include the path.

## YAML frontmatter

`yaml_utils.parse_frontmatter(text)` parses string, sequence, date and boolean values. `update_frontmatter(path, fields)` changes only named fields and uses ruamel.yaml round-trip mode to retain unrelated keys and comments. Missing, malformed or non-mapping frontmatter is reported without changing the note.

## Topic notes

`note_manager.create_topic_notes(vault, subject, topic, initial_content="")` creates the dated topic folder with `01-学习前版.md`, `02-交流后版.md` and `03-AI参考版.md`. Existing folders are never overwritten. The update functions preserve frontmatter, and AI reference additions are idempotent.

## Configuration and credentials

Configuration defaults to `~/.config/daily-knowledge-learning/config.json`; set `DAILY_KNOWLEDGE_LEARNING_CONFIG` for an alternate location. Values are validated on read and write. Config writes are atomic and permissions are restricted to the current user (POSIX mode 0600 or a Windows user-only ACL). OpenAI and Anthropic credentials go through the `keyring` API, which uses Windows Credential Manager on Windows; they are never serialized into the JSON config. On systems without a secure keyring backend, keyring errors are surfaced to the caller.
