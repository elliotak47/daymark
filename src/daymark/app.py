import os
import sys
import signal
import logging
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, GLib
from pathlib import Path

from daymark import APP_ID
from daymark.db.database import Database
from daymark.settings.config import Config
from daymark.window import DaymarkWindow
from daymark.dbus_service import DaymarkDBusService

logger = logging.getLogger(__name__)


def get_data_dir() -> Path:
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home()))
        return base / 'daymark'
    elif sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'daymark'
    else:
        xdg = os.environ.get('XDG_DATA_HOME', '')
        return Path(xdg) / 'daymark' if xdg else Path.home() / '.local' / 'share' / 'daymark'


class DaymarkApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self._db     = None
        self._config = None
        self._window = None
        self._dbus   = None

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(name)s %(levelname)s: %(message)s',
        )

    def do_startup(self):
        Adw.Application.do_startup(self)
        data_dir = get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        self._db     = Database(data_dir / 'daymark.db')
        self._config = Config(self._db)

        if sys.platform != 'win32':
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._on_sigterm)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT,  self._on_sigterm)

    def do_activate(self):
        if self._window is None:
            self._window = DaymarkWindow(self, self._db, self._config)
            self._dbus   = DaymarkDBusService(self)
            # Keep running even when window is hidden
            self.hold()

        # Show window — unless started with --background flag (for autostart)
        if '--background' not in sys.argv:
            self._window.present()

    # ------------------------------------------------------------------
    # Called by D-Bus service
    # ------------------------------------------------------------------

    def toggle_window(self):
        if self._window:
            self._window.toggle()

    def show_window(self):
        if self._window:
            self._window.show_window()

    # ------------------------------------------------------------------

    def _on_sigterm(self):
        self.quit()
        return GLib.SOURCE_REMOVE

    def do_shutdown(self):
        if self._db:
            self._db.close()
        Adw.Application.do_shutdown(self)

    def get_pending_count(self) -> int:
        """Return number of incomplete tasks for today — called by D-Bus."""
        if not self._db:
            return 0
        from datetime import date
        from daymark.core.tasks import TaskManager
        tasks = TaskManager(self._db).get_tasks_for_date(date.today().isoformat())
        return sum(1 for t in tasks if not t.completed)
