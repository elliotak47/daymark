import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject, Gdk
from datetime import date, timedelta


class DateHeader(Gtk.Box):
    """Date navigation bar. Clicking the date label emits calendar-toggle."""

    __gsignals__ = {
        'date-changed':    (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'calendar-toggle': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._current_date = date.today().isoformat()

        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(10)
        self.set_margin_bottom(8)
        self.add_css_class('date-header')

        # Prev button
        self._prev_btn = Gtk.Button()
        self._prev_btn.set_icon_name('go-previous-symbolic')
        self._prev_btn.add_css_class('flat')
        self._prev_btn.add_css_class('nav-btn')
        self._prev_btn.set_tooltip_text('Previous day  (Alt+Left)')
        self._prev_btn.connect('clicked', self._on_prev)
        self.append(self._prev_btn)

        # Clickable date area — emits calendar-toggle
        date_btn = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        date_btn.set_hexpand(True)
        date_btn.set_halign(Gtk.Align.CENTER)
        date_btn.set_cursor(Gdk.Cursor.new_from_name('pointer'))
        date_btn.set_tooltip_text('Click to show / hide calendar')

        self._date_label = Gtk.Label()
        self._date_label.add_css_class('date-label')
        date_btn.append(self._date_label)

        cal_icon = Gtk.Image.new_from_icon_name('x-office-calendar-symbolic')
        cal_icon.add_css_class('cal-hint-icon')
        date_btn.append(cal_icon)

        click = Gtk.GestureClick()
        click.connect('released', self._on_date_clicked)
        date_btn.add_controller(click)
        self.append(date_btn)

        # Today button (hidden when already on today)
        self._today_btn = Gtk.Button(label='Today')
        self._today_btn.add_css_class('flat')
        self._today_btn.add_css_class('today-button')
        self._today_btn.set_tooltip_text('Jump to today')
        self._today_btn.connect('clicked', self._on_today)
        self.append(self._today_btn)

        # Next button
        self._next_btn = Gtk.Button()
        self._next_btn.set_icon_name('go-next-symbolic')
        self._next_btn.add_css_class('flat')
        self._next_btn.add_css_class('nav-btn')
        self._next_btn.set_tooltip_text('Next day  (Alt+Right)')
        self._next_btn.connect('clicked', self._on_next)
        self.append(self._next_btn)

        self.set_date(self._current_date)

    def set_date(self, date_str: str):
        self._current_date = date_str
        d = date.fromisoformat(date_str)
        # e.g. "WEDNESDAY · NOV 11"
        self._date_label.set_label(d.strftime('%A · %b %-d').upper())

        today = date.today().isoformat()
        self._today_btn.set_visible(date_str != today)
        future_limit = (date.today() + timedelta(days=1)).isoformat()
        self._next_btn.set_sensitive(date_str < future_limit)

    def get_date(self) -> str:
        return self._current_date

    def _on_date_clicked(self, _gesture, _n, _x, _y):
        self.emit('calendar-toggle')

    def _on_prev(self, _btn):
        d = date.fromisoformat(self._current_date)
        new_date = (d - timedelta(days=1)).isoformat()
        self.set_date(new_date)
        self.emit('date-changed', new_date)

    def _on_next(self, _btn):
        d = date.fromisoformat(self._current_date)
        new_date = (d + timedelta(days=1)).isoformat()
        self.set_date(new_date)
        self.emit('date-changed', new_date)

    def _on_today(self, _btn):
        today = date.today().isoformat()
        if today != self._current_date:
            self.set_date(today)
            self.emit('date-changed', today)
