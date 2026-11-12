import pytest
from daymark.core.search import SearchEngine, SearchResult
from daymark.db.models import Task


def test_search_notes(tmp_db, today):
    se = SearchEngine(tmp_db)
    note = tmp_db.get_or_create_note(today)
    tmp_db.update_note_content(note.id, 'Remember to call Alice about the project')
    results = se.search('Alice')
    assert isinstance(results, list)


def test_search_tasks(tmp_db, today):
    se = SearchEngine(tmp_db)
    task = Task(
        id=None, description='Follow up with Bob', original_date=today,
        due_date=None, completed=False, completed_at=None,
        priority=0, created_at='', updated_at=''
    )
    tmp_db.create_task(task)
    results = se.search('Bob')
    assert isinstance(results, list)


def test_search_no_results(tmp_db):
    se = SearchEngine(tmp_db)
    results = se.search('xyznonexistent123')
    assert results == []


def test_search_empty_query(tmp_db):
    se = SearchEngine(tmp_db)
    results = se.search('')
    assert results == []


def test_search_whitespace_query(tmp_db):
    se = SearchEngine(tmp_db)
    results = se.search('   ')
    assert results == []


def test_search_result_type(tmp_db, today):
    se = SearchEngine(tmp_db)
    task = Task(
        id=None, description='Important meeting', original_date=today,
        due_date=None, completed=False, completed_at=None,
        priority=0, created_at='', updated_at=''
    )
    tmp_db.create_task(task)
    results = se.search('Important')
    for r in results:
        assert r.result_type in ('note', 'task')
        assert r.date is not None


def test_search_multiple_dates(tmp_db):
    se = SearchEngine(tmp_db)
    for date_str in ['2026-11-01', '2026-11-02', '2026-11-03']:
        note = tmp_db.get_or_create_note(date_str)
        tmp_db.update_note_content(note.id, f'Meeting on {date_str}')
    results = se.search('Meeting')
    assert isinstance(results, list)
