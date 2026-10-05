"""
Карточка климатических норм: графики сопоставления с 30-летней нормой ВМО и таблицы температур и осадков по месяцам.
"""

from __future__ import annotations

import logging
import math

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from i18n import get_current_language

logger = logging.getLogger(__name__)


class TempCapsuleBarArea(Gtk.DrawingArea):
    """Горизонтальная полоска-капсула диапазона температур месяца."""

    def __init__(self, t_min: float, t_max: float, global_min: float, global_max: float, current_temp: float = None):
        super().__init__()
        self.set_content_height(14)
        self.set_hexpand(True)
        self.t_min = t_min
        self.t_max = t_max
        self.global_min = global_min
        self.global_max = global_max
        self.current_temp = current_temp
        self.set_draw_func(self._on_draw)

    def update_data(self, t_min: float, t_max: float, global_min: float, global_max: float, current_temp: float = None):
        self.t_min = t_min
        self.t_max = t_max
        self.global_min = global_min
        self.global_max = global_max
        self.current_temp = current_temp
        self.queue_draw()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        pad_x = 2.0
        w = max(10.0, width - 2 * pad_x)
        span = max(5.0, self.global_max - self.global_min)

        r0 = max(0.0, min(1.0, (self.t_min - self.global_min) / span))
        r1 = max(0.0, min(1.0, (self.t_max - self.global_min) / span))

        bx1 = pad_x + r0 * w
        bx2 = pad_x + r1 * w
        bw = max(8.0, bx2 - bx1)
        bh = 5.0
        by = (height - bh) / 2.0

        cr.save()

        # 1. Subtle horizontal guide track
        track_h = 3.0
        track_y = (height - track_h) / 2.0
        cr.new_sub_path()
        cr.rectangle(pad_x, track_y, w, track_h)
        cr.set_source_rgba(1, 1, 1, 0.12)
        cr.fill()

        # 2. Precision range bar with micro-chamfer
        bar_r = 1.5
        cr.new_sub_path()
        cr.arc(bx1 + bar_r, by + bar_r, bar_r, math.pi, 1.5 * math.pi)
        cr.arc(bx1 + bw - bar_r, by + bar_r, bar_r, 1.5 * math.pi, 2 * math.pi)
        cr.arc(bx1 + bw - bar_r, by + bh - bar_r, bar_r, 0, 0.5 * math.pi)
        cr.arc(bx1 + bar_r, by + bh - bar_r, bar_r, 0.5 * math.pi, math.pi)
        cr.close_path()

        pat = cairo.LinearGradient(bx1, by, bx1 + bw, by)
        if self.t_max <= -5:
            pat.add_color_stop_rgba(0.0, 0.15, 0.45, 0.95, 0.95)
            pat.add_color_stop_rgba(1.0, 0.20, 0.65, 0.95, 0.95)
        elif self.t_max <= 5:
            pat.add_color_stop_rgba(0.0, 0.20, 0.65, 0.95, 0.95)
            pat.add_color_stop_rgba(1.0, 0.20, 0.85, 0.70, 0.95)
        elif self.t_max <= 18:
            pat.add_color_stop_rgba(0.0, 0.20, 0.85, 0.70, 0.95)
            pat.add_color_stop_rgba(1.0, 0.35, 0.90, 0.55, 0.95)
        elif self.t_max <= 24:
            pat.add_color_stop_rgba(0.0, 0.35, 0.90, 0.55, 0.95)
            pat.add_color_stop_rgba(1.0, 0.98, 0.75, 0.15, 0.95)
        else:
            pat.add_color_stop_rgba(0.0, 0.98, 0.75, 0.15, 0.95)
            pat.add_color_stop_rgba(1.0, 0.98, 0.35, 0.25, 0.95)

        cr.set_source(pat)
        cr.fill()

        # 3. Precision tick marks at min and max bounds
        tick_h = 7.0
        tick_y = (height - tick_h) / 2.0
        cr.set_line_width(1.2)
        cr.set_source_rgba(1, 1, 1, 0.45)
        cr.move_to(bx1, tick_y)
        cr.line_to(bx1, tick_y + tick_h)
        cr.move_to(bx1 + bw, tick_y)
        cr.line_to(bx1 + bw, tick_y + tick_h)
        cr.stroke()

        # 4. Current temperature precision needle indicator
        if self.current_temp is not None:
            r_cur = max(0.0, min(1.0, (self.current_temp - self.global_min) / span))
            needle_x = pad_x + r_cur * w
            needle_h = 10.0
            needle_y = (height - needle_h) / 2.0

            # Subtle glow behind needle
            cr.set_line_width(3.2)
            cr.set_source_rgba(0, 0, 0, 0.35)
            cr.move_to(needle_x, needle_y)
            cr.line_to(needle_x, needle_y + needle_h)
            cr.stroke()

            # Crisp white needle
            cr.set_line_width(2.0)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.move_to(needle_x, needle_y)
            cr.line_to(needle_x, needle_y + needle_h)
            cr.stroke()

        cr.restore()


class PrecipCapsuleBarArea(Gtk.DrawingArea):
    """Горизонтальная полоска объема осадков относительно годового максимума."""

    def __init__(self, val_mm: float, max_annual_mm: float):
        super().__init__()
        self.set_content_height(14)
        self.set_hexpand(True)
        self.val_mm = val_mm
        self.max_annual_mm = max_annual_mm
        self.set_draw_func(self._on_draw)

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        pad_x = 2.0
        w = max(10.0, width - 2 * pad_x)
        span = max(10.0, self.max_annual_mm)
        ratio = max(0.02, min(1.0, self.val_mm / span))

        bh = 7.0
        by = (height - bh) / 2.0
        bw = max(bh, ratio * w)

        cr.save()
        cr.new_sub_path()
        r = bh / 2.0
        cr.arc(pad_x + r, by + r, r, math.pi, 1.5 * math.pi)
        cr.arc(pad_x + w - r, by + r, r, 1.5 * math.pi, 2 * math.pi)
        cr.arc(pad_x + w - r, by + bh - r, r, 0, 0.5 * math.pi)
        cr.arc(pad_x + r, by + bh - r, r, 0.5 * math.pi, math.pi)
        cr.close_path()
        cr.set_source_rgba(1, 1, 1, 0.08)
        cr.fill()

        cr.new_sub_path()
        cr.arc(pad_x + r, by + r, r, math.pi, 1.5 * math.pi)
        cr.arc(pad_x + bw - r, by + r, r, 1.5 * math.pi, 2 * math.pi)
        cr.arc(pad_x + bw - r, by + bh - r, r, 0, 0.5 * math.pi)
        cr.arc(pad_x + r, by + bh - r, r, 0.5 * math.pi, math.pi)
        cr.close_path()

        cr.set_source_rgba(0.22, 0.74, 0.98, 0.92)
        cr.fill()
        cr.restore()


class ClimateMonthlyTempTable(Gtk.Box):
    """Таблица среднемесячных температур года."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add_css_class("climate-monthly-table")

    def update_data(self, monthly_list, current_m_idx):
        while child := self.get_first_child():
            self.remove(child)

        if not monthly_list:
            return

        all_mins = [m["temp_min"] for m in monthly_list]
        all_maxs = [m["temp_max"] for m in monthly_list]
        g_min = min(all_mins) - 2.0
        g_max = max(all_maxs) + 2.0

        for idx, m in enumerate(monthly_list):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row.add_css_class("climate-month-row")
            is_cur = (idx == current_m_idx)
            if is_cur:
                row.add_css_class("climate-month-row-active")

            lbl_name = Gtk.Label(label=m["name"])
            lbl_name.add_css_class("climate-month-name")
            if is_cur:
                lbl_name.add_css_class("climate-month-name-active")
            lbl_name.set_xalign(0.0)
            lbl_name.set_size_request(44, -1)
            row.append(lbl_name)

            lbl_min = Gtk.Label(label=f"{m['temp_min']}°")
            lbl_min.add_css_class("climate-temp-min")
            lbl_min.set_xalign(1.0)
            lbl_min.set_size_request(32, -1)
            row.append(lbl_min)

            bar = TempCapsuleBarArea(m["temp_min"], m["temp_max"], g_min, g_max)
            row.append(bar)

            lbl_max = Gtk.Label(label=f"{m['temp_max']}°")
            lbl_max.add_css_class("climate-temp-max")
            if is_cur:
                lbl_max.add_css_class("climate-temp-max-active")
            lbl_max.set_xalign(0.0)
            lbl_max.set_size_request(32, -1)
            row.append(lbl_max)

            self.append(row)


class ClimateMonthlyPrecipTable(Gtk.Box):
    """Таблица среднемесячных объемов осадков года."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add_css_class("climate-monthly-table")

    def update_data(self, monthly_list, current_m_idx):
        while child := self.get_first_child():
            self.remove(child)

        if not monthly_list:
            return

        all_precips = [m["precip_mm"] for m in monthly_list]
        max_p = max(all_precips) if all_precips else 100.0

        for idx, m in enumerate(monthly_list):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row.add_css_class("climate-month-row")
            is_cur = (idx == current_m_idx)
            if is_cur:
                row.add_css_class("climate-month-row-active")

            lbl_name = Gtk.Label(label=m["name"])
            lbl_name.add_css_class("climate-month-name")
            if is_cur:
                lbl_name.add_css_class("climate-month-name-active")
            lbl_name.set_xalign(0.0)
            lbl_name.set_size_request(44, -1)
            row.append(lbl_name)

            bar = PrecipCapsuleBarArea(m["precip_mm"], max_p)
            row.append(bar)

            is_ru = (get_current_language() == "ru")
            lbl_val = Gtk.Label(label=f"{m['precip_mm']} мм" if is_ru else f"{m['precip_mm']} mm")
            lbl_val.add_css_class("climate-precip-val")
            if is_cur:
                lbl_val.add_css_class("climate-precip-val-active")
            lbl_val.set_xalign(1.0)
            lbl_val.set_size_request(54, -1)
            row.append(lbl_val)

            self.append(row)


class ClimateTempChartArea(Gtk.DrawingArea):
    """24-часовой график температуры по сравнению с 80% коридором климатической нормы."""

    def __init__(self):
        super().__init__()
        self.set_content_height(230)
        self.set_hexpand(True)
        self.hourly_temps = [20.0] * 24
        self.hourly_normal_band = [(10.0, 20.0)] * 24
        self.normal_p10 = 10.0
        self.normal_p90 = 24.0
        self.today_max = 28.0
        self.cur_hour = 12

        self.is_scrubbing = False
        self.scrub_hour_frac = None
        self.scrub_x = 0.0
        self.scrub_y = 0.0
        self.on_scrub = None

        self.set_draw_func(self._on_draw)
        self._setup_gestures()

    def _setup_gestures(self):
        self.drag_gesture = Gtk.GestureDrag.new()
        self.drag_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.drag_gesture.connect("drag-begin", self._on_drag_begin)
        self.drag_gesture.connect("drag-update", self._on_drag_update)
        self.drag_gesture.connect("drag-end", self._on_drag_end)
        self.drag_gesture.connect("cancel", self._on_drag_end)
        self.add_controller(self.drag_gesture)
        try:
            self.set_cursor_from_name("pointer")
        except (GLib.Error, TypeError) as e:
            logger.debug("Could not set pointer cursor: %s", e)

    def _on_drag_begin(self, gesture, start_x, start_y):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.is_scrubbing = True
        self._handle_interaction(start_x, start_y)

    def _on_drag_update(self, gesture, offset_x, offset_y):
        ok, start_x, start_y = gesture.get_start_point()
        if not ok:
            start_x, start_y = 0.0, 0.0
        self._handle_interaction(start_x + offset_x, start_y + offset_y)

    def _on_drag_end(self, gesture, offset_x=0.0, offset_y=0.0):
        self.is_scrubbing = False
        self.scrub_hour_frac = None
        self.queue_draw()
        if callable(self.on_scrub):
            self.on_scrub(None, None, None, None)

    def _handle_interaction(self, x, y):
        pad_l = 16.0
        pad_r = 44.0
        w = max(10.0, self.get_width() - pad_l - pad_r)
        clamped_x = max(pad_l, min(self.get_width() - pad_r, x))
        frac = (clamped_x - pad_l) / w
        hour_frac = max(0.0, min(23.0, frac * 23.0))

        self.is_scrubbing = True
        self.scrub_hour_frac = hour_frac
        self.scrub_x = clamped_x
        self.scrub_y = y
        self.queue_draw()

        h_idx = int(round(hour_frac))
        h_idx = max(0, min(23, h_idx))
        cur_t = self.hourly_temps[h_idx] if h_idx < len(self.hourly_temps) else self.today_max
        band = self.hourly_normal_band[h_idx] if h_idx < len(self.hourly_normal_band) else (self.normal_p10, self.normal_p90)
        if callable(self.on_scrub):
            self.on_scrub(h_idx, cur_t, band[0], band[1])

    def update_data(self, hourly_temps, p10, p90, normal_band, today_max, cur_hour=12):
        self.hourly_temps = hourly_temps if len(hourly_temps) >= 24 else ([20.0] * 24)
        self.normal_p10 = float(p10)
        self.normal_p90 = float(p90)
        self.hourly_normal_band = normal_band if len(normal_band) >= 24 else ([(p10, p90)] * 24)
        self.today_max = float(today_max)
        self.cur_hour = cur_hour
        self.queue_draw()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        pad_l = 16.0
        pad_r = 44.0
        pad_t = 50.0
        pad_b = 42.0

        plot_w = max(20.0, width - pad_l - pad_r)
        plot_h = max(20.0, height - pad_t - pad_b)

        all_vals = list(self.hourly_temps) + [self.normal_p10, self.normal_p90, self.today_max]
        for b in self.hourly_normal_band:
            all_vals.extend(b)
        v_min = min(all_vals)
        v_max = max(all_vals)

        y_min = math.floor(v_min / 3.0) * 3.0 - 3.0
        y_max = math.ceil(v_max / 3.0) * 3.0 + 3.0
        if y_max - y_min < 12.0:
            y_max = y_min + 12.0

        def to_xy(h_idx: float, val: float):
            x = pad_l + (h_idx / 23.0) * plot_w
            ratio = (val - y_min) / float(y_max - y_min)
            y = pad_t + plot_h - ratio * plot_h
            return x, y

        cr.select_font_face("Inter, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9.5)

        step = 3.0 if (y_max - y_min) <= 24.0 else (6.0 if (y_max - y_min) <= 45.0 else 10.0)
        t_val = math.ceil(y_min / step) * step
        while t_val <= y_max:
            _, gy = to_xy(0, t_val)
            if pad_t <= gy <= pad_t + plot_h:
                cr.set_line_width(0.6)
                cr.set_source_rgba(1, 1, 1, 0.08)
                cr.move_to(pad_l, gy)
                cr.line_to(pad_l + plot_w, gy)
                cr.stroke()

                cr.set_source_rgba(1, 1, 1, 0.45)
                lbl_txt = f"{int(round(t_val))}°"
                cr.move_to(pad_l + plot_w + 6, gy + 3.5)
                cr.show_text(lbl_txt)
            t_val += step

        hour_marks = [0, 6, 12, 18]
        cr.set_line_width(0.6)
        cr.set_dash([2.0, 3.0])
        cr.set_source_rgba(1, 1, 1, 0.12)
        for hm in hour_marks:
            hx, _ = to_xy(hm, y_min)
            cr.move_to(hx, pad_t)
            cr.line_to(hx, pad_t + plot_h)
            cr.stroke()
        cr.set_dash([])

        cr.set_source_rgba(1, 1, 1, 0.50)
        cr.set_font_size(10.0)
        for hm in hour_marks:
            hx, _ = to_xy(hm, y_min)
            txt = f"{hm:02d}"
            ext = cr.text_extents(txt)
            cr.move_to(hx - ext.width / 2.0, height - 26)
            cr.show_text(txt)

        pts_up = [to_xy(h, self.hourly_normal_band[h][1]) for h in range(24)]
        pts_dn = [to_xy(h, self.hourly_normal_band[h][0]) for h in range(24)]

        cr.save()
        cr.move_to(pts_up[0][0], pts_up[0][1])
        for i in range(len(pts_up) - 1):
            p0 = pts_up[max(0, i - 1)]
            p1 = pts_up[i]
            p2 = pts_up[i + 1]
            p3 = pts_up[min(len(pts_up) - 1, i + 2)]
            cr.curve_to(p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0,
                        p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0,
                        p2[0], p2[1])
        cr.line_to(pts_dn[-1][0], pts_dn[-1][1])
        for i in range(len(pts_dn) - 1, 0, -1):
            p0 = pts_dn[min(len(pts_dn) - 1, i + 1)]
            p1 = pts_dn[i]
            p2 = pts_dn[i - 1]
            p3 = pts_dn[max(0, i - 2)]
            cr.curve_to(p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0,
                        p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0,
                        p2[0], p2[1])
        cr.close_path()

        pat = cairo.LinearGradient(0, pad_t, 0, pad_t + plot_h)
        pat.add_color_stop_rgba(0.0, 0.22, 0.65, 0.58, 0.45)
        pat.add_color_stop_rgba(0.5, 0.18, 0.52, 0.48, 0.32)
        pat.add_color_stop_rgba(1.0, 0.12, 0.38, 0.38, 0.18)
        cr.set_source(pat)
        cr.fill_preserve()

        cr.set_line_width(1.0)
        cr.set_source_rgba(0.35, 0.78, 0.72, 0.45)
        cr.stroke()
        cr.restore()

        pts_today = [to_xy(h, self.hourly_temps[h]) for h in range(24)]
        cr.save()
        cr.move_to(pts_today[0][0], pts_today[0][1])
        for i in range(len(pts_today) - 1):
            p0 = pts_today[max(0, i - 1)]
            p1 = pts_today[i]
            p2 = pts_today[i + 1]
            p3 = pts_today[min(len(pts_today) - 1, i + 2)]
            cr.curve_to(p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0,
                        p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0,
                        p2[0], p2[1])
        cr.set_line_width(3.0)
        cr.set_source_rgba(1.0, 0.82, 0.12, 0.98)
        cr.stroke()
        cr.restore()

        max_h = max(range(len(self.hourly_temps)), key=lambda idx: self.hourly_temps[idx])
        mx_x, mx_y = pts_today[max_h]
        cr.arc(mx_x, mx_y, 7.5, 0, 2 * math.pi)
        cr.set_source_rgba(1.0, 0.82, 0.12, 0.35)
        cr.fill()
        cr.arc(mx_x, mx_y, 4.5, 0, 2 * math.pi)
        cr.set_source_rgba(1.0, 0.82, 0.12, 1.0)
        cr.fill()

        cr.save()
        if self.is_scrubbing and self.scrub_hour_frac is not None:
            scrub_h = int(round(self.scrub_hour_frac))
            scrub_h = max(0, min(23, scrub_h))
            t_val = self.hourly_temps[scrub_h]
            sub_title = f"{scrub_h:02d}:00"
            main_title = f"{int(round(t_val))}°"
        else:
            is_ru = (get_current_language() == "ru")
            sub_title = "Макс. сегодня" if is_ru else "Today's Max"
            main_title = f"{int(round(self.today_max))}°"

        cr.set_source_rgba(1, 1, 1, 0.70)
        cr.set_font_size(11.0)
        cr.move_to(pad_l + 2, pad_t - 24)
        cr.show_text(sub_title)

        cr.set_source_rgba(1, 1, 1, 0.98)
        cr.select_font_face("Inter, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(24.0)
        cr.move_to(pad_l + 2, pad_t - 4)
        cr.show_text(main_title)
        cr.restore()

        if self.is_scrubbing and self.scrub_hour_frac is not None:
            sx = self.scrub_x
            sh = int(round(self.scrub_hour_frac))
            sh = max(0, min(23, sh))
            sy = pts_today[sh][1]

            cr.save()
            cr.set_line_width(1.5)
            cr.set_source_rgba(1, 1, 1, 0.90)
            cr.move_to(sx, pad_t)
            cr.line_to(sx, pad_t + plot_h)
            cr.stroke()

            cr.arc(sx, sy, 8.5, 0, 2 * math.pi)
            cr.set_source_rgba(1, 1, 1, 0.35)
            cr.fill()

            cr.arc(sx, sy, 5.0, 0, 2 * math.pi)
            cr.set_source_rgba(1, 1, 1, 1.0)
            cr.fill()
            cr.restore()

        cr.save()
        leg_y = height - 8
        cr.select_font_face("Inter, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10.5)

        cr.arc(pad_l + 6, leg_y - 3.5, 4.5, 0, 2 * math.pi)
        cr.set_source_rgba(1.0, 0.82, 0.12, 1.0)
        cr.fill()

        cr.set_source_rgba(1, 1, 1, 0.85)
        cr.move_to(pad_l + 16, leg_y)
        cr.show_text("Сегодня")

        leg_x2 = pad_l + 100.0
        cr.arc(leg_x2 + 6, leg_y - 3.5, 4.5, 0, 2 * math.pi)
        cr.set_source_rgba(0.28, 0.72, 0.65, 1.0)
        cr.fill()

        cr.set_source_rgba(1, 1, 1, 0.85)
        cr.move_to(leg_x2 + 16, leg_y)
        cr.show_text(f"Норма (от {int(round(self.normal_p10))}° до {int(round(self.normal_p90))}°)")
        cr.restore()


class ClimatePrecipChartArea(Gtk.DrawingArea):
    """30-дневный накопительный график осадков против климатической нормы."""

    def __init__(self):
        super().__init__()
        self.set_content_height(230)
        self.set_hexpand(True)
        self.precip_series = [0.0] * 31
        self.avg_30d_total = 65.0
        self.actual_30d_total = 89.0
        self.dates_30d = []

        self.is_scrubbing = False
        self.scrub_day_frac = None
        self.scrub_x = 0.0
        self.on_scrub = None

        self.set_draw_func(self._on_draw)
        self._setup_gestures()

    def _setup_gestures(self):
        self.drag_gesture = Gtk.GestureDrag.new()
        self.drag_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.drag_gesture.connect("drag-begin", self._on_drag_begin)
        self.drag_gesture.connect("drag-update", self._on_drag_update)
        self.drag_gesture.connect("drag-end", self._on_drag_end)
        self.drag_gesture.connect("cancel", self._on_drag_end)
        self.add_controller(self.drag_gesture)
        try:
            self.set_cursor_from_name("pointer")
        except (GLib.Error, TypeError) as e:
            logger.debug("Could not set pointer cursor: %s", e)

    def _on_drag_begin(self, gesture, start_x, start_y):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.is_scrubbing = True
        self._handle_interaction(start_x)

    def _on_drag_update(self, gesture, offset_x, offset_y):
        ok, start_x, _ = gesture.get_start_point()
        if not ok:
            start_x = 0.0
        self._handle_interaction(start_x + offset_x)

    def _on_drag_end(self, gesture, offset_x=0.0, offset_y=0.0):
        self.is_scrubbing = False
        self.scrub_day_frac = None
        self.queue_draw()
        if callable(self.on_scrub):
            self.on_scrub(None, None, None)

    def _handle_interaction(self, x):
        pad_l = 16.0
        pad_r = 44.0
        w = max(10.0, self.get_width() - pad_l - pad_r)
        clamped_x = max(pad_l, min(self.get_width() - pad_r, x))
        frac = (clamped_x - pad_l) / w
        day_frac = max(0.0, min(30.0, frac * 30.0))

        self.is_scrubbing = True
        self.scrub_day_frac = day_frac
        self.scrub_x = clamped_x
        self.queue_draw()

        d_idx = int(round(day_frac))
        d_idx = max(0, min(len(self.precip_series) - 1, d_idx))
        cum_val = self.precip_series[d_idx]
        is_ru = (get_current_language() == "ru")
        d_str = self.dates_30d[d_idx] if d_idx < len(self.dates_30d) else (f"{30 - d_idx} дн назад" if is_ru else f"{30 - d_idx}d ago")
        if callable(self.on_scrub):
            self.on_scrub(d_idx, d_str, cum_val)

    def update_data(self, series, avg_30d, actual_30d, dates=None):
        self.precip_series = series if len(series) >= 2 else ([0.0] * 31)
        self.avg_30d_total = float(avg_30d)
        self.actual_30d_total = float(actual_30d)
        self.dates_30d = dates or []
        self.queue_draw()

    def _on_draw(self, area, cr: cairo.Context, width: int, height: int):
        pad_l = 16.0
        pad_r = 44.0
        pad_t = 50.0
        pad_b = 42.0

        plot_w = max(20.0, width - pad_l - pad_r)
        plot_h = max(20.0, height - pad_t - pad_b)

        max_p = max(self.avg_30d_total, self.actual_30d_total, max(self.precip_series) if self.precip_series else 10.0, 10.0)
        y_max = math.ceil(max_p / 25.0) * 25.0
        if y_max < 50.0:
            y_max = 50.0

        def to_xy(day_idx: float, val: float):
            total_days = max(1.0, float(len(self.precip_series) - 1))
            x = pad_l + (day_idx / total_days) * plot_w
            ratio = val / float(y_max)
            y = pad_t + plot_h - ratio * plot_h
            return x, y

        cr.select_font_face("Inter, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(9.5)

        step = 25.0 if y_max <= 150.0 else 50.0
        curr_y = 0.0
        while curr_y <= y_max + 0.1:
            _, gy = to_xy(0, curr_y)
            if pad_t - 5 <= gy <= pad_t + plot_h + 5:
                cr.set_line_width(0.6)
                cr.set_source_rgba(1, 1, 1, 0.08)
                cr.move_to(pad_l, gy)
                cr.line_to(pad_l + plot_w, gy)
                cr.stroke()

                cr.set_source_rgba(1, 1, 1, 0.45)
                lbl_txt = f"{int(round(curr_y))} мм" if curr_y == 0 else f"{int(round(curr_y))}"
                cr.move_to(pad_l + plot_w + 6, gy + 3.5)
                cr.show_text(lbl_txt)
            curr_y += step

        is_ru = (get_current_language() == "ru")
        cr.set_source_rgba(1, 1, 1, 0.55)
        cr.set_font_size(10.0)
        cr.move_to(pad_l, height - 26)
        cr.show_text("30 дн назад" if is_ru else "30d ago")

        today_lbl = "Сегодня" if is_ru else "Today"
        ext_today = cr.text_extents(today_lbl)
        cr.move_to(pad_l + plot_w - ext_today.width, height - 26)
        cr.show_text(today_lbl)

        cr.save()
        cr.set_line_width(1.8)
        cr.set_dash([4.0, 4.0])
        cr.set_source_rgba(1, 1, 1, 0.38)
        x0, y0 = to_xy(0, 0)
        x1, y1 = to_xy(len(self.precip_series) - 1, self.avg_30d_total)
        cr.move_to(x0, y0)
        cr.line_to(x1, y1)
        cr.stroke()
        cr.set_dash([])

        cr.arc(x1, y1, 3.5, 0, 2 * math.pi)
        cr.set_source_rgba(1, 1, 1, 0.50)
        cr.fill()
        cr.restore()

        pts = [to_xy(i, self.precip_series[i]) for i in range(len(self.precip_series))]
        if len(pts) >= 2:
            cr.save()
            cr.move_to(pts[0][0], pts[0][1])
            for i in range(len(pts) - 1):
                p0 = pts[max(0, i - 1)]
                p1 = pts[i]
                p2 = pts[i + 1]
                p3 = pts[min(len(pts) - 1, i + 2)]
                cr.curve_to(p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0,
                            p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0,
                            p2[0], p2[1])
            cr.set_line_width(2.8)
            cr.set_source_rgba(0.22, 0.74, 0.98, 0.98)
            cr.stroke()
            cr.restore()

            end_x, end_y = pts[-1]
            cr.arc(end_x, end_y, 7.5, 0, 2 * math.pi)
            cr.set_source_rgba(0.22, 0.74, 0.98, 0.35)
            cr.fill()
            cr.arc(end_x, end_y, 4.5, 0, 2 * math.pi)
            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.fill()

        cr.save()
        if self.is_scrubbing and self.scrub_day_frac is not None:
            scrub_d = int(round(self.scrub_day_frac))
            scrub_d = max(0, min(len(self.precip_series) - 1, scrub_d))
            cum_val = self.precip_series[scrub_d]
            sub_title = self.dates_30d[scrub_d] if scrub_d < len(self.dates_30d) else (f"{30 - scrub_d} дн назад" if is_ru else f"{30 - scrub_d}d ago")
            main_title = f"{cum_val:.1f} мм" if is_ru else f"{cum_val:.1f} mm"

            cr.set_source_rgba(1, 1, 1, 0.70)
            cr.set_font_size(11.0)
            cr.move_to(pad_l + 2, pad_t - 24)
            cr.show_text(sub_title)

            cr.set_source_rgba(1, 1, 1, 0.98)
            cr.select_font_face("Inter, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(24.0)
            cr.move_to(pad_l + 2, pad_t - 4)
            cr.show_text(main_title)
        else:
            cr.set_source_rgba(1, 1, 1, 0.65)
            cr.select_font_face("Inter, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(20.0)
            cr.move_to(pad_l + 2, pad_t - 10)
            mm_u = "мм" if is_ru else "mm"
            cr.show_text(f"{int(round(self.avg_30d_total))} {mm_u}")

            cr.set_source_rgba(1, 1, 1, 0.98)
            cr.set_font_size(26.0)
            ext_r = cr.text_extents(f"{int(round(self.actual_30d_total))} {mm_u}")
            cr.move_to(pad_l + plot_w - ext_r.width - 20, pad_t - 10)
            cr.show_text(f"{int(round(self.actual_30d_total))} {mm_u}")
        cr.restore()

        if self.is_scrubbing and self.scrub_day_frac is not None:
            sx = self.scrub_x
            sh = int(round(self.scrub_day_frac))
            sh = max(0, min(len(pts) - 1, sh))
            sy = pts[sh][1]

            cr.save()
            cr.set_line_width(1.5)
            cr.set_source_rgba(1, 1, 1, 0.90)
            cr.move_to(sx, pad_t)
            cr.line_to(sx, pad_t + plot_h)
            cr.stroke()

            cr.arc(sx, sy, 8.5, 0, 2 * math.pi)
            cr.set_source_rgba(0.22, 0.74, 0.98, 0.40)
            cr.fill()

            cr.arc(sx, sy, 5.0, 0, 2 * math.pi)
            cr.set_source_rgba(1, 1, 1, 1.0)
            cr.fill()
            cr.restore()

        cr.save()
        leg_y = height - 8
        cr.select_font_face("Inter, Roboto, Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10.5)

        cr.arc(pad_l + 6, leg_y - 3.5, 4.5, 0, 2 * math.pi)
        cr.set_source_rgba(0.22, 0.74, 0.98, 1.0)
        cr.fill()

        cr.set_source_rgba(1, 1, 1, 0.85)
        cr.move_to(pad_l + 16, leg_y)
        cr.show_text("Последние 30 дней")

        leg_x2 = pad_l + 140.0
        cr.arc(leg_x2 + 6, leg_y - 3.5, 4.5, 0, 2 * math.pi)
        cr.set_source_rgba(1, 1, 1, 0.50)
        cr.fill()

        cr.set_source_rgba(1, 1, 1, 0.85)
        cr.move_to(leg_x2 + 16, leg_y)
        cr.show_text("Среднее значение")
        cr.restore()


def build_averages_view(sheet):
    """Построение карточки климатических норм и подключение к WeatherDetailSheet."""
    is_ru = (get_current_language() == "ru")
    sheet.current_averages_subtab = "temp"

    sheet.averages_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    sheet.averages_box.set_valign(Gtk.Align.START)

    # 1. Переключатель Температура / Осадки
    seg_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    seg_box.add_css_class("segmented-control")
    seg_box.set_halign(Gtk.Align.CENTER)
    seg_box.set_margin_bottom(2)

    sheet.btn_avg_temp = Gtk.Button(label="Температура" if is_ru else "Temperature")
    sheet.btn_avg_temp.add_css_class("segmented-btn")
    sheet.btn_avg_temp.add_css_class("segmented-btn-active")
    sheet.btn_avg_temp.connect("clicked", lambda _: sheet._set_averages_subtab("temp"))
    seg_box.append(sheet.btn_avg_temp)

    sheet.btn_avg_precip = Gtk.Button(label="Осадки" if is_ru else "Precipitation")
    sheet.btn_avg_precip.add_css_class("segmented-btn")
    sheet.btn_avg_precip.connect("clicked", lambda _: sheet._set_averages_subtab("precip"))
    seg_box.append(sheet.btn_avg_precip)
    sheet.averages_box.append(seg_box)

    # 2. Стек подвкладок
    sheet.averages_stack = Gtk.Stack()
    sheet.averages_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
    sheet.averages_stack.set_transition_duration(280)
    sheet.averages_stack.set_interpolate_size(True)
    sheet.averages_stack.set_vhomogeneous(False)
    sheet.averages_stack.set_hhomogeneous(False)

    # Подвкладка: Температура
    sheet.avg_temp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

    hero_temp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    hero_temp_box.add_css_class("weather-averages-hero-box")
    sheet.lbl_avg_temp_hero = Gtk.Label(label="+0° > среднего" if is_ru else "+0° > average")
    sheet.lbl_avg_temp_hero.add_css_class("weather-averages-hero-title")
    sheet.lbl_avg_temp_hero.set_xalign(0.0)
    hero_temp_box.append(sheet.lbl_avg_temp_hero)

    placeholder_temp = "\u2014"
    sheet.lbl_avg_temp_sub = Gtk.Label(
        label=f"Средн. макс: {placeholder_temp}°" if is_ru else f"Avg high: {placeholder_temp}°"
    )
    sheet.lbl_avg_temp_sub.add_css_class("weather-averages-hero-sub")
    sheet.lbl_avg_temp_sub.set_xalign(0.0)
    hero_temp_box.append(sheet.lbl_avg_temp_sub)
    sheet.avg_temp_box.append(hero_temp_box)

    chart_temp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    chart_temp_card.add_css_class("weather-glass-card")
    sheet.climate_temp_chart = ClimateTempChartArea()
    chart_temp_card.append(sheet.climate_temp_chart)
    sheet.avg_temp_box.append(chart_temp_card)

    sum_temp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    sum_temp_card.add_css_class("weather-glass-card")
    lbl_sum_t_hdr = Gtk.Label(label="Сводка" if is_ru else "Summary")
    lbl_sum_t_hdr.add_css_class("weather-section-title")
    lbl_sum_t_hdr.set_xalign(0.0)
    sum_temp_card.append(lbl_sum_t_hdr)

    sheet.lbl_avg_temp_summary = Gtk.Label(label="")
    sheet.lbl_avg_temp_summary.add_css_class("weather-body-text")
    sheet.lbl_avg_temp_summary.set_wrap(True)
    sheet.lbl_avg_temp_summary.set_xalign(0.0)
    sum_temp_card.append(sheet.lbl_avg_temp_summary)
    sheet.avg_temp_box.append(sum_temp_card)

    month_temp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    month_temp_card.add_css_class("weather-glass-card")
    lbl_m_t_hdr = Gtk.Label(label="Среднее за месяц" if is_ru else "Monthly Averages")
    lbl_m_t_hdr.add_css_class("weather-section-title")
    lbl_m_t_hdr.set_xalign(0.0)
    month_temp_card.append(lbl_m_t_hdr)

    sheet.lbl_avg_temp_month_sub = Gtk.Label(label="")
    sheet.lbl_avg_temp_month_sub.add_css_class("weather-body-text")
    sheet.lbl_avg_temp_month_sub.set_wrap(True)
    sheet.lbl_avg_temp_month_sub.set_xalign(0.0)
    month_temp_card.append(sheet.lbl_avg_temp_month_sub)

    div_m_t = Gtk.Box()
    div_m_t.add_css_class("weather-card-divider")
    month_temp_card.append(div_m_t)

    sheet.climate_temp_table = ClimateMonthlyTempTable()
    month_temp_card.append(sheet.climate_temp_table)
    sheet.avg_temp_box.append(month_temp_card)

    edu_norm_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    edu_norm_card.add_css_class("weather-glass-card")
    lbl_edu_n_hdr = Gtk.Label(label="О норме" if is_ru else "About the Norm")
    lbl_edu_n_hdr.add_css_class("weather-section-title")
    lbl_edu_n_hdr.set_xalign(0.0)
    edu_norm_card.append(lbl_edu_n_hdr)

    lbl_edu_n_text = Gtk.Label(
        label=(
            "Диапазон климатической нормы охватывает типичные погодные условия для текущего дня года на основе "
            "многолетних метеорологических наблюдений (30-летний базовый цикл Всемирной метеорологической организации). "
            "В этот доверительный интервал укладывается около 80% всех исторических показаний температуры.\n\n"
            "Если фактическая кривая выходит за пределы полосы нормы, это свидетельствует о выраженной аномалии: "
            "значение выше верхней границы попадает в 10% самых жарких дней за историю наблюдений в это время года, "
            "а значение ниже нижней границы \u2014 в 10% самых холодных дней."
        ) if is_ru else (
            "The climate normal range represents the typical temperature envelope for this calendar day based on "
            "long-term meteorological observation series (standard 30-year WMO climate normal). Roughly 80% of historical "
            "temperature readings fall within this band.\n\n"
            "Readings extending above this corridor indicate unseasonably warm conditions (top 10% warmest days), "
            "while dips below indicate rare cold snaps (bottom 10% coldest days)."
        )
    )
    lbl_edu_n_text.add_css_class("weather-body-text")
    lbl_edu_n_text.set_wrap(True)
    lbl_edu_n_text.set_xalign(0.0)
    edu_norm_card.append(lbl_edu_n_text)
    sheet.avg_temp_box.append(edu_norm_card)

    edu_temp_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    edu_temp_card.add_css_class("weather-glass-card")
    lbl_edu_t_hdr = Gtk.Label(label="О средней температуре" if is_ru else "About Average Temperature")
    lbl_edu_t_hdr.add_css_class("weather-section-title")
    lbl_edu_t_hdr.set_xalign(0.0)
    edu_temp_card.append(lbl_edu_t_hdr)

    lbl_edu_t_text = Gtk.Label(
        label=(
            "Средний максимум и минимум определяют математическое ожидание экстремальных температур для конкретной "
            "календарной даты, рассчитанное по долгосрочным рядам климатических наблюдений.\n\n"
            "Среднемесячные показатели отражают среднее арифметическое суточных максимумов и минимумов за весь "
            "календарный месяц. Это позволяет наглядно сопоставить текущую погоду с устоявшимся региональным "
            "климатическим трендом."
        ) if is_ru else (
            "Daily average highs and lows represent the statistical expectation of peak daily extremes for a specific date, "
            "derived from multi-decade meteorological reanalysis.\n\n"
            "Monthly climate normals synthesize diurnal highs and lows over the full month, providing a reliable baseline "
            "to gauge seasonal progression."
        )
    )
    lbl_edu_t_text.add_css_class("weather-body-text")
    lbl_edu_t_text.set_wrap(True)
    lbl_edu_t_text.set_xalign(0.0)
    edu_temp_card.append(lbl_edu_t_text)
    sheet.avg_temp_box.append(edu_temp_card)

    sheet.averages_stack.add_named(sheet.avg_temp_box, "temp")

    # Подвкладка: Осадки
    sheet.avg_precip_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

    hero_pr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    hero_pr_box.add_css_class("weather-averages-hero-box")
    sheet.lbl_avg_precip_hero = Gtk.Label(label="+0 мм > среднего" if is_ru else "+0 mm > average")
    sheet.lbl_avg_precip_hero.add_css_class("weather-averages-hero-title")
    sheet.lbl_avg_precip_hero.set_xalign(0.0)
    hero_pr_box.append(sheet.lbl_avg_precip_hero)

    placeholder_mm = "\u2014"
    sheet.lbl_avg_precip_sub = Gtk.Label(
        label=f"Средн. за 30 дней: {placeholder_mm} мм" if is_ru else f"30-day avg: {placeholder_mm} mm"
    )
    sheet.lbl_avg_precip_sub.add_css_class("weather-averages-hero-sub")
    sheet.lbl_avg_precip_sub.set_xalign(0.0)
    hero_pr_box.append(sheet.lbl_avg_precip_sub)
    sheet.avg_precip_box.append(hero_pr_box)

    chart_pr_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    chart_pr_card.add_css_class("weather-glass-card")
    sheet.climate_precip_chart = ClimatePrecipChartArea()
    chart_pr_card.append(sheet.climate_precip_chart)
    sheet.avg_precip_box.append(chart_pr_card)

    sum_pr_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    sum_pr_card.add_css_class("weather-glass-card")
    lbl_sum_p_hdr = Gtk.Label(label="Сводка" if is_ru else "Summary")
    lbl_sum_p_hdr.add_css_class("weather-section-title")
    lbl_sum_p_hdr.set_xalign(0.0)
    sum_pr_card.append(lbl_sum_p_hdr)

    sheet.lbl_avg_precip_summary = Gtk.Label(label="")
    sheet.lbl_avg_precip_summary.add_css_class("weather-body-text")
    sheet.lbl_avg_precip_summary.set_wrap(True)
    sheet.lbl_avg_precip_summary.set_xalign(0.0)
    sum_pr_card.append(sheet.lbl_avg_precip_summary)
    sheet.avg_precip_box.append(sum_pr_card)

    month_pr_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    month_pr_card.add_css_class("weather-glass-card")
    lbl_m_p_hdr = Gtk.Label(label="Среднее за месяц" if is_ru else "Monthly Averages")
    lbl_m_p_hdr.add_css_class("weather-section-title")
    lbl_m_p_hdr.set_xalign(0.0)
    month_pr_card.append(lbl_m_p_hdr)

    sheet.lbl_avg_precip_month_sub = Gtk.Label(label="")
    sheet.lbl_avg_precip_month_sub.add_css_class("weather-body-text")
    sheet.lbl_avg_precip_month_sub.set_wrap(True)
    sheet.lbl_avg_precip_month_sub.set_xalign(0.0)
    month_pr_card.append(sheet.lbl_avg_precip_month_sub)

    div_m_p = Gtk.Box()
    div_m_p.add_css_class("weather-card-divider")
    month_pr_card.append(div_m_p)

    sheet.climate_precip_table = ClimateMonthlyPrecipTable()
    month_pr_card.append(sheet.climate_precip_table)
    sheet.avg_precip_box.append(month_pr_card)

    edu_pr_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    edu_pr_card.add_css_class("weather-glass-card")
    lbl_edu_p_hdr = Gtk.Label(label="О среднем объеме осадков" if is_ru else "About Precipitation Averages")
    lbl_edu_p_hdr.add_css_class("weather-section-title")
    lbl_edu_p_hdr.set_xalign(0.0)
    edu_pr_card.append(lbl_edu_p_hdr)

    lbl_edu_p_text = Gtk.Label(
        label=(
            "Климатическая норма осадков представляет собой совокупное среднемноголетнее количество влаги "
            "(в миллиметрах водяного столба), выпадающее в регионе за определенный календарный месяц.\n\n"
            "Накопительный 30-дневный график наглядно отражает ритм поступления влаги: пологие участки соответствуют "
            "периодам сухой и ясной погоды, а крутые ступени вверх отражают прохождение дождевых фронтов и обильные "
            "осадки по сравнению с равномерным многолетним климатическим темпом."
        ) if is_ru else (
            "Precipitation normals represent the expected cumulative volume of atmospheric moisture (in millimeters) "
            "falling within a given calendar month over a multi-decade baseline.\n\n"
            "The 30-day cumulative chart illustrates precipitation accumulation dynamics: flat steps indicate dry spells, "
            "while steep rises mark intense rain events and frontal passages against the steady climatological pace."
        )
    )
    lbl_edu_p_text.add_css_class("weather-body-text")
    lbl_edu_p_text.set_wrap(True)
    lbl_edu_p_text.set_xalign(0.0)
    edu_pr_card.append(lbl_edu_p_text)
    sheet.avg_precip_box.append(edu_pr_card)

    sheet.averages_stack.add_named(sheet.avg_precip_box, "precip")

    sheet.averages_box.append(sheet.averages_stack)
    sheet.mode_stack.add_named(sheet.averages_box, "averages")
