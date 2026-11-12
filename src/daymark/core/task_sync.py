"""
task_sync — synchronises DB tasks with [] markers in a daily note.

Task block syntax:
    [] task description        ← incomplete
    [x] task description       ← completed
    any non-empty lines here   ← context (prose, bullets, numbered lists)
                               ← blank line ends the block

Only tasks with source='note' are managed here.
Tasks with source='direct' (legacy / quick-add fallback) are never touched.
"""
import re
from daymark.core.tasks import TaskManager

_TASK_LINE_RE = re.compile(r'^\[([ xX]?)\]\s+(.+)')


def parse_task_blocks(text: str) -> list:
    """Return a list of task-block dicts parsed from note text.

    Each dict has:
        line        — 0-based index of the [] line
        end_line    — 0-based index of the last context line (== line if no context)
        completed   — bool
        description — str (stripped)
        marker_len  — int, length of the bracket token (2 for [], 3 for [x])
        context     — list[str] of context lines
    """
    blocks = []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        m = _TASK_LINE_RE.match(lines[i])
        if m:
            marker_inner = m.group(1)   # '', ' ', 'x', or 'X'
            completed    = marker_inner.lower() == 'x'
            description  = m.group(2).strip()
            marker_len   = 2 + len(marker_inner)  # [] = 2, [ ] = 3, [x] = 3

            context = []
            j = i + 1
            while j < len(lines):
                stripped = lines[j].strip()
                if not stripped:                    # blank line → end of block
                    break
                if _TASK_LINE_RE.match(lines[j]):  # next task → end of block
                    break
                context.append(lines[j])
                j += 1

            blocks.append({
                'line':        i,
                'end_line':    j - 1,
                'completed':   completed,
                'description': description,
                'marker_len':  marker_len,
                'context':     context,
            })
            i = j
        else:
            i += 1
    return blocks


def sync_tasks_from_note(task_mgr: TaskManager, date_str: str, note_text: str):
    """Diff the note's [] lines against DB tasks; create / update / delete.

    Rules:
    - New [] lines  → create task (source='note')
    - [] → [x]      → mark task complete
    - [x] → []      → reopen task
    - [] line gone  → delete task (source='note' only)
    - 'direct' tasks are never modified
    """
    parsed  = parse_task_blocks(note_text)
    p_map   = {b['description']: b for b in parsed}

    db_tasks   = task_mgr.get_tasks_for_date(date_str)
    note_tasks = {t.description: t for t in db_tasks
                  if getattr(t, 'source', 'direct') == 'note'}

    # Create or update completion state
    for desc, block in p_map.items():
        if desc in note_tasks:
            task = note_tasks[desc]
            if task.completed != block['completed']:
                if block['completed']:
                    task_mgr.complete_task(task.id)
                else:
                    task_mgr.reopen_task(task.id)
        else:
            created = task_mgr.create_task(desc, date_str, source='note')
            if block['completed']:
                task_mgr.complete_task(created.id)

    # Delete note-sourced tasks whose [] line disappeared
    for desc, task in note_tasks.items():
        if desc not in p_map:
            task_mgr.delete_task(task.id)


def remove_task_block_from_note(note_text: str, description: str) -> str:
    """Remove the [] block (task line + all context lines) matching description."""
    lines = note_text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        m = _TASK_LINE_RE.match(lines[i])
        if m and m.group(2).strip() == description:
            # Skip task line + its context lines
            j = i + 1
            while j < len(lines):
                if not lines[j].strip():   # blank line after block — consume it
                    j += 1
                    break
                if _TASK_LINE_RE.match(lines[j]):  # next task starts
                    break
                j += 1
            i = j
        else:
            result.append(lines[i])
            i += 1
    # Collapse any consecutive blank lines left behind
    cleaned = []
    prev_blank = False
    for line in result:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = is_blank
    return '\n'.join(cleaned)


def update_task_in_note(note_text: str, description: str, completed: bool) -> str:
    """Find the [] / [x] line matching *description* and flip its marker.

    Returns the updated note text (unchanged if the line is not found).
    """
    new_marker = '[x]' if completed else '[]'
    lines = note_text.split('\n')
    for i, line in enumerate(lines):
        m = _TASK_LINE_RE.match(line)
        if m and m.group(2).strip() == description:
            lines[i] = f'{new_marker} {description}'
            return '\n'.join(lines)
    return note_text
