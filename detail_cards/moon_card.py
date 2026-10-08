"""
Карточка луны: 3D сфера фазы, интерактивная шкала времени и лунный календарь на месяц.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from data.wmo_conditions import WEEKDAY_LETTERS, get_weekday_name
from i18n import get_current_language, t
from weather_atmosphere import MoonSphereArea

logger = logging.getLogger(__name__)


class MoonTimelineRuler(Gtk.DrawingArea):
    """Горизонтальная линейка времени с делениями по часам и дням и центральным указателем."""

    def __init__(self, on_change_callback=None):
        super().__init__()
        self.on_change_callback = on_change_callback
        self.center_offset_hours = 0.0
        self.min_offset_hours = -30 * 24.0
        self.max_offset_hours = +30 * 24.0
        self.pixels_per_hour = 4.0

        self.base_dt = datetime.now()

        self.set_content_height(66)
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

        self.scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        self.scroll.connect("scroll", self._on_scroll)
        self.add_controller(self.scroll)

        self._drag_start_offset = 0.0

    def set_base_datetime(self, dt: datetime):
        self.base_dt = dt
        self.queue_draw()

    def set_offset_hours(self, offset: float, trigger_callback: bool = True):
        self.center_offset_hours = max(self.min_offset_hours, min(self.max_offset_hours, offset))
        self.queue_draw()
        if trigger_callback and self.on_change_callback:
            target_dt = self.base_dt + timedelta(hours=self.center_offset_hours)
            self.on_change_callback(self.center_offset_hours, target_dt)

    def reset_to_now(self):
        self.set_offset_hours(0.0, trigger_callback=True)

    def _on_drag_begin(self, gesture, start_x, start_y):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self._drag_start_offset = self.center_offset_hours

    def _on_drag_update(self, gesture, offset_x, offset_y):
        new_offset = self._drag_start_offset - (offset_x / self.pixels_per_hour)
        self.set_offset_hours(new_offset, trigger_callback=True)

    def _on_drag_end(self, gesture, offset_x, offset_y):
        pass

    def _on_scroll(self, controller, dx, dy):
        delta = (dx if abs(dx) > abs(dy) else dy) * 1.5
        new_offset = self.center_offset_hours + delta
        self.set_offset_hours(new_offset, trigger_callback=True)
        return True

    def _draw(self, area, cr, width, height, user_data):
        cx = width / 2.0
        hours_half = (width / 2.0) / self.pixels_per_hour + 2.0

        center_h_floor = math.floor(self.center_offset_hours)
        h_start = int(center_h_floor - hours_half)
        h_end = int(center_h_floor + hours_half)

        cur_lang = get_current_language()

        for h in range(h_start, h_end + 1):
            x = cx + (h - self.center_offset_hours) * self.pixels_per_hour
            tick_dt = self.base_dt + timedelta(hours=h)
            hour_of_day = tick_dt.hour

            if hour_of_day == 12:
                diff_days = (tick_dt.date() - self.base_dt.date()).days
                if diff_days == 0:
                    lbl = t("weather_today_label")
                    is_today = True
                elif diff_days == -1:
                    lbl = t("weather_yesterday_upper")
                    is_today = False
                elif diff_days == 1:
                    lbl = t("weather_tomorrow_upper")
                    is_today = False
                else:
                    d_name = get_weekday_name(tick_dt.weekday(), lang=cur_lang).upper()
                    lbl = f"{d_name} {tick_dt.day}"
                    is_today = False

                cr.save()
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if is_today else cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(10.0 if is_today else 9.0)
                if is_today:
                    cr.set_source_rgba(0.4, 0.8, 1.0, 0.95)
                else:
                    cr.set_source_rgba(0.85, 0.88, 0.95, 0.65)

                extents = cr.text_extents(lbl)
                cr.move_to(x - extents.width / 2.0, height - 26)
                cr.show_text(lbl)
                cr.restore()

                cr.set_source_rgba(1.0, 1.0, 1.0, 0.75)
                cr.set_line_width(1.5)
                cr.move_to(x, height - 18)
                cr.line_to(x, height - 4)
                cr.stroke()
            elif hour_of_day == 0:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.4)
                cr.set_line_width(1.2)
                cr.move_to(x, height - 14)
                cr.line_to(x, height - 4)
                cr.stroke()
            elif hour_of_day % 4 == 0:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.25)
                cr.set_line_width(1.0)
                cr.move_to(x, height - 10)
                cr.line_to(x, height - 4)
                cr.stroke()
            elif hour_of_day % 2 == 0:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.12)
                cr.set_line_width(1.0)
                cr.move_to(x, height - 6)
                cr.line_to(x, height - 4)
                cr.stroke()

        cr.save()
        cr.set_source_rgba(0.4, 0.8, 1.0, 0.35)
        cr.set_line_width(1.0)
        cr.move_to(cx, 14)
        cr.line_to(cx, height - 2)
        cr.stroke()

        cr.set_source_rgba(0.4, 0.8, 1.0, 0.95)
        cr.move_to(cx - 5.0, 2.0)
        cr.line_to(cx + 5.0, 2.0)
        cr.line_to(cx, 8.5)
        cr.close_path()
        cr.fill()
        cr.restore()


class MiniMoonIcon(Gtk.DrawingArea):
    """Мини-иконка фазы луны 18x18 для ячейки календаря."""

    def __init__(self, cycle_fraction: float):
        super().__init__()
        self.cycle_fraction = cycle_fraction % 1.0
        self.set_content_width(18)
        self.set_content_height(18)
        self.set_draw_func(self._draw, None)

    def _draw(self, area, cr, width, height, user_data):
        cx = width / 2.0
        cy = height / 2.0
        r = 6.5
        f = self.cycle_fraction

        cr.set_source_rgba(0.25, 0.28, 0.35, 0.85)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()

        illum = 0.5 * (1.0 - math.cos(2 * math.pi * f))
        if illum > 0.02:
            cr.save()
            cr.translate(cx, cy)
            cr.new_path()
            if illum >= 0.98:
                cr.arc(0, 0, r, 0, 2 * math.pi)
            elif f <= 0.5:
                cr.arc(0, 0, r, -math.pi / 2.0, math.pi / 2.0)
                steps = 16
                for i in range(steps + 1):
                    theta = (math.pi / 2.0) - (math.pi * i / steps)
                    x = r * math.cos(2 * math.pi * f) * math.cos(theta)
                    y = r * math.sin(theta)
                    cr.line_to(x, y)
                cr.close_path()
            else:
                cr.arc(0, 0, r, math.pi / 2.0, 3 * math.pi / 2.0)
                steps = 16
                for i in range(steps + 1):
                    theta = (-math.pi / 2.0) + (math.pi * i / steps)
                    x = -r * math.cos(2 * math.pi * f) * math.cos(theta)
                    y = r * math.sin(theta)
                    cr.line_to(x, y)
                cr.close_path()

            cr.set_source_rgba(0.92, 0.95, 1.0, 0.95)
            cr.fill()
            cr.restore()


class MoonCalendarCard(Gtk.Box):
    """Интерактивный календарь фаз луны на месяц с ключевыми датами."""

    def __init__(self, lat: float = 53.7557, lon: float = 87.1099, utc_offset_hours: float = 0.0, on_day_selected_callback=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.lat = lat
        self.lon = lon
        self.utc_offset_hours = utc_offset_hours
        self.on_day_selected_callback = on_day_selected_callback
        self.add_css_class("weather-glass-card")
        self.set_margin_top(4)

        now = datetime.now()
        self.year = now.year
        self.month = now.month
        self.selected_day = now.day

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hdr.set_margin_start(4)
        hdr.set_margin_end(4)
        hdr.set_margin_top(4)

        self.btn_prev = Gtk.Button()
        self.btn_prev.add_css_class("weather-cal-nav-btn")
        prev_icon = Gtk.Image.new_from_icon_name("go-previous-symbolic")
        prev_icon.set_pixel_size(12)
        self.btn_prev.set_child(prev_icon)
        self.btn_prev.connect("clicked", lambda b: self._change_month(-1))
        hdr.append(self.btn_prev)

        self.lbl_month_title = Gtk.Label(label="")
        self.lbl_month_title.add_css_class("weather-cal-title")
        self.lbl_month_title.set_hexpand(True)
        hdr.append(self.lbl_month_title)

        self.btn_next = Gtk.Button()
        self.btn_next.add_css_class("weather-cal-nav-btn")
        next_icon = Gtk.Image.new_from_icon_name("go-next-symbolic")
        next_icon.set_pixel_size(12)
        self.btn_next.set_child(next_icon)
        self.btn_next.connect("clicked", lambda b: self._change_month(1))
        hdr.append(self.btn_next)

        self.append(hdr)

        wd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        wd_box.set_homogeneous(True)
        cur_lang = get_current_language()
        w_labels = WEEKDAY_LETTERS.get(cur_lang, WEEKDAY_LETTERS["en"])
        for w_txt in w_labels:
            lbl_w = Gtk.Label(label=w_txt)
            lbl_w.add_css_class("weather-cal-weekday")
            wd_box.append(lbl_w)
        self.append(wd_box)

        self.grid_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.append(self.grid_container)

        div = Gtk.Box()
        div.add_css_class("weather-card-divider")
        div.set_margin_top(6)
        self.append(div)

        placeholder = "\u2014"
        self.lbl_new_moon_row = self._create_key_row(t("weather_next_new_moon"), placeholder)
        self.append(self.lbl_new_moon_row)

        div2 = Gtk.Box()
        div2.add_css_class("weather-card-divider")
        self.append(div2)

        self.lbl_full_moon_row = self._create_key_row(t("weather_full_moon"), placeholder)
        self.append(self.lbl_full_moon_row)

        self._refresh_calendar()

    def _create_key_row(self, title: str, val: str):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_margin_start(12)
        row.set_margin_end(12)
        row.set_margin_top(6)
        row.set_margin_bottom(6)
        lbl_t = Gtk.Label(label=title)
        lbl_t.add_css_class("weather-sun-row-title")
        lbl_t.set_xalign(0.0)
        lbl_t.set_hexpand(True)
        row.append(lbl_t)

        lbl_v = Gtk.Label(label=val)
        lbl_v.add_css_class("weather-sun-row-value")
        lbl_v.set_xalign(1.0)
        row.append(lbl_v)
        row._lbl_val = lbl_v
        return row

    def _change_month(self, delta: int):
        m = self.month + delta
        y = self.year
        if m < 1:
            m = 12
            y -= 1
        elif m > 12:
            m = 1
            y += 1
        self.year = y
        self.month = m
        self._refresh_calendar()

    def update_location(self, lat: float, lon: float, utc_offset_hours: float):
        self.lat = lat
        self.lon = lon
        self.utc_offset_hours = utc_offset_hours
        self._refresh_calendar()

    def set_selected_day(self, day: int):
        self.selected_day = day
        self._refresh_calendar()

    def _refresh_calendar(self):
        from providers.weather import calculate_detailed_moon, calculate_month_moon_calendar
        cur_lang = get_current_language()
        cal_data = calculate_month_moon_calendar(self.year, self.month, lang=cur_lang)
        self.lbl_month_title.set_label(cal_data["title"])

        while child := self.grid_container.get_first_child():
            self.grid_container.remove(child)

        days = cal_data["days"]
        first_w = cal_data["first_weekday"]

        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        row_box.set_homogeneous(True)
        self.grid_container.append(row_box)

        for _ in range(first_w):
            empty_cell = Gtk.Box()
            empty_cell.set_size_request(36, 42)
            row_box.append(empty_cell)

        cur_col = first_w
        for day_info in days:
            d_num = day_info["day"]
            cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            cell.set_valign(Gtk.Align.CENTER)
            cell.set_halign(Gtk.Align.CENTER)
            cell.set_size_request(38, 42)
            cell.add_css_class("weather-cal-cell")

            is_sel = (d_num == self.selected_day)
            if is_sel:
                cell.add_css_class("weather-cal-cell-selected")

            lbl_d = Gtk.Label(label=str(d_num))
            lbl_d.add_css_class("weather-cal-cell-num")
            cell.append(lbl_d)

            icon = MiniMoonIcon(day_info["cycle_fraction"])
            cell.append(icon)

            click = Gtk.GestureClick.new()
            click.connect("released", lambda g, n, x, y, d=d_num: self._on_cell_clicked(d))
            cell.add_controller(click)

            row_box.append(cell)
            cur_col += 1
            if cur_col == 7:
                cur_col = 0
                row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
                row_box.set_homogeneous(True)
                self.grid_container.append(row_box)

        if cur_col > 0:
            for _ in range(7 - cur_col):
                empty_cell = Gtk.Box()
                empty_cell.set_size_request(36, 42)
                row_box.append(empty_cell)

        detailed_mid = calculate_detailed_moon(self.lat, self.lon, datetime(self.year, self.month, 15), self.utc_offset_hours, lang=cur_lang)
        self.lbl_new_moon_row._lbl_val.set_label(detailed_mid["next_new_moon_date_str"])
        self.lbl_full_moon_row._lbl_val.set_label(detailed_mid["next_full_moon_date_str"])

    def _on_cell_clicked(self, day: int):
        self.selected_day = day
        self._refresh_calendar()
        if self.on_day_selected_callback:
            self.on_day_selected_callback(self.year, self.month, day)


def create_moon_metric_row(title: str, value: str):
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.add_css_class("weather-moon-metric-row")
    row.set_hexpand(True)

    lbl_t = Gtk.Label(label=title)
    lbl_t.add_css_class("weather-moon-metric-label")
    lbl_t.set_xalign(0.0)
    lbl_t.set_hexpand(True)
    row.append(lbl_t)

    lbl_v = Gtk.Label(label=value)
    lbl_v.add_css_class("weather-moon-metric-val")
    lbl_v.set_xalign(1.0)
    row.append(lbl_v)
    return row, lbl_v


def build_moon_view(sheet):
    """Построение карточки луны и подключение к WeatherDetailSheet."""
    sheet.moon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    sheet.moon_box.set_valign(Gtk.Align.START)

    # 1. 3D сфера луны
    sheet.moon_sphere = MoonSphereArea(size=230)
    sheet.moon_box.append(sheet.moon_sphere)

    # 2. Интерактивная шкала времени
    ruler_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    ruler_card.add_css_class("weather-glass-card")
    ruler_card.add_css_class("weather-moon-ruler-card")

    sheet.moon_ruler = MoonTimelineRuler(on_change_callback=sheet._on_moon_ruler_scrub)
    ruler_card.append(sheet.moon_ruler)
    sheet.moon_box.append(ruler_card)

    # 3. Карточка метрик
    metrics_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    metrics_card.add_css_class("weather-glass-card")
    metrics_card.set_margin_top(4)

    placeholder_time = "\u2014:\u2014"
    placeholder_val = "\u2014"

    sheet.row_m_illum, sheet.lbl_m_illum_val = create_moon_metric_row(
        t("weather_moon_illumination"), "0%"
    )
    metrics_card.append(sheet.row_m_illum)
    div1 = Gtk.Box()
    div1.add_css_class("weather-card-divider")
    metrics_card.append(div1)

    sheet.row_m_rise, sheet.lbl_m_rise_val = create_moon_metric_row(
        t("weather_moonrise"), placeholder_time
    )
    metrics_card.append(sheet.row_m_rise)
    div2 = Gtk.Box()
    div2.add_css_class("weather-card-divider")
    metrics_card.append(div2)

    sheet.row_m_set, sheet.lbl_m_set_val = create_moon_metric_row(
        t("weather_moonset"), placeholder_time
    )
    metrics_card.append(sheet.row_m_set)
    div3 = Gtk.Box()
    div3.add_css_class("weather-card-divider")
    metrics_card.append(div3)

    sheet.row_m_full, sheet.lbl_m_full_val = create_moon_metric_row(
        t("weather_next_full_moon"), placeholder_val
    )
    metrics_card.append(sheet.row_m_full)
    div4 = Gtk.Box()
    div4.add_css_class("weather-card-divider")
    metrics_card.append(div4)

    sheet.row_m_dist, sheet.lbl_m_dist_val = create_moon_metric_row(
        t("weather_moon_distance"), placeholder_val
    )
    metrics_card.append(sheet.row_m_dist)

    sheet.moon_box.append(metrics_card)

    # 4. Лунный календарь
    lat = sheet.data.get("lat", 53.7557)
    lon = sheet.data.get("lon", 87.1099)
    utc_off = sheet.data.get("utc_offset_seconds", 0) / 3600.0
    sheet.moon_calendar = MoonCalendarCard(
        lat=lat,
        lon=lon,
        utc_offset_hours=utc_off,
        on_day_selected_callback=sheet._on_moon_calendar_day_selected
    )
    sheet.moon_box.append(sheet.moon_calendar)

    sheet.mode_stack.add_named(sheet.moon_box, "moon")
