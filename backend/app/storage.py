"""SQLite é a fonte de verdade do MVP; gravações correlatas são atômicas."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DDL = '''
CREATE TABLE IF NOT EXISTS ticket_numbers (n INTEGER PRIMARY KEY AUTOINCREMENT);
CREATE TABLE IF NOT EXISTS tickets (
  id TEXT PRIMARY KEY, public_id TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
  description TEXT NOT NULL, affected_service TEXT, reported_impact TEXT,
  impact_scope TEXT NOT NULL DEFAULT 'unknown',
  ticket_status TEXT NOT NULL DEFAULT 'created',
  analysis_status TEXT NOT NULL DEFAULT 'pending',
  sync_status TEXT NOT NULL DEFAULT 'pending',
  effective_priority TEXT, resolution_notes TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  resolved_at TEXT, closed_at TEXT
);
CREATE TABLE IF NOT EXISTS analysis_results (
  id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets(id),
  event_id TEXT NOT NULL UNIQUE, attempt_number INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL, category TEXT, suggested_priority TEXT,
  summary TEXT, recommendations_json TEXT,
  review_reason TEXT, requires_human_review INTEGER,
  effective_priority TEXT, model_name TEXT, provider_model TEXT, prompt_version TEXT,
  error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox_events (
  event_id TEXT PRIMARY KEY,
  ticket_id TEXT NOT NULL REFERENCES tickets(id),
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT NOT NULL,
  last_error TEXT, created_at TEXT NOT NULL, delivered_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_outbox_pending ON outbox_events(state, next_attempt_at);
CREATE TABLE IF NOT EXISTS ticket_status_history (
  id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets(id),
  previous_status TEXT, new_status TEXT NOT NULL,
  actor_type TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS priority_review_history (
  id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets(id),
  previous_priority TEXT, new_priority TEXT NOT NULL,
  actor_type TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS external_syncs (
  id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets(id),
  provider TEXT NOT NULL, external_key TEXT NOT NULL,
  status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT, updated_at TEXT NOT NULL,
  UNIQUE(ticket_id, provider)
);
'''


def connect(path):
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=10000')
    return conn


def init_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript(DDL)
        # Migração aditiva e idempotente: preserva o volume SQLite já existente.
        columns={r[1] for r in conn.execute('PRAGMA table_info(analysis_results)')}
        if 'provider_model' not in columns:
            conn.execute('ALTER TABLE analysis_results ADD COLUMN provider_model TEXT')
    finally:
        conn.close()


@contextmanager
def session(path, write=False):
    conn = connect(path)
    try:
        if write:
            conn.execute('BEGIN IMMEDIATE')
        yield conn
        if write:
            conn.commit()
    except Exception:
        if write:
            conn.rollback()
        raise
    finally:
        conn.close()


def row_as_dict(row):
    return dict(row) if row is not None else None
