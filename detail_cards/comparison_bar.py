"""
Виджет полосы сравнения показателей день-к-дню (Day Comparison Bar).
Поддерживает интервальные метрики (диапазон температур, давление)
и точечные метрики (УФ, ветер, осадки, влажность, видимость).
"""

from __future__ import annotations

import math

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from i18n import get_current_language


class DayComparisonBarArea(Gtk.DrawingArea):
    """Универсальная графическая область сравнения сегодня и вчера с градиентами категорий."""

    def __init__(self):
        super().__init__()
        self.set_content_height(62)
        self.set_hexpand(True)
        self.mode = "range"
        self.category = "conditions"
        self.label_cur = "Сегодня"
        self.label_prev = "Вчера"
        self.val_cur_min = 10.0
        self.val_cur_max = 24.0
        self.val_prev_min = 8.0
        self.val_prev_max = 22.0
        self.val_cur = 24.0
        self.val_prev = 22.0
        self.unit = "°"
        self.precision = 0
        self.set_draw_func(self._on_draw)

    def update_data(self, t_min_today, t_max_today, t_min_yesterday, t_max_yesterday):
        """Совместимость для экрана общих условий."""
        self.update_range(
            "conditions",
            t("weather_today"),
            t("weather_yesterday"),
            t_min_today,
            t_max_today,
            t_min_yesterday,
            t_max_yesterday,
            "°",
            0,
        )

    def update_range(
        self,
        category: str,
        label_cur: str,
        label_prev: str,
        cur_min: float,
        cur_max: float,
        prev_min: float,
        prev_max: float,
        unit: str = "°",
        precision: int = 0,
    ):
        self.mode = "range"
        self.category = category
        self.label_cur = label_cur
        self.label_prev = label_prev
        self.val_cur_min = float(cur_min)
        self.val_cur_max = float(cur_max)
        self.val_prev_min = float(prev_min)
        self.val_prev_max = float(prev_max)
        self.unit = unit
        self.precision = precision
        self.queue_draw()

    def update_single(
        self,
        category: str,
        label_cur: str,
        label_prev: str,
        val_cur: float,
        val_prev: float,
        unit: str = "",
        precision: int = 0,
    ):
        self.mode = "single"
        self.category = category
        self.label_cur = label_cur
        self.label_prev = label_prev
        self.val_cur = float(val_cur)
        self.val_prev = float(val_prev)
        self.unit = unit
        self.precision = precision
        self.queue_draw()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        if self.mode == "range":
            all_vals = [self.val_cur_min, self.val_cur_max, self.val_prev_min, self.val_prev_max]
            pad = 2.0 if self.category != "pressure" else 3.0
            v_min = min(all_vals) - pad
            v_max = max(all_vals) + pad
        else:
            cat = self.category
            if cat == "conditions":
                all_t = [self.val_cur, self.val_prev]
                v_min = min(0.0, min(all_t) - 5.0)
                v_max = max(35.0, max(all_t) + 5.0)
            elif cat == "uv":
                v_min = 0.0
                v_max = max(11.0, self.val_cur, self.val_prev) + 0.5
            elif cat == "wind":
                v_min = 0.0
                v_max = max(25.0, self.val_cur, self.val_prev) + 5.0
            elif cat == "precipitation":
                v_min = 0.0
                v_max = max(5.0, self.val_cur, self.val_prev) + 1.0
            elif cat == "humidity":
                v_min = 0.0
                v_max = 100.0
            elif cat == "visibility":
                v_min = 0.0
                v_max = max(10.0, self.val_cur, self.val_prev) + 1.0
            elif cat == "pressure":
                if self.val_cur > 850 or self.val_prev > 850:
                    v_min = 960.0
                    v_max = 1040.0
                else:
                    v_min = 720.0
                    v_max = 780.0
            else:
                v_min = 0.0
                v_max = max(self.val_cur, self.val_prev, 1.0) * 1.2
        if v_max <= v_min:
            v_max = v_min + 5.0

        lbl_w = 64
        val_w = 68
        bar_x = lbl_w + 6
        bar_w = max(20, width - bar_x - val_w - 6)

        def to_x(val):
            ratio = (val - v_min) / float(v_max - v_min)
            ratio = max(0.0, min(1.0, ratio))
            return bar_x + ratio * bar_w

        def get_active_pattern(bx1, bw, by, bh, is_cur):
            pat = cairo.LinearGradient(bx1, by, bx1 + max(1.0, bw), by)
            alpha = 0.95 if is_cur else 0.58
            cat = self.category
            if cat == "conditions":
                pat.add_color_stop_rgba(0.0, 0.25, 0.65, 0.98, alpha)
                pat.add_color_stop_rgba(1.0, 0.98, 0.65, 0.25, alpha)
            elif cat == "uv":
                pat.add_color_stop_rgba(0.0, 0.30, 0.85, 0.40, alpha)
                pat.add_color_stop_rgba(0.5, 0.95, 0.75, 0.20, alpha)
                pat.add_color_stop_rgba(1.0, 0.95, 0.30, 0.30, alpha)
            elif cat == "wind":
                pat.add_color_stop_rgba(0.0, 0.20, 0.80, 0.80, alpha)
                pat.add_color_stop_rgba(1.0, 0.35, 0.95, 0.75, alpha)
            elif cat == "precipitation":
                pat.add_color_stop_rgba(0.0, 0.20, 0.60, 0.98, alpha)
                pat.add_color_stop_rgba(1.0, 0.35, 0.75, 1.00, alpha)
            elif cat == "humidity":
                pat.add_color_stop_rgba(0.0, 0.25, 0.70, 0.95, alpha)
                pat.add_color_stop_rgba(1.0, 0.40, 0.85, 0.95, alpha)
            elif cat == "visibility":
                pat.add_color_stop_rgba(0.0, 0.20, 0.85, 0.60, alpha)
                pat.add_color_stop_rgba(1.0, 0.40, 0.95, 0.75, alpha)
            elif cat == "pressure":
                pat.add_color_stop_rgba(0.0, 0.70, 0.45, 0.95, alpha)
                pat.add_color_stop_rgba(1.0, 0.85, 0.60, 1.00, alpha)
            else:
                pat.add_color_stop_rgba(0.0, 0.4, 0.7, 1.0, alpha)
                pat.add_color_stop_rgba(1.0, 0.6, 0.85, 1.0, alpha)
            return pat

        def draw_capsule(x, y, w, h):
            cr.new_sub_path()
            r = h / 2.0
            cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
            cr.arc(x + w - r, y + r, r, 1.5 * math.pi, 2 * math.pi)
            cr.arc(x + w - r, y + h - r, r, 0, 0.5 * math.pi)
            cr.arc(x + r, y + h - r, r, 0.5 * math.pi, math.pi)
            cr.close_path()

        def draw_row(y, label, val_text, is_cur, x1, x2):
            cr.set_source_rgba(1, 1, 1, 0.90 if is_cur else 0.55)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(11.0)
            cr.move_to(8, y + 10)
            cr.show_text(label)

            bh = 8
            by = y + 3
            cr.save()
            draw_capsule(bar_x, by, bar_w, bh)
            cr.set_source_rgba(1, 1, 1, 0.08)
            cr.fill()
            cr.restore()

            bx1 = min(x1, x2)
            bw = max(bh, abs(x2 - x1))
            cr.save()
            draw_capsule(bx1, by, bw, bh)
            cr.set_source(get_active_pattern(bx1, bw, by, bh, is_cur))
            cr.fill()
            cr.restore()

            cr.set_source_rgba(1, 1, 1, 0.85 if is_cur else 0.50)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if is_cur else cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(10.5)
            ext = cr.text_extents(val_text)
            cr.move_to(width - ext.width - 8, y + 10)
            cr.show_text(val_text)

        if self.mode == "range":
            x1 = to_x(self.val_cur_min)
            x2 = to_x(self.val_cur_max)
            if self.precision == 0:
                txt1 = f"{int(round(self.val_cur_min))}–{int(round(self.val_cur_max))}{self.unit}"
            else:
                txt1 = f"{self.val_cur_min:.1f}–{self.val_cur_max:.1f}{self.unit}"
        else:
            x1 = to_x(v_min)
            x2 = to_x(self.val_cur)
            if self.precision == 0:
                txt1 = f"{int(round(self.val_cur))}{self.unit}"
            else:
                txt1 = f"{self.val_cur:.1f}{self.unit}"
        draw_row(7, self.label_cur, txt1, True, x1, x2)

        if self.mode == "range":
            x1 = to_x(self.val_prev_min)
            x2 = to_x(self.val_prev_max)
            if self.precision == 0:
                txt2 = f"{int(round(self.val_prev_min))}–{int(round(self.val_prev_max))}{self.unit}"
            else:
                txt2 = f"{self.val_prev_min:.1f}–{self.val_prev_max:.1f}{self.unit}"
        else:
            x1 = to_x(v_min)
            x2 = to_x(self.val_prev)
            if self.precision == 0:
                txt2 = f"{int(round(self.val_prev))}{self.unit}"
            else:
                txt2 = f"{self.val_prev:.1f}{self.unit}"
        draw_row(35, self.label_prev, txt2, False, x1, x2)


ComparisonBarArea = DayComparisonBarArea
