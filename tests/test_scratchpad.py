import pytest
from daymark.core.scratchpad import ScratchpadManager


def test_get_or_create_today(tmp_db, today):
    mgr = ScratchpadManager(tmp_db)
    note = mgr.get_or_create_today()
    assert note.note_date == today


def test_save_content(tmp_db, today):
    mgr = ScratchpadManager(tmp_db)
    note = mgr.get_or_create_today()
    mgr.save_content(note.id, 'My content')
    note2 = mgr.get_note_for_date(today)
    assert note2.content == 'My content'


def test_historical_note(tmp_db):
    mgr = ScratchpadManager(tmp_db)
    note = mgr.get_or_create_for_date('2026-01-15')
    mgr.save_content(note.id, 'Historical content')
    retrieved = mgr.get_note_for_date('2026-01-15')
    assert retrieved.content == 'Historical content'


def test_idempotent(tmp_db, today):
    mgr = ScratchpadManager(tmp_db)
    n1 = mgr.get_or_create_today()
    n2 = mgr.get_or_create_today()
    assert n1.id == n2.id


def test_all_dates(tmp_db):
    mgr = ScratchpadManager(tmp_db)
    mgr.get_or_create_for_date('2026-11-01')
    mgr.get_or_create_for_date('2026-11-02')
    dates = mgr.get_all_dates()
    assert '2026-11-01' in dates
    assert '2026-11-02' in dates
