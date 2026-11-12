import pytest
from pathlib import Path
from daymark.db.database import Database
from daymark.db.models import Task
from datetime import datetime


def test_create_note(tmp_db, today):
    note = tmp_db.get_or_create_note(today)
    assert note.note_date == today
    assert note.id is not None
    assert note.content == ''


def test_idempotent_create(tmp_db, today):
    note1 = tmp_db.get_or_create_note(today)
    note2 = tmp_db.get_or_create_note(today)
    assert note1.id == note2.id


def test_update_content(tmp_db, today):
    note = tmp_db.get_or_create_note(today)
    tmp_db.update_note_content(note.id, 'Hello World')
    note2 = tmp_db.get_note_for_date(today)
    assert note2.content == 'Hello World'


def test_database_migration(tmp_path):
    db = Database(tmp_path / 'test.db')
    cur = db._conn.cursor()
    cur.execute("SELECT version FROM schema_migrations")
    versions = [row[0] for row in cur.fetchall()]
    cur.close()
    assert 1 in versions
    db.close()


def test_integrity(tmp_db):
    assert tmp_db.integrity_check() is True


def test_create_task(tmp_db, today):
    task = Task(
        id=None, description='Test task', original_date=today,
        due_date=None, completed=False, completed_at=None,
        priority=0, created_at='', updated_at=''
    )
    created = tmp_db.create_task(task)
    assert created.id is not None
    assert created.description == 'Test task'
    assert created.original_date == today


def test_update_task(tmp_db, today):
    task = Task(
        id=None, description='Test', original_date=today,
        due_date=None, completed=False, completed_at=None,
        priority=0, created_at='', updated_at=''
    )
    task = tmp_db.create_task(task)
    task.completed = True
    task.completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tmp_db.update_task(task)
    retrieved = tmp_db.get_task(task.id)
    assert retrieved.completed is True


def test_get_pending_tasks_before(tmp_db, today, yesterday):
    task = Task(
        id=None, description='Pending', original_date=yesterday,
        due_date=None, completed=False, completed_at=None,
        priority=0, created_at='', updated_at=''
    )
    tmp_db.create_task(task)
    pending = tmp_db.get_pending_tasks_before(today)
    assert len(pending) == 1
    assert pending[0].original_date == yesterday


def test_no_pending_tasks_on_completion(tmp_db, today, yesterday):
    task = Task(
        id=None, description='Pending', original_date=yesterday,
        due_date=None, completed=False, completed_at=None,
        priority=0, created_at='', updated_at=''
    )
    task = tmp_db.create_task(task)
    task.completed = True
    task.completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tmp_db.update_task(task)
    pending = tmp_db.get_pending_tasks_before(today)
    assert len(pending) == 0


def test_delete_task(tmp_db, today):
    task = Task(
        id=None, description='Delete me', original_date=today,
        due_date=None, completed=False, completed_at=None,
        priority=0, created_at='', updated_at=''
    )
    task = tmp_db.create_task(task)
    tmp_db.delete_task(task.id)
    assert tmp_db.get_task(task.id) is None


def test_settings(tmp_db):
    tmp_db.settings_set('theme', 'dark')
    assert tmp_db.settings_get('theme') == 'dark'
    assert tmp_db.settings_get('nonexistent', 'default') == 'default'


def test_backup(tmp_db, tmp_path):
    tmp_db.get_or_create_note('2026-01-01')
    backup_path = tmp_path / 'backup' / 'daymark_backup.db'
    tmp_db.backup(backup_path)
    assert backup_path.exists()
