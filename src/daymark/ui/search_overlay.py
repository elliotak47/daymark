import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject, GLib, Gdk, Pango
from daymark.core.search import SearchResult


class SearchOverlay(Gtk.Box):
    """Search bar + results overlay."""

    __gsignals__ = {
        'result-selected': (GObject.SignalFlags.RUN_LAST, None, (str,)),  # emits date_str
        'closed': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, search_engine):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._search_engine = search_engine
        self._search_timer = None
        self._visible_flag = False

        self.add_css_class('search-overlay')

        # Search entry row
        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        entry_row.set_margin_start(12)
        entry_row.set_margin_end(12)
        entry_row.set_margin_top(8)
        entry_row.set_margin_bottom(4)

        search_icon = Gtk.Image.new_from_icon_name('system-search-symbolic')
        entry_row.append(search_icon)

        self._entry = Gtk.SearchEntry()
        self._entry.set_placeholder_text('Search notes and tasks\u2026')
        self._entry.set_hexpand(True)
        self._entry.connect('search-changed', self._on_search_changed)
        self._entry.connect('stop-search', self._on_close)
        entry_row.append(self._entry)

        close_btn = Gtk.Button()
        close_btn.set_icon_name('window-close-symbolic')
        close_btn.add_css_class('flat')
        close_btn.connect('clicked', self._on_close)
        entry_row.append(close_btn)
        self.append(entry_row)

        # Separator
        sep = Gtk.Separator()
        self.append(sep)

        # Results
        scroll = Gtk.ScrolledWindow()
        scroll.set_max_content_height(300)
        scroll.set_propagate_natural_height(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._results_box = Gtk.ListBox()
        self._results_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._results_box.add_css_class('search-results-list')
        self._results_box.connect('row-activated', self._on_result_activated)
        scroll.set_child(self._results_box)
        self.append(scroll)

        self.set_visible(False)

    def show_search(self):
        self.set_visible(True)
        self._visible_flag = True
        self._entry.grab_focus()

    def hide_search(self):
        self.set_visible(False)
        self._visible_flag = False
        self._entry.set_text('')
        self._clear_results()

    def _on_close(self, *args):
        self.hide_search()
        self.emit('closed')

    def _on_search_changed(self, entry):
        if self._search_timer:
            GLib.source_remove(self._search_timer)
        self._search_timer = GLib.timeout_add(300, self._do_search)

    def _do_search(self) -> bool:
        self._search_timer = None
        query = self._entry.get_text().strip()
        self._clear_results()
        if not query:
            return False
        results = self._search_engine.search(query)
        for result in results[:30]:
            self._add_result_row(result)
        if not results:
            empty = Gtk.ListBoxRow()
            lbl = Gtk.Label(label='No results found')
            lbl.set_margin_top(12)
            lbl.set_margin_bottom(12)
            lbl.add_css_class('search-empty')
            empty.set_child(lbl)
            self._results_box.append(empty)
        return False

    def _add_result_row(self, result: SearchResult):
        row = Gtk.ListBoxRow()
        row._date_str = result.date

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        # Type + date
        meta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        type_lbl = Gtk.Label(label='NOTE' if result.result_type == 'note' else 'TASK')
        type_lbl.add_css_class('search-result-type')
        meta.append(type_lbl)
        date_lbl = Gtk.Label(label=result.date)
        date_lbl.add_css_class('search-result-date')
        meta.append(date_lbl)
        if result.task_completed:
            done_lbl = Gtk.Label(label='\u2713')
            done_lbl.add_css_class('search-result-done')
            meta.append(done_lbl)
        box.append(meta)

        # Snippet
        snippet_lbl = Gtk.Label(label=result.snippet[:120])
        snippet_lbl.set_halign(Gtk.Align.START)
        snippet_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        snippet_lbl.add_css_class('search-result-snippet')
        box.append(snippet_lbl)

        row.set_child(box)
        self._results_box.append(row)

    def _clear_results(self):
        while True:
            row = self._results_box.get_first_child()
            if row is None:
                break
            self._results_box.remove(row)

    def _on_result_activated(self, _lb, row):
        if hasattr(row, '_date_str'):
            self.emit('result-selected', row._date_str)
            self.hide_search()
