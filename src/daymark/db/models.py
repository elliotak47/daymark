from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DailyNote:
    id: Optional[int]
    note_date: str          # ISO date "YYYY-MM-DD"
    content: str
    created_at: str
    updated_at: str


@dataclass
class Task:
    id: Optional[int]
    description: str
    original_date: str      # ISO date "YYYY-MM-DD"
    due_date: Optional[str]
    completed: bool
    completed_at: Optional[str]
    priority: int           # 0=normal, 1=high, 2=urgent
    created_at: str
    updated_at: str
    body: str = ''          # kept for DB compat; not used in UI
    source: str = 'direct' # 'note' = created from [] in notes; 'direct' = quick-add / legacy
