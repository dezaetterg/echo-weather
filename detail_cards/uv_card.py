"""
Карточка УФ-индекса: график по часам со скруббером, шкала ВОЗ и рекомендации по защите от солнца.
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


class UVHourlyArea(BaseWeatherHourlyArea):
    """Интерактивный 24-часовой график УФ-индекса со шкалой ВОЗ и скруббером."""

    def __init__(self):
        self.uvs = [0.0] * 24
        super().__init__(content_height=190)

    def _process_scrub(self, x: float, y: float):
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return

        pad_l = 28
        pad_r = 38
        pad_t = 32
        pad_b = 32
        plot_w = max(10, width - pad_l - pad_r)
        plot_h = max(10, height - pad_t - pad_b)

        frac_h = self._calc_frac_h(x, pad_l, plot_w)

        if not self.uvs or len(self.uvs) < 24:
            return

        max_val = max(11.0, max(self.uvs) + 1.0)
        y_max = 12.0 if max_val <= 12.0 else math.ceil(max_val)

        def to_xy(idx, val):
            px = pad_l + (idx / 23.0) * plot_w
            py = pad_t + plot_h - (val / float(y_max)) * plot_h
            return px, py

        pts = [to_xy(i, v) for i, v in enumerate(self.uvs)]

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
        val = max(0.0, norm_y * y_max)

        self.queue_draw()

        if callable(self.on_scrub):
            self.on_scrub({
                "active": True,
                "frac_h": frac_h,
                "hour": h_int,
                "minute": minute,
                "time_str": time_str,
                "uv_val": round(val, 1),
            })

    def update_data(self, uvs: list, cur_hour: int, is_today: bool):
        self.uvs = [float(x) for x in uvs[:24]] if len(uvs) >= 24 else ([0.0] * 24)
        self.cur_hour = cur_hour
        self.is_today = is_today
        self.queue_draw()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        pad_l = 28
        pad_r = 38
        pad_t = 32
        pad_b = 32

        plot_w = max(10, width - pad_l - pad_r)
        plot_h = max(10, height - pad_t - pad_b)

        max_val = max(11.0, max(self.uvs) + 1.0)
        y_max = 12.0 if max_val <= 12.0 else math.ceil(max_val)

        def to_xy(idx, val):
            x = pad_l + (idx / 23.0) * plot_w
            y = pad_t + plot_h - (val / float(y_max)) * plot_h
            return x, y

        pts = [to_xy(i, v) for i, v in enumerate(self.uvs)]

        # 1. Горизонтальные зоны ВОЗ
        levels = [
            (0, 3, (0.2, 0.78, 0.35, 0.05)),
            (3, 6, (0.92, 0.79, 0.25, 0.06)),
            (6, 8, (0.95, 0.55, 0.20, 0.07)),
            (8, 11, (0.90, 0.25, 0.25, 0.07)),
            (11, int(y_max), (0.65, 0.35, 0.85, 0.08)),
        ]
        for l_min, l_max, color in levels:
            if l_min < y_max:
                _, y_top = to_xy(0, min(y_max, l_max))
                _, y_bot = to_xy(0, l_min)
                cr.set_source_rgba(*color)
                cr.rectangle(pad_l, y_top, plot_w, y_bot - y_top)
                cr.fill()

        # 1.5. Числовые значения УФ сверху
        cr.set_source_rgba(1, 1, 1, 0.45)
        cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9.5)
        for gh in (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22):
            if gh < len(self.uvs):
                gx = pad_l + (gh / 23.0) * plot_w
                u_int = round(self.uvs[gh])
                txt = str(u_int)
                ext = cr.text_extents(txt)
                cr.move_to(gx - ext.width / 2.0, pad_t - 10)
                cr.show_text(txt)

        # 2. Сетка на отметках 3, 6, 8, 11
        cr.set_line_width(0.7)
        for val in [3, 6, 8, 11]:
            if val <= y_max:
                _, y = to_xy(0, val)
                cr.set_source_rgba(1, 1, 1, 0.09)
                cr.move_to(pad_l, y)
                cr.line_to(pad_l + plot_w, y)
                cr.stroke()

                cr.set_source_rgba(1, 1, 1, 0.42)
                cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(9.5)
                cr.move_to(pad_l + plot_w + 6, y + 3.5)
                cr.show_text(str(val))

        # 3. Часы по оси X
        cr.set_source_rgba(1, 1, 1, 0.42)
        cr.set_font_size(9.5)
        for h in (0, 6, 12, 18, 23):
            hx, _ = to_xy(h, 0)
            txt = f"{h:02d}"
            ext = cr.text_extents(txt)
            cr.move_to(hx - ext.width / 2.0, height - 10)
            cr.show_text(txt)

        # 4. Заливка кривой
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
        pat.add_color_stop_rgba(0.0, 0.95, 0.70, 0.20, 0.35)
        pat.add_color_stop_rgba(0.7, 0.40, 0.80, 0.30, 0.10)
        pat.add_color_stop_rgba(1.0, 0.40, 0.80, 0.30, 0.00)
        cr.set_source(pat)
        cr.fill()
        cr.restore()

        # 5. Линия кривой
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
        cr.set_line_width(2.5)
        cr.set_source_rgba(0.98, 0.75, 0.25, 0.95)
        cr.stroke()
        cr.restore()

        # 6. Индикатор пика
        peak_val = max(self.uvs)
        peak_idx = self.uvs.index(peak_val)
        px, py = pts[peak_idx]

        if peak_val > 0.2:
            cr.arc(px, py, 4.5, 0, 2 * math.pi)
            cr.set_source_rgba(1, 1, 1, 1)
            cr.fill()

            is_ru = (get_current_language() == "ru")
            badge_txt = f"Пик {peak_val:.1f}" if is_ru else f"Peak {peak_val:.1f}"
            cr.select_font_face("Inter, -apple-system, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(10.5)
            ext = cr.text_extents(badge_txt)
            bw = ext.width + 12
            bh = 18
            bx = max(pad_l - 4, min(width - pad_r - bw + 4, px - bw / 2.0))
            by = py - bh - 6

            cr.save()
            cr.new_sub_path()
            r = 6.0
            cr.arc(bx + r, by + r, r, math.pi, 1.5 * math.pi)
            cr.arc(bx + bw - r, by + r, r, 1.5 * math.pi, 2 * math.pi)
            cr.arc(bx + bw - r, by + bh - r, r, 0, 0.5 * math.pi)
            cr.arc(bx + r, by + bh - r, r, 0.5 * math.pi, math.pi)
            cr.close_path()
            cr.set_source_rgba(0.12, 0.14, 0.22, 0.90)
            cr.fill_preserve()
            cr.set_source_rgba(1, 1, 1, 0.2)
            cr.set_line_width(0.8)
            cr.stroke()

            cr.set_source_rgba(1, 1, 1, 0.95)
            cr.move_to(bx + (bw - ext.width) / 2.0, by + bh - 4.5)
            cr.show_text(badge_txt)
            cr.restore()

        # 7. Индикатор текущего часа
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

        # 8. Скруббер
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
            cr.set_source_rgba(0.98, 0.75, 0.25, 0.95)
            cr.stroke()
            cr.restore()


def build_uv_view(sheet) -> Gtk.Box:
    """Конструирует контейнер карточки УФ-индекса и связывает его с объектом листа деталей."""
    is_ru = (get_current_language() == "ru")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.set_valign(Gtk.Align.START)

    # 1. 24h UV Curve Card
    uv_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    uv_card.add_css_class("weather-glass-card")

    lbl_uv_hdr = Gtk.Label(label="ГРАФИК УФ-ИНДЕКСА ПО ЧАСАМ" if is_ru else "HOURLY UV INDEX GRAPH")
    lbl_uv_hdr.add_css_class("weather-section-title")
    lbl_uv_hdr.set_halign(Gtk.Align.START)
    uv_card.append(lbl_uv_hdr)

    sheet.uv_hourly_area = UVHourlyArea()
    sheet.uv_hourly_area.on_scrub = sheet._on_uv_scrub
    uv_card.append(sheet.uv_hourly_area)

    div_uv = Gtk.Box()
    div_uv.add_css_class("weather-card-divider")
    uv_card.append(div_uv)

    sum_uv_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    sum_uv_box.add_css_class("weather-chart-summary-box")

    sheet.lbl_uv_sum_time = Gtk.Label()
    sheet.lbl_uv_sum_time.add_css_class("weather-chart-summary-time")
    sheet.lbl_uv_sum_time.set_halign(Gtk.Align.START)
    sheet.lbl_uv_sum_time.set_xalign(0.0)
    sum_uv_box.append(sheet.lbl_uv_sum_time)

    sheet.lbl_uv_sum_text = Gtk.Label()
    sheet.lbl_uv_sum_text.add_css_class("weather-chart-summary-text")
    sheet.lbl_uv_sum_text.set_wrap(True)
    sheet.lbl_uv_sum_text.set_halign(Gtk.Align.START)
    sheet.lbl_uv_sum_text.set_xalign(0.0)
    sum_uv_box.append(sheet.lbl_uv_sum_text)

    uv_card.append(sum_uv_box)
    box.append(uv_card)

    # 2. Level & Peak Info Card
    lvl_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    lvl_card.add_css_class("weather-glass-card")

    lbl_lvl_title = Gtk.Label(label="УРОВЕНЬ ИЗЛУЧЕНИЯ" if is_ru else "RADIATION LEVEL")
    lbl_lvl_title.add_css_class("weather-section-title")
    lbl_lvl_title.set_halign(Gtk.Align.START)
    lvl_card.append(lbl_lvl_title)

    div_l = Gtk.Box()
    div_l.add_css_class("weather-card-divider")
    lvl_card.append(div_l)

    row_u1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_u1 = Gtk.Label(label="Максимальный индекс сегодня" if is_ru else "Peak index today")
    lbl_u1.add_css_class("weather-body-text")
    row_u1.append(lbl_u1)
    sheet.lbl_uv_val = Gtk.Label(label="0.0")
    sheet.lbl_uv_val.add_css_class("weather-item-bold")
    sheet.lbl_uv_val.set_hexpand(True)
    sheet.lbl_uv_val.set_halign(Gtk.Align.END)
    row_u1.append(sheet.lbl_uv_val)
    lvl_card.append(row_u1)

    row_u2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    lbl_u2 = Gtk.Label(label="Уровень опасности" if is_ru else "Hazard level")
    lbl_u2.add_css_class("weather-body-text")
    row_u2.append(lbl_u2)
    sheet.lbl_uv_level = Gtk.Label(label="Низкий" if is_ru else "Low")
    sheet.lbl_uv_level.add_css_class("weather-item-bold")
    sheet.lbl_uv_level.set_hexpand(True)
    sheet.lbl_uv_level.set_halign(Gtk.Align.END)
    row_u2.append(sheet.lbl_uv_level)
    lvl_card.append(row_u2)

    box.append(lvl_card)

    # 3. Day Comparison Card
    sheet.uv_comp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    sheet.uv_comp_card.add_css_class("weather-glass-card")

    lbl_uv_comp_title = Gtk.Label(label="СРАВНЕНИЕ ПО ДНЯМ" if is_ru else "DAY COMPARISON")
    lbl_uv_comp_title.add_css_class("weather-section-title")
    lbl_uv_comp_title.set_halign(Gtk.Align.START)
    sheet.uv_comp_card.append(lbl_uv_comp_title)

    div_uv_comp = Gtk.Box()
    div_uv_comp.add_css_class("weather-card-divider")
    sheet.uv_comp_card.append(div_uv_comp)

    sheet.lbl_uv_comp_sub = Gtk.Label()
    sheet.lbl_uv_comp_sub.add_css_class("weather-card-subtitle")
    sheet.lbl_uv_comp_sub.set_wrap(True)
    sheet.lbl_uv_comp_sub.set_halign(Gtk.Align.START)
    sheet.uv_comp_card.append(sheet.lbl_uv_comp_sub)

    sheet.uv_comp_bar = DayComparisonBarArea()
    sheet.uv_comp_card.append(sheet.uv_comp_bar)

    box.append(sheet.uv_comp_card)

    # 4. Sun Protection Advice Card
    adv_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    adv_card.add_css_class("weather-glass-card")

    lbl_adv_title = Gtk.Label(label="РЕКОМЕНДАЦИИ ПО ЗАЩИТЕ" if is_ru else "SUN PROTECTION ADVICE")
    lbl_adv_title.add_css_class("weather-section-title")
    lbl_adv_title.set_halign(Gtk.Align.START)
    adv_card.append(lbl_adv_title)

    div_a = Gtk.Box()
    div_a.add_css_class("weather-card-divider")
    adv_card.append(div_a)

    sheet.lbl_uv_advice = Gtk.Label()
    sheet.lbl_uv_advice.add_css_class("weather-body-text")
    sheet.lbl_uv_advice.set_wrap(True)
    sheet.lbl_uv_advice.set_halign(Gtk.Align.START)
    adv_card.append(sheet.lbl_uv_advice)

    box.append(adv_card)

    # 5. WHO UV Scale Card
    who_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    who_card.add_css_class("weather-glass-card")
    lbl_who_title = Gtk.Label(label="ШКАЛА УФ-ИНДЕКСА ВОЗ" if is_ru else "WHO UV INDEX SCALE")
    lbl_who_title.add_css_class("weather-section-title")
    lbl_who_title.set_halign(Gtk.Align.START)
    who_card.append(lbl_who_title)
    div_w = Gtk.Box()
    div_w.add_css_class("weather-card-divider")
    who_card.append(div_w)

    who_items = [
        ("0 – 2", "Низкий" if is_ru else "Low", "Защита не требуется. Безопасно для кожи." if is_ru else "No protection needed. Safe for skin."),
        ("3 – 5", "Умеренный" if is_ru else "Moderate", "Необходима защита. SPF 30+, очки, головной убор." if is_ru else "Protection required. SPF 30+, sunglasses."),
        ("6 – 7", "Высокий" if is_ru else "High", "Тень в полуденные часы, SPF 50+, закрытая одежда." if is_ru else "Seek shade at midday, SPF 50+, protective clothing."),
        ("8 – 10", "Очень высокий" if is_ru else "Very High", "Опасно. Избегайте нахождения на открытом солнце." if is_ru else "Dangerous. Avoid open sun during midday hours."),
        ("11+", "Экстремальный" if is_ru else "Extreme", "Максимальный риск ожогов за 5–10 минут." if is_ru else "Extreme burn risk in 5–10 minutes."),
    ]
    for idx_range, name, desc in who_items:
        r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_r = Gtk.Label(label=idx_range)
        lbl_r.add_css_class("weather-item-bold")
        lbl_r.set_size_request(46, -1)
        lbl_r.set_xalign(0.0)
        r.append(lbl_r)

        lbl_n = Gtk.Label(label=f"{name} — {desc}")
        lbl_n.add_css_class("weather-body-text")
        lbl_n.set_wrap(True)
        lbl_n.set_hexpand(True)
        lbl_n.set_xalign(0.0)
        r.append(lbl_n)
        who_card.append(r)

    box.append(who_card)
    sheet.mode_stack.add_named(box, "uv")
    return box
