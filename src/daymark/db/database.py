import sqlite3
import logging
import shutil
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from .models import DailyNote, Task

logger = logging.getLogger(__name__)

MIGRATION_001 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS daily_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_date TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    original_date TEXT NOT NULL,
    due_date TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_original_date ON tasks(original_date);
CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed);
CREATE INDEX IF NOT EXISTS idx_daily_notes_date ON daily_notes(note_date)
"""

MIGRATION_002_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    content,
    content='daily_notes',
    content_rowid='id',
    tokenize='porter ascii'
);

CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
    description,
    content='tasks',
    content_rowid='id',
    tokenize='porter ascii'
);

CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON daily_notes BEGIN
    INSERT INTO notes_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON daily_notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON daily_notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, content) VALUES ('delete', old.id, old.content);
    INSERT INTO notes_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS tasks_ai AFTER INSERT ON tasks BEGIN
    INSERT INTO tasks_fts(rowid, description) VALUES (new.id, new.description);
END;
CREATE TRIGGER IF NOT EXISTS tasks_ad AFTER DELETE ON tasks BEGIN
    INSERT INTO tasks_fts(tasks_fts, rowid, description) VALUES ('delete', old.id, old.description);
END;
CREATE TRIGGER IF NOT EXISTS tasks_au AFTER UPDATE ON tasks BEGIN
    INSERT INTO tasks_fts(tasks_fts, rowid, description) VALUES ('delete', old.id, old.description);
    INSERT INTO tasks_fts(rowid, description) VALUES (new.id, new.description);
END
"""

MIGRATION_003_BODY = """
ALTER TABLE tasks ADD COLUMN body TEXT NOT NULL DEFAULT ''
"""

MIGRATION_004_SOURCE = """
ALTER TABLE tasks ADD COLUMN source TEXT NOT NULL DEFAULT 'direct'
"""

MIGRATIONS = [
    (1, MIGRATION_001),
    (2, MIGRATION_002_FTS),
    (3, MIGRATION_003_BODY),
    (4, MIGRATION_004_SOURCE),
]


class Database:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._fts_available = True
        self.connect()
        self._run_migrations()

    def connect(self):
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA synchronous=NORMAL")

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    @contextmanager
    def cursor(self):
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cur.close()

    def _run_migrations(self):
        # Ensure schema_migrations table exists first
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        self._conn.commit()

        applied = {row[0] for row in self._conn.execute("SELECT version FROM schema_migrations")}

        for version, sql in MIGRATIONS:
            if version in applied:
                continue
            try:
                # executescript handles multi-statement DDL correctly and auto-commits
                self._conn.executescript(sql)
                self._conn.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)", (version,)
                )
                self._conn.commit()
                logger.info(f"Applied migration {version}")
            except sqlite3.OperationalError as e:
                if 'fts5' in str(e).lower() or 'no such module' in str(e).lower():
                    logger.warning(f"FTS5 not available, skipping migration {version}: {e}")
                    self._fts_available = False
                    # Mark as applied anyway so we don't retry
                    self._conn.execute(
                        "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (version,)
                    )
                    self._conn.commit()
                else:
                    raise

    def _now(self) -> str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # --- Daily Notes ---

    def get_or_create_note(self, date_str: str) -> DailyNote:
        with self.cursor() as cur:
            cur.execute("SELECT * FROM daily_notes WHERE note_date = ?", (date_str,))
            row = cur.fetchone()
            if row:
                return DailyNote(**dict(row))
            now = self._now()
            cur.execute(
                "INSERT INTO daily_notes(note_date, content, created_at, updated_at) VALUES (?, '', ?, ?)",
                (date_str, now, now)
            )
            note_id = cur.lastrowid
        return DailyNote(id=note_id, note_date=date_str, content='', created_at=now, updated_at=now)

    def get_note_for_date(self, date_str: str) -> Optional[DailyNote]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM daily_notes WHERE note_date = ?", (date_str,))
        row = cur.fetchone()
        cur.close()
        if row:
            return DailyNote(**dict(row))
        return None

    def update_note_content(self, note_id: int, content: str):
        now = self._now()
        with self.cursor() as cur:
            cur.execute(
                "UPDATE daily_notes SET content = ?, updated_at = ? WHERE id = ?",
                (content, now, note_id)
            )

    def get_all_dates_with_activity(self) -> dict:
        result = {}
        cur = self._conn.cursor()
        # Notes
        cur.execute("SELECT note_date FROM daily_notes")
        for row in cur.fetchall():
            d = row[0]
            if d not in result:
                result[d] = {'has_pending': False, 'task_count': 0, 'pending_count': 0}
        # Tasks with pending counts
        cur.execute(
            "SELECT original_date, completed, COUNT(*) as cnt "
            "FROM tasks GROUP BY original_date, completed"
        )
        for row in cur.fetchall():
            d, completed, cnt = row[0], row[1], row[2]
            if d not in result:
                result[d] = {'has_pending': False, 'task_count': 0, 'pending_count': 0}
            result[d]['task_count'] += cnt
            if not completed:
                result[d]['has_pending'] = True
                result[d]['pending_count'] += cnt
        cur.close()
        return result

    # --- Tasks ---

    def create_task(self, task: Task) -> Task:
        now = self._now()
        with self.cursor() as cur:
            cur.execute(
                """INSERT INTO tasks
                   (description, body, source, original_date, due_date, completed, completed_at, priority, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 0, NULL, ?, ?, ?)""",
                (task.description, task.body, task.source,
                 task.original_date, task.due_date, task.priority, now, now)
            )
            task.id = cur.lastrowid
            task.created_at = now
            task.updated_at = now
            task.completed = False
            task.completed_at = None
        return task

    def update_task(self, task: Task):
        now = self._now()
        with self.cursor() as cur:
            cur.execute(
                """UPDATE tasks SET
                   description=?, body=?, source=?, due_date=?, completed=?, completed_at=?, priority=?, updated_at=?
                   WHERE id=?""",
                (task.description, task.body, task.source, task.due_date,
                 1 if task.completed else 0,
                 task.completed_at, task.priority, now, task.id)
            )
            task.updated_at = now

    def get_task(self, task_id: int) -> Optional[Task]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        d = dict(row)
        d['completed'] = bool(d['completed'])
        return Task(**d)

    def get_tasks_for_date(self, date_str: str) -> list:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM tasks WHERE original_date = ? ORDER BY created_at ASC",
            (date_str,)
        )
        rows = cur.fetchall()
        cur.close()
        result = []
        for row in rows:
            d = dict(row)
            d['completed'] = bool(d['completed'])
            result.append(Task(**d))
        return result

    def get_pending_tasks_before(self, date_str: str) -> list:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM tasks WHERE completed = 0 AND original_date < ? ORDER BY original_date DESC, created_at ASC",
            (date_str,)
        )
        rows = cur.fetchall()
        cur.close()
        result = []
        for row in rows:
            d = dict(row)
            d['completed'] = bool(d['completed'])
            result.append(Task(**d))
        return result

    def get_dates_with_pending_tasks(self) -> list:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT DISTINCT original_date FROM tasks WHERE completed = 0 ORDER BY original_date"
        )
        rows = cur.fetchall()
        cur.close()
        return [row[0] for row in rows]

    def delete_task(self, task_id: int):
        with self.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    # --- Settings ---

    def settings_get(self, key: str, default: str = '') -> str:
        cur = self._conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else default

    def settings_set(self, key: str, value: str):
        with self.cursor() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                (key, value)
            )

    # --- Search ---

    def search_notes(self, query: str) -> list:
        if not self._fts_available:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT id, note_date, content FROM daily_notes WHERE content LIKE ? LIMIT 50",
                (f'%{query}%',)
            )
            rows = cur.fetchall()
            cur.close()
            return [{'id': r[0], 'note_date': r[1], 'snippet': r[2][:200]} for r in rows]

        try:
            cur = self._conn.cursor()
            cur.execute(
                """SELECT dn.id, dn.note_date,
                   snippet(notes_fts, 0, '<b>', '</b>', '...', 20) AS snippet
                   FROM notes_fts
                   JOIN daily_notes dn ON dn.id = notes_fts.rowid
                   WHERE notes_fts MATCH ?
                   ORDER BY rank
                   LIMIT 50""",
                (query,)
            )
            rows = cur.fetchall()
            cur.close()
            return [{'id': r[0], 'note_date': r[1], 'snippet': r[2]} for r in rows]
        except sqlite3.OperationalError as e:
            logger.warning(f"FTS search failed: {e}")
            return []

    def search_tasks(self, query: str) -> list:
        if not self._fts_available:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT id, description, original_date, completed FROM tasks WHERE description LIKE ? LIMIT 50",
                (f'%{query}%',)
            )
            rows = cur.fetchall()
            cur.close()
            return [{'id': r[0], 'description': r[1], 'original_date': r[2], 'completed': bool(r[3])} for r in rows]

        try:
            cur = self._conn.cursor()
            cur.execute(
                """SELECT t.id, t.description, t.original_date, t.completed
                   FROM tasks_fts
                   JOIN tasks t ON t.id = tasks_fts.rowid
                   WHERE tasks_fts MATCH ?
                   ORDER BY rank
                   LIMIT 50""",
                (query,)
            )
            rows = cur.fetchall()
            cur.close()
            return [{'id': r[0], 'description': r[1], 'original_date': r[2], 'completed': bool(r[3])} for r in rows]
        except sqlite3.OperationalError as e:
            logger.warning(f"FTS search failed: {e}")
            return []

    def backup(self, backup_path: Path):
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(self.db_path), str(backup_path))
        logger.info(f"Backup created at {backup_path}")

    def integrity_check(self) -> bool:
        cur = self._conn.cursor()
        cur.execute("PRAGMA integrity_check")
        result = cur.fetchone()
        cur.close()
        return result and result[0] == 'ok'
