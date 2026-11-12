import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GObject
from datetime import date, timedelta
import calendar


class HistoryPanel(Gtk.Box):
    """Month-view calendar designed to live inside a Gtk.Popover.

    Always fully visible (no Revealer / collapse logic).  Shows a DOW
    header row (Mo Tu … Su) and a Today button in the nav bar.
    """

    __gsignals__ = {
        'date-selected': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._current_year  = date.today().year
        self._current_month = date.today().month
        self._selected_date = date.today().isoformat()
        self._pending_dates  = set()
        self._activity_dates = set()

        self.add_css_class('history-panel')
        self.set_size_request(300, -1)

        # ── Month navigation row ───────────────────────────────
        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        nav.set_margin_start(8)
        nav.set_margin_end(8)
        nav.set_margin_top(8)
        nav.set_margin_bottom(4)

        prev_btn = Gtk.Button()
        prev_btn.set_icon_name('go-previous-symbolic')
        prev_btn.add_css_class('flat')
        prev_btn.add_css_class('nav-btn')
        prev_btn.connect('clicked', self._on_prev_month)
        nav.append(prev_btn)

        self._month_label = Gtk.Label()
        self._month_label.add_css_class('history-month-label')
        self._month_label.set_hexpand(True)
        self._month_label.set_halign(Gtk.Align.CENTER)
        nav.append(self._month_label)

        today_btn = Gtk.Button(label='Today')
        today_btn.add_css_class('today-button')
        today_btn.connect('clicked', self._on_today_clicked)
        nav.append(today_btn)

        next_btn = Gtk.Button()
        next_btn.set_icon_name('go-next-symbolic')
        next_btn.add_css_class('flat')
        next_btn.add_css_class('nav-btn')
        next_btn.connect('clicked', self._on_next_month)
        nav.append(next_btn)

        self.append(nav)

        # ── DOW header row ─────────────────────────────────────
        dow_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        dow_row.set_homogeneous(True)
        dow_row.set_margin_start(6)
        dow_row.set_margin_end(6)
        dow_row.set_margin_bottom(2)
        for name in ('Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'):
            lbl = Gtk.Label(label=name)
            lbl.add_css_class('cal-dow-label')
            dow_row.append(lbl)
        self.append(dow_row)

        # ── Day grid ───────────────────────────────────────────
        self._flow = Gtk.FlowBox()
        self._flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._flow.set_homogeneous(True)
        self._flow.set_max_children_per_line(7)
        self._flow.set_min_children_per_line(7)
        self._flow.set_row_spacing(2)
        self._flow.set_column_spacing(2)
        self._flow.set_margin_start(6)
        self._flow.set_margin_end(6)
        self._flow.set_margin_bottom(8)
        self._flow.connect('child-activated', self._on_child_activated)
        self.append(self._flow)

        self._rebuild_month()

    # ── Public API ─────────────────────────────────────────────

    def update_pending_indicators(self, pending_dates: set, activity_dates: set = None):
        self._pending_dates  = set(pending_dates)
        self._activity_dates = set(activity_dates) if activity_dates else set()
        self._rebuild_month()
        self._select_current()

    def select_date(self, date_str: str):
        self._selected_date = date_str
        d = date.fromisoformat(date_str)
        if d.year != self._current_year or d.month != self._current_month:
            self._current_year  = d.year
            self._current_month = d.month
        self._rebuild_month()
        self._select_current()

    # ── Internal ───────────────────────────────────────────────

    def _rebuild_month(self):
        while True:
            child = self._flow.get_child_at_index(0)
            if child is None:
                break
            self._flow.remove(child)

        self._month_label.set_label(
            date(self._current_year, self._current_month, 1).strftime('%B %Y').upper()
        )

        today = date.today()
        first_day, days_in_month = calendar.monthrange(self._current_year, self._current_month)

        for _ in range(first_day):
            spacer = Gtk.FlowBoxChild()
            spacer.set_focusable(False)
            spacer.set_sensitive(False)
            spacer.set_child(Gtk.Label(label=''))
            self._flow.append(spacer)

        for day in range(1, days_in_month + 1):
            d = date(self._current_year, self._current_month, day)
            date_str = d.isoformat()

            child = Gtk.FlowBoxChild()
            child._date_str = date_str

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            box.set_halign(Gtk.Align.CENTER)
            box.set_valign(Gtk.Align.CENTER)
            box.set_margin_top(2)
            box.set_margin_bottom(2)

            day_label = Gtk.Label(label=str(day))
            day_label.add_css_class('history-day-num')
            box.append(day_label)

            dot = Gtk.Label(label='●')
            dot.add_css_class('pending-dot')
            dot.set_visible(date_str in self._pending_dates)
            box.append(dot)

            child.set_child(box)

            if date_str == today.isoformat():
                child.add_css_class('today-chip')
            if date_str == self._selected_date:
                child.add_css_class('selected-chip')
            if d > today:
                child.set_sensitive(False)

            self._flow.append(child)

    def _select_current(self):
        idx = 0
        while True:
            child = self._flow.get_child_at_index(idx)
            if child is None:
                break
            if hasattr(child, '_date_str') and child._date_str == self._selected_date:
                self._flow.select_child(child)
                break
            idx += 1

    def _on_child_activated(self, _flow, child):
        if hasattr(child, '_date_str'):
            self.emit('date-selected', child._date_str)

    def _on_prev_month(self, _btn):
        if self._current_month == 1:
            self._current_month = 12
            self._current_year -= 1
        else:
            self._current_month -= 1
        self._rebuild_month()

    def _on_next_month(self, _btn):
        today = date.today()
        if self._current_year < today.year or (
            self._current_year == today.year and self._current_month < today.month
        ):
            if self._current_month == 12:
                self._current_month = 1
                self._current_year += 1
            else:
                self._current_month += 1
            self._rebuild_month()

    def _on_today_clicked(self, _btn):
        today = date.today()
        self._current_year  = today.year
        self._current_month = today.month
        self._selected_date = today.isoformat()
        self._rebuild_month()
        self._select_current()
        self.emit('date-selected', today.isoformat())
