from datetime import date
from typing import Optional
from daymark.db.database import Database
from daymark.db.models import DailyNote


class ScratchpadManager:
    def __init__(self, db: Database):
        self._db = db

    def get_or_create_today(self) -> DailyNote:
        return self._db.get_or_create_note(date.today().isoformat())

    def get_note_for_date(self, date_str: str) -> Optional[DailyNote]:
        return self._db.get_note_for_date(date_str)

    def get_or_create_for_date(self, date_str: str) -> DailyNote:
        return self._db.get_or_create_note(date_str)

    def save_content(self, note_id: int, content: str):
        self._db.update_note_content(note_id, content)

    def get_all_dates(self) -> list:
        activity = self._db.get_all_dates_with_activity()
        return sorted(activity.keys())
