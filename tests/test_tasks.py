import pytest
from daymark.core.tasks import TaskManager


def test_create_task(tmp_db, today):
    mgr = TaskManager(tmp_db)
    task = mgr.create_task('Do something', today)
    assert task.id is not None
    assert task.description == 'Do something'
    assert task.original_date == today
    assert task.completed is False


def test_complete_task(tmp_db, today):
    mgr = TaskManager(tmp_db)
    task = mgr.create_task('Complete me', today)
    completed = mgr.complete_task(task.id)
    assert completed.completed is True
    assert completed.completed_at is not None


def test_reopen_task(tmp_db, today):
    mgr = TaskManager(tmp_db)
    task = mgr.create_task('Reopen me', today)
    mgr.complete_task(task.id)
    reopened = mgr.reopen_task(task.id)
    assert reopened.completed is False
    assert reopened.completed_at is None


def test_carry_forward(tmp_db, today, yesterday):
    mgr = TaskManager(tmp_db)
    mgr.create_task('Yesterday task', yesterday)
    carried = mgr.get_carried_forward(today)
    assert len(carried) == 1
    assert carried[0].original_date == yesterday


def test_no_duplicate_carry_forward(tmp_db, today, yesterday):
    mgr = TaskManager(tmp_db)
    mgr.create_task('Task A', yesterday)
    # Calling get_carried_forward multiple times should not create duplicates
    c1 = mgr.get_carried_forward(today)
    c2 = mgr.get_carried_forward(today)
    assert len(c1) == len(c2) == 1


def test_complete_carried_task(tmp_db, today, yesterday):
    mgr = TaskManager(tmp_db)
    task = mgr.create_task('Old task', yesterday)
    mgr.complete_task(task.id)
    carried = mgr.get_carried_forward(today)
    assert len(carried) == 0


def test_pending_indicators(tmp_db, today, yesterday, two_days_ago):
    mgr = TaskManager(tmp_db)
    mgr.create_task('Task 1', yesterday)
    mgr.create_task('Task 2', two_days_ago)
    counts = mgr.get_pending_count_before(today)
    assert counts[yesterday] == 1
    assert counts[two_days_ago] == 1


def test_delete_task(tmp_db, today):
    mgr = TaskManager(tmp_db)
    task = mgr.create_task('Delete me', today)
    mgr.delete_task(task.id)
    tasks = mgr.get_tasks_for_date(today)
    assert all(t.id != task.id for t in tasks)


def test_priority(tmp_db, today):
    mgr = TaskManager(tmp_db)
    task = mgr.create_task('High priority', today, priority=1)
    assert task.priority == 1


def test_update_description(tmp_db, today):
    mgr = TaskManager(tmp_db)
    task = mgr.create_task('Original', today)
    mgr.update_description(task.id, 'Updated')
    tasks = mgr.get_tasks_for_date(today)
    assert tasks[0].description == 'Updated'
