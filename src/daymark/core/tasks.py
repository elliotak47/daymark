from datetime import datetime, date
from typing import Optional
from daymark.db.database import Database
from daymark.db.models import Task


class TaskManager:
    def __init__(self, db: Database):
        self._db = db

    def create_task(self, description: str, date_str: str, body: str = '',
                    source: str = 'direct', priority: int = 0,
                    due_date: Optional[str] = None) -> Task:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        task = Task(
            id=None,
            description=description,
            original_date=date_str,
            due_date=due_date,
            completed=False,
            completed_at=None,
            priority=priority,
            created_at=now,
            updated_at=now,
            body=body,
            source=source,
        )
        return self._db.create_task(task)

    def complete_task(self, task_id: int) -> Optional[Task]:
        task = self._db.get_task(task_id)
        if task is None:
            return None
        task.completed = True
        task.completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self._db.update_task(task)
        return task

    def reopen_task(self, task_id: int) -> Optional[Task]:
        task = self._db.get_task(task_id)
        if task is None:
            return None
        task.completed = False
        task.completed_at = None
        self._db.update_task(task)
        return task

    def delete_task(self, task_id: int):
        self._db.delete_task(task_id)

    def update_description(self, task_id: int, description: str):
        task = self._db.get_task(task_id)
        if task is None:
            return
        task.description = description
        self._db.update_task(task)

    def update_body(self, task_id: int, body: str):
        task = self._db.get_task(task_id)
        if task is None:
            return
        task.body = body
        self._db.update_task(task)

    def get_tasks_for_date(self, date_str: str) -> list:
        return self._db.get_tasks_for_date(date_str)

    def get_carried_forward(self, date_str: str) -> list:
        """Return incomplete tasks from BEFORE the given date."""
        return self._db.get_pending_tasks_before(date_str)

    def get_pending_count_before(self, date_str: str) -> dict:
        """Return {date_str: count} of dates with pending tasks before given date."""
        tasks = self._db.get_pending_tasks_before(date_str)
        counts = {}
        for t in tasks:
            counts[t.original_date] = counts.get(t.original_date, 0) + 1
        return counts
