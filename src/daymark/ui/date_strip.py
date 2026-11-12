import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject, Gdk
from datetime import date, timedelta


class DateStrip(Gtk.Box):
    """Always-visible 7-day horizontal strip (3 before + selected + 3 after).

    Emits ``date-selected`` when the user clicks a day chip.  Call
    ``set_selected_date()`` to highlight a specific day and
    ``update_activity()`` to show / hide activity dots.
    """

    __gsignals__ = {
        'date-selected': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._selected = date.today()
        self._activity_dates: set = set()
        self._pending_dates: set  = set()
        self._chips: list[Gtk.Button] = []

        self.set_homogeneous(True)
        self.add_css_class('date-strip')

        # Mouse-wheel scrolls days
        scroll_ctrl = Gtk.EventControllerScroll()
        scroll_ctrl.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_ctrl.connect('scroll', self._on_scroll)
        self.add_controller(scroll_ctrl)

        self._rebuild()

    # ── Public API ─────────────────────────────────────────────

    def set_selected_date(self, date_str: str):
        d = date.fromisoformat(date_str)
        if d != self._selected:
            self._selected = d
            self._rebuild()

    def update_activity(self, pending_dates: set, activity_dates: set):
        self._pending_dates  = set(pending_dates)
        self._activity_dates = set(activity_dates)
        self._rebuild()

    # ── Internal ───────────────────────────────────────────────

    def _rebuild(self):
        for chip in self._chips:
            self.remove(chip)
        self._chips.clear()

        today = date.today()
        for offset in range(-3, 4):
            d = self._selected + timedelta(days=offset)
            chip = self._make_chip(d, today)
            self._chips.append(chip)
            self.append(chip)

    def _make_chip(self, d: date, today: date) -> Gtk.Button:
        date_str = d.isoformat()
        is_selected = (d == self._selected)
        is_today    = (d == today)
        is_future   = (d > today)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        vbox.set_halign(Gtk.Align.CENTER)

        dow_label = Gtk.Label(label=d.strftime('%a')[:2].upper())
        dow_label.add_css_class('date-chip-dow')
        vbox.append(dow_label)

        day_label = Gtk.Label(label=str(d.day))
        day_label.add_css_class('date-chip-day')
        vbox.append(day_label)

        dot = Gtk.Label(label='●')
        dot.add_css_class('date-chip-dot')
        dot.set_visible(date_str in self._pending_dates)
        vbox.append(dot)

        btn = Gtk.Button()
        btn.set_child(vbox)
        btn.add_css_class('date-chip')
        btn.set_sensitive(not is_future)

        if is_selected:
            btn.add_css_class('date-chip-selected')
        if is_today:
            btn.add_css_class('date-chip-today')

        btn.connect('clicked', lambda _b, ds=date_str: self.emit('date-selected', ds))
        return btn

    def _on_scroll(self, _ctrl, _dx, dy):
        today = date.today()
        if dy < 0:
            new = self._selected + timedelta(days=1)
        else:
            new = self._selected - timedelta(days=1)
        if new <= today:
            self._selected = new
            self._rebuild()
            self.emit('date-selected', self._selected.isoformat())
        return True
