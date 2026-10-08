"""
Карточка влажности: суточный сплайн влажности с зоной комфорта (40-60%), оценка точки росы и шкала комфорта.
"""

from __future__ import annotations

import math

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from detail_cards.base import BaseWeatherHourlyArea
from detail_cards.comparison_bar import DayComparisonBarArea
from i18n import get_current_language, t


class HumidityHourlyArea(BaseWeatherHourlyArea):
    """График относительной влажности с полосой комфорта (40-60%), точкой росы и скруббером."""

    def __init__(self):
        self.hums = [60] * 24
        self.dews = [10] * 24
        super().__init__(content_height=190)

    def _process_scrub(self, x: float, y: float):
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return

        pad_l = 28
        pad_r = 44
        pad_t = 30
        pad_b = 30
        plot_w = max(10, width - pad_l - pad_r)
        plot_h = max(10, height - pad_t - pad_b)

        frac_h = self._calc_frac_h(x, pad_l, plot_w)

        if not self.hums or len(self.hums) < 24:
            return

        def to_xy(idx, val):
            px = pad_l + (idx / 23.0) * plot_w
            py = pad_t + plot_h - (val / 100.0) * plot_h
            return px, py

        pts_hum = [to_xy(i, v) for i, v in enumerate(self.hums)]

        i = min(22, max(0, int(frac_h)))
        f = frac_h - i
        p0 = pts_hum[max(0, i - 1)]
        p1 = pts_hum[i]
        p2 = pts_hum[i + 1]
        p3 = pts_hum[min(len(pts_hum) - 1, i + 2)]

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
        hum_val = min(100, max(0, round(norm_y * 100.0)))
        dew_val = round(self.dews[i] * (1.0 - f) + self.dews[i + 1] * f)

        self.queue_draw()

        if callable(self.on_scrub):
            self.on_scrub({
                "active": True,
                "frac_h": frac_h,
                "hour": h_int,
                "minute": minute,
                "time_str": time_str,
                "humidity": hum_val,
                "dew_point": dew_val,
            })

    def update_data(self, hums: list, dews: list, cur_hour: int, is_today: bool):
        self.hums = hums if len(hums) >= 24 else ([60] * 24)
        self.dews = dews if len(dews) >= 24 else ([10] * 24)
        self.cur_hour = cur_hour
        self.is_today = is_today
        self.queue_draw()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        pad_l = 28
        pad_r = 44
        pad_t = 30
        pad_b = 30

        plot_w = max(10, width - pad_l - pad_r)
        plot_h = max(10, height - pad_t - pad_b)

        def to_xy(idx, val):
            x = pad_l + (idx / 23.0) * plot_w
            y = pad_t + plot_h - (val / 100.0) * plot_h
            return x, y

        pts_hum = [to_xy(i, v) for i, v in enumerate(self.hums)]

        # 1. Полоса комфорта 40% - 60%
        _, y_top_comf = to_xy(0, 60)
        _, y_bot_comf = to_xy(0, 40)
        cr.set_source_rgba(0.25, 0.85, 0.55, 0.08)
        cr.rectangle(pad_l, y_top_comf, plot_w, y_bot_comf - y_top_comf)
        cr.fill()

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9)
        cr.set_source_rgba(0.35, 0.85, 0.55, 0.65)
        cr.move_to(pad_l + 8, (y_top_comf + y_bot_comf) / 2.0 + 3.5)
        cr.show_text(t("weather_hum_comfort_zone"))

        # 2. Сетка (20%, 40%, 60%, 80%, 100%)
        cr.set_line_width(0.7)
        for pct in (20, 40, 60, 80, 100):
            _, y = to_xy(0, pct)
            cr.set_source_rgba(1, 1, 1, 0.08)
            cr.move_to(pad_l, y)
            cr.line_to(pad_l + plot_w, y)
            cr.stroke()

            cr.set_source_rgba(1, 1, 1, 0.40)
            cr.set_font_size(9)
            cr.move_to(pad_l + plot_w + 6, y + 3)
            cr.show_text(f"{pct}%")

        # 3. Заливка графика влажности
        cr.save()
        cr.move_to(pts_hum[0][0], pad_t + plot_h)
        cr.line_to(pts_hum[0][0], pts_hum[0][1])
        for i in range(len(pts_hum) - 1):
            p0 = pts_hum[max(0, i - 1)]
            p1 = pts_hum[i]
            p2 = pts_hum[i + 1]
            p3 = pts_hum[min(len(pts_hum) - 1, i + 2)]
            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
            cr.curve_to(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
        cr.line_to(pts_hum[-1][0], pad_t + plot_h)
        cr.close_path()

        pat = cairo.LinearGradient(0, pad_t, 0, pad_t + plot_h)
        pat.add_color_stop_rgba(0.0, 0.15, 0.70, 0.95, 0.35)
        pat.add_color_stop_rgba(1.0, 0.15, 0.70, 0.95, 0.03)
        cr.set_source(pat)
        cr.fill()
        cr.restore()

        # 4. Линия кривой
        cr.save()
        cr.move_to(pts_hum[0][0], pts_hum[0][1])
        for i in range(len(pts_hum) - 1):
            p0 = pts_hum[max(0, i - 1)]
            p1 = pts_hum[i]
            p2 = pts_hum[i + 1]
            p3 = pts_hum[min(len(pts_hum) - 1, i + 2)]
            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
            cr.curve_to(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
        cr.set_line_width(2.2)
        cr.set_source_rgba(0.30, 0.85, 1.0, 0.95)
        cr.stroke()
        cr.restore()

        # 5. Метки часов
        cr.set_source_rgba(1, 1, 1, 0.42)
        cr.set_font_size(9.5)
        for h in (0, 6, 12, 18, 23):
            hx, _ = to_xy(h, 0)
            txt = f"{h:02d}"
            ext = cr.text_extents(txt)
            cr.move_to(hx - ext.width / 2.0, height - 8)
            cr.show_text(txt)

        # 6. Текущий час
        if (not self.is_scrubbing) and self.is_today and 0 <= self.cur_hour < 24:
            cx, cy = pts_hum[self.cur_hour]
            cr.set_line_width(1.0)
            cr.set_dash([3.0, 3.0])
            cr.set_source_rgba(1, 1, 1, 0.35)
            cr.move_to(cx, pad_t)
            cr.line_to(cx, pad_t + plot_h)
            cr.stroke()
            cr.set_dash([])

            cr.arc(cx, cy, 4.0, 0, 2 * math.pi)
            cr.set_source_rgba(1, 1, 1, 1.0)
            cr.fill()

        # 7. Скруббер
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
            cr.set_source_rgba(0.30, 0.85, 1.0, 0.95)
            cr.stroke()
            cr.restore()


def build_humidity_view(sheet) -> Gtk.Box:
    """Конструирует контейнер карточки влажности и связывает его с листом деталей."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.set_valign(Gtk.Align.START)

    # 1. 24h Humidity Spline Card
    hum_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    hum_card.add_css_class("weather-glass-card")

    lbl_h_title = Gtk.Label(label=t("weather_hum_title_hdr"))
    lbl_h_title.add_css_class("weather-section-title")
    lbl_h_title.set_halign(Gtk.Align.START)
    hum_card.append(lbl_h_title)

    sheet.humidity_hourly_area = HumidityHourlyArea()
    sheet.humidity_hourly_area.on_scrub = sheet._on_humidity_scrub
    hum_card.append(sheet.humidity_hourly_area)

    div_h = Gtk.Box()
    div_h.add_css_class("weather-card-divider")
    hum_card.append(div_h)

    sum_h_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    sum_h_box.add_css_class("weather-chart-summary-box")

    sheet.lbl_hum_sum_time = Gtk.Label()
    sheet.lbl_hum_sum_time.add_css_class("weather-chart-summary-time")
    sheet.lbl_hum_sum_time.set_halign(Gtk.Align.START)
    sheet.lbl_hum_sum_time.set_xalign(0.0)
    sum_h_box.append(sheet.lbl_hum_sum_time)

    sheet.lbl_hum_sum_text = Gtk.Label()
    sheet.lbl_hum_sum_text.add_css_class("weather-chart-summary-text")
    sheet.lbl_hum_sum_text.set_wrap(True)
    sheet.lbl_hum_sum_text.set_halign(Gtk.Align.START)
    sheet.lbl_hum_sum_text.set_xalign(0.0)
    sum_h_box.append(sheet.lbl_hum_sum_text)

    hum_card.append(sum_h_box)
    box.append(hum_card)

    # 2. Dew Point & Sensation Card
    dew_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    dew_card.add_css_class("weather-glass-card")

    lbl_d_title = Gtk.Label(label=t("weather_hum_dew_sensation_hdr"))
    lbl_d_title.add_css_class("weather-section-title")
    lbl_d_title.set_halign(Gtk.Align.START)
    dew_card.append(lbl_d_title)

    div_d = Gtk.Box()
    div_d.add_css_class("weather-card-divider")
    dew_card.append(div_d)

    row_d1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_d1 = Gtk.Label(label=t("weather_dew_point_label"))
    lbl_d1.add_css_class("weather-body-text")
    row_d1.append(lbl_d1)
    sheet.lbl_hum_dew = Gtk.Label(label="--°C")
    sheet.lbl_hum_dew.add_css_class("weather-item-bold")
    sheet.lbl_hum_dew.set_hexpand(True)
    sheet.lbl_hum_dew.set_halign(Gtk.Align.END)
    row_d1.append(sheet.lbl_hum_dew)
    dew_card.append(row_d1)

    row_d2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_d2 = Gtk.Label(label=t("weather_hum_air_sensation"))
    lbl_d2.add_css_class("weather-body-text")
    row_d2.append(lbl_d2)
    sheet.lbl_hum_sensation = Gtk.Label(label=t("weather_hum_comfortable"))
    sheet.lbl_hum_sensation.add_css_class("weather-item-bold")
    sheet.lbl_hum_sensation.set_hexpand(True)
    sheet.lbl_hum_sensation.set_halign(Gtk.Align.END)
    row_d2.append(sheet.lbl_hum_sensation)
    dew_card.append(row_d2)

    sheet.lbl_hum_dew_desc = Gtk.Label()
    sheet.lbl_hum_dew_desc.add_css_class("weather-card-subtitle")
    sheet.lbl_hum_dew_desc.set_wrap(True)
    sheet.lbl_hum_dew_desc.set_halign(Gtk.Align.START)
    dew_card.append(sheet.lbl_hum_dew_desc)

    box.append(dew_card)

    # 3. Day Comparison Card
    sheet.hum_comp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    sheet.hum_comp_card.add_css_class("weather-glass-card")

    lbl_h_comp_title = Gtk.Label(label=t("weather_comp_days_hdr"))
    lbl_h_comp_title.add_css_class("weather-section-title")
    lbl_h_comp_title.set_halign(Gtk.Align.START)
    sheet.hum_comp_card.append(lbl_h_comp_title)

    div_h_comp = Gtk.Box()
    div_h_comp.add_css_class("weather-card-divider")
    sheet.hum_comp_card.append(div_h_comp)

    sheet.lbl_hum_comp_sub = Gtk.Label()
    sheet.lbl_hum_comp_sub.add_css_class("weather-card-subtitle")
    sheet.lbl_hum_comp_sub.set_wrap(True)
    sheet.lbl_hum_comp_sub.set_halign(Gtk.Align.START)
    sheet.hum_comp_card.append(sheet.lbl_hum_comp_sub)

    sheet.hum_comp_bar = DayComparisonBarArea()
    sheet.hum_comp_card.append(sheet.hum_comp_bar)

    box.append(sheet.hum_comp_card)

    # 4. Humidity Scale Reference Card
    scale_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    scale_card.add_css_class("weather-glass-card")
    lbl_sc_title = Gtk.Label(label=t("weather_hum_scale_hdr"))
    lbl_sc_title.add_css_class("weather-section-title")
    lbl_sc_title.set_halign(Gtk.Align.START)
    scale_card.append(lbl_sc_title)
    div_sc = Gtk.Box()
    div_sc.add_css_class("weather-card-divider")
    scale_card.append(div_sc)

    h_items = [
        ("< 30%", t("weather_hum_scale_dry"), t("weather_hum_scale_dry_desc")),
        ("30% – 60%", t("weather_hum_scale_opt"), t("weather_hum_scale_opt_desc")),
        ("60% – 80%", t("weather_hum_scale_elev"), t("weather_hum_scale_elev_desc")),
        ("> 80%", t("weather_hum_scale_high"), t("weather_hum_scale_high_desc")),
    ]
    for pct_r, h_name, h_desc in h_items:
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_r = Gtk.Label(label=pct_r)
        lbl_r.add_css_class("weather-item-bold")
        lbl_r.set_size_request(70, -1)
        lbl_r.set_xalign(0.0)
        r.append(lbl_r)

        lbl_d = Gtk.Label(label=f"{h_name} — {h_desc}")
        lbl_d.add_css_class("weather-body-text")
        lbl_d.set_wrap(True)
        lbl_d.set_hexpand(True)
        lbl_d.set_xalign(0.0)
        r.append(lbl_d)
        scale_card.append(r)

    box.append(scale_card)
    sheet.mode_stack.add_named(box, "humidity")
    return box
