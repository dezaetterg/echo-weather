"""
Карточка текущих условий: 24-часовой сплайн температур (фактическая / ощущается), вероятность осадков и сводки.
"""

from __future__ import annotations

import math
import os

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from detail_cards.comparison_bar import ComparisonBarArea
from i18n import get_current_language, t
from providers.weather import WMO_INFO

WEATHER_ICONS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "weather")
)


def _get_icon_path(name: str) -> str:
    path = os.path.join(WEATHER_ICONS_DIR, name)
    return path if os.path.exists(path) else ""


class WeatherSplineArea(Gtk.DrawingArea):
    """Интерактивный 24-часовой температурный сплайн с Безье-интерполяцией и скруббером."""

    def __init__(self):
        super().__init__()
        self.set_content_height(190)
        self.set_hexpand(True)
        self.temps = [15] * 24
        self.apparent_temps = [15] * 24
        self.weather_codes = [0] * 24
        self.is_days = [1] * 24
        self.is_today = True
        self.cur_hour = 12
        self.show_feels_like = False
        self.bg_class = "weather-bg-clear-day"

        self.is_scrubbing = False
        self.scrub_x = 0.0
        self.scrub_y = 0.0
        self.scrub_hour_frac = None
        self.on_scrub = None

        self.drag_gesture = Gtk.GestureDrag.new()
        self.drag_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.drag_gesture.connect("drag-begin", self._on_drag_begin)
        self.drag_gesture.connect("drag-update", self._on_drag_update)
        self.drag_gesture.connect("drag-end", self._on_drag_end)
        self.drag_gesture.connect("cancel", self._on_drag_end)
        self.add_controller(self.drag_gesture)

        self.set_cursor_from_name("pointer")
        self.set_draw_func(self._on_draw)

    def _on_drag_begin(self, gesture, start_x, start_y):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.is_scrubbing = True
        self._process_scrub(start_x, start_y)

    def _on_drag_update(self, gesture, offset_x, offset_y):
        ok, start_x, start_y = gesture.get_start_point()
        if not ok:
            start_x, start_y = 0.0, 0.0
        cur_x = start_x + offset_x
        cur_y = start_y + offset_y
        self._process_scrub(cur_x, cur_y)

    def _on_drag_end(self, gesture, offset_x=0.0, offset_y=0.0):
        self.is_scrubbing = False
        self.scrub_hour_frac = None
        self.queue_draw()
        if callable(self.on_scrub):
            self.on_scrub({"active": False})

    def _process_scrub(self, x: float, y: float):
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return

        pad_l = 28
        pad_r = 42
        pad_t = 36
        pad_b = 32
        plot_w = max(10, width - pad_l - pad_r)
        plot_h = max(10, height - pad_t - pad_b)

        clamped_x = max(pad_l, min(pad_l + plot_w, x))
        frac_h = ((clamped_x - pad_l) / float(plot_w)) * 23.0
        frac_h = max(0.0, min(23.0, frac_h))

        active_temps = self.apparent_temps if self.show_feels_like else self.temps
        if not active_temps or len(active_temps) < 24:
            return

        min_t = min(active_temps)
        max_t = max(active_temps)
        y_min = math.floor((min_t - 2) / 5) * 5
        y_max = math.ceil((max_t + 3) / 5) * 5
        if y_max <= y_min:
            y_max = y_min + 10

        def to_xy(idx, val):
            px = pad_l + (idx / 23.0) * plot_w
            py = pad_t + plot_h - ((val - y_min) / float(y_max - y_min)) * plot_h
            return px, py

        pts = [to_xy(i, t_val) for i, t_val in enumerate(active_temps)]

        i = min(22, max(0, int(frac_h)))
        f = frac_h - i
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(len(pts) - 1, i + 2)]

        cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
        cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
        cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
        cp2y = p2[1] - (p3[1] - p1[1]) / 6.0

        u = 1.0 - f
        bx = (u**3) * p1[0] + 3 * (u**2) * f * cp1x + 3 * u * (f**2) * cp2x + (f**3) * p2[0]
        by = (u**3) * p1[1] + 3 * (u**2) * f * cp1y + 3 * u * (f**2) * cp2y + (f**3) * p2[1]

        self.scrub_x = bx
        self.scrub_y = by
        self.scrub_hour_frac = frac_h

        h_int = int(frac_h)
        minute = min(59, max(0, int(round((frac_h - h_int) * 60.0))))
        time_str = f"{h_int:02d}:{minute:02d}"

        norm_y = (pad_t + plot_h - by) / float(plot_h)
        val = y_min + norm_y * (y_max - y_min)

        other_temps = self.temps if self.show_feels_like else self.apparent_temps
        o_val = other_temps[i] * (1.0 - f) + other_temps[min(23, i + 1)] * f

        h_closest = min(23, max(0, int(round(frac_h))))
        code = self.weather_codes[h_closest] if h_closest < len(self.weather_codes) else 0
        is_day = bool(self.is_days[h_closest]) if h_closest < len(self.is_days) else True

        w_info = WMO_INFO.get(code, WMO_INFO.get(0))
        icon_name = w_info["icon_day"] if is_day else w_info["icon_night"]
        icon_path = _get_icon_path(icon_name)

        self.queue_draw()

        if callable(self.on_scrub):
            self.on_scrub({
                "active": True,
                "frac_h": frac_h,
                "hour": h_int,
                "minute": minute,
                "time_str": time_str,
                "temp": round(val),
                "other_temp": round(o_val),
                "weather_code": code,
                "is_day": is_day,
                "icon_path": icon_path,
                "show_feels_like": self.show_feels_like
            })

    def update_data(self, temps: list, apparent: list, codes: list, is_days: list, is_today: bool, cur_hour: int, show_feels_like: bool, bg_class: str = None):
        self.temps = temps if len(temps) >= 24 else ([15] * 24)
        self.apparent_temps = apparent if len(apparent) >= 24 else self.temps
        self.weather_codes = codes if len(codes) >= 24 else ([0] * 24)
        self.is_days = is_days if len(is_days) >= 24 else ([1] * 24)
        self.is_today = is_today
        self.cur_hour = cur_hour
        self.show_feels_like = show_feels_like
        if bg_class:
            self.bg_class = bg_class
        self.queue_draw()

    def set_feels_like(self, feels_like: bool):
        if self.show_feels_like != feels_like:
            self.show_feels_like = feels_like
            if self.is_scrubbing and self.scrub_hour_frac is not None:
                self._process_scrub(self.scrub_x, self.scrub_y)
            else:
                self.queue_draw()

    def _draw_weather_glyph(self, cr: cairo.Context, cx: float, cy: float, code: int, is_day: bool):
        if code in (0, 1):
            if is_day:
                cr.save()
                cr.set_source_rgba(1.0, 0.84, 0.22, 0.95)
                cr.arc(cx, cy, 2.6, 0, 2 * math.pi)
                cr.fill()
                cr.set_line_width(0.8)
                for a in range(0, 360, 45):
                    rad = math.radians(a)
                    cr.move_to(cx + 3.8 * math.cos(rad), cy + 3.8 * math.sin(rad))
                    cr.line_to(cx + 5.0 * math.cos(rad), cy + 5.0 * math.sin(rad))
                cr.stroke()
                cr.restore()
            else:
                cr.save()
                cr.set_source_rgba(0.85, 0.88, 1.0, 0.85)
                r = 3.6
                cr.arc(cx, cy, r, -0.45 * math.pi, 0.7 * math.pi)
                cr.curve_to(cx + 0.2, cy + 1.2, cx + 0.4, cy - 1.2, cx + r * math.cos(-0.45 * math.pi), cy + r * math.sin(-0.45 * math.pi))
                cr.close_path()
                cr.fill()
                cr.restore()
        elif code in (2, 3, 45, 48):
            cr.save()
            cr.set_source_rgba(0.85, 0.88, 0.95, 0.85)
            cr.arc(cx - 2.5, cy + 0.5, 2.2, 0.5 * math.pi, 1.5 * math.pi)
            cr.arc(cx, cy - 1.2, 2.5, math.pi, 2 * math.pi)
            cr.arc(cx + 2.8, cy + 0.5, 2.0, -0.5 * math.pi, 0.5 * math.pi)
            cr.close_path()
            cr.fill()
            cr.restore()
        elif code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
            cr.save()
            cr.set_source_rgba(0.70, 0.82, 0.95, 0.90)
            cr.arc(cx - 2.5, cy - 0.5, 2.2, 0.5 * math.pi, 1.5 * math.pi)
            cr.arc(cx, cy - 2.2, 2.5, math.pi, 2 * math.pi)
            cr.arc(cx + 2.8, cy - 0.5, 2.0, -0.5 * math.pi, 0.5 * math.pi)
            cr.close_path()
            cr.fill()
            cr.set_line_width(1.0)
            cr.set_source_rgba(0.35, 0.75, 1.0, 0.95)
            cr.move_to(cx - 1.5, cy + 2.5)
            cr.line_to(cx - 2.2, cy + 4.8)
            cr.move_to(cx + 1.8, cy + 2.5)
            cr.line_to(cx + 1.1, cy + 4.8)
            cr.stroke()
            cr.restore()
        elif code in (71, 73, 75, 77, 85, 86):
            cr.save()
            cr.set_source_rgba(0.85, 0.92, 1.0, 0.95)
            cr.arc(cx - 2.5, cy - 0.5, 2.2, 0.5 * math.pi, 1.5 * math.pi)
            cr.arc(cx, cy - 2.2, 2.5, math.pi, 2 * math.pi)
            cr.arc(cx + 2.8, cy - 0.5, 2.0, -0.5 * math.pi, 0.5 * math.pi)
            cr.close_path()
            cr.fill()
            cr.arc(cx - 1.5, cy + 3.5, 0.9, 0, 2 * math.pi)
            cr.arc(cx + 1.8, cy + 3.5, 0.9, 0, 2 * math.pi)
            cr.fill()
            cr.restore()
        elif code in (95, 96, 99):
            cr.save()
            cr.set_source_rgba(0.75, 0.75, 0.85, 0.95)
            cr.arc(cx - 2.5, cy - 0.5, 2.2, 0.5 * math.pi, 1.5 * math.pi)
            cr.arc(cx, cy - 2.2, 2.5, math.pi, 2 * math.pi)
            cr.arc(cx + 2.8, cy - 0.5, 2.0, -0.5 * math.pi, 0.5 * math.pi)
            cr.close_path()
            cr.fill()
            cr.set_line_width(1.0)
            cr.set_source_rgba(1.0, 0.85, 0.25, 1.0)
            cr.move_to(cx, cy + 1.5)
            cr.line_to(cx - 1.5, cy + 3.5)
            cr.line_to(cx + 0.5, cy + 3.5)
            cr.line_to(cx - 1.0, cy + 5.5)
            cr.stroke()
            cr.restore()
        else:
            cr.save()
            cr.set_source_rgba(1, 1, 1, 0.45)
            cr.arc(cx, cy, 2.0, 0, 2 * math.pi)
            cr.fill()
            cr.restore()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        active_temps = self.apparent_temps if self.show_feels_like else self.temps
        if not active_temps:
            return

        min_t = min(active_temps)
        max_t = max(active_temps)
        min_idx = active_temps.index(min_t)
        max_idx = active_temps.index(max_t)

        pad_l = 28
        pad_r = 42
        pad_t = 36
        pad_b = 32

        plot_w = max(10, width - pad_l - pad_r)
        plot_h = max(10, height - pad_t - pad_b)

        y_min = math.floor((min_t - 2) / 5) * 5
        y_max = math.ceil((max_t + 3) / 5) * 5
        if y_max <= y_min:
            y_max = y_min + 10

        def to_xy(idx, val):
            x = pad_l + (idx / 23.0) * plot_w
            y = pad_t + plot_h - ((val - y_min) / float(y_max - y_min)) * plot_h
            return x, y

        pts = [to_xy(i, t_val) for i, t_val in enumerate(active_temps)]

        cr.set_line_width(0.75)
        for v in range(int(y_min), int(y_max) + 1, 5):
            _, y = to_xy(0, v)
            cr.set_source_rgba(1, 1, 1, 0.08)
            cr.move_to(pad_l, y)
            cr.line_to(pad_l + plot_w, y)
            cr.stroke()

            cr.set_source_rgba(1, 1, 1, 0.45)
            cr.select_font_face("Inter, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(10)
            cr.move_to(pad_l + plot_w + 7, y + 3.5)
            cr.show_text(f"{v}°")

        top_glyph_y = pad_t - 15
        glyph_hours = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
        for gh in glyph_hours:
            if gh < len(self.weather_codes) and gh < len(self.is_days):
                gx = pad_l + (gh / 23.0) * plot_w
                self._draw_weather_glyph(cr, gx, top_glyph_y, self.weather_codes[gh], bool(self.is_days[gh]))

        hour_marks = [0, 6, 12, 18, 23]
        cr.set_source_rgba(1, 1, 1, 0.42)
        cr.set_font_size(10)
        for h in hour_marks:
            hx, _ = to_xy(h, y_min)
            txt = f"{h:02d}"
            ext = cr.text_extents(txt)
            cr.move_to(hx - ext.width / 2.0, height - 10)
            cr.show_text(txt)

        cr.save()
        cr.move_to(pts[0][0], pad_t + plot_h)
        cr.line_to(pts[0][0], pts[0][1])

        for i in range(len(pts) - 1):
            p0 = pts[max(0, i - 1)]
            p1 = pts[i]
            p2 = pts[i + 1]
            p3 = pts[min(len(pts) - 1, i + 2)]

            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
            cr.curve_to(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])

        cr.line_to(pts[-1][0], pad_t + plot_h)
        cr.close_path()

        pat = cairo.LinearGradient(0, pad_t, 0, pad_t + plot_h)
        if self.show_feels_like:
            pat.add_color_stop_rgba(0.0, 1.0, 0.65, 0.18, 0.38)
            pat.add_color_stop_rgba(0.55, 1.0, 0.60, 0.15, 0.09)
            pat.add_color_stop_rgba(1.0, 1.0, 0.60, 0.15, 0.00)
            stroke_rgba = (1.0, 0.68, 0.22, 0.98)
        else:
            bg = self.bg_class or ""
            if "clear-day" in bg:
                pat.add_color_stop_rgba(0.0, 1.0, 0.88, 0.40, 0.42)
                pat.add_color_stop_rgba(0.55, 1.0, 1.0, 1.0, 0.12)
                pat.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.00)
                stroke_rgba = (1.0, 1.0, 1.0, 0.98)
            elif "clear-night" in bg:
                pat.add_color_stop_rgba(0.0, 0.40, 0.65, 1.0, 0.35)
                pat.add_color_stop_rgba(0.55, 0.30, 0.45, 0.85, 0.08)
                pat.add_color_stop_rgba(1.0, 0.20, 0.30, 0.70, 0.00)
                stroke_rgba = (0.60, 0.82, 1.0, 0.98)
            elif "clouds-day" in bg:
                pat.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.32)
                pat.add_color_stop_rgba(0.55, 1.0, 1.0, 1.0, 0.10)
                pat.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.00)
                stroke_rgba = (1.0, 1.0, 1.0, 0.98)
            elif "clouds-night" in bg:
                pat.add_color_stop_rgba(0.0, 0.70, 0.60, 1.0, 0.30)
                pat.add_color_stop_rgba(0.55, 0.50, 0.40, 0.80, 0.08)
                pat.add_color_stop_rgba(1.0, 0.30, 0.25, 0.60, 0.00)
                stroke_rgba = (0.85, 0.80, 1.0, 0.98)
            elif "rain" in bg:
                pat.add_color_stop_rgba(0.0, 0.20, 0.90, 0.82, 0.36)
                pat.add_color_stop_rgba(0.55, 0.15, 0.65, 0.75, 0.09)
                pat.add_color_stop_rgba(1.0, 0.10, 0.40, 0.60, 0.00)
                stroke_rgba = (0.22, 0.95, 0.86, 0.98)
            elif "storm" in bg:
                pat.add_color_stop_rgba(0.0, 1.0, 0.82, 0.22, 0.36)
                pat.add_color_stop_rgba(0.55, 0.85, 0.65, 0.18, 0.09)
                pat.add_color_stop_rgba(1.0, 0.70, 0.50, 0.10, 0.00)
                stroke_rgba = (1.0, 0.88, 0.25, 0.98)
            elif "snow" in bg:
                pat.add_color_stop_rgba(0.0, 0.75, 0.92, 1.0, 0.38)
                pat.add_color_stop_rgba(0.55, 0.55, 0.80, 0.95, 0.10)
                pat.add_color_stop_rgba(1.0, 0.40, 0.65, 0.90, 0.00)
                stroke_rgba = (0.70, 0.92, 1.0, 0.98)
            elif "fog" in bg:
                pat.add_color_stop_rgba(0.0, 1.0, 0.76, 0.32, 0.32)
                pat.add_color_stop_rgba(0.55, 0.85, 0.65, 0.25, 0.08)
                pat.add_color_stop_rgba(1.0, 0.70, 0.50, 0.15, 0.00)
                stroke_rgba = (1.0, 0.80, 0.38, 0.98)
            elif "night" in bg:
                pat.add_color_stop_rgba(0.0, 0.45, 0.55, 0.95, 0.32)
                pat.add_color_stop_rgba(0.55, 0.30, 0.40, 0.85, 0.08)
                pat.add_color_stop_rgba(1.0, 0.20, 0.25, 0.70, 0.00)
                stroke_rgba = (0.60, 0.82, 1.0, 0.98)
            else:
                pat.add_color_stop_rgba(0.0, 0.35, 0.70, 1.0, 0.35)
                pat.add_color_stop_rgba(0.55, 0.25, 0.55, 0.90, 0.08)
                pat.add_color_stop_rgba(1.0, 0.20, 0.40, 0.80, 0.00)
                stroke_rgba = (0.45, 0.80, 1.0, 0.98)

        cr.set_source(pat)
        cr.fill()
        cr.restore()

        cr.save()
        cr.move_to(pts[0][0], pts[0][1])
        for i in range(len(pts) - 1):
            p0 = pts[max(0, i - 1)]
            p1 = pts[i]
            p2 = pts[i + 1]
            p3 = pts[min(len(pts) - 1, i + 2)]

            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
            cr.curve_to(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])

        cr.set_line_width(2.6)
        cr.set_source_rgba(*stroke_rgba)
        cr.stroke()
        cr.restore()

        if (not self.is_scrubbing) and self.is_today and 0 <= self.cur_hour < 24:
            ch_x, ch_y = pts[self.cur_hour]
            cr.set_line_width(1.0)
            cr.set_dash([3.0, 3.0])
            cr.set_source_rgba(1, 1, 1, 0.35)
            cr.move_to(ch_x, pad_t)
            cr.line_to(ch_x, pad_t + plot_h)
            cr.stroke()
            cr.set_dash([])

            cr.arc(ch_x, ch_y, 4.0, 0, 2 * math.pi)
            cr.set_source_rgba(1, 1, 1, 1.0)
            cr.fill()

        def draw_extreme_pill(x, y, text, is_top):
            cr.select_font_face("Inter, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(10.5)
            ext = cr.text_extents(text)
            p_w = ext.width + 12
            p_h = 18
            p_x = max(pad_l - 6, min(width - pad_r - p_w + 6, x - p_w / 2.0))
            p_y = (y - p_h - 7) if is_top else (y + 8)

            cr.save()
            cr.new_sub_path()
            r = 7.0
            cr.arc(p_x + r, p_y + r, r, math.pi, 1.5 * math.pi)
            cr.arc(p_x + p_w - r, p_y + r, r, 1.5 * math.pi, 2 * math.pi)
            cr.arc(p_x + p_w - r, p_y + p_h - r, r, 0, 0.5 * math.pi)
            cr.arc(p_x + r, p_y + p_h - r, r, 0.5 * math.pi, math.pi)
            cr.close_path()
            cr.set_source_rgba(0.12, 0.14, 0.20, 0.85)
            cr.fill_preserve()
            cr.set_source_rgba(1, 1, 1, 0.18)
            cr.set_line_width(0.8)
            cr.stroke()

            cr.set_source_rgba(1, 1, 1, 0.95)
            cr.move_to(p_x + (p_w - ext.width) / 2.0, p_y + p_h - 4.5)
            cr.show_text(text)
            cr.restore()

        max_x, max_y = pts[max_idx]
        min_x, min_y = pts[min_idx]
        draw_extreme_pill(max_x, max_y, f"{max_t}°", is_top=True)
        draw_extreme_pill(min_x, min_y, f"{min_t}°", is_top=False)

        if self.is_scrubbing and self.scrub_hour_frac is not None:
            sx = self.scrub_x
            sy = self.scrub_y

            cr.save()
            cr.set_line_width(4.0)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.18)
            cr.move_to(sx, pad_t)
            cr.line_to(sx, pad_t + plot_h)
            cr.stroke()

            cr.set_line_width(1.5)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
            cr.move_to(sx, pad_t)
            cr.line_to(sx, pad_t + plot_h)
            cr.stroke()

            cr.arc(sx, sy, 8.5, 0, 2 * math.pi)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.30)
            cr.fill()

            cr.arc(sx, sy, 5.5, 0, 2 * math.pi)
            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.fill_preserve()

            cr.set_line_width(1.2)
            cr.set_source_rgba(*stroke_rgba)
            cr.stroke()
            cr.restore()


class PrecipitationBarArea(Gtk.DrawingArea):
    """24-часовая столбчатая диаграмма вероятности осадков."""

    def __init__(self):
        super().__init__()
        self.set_content_height(100)
        self.set_hexpand(True)
        self.probs = [0] * 24
        self.set_draw_func(self._on_draw)

    def update_data(self, probs: list):
        self.probs = probs if len(probs) >= 24 else ([0] * 24)
        self.queue_draw()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        pad_l = 28
        pad_r = 38
        pad_t = 12
        pad_b = 24

        plot_w = max(10, width - pad_l - pad_r)
        plot_h = max(10, height - pad_t - pad_b)

        cr.set_line_width(0.7)
        for pct in (50, 100):
            y = pad_t + plot_h - (pct / 100.0) * plot_h
            cr.set_source_rgba(1, 1, 1, 0.08)
            cr.move_to(pad_l, y)
            cr.line_to(pad_l + plot_w, y)
            cr.stroke()

            cr.set_source_rgba(1, 1, 1, 0.40)
            cr.select_font_face("Inter, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(9)
            cr.move_to(pad_l + plot_w + 6, y + 3)
            cr.show_text(f"{pct}%")

        bar_slot = plot_w / 24.0
        bar_w = max(2.5, bar_slot - 3.5)

        for h, prob in enumerate(self.probs[:24]):
            bx = pad_l + h * bar_slot + (bar_slot - bar_w) / 2.0
            bh = (prob / 100.0) * plot_h
            by = pad_t + plot_h - bh

            cr.set_source_rgba(1, 1, 1, 0.04)
            cr.rectangle(bx, pad_t, bar_w, plot_h)
            cr.fill()

            if bh > 0.5:
                pat = cairo.LinearGradient(bx, by, bx, by + bh)
                pat.add_color_stop_rgba(0.0, 0.28, 0.68, 1.0, 0.90)
                pat.add_color_stop_rgba(1.0, 0.15, 0.45, 0.85, 0.45)
                cr.set_source(pat)
                cr.rectangle(bx, by, bar_w, bh)
                cr.fill()

        cr.set_source_rgba(1, 1, 1, 0.42)
        cr.set_font_size(9.5)
        for h in (0, 6, 12, 18, 23):
            hx = pad_l + h * bar_slot + bar_slot / 2.0
            txt = f"{h:02d}"
            ext = cr.text_extents(txt)
            cr.move_to(hx - ext.width / 2.0, height - 6)
            cr.show_text(txt)


def build_conditions_view(sheet):
    """Построение карточки текущих условий и подключение к WeatherDetailSheet."""
    lang = get_current_language()
    is_ru = (lang == "ru")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.set_valign(Gtk.Align.START)

    # 1. Сплайн суточной температуры
    spline_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    spline_card.add_css_class("weather-glass-card")

    sheet.spline_area = WeatherSplineArea()
    sheet.spline_area.on_scrub = sheet._on_spline_scrub
    spline_card.append(sheet.spline_area)

    segmented_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    segmented_box.add_css_class("segmented-control")
    segmented_box.set_halign(Gtk.Align.CENTER)

    sheet.btn_seg_actual = Gtk.Button(label=t("weather_btn_actual"))
    sheet.btn_seg_actual.add_css_class("segmented-btn")
    sheet.btn_seg_actual.add_css_class("segmented-btn-active")
    sheet.btn_seg_actual.connect("clicked", lambda _: sheet._set_feels_like_mode(False))
    segmented_box.append(sheet.btn_seg_actual)

    sheet.btn_seg_feels = Gtk.Button(label=t("weather_btn_feels_like"))
    sheet.btn_seg_feels.add_css_class("segmented-btn")
    sheet.btn_seg_feels.connect("clicked", lambda _: sheet._set_feels_like_mode(True))
    segmented_box.append(sheet.btn_seg_feels)

    spline_card.append(segmented_box)

    sheet.lbl_seg_desc = Gtk.Label(label=t("weather_desc_actual_temp"))
    sheet.lbl_seg_desc.add_css_class("segmented-desc")
    sheet.lbl_seg_desc.set_halign(Gtk.Align.CENTER)
    spline_card.append(sheet.lbl_seg_desc)

    div_c = Gtk.Box()
    div_c.add_css_class("weather-card-divider")
    spline_card.append(div_c)

    sum_c_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    sum_c_box.add_css_class("weather-chart-summary-box")

    sheet.lbl_cond_sum_time = Gtk.Label()
    sheet.lbl_cond_sum_time.add_css_class("weather-chart-summary-time")
    sheet.lbl_cond_sum_time.set_halign(Gtk.Align.START)
    sheet.lbl_cond_sum_time.set_xalign(0.0)
    sum_c_box.append(sheet.lbl_cond_sum_time)

    sheet.lbl_cond_sum_text = Gtk.Label()
    sheet.lbl_cond_sum_text.add_css_class("weather-chart-summary-text")
    sheet.lbl_cond_sum_text.set_wrap(True)
    sheet.lbl_cond_sum_text.set_halign(Gtk.Align.START)
    sheet.lbl_cond_sum_text.set_xalign(0.0)
    sum_c_box.append(sheet.lbl_cond_sum_text)

    spline_card.append(sum_c_box)
    box.append(spline_card)

    # 2. Вероятность осадков
    precip_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    precip_card.add_css_class("weather-glass-card")

    precip_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    sheet.lbl_pr_title = Gtk.Label(label=t("weather_card_precip_probability"))
    sheet.lbl_pr_title.add_css_class("weather-section-title")
    precip_hdr.append(sheet.lbl_pr_title)
    precip_card.append(precip_hdr)

    sheet.lbl_pr_sub = Gtk.Label(label=t("weather_precip_chance_today", prob=0))
    sheet.lbl_pr_sub.add_css_class("weather-card-subtitle")
    sheet.lbl_pr_sub.set_halign(Gtk.Align.START)
    precip_card.append(sheet.lbl_pr_sub)

    sheet.precip_prob_area = PrecipitationBarArea()
    precip_card.append(sheet.precip_prob_area)

    sheet.lbl_pr_foot = Gtk.Label(label=t("weather_precip_explanation"))
    sheet.lbl_pr_foot.add_css_class("weather-footnote")
    sheet.lbl_pr_foot.set_wrap(True)
    sheet.lbl_pr_foot.set_halign(Gtk.Align.START)
    precip_card.append(sheet.lbl_pr_foot)

    box.append(precip_card)

    # 3. Объем осадков
    sheet.vol_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    sheet.vol_card.add_css_class("weather-glass-card")

    sheet.lbl_vol_title = Gtk.Label(label=t("weather_card_precip_volume"))
    sheet.lbl_vol_title.add_css_class("weather-section-title")
    sheet.lbl_vol_title.set_halign(Gtk.Align.START)
    sheet.vol_card.append(sheet.lbl_vol_title)

    div_v1 = Gtk.Box()
    div_v1.add_css_class("weather-card-divider")
    sheet.vol_card.append(div_v1)

    row_v1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    sheet.lbl_v1_desc = Gtk.Label(label=t("weather_card_expected_daily"))
    sheet.lbl_v1_desc.add_css_class("weather-body-text")
    row_v1.append(sheet.lbl_v1_desc)
    p_unit = "мм" if is_ru or lang in ("uk", "kk") else "mm"
    sheet.lbl_v1_val = Gtk.Label(label=f"0 {p_unit}")
    sheet.lbl_v1_val.add_css_class("weather-item-bold")
    sheet.lbl_v1_val.set_hexpand(True)
    sheet.lbl_v1_val.set_halign(Gtk.Align.END)
    row_v1.append(sheet.lbl_v1_val)
    sheet.vol_card.append(row_v1)

    box.append(sheet.vol_card)

    # 4. Прогноз
    sheet.summary_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    sheet.summary_card.add_css_class("weather-glass-card")

    sheet.lbl_sum_title = Gtk.Label(label=t("weather_card_forecast"))
    sheet.lbl_sum_title.add_css_class("weather-section-title")
    sheet.lbl_sum_title.set_halign(Gtk.Align.START)
    sheet.summary_card.append(sheet.lbl_sum_title)

    div_s = Gtk.Box()
    div_s.add_css_class("weather-card-divider")
    sheet.summary_card.append(div_s)

    sheet.lbl_summary_text = Gtk.Label()
    sheet.lbl_summary_text.add_css_class("weather-body-text")
    sheet.lbl_summary_text.set_wrap(True)
    sheet.lbl_summary_text.set_halign(Gtk.Align.START)
    sheet.summary_card.append(sheet.lbl_summary_text)

    box.append(sheet.summary_card)

    # 5. Сравнение по дням
    sheet.comp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    sheet.comp_card.add_css_class("weather-glass-card")

    sheet.lbl_comp_title = Gtk.Label(label=t("weather_card_day_comparison"))
    sheet.lbl_comp_title.add_css_class("weather-section-title")
    sheet.lbl_comp_title.set_halign(Gtk.Align.START)
    sheet.comp_card.append(sheet.lbl_comp_title)

    div_comp = Gtk.Box()
    div_comp.add_css_class("weather-card-divider")
    sheet.comp_card.append(div_comp)

    sheet.lbl_comp_sub = Gtk.Label()
    sheet.lbl_comp_sub.add_css_class("weather-card-subtitle")
    sheet.lbl_comp_sub.set_wrap(True)
    sheet.lbl_comp_sub.set_halign(Gtk.Align.START)
    sheet.comp_card.append(sheet.lbl_comp_sub)

    sheet.comp_bar = ComparisonBarArea()
    sheet.comp_card.append(sheet.comp_bar)

    box.append(sheet.comp_card)

    # 6. Ощущается как
    edu_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    edu_card.add_css_class("weather-glass-card")
    sheet.lbl_edu_title = Gtk.Label(label=t("weather_card_about_feels_like"))
    sheet.lbl_edu_title.add_css_class("weather-section-title")
    sheet.lbl_edu_title.set_halign(Gtk.Align.START)
    edu_card.append(sheet.lbl_edu_title)
    div_e = Gtk.Box()
    div_e.add_css_class("weather-card-divider")
    edu_card.append(div_e)
    sheet.lbl_edu_text = Gtk.Label(label=t("weather_desc_about_feels_like"))
    sheet.lbl_edu_text.add_css_class("weather-body-text")
    sheet.lbl_edu_text.set_wrap(True)
    sheet.lbl_edu_text.set_halign(Gtk.Align.START)
    edu_card.append(sheet.lbl_edu_text)
    box.append(edu_card)

    sheet.mode_stack.add_named(box, "conditions")
