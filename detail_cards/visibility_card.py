"""
Карточка видимости: суточный сплайн дальности видимости в км со скруббером, оценка прозрачности и метеорологическая шкала.
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


class VisibilityHourlyArea(BaseWeatherHourlyArea):
    """Почасовой график видимости в км со скруббером и сеткой расстояний."""

    def __init__(self):
        self.vis = [10.0] * 24
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

        if not self.vis or len(self.vis) < 24:
            return

        y_max = max(10.0, math.ceil(max(self.vis)))

        def to_xy(idx, val):
            px = pad_l + (idx / 23.0) * plot_w
            py = pad_t + plot_h - (val / float(y_max)) * plot_h
            return px, py

        pts = [to_xy(i, v) for i, v in enumerate(self.vis)]

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
        vis_val = max(0.0, norm_y * y_max)

        self.queue_draw()

        if callable(self.on_scrub):
            self.on_scrub({
                "active": True,
                "frac_h": frac_h,
                "hour": h_int,
                "minute": minute,
                "time_str": time_str,
                "visibility": vis_val,
            })

    def update_data(self, vis: list, cur_hour: int, is_today: bool):
        self.vis = [float(x) for x in vis[:24]] if len(vis) >= 24 else ([10.0] * 24)
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

        y_max = max(10.0, math.ceil(max(self.vis)))

        def to_xy(idx, val):
            x = pad_l + (idx / 23.0) * plot_w
            y = pad_t + plot_h - (val / float(y_max)) * plot_h
            return x, y

        pts = [to_xy(i, v) for i, v in enumerate(self.vis)]

        # 1. Сетка (2, 5, 10 км)
        cr.set_line_width(0.7)
        for v in [2, 5, 10]:
            if v <= y_max:
                _, y = to_xy(0, v)
                cr.set_source_rgba(1, 1, 1, 0.08)
                cr.move_to(pad_l, y)
                cr.line_to(pad_l + plot_w, y)
                cr.stroke()

                cr.set_source_rgba(1, 1, 1, 0.40)
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(9)
                cr.move_to(pad_l + plot_w + 6, y + 3)
                cr.show_text(f"{v} км")

        # 2. Заливка графика
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
        pat.add_color_stop_rgba(0.0, 0.20, 0.80, 0.70, 0.35)
        pat.add_color_stop_rgba(1.0, 0.20, 0.80, 0.70, 0.02)
        cr.set_source(pat)
        cr.fill()
        cr.restore()

        # 3. Линия кривой
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
        cr.set_line_width(2.2)
        cr.set_source_rgba(0.35, 0.90, 0.80, 0.95)
        cr.stroke()
        cr.restore()

        # 4. Метки часов
        cr.set_source_rgba(1, 1, 1, 0.42)
        cr.set_font_size(9.5)
        for h in (0, 6, 12, 18, 23):
            hx, _ = to_xy(h, 0)
            txt = f"{h:02d}"
            ext = cr.text_extents(txt)
            cr.move_to(hx - ext.width / 2.0, height - 8)
            cr.show_text(txt)

        # 5. Текущий час
        if (not self.is_scrubbing) and self.is_today and 0 <= self.cur_hour < 24:
            cx, cy = pts[self.cur_hour]
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

        # 6. Скруббер
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
            cr.set_source_rgba(0.35, 0.90, 0.80, 0.95)
            cr.stroke()
            cr.restore()


def build_visibility_view(sheet) -> Gtk.Box:
    """Конструирует контейнер карточки видимости и связывает его с листом деталей."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.set_valign(Gtk.Align.START)

    # 1. 24h Visibility Chart Card
    vis_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    vis_card.add_css_class("weather-glass-card")

    lbl_v_title = Gtk.Label(label=t("weather_vis_hourly_hdr"))
    lbl_v_title.add_css_class("weather-section-title")
    lbl_v_title.set_halign(Gtk.Align.START)
    vis_card.append(lbl_v_title)

    sheet.visibility_hourly_area = VisibilityHourlyArea()
    sheet.visibility_hourly_area.on_scrub = sheet._on_vis_scrub
    vis_card.append(sheet.visibility_hourly_area)

    div_vis = Gtk.Box()
    div_vis.add_css_class("weather-card-divider")
    vis_card.append(div_vis)

    sum_vis_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    sum_vis_box.add_css_class("weather-chart-summary-box")

    sheet.lbl_vis_sum_time = Gtk.Label()
    sheet.lbl_vis_sum_time.add_css_class("weather-chart-summary-time")
    sheet.lbl_vis_sum_time.set_halign(Gtk.Align.START)
    sheet.lbl_vis_sum_time.set_xalign(0.0)
    sum_vis_box.append(sheet.lbl_vis_sum_time)

    sheet.lbl_vis_sum_text = Gtk.Label()
    sheet.lbl_vis_sum_text.add_css_class("weather-chart-summary-text")
    sheet.lbl_vis_sum_text.set_wrap(True)
    sheet.lbl_vis_sum_text.set_halign(Gtk.Align.START)
    sheet.lbl_vis_sum_text.set_xalign(0.0)
    sum_vis_box.append(sheet.lbl_vis_sum_text)

    vis_card.append(sum_vis_box)
    box.append(vis_card)

    # 2. Visibility Status Card
    stat_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    stat_card.add_css_class("weather-glass-card")

    lbl_st_title = Gtk.Label(label=t("weather_vis_clarity_hdr"))
    lbl_st_title.add_css_class("weather-section-title")
    lbl_st_title.set_halign(Gtk.Align.START)
    stat_card.append(lbl_st_title)

    div_st = Gtk.Box()
    div_st.add_css_class("weather-card-divider")
    stat_card.append(div_st)

    row_st1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_st1 = Gtk.Label(label=t("weather_vis_current"))
    lbl_st1.add_css_class("weather-body-text")
    row_st1.append(lbl_st1)
    sheet.lbl_vis_km_val = Gtk.Label(label=f"-- {t('unit_km')}")
    sheet.lbl_vis_km_val.add_css_class("weather-item-bold")
    sheet.lbl_vis_km_val.set_hexpand(True)
    sheet.lbl_vis_km_val.set_halign(Gtk.Align.END)
    row_st1.append(sheet.lbl_vis_km_val)
    stat_card.append(row_st1)

    row_st2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_st2 = Gtk.Label(label=t("weather_vis_assessment"))
    lbl_st2.add_css_class("weather-body-text")
    row_st2.append(lbl_st2)
    sheet.lbl_vis_quality = Gtk.Label(label=t("weather_vis_excellent"))
    sheet.lbl_vis_quality.add_css_class("weather-item-bold")
    sheet.lbl_vis_quality.set_hexpand(True)
    sheet.lbl_vis_quality.set_halign(Gtk.Align.END)
    row_st2.append(sheet.lbl_vis_quality)
    stat_card.append(row_st2)

    sheet.lbl_vis_desc = Gtk.Label()
    sheet.lbl_vis_desc.add_css_class("weather-card-subtitle")
    sheet.lbl_vis_desc.set_wrap(True)
    sheet.lbl_vis_desc.set_halign(Gtk.Align.START)
    stat_card.append(sheet.lbl_vis_desc)

    box.append(stat_card)

    # 3. Day Comparison Card
    sheet.vis_comp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    sheet.vis_comp_card.add_css_class("weather-glass-card")

    lbl_v_comp_title = Gtk.Label(label=t("weather_comp_days_hdr"))
    lbl_v_comp_title.add_css_class("weather-section-title")
    lbl_v_comp_title.set_halign(Gtk.Align.START)
    sheet.vis_comp_card.append(lbl_v_comp_title)

    div_v_comp = Gtk.Box()
    div_v_comp.add_css_class("weather-card-divider")
    sheet.vis_comp_card.append(div_v_comp)

    sheet.lbl_vis_comp_sub = Gtk.Label()
    sheet.lbl_vis_comp_sub.add_css_class("weather-card-subtitle")
    sheet.lbl_vis_comp_sub.set_wrap(True)
    sheet.lbl_vis_comp_sub.set_halign(Gtk.Align.START)
    sheet.vis_comp_card.append(sheet.lbl_vis_comp_sub)

    sheet.vis_comp_bar = DayComparisonBarArea()
    sheet.vis_comp_card.append(sheet.vis_comp_bar)

    box.append(sheet.vis_comp_card)

    # 4. Meteorological Visibility Scale Card
    v_scale_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    v_scale_card.add_css_class("weather-glass-card")
    lbl_vs_title = Gtk.Label(label=t("weather_vis_scale_hdr"))
    lbl_vs_title.add_css_class("weather-section-title")
    lbl_vs_title.set_halign(Gtk.Align.START)
    v_scale_card.append(lbl_vs_title)
    div_vs = Gtk.Box()
    div_vs.add_css_class("weather-card-divider")
    v_scale_card.append(div_vs)

    km_u = t("unit_km")
    v_items = [
        (f"< 1 {km_u}", t("weather_vis_scale_fog"), t("weather_vis_scale_fog_desc")),
        (f"1 – 4 {km_u}", t("weather_vis_scale_mist"), t("weather_vis_scale_mist_desc")),
        (f"4 – 10 {km_u}", t("weather_vis_scale_mod"), t("weather_vis_scale_mod_desc")),
        (f"> 10 {km_u}", t("weather_vis_scale_exc"), t("weather_vis_scale_exc_desc")),
    ]
    for d_range, v_name, v_desc in v_items:
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_r = Gtk.Label(label=d_range)
        lbl_r.add_css_class("weather-item-bold")
        lbl_r.set_size_request(66, -1)
        lbl_r.set_xalign(0.0)
        r.append(lbl_r)

        lbl_d = Gtk.Label(label=f"{v_name} — {v_desc}")
        lbl_d.add_css_class("weather-body-text")
        lbl_d.set_wrap(True)
        lbl_d.set_hexpand(True)
        lbl_d.set_xalign(0.0)
        r.append(lbl_d)
        v_scale_card.append(r)

    box.append(v_scale_card)
    sheet.mode_stack.add_named(box, "visibility")
    return box
