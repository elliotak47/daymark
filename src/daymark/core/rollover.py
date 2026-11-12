import logging
from datetime import date
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class RolloverManager:
    def __init__(self, on_date_change: Callable[[str], None]):
        self._on_date_change = on_date_change
        self._last_date: Optional[str] = None
        self._source_id: Optional[int] = None

    def get_current_date(self) -> str:
        return date.today().isoformat()

    def start(self):
        try:
            from gi.repository import GLib
            self._last_date = self.get_current_date()
            self._source_id = GLib.timeout_add_seconds(60, self._check)
        except ImportError:
            logger.warning("GLib not available, rollover polling disabled")

    def stop(self):
        if self._source_id is not None:
            try:
                from gi.repository import GLib
                GLib.source_remove(self._source_id)
            except Exception:
                pass
            self._source_id = None

    def _check(self) -> bool:
        current = self.get_current_date()
        if self._last_date and current != self._last_date:
            logger.info(f"Date changed from {self._last_date} to {current}")
            self._last_date = current
            self._on_date_change(current)
        return True  # keep polling
