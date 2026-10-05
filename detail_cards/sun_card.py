"""
Карточка солнца: 24-часовая дуга траектории с динамическим освещением и годовая таблица светового дня.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from i18n import get_current_language, t

logger = logging.getLogger(__name__)


class SunDaylightBar(Gtk.DrawingArea):
    """Горизонтальная полоска светового дня на 24 часа."""

    def __init__(self, sr_frac: float = 6.0, ss_frac: float = 18.0, is_active: bool = False):
        super().__init__()
        self.sr_frac = sr_frac
        self.ss_frac = ss_frac
        self.is_active = is_active
        self.set_content_width(115)
        self.set_content_height(16)
        self.set_draw_func(self._draw, None)

    def _draw(self, da, cr, w, h, user_data):
        cr.save()
        bar_h = 5.5
        y = (h - bar_h) / 2.0
        r = bar_h / 2.0

        cr.new_sub_path()
        cr.arc(w - r, y + r, r, -math.pi / 2, math.pi / 2)
        cr.arc(r, y + r, r, math.pi / 2, 3 * math.pi / 2)
        cr.close_path()
        cr.set_source_rgba(1, 1, 1, 0.08 if not self.is_active else 0.13)
        cr.fill()

        x_start = max(0.0, min(w, (self.sr_frac / 24.0) * w))
        x_end = max(x_start + 4.0, min(w, (self.ss_frac / 24.0) * w))
        seg_w = x_end - x_start

        if seg_w > 0:
            cr.new_sub_path()
            cr.arc(x_end - r, y + r, r, -math.pi / 2, math.pi / 2)
            cr.arc(x_start + r, y + r, r, math.pi / 2, 3 * math.pi / 2)
            cr.close_path()

            pat = cairo.LinearGradient(x_start, 0, x_end, 0)
            pat.add_color_stop_rgba(0.0, 0.22, 0.70, 0.98, 1.0)
            pat.add_color_stop_rgba(1.0, 0.30, 0.80, 1.0, 1.0)
            cr.set_source(pat)
            cr.fill()

        cr.restore()


class ClimateSunYearTable(Gtk.Box):
    """12-месячная таблица с восходами, закатами и полосками дня для Jan-Dec."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("climate-sun-monthly-table")

    def update_data(self, annual_table_data: dict, current_m_idx: int = -1):
        while child := self.get_first_child():
            self.remove(child)

        if not annual_table_data:
            return

        months = annual_table_data.get("months", [])
        num_m = len(months)
        for idx, m in enumerate(months):
            is_active = (idx == current_m_idx)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class("climate-sun-month-row")
            if is_active:
                row.add_css_class("climate-sun-month-row-active")

            lbl_name = Gtk.Label(label=m.get("name", ""))
            lbl_name.add_css_class("climate-sun-month-name")
            if is_active:
                lbl_name.add_css_class("climate-sun-month-name-active")
            lbl_name.set_size_request(52, -1)
            lbl_name.set_xalign(0.0)
            row.append(lbl_name)

            lbl_sr = Gtk.Label(label=m.get("sunrise_str", ""))
            lbl_sr.add_css_class("climate-sun-time")
            if is_active:
                lbl_sr.add_css_class("climate-sun-time-active")
            lbl_sr.set_size_request(46, -1)
            lbl_sr.set_xalign(1.0)
            row.append(lbl_sr)

            bar = SunDaylightBar(
                sr_frac=m.get("sunrise_frac", 6.0),
                ss_frac=m.get("sunset_frac", 18.0),
                is_active=is_active
            )
            bar.set_hexpand(True)
            row.append(bar)

            lbl_ss = Gtk.Label(label=m.get("sunset_str", ""))
            lbl_ss.add_css_class("climate-sun-time")
            if is_active:
                lbl_ss.add_css_class("climate-sun-time-active")
            lbl_ss.set_size_request(46, -1)
            lbl_ss.set_xalign(0.0)
            row.append(lbl_ss)

            self.append(row)

            if idx < num_m - 1:
                div = Gtk.Box()
                div.add_css_class("climate-sun-row-divider")
                self.append(div)


class SunArcChartArea(Gtk.DrawingArea):
    """Интерактивная 24-часовая траектория солнца с динамическим освещением неба."""

    def __init__(self, on_scrub_callback=None):
        super().__init__()
        self.on_scrub_callback = on_scrub_callback
        self.solar_data = None
        self.current_time_frac = 12.0
        self.scrub_time_frac = None
        self.is_dragging = False

        self.set_content_width(320)
        self.set_content_height(210)
        self.set_hexpand(True)
        self.set_draw_func(self._draw, None)

        self.drag = Gtk.GestureDrag.new()
        self.drag.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.drag.connect("drag-begin", self._on_drag_begin)
        self.drag.connect("drag-update", self._on_drag_update)
        self.drag.connect("drag-end", self._on_drag_end)
        self.drag.connect("cancel", self._on_drag_end)
        self.add_controller(self.drag)
        try:
            self.set_cursor_from_name("pointer")
        except (GLib.Error, TypeError) as e:
            logger.debug("Could not set pointer cursor: %s", e)

    def set_solar_data(self, solar_data: dict, cur_hour_frac: float):
        self.solar_data = solar_data
        self.current_time_frac = cur_hour_frac
        self.queue_draw()

    def _get_elevation_at(self, t_frac: float) -> float:
        if not self.solar_data or "curve_points" not in self.solar_data:
            return 0.0
        pts = self.solar_data["curve_points"]
        if not pts:
            return 0.0
        step = 0.25
        idx = int(t_frac / step)
        if idx < 0:
            return pts[0][1]
        if idx >= len(pts) - 1:
            return pts[-1][1]
        p1 = pts[idx]
        p2 = pts[idx + 1]
        sub = (t_frac - p1[0]) / step
        return p1[1] + (p2[1] - p1[1]) * sub

    def _on_drag_begin(self, gesture, start_x, start_y):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.is_dragging = True
        self._start_x = start_x
        self._update_drag_position(start_x)

    def _on_drag_update(self, gesture, offset_x, offset_y):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        ok, start_x, _ = gesture.get_start_point()
        if not ok:
            start_x = getattr(self, "_start_x", 0.0)
        self._update_drag_position(start_x + offset_x)

    def _on_drag_end(self, gesture, offset_x, offset_y):
        self.is_dragging = False
        self.scrub_time_frac = None
        self.queue_draw()
        if self.on_scrub_callback:
            self.on_scrub_callback(self.current_time_frac, None, None, False)

    def _update_drag_position(self, curr_x: float):
        w = self.get_width()
        pad_l = 22.0
        pad_r = 22.0
        w_plot = max(10.0, w - pad_l - pad_r)
        clamped_x = max(pad_l, min(w - pad_r, curr_x))
        t_frac = ((clamped_x - pad_l) / w_plot) * 24.0
        t_frac = max(0.0, min(24.0, t_frac))
        self.scrub_time_frac = t_frac

        h = int(t_frac) % 24
        m = int(round((t_frac % 1.0) * 60))
        if m == 60:
            m = 0
            h = (h + 1) % 24
        time_str = f"{h:02d}:{m:02d}"

        elev = self._get_elevation_at(t_frac)
        self.queue_draw()

        if self.on_scrub_callback:
            self.on_scrub_callback(t_frac, time_str, elev, True)

    def _draw(self, da, cr, w, h, user_data):
        cr.save()
        pad_l = 22.0
        pad_r = 22.0
        pad_t = 16.0
        pad_b = 32.0
        w_plot = max(10.0, w - pad_l - pad_r)
        h_plot = max(10.0, h - pad_t - pad_b)
        y_horiz = pad_t + h_plot * 0.52

        t_active = self.scrub_time_frac if (self.is_dragging and self.scrub_time_frac is not None) else self.current_time_frac
        t_active = max(0.0, min(24.0, t_active))
        elev_active = self._get_elevation_at(t_active)

        x_sun = pad_l + (t_active / 24.0) * w_plot
        y_sun = y_horiz - (elev_active / 60.0) * (h_plot * 0.44)

        cr.save()
        cr.rectangle(0, 0, w, y_horiz)
        cr.clip()

        sky_grad = cairo.LinearGradient(0, 0, 0, y_horiz)
        if elev_active <= -10.0:
            sky_grad.add_color_stop_rgba(0.0, 0.04, 0.06, 0.10, 0.95)
            sky_grad.add_color_stop_rgba(1.0, 0.08, 0.11, 0.18, 0.90)
            cr.set_source(sky_grad)
            cr.paint()
            cr.set_source_rgba(1, 1, 1, 0.35)
            star_coords = [(pad_l + 32, pad_t + 14), (pad_l + 85, pad_t + 28), (w - pad_r - 45, pad_t + 18), (w - pad_r - 110, pad_t + 10)]
            for sx, sy in star_coords:
                cr.arc(sx, sy, 1.0, 0, 2 * math.pi)
                cr.fill()
        elif elev_active < 2.0:
            factor = (elev_active - (-10.0)) / 12.0
            sky_grad.add_color_stop_rgba(0.0, 0.06, 0.09, 0.16, 0.95)
            sky_grad.add_color_stop_rgba(0.55, 0.18 + 0.15 * factor, 0.10 + 0.08 * factor, 0.22, 0.90)
            sky_grad.add_color_stop_rgba(1.0, 0.95 * factor, 0.45 * factor, 0.15 * factor, 0.85)
            cr.set_source(sky_grad)
            cr.paint()

            glow_pat = cairo.RadialGradient(x_sun, y_horiz, 2.0, x_sun, y_horiz, 95.0)
            glow_pat.add_color_stop_rgba(0.0, 1.0, 0.70, 0.25, 0.65 * factor)
            glow_pat.add_color_stop_rgba(0.5, 0.95, 0.40, 0.15, 0.35 * factor)
            glow_pat.add_color_stop_rgba(1.0, 0.90, 0.30, 0.10, 0.0)
            cr.set_source(glow_pat)
            cr.paint()
        else:
            day_factor = min(1.0, (elev_active - 2.0) / 30.0)
            sky_grad.add_color_stop_rgba(0.0, 0.08 + 0.06 * day_factor, 0.18 + 0.15 * day_factor, 0.38 + 0.25 * day_factor, 0.95)
            sky_grad.add_color_stop_rgba(1.0, 0.20 + 0.15 * day_factor, 0.38 + 0.28 * day_factor, 0.65 + 0.30 * day_factor, 0.90)
            cr.set_source(sky_grad)
            cr.paint()

            sun_corona = cairo.RadialGradient(x_sun, y_sun, 4.0, x_sun, y_sun, 75.0)
            sun_corona.add_color_stop_rgba(0.0, 1.0, 0.98, 0.85, 0.55 * day_factor)
            sun_corona.add_color_stop_rgba(0.35, 0.70, 0.88, 1.0, 0.25 * day_factor)
            sun_corona.add_color_stop_rgba(1.0, 0.50, 0.75, 1.0, 0.0)
            cr.set_source(sun_corona)
            cr.paint()

        cr.restore()

        cr.save()
        cr.rectangle(0, y_horiz, w, h - y_horiz)
        cr.clip()
        under_grad = cairo.LinearGradient(0, y_horiz, 0, h)
        under_grad.add_color_stop_rgba(0.0, 0.05, 0.07, 0.12, 0.85)
        under_grad.add_color_stop_rgba(1.0, 0.03, 0.04, 0.08, 0.98)
        cr.set_source(under_grad)
        cr.paint()
        cr.restore()

        cr.set_source_rgba(1, 1, 1, 0.30)
        cr.set_line_width(1.2)
        cr.move_to(pad_l - 6, y_horiz)
        cr.line_to(w - pad_r + 6, y_horiz)
        cr.stroke()

        cr.set_source_rgba(1, 1, 1, 0.10)
        cr.set_line_width(1.0)
        cr.set_dash([3.0, 4.0])
        for deg in [20, 40, -20, -40]:
            y_g = y_horiz - (deg / 60.0) * (h_plot * 0.44)
            if pad_t <= y_g <= h - pad_b:
                cr.move_to(pad_l, y_g)
                cr.line_to(w - pad_r, y_g)
                cr.stroke()
        cr.set_dash([])

        hour_ticks = [(0, "00"), (6, "06"), (12, "12"), (18, "18"), (24, "")]
        cr.set_dash([3.0, 4.0])
        for hr, lbl in hour_ticks:
            x_tick = pad_l + (hr / 24.0) * w_plot
            cr.set_source_rgba(1, 1, 1, 0.15)
            cr.move_to(x_tick, pad_t)
            cr.line_to(x_tick, h - pad_b + 4)
            cr.stroke()

            if lbl:
                cr.set_source_rgba(1, 1, 1, 0.70)
                cr.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                cr.set_font_size(11.5)
                ext = cr.text_extents(lbl)
                cr.move_to(x_tick - ext.width / 2.0, h - pad_b + 18.0)
                cr.show_text(lbl)
        cr.set_dash([])

        if self.solar_data and "curve_points" in self.solar_data:
            pts = self.solar_data["curve_points"]

            cr.save()
            cr.rectangle(0, y_horiz, w, h - y_horiz)
            cr.clip()
            for idx, (t_val, elev) in enumerate(pts):
                cx = pad_l + (t_val / 24.0) * w_plot
                cy = y_horiz - (elev / 60.0) * (h_plot * 0.44)
                if idx == 0:
                    cr.move_to(cx, cy)
                else:
                    cr.line_to(cx, cy)
            cr.set_source_rgba(0.65, 0.72, 0.85, 0.35)
            cr.set_line_width(1.8)
            cr.stroke()
            cr.restore()

            cr.save()
            cr.rectangle(0, 0, w, y_horiz)
            cr.clip()
            for idx, (t_val, elev) in enumerate(pts):
                cx = pad_l + (t_val / 24.0) * w_plot
                cy = y_horiz - (elev / 60.0) * (h_plot * 0.44)
                if idx == 0:
                    cr.move_to(cx, cy)
                else:
                    cr.line_to(cx, cy)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.22)
            cr.set_line_width(6.0)
            cr.stroke()

            for idx, (t_val, elev) in enumerate(pts):
                cx = pad_l + (t_val / 24.0) * w_plot
                cy = y_horiz - (elev / 60.0) * (h_plot * 0.44)
                if idx == 0:
                    cr.move_to(cx, cy)
                else:
                    cr.line_to(cx, cy)
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
            cr.set_line_width(2.6)
            cr.stroke()
            cr.restore()

            t_sr = self.solar_data.get("t_sunrise_frac", 6.67)
            t_ss = self.solar_data.get("t_sunset_frac", 19.58)
            key_events = [
                (self.solar_data.get("t_dawn_frac", 6.07), 2.2, 0.60),
                (t_sr, 3.2, 0.90),
                (t_ss, 3.2, 0.90),
                (self.solar_data.get("t_dusk_frac", 20.17), 2.2, 0.60),
                (t_sr - 1.0, 1.8, 0.40),
                (t_sr + 1.0, 1.8, 0.50),
                (t_ss - 1.0, 1.8, 0.50),
                (t_ss + 1.0, 1.8, 0.40),
            ]
            for t_evt, dot_r, dot_a in key_events:
                if 0.0 <= t_evt <= 24.0:
                    ex = pad_l + (t_evt / 24.0) * w_plot
                    e_val = self._get_elevation_at(t_evt)
                    ey = y_horiz - (e_val / 60.0) * (h_plot * 0.44)
                    cr.arc(ex, ey, dot_r, 0, 2 * math.pi)
                    cr.set_source_rgba(1.0, 1.0, 1.0, dot_a)
                    cr.fill()

        cr.save()
        if self.is_dragging:
            cr.set_dash([2.5, 3.5])
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.40)
            cr.set_line_width(1.0)
            cr.move_to(x_sun, pad_t)
            cr.line_to(x_sun, h - pad_b)
            cr.stroke()
            cr.set_dash([])

        cr.arc(x_sun, y_sun, 10.5, 0, 2 * math.pi)
        cr.set_line_width(1.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.25)
        cr.stroke()

        cr.arc(x_sun, y_sun, 7.0, 0, 2 * math.pi)
        cr.set_line_width(2.0)
        cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
        cr.stroke()
        cr.restore()

        cr.restore()


def create_sun_metric_row(title: str, value: str):
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.add_css_class("weather-sun-metric-row")

    lbl_title = Gtk.Label(label=title)
    lbl_title.add_css_class("weather-sun-metric-label")
    lbl_title.set_hexpand(True)
    lbl_title.set_xalign(0.0)
    row.append(lbl_title)

    lbl_val = Gtk.Label(label=value)
    lbl_val.add_css_class("weather-sun-metric-val")
    lbl_val.set_xalign(1.0)
    row.append(lbl_val)

    return row, lbl_val


def build_sun_view(sheet):
    """Построение карточки солнца и подключение к WeatherDetailSheet."""
    sheet.sun_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    sheet.sun_box.set_valign(Gtk.Align.START)

    # 1. Интерактивный график дуги солнца
    chart_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    chart_card.add_css_class("weather-glass-card")
    chart_card.set_overflow(Gtk.Overflow.HIDDEN)

    sheet.sun_arc_chart = SunArcChartArea(on_scrub_callback=sheet._on_sun_scrub)
    chart_card.append(sheet.sun_arc_chart)
    sheet.sun_box.append(chart_card)

    # 2. Метрики (первые лучи, восход, закат, последние лучи, световой день)
    metrics_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    metrics_card.add_css_class("weather-glass-card")
    metrics_card.set_margin_top(4)

    placeholder_time = "\u2014:\u2014"
    placeholder_val = "\u2014"

    sheet.row_first_light, sheet.lbl_first_light_val = create_sun_metric_row(
        t("weather_first_light"), placeholder_time
    )
    metrics_card.append(sheet.row_first_light)
    div1 = Gtk.Box()
    div1.add_css_class("weather-card-divider")
    metrics_card.append(div1)

    sheet.row_sunrise, sheet.lbl_sunrise_val = create_sun_metric_row(
        t("weather_sunrise_today"), placeholder_time
    )
    metrics_card.append(sheet.row_sunrise)
    div2 = Gtk.Box()
    div2.add_css_class("weather-card-divider")
    metrics_card.append(div2)

    sheet.row_sunset, sheet.lbl_sunset_val = create_sun_metric_row(
        t("weather_sunset_today"), placeholder_time
    )
    metrics_card.append(sheet.row_sunset)
    div3 = Gtk.Box()
    div3.add_css_class("weather-card-divider")
    metrics_card.append(div3)

    sheet.row_last_light, sheet.lbl_last_light_val = create_sun_metric_row(
        t("weather_last_light"), placeholder_time
    )
    metrics_card.append(sheet.row_last_light)
    div4 = Gtk.Box()
    div4.add_css_class("weather-card-divider")
    metrics_card.append(div4)

    sheet.row_daylight, sheet.lbl_daylight_val = create_sun_metric_row(
        t("weather_daylight_duration"), placeholder_val
    )
    metrics_card.append(sheet.row_daylight)

    sheet.sun_box.append(metrics_card)

    # 3. Годовой блок
    ann_section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
    ann_section_box.set_margin_top(12)

    lbl_ann_title = Gtk.Label(label=t("weather_sun_averages"))
    lbl_ann_title.add_css_class("weather-sun-section-title")
    lbl_ann_title.set_xalign(0.0)
    ann_section_box.append(lbl_ann_title)

    sheet.lbl_ann_longest_day = Gtk.Label(label="")
    sheet.lbl_ann_longest_day.add_css_class("weather-sun-section-sub")
    sheet.lbl_ann_longest_day.set_xalign(0.0)
    ann_section_box.append(sheet.lbl_ann_longest_day)

    sheet.sun_box.append(ann_section_box)

    # 4. Таблица на 12 месяцев
    year_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    year_card.add_css_class("weather-glass-card")
    year_card.set_margin_bottom(16)

    sheet.climate_sun_table = ClimateSunYearTable()
    year_card.append(sheet.climate_sun_table)
    sheet.sun_box.append(year_card)

    sheet.mode_stack.add_named(sheet.sun_box, "sun")
