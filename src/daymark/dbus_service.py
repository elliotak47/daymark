import logging
from gi.repository import Gio, GLib

logger = logging.getLogger(__name__)

_DBUS_XML = """
<node>
  <interface name="com.daymark.App">
    <method name="Toggle"/>
    <method name="Show"/>
    <method name="Quit"/>
    <method name="GetPendingCount">
      <arg type="u" direction="out" name="count"/>
    </method>
  </interface>
</node>
"""


class DaymarkDBusService:
    def __init__(self, app):
        self._app    = app
        self._reg_id = None
        self._conn   = None

        Gio.bus_own_name(
            Gio.BusType.SESSION,
            'com.daymark.App',
            Gio.BusNameOwnerFlags.NONE,
            self._on_bus_acquired,
            self._on_name_acquired,
            self._on_name_lost,
        )

    def _on_bus_acquired(self, conn, name):
        self._conn = conn
        node = Gio.DBusNodeInfo.new_for_xml(_DBUS_XML)
        self._reg_id = conn.register_object(
            '/com/daymark/App',
            node.interfaces[0],
            self._handle_method,
            None, None,
        )
        logger.info('D-Bus registered')

    def _on_name_acquired(self, _conn, name):
        logger.info('D-Bus name: %s', name)

    def _on_name_lost(self, _conn, name):
        logger.warning('D-Bus name lost: %s', name)

    def _handle_method(self, conn, sender, path, iface, method, params, invocation):
        if method == 'Toggle':
            GLib.idle_add(self._app.toggle_window)
            invocation.return_value(None)
        elif method == 'Show':
            GLib.idle_add(self._app.show_window)
            invocation.return_value(None)
        elif method == 'Quit':
            GLib.idle_add(self._app.quit)
            invocation.return_value(None)
        elif method == 'GetPendingCount':
            count = self._app.get_pending_count()
            invocation.return_value(GLib.Variant('(u)', (count,)))
        else:
            invocation.return_error_literal(
                Gio.dbus_error_quark(), Gio.DBusError.UNKNOWN_METHOD, f'Unknown: {method}'
            )
