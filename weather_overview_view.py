"""
Echo Weather - Overview View (Level 1)
Apple Weather inspired overview screen featuring Hero widget, 24-hour forecast strip,
10-day forecast with capsule temperature bars, and interactive Bento Grid cards.
"""

import math
import os
from datetime import datetime

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from data.wmo_conditions import MAJOR_CITIES, get_condition_text, get_weekday_name
from i18n import get_current_language, t
from providers.weather import ICONS_DIR, convert_temp
from weather_detail_sheet import MiniMoonIcon, TempCapsuleBarArea


class MiniUVArc(Gtk.DrawingArea):
    """Miniature 5-step WHO segmented UV meter."""

    def __init__(self, uv_index: float):
        super().__init__()
        self.uv_index = float(uv_index or 0.0)
        self.set_content_width(52)
        self.set_content_height(18)
        self.set_draw_func(self._draw, None)

    def _draw(self, area, cr: cairo.Context, width: int, height: int, user_data):
        w = float(width)
        h = float(height)

        # 5 WHO UV segments: Low (0-2), Moderate (3-5), High (6-7), Very High (8-10), Extreme (11+)
        colors = [
            (0.18, 0.80, 0.44),
            (0.96, 0.76, 0.12),
            (0.98, 0.52, 0.15),
            (0.94, 0.25, 0.25),
            (0.70, 0.35, 0.95),
        ]

        if self.uv_index <= 2:
            active_idx = 0
        elif self.uv_index <= 5:
            active_idx = 1
        elif self.uv_index <= 7:
            active_idx = 2
        elif self.uv_index <= 10:
            active_idx = 3
        else:
            active_idx = 4

        pad_x = 2.0
        gap = 3.0
        n_segs = 5
        seg_w = max(4.0, (w - 2.0 * pad_x - (n_segs - 1) * gap) / n_segs)
        seg_h = 5.0
        seg_y = (h - seg_h) / 2.0 - 1.0

        for i, (cr_r, cr_g, cr_b) in enumerate(colors):
            sx = pad_x + i * (seg_w + gap)

            # Segment box with rounded corners
            cr.new_sub_path()
            r = 1.5
            cr.arc(sx + r, seg_y + r, r, math.pi, 1.5 * math.pi)
            cr.arc(sx + seg_w - r, seg_y + r, r, 1.5 * math.pi, 2.0 * math.pi)
            cr.arc(sx + seg_w - r, seg_y + seg_h - r, r, 0.0, 0.5 * math.pi)
            cr.arc(sx + r, seg_y + seg_h - r, r, 0.5 * math.pi, math.pi)
            cr.close_path()

            if i == active_idx:
                # Active highlighted segment
                cr.set_source_rgba(cr_r, cr_g, cr_b, 0.98)
                cr.fill()

                # Active indicator dot underneath
                dot_cx = sx + seg_w / 2.0
                dot_cy = seg_y + seg_h + 3.5
                cr.arc(dot_cx, dot_cy, 1.6, 0.0, 2.0 * math.pi)
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
                cr.fill()
            elif i < active_idx:
                # Passed levels
                cr.set_source_rgba(cr_r, cr_g, cr_b, 0.40)
                cr.fill()
            else:
                # Inactive levels
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.12)
                cr.fill()


class MiniSunCurve(Gtk.DrawingArea):
    """Miniature circular astronomical solar dial (Solar Ring)."""

    def __init__(self, sunrise_str: str, sunset_str: str, is_day: int):
        super().__init__()
        self.sunrise_str = sunrise_str or "06:00"
        self.sunset_str = sunset_str or "19:00"
        self.is_day = bool(is_day)
        self.set_content_width(28)
        self.set_content_height(28)
        self.set_draw_func(self._draw, None)

    def _draw(self, area, cr: cairo.Context, width: int, height: int, user_data):
        w = float(width)
        h = float(height)
        cx = w / 2.0
        cy = h / 2.0
        radius = min(cx, cy) - 3.5

        now = datetime.now()
        cur_minute = now.hour * 60 + now.minute
        try:
            sr_parts = [int(p) for p in self.sunrise_str.split(":")]
            ss_parts = [int(p) for p in self.sunset_str.split(":")]
            sr_min = sr_parts[0] * 60 + sr_parts[1]
            ss_min = ss_parts[0] * 60 + ss_parts[1]
        except Exception:
            sr_min = 360
            ss_min = 1140

        # Angles on a 24-hour circular dial: 0h at bottom (pi/2), 12h at top (-pi/2)
        def minute_to_angle(m: int) -> float:
            frac = (m % 1440) / 1440.0
            return 0.5 * math.pi + frac * 2.0 * math.pi

        a_sr = minute_to_angle(sr_min)
        a_ss = minute_to_angle(ss_min)
        a_cur = minute_to_angle(cur_minute)

        # 1. Outer full ring (Night/ambient track)
        cr.set_line_width(1.8)
        cr.arc(cx, cy, radius, 0.0, 2.0 * math.pi)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.16)
        cr.stroke()

        # 2. Daylight golden arc (from sunrise angle to sunset angle)
        cr.set_line_width(2.5)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.arc(cx, cy, radius, a_sr, a_ss)
        cr.set_source_rgba(1.0, 0.82, 0.20, 0.88)
        cr.stroke()

        # 3. Horizon subtle cross line
        cr.set_line_width(0.8)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.25)
        cr.move_to(cx - radius - 1.5, cy)
        cr.line_to(cx + radius + 1.5, cy)
        cr.stroke()

        # 4. Sun glowing indicator at current time
        sun_x = cx + radius * math.cos(a_cur)
        sun_y = cy + radius * math.sin(a_cur)

        # Ambient glow
        cr.arc(sun_x, sun_y, 4.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgba(1.0, 0.84, 0.10, 0.35)
        cr.fill()

        # Crisp core
        cr.arc(sun_x, sun_y, 2.2, 0.0, 2.0 * math.pi)
        cr.set_source_rgba(1.0, 0.95, 0.40, 1.0)
        cr.fill()


class MiniWindCompass(Gtk.DrawingArea):
    """Miniature wind compass dial with cardinal marks and arrow."""

    def __init__(self, wind_dir: int):
        super().__init__()
        self.wind_dir = int(wind_dir or 0)
        self.set_content_width(26)
        self.set_content_height(26)
        self.set_draw_func(self._draw, None)

    def _draw(self, area, cr: cairo.Context, width: int, height: int, user_data):
        cx = width / 2.0
        cy = height / 2.0
        radius = min(cx, cy) - 2.0

        # Outer ring
        cr.set_line_width(1.2)
        cr.arc(cx, cy, radius, 0, 2.0 * math.pi)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.25)
        cr.stroke()

        # Cardinal tick for North
        cr.set_line_width(1.5)
        cr.set_source_rgba(1.0, 0.35, 0.35, 0.90)
        cr.move_to(cx, cy - radius)
        cr.line_to(cx, cy - radius + 3.0)
        cr.stroke()

        # Arrow indicating wind direction
        angle_rad = math.radians(self.wind_dir - 90)
        tip_x = cx + (radius - 2.5) * math.cos(angle_rad)
        tip_y = cy + (radius - 2.5) * math.sin(angle_rad)
        base_x = cx - (radius - 5.0) * math.cos(angle_rad)
        base_y = cy - (radius - 5.0) * math.sin(angle_rad)

        cr.set_line_width(1.8)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_source_rgba(0.35, 0.78, 0.98, 0.95)
        cr.move_to(base_x, base_y)
        cr.line_to(tip_x, tip_y)
        cr.stroke()

        # Arrow head
        norm_rad = angle_rad + math.pi / 2.0
        w_wing = 3.5
        cr.move_to(tip_x, tip_y)
        cr.line_to(
            tip_x - 5.0 * math.cos(angle_rad) + w_wing * math.cos(norm_rad),
            tip_y - 5.0 * math.sin(angle_rad) + w_wing * math.sin(norm_rad),
        )
        cr.line_to(
            tip_x - 5.0 * math.cos(angle_rad) - w_wing * math.cos(norm_rad),
            tip_y - 5.0 * math.sin(angle_rad) - w_wing * math.sin(norm_rad),
        )
        cr.close_path()
        cr.fill()


class MiniPressureGauge(Gtk.DrawingArea):
    """Miniature barometer gauge dial with pointer."""

    def __init__(self, pressure_mm: int):
        super().__init__()
        self.pressure_mm = int(pressure_mm or 750)
        self.set_content_width(34)
        self.set_content_height(24)
        self.set_draw_func(self._draw, None)

    def _draw(self, area, cr: cairo.Context, width: int, height: int, user_data):
        cx = width / 2.0
        cy = height - 3.0
        radius = min(cx - 3.0, cy - 3.0)
        start_angle = math.pi * 0.85
        end_angle = math.pi * 2.15

        # Background track
        cr.set_line_width(2.5)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.arc(cx, cy, radius, start_angle, end_angle)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.18)
        cr.stroke()

        # Progress colored arc (720 to 780 mmHg)
        frac = max(0.0, min(1.0, (self.pressure_mm - 720.0) / 60.0))
        val_angle = start_angle + frac * (end_angle - start_angle)

        cr.arc(cx, cy, radius, start_angle, val_angle)
        cr.set_source_rgba(0.35, 0.78, 0.98, 0.90)
        cr.stroke()

        # Pointer dot
        nx = cx + (radius - 1.0) * math.cos(val_angle)
        ny = cy + (radius - 1.0) * math.sin(val_angle)
        cr.arc(nx, ny, 2.5, 0, 2.0 * math.pi)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
        cr.fill()


class MiniHumidityGauge(Gtk.DrawingArea):
    """Miniature humidity droplet gauge."""

    def __init__(self, humidity: int):
        super().__init__()
        self.humidity = max(0, min(100, int(humidity or 50)))
        self.set_content_width(28)
        self.set_content_height(24)
        self.set_draw_func(self._draw, None)

    def _draw(self, area, cr: cairo.Context, width: int, height: int, user_data):
        cx = width / 2.0
        cy = height / 2.0 + 1.0
        radius = 7.5

        # Outer track
        cr.set_line_width(2.2)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        start_a = -math.pi * 0.75
        end_a = math.pi * 0.75
        span = end_a - start_a

        cr.arc(cx, cy, radius, start_a, end_a)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.18)
        cr.stroke()

        # Fill track
        frac = self.humidity / 100.0
        fill_a = start_a + frac * span
        cr.arc(cx, cy, radius, start_a, fill_a)
        cr.set_source_rgba(0.35, 0.78, 0.98, 0.92)
        cr.stroke()


class MiniClimateNormGauge(Gtk.DrawingArea):
    """Miniature climate norm deviation bar."""

    def __init__(self, avg_diff_str: str):
        super().__init__()
        self.avg_diff_str = avg_diff_str or "0°"
        self.set_content_width(44)
        self.set_content_height(20)
        self.set_draw_func(self._draw, None)

    def _draw(self, area, cr: cairo.Context, width: int, height: int, user_data):
        w = float(width)
        h = float(height)
        cy = h / 2.0
        cx = w / 2.0

        # Base track
        cr.set_line_width(3.0)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.16)
        cr.move_to(4.0, cy)
        cr.line_to(w - 4.0, cy)
        cr.stroke()

        # Center norm tick
        cr.set_line_width(1.5)
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.60)
        cr.move_to(cx, cy - 4.0)
        cr.line_to(cx, cy + 4.0)
        cr.stroke()

        # Parse diff delta
        delta = 0.0
        try:
            cleaned = self.avg_diff_str.replace("°", "").replace("к норме", "").replace("vs norm", "").strip()
            delta = float(cleaned)
        except Exception:
            delta = 0.0

        if abs(delta) > 0.1:
            max_dev = 6.0
            frac = max(-1.0, min(1.0, delta / max_dev))
            target_x = cx + frac * (cx - 6.0)

            cr.set_line_width(3.0)
            if delta > 0:
                cr.set_source_rgba(1.0, 0.58, 0.0, 0.95)
            else:
                cr.set_source_rgba(0.2, 0.6, 1.0, 0.95)
            cr.move_to(cx, cy)
            cr.line_to(target_x, cy)
            cr.stroke()

            # End dot
            cr.arc(target_x, cy, 2.5, 0, 2.0 * math.pi)
            cr.fill()


class VerticalTempBarArea(Gtk.DrawingArea):
    """
    Vertical precision range bar showing min/max range on a vertical rail.
    Replaces horizontal capsule bars with an architectural vertical gauge.
    """

    def __init__(self, t_min: float, t_max: float, global_min: float, global_max: float, current_temp: float = None):
        super().__init__()
        self.t_min = float(t_min)
        self.t_max = float(t_max)
        self.global_min = float(global_min)
        self.global_max = float(global_max)
        self.current_temp = float(current_temp) if current_temp is not None else None

        self.set_content_width(8)
        self.set_content_height(46)
        self.set_draw_func(self._draw, None)

    def update_data(self, t_min: float, t_max: float, global_min: float, global_max: float, current_temp: float = None):
        self.t_min = float(t_min)
        self.t_max = float(t_max)
        self.global_min = float(global_min)
        self.global_max = float(global_max)
        self.current_temp = float(current_temp) if current_temp is not None else None
        self.queue_draw()

    def _draw(self, area, cr: cairo.Context, width: int, height: int, user_data):
        w = float(width)
        h = float(height)

        # Background vertical track slot
        bar_w = 4.0
        x0 = (w - bar_w) / 2.0
        radius = 2.0

        cr.save()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.12)
        cr.new_sub_path()
        cr.arc(x0 + radius, radius, radius, math.pi, 1.5 * math.pi)
        cr.arc(x0 + bar_w - radius, radius, radius, 1.5 * math.pi, 2 * math.pi)
        cr.arc(x0 + bar_w - radius, h - radius, radius, 0, 0.5 * math.pi)
        cr.arc(x0 + radius, h - radius, radius, 0.5 * math.pi, math.pi)
        cr.close_path()
        cr.fill()
        cr.restore()

        # Vertical range calculation: high temp is near top (small y)
        span = max(1.0, self.global_max - self.global_min)
        norm_max = max(0.0, min(1.0, (self.t_max - self.global_min) / span))
        norm_min = max(0.0, min(1.0, (self.t_min - self.global_min) / span))

        pad = 2.0
        avail_h = h - 2.0 * pad
        y_top = pad + avail_h * (1.0 - norm_max)
        y_bot = pad + avail_h * (1.0 - norm_min)
        bar_len = max(4.0, y_bot - y_top)

        # Vertical gradient: warm amber at top, cool cyan at bottom
        pat = cairo.LinearGradient(x0, y_top, x0, y_top + bar_len)
        pat.add_color_stop_rgba(0.0, 0.98, 0.65, 0.20, 0.95)
        pat.add_color_stop_rgba(1.0, 0.25, 0.70, 0.95, 0.95)

        cr.save()
        cr.set_source(pat)
        cr.new_sub_path()
        cr.arc(x0 + radius, y_top + radius, radius, math.pi, 1.5 * math.pi)
        cr.arc(x0 + bar_w - radius, y_top + radius, radius, 1.5 * math.pi, 2 * math.pi)
        cr.arc(x0 + bar_w - radius, y_top + bar_len - radius, radius, 0, 0.5 * math.pi)
        cr.arc(x0 + radius, y_top + bar_len - radius, radius, 0.5 * math.pi, math.pi)
        cr.close_path()
        cr.fill()
        cr.restore()

        # Current temperature marker for Today
        if self.current_temp is not None:
            norm_cur = max(0.0, min(1.0, (self.current_temp - self.global_min) / span))
            y_cur = pad + avail_h * (1.0 - norm_cur)

            cr.save()
            cr.set_source_rgba(0.1, 0.1, 0.15, 0.7)
            cr.arc(w / 2.0, y_cur, 3.5, 0, 2.0 * math.pi)
            cr.fill()

            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.arc(w / 2.0, y_cur, 2.2, 0, 2.0 * math.pi)
            cr.fill()
            cr.restore()


class WeatherOverviewView(Gtk.Box):
    """Level 1 Overview screen styled after Apple Weather."""

    def __init__(
        self,
        data: dict,
        temp_unit: str = "celsius",
        on_open_mode_callback = None,
        on_open_day_callback = None,
        two_panel_layout: bool = False,
        on_toggle_home_callback = None,
        on_toggle_pin_callback = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.data = data or {}
        self.temp_unit = temp_unit
        self.on_open_mode_callback = on_open_mode_callback
        self.on_open_day_callback = on_open_day_callback
        self.two_panel_layout = False
        self.on_toggle_home_callback = on_toggle_home_callback
        self.on_toggle_pin_callback = on_toggle_pin_callback

        self.add_css_class("weather-overview-view")
        self.set_vexpand(True)
        self.set_hexpand(True)

        self._build_ui()

    def set_two_panel_layout(self, enabled: bool):
        """Deprecated: Single-column is standard layout."""
        pass

    def update_data(self, data: dict, temp_unit: str = None):
        """Update weather data and rebuild view."""
        self.data = data or {}
        if temp_unit:
            self.temp_unit = temp_unit
        self._rebuild_content()

    def set_temp_unit(self, temp_unit: str):
        """Update temperature unit and rebuild view."""
        if self.temp_unit != temp_unit:
            self.temp_unit = temp_unit
            self._rebuild_content()

    def _open_mode(self, mode_id: str):
        if callable(self.on_open_mode_callback):
            self.on_open_mode_callback(mode_id)

    def _open_day(self, day_idx: int):
        if callable(self.on_open_day_callback):
            self.on_open_day_callback(day_idx)

    def _build_ui(self):
        # Scrolled window container for scrollable overview
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.add_css_class("weather-scrolled-window")
        self.scroll.add_css_class("weather-overview-scroll")
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_vexpand(True)
        self.scroll.set_hexpand(True)
        self.append(self.scroll)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.content_box.add_css_class("weather-overview-content")
        self.content_box.set_valign(Gtk.Align.START)
        self.content_box.set_hexpand(True)

        # Padding constraints
        self.content_box.set_margin_start(20)
        self.content_box.set_margin_end(20)
        self.content_box.set_margin_top(12)
        self.content_box.set_margin_bottom(30)

        self.scroll.set_child(self.content_box)
        self._populate_content()

    def _rebuild_content(self):
        while child := self.content_box.get_first_child():
            self.content_box.remove(child)
        self._populate_content()

    def _populate_content(self):
        # 1. Central Hero widget
        hero_widget = self._build_hero_widget()

        # 2. Hourly forecast card (24 hours)
        hourly_card = self._build_hourly_card()

        # 3. 10-day forecast card
        daily_card = self._build_daily_card()

        # 4. Asymmetric Telemetry Deck (Bento Grid)
        bento_grid = self._build_bento_grid()

        self.content_box.append(hero_widget)
        self.content_box.append(hourly_card)
        self.content_box.append(daily_card)
        self.content_box.append(bento_grid)

    def _build_hero_widget(self) -> Gtk.Widget:
        curr_lang = get_current_language()
        is_ru = (curr_lang == "ru")

        # Asymmetric Cockpit Plate
        hero_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        hero_card.add_css_class("weather-glass-card")
        hero_card.add_css_class("weather-hero-cockpit")
        hero_card.set_hexpand(True)

        # Left Column: Telemetry, Temperature, Condition, Extremes
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        left_box.set_hexpand(True)
        left_box.set_halign(Gtk.Align.START)
        left_box.add_css_class("weather-hero-telemetry-col")

        # 1. Location Header & Coordinates Tag
        loc_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        loc_header.set_halign(Gtk.Align.START)
        loc_header.set_valign(Gtk.Align.CENTER)

        raw_city = self.data.get("city_name") or "Погода"
        city_name = raw_city
        if not is_ru:
            name_en = self.data.get("name_en")
            if name_en:
                city_name = name_en
            else:
                c_clean = raw_city.strip().lower()
                for k, v in MAJOR_CITIES.items():
                    if k == c_clean or v.get("name_ru", "").lower() == c_clean or v.get("name_en", "").lower() == c_clean:
                        city_name = v.get("name_en", city_name)
                        break
        else:
            name_ru = self.data.get("name_ru")
            if name_ru:
                city_name = name_ru
            else:
                c_clean = raw_city.strip().lower()
                for k, v in MAJOR_CITIES.items():
                    if k == c_clean or v.get("name_ru", "").lower() == c_clean or v.get("name_en", "").lower() == c_clean:
                        city_name = v.get("name_ru", city_name)
                        break

        city_lbl = Gtk.Label(label=city_name)
        city_lbl.add_css_class("weather-hero-city")
        city_lbl.set_xalign(0.0)
        loc_header.append(city_lbl)

        lat = self.data.get("latitude")
        lon = self.data.get("longitude")
        if lat is not None and lon is not None:
            coord_str = f"{abs(lat):.2f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.2f}°{'E' if lon >= 0 else 'W'}"
        else:
            coord_str = "МЕТЕОСТАНЦИЯ" if is_ru else "METEO STATION"

        tag_box = Gtk.Box()
        tag_box.add_css_class("weather-hero-coord-tag")
        tag_lbl = Gtk.Label(label=coord_str)
        tag_lbl.add_css_class("weather-hero-coord-text")
        tag_box.append(tag_lbl)
        loc_header.append(tag_box)

        # Home / Main City Action Pill
        is_main_city = bool(self.data.get("is_main_city", False))
        hero_home_btn = Gtk.Button()
        hero_home_btn.add_css_class("weather-hero-action-btn")
        home_pill_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        h_icon = Gtk.Image.new_from_icon_name("user-home-symbolic")
        h_icon.set_pixel_size(13)
        home_pill_box.append(h_icon)
        if is_main_city:
            hero_home_btn.add_css_class("active")
            h_lbl = Gtk.Label(label=t("weather_main_city_badge"))
            hero_home_btn.set_tooltip_text(f"{city_name}: {t('weather_main_city_btn_active')}")
        else:
            h_lbl = Gtk.Label(label=t("weather_main_city_btn_set"))
            hero_home_btn.set_tooltip_text(f"{city_name}: {t('weather_main_city_btn_set')}")
        home_pill_box.append(h_lbl)
        hero_home_btn.set_child(home_pill_box)
        if self.on_toggle_home_callback:
            hero_home_btn.connect("clicked", lambda _: self.on_toggle_home_callback())
        loc_header.append(hero_home_btn)

        # Pin Action Pill
        is_pinned = bool(self.data.get("is_pinned", False))
        hero_pin_btn = Gtk.Button()
        hero_pin_btn.add_css_class("weather-hero-action-btn")
        if is_pinned:
            hero_pin_btn.add_css_class("active")
        pin_pill_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        p_icon = Gtk.Image.new_from_icon_name("view-pin-symbolic")
        p_icon.set_pixel_size(13)
        pin_pill_box.append(p_icon)
        p_lbl = Gtk.Label(label=t("weather_unpin_tooltip") if is_pinned else t("weather_pin_tooltip"))
        pin_pill_box.append(p_lbl)
        hero_pin_btn.set_child(pin_pill_box)
        hero_pin_btn.set_tooltip_text(t("weather_unpin_tooltip") if is_pinned else t("weather_pin_tooltip"))
        if self.on_toggle_pin_callback:
            hero_pin_btn.connect("clicked", lambda _: self.on_toggle_pin_callback())
        loc_header.append(hero_pin_btn)

        left_box.append(loc_header)

        # 2. Main Temperature & Condition Row
        temp_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        temp_row.set_halign(Gtk.Align.START)
        temp_row.set_valign(Gtk.Align.CENTER)

        temp_val = self.data.get("temp", 0)
        temp_disp = convert_temp(temp_val, self.temp_unit)
        temp_lbl = Gtk.Label(label=f"{temp_disp}°")
        temp_lbl.add_css_class("weather-hero-temp")
        temp_lbl.set_xalign(0.0)
        temp_row.append(temp_lbl)

        cond_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        cond_box.set_valign(Gtk.Align.CENTER)

        w_code = self.data.get("weather_code")
        cond_text = self.data.get("condition_text", "")
        is_day = bool(self.data.get("is_day", 1) == 1)
        if w_code is not None:
            trans_cond = get_condition_text(w_code, lang=curr_lang, is_day=is_day)
            if trans_cond:
                cond_text = trans_cond

        cond_lbl = Gtk.Label(label=cond_text)
        cond_lbl.add_css_class("weather-hero-condition")
        cond_lbl.set_xalign(0.0)
        cond_box.append(cond_lbl)

        summary_hint = self.data.get("summary") or ("Стабильные метеоусловия" if is_ru else "Steady conditions")
        if len(summary_hint) > 42:
            summary_hint = summary_hint[:40] + "..."
        trend_lbl = Gtk.Label(label=summary_hint)
        trend_lbl.add_css_class("weather-hero-trend-text")
        trend_lbl.set_xalign(0.0)
        cond_box.append(trend_lbl)

        temp_row.append(cond_box)
        left_box.append(temp_row)

        # 3. Extremes and Telemetry Micro-Chips Row
        t_min = convert_temp(self.data.get("temp_min", temp_val), self.temp_unit)
        t_max = convert_temp(self.data.get("temp_max", temp_val), self.temp_unit)
        feels = convert_temp(self.data.get("feels_like", temp_val), self.temp_unit)

        chips_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        chips_row.set_halign(Gtk.Align.START)
        chips_row.add_css_class("weather-hero-chips-row")
        chips_row.add_css_class("weather-hero-extremes")

        # Range chip
        range_chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        range_chip.add_css_class("weather-hero-chip")
        range_lbl = Gtk.Label(label=f"↓ {t_min}°   ↑ {t_max}°")
        range_lbl.add_css_class("weather-hero-chip-text")
        range_chip.append(range_lbl)
        chips_row.append(range_chip)

        # Feels like chip
        feels_chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        feels_chip.add_css_class("weather-hero-chip")
        feels_label_str = t("weather_feels_like")
        if feels_label_str == "weather_feels_like":
            feels_label_str = "Ощущается" if is_ru else "Feels like"
        feels_lbl = Gtk.Label(label=f"{feels_label_str} {feels}°")
        feels_lbl.add_css_class("weather-hero-chip-text")
        feels_chip.append(feels_lbl)
        chips_row.append(feels_chip)

        # Wind chip
        w_speed = round(self.data.get("wind_speed", 0))
        w_card = self.data.get("wind_cardinal", "С")
        w_unit = "км/ч" if is_ru else "km/h"
        wind_chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        wind_chip.add_css_class("weather-hero-chip")
        wind_lbl = Gtk.Label(label=f"{w_card} {w_speed} {w_unit}")
        wind_lbl.add_css_class("weather-hero-chip-text")
        wind_chip.append(wind_lbl)
        chips_row.append(wind_chip)

        left_box.append(chips_row)
        hero_card.append(left_box)

        # Right Column: Visual Art & Meteorological Model Badge
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right_box.set_halign(Gtk.Align.END)
        right_box.set_valign(Gtk.Align.CENTER)
        right_box.add_css_class("weather-hero-art-col")

        art_frame = Gtk.Box()
        art_frame.add_css_class("weather-hero-art-frame")
        art_frame.set_halign(Gtk.Align.CENTER)

        from providers.weather import WMO_INFO
        w_inf = WMO_INFO.get(w_code, WMO_INFO.get(0, {}))
        icon_name = w_inf.get("icon_day" if is_day else "icon_night", "clear-day.svg")
        icon_path = os.path.join(ICONS_DIR, icon_name)
        if os.path.exists(icon_path):
            hero_icon = Gtk.Image.new_from_file(icon_path)
            hero_icon.set_pixel_size(72)
            art_frame.append(hero_icon)

        right_box.append(art_frame)

        model_badge = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        model_badge.add_css_class("weather-hero-model-tag")
        curr_src = self.data.get("forecast_source", "consensus")
        src_names = {
            "consensus": "Консенсус (ECMWF + ICON + MET Norway)" if is_ru else "Consensus (ECMWF + ICON + MET Norway)",
            "ecmwf": "ECMWF IFS (Европа)" if is_ru else "ECMWF IFS (Europe)",
            "icon": "DWD ICON (Германия)" if is_ru else "DWD ICON (Germany)",
            "met_norway": "MET Norway",
            "open_meteo": "Open-Meteo",
        }
        source_name = src_names.get(curr_src) or self.data.get("source_name") or "MET Norway / Open-Meteo"
        model_lbl = Gtk.Label(label=f"● {source_name}")
        model_lbl.add_css_class("weather-hero-model-text")
        model_badge.append(model_lbl)
        right_box.append(model_badge)

        hero_card.append(right_box)
        return hero_card

    def _build_hourly_card(self) -> Gtk.Widget:
        is_ru = (get_current_language() == "ru")
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("weather-glass-card")
        card.add_css_class("weather-card-clickable")

        # Click handler to open conditions mode in Level 2
        click_gesture = Gtk.GestureClick()
        click_gesture.connect("released", lambda *_: self._open_mode("conditions"))
        card.add_controller(click_gesture)

        # Card summary header
        summary_text = self.data.get("summary") or (
            "В течение дня сохранится устойчивая погода." if is_ru else "Conditions remain steady today."
        )
        summary_lbl = Gtk.Label(label=summary_text)
        summary_lbl.add_css_class("weather-summary-text")
        summary_lbl.set_wrap(True)
        summary_lbl.set_xalign(0.0)
        card.append(summary_lbl)

        # Divider
        divider = Gtk.Box()
        divider.add_css_class("weather-card-divider")
        card.append(divider)

        # Scrolled strip for 24 hours
        scroll_strip = Gtk.ScrolledWindow()
        scroll_strip.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroll_strip.set_vexpand(False)

        hourly_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        hourly_box.add_css_class("weather-hourly-box")
        scroll_strip.set_child(hourly_box)

        # Collect 24-hour items
        items = self._get_24h_forecast_items()
        for idx, item in enumerate(items):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            col.add_css_class("weather-hourly-col")
            col.set_halign(Gtk.Align.CENTER)

            # Time label
            time_lbl = Gtk.Label(label=item["time"])
            time_lbl.add_css_class("weather-hourly-time")
            col.append(time_lbl)

            # Weather icon
            icon_file = item.get("icon_file")
            if icon_file and os.path.exists(icon_file):
                icon_img = Gtk.Image.new_from_file(icon_file)
                icon_img.set_pixel_size(24)
                col.append(icon_img)

            # Precipitation probability (if greater than 0)
            prob = item.get("prob", 0)
            if prob > 0:
                prob_lbl = Gtk.Label(label=f"{prob}%")
                prob_lbl.add_css_class("weather-hourly-precip")
                col.append(prob_lbl)
            else:
                spacer = Gtk.Box()
                spacer.set_size_request(-1, 14)
                col.append(spacer)

            # Temperature label
            t_disp = convert_temp(item["temp"], self.temp_unit)
            t_lbl = Gtk.Label(label=f"{t_disp}°")
            t_lbl.add_css_class("weather-hourly-temp")
            col.append(t_lbl)

            hourly_box.append(col)

        card.append(scroll_strip)
        return card

    def _get_24h_forecast_items(self) -> list[dict]:
        """Collect up to 24 forward hours starting from the current hour."""
        is_ru = (get_current_language() == "ru")
        days_detailed = self.data.get("days_detailed", [])
        if not days_detailed:
            # Fallback to hourly array if days_detailed is absent
            fallback_items = []
            hourly_list = self.data.get("hourly", [])
            for h in hourly_list:
                t_str = str(h.get("time", ""))
                if ":" not in t_str and len(t_str) == 2:
                    t_str = f"{t_str}:00"
                fallback_items.append({
                    "time": t_str,
                    "temp": h.get("temp", 0),
                    "icon_file": h.get("icon_file", ""),
                    "prob": 0
                })
            return fallback_items

        day0 = days_detailed[0]
        cur_h = datetime.now().hour
        day0_temps = day0.get("hourly_temps", [])
        day0_probs = day0.get("hourly_probs", [])

        items = []
        # Day 0 hours from cur_h to 23
        for h in range(cur_h, min(24, len(day0_temps))):
            is_now = (h == cur_h)
            lbl = ("Сейчас" if is_ru else "Now") if is_now else f"{h:02d}:00"
            t_val = day0_temps[h] if h < len(day0_temps) else 0
            p_val = day0_probs[h] if h < len(day0_probs) else 0
            icon_file = self._resolve_icon_for_hour(day0, h)
            items.append({
                "time": lbl,
                "temp": t_val,
                "prob": p_val,
                "icon_file": icon_file
            })

        # Fill remaining hours from day 1 up to 24
        if len(items) < 24 and len(days_detailed) > 1:
            day1 = days_detailed[1]
            day1_temps = day1.get("hourly_temps", [])
            day1_probs = day1.get("hourly_probs", [])
            needed = 24 - len(items)
            for h in range(0, min(needed, len(day1_temps))):
                lbl = f"{h:02d}:00"
                t_val = day1_temps[h] if h < len(day1_temps) else 0
                p_val = day1_probs[h] if h < len(day1_probs) else 0
                icon_file = self._resolve_icon_for_hour(day1, h)
                items.append({
                    "time": lbl,
                    "temp": t_val,
                    "prob": p_val,
                    "icon_file": icon_file
                })

        return items

    def _resolve_icon_for_hour(self, day_info: dict, hour: int) -> str:
        code = 0
        hourly_codes = day_info.get("hourly_codes", [])
        if hour < len(hourly_codes):
            code = hourly_codes[hour]
        is_day = 1 if 6 <= hour < 21 else 0

        from providers.weather import WMO_INFO
        w_inf = WMO_INFO.get(code, WMO_INFO.get(0, {}))
        icon_name = w_inf.get("icon_day" if is_day else "icon_night", "clear-day.svg")
        return os.path.join(ICONS_DIR, icon_name)

    def _build_daily_card(self) -> Gtk.Widget:
        is_ru = (get_current_language() == "ru")
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("weather-glass-card")
        card.add_css_class("weather-daily-columns-card")

        # Title Header
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        cal_icon_path = os.path.join(ICONS_DIR, "calendar.svg")
        if os.path.exists(cal_icon_path):
            cal_img = Gtk.Image.new_from_file(cal_icon_path)
            cal_img.set_pixel_size(13)
            cal_img.set_opacity(0.65)
            title_box.append(cal_img)

        title_lbl = Gtk.Label(label="// Прогноз на 10 дней" if is_ru else "// 10-Day Synoptic Rail")
        title_lbl.add_css_class("weather-section-title")
        title_lbl.set_xalign(0.0)
        title_box.append(title_lbl)
        card.append(title_box)

        # Divider
        divider = Gtk.Box()
        divider.add_css_class("weather-card-divider")
        card.append(divider)

        # Daily columns rail
        days_detailed = self.data.get("days_detailed", [])
        daily_list = self.data.get("daily", [])
        effective_days = days_detailed if days_detailed else daily_list

        def _get_val(d, *keys, default=0):
            for k in keys:
                v = d.get(k)
                if v is not None:
                    return v
            return default

        all_mins = [convert_temp(_get_val(d, "min", "t_min", "temp_min", "min_temp"), self.temp_unit) for d in effective_days[:10]]
        all_maxs = [convert_temp(_get_val(d, "max", "t_max", "temp_max", "max_temp"), self.temp_unit) for d in effective_days[:10]]
        if not all_mins:
            all_mins = [0]
            all_maxs = [20]
        global_min = min(all_mins)
        global_max = max(all_maxs)
        cur_temp_disp = convert_temp(self.data.get("temp", 0), self.temp_unit)

        # ScrolledWindow with horizontal scrolling
        scroll_rail = Gtk.ScrolledWindow()
        scroll_rail.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroll_rail.set_vexpand(False)
        scroll_rail.add_css_class("weather-daily-scroll-rail")

        rail_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        rail_box.add_css_class("weather-daily-rail-box")
        rail_box.set_hexpand(True)
        scroll_rail.set_child(rail_box)

        count = min(10, len(effective_days))
        for i in range(count):
            day_info = effective_days[i]
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            col.add_css_class("weather-day-column")
            col.add_css_class("weather-card-clickable")
            if i == 0:
                col.add_css_class("weather-day-column-today")

            # Click gesture to open day detail in Level 2
            day_click = Gtk.GestureClick()
            day_click.connect("released", lambda *_, d_idx=i: self._open_day(d_idx))
            col.add_controller(day_click)

            # 1. Weekday & Date
            cur_lang = get_current_language()
            d_str = day_info.get("date_str")
            date_num_str = ""
            if i == 0:
                day_name = "Сегодня" if is_ru else "Today"
            else:
                raw_name = day_info.get("weekday_short") or day_info.get("day") or day_info.get("day_name", "")
                ru_weekdays = {"Пн": 0, "Вт": 1, "Ср": 2, "Чт": 3, "Пт": 4, "Сб": 5, "Вс": 6}
                if d_str:
                    try:
                        from datetime import datetime
                        dt_val = datetime.strptime(d_str, "%Y-%m-%d")
                        day_name = get_weekday_name(dt_val.weekday(), lang=cur_lang)
                        date_num_str = dt_val.strftime("%d.%m")
                    except Exception:
                        day_name = raw_name or (f"День {i + 1}" if is_ru else f"Day {i + 1}")
                elif raw_name in ru_weekdays and not is_ru:
                    day_name = get_weekday_name(ru_weekdays[raw_name], lang=cur_lang)
                else:
                    day_name = raw_name or (f"День {i + 1}" if is_ru else f"Day {i + 1}")

            name_lbl = Gtk.Label(label=day_name)
            name_lbl.add_css_class("weather-day-col-name")
            name_lbl.set_halign(Gtk.Align.CENTER)
            col.append(name_lbl)

            if date_num_str:
                date_lbl = Gtk.Label(label=date_num_str)
                date_lbl.add_css_class("weather-day-col-date")
                date_lbl.set_halign(Gtk.Align.CENTER)
                col.append(date_lbl)
            else:
                spacer_date = Gtk.Box()
                spacer_date.set_size_request(-1, 12)
                col.append(spacer_date)

            # 2. Weather Icon
            icon_file = day_info.get("icon_file")
            if icon_file and os.path.exists(icon_file):
                icon_img = Gtk.Image.new_from_file(icon_file)
                icon_img.set_pixel_size(24)
                col.append(icon_img)
            else:
                spacer_icon = Gtk.Box()
                spacer_icon.set_size_request(24, 24)
                col.append(spacer_icon)

            # 3. Precip probability badge (if > 0)
            prob_val = day_info.get("precipitation_probability") or day_info.get("precip_prob", 0)
            if prob_val > 0:
                p_lbl = Gtk.Label(label=f"{prob_val}%")
                p_lbl.add_css_class("weather-day-col-precip")
                col.append(p_lbl)
            else:
                p_spacer = Gtk.Box()
                p_spacer.set_size_request(-1, 14)
                col.append(p_spacer)

            # 4. Max temperature
            v_max = _get_val(day_info, "max", "t_max", "temp_max", "max_temp")
            t_max_disp = convert_temp(v_max, self.temp_unit)
            max_lbl = Gtk.Label(label=f"{t_max_disp}°")
            max_lbl.add_css_class("weather-day-col-temp-max")
            max_lbl.set_halign(Gtk.Align.CENTER)
            col.append(max_lbl)

            # 5. Vertical Range Bar
            v_min = _get_val(day_info, "min", "t_min", "temp_min", "min_temp")
            t_min_disp = convert_temp(v_min, self.temp_unit)
            v_bar = VerticalTempBarArea(
                t_min=t_min_disp,
                t_max=t_max_disp,
                global_min=global_min,
                global_max=global_max,
                current_temp=cur_temp_disp if i == 0 else None,
            )
            v_bar.set_halign(Gtk.Align.CENTER)
            col.append(v_bar)

            # 6. Min temperature
            min_lbl = Gtk.Label(label=f"{t_min_disp}°")
            min_lbl.add_css_class("weather-day-col-temp-min")
            min_lbl.set_halign(Gtk.Align.CENTER)
            col.append(min_lbl)

            rail_box.append(col)

        card.append(scroll_rail)
        return card

    def _create_telemetry_vdivider(self) -> Gtk.Widget:
        div = Gtk.Box()
        div.add_css_class("weather-telemetry-vdivider")
        return div

    def _create_telemetry_cell(
        self,
        title: str,
        icon_file_name: str,
        value_text: str,
        subtitle_text: str,
        mode_id: str,
        custom_widget: Gtk.Widget = None,
    ) -> Gtk.Widget:
        cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        cell.add_css_class("weather-telemetry-cell")
        cell.add_css_class("weather-card-clickable")
        cell.set_hexpand(True)

        click = Gtk.GestureClick()
        click.connect("released", lambda *_, m=mode_id: self._open_mode(m))
        cell.add_controller(click)

        # Header row
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        icon_path = os.path.join(ICONS_DIR, icon_file_name)
        if os.path.exists(icon_path):
            img = Gtk.Image.new_from_file(icon_path)
            img.set_pixel_size(13)
            img.set_opacity(0.7)
            hdr.append(img)

        lbl_t = Gtk.Label(label=title)
        lbl_t.add_css_class("weather-telemetry-key")
        lbl_t.set_xalign(0.0)
        lbl_t.set_hexpand(True)
        hdr.append(lbl_t)

        cell.append(hdr)

        # Value + optional widget
        val_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_v = Gtk.Label(label=value_text)
        lbl_v.add_css_class("weather-telemetry-val")
        lbl_v.set_xalign(0.0)
        lbl_v.set_hexpand(True)
        val_box.append(lbl_v)

        if custom_widget:
            custom_widget.set_valign(Gtk.Align.CENTER)
            val_box.append(custom_widget)

        cell.append(val_box)

        # Subtitle
        if subtitle_text:
            lbl_s = Gtk.Label(label=subtitle_text)
            lbl_s.add_css_class("weather-telemetry-sub")
            lbl_s.set_xalign(0.0)
            cell.append(lbl_s)

        return cell

    def _build_bento_grid(self) -> Gtk.Widget:
        is_ru = (get_current_language() == "ru")
        grid = Gtk.Grid()
        grid.add_css_class("weather-dashboard-deck")
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(12)
        grid.set_row_spacing(12)
        grid.set_hexpand(True)

        # TIER 1: Atmospheric Telemetry Strip (Full width, spans 10 columns)
        strip_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        strip_card.add_css_class("weather-glass-card")
        strip_card.add_css_class("weather-telemetry-strip")
        strip_card.set_hexpand(True)

        # Cell 1: Pressure
        press_mm = self.data.get("pressure_mm", 750)
        press_desc = self.data.get("pressure_desc") or (
            "Давление стабильное." if is_ru else "Pressure steady."
        )
        cell_press = self._create_telemetry_cell(
            title="// Барометр" if is_ru else "// Barometer",
            icon_file_name="gauge.svg",
            value_text=f"{press_mm} мм" if is_ru else f"{press_mm} mmHg",
            subtitle_text=press_desc,
            mode_id="pressure",
            custom_widget=MiniPressureGauge(press_mm),
        )
        strip_card.append(cell_press)

        strip_card.append(self._create_telemetry_vdivider())

        # Cell 2: Humidity
        humidity = self.data.get("humidity", 50)
        dew_point_val = self.data.get("dew_point", 10)
        dew_disp = convert_temp(dew_point_val, self.temp_unit)
        cell_humidity = self._create_telemetry_cell(
            title="// Влажность" if is_ru else "// Humidity",
            icon_file_name="humidity.svg",
            value_text=f"{humidity}%",
            subtitle_text=f"Точка росы: {dew_disp}°" if is_ru else f"Dew point: {dew_disp}°",
            mode_id="humidity",
            custom_widget=MiniHumidityGauge(humidity),
        )
        strip_card.append(cell_humidity)

        strip_card.append(self._create_telemetry_vdivider())

        # Cell 3: Visibility
        vis_km = self.data.get("visibility_km", 10.0)
        vis_desc = self.data.get("visibility_desc") or (
            "Ясный горизонт" if is_ru else "Clear horizon"
        )
        cell_vis = self._create_telemetry_cell(
            title="// Видимость" if is_ru else "// Visibility",
            icon_file_name="eye.svg",
            value_text=f"{vis_km} км" if is_ru else f"{vis_km} km",
            subtitle_text=vis_desc,
            mode_id="visibility",
        )
        strip_card.append(cell_vis)

        strip_card.append(self._create_telemetry_vdivider())

        # Cell 4: UV Index
        uv_idx = self.data.get("uv_index", 0)
        uv_lvl = self.data.get("uv_level") or ("Низкий" if is_ru else "Low")
        cell_uv = self._create_telemetry_cell(
            title="// УФ-индекс" if is_ru else "// UV Index",
            icon_file_name="sun-uv.svg",
            value_text=str(uv_idx),
            subtitle_text=uv_lvl,
            mode_id="uv",
            custom_widget=MiniUVArc(uv_idx),
        )
        strip_card.append(cell_uv)

        grid.attach(strip_card, 0, 0, 10, 1)

        # TIER 2: Asymmetric Split 60% / 40% (Wind & Dynamics 6 cols, Thermal Comfort 4 cols)
        wind_speed = round(self.data.get("wind_speed", 0))
        wind_gusts = round(self.data.get("wind_gusts", wind_speed))
        wind_cardinal = self.data.get("wind_cardinal", "С")
        wind_dir = self.data.get("wind_direction", 0)
        wind_desc = self.data.get("wind_desc") or (
            f"Порывы до {wind_gusts} км/ч • {wind_cardinal}" if is_ru else f"Gusts up to {wind_gusts} km/h • {wind_cardinal}"
        )
        card_wind = self._create_bento_card(
            title="// Ветровой режим" if is_ru else "// Wind Dynamics",
            icon_file_name="wind.svg",
            value_text=f"{wind_speed} км/ч" if is_ru else f"{wind_speed} km/h",
            subtitle_text=f"Азимут: {wind_cardinal} ({wind_dir}°) • Порывы до {wind_gusts} км/ч" if is_ru else f"Heading: {wind_cardinal} ({wind_dir}°) • Gusts to {wind_gusts} km/h",
            desc_text=wind_desc,
            mode_id="wind",
            custom_widget=MiniWindCompass(wind_dir),
            is_wide=True,
        )
        grid.attach(card_wind, 0, 1, 6, 1)

        temp_val = self.data.get("temp", 0)
        temp_disp = convert_temp(temp_val, self.temp_unit)
        feels_val = self.data.get("feels_like", temp_val)
        feels_disp = convert_temp(feels_val, self.temp_unit)
        feels_desc = self.data.get("feels_like_desc") or (
            "Влажность и ветер в балансе с температурой." if is_ru else "Humidity and wind balanced with temperature."
        )
        card_comfort = self._create_bento_card(
            title="// Биокомфорт" if is_ru else "// Thermal Comfort",
            icon_file_name="thermometer.svg",
            value_text=f"{feels_disp}°",
            subtitle_text=f"Фактически: {temp_disp}°" if is_ru else f"Actual: {temp_disp}°",
            desc_text=feels_desc,
            mode_id="conditions",
        )
        grid.attach(card_comfort, 6, 1, 4, 1)

        # TIER 3: Asymmetric Split 40% / 30% / 30% (Precipitation 4 cols, Sun 3 cols, Moon 3 cols)
        precip_sum = self.data.get("precipitation_sum", 0.0)
        precip_desc = self.data.get("precip_desc") or (
            "Осадков за 24 ч не ожидается." if is_ru else "No precipitation expected in 24h."
        )
        card_precip = self._create_bento_card(
            title="// Режим осадков" if is_ru else "// Precipitation",
            icon_file_name="rain-drop.svg",
            value_text=f"{precip_sum} мм" if is_ru else f"{precip_sum} mm",
            subtitle_text="За последние 24 ч" if is_ru else "Past 24 hours",
            desc_text=precip_desc,
            mode_id="precipitation",
        )
        grid.attach(card_precip, 0, 2, 4, 1)

        sunrise = self.data.get("sunrise_str", "06:00")
        sunset = self.data.get("sunset_str", "19:00")
        is_day = bool(self.data.get("is_day", 1))
        if is_day:
            sun_sub = f"Закат: {sunset}" if is_ru else f"Sunset: {sunset}"
        else:
            sun_sub = f"Восход: {sunrise}" if is_ru else f"Sunrise: {sunrise}"

        card_sun = self._create_bento_card(
            title="// Солнечный цикл" if is_ru else "// Solar Cycle",
            icon_file_name="sunset.svg" if is_day else "sunrise.svg",
            value_text=sunset if is_day else sunrise,
            subtitle_text=sun_sub,
            desc_text="Световой день продолжается." if is_ru else "Daylight in progress.",
            mode_id="sun",
            custom_widget=MiniSunCurve(sunrise, sunset, is_day),
        )
        grid.attach(card_sun, 4, 2, 3, 1)

        moon_data = self.data.get("moon_phase") or {}
        moon_name = moon_data.get("name_ru" if is_ru else "name_en") or (
            "Растущая Луна" if is_ru else "Waxing Moon"
        )
        moon_illum = round(moon_data.get("illumination", 50))
        cycle_frac = moon_data.get("cycle_fraction", 0.5)

        moon_widget = MiniMoonIcon(cycle_fraction=cycle_frac)
        moon_widget.set_size_request(24, 24)

        card_moon = self._create_bento_card(
            title="// Фаза Луны" if is_ru else "// Lunar Ephemeris",
            icon_file_name="moon.svg",
            value_text=moon_name,
            subtitle_text=f"Освещенность: {moon_illum}%" if is_ru else f"Illumination: {moon_illum}%",
            desc_text="Синодический цикл." if is_ru else "Synodic cycle.",
            mode_id="moon",
            custom_widget=moon_widget,
        )
        grid.attach(card_moon, 7, 2, 3, 1)

        # TIER 4: Full-Width Climatological Baseline Strip (spans 10 columns)
        avg_diff = self.data.get("avg_diff_str")
        clim_avg = self.data.get("climate_averages") or {}
        if not avg_diff or avg_diff in ("0° к норме", "0° vs norm"):
            diff_short = clim_avg.get("temp_diff_str_short")
            if diff_short:
                avg_diff = f"{diff_short} к норме" if is_ru else f"{diff_short} vs norm"
            elif clim_avg.get("temp_diff_str"):
                avg_diff = f"{clim_avg.get('temp_diff_str')}"
            else:
                avg_diff = "0° к норме" if is_ru else "0° vs norm"

        avg_desc = self.data.get("avg_desc") or clim_avg.get("summary_temp") or (
            "Температура около многолетней климатической нормы." if is_ru else "Temperature close to long-term climate average."
        )
        card_avg = self._create_climate_norm_bar(
            title="// Климатическая норма" if is_ru else "// Climate Baseline",
            icon_file_name="chart-norm.svg",
            value_text=avg_diff,
            subtitle_text="Многолетний базис" if is_ru else "Monthly baseline",
            desc_text=avg_desc,
            mode_id="averages",
            custom_widget=MiniClimateNormGauge(avg_diff),
        )
        grid.attach(card_avg, 0, 3, 10, 1)

        return grid

    def _create_climate_norm_bar(
        self,
        title: str,
        icon_file_name: str,
        value_text: str,
        subtitle_text: str,
        desc_text: str,
        mode_id: str,
        custom_widget: Gtk.Widget = None,
    ) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("weather-glass-card")
        card.add_css_class("weather-telemetry-full-card")
        card.add_css_class("weather-card-clickable")

        click = Gtk.GestureClick()
        click.connect("released", lambda *_, m=mode_id: self._open_mode(m))
        card.add_controller(click)

        # Header: icon + title
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hdr.add_css_class("weather-bento-header")
        icon_path = os.path.join(ICONS_DIR, icon_file_name)
        if os.path.exists(icon_path):
            img = Gtk.Image.new_from_file(icon_path)
            img.set_pixel_size(14)
            img.set_opacity(0.75)
            hdr.append(img)

        title_lbl = Gtk.Label(label=title)
        title_lbl.add_css_class("weather-bento-title")
        title_lbl.set_xalign(0.0)
        hdr.append(title_lbl)
        card.append(hdr)

        # Horizontal body
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        body.set_valign(Gtk.Align.CENTER)

        # Left: value + subtitle
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        val_lbl = Gtk.Label(label=value_text)
        val_lbl.add_css_class("weather-bento-val-hero")
        val_lbl.set_xalign(0.0)
        left_box.append(val_lbl)

        sub_lbl = Gtk.Label(label=subtitle_text)
        sub_lbl.add_css_class("weather-bento-val-level")
        sub_lbl.set_xalign(0.0)
        left_box.append(sub_lbl)
        body.append(left_box)

        # Center: description
        desc_lbl = Gtk.Label(label=desc_text)
        desc_lbl.add_css_class("weather-bento-desc")
        desc_lbl.set_wrap(True)
        desc_lbl.set_hexpand(True)
        desc_lbl.set_xalign(0.0)
        body.append(desc_lbl)

        # Right: gauge
        if custom_widget:
            custom_widget.set_valign(Gtk.Align.CENTER)
            body.append(custom_widget)

        card.append(body)
        return card

    def _create_bento_card(
        self,
        title: str,
        icon_file_name: str,
        value_text: str,
        subtitle_text: str,
        desc_text: str,
        mode_id: str,
        custom_widget: Gtk.Widget = None,
        is_wide: bool = False,
    ) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("weather-glass-card")
        card.add_css_class("weather-bento-card")
        card.add_css_class("weather-telemetry-card")
        card.add_css_class("weather-bento-card-interactive")
        card.add_css_class("weather-card-clickable")
        if is_wide:
            card.add_css_class("weather-bento-wide-card")

        # Click gesture to open mode in Level 2
        card_gesture = Gtk.GestureClick()
        card_gesture.connect("released", lambda *_, m=mode_id: self._open_mode(m))
        card.add_controller(card_gesture)

        # Header: Icon + Title (NO chevron arrow)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.add_css_class("weather-bento-header")

        icon_path = os.path.join(ICONS_DIR, icon_file_name)
        if os.path.exists(icon_path):
            img = Gtk.Image.new_from_file(icon_path)
            img.set_pixel_size(14)
            img.set_opacity(0.75)
            header_box.append(img)

        title_lbl = Gtk.Label(label=title)
        title_lbl.add_css_class("weather-bento-title")
        title_lbl.set_hexpand(True)
        title_lbl.set_xalign(0.0)
        header_box.append(title_lbl)

        card.append(header_box)

        # Value row with optional custom widget
        val_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        val_lbl = Gtk.Label(label=value_text)
        val_lbl.add_css_class("weather-bento-val-hero")
        val_lbl.set_xalign(0.0)
        val_lbl.set_hexpand(True)
        val_box.append(val_lbl)

        if custom_widget:
            custom_widget.set_valign(Gtk.Align.CENTER)
            val_box.append(custom_widget)

        card.append(val_box)

        # Subtitle / level
        if subtitle_text:
            sub_lbl = Gtk.Label(label=subtitle_text)
            sub_lbl.add_css_class("weather-bento-val-level")
            sub_lbl.set_xalign(0.0)
            card.append(sub_lbl)

        # Description text
        if desc_text:
            desc_lbl = Gtk.Label(label=desc_text)
            desc_lbl.add_css_class("weather-bento-desc")
            desc_lbl.set_wrap(True)
            desc_lbl.set_xalign(0.0)
            card.append(desc_lbl)

        return card
