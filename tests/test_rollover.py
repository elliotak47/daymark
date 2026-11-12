import pytest
from datetime import date
from unittest.mock import MagicMock, patch


def test_date_detection():
    from daymark.core.rollover import RolloverManager
    mgr = RolloverManager(lambda d: None)
    assert mgr.get_current_date() == date.today().isoformat()


def test_rollover_callback():
    from daymark.core.rollover import RolloverManager
    callback = MagicMock()
    mgr = RolloverManager(callback)
    mgr._last_date = '2026-01-01'
    with patch.object(mgr, 'get_current_date', return_value='2026-01-02'):
        mgr._check()
    callback.assert_called_once_with('2026-01-02')


def test_no_duplicate_callback():
    from daymark.core.rollover import RolloverManager
    callback = MagicMock()
    mgr = RolloverManager(callback)
    today = date.today().isoformat()
    mgr._last_date = today
    mgr._check()
    callback.assert_not_called()


def test_timezone_handling():
    from daymark.core.rollover import RolloverManager
    mgr = RolloverManager(lambda d: None)
    # Should return local date, not UTC
    local_date = date.today().isoformat()
    assert mgr.get_current_date() == local_date
