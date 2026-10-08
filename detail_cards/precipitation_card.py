"""
Карточка осадков: почасовой объем (столбцы мм), кривая вероятности (%) со скруббером и сравнение по дням.
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


class PrecipitationHourlyArea(BaseWeatherHourlyArea):
    """Почасовой объем (столбики мм) и вероятность (% кривая) осадков с интерактивным скруббером."""

    def __init__(self):
        self.precips = [0.0] * 24
        self.probs = [0] * 24
        super().__init__(content_height=190)

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
        bar_slot = plot_w / 24.0

        clamped_x = max(pad_l + bar_slot / 2.0, min(pad_l + plot_w - bar_slot / 2.0, x))
        frac_h = (clamped_x - (pad_l + bar_slot / 2.0)) / float(bar_slot)
        frac_h = max(0.0, min(23.0, frac_h))

        if not self.probs or len(self.probs) < 24:
            return

        pts_prob = [
            (pad_l + h * bar_slot + bar_slot / 2.0, pad_t + plot_h - (p / 100.0) * plot_h)
            for h, p in enumerate(self.probs)
        ]

        i = min(22, max(0, int(frac_h)))
        f = frac_h - i
        p0 = pts_prob[max(0, i - 1)]
        p1 = pts_prob[i]
        p2 = pts_prob[i + 1]
        p3 = pts_prob[min(len(pts_prob) - 1, i + 2)]

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

        h_closest = min(23, max(0, int(round(frac_h))))
        val_mm = self.precips[h_closest]
        prob_val = min(100, max(0, round(self.probs[i] * (1.0 - f) + self.probs[i + 1] * f)))

        self.queue_draw()

        if callable(self.on_scrub):
            self.on_scrub({
                "active": True,
                "frac_h": frac_h,
                "hour": h_int,
                "minute": minute,
                "time_str": time_str,
                "precip": val_mm,
                "prob": prob_val,
            })

    def update_data(self, precips: list, probs: list, cur_hour: int, is_today: bool):
        self.precips = [float(x) for x in precips[:24]] if len(precips) >= 24 else ([0.0] * 24)
        self.probs = [int(x) for x in probs[:24]] if len(probs) >= 24 else ([0] * 24)
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

        max_p = max(self.precips)
        y_max_mm = max(2.0, math.ceil(max_p * 2.0) / 2.0)

        # 1. Сетка
        cr.set_line_width(0.7)
        for pct in (0, 50, 100):
            y = pad_t + plot_h - (pct / 100.0) * plot_h
            cr.set_source_rgba(1, 1, 1, 0.08)
            cr.move_to(pad_l, y)
            cr.line_to(pad_l + plot_w, y)
            cr.stroke()

            cr.set_source_rgba(1, 1, 1, 0.40)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(9)
            cr.move_to(pad_l + plot_w + 6, y + 3)
            cr.show_text(f"{pct}%")

        # 2. Столбики осадков (мм)
        bar_slot = plot_w / 24.0
        bar_w = max(3.0, bar_slot - 3.5)
        h_closest = (
            min(23, max(0, int(round(self.scrub_hour_frac))))
            if (self.is_scrubbing and self.scrub_hour_frac is not None)
            else -1
        )

        for h in range(24):
            val_mm = self.precips[h]
            bx = pad_l + h * bar_slot + (bar_slot - bar_w) / 2.0
            bh = (val_mm / y_max_mm) * plot_h
            by = pad_t + plot_h - bh

            cr.set_source_rgba(1, 1, 1, 0.04)
            cr.rectangle(bx, pad_t, bar_w, plot_h)
            cr.fill()

            if val_mm > 0.05:
                pat = cairo.LinearGradient(bx, by, bx, by + bh)
                pat.add_color_stop_rgba(0.0, 0.25, 0.65, 0.98, 0.95)
                pat.add_color_stop_rgba(1.0, 0.15, 0.45, 0.85, 0.50)
                cr.set_source(pat)
                cr.rectangle(bx, by, bar_w, bh)
                cr.fill()

                if val_mm >= 0.5:
                    cr.set_source_rgba(1, 1, 1, 0.90)
                    cr.set_font_size(8)
                    txt = f"{val_mm:.1f}"
                    ext = cr.text_extents(txt)
                    cr.move_to(bx + bar_w / 2.0 - ext.width / 2.0, max(12, by - 4))
                    cr.show_text(txt)

            if self.is_scrubbing and h == h_closest:
                cr.set_source_rgba(1, 1, 1, 0.45)
                cr.set_line_width(1.0)
                cr.rectangle(bx - 0.5, by - 0.5, bar_w + 1, bh + 0.5)
                cr.stroke()

        # 3. Линия вероятности осадков (%)
        pts_prob = [
            (pad_l + h * bar_slot + bar_slot / 2.0, pad_t + plot_h - (p / 100.0) * plot_h)
            for h, p in enumerate(self.probs)
        ]
        cr.save()
        cr.move_to(pts_prob[0][0], pts_prob[0][1])
        for i in range(len(pts_prob) - 1):
            p0 = pts_prob[max(0, i - 1)]
            p1 = pts_prob[i]
            p2 = pts_prob[i + 1]
            p3 = pts_prob[min(len(pts_prob) - 1, i + 2)]
            cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
            cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
            cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
            cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
            cr.curve_to(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1])
        cr.set_line_width(1.8)
        cr.set_dash([3.0, 3.0])
        cr.set_source_rgba(0.40, 0.85, 1.0, 0.85)
        cr.stroke()
        cr.restore()

        # 4. Часы
        cr.set_source_rgba(1, 1, 1, 0.42)
        cr.set_font_size(9.5)
        for h in (0, 6, 12, 18, 23):
            hx = pad_l + h * bar_slot + bar_slot / 2.0
            txt = f"{h:02d}"
            ext = cr.text_extents(txt)
            cr.move_to(hx - ext.width / 2.0, height - 8)
            cr.show_text(txt)

        # 5. Текущий час
        if (not self.is_scrubbing) and self.is_today and 0 <= self.cur_hour < 24:
            cx = pad_l + self.cur_hour * bar_slot + bar_slot / 2.0
            cy = pts_prob[self.cur_hour][1]
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
            cr.set_source_rgba(0.40, 0.85, 1.0, 0.95)
            cr.stroke()
            cr.restore()


def build_precipitation_view(sheet) -> Gtk.Box:
    """Конструирует контейнер карточки осадков и связывает его с листом деталей."""
    is_ru = (get_current_language() == "ru")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.set_valign(Gtk.Align.START)

    # 1. 24h Hourly Precipitation Card
    precip_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    precip_card.add_css_class("weather-glass-card")

    lbl_pr_title = Gtk.Label(label=t("weather_precip_hourly_hdr"))
    lbl_pr_title.add_css_class("weather-section-title")
    lbl_pr_title.set_halign(Gtk.Align.START)
    precip_card.append(lbl_pr_title)

    sheet.precip_hourly_area = PrecipitationHourlyArea()
    sheet.precip_hourly_area.on_scrub = sheet._on_precip_scrub
    precip_card.append(sheet.precip_hourly_area)

    div_p = Gtk.Box()
    div_p.add_css_class("weather-card-divider")
    precip_card.append(div_p)

    sum_p_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    sum_p_box.add_css_class("weather-chart-summary-box")

    sheet.lbl_precip_sum_time = Gtk.Label()
    sheet.lbl_precip_sum_time.add_css_class("weather-chart-summary-time")
    sheet.lbl_precip_sum_time.set_halign(Gtk.Align.START)
    sheet.lbl_precip_sum_time.set_xalign(0.0)
    sum_p_box.append(sheet.lbl_precip_sum_time)

    sheet.lbl_precip_sum_text = Gtk.Label()
    sheet.lbl_precip_sum_text.add_css_class("weather-chart-summary-text")
    sheet.lbl_precip_sum_text.set_wrap(True)
    sheet.lbl_precip_sum_text.set_halign(Gtk.Align.START)
    sheet.lbl_precip_sum_text.set_xalign(0.0)
    sum_p_box.append(sheet.lbl_precip_sum_text)

    precip_card.append(sum_p_box)
    box.append(precip_card)

    # 2. Daily Precipitation Summary Card
    vol_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    vol_card.add_css_class("weather-glass-card")

    lbl_v_title = Gtk.Label(label=t("weather_precip_daily_hdr"))
    lbl_v_title.add_css_class("weather-section-title")
    lbl_v_title.set_halign(Gtk.Align.START)
    vol_card.append(lbl_v_title)

    div_v = Gtk.Box()
    div_v.add_css_class("weather-card-divider")
    vol_card.append(div_v)

    row_p1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_p1 = Gtk.Label(label=t("weather_precip_total_vol"))
    lbl_p1.add_css_class("weather-body-text")
    row_p1.append(lbl_p1)
    sheet.lbl_pr_day_vol = Gtk.Label(label=f"0.0 {t('unit_mm')}")
    sheet.lbl_pr_day_vol.add_css_class("weather-item-bold")
    sheet.lbl_pr_day_vol.set_hexpand(True)
    sheet.lbl_pr_day_vol.set_halign(Gtk.Align.END)
    row_p1.append(sheet.lbl_pr_day_vol)
    vol_card.append(row_p1)

    row_p2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_p2 = Gtk.Label(label=t("weather_precip_peak_prob"))
    lbl_p2.add_css_class("weather-body-text")
    row_p2.append(lbl_p2)
    sheet.lbl_pr_day_prob = Gtk.Label(label="0%")
    sheet.lbl_pr_day_prob.add_css_class("weather-item-bold")
    sheet.lbl_pr_day_prob.set_hexpand(True)
    sheet.lbl_pr_day_prob.set_halign(Gtk.Align.END)
    row_p2.append(sheet.lbl_pr_day_prob)
    vol_card.append(row_p2)

    box.append(vol_card)

    # 3. Day Comparison Card
    sheet.precip_comp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    sheet.precip_comp_card.add_css_class("weather-glass-card")

    lbl_pr_comp_title = Gtk.Label(label=t("weather_comp_days_hdr"))
    lbl_pr_comp_title.add_css_class("weather-section-title")
    lbl_pr_comp_title.set_halign(Gtk.Align.START)
    sheet.precip_comp_card.append(lbl_pr_comp_title)

    div_pr_comp = Gtk.Box()
    div_pr_comp.add_css_class("weather-card-divider")
    sheet.precip_comp_card.append(div_pr_comp)

    sheet.lbl_precip_comp_sub = Gtk.Label()
    sheet.lbl_precip_comp_sub.add_css_class("weather-card-subtitle")
    sheet.lbl_precip_comp_sub.set_wrap(True)
    sheet.lbl_precip_comp_sub.set_halign(Gtk.Align.START)
    sheet.precip_comp_card.append(sheet.lbl_precip_comp_sub)

    sheet.precip_comp_bar = DayComparisonBarArea()
    sheet.precip_comp_card.append(sheet.precip_comp_bar)

    box.append(sheet.precip_comp_card)

    # 4. Atmospheric Moisture Card
    info_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    info_card.add_css_class("weather-glass-card")
    lbl_i_title = Gtk.Label(label=t("weather_precip_dynamics_hdr"))
    lbl_i_title.add_css_class("weather-section-title")
    lbl_i_title.set_halign(Gtk.Align.START)
    info_card.append(lbl_i_title)
    div_i = Gtk.Box()
    div_i.add_css_class("weather-card-divider")
    info_card.append(div_i)
    lbl_i_text = Gtk.Label(
        label=(
            "Вероятность осадков отражает шанс выпадения дождя или снега в любой точке города в течение указанного времени. "
            "Объем менее 1 мм считается слабыми осадками (морось), от 2 до 10 мм — умеренным дождем, свыше 15 мм — сильным ливнем."
            if is_ru
            else "Precipitation probability reflects the chance of rain or snow in the area. Less than 1 mm is considered light drizzle, 2 to 10 mm moderate rain, and over 15 mm heavy downpour."
        )
    )
    lbl_i_text.add_css_class("weather-body-text")
    lbl_i_text.set_wrap(True)
    lbl_i_text.set_halign(Gtk.Align.START)
    info_card.append(lbl_i_text)
    box.append(info_card)

    sheet.mode_stack.add_named(box, "precipitation")
    return box
