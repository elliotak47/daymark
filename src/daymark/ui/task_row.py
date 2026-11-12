import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GObject, Pango
from datetime import date as Date
from daymark.db.models import Task


class TaskRow(Gtk.Box):
    """A single task row: checkbox, description, context preview, hover-reveal delete.

    Context is sourced from the note (lines below the [] block).
    It shows as a single dim line; hovering expands it to full text.
    Task section is view-only — editing happens in the notes editor.
    """

    __gsignals__ = {
        'task-toggled': (GObject.SignalFlags.RUN_LAST, None, (int, bool)),
        'task-deleted': (GObject.SignalFlags.RUN_LAST, None, (int,)),
    }

    def __init__(self, task: Task, show_original_date: bool = False, context: str = ''):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.task = task
        self._context = context

        self.set_margin_start(4)
        self.set_margin_end(4)
        self.set_margin_top(3)
        self.set_margin_bottom(3)
        self.add_css_class('task-row')

        # Narrow priority colour bar
        priority_bar = Gtk.Box()
        priority_bar.set_size_request(3, -1)
        if task.priority == 1:
            priority_bar.add_css_class('priority-high')
        elif task.priority == 2:
            priority_bar.add_css_class('priority-urgent')
        self.append(priority_bar)

        # Checkbox
        self._check = Gtk.CheckButton()
        self._check.set_active(task.completed)
        self._check.set_valign(Gtk.Align.START)
        self._check.set_margin_top(5)
        self._check.connect('toggled', self._on_toggled)
        self.append(self._check)

        # Content column
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        content_box.set_hexpand(True)

        # Description label — wraps fully
        self._label = Gtk.Label(label=task.description)
        self._label.set_halign(Gtk.Align.START)
        self._label.set_hexpand(True)
        self._label.set_wrap(True)
        self._label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)

        if task.completed:
            attrs = Pango.AttrList()
            attrs.insert(Pango.attr_strikethrough_new(True))
            self._label.set_attributes(attrs)
            self._label.add_css_class('completed-task-label')
        content_box.append(self._label)

        # Context preview — dim single line from note, expands on hover
        # Collapsed: flatten to one line with · separators (strip list markers)
        self._preview_text = '  ·  '.join(
            ln.strip().lstrip('-•').lstrip('0123456789.').strip()
            for ln in context.split('\n') if ln.strip()
        ) if context else ''
        # Expanded: original lines preserved exactly (bullets stay as bullets)
        self._context_full = context or ''

        self._context_label = Gtk.Label(label=self._preview_text)
        self._context_label.set_halign(Gtk.Align.START)
        self._context_label.set_hexpand(True)
        self._context_label.set_wrap(True)
        self._context_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self._context_label.set_lines(1)
        self._context_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._context_label.add_css_class('task-body-preview')
        self._context_label.set_visible(bool(self._preview_text))
        self._context_label.set_margin_top(1)
        content_box.append(self._context_label)

        # Original date sub-label for carried-forward tasks
        if show_original_date and task.original_date:
            today = Date.today().isoformat()
            if task.original_date < today:
                origin_label = Gtk.Label()
                origin_label.set_markup(
                    f'<small><span alpha="45%">from {self._format_date(task.original_date)}</span></small>'
                )
                origin_label.set_halign(Gtk.Align.START)
                content_box.append(origin_label)

        self.append(content_box)

        # Delete button (opacity 0 → 1 on row hover via CSS)
        actions = Gtk.Box(spacing=2)
        actions.add_css_class('task-actions')

        del_btn = Gtk.Button()
        del_btn.set_icon_name('user-trash-symbolic')
        del_btn.add_css_class('flat')
        del_btn.add_css_class('destructive-action')
        del_btn.set_tooltip_text('Delete task')
        del_btn.connect('clicked', lambda _b: self.emit('task-deleted', self.task.id))
        actions.append(del_btn)

        self.append(actions)

        # Carried-forward styling
        if show_original_date and not task.completed:
            today = Date.today().isoformat()
            if task.original_date < today:
                self.add_css_class('carried-forward')

        # Hover → expand / collapse context preview
        if self._preview_text:
            motion = Gtk.EventControllerMotion()
            motion.connect('enter', self._on_hover_enter)
            motion.connect('leave', self._on_hover_leave)
            self.add_controller(motion)

    def _on_hover_enter(self, *_):
        # Switch to original context (bullets/numbered lines preserved)
        self._context_label.set_label(self._context_full)
        self._context_label.set_lines(0)
        self._context_label.set_ellipsize(Pango.EllipsizeMode.NONE)

    def _on_hover_leave(self, *_):
        # Restore collapsed single-line preview
        self._context_label.set_label(self._preview_text)
        self._context_label.set_lines(1)
        self._context_label.set_ellipsize(Pango.EllipsizeMode.END)

    def _format_date(self, date_str: str) -> str:
        from datetime import date
        try:
            d = date.fromisoformat(date_str)
            return d.strftime('%b %-d')
        except Exception:
            return date_str

    def _on_toggled(self, check):
        self.emit('task-toggled', self.task.id, check.get_active())
