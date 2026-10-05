"""
Базовый класс для интерактивных 24-часовых графиков метеорологических метрик с интерактивным ползунком (скруббером).
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from logger import get_logger

logger = get_logger("weather.detail_cards.base")


class BaseWeatherHourlyArea(Gtk.DrawingArea):
    """Базовый класс для интерактивных графиков почасовых метрик со скруббером."""

    def __init__(self, content_height: int = 190):
        super().__init__()
        self.set_content_height(content_height)
        self.set_hexpand(True)
        self.cur_hour = 12
        self.is_today = True

        self.is_scrubbing = False
        self.scrub_x = 0.0
        self.scrub_y = 0.0
        self.scrub_hour_frac = None
        self.on_scrub = None

        self._setup_gestures()
        self._setup_cursor()
        self.set_draw_func(self._on_draw)

    def _setup_gestures(self):
        self.drag_gesture = Gtk.GestureDrag.new()
        self.drag_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.drag_gesture.connect("drag-begin", self._on_drag_begin)
        self.drag_gesture.connect("drag-update", self._on_drag_update)
        self.drag_gesture.connect("drag-end", self._on_drag_end)
        self.drag_gesture.connect("cancel", self._on_drag_end)
        self.add_controller(self.drag_gesture)

    def _setup_cursor(self):
        try:
            self.set_cursor_from_name("pointer")
        except (GLib.Error, TypeError) as e:
            logger.debug("Failed setting pointer cursor: %s", e)

    def _on_drag_begin(self, gesture, start_x, start_y):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.is_scrubbing = True
        self._process_scrub(start_x, start_y)

    def _on_drag_update(self, gesture, offset_x, offset_y):
        ok, start_x, start_y = gesture.get_start_point()
        if not ok:
            start_x, start_y = 0.0, 0.0
        self._process_scrub(start_x + offset_x, start_y + offset_y)

    def _on_drag_end(self, gesture, offset_x=0.0, offset_y=0.0):
        self.is_scrubbing = False
        self.scrub_hour_frac = None
        self.queue_draw()
        if callable(self.on_scrub):
            self.on_scrub({"active": False})

    def _calc_frac_h(self, x: float, pad_l: float, plot_w: float) -> float:
        clamped_x = max(pad_l, min(pad_l + plot_w, x))
        frac_h = ((clamped_x - pad_l) / float(plot_w)) * 23.0
        return max(0.0, min(23.0, frac_h))

    def _process_scrub(self, x: float, y: float):
        """Переопределяется в подклассах для обработки специфики метрики."""
        pass

    def _on_draw(self, area, cr, width, height):
        """Переопределяется в подклассах для отрисовки графиков."""
        pass
