import logging
from pathlib import Path
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

from daymark.db.database import Database
from daymark.settings.config import Config
from daymark.ui.main_panel import MainPanel

logger = logging.getLogger(__name__)

DEFAULT_WIDTH  = 460
DEFAULT_HEIGHT = 720
MIN_WIDTH      = 380
MIN_HEIGHT     = 520


class DaymarkWindow(Adw.ApplicationWindow):
    def __init__(self, app, db: Database, config: Config):
        super().__init__(application=app)
        self._db     = db
        self._config = config
        self._hide_timer_id      = None
        self._size_at_hide_sched = None

        self.set_title('Daymark')
        self.set_size_request(MIN_WIDTH, MIN_HEIGHT)
        self.set_default_size(
            int(self._config.get('window_width',  str(DEFAULT_WIDTH))),
            int(self._config.get('window_height', str(DEFAULT_HEIGHT))),
        )
        self.set_resizable(True)

        # X button → hide to background, not quit
        self.connect('close-request', self._on_close_request)

        # Click outside → hide (panel popup behaviour)
        self.connect('notify::is-active', self._on_active_changed)

        # Hide from taskbar / dock after surface is ready
        self.connect('realize', self._on_realize)

        self._panel = MainPanel(db, config)
        self.set_content(self._panel)
        self._load_css()

    # ------------------------------------------------------------------
    # Called by app (from D-Bus)
    # ------------------------------------------------------------------

    def toggle(self):
        if self.get_visible():
            self._save_size()
            self.hide()
        else:
            self.present()

    def show_window(self):
        self.present()

    # ------------------------------------------------------------------

    def _on_active_changed(self, win, _param):
        if not win.is_active() and win.get_visible():
            if self._hide_timer_id is not None:
                GLib.source_remove(self._hide_timer_id)
            self._size_at_hide_sched = (self.get_width(), self.get_height())
            self._hide_timer_id = GLib.timeout_add(500, self._maybe_hide)

    def _maybe_hide(self):
        self._hide_timer_id = None
        if not (self.get_visible() and not self.is_active()):
            return False
        current = (self.get_width(), self.get_height())
        if current != self._size_at_hide_sched:
            # Size changed between scheduling and now — this was a resize, not
            # a click-outside.  Reschedule and wait until the size stabilises.
            self._size_at_hide_sched = current
            self._hide_timer_id = GLib.timeout_add(500, self._maybe_hide)
            return False
        self._save_size()
        self.hide()
        return False

    def _on_realize(self, _win):
        try:
            # X11: set skip-taskbar hint so the window doesn't appear in the dock
            from gi.repository import GdkX11
            surface = self.get_surface()
            if isinstance(surface, GdkX11.X11Surface):
                surface.set_skip_taskbar_hint(True)
                surface.set_skip_pager_hint(True)
        except Exception:
            pass

    def _on_close_request(self, _win):
        self._save_size()
        self.hide()
        return True  # prevent destroy

    def _save_size(self):
        self._config.set('window_width',  str(self.get_width()))
        self._config.set('window_height', str(self.get_height()))

    def _load_css(self):
        css_path = Path(__file__).parent.parent.parent / 'data' / 'daymark.css'
        css = Gtk.CssProvider()
        if css_path.exists():
            css.load_from_path(str(css_path))
        else:
            css.load_from_string('.daymark-panel { background-color: #1e1e2e; }')
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
