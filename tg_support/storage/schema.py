CURRENT_SCHEMA_VERSION = 4

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  input TEXT NOT NULL UNIQUE,
  telegram_id TEXT,
  title TEXT,
  type TEXT,
  resolved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  telegram_id TEXT UNIQUE,
  username TEXT,
  display_name TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL REFERENCES chats(id),
  telegram_message_id INTEGER NOT NULL,
  author_id INTEGER REFERENCES users(id),
  author_username TEXT,
  sent_at TEXT NOT NULL,
  text TEXT NOT NULL,
  reply_to_message_id INTEGER,
  source_ref TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT NOT NULL UNIQUE,
  title TEXT,
  text TEXT NOT NULL,
  fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  rendered INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'ok',
  error TEXT
);

CREATE TABLE IF NOT EXISTS manual_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  text TEXT NOT NULL,
  effective_date TEXT NOT NULL,
  expires_date TEXT,
  caveats TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_type TEXT NOT NULL CHECK(source_type IN ('telegram','web','manual','exchange')),
  source_id INTEGER NOT NULL,
  ordinal INTEGER NOT NULL,
  text TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_type, source_id, ordinal)
);

CREATE TABLE IF NOT EXISTS index_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  embedding_model TEXT NOT NULL,
  index_version TEXT NOT NULL,
  source_max_chunk_id INTEGER NOT NULL,
  source_signature TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  chunk_id INTEGER NOT NULL UNIQUE REFERENCES chunks(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL,
  source_id INTEGER NOT NULL,
  ordinal INTEGER NOT NULL,
  text TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  source_updated_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS fts_documents USING fts5(
  text,
  content='documents',
  content_rowid='id',
  tokenize = "unicode61 tokenchars '-_'"
);

CREATE TABLE IF NOT EXISTS support_exchanges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK(status IN ('answered_by_operator','peer_response_only','ambiguous','unanswered')),
  confidence REAL NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS support_exchange_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  exchange_id INTEGER NOT NULL REFERENCES support_exchanges(id) ON DELETE CASCADE,
  message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('requester','operator_response','peer_response','ambiguous_response','context')),
  authority TEXT NOT NULL CHECK(authority IN ('operator','peer','ambiguous','none')),
  ordinal INTEGER NOT NULL,
  UNIQUE(exchange_id, message_id, role)
);

CREATE TABLE IF NOT EXISTS drafts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_chat TEXT NOT NULL,
  target_user TEXT,
  target_message_id INTEGER,
  message_text TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS confirmations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id INTEGER NOT NULL REFERENCES drafts(id),
  token TEXT NOT NULL UNIQUE,
  action TEXT NOT NULL CHECK(action IN ('post','cancel')),
  consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS post_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id INTEGER NOT NULL REFERENCES drafts(id),
  confirmation_id INTEGER REFERENCES confirmations(id),
  status TEXT NOT NULL,
  telegram_message_id INTEGER,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_author_sent_at ON messages(author_username, sent_at);
CREATE INDEX IF NOT EXISTS idx_messages_telegram_message_id ON messages(telegram_message_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat_message_id ON messages(chat_id, telegram_message_id);
CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at);
"""
