import re
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, GObject, Gdk, Pango
from daymark.core.task_sync import parse_task_blocks

# Inline markup patterns
_BOLD_RE   = re.compile(r'\*\*(.+?)\*\*', re.DOTALL)
_ITALIC_RE = re.compile(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', re.DOTALL)
_UNDER_RE  = re.compile(r'__(.+?)__', re.DOTALL)

# Line-level patterns (checked at start of each line)
_NUM_LINE_RE  = re.compile(r'^(\d+)\.\s+(.*)')
_BULL_LINE_RE = re.compile(r'^([-•])\s+(.*)')
_QUOT_LINE_RE = re.compile(r'^>\s+(.*)')


class NotesEditor(Gtk.Box):
    """Notes editor with autosave, live bold/italic/underline/list rendering,
    auto-numbered lists, bullet lists, and blockquote continuation."""

    __gsignals__ = {
        'content-saved': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self, autosave_delay_ms: int = 500):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._autosave_delay = autosave_delay_ms
        self._autosave_source_id = None
        self._save_callback = None
        self._loading = False

        # ── Header row ─────────────────────────────────────────
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.set_margin_start(14)
        header.set_margin_end(12)
        header.set_margin_top(14)
        header.set_margin_bottom(4)

        notes_label = Gtk.Label(label="NOTES")
        notes_label.add_css_class('section-header')
        notes_label.set_halign(Gtk.Align.START)
        notes_label.set_hexpand(True)
        header.append(notes_label)

        # Formatting buttons B I U
        fmt_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        for markup, tooltip, action in [
            ('<b>B</b>', 'Bold — Ctrl+B',      self._insert_bold),
            ('<i>I</i>', 'Italic — Ctrl+I',    self._insert_italic),
            ('<u>U</u>', 'Underline — Ctrl+U', self._insert_underline),
        ]:
            lbl = Gtk.Label()
            lbl.set_markup(markup)
            btn = Gtk.Button()
            btn.set_child(lbl)
            btn.set_tooltip_text(tooltip)
            btn.add_css_class('notes-fmt-btn')
            btn.connect('clicked', lambda _b, a=action: a())
            fmt_box.append(btn)
        header.append(fmt_box)

        self._save_indicator = Gtk.Label(label='')
        self._save_indicator.add_css_class('save-indicator')
        self._save_indicator.set_margin_start(8)
        header.append(self._save_indicator)
        self.append(header)

        # ── Overlay: textview + placeholder ───────────────────
        overlay = Gtk.Overlay()

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_height(True)
        scroll.set_min_content_height(200)
        scroll.set_max_content_height(380)
        scroll.add_css_class('notes-scroll')

        self._textview = Gtk.TextView()
        self._textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._textview.set_left_margin(14)
        self._textview.set_right_margin(14)
        self._textview.set_top_margin(10)
        self._textview.set_bottom_margin(12)
        self._textview.set_accepts_tab(False)
        self._textview.set_pixels_above_lines(1)
        self._textview.set_pixels_below_lines(1)
        self._textview.set_pixels_inside_wrap(2)
        self._textview.add_css_class('notes-textview')

        buf = self._textview.get_buffer()
        self._tag_bold   = buf.create_tag('bold',      weight=Pango.Weight.BOLD)
        self._tag_italic = buf.create_tag('italic',    style=Pango.Style.ITALIC)
        self._tag_under  = buf.create_tag('underline', underline=Pango.Underline.SINGLE)
        self._tag_syntax = buf.create_tag('syntax',    foreground='#4a5068', scale=0.85)
        self._tag_list   = buf.create_tag('list',      left_margin=18, indent=-18)
        self._tag_prefix = buf.create_tag('prefix',    foreground='#5a5f80')
        self._tag_quote  = buf.create_tag('blockquote', left_margin=14, pixels_above_lines=2,
                                          pixels_below_lines=2)
        # Task block tags
        self._tag_task_block   = buf.create_tag('task_block',   left_margin=8,
                                                 pixels_above_lines=1, pixels_below_lines=1)
        self._tag_task_bracket = buf.create_tag('task_bracket', foreground='#8b5cf6',
                                                 weight=Pango.Weight.BOLD)
        self._tag_task_done    = buf.create_tag('task_done',    strikethrough=True,
                                                 foreground='#5a5870')
        try:
            rgba = Gdk.RGBA()
            rgba.parse('rgba(80,70,120,0.18)')
            self._tag_quote.set_property('paragraph-background-rgba', rgba)
            block_bg = Gdk.RGBA()
            block_bg.parse('rgba(100,80,200,0.09)')
            self._tag_task_block.set_property('paragraph-background-rgba', block_bg)
        except Exception:
            pass

        buf.connect('changed', self._on_text_changed)

        # Key controller — CAPTURE phase so we intercept Enter before textview
        kctrl = Gtk.EventControllerKey()
        kctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        kctrl.connect('key-pressed', self._on_key_pressed)
        self._textview.add_controller(kctrl)

        scroll.set_child(self._textview)
        overlay.set_child(scroll)

        # Placeholder label
        self._placeholder = Gtk.Label(label='Write your thoughts for today…')
        self._placeholder.add_css_class('notes-placeholder')
        self._placeholder.set_halign(Gtk.Align.START)
        self._placeholder.set_valign(Gtk.Align.START)
        self._placeholder.set_margin_start(15)
        self._placeholder.set_margin_top(11)
        self._placeholder.set_sensitive(False)
        overlay.add_overlay(self._placeholder)

        self.append(overlay)

    # ── Keyboard shortcuts ─────────────────────────────────────

    def _on_key_pressed(self, _ctrl, keyval, _keycode, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        if ctrl:
            if keyval == Gdk.KEY_b:
                self._insert_bold()
                return True
            if keyval == Gdk.KEY_i:
                self._insert_italic()
                return True
            if keyval == Gdk.KEY_u:
                self._insert_underline()
                return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if not ctrl:
                return self._handle_enter()
        return False

    # ── Auto-list Enter handling ────────────────────────────────

    def _handle_enter(self) -> bool:
        buf = self._textview.get_buffer()
        cursor = buf.get_iter_at_mark(buf.get_insert())

        # Only activate when cursor is at end-of-line
        if not cursor.ends_line():
            return False

        line_start = cursor.copy()
        line_start.set_line_offset(0)
        line_text = buf.get_text(line_start, cursor, False)

        # Numbered list
        m = _NUM_LINE_RE.match(line_text)
        if m:
            if not m.group(2).strip():
                # Empty item — exit list mode
                buf.delete(line_start, cursor)
            else:
                next_num = int(m.group(1)) + 1
                buf.insert_at_cursor(f'\n{next_num}. ')
            return True

        # Bullet list
        m = _BULL_LINE_RE.match(line_text)
        if m:
            if not m.group(2).strip():
                buf.delete(line_start, cursor)
            else:
                buf.insert_at_cursor(f'\n{m.group(1)} ')
            return True

        # Blockquote
        m = _QUOT_LINE_RE.match(line_text)
        if m:
            if not m.group(1).strip():
                buf.delete(line_start, cursor)
            else:
                buf.insert_at_cursor('\n> ')
            return True

        return False

    # ── Marker insertion ───────────────────────────────────────

    def _wrap_selection(self, open_m: str, close_m: str):
        buf = self._textview.get_buffer()
        if buf.get_has_selection():
            start, end = buf.get_selection_bounds()
            text = buf.get_text(start, end, False)
            buf.delete(start, end)
            buf.insert_at_cursor(f'{open_m}{text}{close_m}')
        else:
            buf.insert_at_cursor(f'{open_m}{close_m}')
            it = buf.get_iter_at_mark(buf.get_insert())
            it.backward_chars(len(close_m))
            buf.place_cursor(it)

    def _insert_bold(self):       self._wrap_selection('**', '**')
    def _insert_italic(self):     self._wrap_selection('*', '*')
    def _insert_underline(self):  self._wrap_selection('__', '__')

    # ── Live formatting ────────────────────────────────────────

    def _apply_tags(self):
        buf  = self._textview.get_buffer()
        s    = buf.get_start_iter()
        e    = buf.get_end_iter()
        text = buf.get_text(s, e, False)

        for tag in (self._tag_bold, self._tag_italic, self._tag_under,
                    self._tag_syntax, self._tag_list, self._tag_prefix,
                    self._tag_quote, self._tag_task_block, self._tag_task_bracket,
                    self._tag_task_done):
            buf.remove_tag(tag, s, e)

        # Inline bold
        for m in _BOLD_RE.finditer(text):
            self._tag_span(buf, m.start(),   m.start(1), self._tag_syntax)
            self._tag_span(buf, m.start(1),  m.end(1),   self._tag_bold)
            self._tag_span(buf, m.end(1),    m.end(),    self._tag_syntax)

        bold_ranges = {i for m in _BOLD_RE.finditer(text) for i in range(m.start(), m.end())}

        # Inline italic (skip inside bold)
        for m in _ITALIC_RE.finditer(text):
            if m.start() in bold_ranges:
                continue
            self._tag_span(buf, m.start(),   m.start(1), self._tag_syntax)
            self._tag_span(buf, m.start(1),  m.end(1),   self._tag_italic)
            self._tag_span(buf, m.end(1),    m.end(),    self._tag_syntax)

        # Inline underline
        for m in _UNDER_RE.finditer(text):
            self._tag_span(buf, m.start(),   m.start(1), self._tag_syntax)
            self._tag_span(buf, m.start(1),  m.end(1),   self._tag_under)
            self._tag_span(buf, m.end(1),    m.end(),    self._tag_syntax)

        # Line-level: numbered list, bullet list, blockquote
        lines_list = text.split('\n')
        # Pre-compute char offset of each line start
        line_offsets = [0]
        for ln in lines_list[:-1]:
            line_offsets.append(line_offsets[-1] + len(ln) + 1)

        for ln_no, line in enumerate(lines_list):
            pos     = line_offsets[ln_no]
            end_pos = pos + len(line)
            if _NUM_LINE_RE.match(line) or _BULL_LINE_RE.match(line):
                prefix_end = line.index(' ') + 2 if ' ' in line else len(line)
                self._tag_span(buf, pos, pos + prefix_end, self._tag_prefix)
                self._tag_span(buf, pos, end_pos, self._tag_list)
            elif _QUOT_LINE_RE.match(line):
                self._tag_span(buf, pos, pos + 2, self._tag_prefix)
                self._tag_span(buf, pos, end_pos, self._tag_quote)

        # ── Task blocks ────────────────────────────────────────
        for block in parse_task_blocks(text):
            b_start  = line_offsets[block['line']]
            last_ln  = block['end_line']
            b_end    = line_offsets[last_ln] + len(lines_list[last_ln])

            # Whole-block subtle background
            self._tag_span(buf, b_start, b_end, self._tag_task_block)

            # Purple bracket chars: [] or [x]
            bracket_end = b_start + block['marker_len']
            self._tag_span(buf, b_start, bracket_end, self._tag_task_bracket)

            # Completed: strikethrough on description text
            if block['completed']:
                desc_start   = bracket_end + 1   # skip the space after bracket
                task_line_end = line_offsets[block['line']] + len(lines_list[block['line']])
                self._tag_span(buf, desc_start, task_line_end, self._tag_task_done)

    def _tag_span(self, buf, char_start: int, char_end: int, tag):
        buf.apply_tag(tag,
                      buf.get_iter_at_offset(char_start),
                      buf.get_iter_at_offset(char_end))

    # ── Load / save ────────────────────────────────────────────

    def load_content(self, text: str):
        self._loading = True
        self._textview.get_buffer().set_text(text or '')
        self._loading = False
        self._apply_tags()
        self._update_placeholder()

    def get_content(self) -> str:
        buf = self._textview.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

    def set_save_callback(self, cb):
        self._save_callback = cb

    def _on_text_changed(self, buf):
        if self._loading:
            return
        self._apply_tags()
        self._update_placeholder()
        if self._autosave_source_id is not None:
            GLib.source_remove(self._autosave_source_id)
            self._autosave_source_id = None
        self._autosave_source_id = GLib.timeout_add(
            self._autosave_delay, self._do_autosave
        )

    def _update_placeholder(self):
        buf = self._textview.get_buffer()
        empty = not buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        self._placeholder.set_visible(empty)

    def _do_autosave(self) -> bool:
        self._autosave_source_id = None
        if self._save_callback:
            self._save_callback(self.get_content())
        self._show_saved_indicator()
        return False

    def _show_saved_indicator(self):
        self._save_indicator.set_label('Saved ✓')
        GLib.timeout_add(2000, self._hide_saved_indicator)

    def _hide_saved_indicator(self) -> bool:
        self._save_indicator.set_label('')
        return False

    def grab_focus_editor(self):
        self._textview.grab_focus()
