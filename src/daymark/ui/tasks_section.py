import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GObject, Gdk
from daymark.db.models import Task
from .task_row import TaskRow


class TasksSection(Gtk.Box):
    """Displays a list of tasks.  View-only — editing happens in the notes editor.

    Supported interactions:
      • Checkbox toggle (task-toggled signal)
      • Delete (task-deleted signal)
      • Quick-add entry at the bottom — emits task-added(description) which
        MainPanel turns into a '[] ...' line appended to the note.
    """

    __gsignals__ = {
        'task-toggled': (GObject.SignalFlags.RUN_LAST, None, (int, bool)),
        'task-deleted': (GObject.SignalFlags.RUN_LAST, None, (int,)),
        # description + optional context (empty string if none)
        'task-added':   (GObject.SignalFlags.RUN_LAST, None, (str, str)),
    }

    def __init__(self, title: str = "TODAY'S TASKS",
                 show_original_date: bool = False,
                 allow_add: bool = True,
                 collapsible: bool = False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._show_original_date = show_original_date
        self._allow_add  = allow_add
        self._collapsible = collapsible
        self._collapsed  = False

        # ── Section header ─────────────────────────────────────
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_row.set_margin_start(14)
        header_row.set_margin_end(10)
        header_row.set_margin_top(14)
        header_row.set_margin_bottom(6)

        self._header = Gtk.Label(label=title)
        self._header.set_halign(Gtk.Align.START)
        self._header.set_hexpand(True)
        self._header.add_css_class('section-header')
        header_row.append(self._header)

        self._stats_label = Gtk.Label(label='')
        self._stats_label.add_css_class('task-stats-label')
        self._stats_label.set_halign(Gtk.Align.END)
        header_row.append(self._stats_label)

        if collapsible:
            self._collapse_icon = Gtk.Image.new_from_icon_name('pan-down-symbolic')
            collapse_btn = Gtk.Button()
            collapse_btn.set_child(self._collapse_icon)
            collapse_btn.add_css_class('flat')
            collapse_btn.add_css_class('section-collapse-btn')
            collapse_btn.set_tooltip_text('Collapse / expand')
            collapse_btn.connect('clicked', self._on_toggle_collapse)
            header_row.append(collapse_btn)

        self.append(header_row)

        # ── Content ────────────────────────────────────────────
        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class('task-list')
        if show_original_date:
            self._list_box.add_css_class('carried-list')
        self._content_box.append(self._list_box)

        self._empty_label = Gtk.Label(label='No pending tasks')
        self._empty_label.add_css_class('empty-state-label')
        self._empty_label.set_margin_start(16)
        self._empty_label.set_margin_top(6)
        self._empty_label.set_margin_bottom(6)
        self._empty_label.set_visible(False)
        self._content_box.append(self._empty_label)

        if allow_add:
            add_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            add_outer.set_margin_start(14)
            add_outer.set_margin_end(12)
            add_outer.set_margin_top(6)
            add_outer.set_margin_bottom(6)

            # Title row
            add_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            add_icon = Gtk.Image.new_from_icon_name('list-add-symbolic')
            add_icon.add_css_class('add-task-icon')
            add_box.append(add_icon)

            self._add_entry = Gtk.Entry()
            self._add_entry.set_placeholder_text('Add a task…')
            self._add_entry.set_hexpand(True)
            self._add_entry.add_css_class('add-task-entry')
            self._add_entry.connect('activate', self._on_add_task)
            add_box.append(self._add_entry)
            add_outer.append(add_box)

            # Shift+Enter key controller
            key_ctrl = Gtk.EventControllerKey()
            key_ctrl.connect('key-pressed', self._on_add_key)
            self._add_entry.add_controller(key_ctrl)

            # Context row (shown after Shift+Enter)
            ctx_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            ctx_box.set_margin_top(3)
            ctx_indent = Gtk.Box()
            ctx_indent.set_size_request(24, -1)
            ctx_box.append(ctx_indent)

            self._ctx_entry = Gtk.Entry()
            self._ctx_entry.set_placeholder_text('Steps or context…  (Enter to save · Esc to cancel)')
            self._ctx_entry.set_hexpand(True)
            self._ctx_entry.add_css_class('add-task-body-entry')
            self._ctx_entry.connect('activate', self._on_ctx_activate)
            ctx_box.append(self._ctx_entry)

            ctx_key = Gtk.EventControllerKey()
            ctx_key.connect('key-pressed', self._on_ctx_key)
            self._ctx_entry.add_controller(ctx_key)

            self._ctx_box = ctx_box
            self._ctx_box.set_visible(False)
            add_outer.append(ctx_box)

            self._content_box.append(add_outer)

        self.append(self._content_box)

    # ── Public API ─────────────────────────────────────────────

    def set_title(self, title: str):
        self._header.set_label(title)

    def update_stats(self, completed: int, total: int):
        if total == 0:
            self._stats_label.set_label('')
        elif completed == total:
            self._stats_label.set_label('all done ✓')
            self._stats_label.add_css_class('task-stats-done')
        else:
            self._stats_label.set_label(f'{completed} of {total}')
            self._stats_label.remove_css_class('task-stats-done')

    def load_tasks(self, tasks: list, context_map: dict = None):
        context_map = context_map or {}
        while True:
            row = self._list_box.get_first_child()
            if row is None:
                break
            self._list_box.remove(row)

        for task in tasks:
            self._add_task_row(task, context_map.get(task.description, ''))

        show_empty = (len(tasks) == 0 and not self._allow_add)
        self._empty_label.set_visible(show_empty)

    def focus_add_entry(self):
        if self._allow_add:
            self._add_entry.grab_focus()

    # ── Internal ───────────────────────────────────────────────

    def _add_task_row(self, task: Task, context: str = ''):
        row = TaskRow(task, show_original_date=self._show_original_date, context=context)
        row.connect('task-toggled', lambda w, tid, s: self.emit('task-toggled', tid, s))
        row.connect('task-deleted', lambda w, tid:    self.emit('task-deleted', tid))
        self._list_box.append(row)

    def _on_add_key(self, _ctrl, keyval, _keycode, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if state & Gdk.ModifierType.SHIFT_MASK:
                if self._add_entry.get_text().strip():
                    self._ctx_box.set_visible(True)
                    self._ctx_entry.grab_focus()
                    return True
        return False

    def _on_add_task(self, entry):
        text = entry.get_text().strip()
        if text:
            self.emit('task-added', text, '')
            entry.set_text('')
            self._ctx_entry.set_text('')
            self._ctx_box.set_visible(False)

    def _on_ctx_activate(self, _entry):
        description = self._add_entry.get_text().strip()
        context     = self._ctx_entry.get_text().strip()
        if description:
            self.emit('task-added', description, context)
            self._add_entry.set_text('')
            self._ctx_entry.set_text('')
            self._ctx_box.set_visible(False)
            self._add_entry.grab_focus()

    def _on_ctx_key(self, _ctrl, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self._ctx_entry.set_text('')
            self._ctx_box.set_visible(False)
            self._add_entry.grab_focus()
            return True
        return False

    def _on_toggle_collapse(self, _btn):
        self._collapsed = not self._collapsed
        self._content_box.set_visible(not self._collapsed)
        if hasattr(self, '_collapse_icon'):
            self._collapse_icon.set_from_icon_name(
                'pan-end-symbolic' if self._collapsed else 'pan-down-symbolic'
            )
