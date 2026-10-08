#!/usr/bin/env python3
"""
Echo Weather - Desktop Application Entrypoint
Meteorological desktop application for Linux.
"""

import os
import signal
import sys

from logger import get_logger

logger = get_logger("main")


def _check_system_dependencies():
    missing = []
    try:
        import gi
        gi.require_version("Gtk", "4.0")
    except (ValueError, ImportError):
        missing.append("GTK4 / PyGObject (gir1.2-gtk-4.0, python3-gi)")

    try:
        import cairo  # noqa: F401
    except ImportError:
        missing.append("pycairo (python3-cairo)")

    if missing:
        logger.critical("Missing system dependencies for Echo Weather:")
        for item in missing:
            logger.critical("  • %s", item)
        sys.exit(1)


_check_system_dependencies()

import gi

gi.require_version("Gtk", "4.0")
HAS_ADW = False
try:
    gi.require_version("Adw", "1")
    from gi.repository import Adw
    HAS_ADW = True
except (ValueError, ImportError):
    HAS_ADW = False

from gi.repository import Gio, Gtk

from ui import EchoWeatherWindow

BaseApplication = Adw.Application if HAS_ADW else Gtk.Application


class EchoWeatherApp(BaseApplication):
    def __init__(self):
        super().__init__(
            application_id="com.echo.weather",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        )
        self.window = None
        self._target_city = None

    def do_activate(self):
        if not self.window:
            self.window = EchoWeatherWindow(self, initial_city=self._target_city)
            self.window.present()
        else:
            if self._target_city:
                self.window.load_city(self._target_city)
            self.window.present()

    def do_command_line(self, command_line):
        args = command_line.get_arguments()
        # args[0] is program name, subsequent are city names
        if len(args) > 1:
            self._target_city = " ".join(args[1:]).strip()
        else:
            self._target_city = None

        self.activate()
        return 0


def on_signal(signum, frame):
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    app = EchoWeatherApp()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


if __name__ == "__main__":
    main()
