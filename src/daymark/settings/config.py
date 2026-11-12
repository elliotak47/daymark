from daymark.db.database import Database

DEFAULTS = {
    'panel_position': 'right',
    'panel_width': '380',
    'theme': 'system',
    'font_size': '14',
    'autosave_delay_ms': '500',
    'show_history_panel': 'true',
}


class Config:
    def __init__(self, db: Database):
        self._db = db

    def get(self, key: str, default: str = '') -> str:
        val = self._db.settings_get(key)
        if val:
            return val
        return DEFAULTS.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, str(default)))
        except ValueError:
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        return self.get(key, str(default).lower()).lower() in ('true', '1', 'yes')

    def set(self, key: str, value: str):
        self._db.settings_set(key, value)
