from dataclasses import dataclass
from typing import Optional
from daymark.db.database import Database


@dataclass
class SearchResult:
    result_type: str        # "note" or "task"
    date: str
    snippet: str
    task_id: Optional[int] = None
    task_completed: Optional[bool] = None


class SearchEngine:
    def __init__(self, db: Database):
        self._db = db

    def search(self, query: str) -> list:
        if not query or not query.strip():
            return []
        query = query.strip()
        results = []
        # Search notes
        for row in self._db.search_notes(query):
            results.append(SearchResult(
                result_type='note',
                date=row['note_date'],
                snippet=row['snippet'],
            ))
        # Search tasks
        for row in self._db.search_tasks(query):
            results.append(SearchResult(
                result_type='task',
                date=row['original_date'],
                snippet=row['description'],
                task_id=row['id'],
                task_completed=row['completed'],
            ))
        return results
