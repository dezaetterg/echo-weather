"""
Карточка ветра: компас направления с круглой стрелкой, почасовой график скорости и порывов, шкала Бофорта.
"""

from __future__ import annotations

import math

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from detail_cards.base import BaseWeatherHourlyArea
from detail_cards.comparison_bar import DayComparisonBarArea
from i18n import get_current_language


class WindCompassArea(Gtk.DrawingArea):
    """Круговой компас с указателем направления ветра и текущей скоростью."""

    def __init__(self):
        super().__init__()
        self.set_content_height(205)
        self.set_hexpand(True)
        self.wind_speed = 12
        self.wind_gust = 22
        self.wind_dir = 270
        self.set_draw_func(self._on_draw)

    def update_data(self, wind_speed: int, wind_gust: int, wind_dir: int):
        self.wind_speed = wind_speed
        self.wind_gust = wind_gust
        self.wind_dir = wind_dir
        self.queue_draw()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        cx = width / 2.0
        cy = 76.0
        radius = min(cx - 24, 52.0)

        # 1. Внешнее кольцо
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.set_source_rgba(1, 1, 1, 0.09)
        cr.set_line_width(1.5)
        cr.stroke()

        # 2. Градусные засечки
        for deg in range(0, 360, 30):
            rad = math.radians(deg - 90)
            is_cardinal = (deg % 90 == 0)
            t_len = 5 if is_cardinal else 3
            x1 = cx + (radius - t_len) * math.cos(rad)
            y1 = cy + (radius - t_len) * math.sin(rad)
            x2 = cx + radius * math.cos(rad)
            y2 = cy + radius * math.sin(rad)

            cr.set_line_width(1.2 if is_cardinal else 0.7)
            cr.set_source_rgba(1, 1, 1, 0.40 if is_cardinal else 0.15)
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()

        # 3. Метки сторон света (С, В, Ю, З / N, E, S, W)
        is_ru = (get_current_language() == "ru")
        cardinals = [
            (0, "С" if is_ru else "N", (0.98, 0.35, 0.35, 0.95)),
            (90, "В" if is_ru else "E", (1, 1, 1, 0.65)),
            (180, "Ю" if is_ru else "S", (1, 1, 1, 0.65)),
            (270, "З" if is_ru else "W", (1, 1, 1, 0.65)),
        ]
        cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(10.5)
        for deg, lbl, col in cardinals:
            rad = math.radians(deg - 90)
            tx = cx + (radius + 13) * math.cos(rad)
            ty = cy + (radius + 13) * math.sin(rad)
            ext = cr.text_extents(lbl)
            cr.set_source_rgba(*col)
            cr.move_to(tx - ext.width / 2.0, ty + ext.height / 2.0)
            cr.show_text(lbl)

        # 4. Стрелка направления ветра
        needle_rad = math.radians(self.wind_dir - 90)
        nx = cx + (radius - 9) * math.cos(needle_rad)
        ny = cy + (radius - 9) * math.sin(needle_rad)
        bx = cx - 12 * math.cos(needle_rad)
        by = cy - 12 * math.sin(needle_rad)
        px1 = cx + 7 * math.cos(needle_rad + math.pi / 2)
        py1 = cy + 7 * math.sin(needle_rad + math.pi / 2)
        px2 = cx + 7 * math.cos(needle_rad - math.pi / 2)
        py2 = cy + 7 * math.sin(needle_rad - math.pi / 2)

        cr.save()
        cr.move_to(nx, ny)
        cr.line_to(px1, py1)
        cr.line_to(bx, by)
        cr.line_to(px2, py2)
        cr.close_path()
        pat = cairo.LinearGradient(bx, by, nx, ny)
        pat.add_color_stop_rgba(0.0, 0.20, 0.50, 0.90, 0.30)
        pat.add_color_stop_rgba(1.0, 0.35, 0.75, 1.0, 0.95)
        cr.set_source(pat)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.45)
        cr.set_line_width(1.0)
        cr.stroke()
        cr.restore()

        # Центральная точка
        cr.arc(cx, cy, 5.5, 0, 2 * math.pi)
        cr.set_source_rgba(0.15, 0.18, 0.26, 1.0)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.65)
        cr.set_line_width(1.2)
        cr.stroke()

        # 5. Значение скорости под компасом
        val_str = f"{self.wind_speed}"
        unit_str = " км/ч" if is_ru else " km/h"

        cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(21)
        ext_val = cr.text_extents(val_str)

        cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(12.5)
        ext_unit = cr.text_extents(unit_str)

        total_w = ext_val.width + ext_unit.width
        start_x = cx - total_w / 2.0
        base_y = height - 12

        cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(21)
        cr.set_source_rgba(1, 1, 1, 0.98)
        cr.move_to(start_x, base_y)
        cr.show_text(val_str)

        cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(12.5)
        cr.set_source_rgba(1, 1, 1, 0.65)
        cr.move_to(start_x + ext_val.width, base_y)
        cr.show_text(unit_str)


class WindHourlyArea(BaseWeatherHourlyArea):
    """Почасовой график ветра и порывов со стрелками направлений и скруббером."""

    def __init__(self):
        self.speeds = [10] * 24
        self.gusts = [18] * 24
        self.dirs = [270] * 24
        super().__init__(content_height=190)

    def _process_scrub(self, x: float, y: float):
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return

        pad_l = 28
        pad_r = 44
        pad_t = 30
        pad_b = 38
        plot_w = max(10, width - pad_l - pad_r)
        plot_h = max(10, height - pad_t - pad_b)

        frac_h = self._calc_frac_h(x, pad_l, plot_w)

        if not self.speeds or len(self.speeds) < 24:
            return

        max_v = max(self.gusts + self.speeds)
        y_max = max(20, math.ceil((max_v + 5) / 10.0) * 10)

        def to_xy(idx, val):
            px = pad_l + (idx / 23.0) * plot_w
            py = pad_t + plot_h - (val / float(y_max)) * plot_h
            return px, py

        pts_spd = [to_xy(i, v) for i, v in enumerate(self.speeds)]

        i = min(22, max(0, int(frac_h)))
        f = frac_h - i
        p0 = pts_spd[max(0, i - 1)]
        p1 = pts_spd[i]
        p2 = pts_spd[i + 1]
        p3 = pts_spd[min(len(pts_spd) - 1, i + 2)]

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
        spd_val = max(0, round(norm_y * y_max))
        gust_val = max(0, round(self.gusts[i] * (1.0 - f) + self.gusts[i + 1] * f))
        dir_val = self.dirs[min(23, max(0, round(frac_h)))]

        self.queue_draw()

        if callable(self.on_scrub):
            self.on_scrub({
                "active": True,
                "frac_h": frac_h,
                "hour": h_int,
                "minute": minute,
                "time_str": time_str,
                "speed": spd_val,
                "gust": gust_val,
                "direction": dir_val,
            })

    def update_data(self, speeds: list, gusts: list, dirs: list, cur_hour: int, is_today: bool):
        self.speeds = speeds if len(speeds) >= 24 else ([10] * 24)
        self.gusts = gusts if len(gusts) >= 24 else ([18] * 24)
        self.dirs = dirs if len(dirs) >= 24 else ([270] * 24)
        self.cur_hour = cur_hour
        self.is_today = is_today
        self.queue_draw()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        pad_l = 28
        pad_r = 44
        pad_t = 30
        pad_b = 38

        plot_w = max(10, width - pad_l - pad_r)
        plot_h = max(10, height - pad_t - pad_b)

        max_v = max(self.gusts + self.speeds)
        y_max = max(20, math.ceil((max_v + 5) / 10.0) * 10)

        def to_xy(idx, val):
            x = pad_l + (idx / 23.0) * plot_w
            y = pad_t + plot_h - (val / float(y_max)) * plot_h
            return x, y

        pts_spd = [to_xy(i, v) for i, v in enumerate(self.speeds)]
        pts_gust = [to_xy(i, v) for i, v in enumerate(self.gusts)]

        # 1. Сетка
        cr.set_line_width(0.7)
        for v in range(0, int(y_max) + 1, 10):
            _, y = to_xy(0, v)
            cr.set_source_rgba(1, 1, 1, 0.08)
            cr.move_to(pad_l, y)
            cr.line_to(pad_l + plot_w, y)
            cr.stroke()

            cr.set_source_rgba(1, 1, 1, 0.42)
            cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(9)
            cr.move_to(pad_l + plot_w + 6, y + 3)
            cr.show_text(f"{v}")

        # 2. Заливка графика скорости
        cr.save()
        cr.move_to(pts_spd[0][0], pad_t + plot_h)
        cr.line_to(pts_spd[0][0], pts_spd[0][1])
        for i in range(len(pts_spd) - 1):
            p0 = pts_spd[max(0, i - 1)]
            p1 = pts_spd[i]
            p2 = pts_spd[i + 1]
            p3 = pts_spd[min(len(pts_spd) - 1, i + 2)]
            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
            cr.curve_to(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
        cr.line_to(pts_spd[-1][0], pad_t + plot_h)
        cr.close_path()

        pat = cairo.LinearGradient(0, pad_t, 0, pad_t + plot_h)
        pat.add_color_stop_rgba(0.0, 0.20, 0.70, 0.95, 0.35)
        pat.add_color_stop_rgba(1.0, 0.20, 0.70, 0.95, 0.02)
        cr.set_source(pat)
        cr.fill()
        cr.restore()

        # 3. Линия скорости
        cr.save()
        cr.move_to(pts_spd[0][0], pts_spd[0][1])
        for i in range(len(pts_spd) - 1):
            p0 = pts_spd[max(0, i - 1)]
            p1 = pts_spd[i]
            p2 = pts_spd[i + 1]
            p3 = pts_spd[min(len(pts_spd) - 1, i + 2)]
            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
            cr.curve_to(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
        cr.set_line_width(2.2)
        cr.set_source_rgba(0.35, 0.80, 1.0, 0.95)
        cr.stroke()
        cr.restore()

        # 4. Пунктирная линия порывов
        cr.save()
        cr.move_to(pts_gust[0][0], pts_gust[0][1])
        for i in range(len(pts_gust) - 1):
            p0 = pts_gust[max(0, i - 1)]
            p1 = pts_gust[i]
            p2 = pts_gust[i + 1]
            p3 = pts_gust[min(len(pts_gust) - 1, i + 2)]
            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
            cr.curve_to(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
        cr.set_dash([2.5, 3.0])
        cr.set_line_width(1.8)
        cr.set_source_rgba(1.0, 0.65, 0.25, 0.85)
        cr.stroke()
        cr.restore()

        # 5. Стрелки направления каждые 3 часа
        for h in range(0, 24, 3):
            ax, _ = to_xy(h, 0)
            ay = height - 16
            deg = self.dirs[h]
            rad = math.radians(deg - 90)

            cr.save()
            cr.translate(ax, ay)
            cr.rotate(rad)
            cr.set_line_width(1.2)
            cr.set_source_rgba(1, 1, 1, 0.65)
            cr.move_to(0, 4)
            cr.line_to(0, -4)
            cr.line_to(-2.5, -1.5)
            cr.move_to(0, -4)
            cr.line_to(2.5, -1.5)
            cr.stroke()
            cr.restore()

        # 6. Временные метки (00, 06, 12, 18, 23)
        cr.set_source_rgba(1, 1, 1, 0.42)
        cr.set_font_size(9.5)
        for h in (0, 6, 12, 18, 23):
            hx, _ = to_xy(h, 0)
            txt = f"{h:02d}"
            ext = cr.text_extents(txt)
            cr.move_to(hx - ext.width / 2.0, height - 28)
            cr.show_text(txt)

        # 7. Легенда
        is_ru = (get_current_language() == "ru")
        cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9.5)

        cr.set_source_rgba(0.35, 0.80, 1.0, 0.95)
        cr.rectangle(pad_l + 4, 12, 12, 3)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.75)
        cr.move_to(pad_l + 20, 16)
        cr.show_text("Ветер" if is_ru else "Wind")

        cr.set_source_rgba(1.0, 0.65, 0.25, 0.85)
        cr.rectangle(pad_l + 80, 12, 12, 3)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.75)
        cr.move_to(pad_l + 96, 16)
        cr.show_text("Порывы" if is_ru else "Gusts")

        # 8. Индикатор текущего часа
        if (not self.is_scrubbing) and self.is_today and 0 <= self.cur_hour < 24:
            cx, cy = pts_spd[self.cur_hour]
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

        # 9. Скруббер
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
            cr.set_source_rgba(0.35, 0.80, 1.0, 0.95)
            cr.stroke()
            cr.restore()


def build_wind_view(sheet) -> Gtk.Box:
    """Конструирует контейнер карточки ветра и связывает его с листом деталей."""
    is_ru = (get_current_language() == "ru")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.set_valign(Gtk.Align.START)

    # 1. Compass Card
    comp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    comp_card.add_css_class("weather-glass-card")

    lbl_comp_title = Gtk.Label(label="НАПРАВЛЕНИЕ И СКОРОСТЬ ВЕТРА" if is_ru else "WIND DIRECTION & SPEED")
    lbl_comp_title.add_css_class("weather-section-title")
    lbl_comp_title.set_halign(Gtk.Align.START)
    comp_card.append(lbl_comp_title)

    sheet.wind_compass_area = WindCompassArea()
    comp_card.append(sheet.wind_compass_area)

    sheet.lbl_compass_desc = Gtk.Label()
    sheet.lbl_compass_desc.add_css_class("weather-card-subtitle")
    sheet.lbl_compass_desc.set_halign(Gtk.Align.CENTER)
    comp_card.append(sheet.lbl_compass_desc)

    box.append(comp_card)

    # 2. 24h Hourly Speed & Gusts Chart
    hourly_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    hourly_card.add_css_class("weather-glass-card")

    lbl_h_title = Gtk.Label(label="ПОЧАСОВОЙ ГРАФИК ВЕТРА И ПОРЫВОВ" if is_ru else "HOURLY WIND & GUSTS GRAPH")
    lbl_h_title.add_css_class("weather-section-title")
    lbl_h_title.set_halign(Gtk.Align.START)
    hourly_card.append(lbl_h_title)

    sheet.wind_hourly_area = WindHourlyArea()
    sheet.wind_hourly_area.on_scrub = sheet._on_wind_scrub
    hourly_card.append(sheet.wind_hourly_area)

    div_w = Gtk.Box()
    div_w.add_css_class("weather-card-divider")
    hourly_card.append(div_w)

    sum_w_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    sum_w_box.add_css_class("weather-chart-summary-box")

    sheet.lbl_wind_sum_time = Gtk.Label()
    sheet.lbl_wind_sum_time.add_css_class("weather-chart-summary-time")
    sheet.lbl_wind_sum_time.set_halign(Gtk.Align.START)
    sheet.lbl_wind_sum_time.set_xalign(0.0)
    sum_w_box.append(sheet.lbl_wind_sum_time)

    sheet.lbl_wind_sum_text = Gtk.Label()
    sheet.lbl_wind_sum_text.add_css_class("weather-chart-summary-text")
    sheet.lbl_wind_sum_text.set_wrap(True)
    sheet.lbl_wind_sum_text.set_halign(Gtk.Align.START)
    sheet.lbl_wind_sum_text.set_xalign(0.0)
    sum_w_box.append(sheet.lbl_wind_sum_text)

    hourly_card.append(sum_w_box)
    box.append(hourly_card)

    # 3. Wind Characteristics Card
    char_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    char_card.add_css_class("weather-glass-card")

    lbl_char_title = Gtk.Label(label="ХАРАКТЕРИСТИКИ ВЕТРА" if is_ru else "WIND CHARACTERISTICS")
    lbl_char_title.add_css_class("weather-section-title")
    lbl_char_title.set_halign(Gtk.Align.START)
    char_card.append(lbl_char_title)

    div_c = Gtk.Box()
    div_c.add_css_class("weather-card-divider")
    char_card.append(div_c)

    row_w1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_w1 = Gtk.Label(label="Максимальная скорость" if is_ru else "Max wind speed")
    lbl_w1.add_css_class("weather-body-text")
    row_w1.append(lbl_w1)
    sheet.lbl_wind_max = Gtk.Label(label="-- км/ч" if is_ru else "-- km/h")
    sheet.lbl_wind_max.add_css_class("weather-item-bold")
    sheet.lbl_wind_max.set_hexpand(True)
    sheet.lbl_wind_max.set_halign(Gtk.Align.END)
    row_w1.append(sheet.lbl_wind_max)
    char_card.append(row_w1)

    row_w2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_w2 = Gtk.Label(label="Максимальные порывы" if is_ru else "Peak gusts")
    lbl_w2.add_css_class("weather-body-text")
    row_w2.append(lbl_w2)
    sheet.lbl_wind_gusts_max = Gtk.Label(label="-- км/ч" if is_ru else "-- km/h")
    sheet.lbl_wind_gusts_max.add_css_class("weather-item-bold")
    sheet.lbl_wind_gusts_max.set_hexpand(True)
    sheet.lbl_wind_gusts_max.set_halign(Gtk.Align.END)
    row_w2.append(sheet.lbl_wind_gusts_max)
    char_card.append(row_w2)

    row_w3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_w3 = Gtk.Label(label="Преобладающее направление" if is_ru else "Dominant direction")
    lbl_w3.add_css_class("weather-body-text")
    row_w3.append(lbl_w3)
    sheet.lbl_wind_dir_name = Gtk.Label(label="--")
    sheet.lbl_wind_dir_name.add_css_class("weather-item-bold")
    sheet.lbl_wind_dir_name.set_hexpand(True)
    sheet.lbl_wind_dir_name.set_halign(Gtk.Align.END)
    row_w3.append(sheet.lbl_wind_dir_name)
    char_card.append(row_w3)

    box.append(char_card)

    # 4. Day Comparison Card
    sheet.wind_comp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    sheet.wind_comp_card.add_css_class("weather-glass-card")

    lbl_w_comp_title = Gtk.Label(label="СРАВНЕНИЕ ПО ДНЯМ" if is_ru else "DAY COMPARISON")
    lbl_w_comp_title.add_css_class("weather-section-title")
    lbl_w_comp_title.set_halign(Gtk.Align.START)
    sheet.wind_comp_card.append(lbl_w_comp_title)

    div_w_comp = Gtk.Box()
    div_w_comp.add_css_class("weather-card-divider")
    sheet.wind_comp_card.append(div_w_comp)

    sheet.lbl_wind_comp_sub = Gtk.Label()
    sheet.lbl_wind_comp_sub.add_css_class("weather-card-subtitle")
    sheet.lbl_wind_comp_sub.set_wrap(True)
    sheet.lbl_wind_comp_sub.set_halign(Gtk.Align.START)
    sheet.wind_comp_card.append(sheet.lbl_wind_comp_sub)

    sheet.wind_comp_bar = DayComparisonBarArea()
    sheet.wind_comp_card.append(sheet.wind_comp_bar)

    box.append(sheet.wind_comp_card)

    # 5. Beaufort Scale Reference Card
    bft_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    bft_card.add_css_class("weather-glass-card")
    lbl_bft_title = Gtk.Label(label="ШКАЛА БОФОРТА" if is_ru else "BEAUFORT SCALE")
    lbl_bft_title.add_css_class("weather-section-title")
    lbl_bft_title.set_halign(Gtk.Align.START)
    bft_card.append(lbl_bft_title)
    div_b = Gtk.Box()
    div_b.add_css_class("weather-card-divider")
    bft_card.append(div_b)

    spd_u = "км/ч" if is_ru else "km/h"
    bft_rows = [
        (f"< 6 {spd_u}", "Штиль / тихий" if is_ru else "Calm / Light air", "Дым поднимается почти вертикально" if is_ru else "Smoke rises vertically"),
        (f"6 – 19 {spd_u}", "Легкий / слабый" if is_ru else "Light / Gentle breeze", "Листья шелестят, флюгер движется" if is_ru else "Leaves rustle, vanes moved"),
        (f"20 – 38 {spd_u}", "Умеренный / свежий" if is_ru else "Moderate / Fresh breeze", "Колышутся тонкие ветви, поднимается пыль" if is_ru else "Small trees begin to sway"),
        (f"39 – 61 {spd_u}", "Сильный / крепкий" if is_ru else "Strong breeze / Gale", "Качаются большие ветви, зонты гнутся" if is_ru else "Large branches in motion"),
        (f"62+ {spd_u}", "Шторм / буря" if is_ru else "Storm / Gale", "Ломаются сучья деревьев, трудно идти" if is_ru else "Structural damage possible"),
    ]
    for spd_r, b_name, b_desc in bft_rows:
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_r = Gtk.Label(label=spd_r)
        lbl_r.add_css_class("weather-item-bold")
        lbl_r.set_size_request(80, -1)
        lbl_r.set_xalign(0.0)
        r.append(lbl_r)

        lbl_d = Gtk.Label(label=f"{b_name} ({b_desc})")
        lbl_d.add_css_class("weather-body-text")
        lbl_d.set_wrap(True)
        lbl_d.set_hexpand(True)
        lbl_d.set_xalign(0.0)
        r.append(lbl_d)
        bft_card.append(r)

    box.append(bft_card)
    sheet.mode_stack.add_named(box, "wind")
    return box
