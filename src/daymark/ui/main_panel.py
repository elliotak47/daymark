import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GObject, GLib, Gdk
from datetime import date, timedelta

from daymark.db.database import Database
from daymark.core.scratchpad import ScratchpadManager
from daymark.core.tasks import TaskManager
from daymark.core.search import SearchEngine
from daymark.core.rollover import RolloverManager
from daymark.core.task_sync import (sync_tasks_from_note, update_task_in_note,
                                    remove_task_block_from_note, parse_task_blocks)
from daymark.settings.config import Config
from .date_header import DateHeader
from .date_strip import DateStrip
from .notes_editor import NotesEditor
from .tasks_section import TasksSection
from .history_panel import HistoryPanel
from .search_overlay import SearchOverlay


class MainPanel(Gtk.Box):
    """Root content panel — coordinates all sub-widgets and data flow."""

    def __init__(self, db: Database, config: Config):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._db = db
        self._config = config
        self._scratchpad = ScratchpadManager(db)
        self._task_mgr = TaskManager(db)
        self._search_engine = SearchEngine(db)
        self._current_note = None
        self._current_date = date.today().isoformat()

        self.add_css_class('main-panel')

        # Search overlay
        self._search_overlay = SearchOverlay(self._search_engine)
        self._search_overlay.connect('result-selected', self._on_search_result_selected)
        self._search_overlay.connect('closed', lambda _: None)
        self.append(self._search_overlay)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_hexpand(True)
        content.set_vexpand(True)
        self.append(content)

        # Date header
        self._date_header = DateHeader()
        self._date_header.connect('date-changed', self._on_date_changed)
        self._date_header.connect('calendar-toggle', self._on_calendar_toggle)
        content.append(self._date_header)

        # 7-day date strip
        self._date_strip = DateStrip()
        self._date_strip.connect('date-selected', self._on_date_strip_selected)
        content.append(self._date_strip)

        content.append(Gtk.Separator())

        # Notes editor — adaptive height, source of truth for tasks
        self._notes_editor = NotesEditor(
            autosave_delay_ms=config.get_int('autosave_delay_ms', 500)
        )
        self._notes_editor.set_save_callback(self._on_save_notes)
        content.append(self._notes_editor)

        content.append(Gtk.Separator())

        # Tasks section — view only (toggling + delete)
        self._tasks_section = TasksSection(title="TODAY'S TASKS", allow_add=True)
        self._tasks_section.connect('task-toggled', self._on_task_toggled)
        self._tasks_section.connect('task-deleted', self._on_task_deleted)
        self._tasks_section.connect('task-added',   self._on_task_quick_added)

        # Carried-forward section
        self._carried_section = TasksSection(
            title='CARRIED FORWARD', show_original_date=True,
            allow_add=False, collapsible=True
        )
        self._carried_section.connect('task-toggled', self._on_task_toggled)
        self._carried_section.connect('task-deleted', self._on_task_deleted)

        tasks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        tasks_box.append(self._tasks_section)
        tasks_box.append(self._carried_section)

        tasks_scroll = Gtk.ScrolledWindow()
        tasks_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        tasks_scroll.set_max_content_height(260)
        tasks_scroll.set_propagate_natural_height(True)
        tasks_scroll.set_child(tasks_box)
        tasks_scroll.set_vexpand(True)
        content.append(tasks_scroll)

        content.append(Gtk.Separator())

        # Calendar popover
        self._history_panel = HistoryPanel()
        self._history_panel.connect('date-selected', self._on_history_date_selected)

        self._calendar_popover = Gtk.Popover()
        self._calendar_popover.set_autohide(True)
        self._calendar_popover.add_css_class('calendar-popover')
        self._calendar_popover.set_child(self._history_panel)
        self._calendar_popover.set_parent(self._date_header)
        self._calendar_popover.set_position(Gtk.PositionType.BOTTOM)

        self._setup_shortcuts()

        self._rollover = RolloverManager(self._on_day_rollover)
        self._rollover.start()

        self._load_date(self._current_date)
        self._refresh_history()

    # ── Shortcuts ──────────────────────────────────────────────

    def _setup_shortcuts(self):
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.MANAGED)
        ctrl.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string('<Control>f'),
            Gtk.CallbackAction.new(lambda *a: self._open_search())
        ))
        ctrl.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string('<Alt>Left'),
            Gtk.CallbackAction.new(lambda *a: self._navigate_day(-1))
        ))
        ctrl.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string('<Alt>Right'),
            Gtk.CallbackAction.new(lambda *a: self._navigate_day(1))
        ))
        ctrl.add_shortcut(Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string('<Control>n'),
            Gtk.CallbackAction.new(lambda *a: self._tasks_section.focus_add_entry())
        ))
        self.add_controller(ctrl)

    def _open_search(self, *args):
        self._search_overlay.show_search()
        return True

    def _navigate_day(self, delta: int):
        d = date.fromisoformat(self._current_date)
        new_d = d + timedelta(days=delta)
        if new_d <= date.today():
            self._load_date(new_d.isoformat())
        return True

    # ── Load date ──────────────────────────────────────────────

    def _load_date(self, date_str: str):
        self._current_date = date_str
        self._date_header.set_date(date_str)
        self._date_strip.set_selected_date(date_str)
        self._history_panel.select_date(date_str)

        self._current_note = self._scratchpad.get_or_create_for_date(date_str)
        self._notes_editor.load_content(self._current_note.content)

        self._reload_tasks()

    def _reload_tasks(self):
        date_str = self._current_date

        # Build context map from whatever is currently in the notes editor
        context_map = {}
        current_content = self._notes_editor.get_content()
        for block in parse_task_blocks(current_content):
            if block['context']:
                context_map[block['description']] = '\n'.join(block['context'])

        today_tasks = self._task_mgr.get_tasks_for_date(date_str)
        self._tasks_section.load_tasks(today_tasks, context_map)
        completed_count = sum(1 for t in today_tasks if t.completed)
        self._tasks_section.update_stats(completed_count, len(today_tasks))

        carried = self._task_mgr.get_carried_forward(date_str)
        self._carried_section.load_tasks(carried)
        if carried:
            self._carried_section.set_title(f'CARRIED FORWARD \u2014 {len(carried)} PENDING')
        else:
            self._carried_section.set_title('CARRIED FORWARD')
        self._carried_section.set_visible(len(carried) > 0)

    def _refresh_history(self):
        activity = self._db.get_all_dates_with_activity()
        pending_dates  = {d for d, info in activity.items() if info['has_pending']}
        activity_dates = set(activity.keys())
        self._history_panel.update_pending_indicators(pending_dates, activity_dates)
        self._date_strip.update_activity(pending_dates, activity_dates)

    # ── Notes callbacks ────────────────────────────────────────

    def _on_save_notes(self, content: str):
        if self._current_note:
            self._scratchpad.save_content(self._current_note.id, content)
            # Sync [] task markers in note → DB
            sync_tasks_from_note(self._task_mgr, self._current_date, content)
            self._reload_tasks()
            self._refresh_history()

    # ── Task callbacks ─────────────────────────────────────────

    def _on_task_toggled(self, _widget, task_id: int, completed: bool):
        task = self._task_mgr.complete_task(task_id) if completed \
               else self._task_mgr.reopen_task(task_id)

        # Mirror toggle in the note text so [] ↔ [x] stays in sync
        if task and self._current_note:
            # For carried-forward tasks the note may be from a different date
            note = self._scratchpad.get_or_create_for_date(task.original_date)
            updated = update_task_in_note(note.content, task.description, completed)
            if updated != note.content:
                self._scratchpad.save_content(note.id, updated)
                # If the toggled task is from today, refresh the note editor live
                if task.original_date == self._current_date:
                    self._notes_editor.load_content(updated)
                    self._current_note = self._scratchpad.get_or_create_for_date(
                        self._current_date)

        self._reload_tasks()
        self._refresh_history()

    def _on_task_deleted(self, _widget, task_id: int):
        # Find the task first so we can remove its block from the note
        task = self._task_mgr._db.get_task(task_id)
        self._task_mgr.delete_task(task_id)

        if task:
            # Remove the [] block from the original date's note
            note = self._scratchpad.get_or_create_for_date(task.original_date)
            updated = remove_task_block_from_note(note.content, task.description)
            if updated != note.content:
                self._scratchpad.save_content(note.id, updated)
                if task.original_date == self._current_date:
                    self._notes_editor.load_content(updated)
                    self._current_note = self._scratchpad.get_or_create_for_date(
                        self._current_date)

        self._reload_tasks()
        self._refresh_history()

    def _on_task_quick_added(self, _widget, description: str, context: str):
        """Quick-add: append '[] description\ncontext' to today's note, let sync create task."""
        if not self._current_note:
            return
        content = self._notes_editor.get_content()
        separator = '\n\n' if content.strip() else ''
        block = f'[] {description}\n'
        if context.strip():
            block += context.strip() + '\n'
        new_content = content.rstrip('\n') + separator + block
        self._notes_editor.load_content(new_content)
        self._scratchpad.save_content(self._current_note.id, new_content)
        self._current_note = self._scratchpad.get_or_create_for_date(self._current_date)
        sync_tasks_from_note(self._task_mgr, self._current_date, new_content)
        self._reload_tasks()
        self._refresh_history()

    # ── Navigation callbacks ───────────────────────────────────

    def _on_date_changed(self, _header, date_str: str):
        self._load_date(date_str)

    def _on_calendar_toggle(self, _header):
        if self._calendar_popover.is_visible():
            self._calendar_popover.popdown()
        else:
            self._calendar_popover.popup()

    def _on_date_strip_selected(self, _strip, date_str: str):
        self._load_date(date_str)

    def _on_history_date_selected(self, _panel, date_str: str):
        self._calendar_popover.popdown()
        self._load_date(date_str)

    def _on_search_result_selected(self, _overlay, date_str: str):
        self._load_date(date_str)

    def _on_day_rollover(self, new_date: str):
        self._load_date(new_date)
        self._refresh_history()

    def cleanup(self):
        self._rollover.stop()
