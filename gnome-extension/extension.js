/**
 * Daymark — panel icon extension
 *
 * Left-click  : toggle Daymark window
 * Right-click : Quit option
 * Badge       : pending task count for today
 * Position    : top-right corner, just below the panel
 */

import St from 'gi://St';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const DBUS_NAME  = 'com.daymark.App';
const DBUS_PATH  = '/com/daymark/App';
const DBUS_IFACE = 'com.daymark.App';
const LAUNCHER   = `${GLib.get_home_dir()}/.local/bin/daymark`;

export default class DaymarkExtension {

    enable() {
        this._button = new PanelMenu.Button(0.0, 'Daymark', false);

        const box = new St.BoxLayout({ y_align: Clutter.ActorAlign.CENTER });

        const icon = new St.Icon({
            icon_name: 'document-edit-symbolic',
            style_class: 'system-status-icon',
        });
        box.add_child(icon);

        this._badge = new St.Label({
            text: '',
            y_align: Clutter.ActorAlign.CENTER,
            style: 'font-size: 10px; padding: 0 3px 0 1px; font-weight: bold;',
        });
        box.add_child(this._badge);
        this._button.add_child(box);

        // captured-event fires BEFORE PanelMenu.Button's own button-press-event handler,
        // so we can intercept left-click before the menu opens.
        this._button.connect('captured-event', (_a, event) => {
            if (event.type() !== Clutter.EventType.BUTTON_PRESS)
                return Clutter.EVENT_PROPAGATE;
            if (event.get_button() === 1) {
                this._button.menu.close();
                this._toggle();
                return Clutter.EVENT_STOP;   // prevent menu from opening
            }
            return Clutter.EVENT_PROPAGATE;  // right-click → menu opens normally
        });

        const quitItem = new PopupMenu.PopupMenuItem('Quit Daymark');
        quitItem.connect('activate', () => this._callDbus('Quit'));
        this._button.menu.addMenuItem(quitItem);

        Main.panel.addToStatusArea('daymark', this._button, 1, 'right');

        this._refreshBadge();
        this._badgeTimer = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT, 60,
            () => { this._refreshBadge(); return GLib.SOURCE_CONTINUE; }
        );

        log('Daymark: enabled');
    }

    disable() {
        if (this._badgeTimer) { GLib.source_remove(this._badgeTimer); this._badgeTimer = null; }
        this._button?.destroy();
        this._button = null;
        this._badge  = null;
        log('Daymark: disabled');
    }

    _toggle() {
        Gio.DBus.session.call(
            DBUS_NAME, DBUS_PATH, DBUS_IFACE, 'Toggle',
            null, null, Gio.DBusCallFlags.NONE, 500, null,
            (_conn, res) => {
                try {
                    Gio.DBus.session.call_finish(res);
                    GLib.timeout_add(300, () => { this._positionWindow(); return GLib.SOURCE_REMOVE; });
                    GLib.timeout_add(350, () => { this._refreshBadge();   return GLib.SOURCE_REMOVE; });
                } catch (_e) {
                    this._spawn();
                }
            }
        );
    }

    _positionWindow() {
        for (const actor of global.get_window_actors()) {
            const win = actor.meta_window;
            if ((win.get_title() || '').trim() !== 'Daymark') continue;
            if (win.minimized) continue;

            const rect     = win.get_frame_rect();
            const winWidth = rect.width  || 460;
            const panelH   = Main.panel.height;

            // Position directly below the panel button, right-aligned to it
            const [btnX] = this._button.get_transformed_position();
            const btnW   = this._button.width;
            const area   = win.get_work_area_current_monitor();

            // Right-align window to button, clamp so it doesn't go off-screen
            let x = Math.round(btnX + btnW - winWidth);
            x = Math.max(area.x + 4, Math.min(x, area.x + area.width - winWidth - 4));
            const y = panelH + 4;

            win.move_frame(true, x, y);

            // Suppress dock / taskbar icon
            try { win.skip_taskbar = true; } catch (_) {}
            return;
        }
    }

    _refreshBadge() {
        Gio.DBus.session.call(
            DBUS_NAME, DBUS_PATH, DBUS_IFACE, 'GetPendingCount',
            null, new GLib.VariantType('(u)'),
            Gio.DBusCallFlags.NONE, 500, null,
            (_conn, res) => {
                try {
                    const count = Gio.DBus.session.call_finish(res).get_child_value(0).get_uint32();
                    if (this._badge) this._badge.text = count > 0 ? String(count) : '';
                } catch (_e) {
                    if (this._badge) this._badge.text = '';
                }
            }
        );
    }

    _callDbus(method) {
        Gio.DBus.session.call(
            DBUS_NAME, DBUS_PATH, DBUS_IFACE, method,
            null, null, Gio.DBusCallFlags.NONE, 500, null, null
        );
    }

    _spawn() {
        try {
            GLib.spawn_command_line_async(LAUNCHER);
            GLib.timeout_add(1500, () => { this._positionWindow(); return GLib.SOURCE_REMOVE; });
            GLib.timeout_add(1600, () => { this._refreshBadge();   return GLib.SOURCE_REMOVE; });
        } catch (e) {
            logError(e, 'Daymark: spawn failed');
        }
    }
}
