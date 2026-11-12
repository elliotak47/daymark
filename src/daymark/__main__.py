import sys
from daymark.app import DaymarkApp


def main():
    app = DaymarkApp()
    # Filter out our custom flag before passing args to GLib (it doesn't know about --background)
    glib_args = [a for a in sys.argv if a != '--background']
    return app.run(glib_args)


if __name__ == '__main__':
    sys.exit(main())
