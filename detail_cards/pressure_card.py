"""
Карточка давления: аналоговый круговой стрелочный барометр, 24-часовой график тренда со скруббером и шкала влияния.
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


class PressureGaugeArea(Gtk.DrawingArea):
    """Круговой аналоговый барометр со стрелкой, индикатором нормального давления и единицами."""

    def __init__(self):
        super().__init__()
        self.set_content_height(170)
        self.set_hexpand(True)
        self.pressure_mm = 752
        self.pressure_hpa = 1003
        self.set_draw_func(self._on_draw)

    def update_data(self, press_mm: int, press_hpa: int):
        self.pressure_mm = press_mm
        self.pressure_hpa = press_hpa
        self.queue_draw()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        cx = width / 2.0
        cy = height / 2.0 + 10
        radius = min(cx - 30, cy - 10, 68)

        start_ang = math.pi * 0.80
        end_ang = math.pi * 2.20

        # 1. Фоновая дуга
        cr.set_line_width(9.0)
        cr.arc(cx, cy, radius, start_ang, end_ang)
        cr.set_source_rgba(1, 1, 1, 0.08)
        cr.stroke()

        def to_ang(val):
            pct = max(0.0, min(1.0, (val - 720.0) / 60.0))
            return start_ang + pct * (end_ang - start_ang)

        # Активная дуга значения
        val_ang = to_ang(self.pressure_mm)
        cr.arc(cx, cy, radius, start_ang, val_ang)
        pat = cairo.LinearGradient(cx - radius, cy, cx + radius, cy)
        pat.add_color_stop_rgba(0.0, 0.35, 0.70, 0.98, 0.95)
        pat.add_color_stop_rgba(0.5, 0.40, 0.85, 0.65, 0.95)
        pat.add_color_stop_rgba(1.0, 0.95, 0.65, 0.25, 0.95)
        cr.set_source(pat)
        cr.set_line_width(9.0)
        cr.stroke()

        # 2. Метки делений
        for v in [720, 740, 750, 760, 780]:
            ang = to_ang(v)
            x1 = cx + (radius - 8) * math.cos(ang)
            y1 = cy + (radius - 8) * math.sin(ang)
            x2 = cx + (radius + 8) * math.cos(ang)
            y2 = cy + (radius + 8) * math.sin(ang)
            cr.set_line_width(1.2)
            cr.set_source_rgba(1, 1, 1, 0.45)
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()

        # 3. Стрелка барометра
        nx = cx + (radius - 4) * math.cos(val_ang)
        ny = cy + (radius - 4) * math.sin(val_ang)
        bx = cx - 10 * math.cos(val_ang)
        by = cy - 10 * math.sin(val_ang)

        cr.set_line_width(2.5)
        cr.set_source_rgba(1, 1, 1, 0.95)
        cr.move_to(bx, by)
        cr.line_to(nx, ny)
        cr.stroke()

        # Центр
        cr.arc(cx, cy, 5.0, 0, 2 * math.pi)
        cr.set_source_rgba(0.15, 0.18, 0.26, 1.0)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.8)
        cr.set_line_width(1.5)
        cr.stroke()

        # 4. Числовое значение
        cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(17)
        val_str = f"{self.pressure_mm}"
        ext = cr.text_extents(val_str)
        cr.set_source_rgba(1, 1, 1, 0.95)
        cr.move_to(cx - ext.width / 2.0, cy - 10)
        cr.show_text(val_str)

        cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9)
        unit_str = "мм рт. ст." if get_current_language() == "ru" else "mmHg"
        ext_u = cr.text_extents(unit_str)
        cr.set_source_rgba(1, 1, 1, 0.55)
        cr.move_to(cx - ext_u.width / 2.0, cy + 4)
        cr.show_text(unit_str)

        hpa_str = f"{self.pressure_hpa} гПа" if get_current_language() == "ru" else f"{self.pressure_hpa} hPa"
        ext_h = cr.text_extents(hpa_str)
        cr.set_source_rgba(1, 1, 1, 0.40)
        cr.move_to(cx - ext_h.width / 2.0, cy + 18)
        cr.show_text(hpa_str)


class PressureHourlyArea(BaseWeatherHourlyArea):
    """Почасовой график изменения давления со скруббером и линией тренда."""

    def __init__(self):
        self.pressures = [752] * 24
        super().__init__(content_height=170)

    def _process_scrub(self, x: float, y: float):
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return

        pad_l = 28
        pad_r = 44
        pad_t = 28
        pad_b = 30
        plot_w = max(10, width - pad_l - pad_r)
        plot_h = max(10, height - pad_t - pad_b)

        frac_h = self._calc_frac_h(x, pad_l, plot_w)

        if not self.pressures or len(self.pressures) < 24:
            return

        min_p = min(self.pressures)
        max_p = max(self.pressures)
        y_min = min_p - 2
        y_max = max_p + 2
        if y_max <= y_min:
            y_max = y_min + 4

        def to_xy(idx, val):
            px = pad_l + (idx / 23.0) * plot_w
            py = pad_t + plot_h - ((val - y_min) / float(y_max - y_min)) * plot_h
            return px, py

        pts = [to_xy(i, v) for i, v in enumerate(self.pressures)]

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
        press_val = round(y_min + norm_y * (y_max - y_min))
        press_hpa = round(press_val / 0.75006)

        self.queue_draw()

        if callable(self.on_scrub):
            self.on_scrub({
                "active": True,
                "frac_h": frac_h,
                "hour": h_int,
                "minute": minute,
                "time_str": time_str,
                "pressure_mm": press_val,
                "pressure_hpa": press_hpa,
            })

    def update_data(self, pressures: list, cur_hour: int, is_today: bool):
        self.pressures = pressures if len(pressures) >= 24 else ([752] * 24)
        self.cur_hour = cur_hour
        self.is_today = is_today
        self.queue_draw()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        pad_l = 28
        pad_r = 44
        pad_t = 28
        pad_b = 30

        plot_w = max(10, width - pad_l - pad_r)
        plot_h = max(10, height - pad_t - pad_b)

        min_p = min(self.pressures)
        max_p = max(self.pressures)
        y_min = min_p - 2
        y_max = max_p + 2
        if y_max <= y_min:
            y_max = y_min + 4

        def to_xy(idx, val):
            x = pad_l + (idx / 23.0) * plot_w
            y = pad_t + plot_h - ((val - y_min) / float(y_max - y_min)) * plot_h
            return x, y

        pts = [to_xy(i, v) for i, v in enumerate(self.pressures)]

        # 1. Сетка
        cr.set_line_width(0.7)
        for v in range(int(y_min), int(y_max) + 1, 2):
            _, y = to_xy(0, v)
            cr.set_source_rgba(1, 1, 1, 0.08)
            cr.move_to(pad_l, y)
            cr.line_to(pad_l + plot_w, y)
            cr.stroke()

            cr.set_source_rgba(1, 1, 1, 0.40)
            cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(9)
            cr.move_to(pad_l + plot_w + 6, y + 3)
            cr.show_text(f"{v}")

        # 2. Заливка кривой
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
        pat.add_color_stop_rgba(0.0, 0.65, 0.45, 0.95, 0.30)
        pat.add_color_stop_rgba(1.0, 0.65, 0.45, 0.95, 0.02)
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
        cr.set_source_rgba(0.75, 0.55, 1.0, 0.95)
        cr.stroke()
        cr.restore()

        # 4. Часы
        cr.set_source_rgba(1, 1, 1, 0.42)
        cr.set_font_size(9.5)
        for h in (0, 6, 12, 18, 23):
            hx, _ = to_xy(h, y_min)
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
            cr.set_source_rgba(0.75, 0.55, 1.0, 0.95)
            cr.stroke()
            cr.restore()


def build_pressure_view(sheet) -> Gtk.Box:
    """Конструирует контейнер карточки давления и связывает его с листом деталей."""
    is_ru = (get_current_language() == "ru")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.set_valign(Gtk.Align.START)

    # 1. Analog Barometer Gauge Card
    gauge_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    gauge_card.add_css_class("weather-glass-card")

    lbl_g_title = Gtk.Label(label="БАРОМЕТР" if is_ru else "BAROMETER GAUGE")
    lbl_g_title.add_css_class("weather-section-title")
    lbl_g_title.set_halign(Gtk.Align.START)
    gauge_card.append(lbl_g_title)

    sheet.pressure_gauge_area = PressureGaugeArea()
    gauge_card.append(sheet.pressure_gauge_area)

    sheet.lbl_press_status_sub = Gtk.Label()
    sheet.lbl_press_status_sub.add_css_class("weather-card-subtitle")
    sheet.lbl_press_status_sub.set_halign(Gtk.Align.CENTER)
    gauge_card.append(sheet.lbl_press_status_sub)

    box.append(gauge_card)

    # 2. 24h Barometric Trend Card
    trend_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    trend_card.add_css_class("weather-glass-card")

    lbl_t_title = Gtk.Label(label="СУТОЧНЫЙ ТРЕНД ДАВЛЕНИЯ" if is_ru else "24-HOUR PRESSURE TREND")
    lbl_t_title.add_css_class("weather-section-title")
    lbl_t_title.set_halign(Gtk.Align.START)
    trend_card.append(lbl_t_title)

    sheet.pressure_hourly_area = PressureHourlyArea()
    sheet.pressure_hourly_area.on_scrub = sheet._on_press_scrub
    trend_card.append(sheet.pressure_hourly_area)

    div_pr = Gtk.Box()
    div_pr.add_css_class("weather-card-divider")
    trend_card.append(div_pr)

    sum_pr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    sum_pr_box.add_css_class("weather-chart-summary-box")

    sheet.lbl_press_sum_time = Gtk.Label()
    sheet.lbl_press_sum_time.add_css_class("weather-chart-summary-time")
    sheet.lbl_press_sum_time.set_halign(Gtk.Align.START)
    sheet.lbl_press_sum_time.set_xalign(0.0)
    sum_pr_box.append(sheet.lbl_press_sum_time)

    sheet.lbl_press_sum_text = Gtk.Label()
    sheet.lbl_press_sum_text.add_css_class("weather-chart-summary-text")
    sheet.lbl_press_sum_text.set_wrap(True)
    sheet.lbl_press_sum_text.set_halign(Gtk.Align.START)
    sheet.lbl_press_sum_text.set_xalign(0.0)
    sum_pr_box.append(sheet.lbl_press_sum_text)

    trend_card.append(sum_pr_box)
    box.append(trend_card)

    # 3. Barometric Values Card
    val_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    val_card.add_css_class("weather-glass-card")

    lbl_v_title = Gtk.Label(label="ПАРАМЕТРЫ ДАВЛЕНИЯ" if is_ru else "PRESSURE READINGS")
    lbl_v_title.add_css_class("weather-section-title")
    lbl_v_title.set_halign(Gtk.Align.START)
    val_card.append(lbl_v_title)

    div_v = Gtk.Box()
    div_v.add_css_class("weather-card-divider")
    val_card.append(div_v)

    row_pr1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_pr1 = Gtk.Label(label="В миллиметрах ртутного столба" if is_ru else "In millimeters of mercury")
    lbl_pr1.add_css_class("weather-body-text")
    row_pr1.append(lbl_pr1)
    sheet.lbl_press_val_mm = Gtk.Label(label="752 мм" if is_ru else "752 mmHg")
    sheet.lbl_press_val_mm.add_css_class("weather-item-bold")
    sheet.lbl_press_val_mm.set_hexpand(True)
    sheet.lbl_press_val_mm.set_halign(Gtk.Align.END)
    row_pr1.append(sheet.lbl_press_val_mm)
    val_card.append(row_pr1)

    row_pr2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_pr2 = Gtk.Label(label="В гектопаскалях (гПа / мбар)" if is_ru else "In hectopascals (hPa / mbar)")
    lbl_pr2.add_css_class("weather-body-text")
    row_pr2.append(lbl_pr2)
    sheet.lbl_press_val_hpa = Gtk.Label(label="1003 гПа" if is_ru else "1003 hPa")
    sheet.lbl_press_val_hpa.add_css_class("weather-item-bold")
    sheet.lbl_press_val_hpa.set_hexpand(True)
    sheet.lbl_press_val_hpa.set_halign(Gtk.Align.END)
    row_pr2.append(sheet.lbl_press_val_hpa)
    val_card.append(row_pr2)

    row_pr3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_pr3 = Gtk.Label(label="Тенденция" if is_ru else "Barometric tendency")
    lbl_pr3.add_css_class("weather-body-text")
    row_pr3.append(lbl_pr3)
    sheet.lbl_press_trend_desc = Gtk.Label(label="Стабильно" if is_ru else "Steady")
    sheet.lbl_press_trend_desc.add_css_class("weather-item-bold")
    sheet.lbl_press_trend_desc.set_hexpand(True)
    sheet.lbl_press_trend_desc.set_halign(Gtk.Align.END)
    row_pr3.append(sheet.lbl_press_trend_desc)
    val_card.append(row_pr3)

    box.append(val_card)

    # 4. Day Comparison Card
    sheet.press_comp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    sheet.press_comp_card.add_css_class("weather-glass-card")

    lbl_pr_comp_title = Gtk.Label(label="СРАВНЕНИЕ ПО ДНЯМ" if is_ru else "DAY COMPARISON")
    lbl_pr_comp_title.add_css_class("weather-section-title")
    lbl_pr_comp_title.set_halign(Gtk.Align.START)
    sheet.press_comp_card.append(lbl_pr_comp_title)

    div_pr_comp = Gtk.Box()
    div_pr_comp.add_css_class("weather-card-divider")
    sheet.press_comp_card.append(div_pr_comp)

    sheet.lbl_press_comp_sub = Gtk.Label()
    sheet.lbl_press_comp_sub.add_css_class("weather-card-subtitle")
    sheet.lbl_press_comp_sub.set_wrap(True)
    sheet.lbl_press_comp_sub.set_halign(Gtk.Align.START)
    sheet.press_comp_card.append(sheet.lbl_press_comp_sub)

    sheet.press_comp_bar = DayComparisonBarArea()
    sheet.press_comp_card.append(sheet.press_comp_bar)

    box.append(sheet.press_comp_card)

    # 5. Medical & Atmospheric Guide Card
    med_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    med_card.add_css_class("weather-glass-card")
    lbl_m_title = Gtk.Label(label="ВЛИЯНИЕ НА САМОЧУВСТВИЕ" if is_ru else "HEALTH & BAROMETRIC IMPACT")
    lbl_m_title.add_css_class("weather-section-title")
    lbl_m_title.set_halign(Gtk.Align.START)
    med_card.append(lbl_m_title)
    div_m = Gtk.Box()
    div_m.add_css_class("weather-card-divider")
    med_card.append(div_m)
    lbl_m_text = Gtk.Label(
        label=(
            "Стандартным нормальным давлением на уровне моря считается 760 мм рт. ст. (1013 гПа). "
            "При резком падении давления (прохождение циклона) у метеозависимых людей могут наблюдаться сонливость, головная боль и снижение тонуса. "
            "При росте давления (антициклон) устанавливается ясная сухая погода."
            if is_ru
            else "Standard sea-level pressure is 760 mmHg (1013 hPa). Sudden pressure drops indicate an approaching cyclone, which can cause fatigue and headaches in barosensitive people. High pressure brings clear, stable conditions."
        )
    )
    lbl_m_text.add_css_class("weather-body-text")
    lbl_m_text.set_wrap(True)
    lbl_m_text.set_halign(Gtk.Align.START)
    med_card.append(lbl_m_text)
    box.append(med_card)

    sheet.mode_stack.add_named(box, "pressure")
    return box
