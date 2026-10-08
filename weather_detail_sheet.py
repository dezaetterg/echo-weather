# Weather Detail Sheet - detailed meteorological view
import math
import os
from datetime import datetime, timedelta

import cairo

from logger import get_logger

logger = get_logger("weather_detail")
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk, Pango

from i18n import get_current_language, t
from providers.weather import (
    WEEKDAY_LETTERS,
    WMO_INFO,
    convert_temp,
    convert_temp_diff,
    format_full_date,
    format_temp,
    get_condition_text,
    get_smart_day_summary,
)

WEATHER_ICONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons', 'weather'))

def _get_icon_path(name: str) -> str:
    path = os.path.join(WEATHER_ICONS_DIR, name)
    return path if os.path.exists(path) else ''

def _hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))


from detail_cards import (
    BaseWeatherHourlyArea,
    ClimateMonthlyPrecipTable,
    ClimateMonthlyTempTable,
    ClimatePrecipChartArea,
    ClimateSunYearTable,
    ClimateTempChartArea,
    ComparisonBarArea,
    DayComparisonBarArea,
    HumidityHourlyArea,
    MiniMoonIcon,
    MoonCalendarCard,
    MoonTimelineRuler,
    PrecipCapsuleBarArea,
    PrecipitationBarArea,
    PrecipitationHourlyArea,
    PressureGaugeArea,
    PressureHourlyArea,
    SunArcChartArea,
    SunDaylightBar,
    TempCapsuleBarArea,
    UVHourlyArea,
    VisibilityHourlyArea,
    WeatherSplineArea,
    WindCompassArea,
    WindHourlyArea,
    build_averages_view,
    build_conditions_view,
    build_humidity_view,
    build_moon_view,
    build_precipitation_view,
    build_pressure_view,
    build_sun_view,
    build_uv_view,
    build_visibility_view,
    build_wind_view,
    create_moon_metric_row,
    create_sun_metric_row,
)
from weather_atmosphere import MoonSphereArea


def _get_beaufort_desc(spd: int | float, is_ru: bool) -> str:
    if spd < 6:
        return "Штиль / тихий" if is_ru else "Calm / Light air"
    elif spd < 20:
        return "Легкий / слабый" if is_ru else "Light / Gentle breeze"
    elif spd < 39:
        return "Умеренный / свежий" if is_ru else "Moderate / Fresh breeze"
    elif spd < 62:
        return "Сильный / крепкий" if is_ru else "Strong breeze / Gale"
    else:
        return "Шторм / буря" if is_ru else "Storm / Gale"


def _get_precip_desc(vol: float, prob: int, is_ru: bool) -> str:
    if vol <= 0 or prob == 0:
        return "Осадки маловероятны." if is_ru else "Precipitation unlikely."
    elif vol < 0.5:
        return "Небольшая морось / слабый дождь." if is_ru else "Light drizzle / light rain."
    elif vol < 2.5:
        return "Умеренный дождь." if is_ru else "Moderate rain."
    elif vol < 10.0:
        return "Сильный дождь." if is_ru else "Heavy rain."
    else:
        return "Очень сильный ливень." if is_ru else "Violent downpour."


def _get_dew_comfort(dew: float, is_ru: bool) -> str:
    if dew < 10:
        return "Сухой комфортный воздух." if is_ru else "Dry, comfortable air."
    elif dew < 16:
        return "Комфортно и приятно." if is_ru else "Comfortable conditions."
    elif dew < 19:
        return "Ощутимая влажность." if is_ru else "Noticeable humidity."
    elif dew < 22:
        return "Влажно и душно." if is_ru else "Humid and muggy."
    else:
        return "Очень душно и тяжело." if is_ru else "Very oppressive humidity."


def _get_vis_desc(vis: float, is_ru: bool) -> str:
    if vis >= 10.0:
        return "Идеальная прозрачность атмосферы." if is_ru else "Clear atmospheric conditions."
    elif vis >= 4.0:
        return "Хорошая видимость горизонта." if is_ru else "Good visibility."
    elif vis >= 1.0:
        return "Сниженная видимость из-за дымки или осадков." if is_ru else "Reduced visibility due to mist or rain."
    else:
        return "Опасная видимость из-за тумана." if is_ru else "Hazardous fog."


class WeatherDetailSheet(Gtk.Box):
    """Comprehensive meteorological deep-dive sheet with 10 specialized analysis modes."""

    MODES = [
        ('conditions', 'weather_mode_conditions', 'partly-cloudy-day.svg', 'weather-clouds-symbolic', 'Погодные условия', 'Температура и прогноз'),
        ('uv', 'weather_mode_uv', 'sun-uv.svg', 'weather-clear-symbolic', 'УФ-индекс', 'Солнечная активность и защита'),
        ('wind', 'weather_mode_wind', 'wind.svg', 'weather-windy-symbolic', 'Ветер', 'Скорость, порывы и направление'),
        ('precipitation', 'weather_mode_precipitation', 'umbrella.svg', 'weather-showers-symbolic', 'Осадки', 'Вероятность и объем в мм'),
        ('sun', 'weather_mode_sun', 'sunset.svg', 'weather-clear-symbolic', 'Восход солнца', 'Восход, закат и световой день'),
        ('moon', 'weather_mode_moon', 'moon.svg', 'weather-clear-night-symbolic', 'Фаза луны', 'Освещенность, восход и лунный календарь'),
        ('humidity', 'weather_mode_humidity', 'droplet.svg', 'weather-fog-symbolic', 'Влажность', 'Точка росы и зона комфорта'),
        ('visibility', 'weather_mode_visibility', 'eye.svg', 'find-location-symbolic', 'Видимость', 'Дальность обзора и дымка'),
        ('pressure', 'weather_mode_pressure', 'gauge.svg', 'speedometer-symbolic', 'Давление', 'Барометр и тенденция'),
        ('averages', 'weather_mode_averages', 'chart-norm.svg', 'utilities-system-monitor-symbolic', 'Средние значения', 'Климатическая норма и статистика')
    ]

    def __init__(self, data: dict, on_back_callback, initial_day_idx: int = 0, initial_mode: str = 'conditions', temp_unit: str = None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.data = data
        self.on_back_callback = on_back_callback
        self.days_detailed = list(data.get('days_detailed') or [])
        if not self.days_detailed and data.get('daily'):
            for idx, d in enumerate(data.get('daily', [])):
                self.days_detailed.append({
                    'day_index': idx,
                    'day_num': idx + 1,
                    'weekday_short': d.get('day', f'Day {idx + 1}'),
                    'min': d.get('min', 0),
                    'max': d.get('max', 20),
                    'code': d.get('code', 0),
                    'icon_file': d.get('icon_file', ''),
                    'hourly_temps': [d.get('min', 0)] * 24,
                })
        self.selected_day_idx = max(0, min(initial_day_idx, max(0, len(self.days_detailed) - 1)))
        self.current_mode = initial_mode if any(m[0] == initial_mode for m in self.MODES) else 'conditions'
        self.show_feels_like = False
        self.bg_class = data.get('bg_class', 'weather-bg-clear-day')
        if not temp_unit:
            try:
                from config_manager import ConfigManager
                temp_unit = data.get('temp_unit') or ConfigManager().get('temperature_unit', 'celsius')
            except Exception:
                temp_unit = data.get('temp_unit') or 'celsius'
        self.temp_unit = temp_unit

        self.add_css_class('weather-detail-view')
        self.add_css_class(self.bg_class)
        self.set_vexpand(True)
        self.set_hexpand(True)

        self._build_ui()

    def _build_ui(self):
        is_ru = (get_current_language() == 'ru')

        # 1. Top Navigation Bar (Gtk.CenterBox)
        nav_bar = Gtk.CenterBox()
        nav_bar.add_css_class('weather-nav-bar')

        # Back Button: [ ← Назад ]
        self.btn_back = Gtk.Button()
        self.btn_back.add_css_class('weather-back-btn')
        btn_back_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        arrow_icon = Gtk.Image.new_from_icon_name('go-previous-symbolic')
        arrow_icon.set_pixel_size(13)
        btn_back_box.append(arrow_icon)
        self.lbl_back = Gtk.Label(label=t('weather_back'))
        self.lbl_back.add_css_class('weather-back-label')
        btn_back_box.append(self.lbl_back)
        self.btn_back.set_child(btn_back_box)
        self.btn_back.connect('clicked', lambda _: self._on_back())
        nav_bar.set_start_widget(self.btn_back)

        # Center Title (strictly centered in window)
        self.lbl_nav_title = Gtk.Label(label=t(f'weather_mode_{self.current_mode}'))
        self.lbl_nav_title.add_css_class('weather-nav-title')
        nav_bar.set_center_widget(self.lbl_nav_title)

        self.append(nav_bar)

        # 2. Scrolled Window Container
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.add_css_class('weather-detail-scroll')
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_vexpand(True)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.content_box.set_valign(Gtk.Align.START)
        self.content_box.add_css_class('weather-detail-content')

        # 3. Horizontal Day Strip
        self.strip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.strip_box.add_css_class('weather-day-strip')
        self.strip_box.set_halign(Gtk.Align.CENTER)
        self._build_day_strip()
        self.content_box.append(self.strip_box)

        # 4. Date Subtitle
        self.lbl_date_sub = Gtk.Label()
        self.lbl_date_sub.add_css_class('weather-detail-date')
        self.lbl_date_sub.set_halign(Gtk.Align.START)
        self.content_box.append(self.lbl_date_sub)

        # 5. Dynamic Hero Metric Row
        self.hero_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.hero_row.add_css_class('weather-detail-hero-row')

        self.hero_left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.hero_left.set_hexpand(True)
        self.hero_left.set_halign(Gtk.Align.START)

        self.lbl_hero_time = Gtk.Label(label='')
        self.lbl_hero_time.add_css_class('weather-detail-scrub-time')
        self.lbl_hero_time.set_halign(Gtk.Align.START)
        self.lbl_hero_time.set_visible(False)
        self.hero_left.append(self.lbl_hero_time)

        hero_mid_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hero_mid_row.set_halign(Gtk.Align.START)

        self.lbl_hero_main = Gtk.Label(label='--°')
        self.lbl_hero_main.add_css_class('weather-detail-hero-temp')
        hero_mid_row.append(self.lbl_hero_main)

        self.hero_icon = Gtk.Image()
        self.hero_icon.set_pixel_size(28)
        hero_mid_row.append(self.hero_icon)

        self.lbl_hero_sub = Gtk.Label(label='↓ --° ↑ --°')
        self.lbl_hero_sub.add_css_class('weather-detail-hero-extremes')
        self.lbl_hero_sub.set_valign(Gtk.Align.CENTER)
        hero_mid_row.append(self.lbl_hero_sub)

        self.hero_left.append(hero_mid_row)
        self.hero_row.append(self.hero_left)

        # Dedicated Hero block for Sun mode
        self.hero_sun_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.hero_sun_box.add_css_class('weather-sun-hero-box')
        self.hero_sun_box.set_hexpand(True)
        self.hero_sun_box.set_halign(Gtk.Align.START)
        self.hero_sun_box.set_visible(False)

        self.lbl_sun_hero_time = Gtk.Label(label='06:40')
        self.lbl_sun_hero_time.add_css_class('weather-sun-hero-title')
        self.lbl_sun_hero_time.set_xalign(0.0)
        self.hero_sun_box.append(self.lbl_sun_hero_time)

        self.lbl_sun_hero_sub = Gtk.Label(label='Световой день: -- ч -- мин' if is_ru else 'Daylight: -- h -- min')
        self.lbl_sun_hero_sub.add_css_class('weather-sun-hero-sub')
        self.lbl_sun_hero_sub.set_xalign(0.0)
        self.hero_sun_box.append(self.lbl_sun_hero_sub)

        self.hero_row.append(self.hero_sun_box)

        # Dedicated Hero block for Moon mode
        self.hero_moon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.hero_moon_box.add_css_class('weather-moon-hero-box')
        self.hero_moon_box.set_hexpand(True)
        self.hero_moon_box.set_halign(Gtk.Align.START)
        self.hero_moon_box.set_visible(False)

        hero_moon_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.lbl_moon_hero_title = Gtk.Label(label=t('weather_moon_phase_waxing_crescent'))
        self.lbl_moon_hero_title.add_css_class('weather-moon-hero-title')
        self.lbl_moon_hero_title.set_xalign(0.0)
        hero_moon_top.append(self.lbl_moon_hero_title)

        self.btn_moon_reset = Gtk.Button(label='↺')
        self.btn_moon_reset.add_css_class('weather-moon-reset-btn')
        self.btn_moon_reset.set_tooltip_text(t('weather_reset_now'))
        self.btn_moon_reset.set_valign(Gtk.Align.CENTER)
        self.btn_moon_reset.set_visible(False)
        self.btn_moon_reset.connect('clicked', lambda b: self._on_moon_reset_clicked())
        hero_moon_top.append(self.btn_moon_reset)

        self.hero_moon_box.append(hero_moon_top)

        self.lbl_moon_hero_sub = Gtk.Label(label=t('weather_moon_illum_title', val='--'))
        self.lbl_moon_hero_sub.add_css_class('weather-moon-hero-sub')
        self.lbl_moon_hero_sub.set_xalign(0.0)
        self.hero_moon_box.append(self.lbl_moon_hero_sub)

        self.hero_row.append(self.hero_moon_box)

        # Metric MenuButton with Popover [ ☁ Погодные условия ⌄ ]
        self._build_metric_menu_button()
        self.hero_row.append(self.metric_menu_btn)

        self.content_box.append(self.hero_row)

        # 6. Mode Stack (7 Specialized Meteorological Views)
        self.mode_stack = Gtk.Stack()
        self.mode_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.mode_stack.set_transition_duration(280)
        self.mode_stack.set_interpolate_size(True)
        self.mode_stack.set_vhomogeneous(False)
        self.mode_stack.set_hhomogeneous(False)

        self._build_conditions_view()
        self._build_uv_view()
        self._build_wind_view()
        self._build_precipitation_view()
        self._build_humidity_view()
        self._build_visibility_view()
        self._build_pressure_view()
        self._build_averages_view()
        self._build_sun_view()
        self._build_moon_view()

        self.content_box.append(self.mode_stack)

        self.scroll.set_child(self.content_box)
        self.append(self.scroll)

        # Set initial mode and day
        self.set_mode(self.current_mode)

    def _build_metric_menu_button(self):
        is_ru = (get_current_language() == 'ru')

        self.metric_menu_btn = Gtk.MenuButton()
        self.metric_menu_btn.add_css_class('weather-metric-pill-btn')
        if hasattr(self, 'bg_class') and self.bg_class:
            self.metric_menu_btn.add_css_class(self.bg_class)
        self.metric_menu_btn.set_halign(Gtk.Align.END)
        self.metric_menu_btn.set_hexpand(True)

        pill_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.lbl_metric_icon = Gtk.Image()
        self.lbl_metric_icon.set_pixel_size(14)
        pill_box.append(self.lbl_metric_icon)

        self.lbl_metric_label = Gtk.Label(label=t(f'weather_mode_{self.current_mode}'))
        self.lbl_metric_label.add_css_class('weather-metric-label')
        pill_box.append(self.lbl_metric_label)

        chevron = Gtk.Image.new_from_icon_name('pan-down-symbolic')
        chevron.set_pixel_size(10)
        pill_box.append(chevron)

        self.metric_menu_btn.set_child(pill_box)

        # Popover setup
        self.popover = Gtk.Popover()
        self.popover.add_css_class('weather-metric-popover')
        if hasattr(self, 'bg_class') and self.bg_class:
            self.popover.add_css_class(self.bg_class)

        popover_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        popover_list.add_css_class('weather-popover-list')

        self.popover_items = {}

        for mode_id, trans_key, icon_svg, sym_icon, title_fallback, desc_fallback in self.MODES:
            btn_item = Gtk.Button()
            btn_item.add_css_class('weather-popover-item')

            item_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

            # Icon
            svg_path = _get_icon_path(icon_svg)
            if svg_path:
                img = Gtk.Image.new_from_file(svg_path)
            else:
                img = Gtk.Image.new_from_icon_name(sym_icon)
            img.set_pixel_size(18)
            item_box.append(img)

            # Text
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text_box.set_hexpand(True)
            text_box.set_halign(Gtk.Align.START)

            lbl_title = Gtk.Label(label=t(trans_key))
            lbl_title.add_css_class('weather-popover-title')
            lbl_title.set_xalign(0.0)
            text_box.append(lbl_title)

            desc_txt = t(f"weather_mode_desc_{mode_id}")
            if desc_txt == f"weather_mode_desc_{mode_id}":
                desc_txt = desc_fallback
            lbl_desc = Gtk.Label(label=desc_txt)
            lbl_desc.add_css_class('weather-popover-desc')
            lbl_desc.set_xalign(0.0)
            text_box.append(lbl_desc)

            item_box.append(text_box)
            btn_item.set_child(item_box)

            def _make_click_handler(m_id):
                return lambda _: (self.popover.popdown(), self.set_mode(m_id))

            btn_item.connect('clicked', _make_click_handler(mode_id))
            popover_list.append(btn_item)
            self.popover_items[mode_id] = btn_item

        self.popover.set_child(popover_list)
        self.metric_menu_btn.set_popover(self.popover)

    def apply_weather_theme(self, bg_class: str):
        theme_classes = [
            'weather-bg-clear-day', 'weather-bg-clear-night',
            'weather-bg-clouds-day', 'weather-bg-clouds-night',
            'weather-bg-rain-day', 'weather-bg-rain-night',
            'weather-bg-drizzle-day', 'weather-bg-drizzle-night',
            'weather-bg-storm-day', 'weather-bg-storm-night',
            'weather-bg-snow-day', 'weather-bg-snow-night',
            'weather-bg-fog-day', 'weather-bg-fog-night'
        ]
        for c in theme_classes:
            self.remove_css_class(c)
            if hasattr(self, 'popover') and self.popover:
                self.popover.remove_css_class(c)
            if hasattr(self, 'metric_menu_btn') and self.metric_menu_btn:
                self.metric_menu_btn.remove_css_class(c)
        self.bg_class = bg_class
        self.add_css_class(bg_class)
        if hasattr(self, 'popover') and self.popover:
            self.popover.add_css_class(bg_class)
        if hasattr(self, 'metric_menu_btn') and self.metric_menu_btn:
            self.metric_menu_btn.add_css_class(bg_class)
        if hasattr(self, 'spline_area') and self.spline_area:
            self.spline_area.bg_class = bg_class
            self.spline_area.queue_draw()

    def set_mode(self, mode_id: str):
        if not any(m[0] == mode_id for m in self.MODES):
            mode_id = 'conditions'
        self.current_mode = mode_id

        # Update button label & icon
        self.lbl_metric_label.set_label(t(f'weather_mode_{mode_id}'))
        self.lbl_nav_title.set_label(t(f'weather_mode_{mode_id}'))

        # Find mode info
        m_info = next(m for m in self.MODES if m[0] == mode_id)
        svg_path = _get_icon_path(m_info[2])
        if svg_path:
            self.lbl_metric_icon.set_from_file(svg_path)
        else:
            self.lbl_metric_icon.set_from_icon_name(m_info[3])

        # Update popover items active class
        for mid, b in self.popover_items.items():
            if mid == mode_id:
                b.add_css_class('weather-popover-item-active')
            else:
                b.remove_css_class('weather-popover-item-active')

        # Switch visible stack child
        if mode_id == 'sun':
            self.strip_box.set_visible(False)
            self.lbl_date_sub.set_visible(False)
            if hasattr(self, 'hero_left'):
                self.hero_left.set_visible(False)
            if hasattr(self, 'hero_sun_box'):
                self.hero_sun_box.set_visible(True)
            if hasattr(self, 'hero_moon_box'):
                self.hero_moon_box.set_visible(False)
            self.metric_menu_btn.set_valign(Gtk.Align.START)
        elif mode_id == 'moon':
            self.strip_box.set_visible(False)
            self.lbl_date_sub.set_visible(False)
            if hasattr(self, 'hero_left'):
                self.hero_left.set_visible(False)
            if hasattr(self, 'hero_sun_box'):
                self.hero_sun_box.set_visible(False)
            if hasattr(self, 'hero_moon_box'):
                self.hero_moon_box.set_visible(True)
            self.metric_menu_btn.set_valign(Gtk.Align.START)
        elif mode_id == 'averages':
            self.strip_box.set_visible(False)
            self.lbl_date_sub.set_visible(False)
            if hasattr(self, 'hero_left'):
                self.hero_left.set_visible(False)
            if hasattr(self, 'hero_sun_box'):
                self.hero_sun_box.set_visible(False)
            if hasattr(self, 'hero_moon_box'):
                self.hero_moon_box.set_visible(False)
            self.metric_menu_btn.set_valign(Gtk.Align.CENTER)
        else:
            self.strip_box.set_visible(True)
            self.lbl_date_sub.set_visible(True)
            if hasattr(self, 'hero_left'):
                self.hero_left.set_visible(True)
            if hasattr(self, 'hero_sun_box'):
                self.hero_sun_box.set_visible(False)
            if hasattr(self, 'hero_moon_box'):
                self.hero_moon_box.set_visible(False)
            self.metric_menu_btn.set_valign(Gtk.Align.CENTER)
        self.mode_stack.set_visible_child_name(mode_id)
        if hasattr(self, 'mode_stack') and self.mode_stack:
            self._refresh_selected_day()

    def retranslate(self):
        lang = get_current_language()
        is_ru = (lang == 'ru')
        if hasattr(self, 'lbl_back') and self.lbl_back:
            self.lbl_back.set_label(t('weather_back'))
        if hasattr(self, 'lbl_metric_label') and self.lbl_metric_label:
            self.lbl_metric_label.set_label(t(f'weather_mode_{self.current_mode}'))
        if hasattr(self, 'lbl_nav_title') and self.lbl_nav_title:
            self.lbl_nav_title.set_label(t(f'weather_mode_{self.current_mode}'))
        if hasattr(self, 'popover_items'):
            for mode_id, trans_key, icon_svg, sym_icon, title_fallback, desc_fallback in self.MODES:
                btn_item = self.popover_items.get(mode_id)
                if btn_item:
                    item_box = btn_item.get_child()
                    if item_box:
                        text_box = item_box.get_last_child()
                        if text_box:
                            lbl_t = text_box.get_first_child()
                            if lbl_t:
                                lbl_t.set_label(t(trans_key))
                            lbl_d = text_box.get_last_child()
                            if lbl_d:
                                desc_txt = t(f"weather_mode_desc_{mode_id}")
                                if desc_txt == f"weather_mode_desc_{mode_id}":
                                    desc_txt = desc_fallback
                                lbl_d.set_label(desc_txt)
        if hasattr(self, 'btn_seg_actual') and self.btn_seg_actual:
            self.btn_seg_actual.set_label(t('weather_btn_actual'))
        if hasattr(self, 'btn_seg_feels') and self.btn_seg_feels:
            self.btn_seg_feels.set_label(t('weather_btn_feels_like'))
        if hasattr(self, 'lbl_seg_desc') and self.lbl_seg_desc:
            desc = t('weather_desc_feels_temp') if getattr(self, 'show_feels_like', False) else t('weather_desc_actual_temp')
            self.lbl_seg_desc.set_label(desc)

        # Conditions cards titles and labels
        if hasattr(self, 'lbl_sum_title') and self.lbl_sum_title:
            self.lbl_sum_title.set_label(t('weather_card_forecast'))
        if hasattr(self, 'lbl_comp_title') and self.lbl_comp_title:
            self.lbl_comp_title.set_label(t('weather_card_day_comparison'))
        if hasattr(self, 'lbl_pr_title') and self.lbl_pr_title:
            self.lbl_pr_title.set_label(t('weather_card_precip_probability'))
        if hasattr(self, 'lbl_pr_foot') and self.lbl_pr_foot:
            self.lbl_pr_foot.set_label(t('weather_precip_explanation'))
        if hasattr(self, 'lbl_vol_title') and self.lbl_vol_title:
            self.lbl_vol_title.set_label(t('weather_card_precip_volume'))
        if hasattr(self, 'lbl_v1_desc') and self.lbl_v1_desc:
            self.lbl_v1_desc.set_label(t('weather_card_expected_daily'))
        if hasattr(self, 'lbl_edu_title') and self.lbl_edu_title:
            self.lbl_edu_title.set_label(t('weather_card_about_feels_like'))
        if hasattr(self, 'lbl_edu_text') and self.lbl_edu_text:
            self.lbl_edu_text.set_label(t('weather_desc_about_feels_like'))

        # Update day strip letters across languages
        self._update_day_strip_labels()

        # Smoothly reset scroll to top when changing modes to avoid jarring visual jumps
        if hasattr(self, 'scroll') and self.scroll:
            adj = self.scroll.get_vadjustment()
            if adj:
                cur_val = adj.get_value()
                if cur_val > 1.0:
                    steps = 8
                    delta = cur_val / steps
                    step_count = 0

                    def _smooth_scroll_step():
                        nonlocal step_count
                        step_count += 1
                        new_val = max(0.0, cur_val - delta * step_count)
                        adj.set_value(new_val)
                        if step_count < steps and new_val > 0.0:
                            return GLib.SOURCE_CONTINUE
                        return GLib.SOURCE_REMOVE

                    GLib.timeout_add(16, _smooth_scroll_step)

        # Refresh day content
        self._refresh_selected_day()

    def update_metrics(self):
        self._refresh_selected_day()

    def _build_day_strip(self):
        while child := self.strip_box.get_first_child():
            self.strip_box.remove(child)

        self.day_buttons = []
        lang = get_current_language()
        letters = WEEKDAY_LETTERS.get(lang, WEEKDAY_LETTERS['en'])

        for idx, day_info in enumerate(self.days_detailed):
            btn = Gtk.Button()
            btn.add_css_class('weather-day-tab')
            if idx == self.selected_day_idx:
                btn.add_css_class('weather-day-tab-active')

            tab_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            tab_box.add_css_class('weather-day-tab-content')

            dt = None
            date_str = day_info.get('date_str')
            if date_str:
                try:
                    dt = datetime.strptime(date_str.split('T')[0], "%Y-%m-%d")
                except (ValueError, TypeError) as e:
                    logger.debug("Failed parsing date %s: %s", date_str, e)
            if dt is None:
                dt = datetime.now() + timedelta(days=idx)
            w_idx = dt.weekday()
            w_letter = letters[w_idx % 7]

            lbl_letter = Gtk.Label(label=w_letter)
            lbl_letter.add_css_class('weather-tab-letter')
            tab_box.append(lbl_letter)

            lbl_num = Gtk.Label(label=str(dt.day))
            lbl_num.add_css_class('weather-tab-num')
            tab_box.append(lbl_num)

            btn.lbl_letter = lbl_letter
            btn.day_dt = dt
            btn.day_info = day_info

            btn.set_child(tab_box)
            btn.connect('clicked', lambda _, d_i=idx: self.select_day(d_i))
            self.strip_box.append(btn)
            self.day_buttons.append(btn)

    def _update_day_strip_labels(self):
        lang = get_current_language()
        letters = WEEKDAY_LETTERS.get(lang, WEEKDAY_LETTERS['en'])
        for idx, btn in enumerate(getattr(self, 'day_buttons', [])):
            dt = getattr(btn, 'day_dt', None)
            if dt is None:
                date_str = getattr(btn, 'day_info', {}).get('date_str')
                if date_str:
                    try:
                        dt = datetime.strptime(date_str.split('T')[0], "%Y-%m-%d")
                    except (ValueError, TypeError) as e:
                        logger.debug("Failed parsing date %s: %s", date_str, e)
            if dt:
                w_idx = dt.weekday()
            else:
                w_idx = (datetime.now().weekday() + idx) % 7
            if hasattr(btn, 'lbl_letter') and btn.lbl_letter:
                btn.lbl_letter.set_label(letters[w_idx % 7])

    def select_day(self, day_idx: int):
        if 0 <= day_idx < len(self.days_detailed):
            self.selected_day_idx = day_idx
            for i, b in enumerate(self.day_buttons):
                if i == day_idx:
                    b.add_css_class('weather-day-tab-active')
                else:
                    b.remove_css_class('weather-day-tab-active')
            self._refresh_selected_day()

    def set_temp_unit(self, unit: str):
        self.temp_unit = unit
        self._refresh_selected_day()
        if self.current_mode == 'averages':
            self._refresh_averages_view()

    def _on_back(self):
        if callable(self.on_back_callback):
            self.on_back_callback()

    def _build_conditions_view(self):
        build_conditions_view(self)

    def _set_feels_like_mode(self, feels_like: bool):
        self.show_feels_like = feels_like
        if feels_like:
            self.btn_seg_feels.add_css_class('segmented-btn-active')
            self.btn_seg_actual.remove_css_class('segmented-btn-active')
            self.lbl_seg_desc.set_label(t('weather_desc_feels_temp'))
        else:
            self.btn_seg_actual.add_css_class('segmented-btn-active')
            self.btn_seg_feels.remove_css_class('segmented-btn-active')
            self.lbl_seg_desc.set_label(t('weather_desc_actual_temp'))
        self.spline_area.set_feels_like(feels_like)

    def _on_spline_scrub(self, data: dict):
        if not data.get('active'):
            if hasattr(self, 'lbl_hero_time'):
                self.lbl_hero_time.set_visible(False)
            self._refresh_selected_day()
            return

        lang = get_current_language()
        time_str = data.get('time_str', '')
        temp = data.get('temp', 0)
        other_temp = data.get('other_temp', 0)
        icon_path = data.get('icon_path', '')
        show_feels = data.get('show_feels_like', False)

        if hasattr(self, 'lbl_hero_time'):
            self.lbl_hero_time.set_label(time_str)
            self.lbl_hero_time.set_visible(True)

        self.lbl_hero_main.set_label(f"{temp}°")

        if icon_path and os.path.exists(icon_path):
            self.hero_icon.set_from_file(icon_path)
            self.hero_icon.set_visible(True)

        if not show_feels:
            self.lbl_hero_sub.set_label(t('weather_feels_like_prefix', temp=f"{other_temp}°"))
        else:
            self.lbl_hero_sub.set_label(f"{t('weather_btn_actual')}: {other_temp}°")

        code = data.get('weather_code', 0)
        cond_str = get_condition_text(code, lang=lang, is_day=True)

        if hasattr(self, 'lbl_cond_sum_time'):
            self.lbl_cond_sum_time.set_label(t('weather_scrub_at_time', time=time_str))
            self.lbl_cond_sum_text.set_label(
                t('weather_scrub_conditions_text', cond=cond_str, temp=temp, other=other_temp)
            )

        if hasattr(self, 'lbl_summary_text'):
            self.lbl_summary_text.set_label(
                t('weather_scrub_summary_text', time=time_str, cond=cond_str, temp=temp, other=other_temp)
            )

    def _on_uv_scrub(self, data: dict):
        if not data.get('active'):
            if hasattr(self, 'lbl_hero_time'):
                self.lbl_hero_time.set_visible(False)
            self._refresh_selected_day()
            return

        is_ru = (get_current_language() == 'ru')
        time_str = data.get('time_str', '')
        uv_val = data.get('uv_val', 0.0)

        if hasattr(self, 'lbl_hero_time'):
            self.lbl_hero_time.set_label(time_str)
            self.lbl_hero_time.set_visible(True)

        self.lbl_hero_main.set_label(f"{uv_val:.1f}")

        if uv_val <= 2.9:
            uv_name = 'Низкий' if is_ru else 'Low'
            adv = 'Защита от солнца не требуется, безопасно находиться на открытом воздухе.' if is_ru else 'No sun protection required, safe outdoors.'
        elif uv_val <= 5.9:
            uv_name = 'Умеренный' if is_ru else 'Moderate'
            adv = 'Рекомендуется защита: наносите крем SPF 30+, надевайте очки и головной убор.' if is_ru else 'Protection recommended: SPF 30+ sunscreen, sunglasses and a hat.'
        elif uv_val <= 7.9:
            uv_name = 'Высокий' if is_ru else 'High'
            adv = 'Высокий уровень: оставайтесь в тени в полуденные часы, используйте крем SPF 50+.' if is_ru else 'High level: stay in shade during midday, use SPF 50+ sunscreen.'
        elif uv_val <= 10.9:
            uv_name = 'Очень высокий' if is_ru else 'Very High'
            adv = 'Очень высокий уровень: избегайте прямого солнца, риск быстрого ожога.' if is_ru else 'Very high level: avoid direct sun, risk of rapid sunburn.'
        else:
            uv_name = 'Экстремальный' if is_ru else 'Extreme'
            adv = 'Экстремальный уровень: оставайтесь в помещении или в густой тени.' if is_ru else 'Extreme level: stay indoors or in deep shade.'

        if self.current_mode == 'averages':
            self._refresh_averages_view()
            return
        if self.current_mode == 'sun':
            self._refresh_sun_view()
            return
        if self.current_mode == 'moon':
            self._refresh_moon_view()
            return
        if self.current_mode == 'moon':
            self._refresh_moon_view()
            return
        cur_day = self.days_detailed[self.selected_day_idx] if self.days_detailed and self.selected_day_idx < len(self.days_detailed) else {}
        peak_val = cur_day.get('uv_max', uv_val)
        self.lbl_hero_sub.set_label(f"{uv_name} • Пик {peak_val:.1f}" if is_ru else f"{uv_name} • Peak {peak_val:.1f}")

        if hasattr(self, 'lbl_uv_sum_time'):
            self.lbl_uv_sum_time.set_label(f"В {time_str}" if is_ru else f"At {time_str}")
            self.lbl_uv_sum_text.set_label(f"УФ-индекс: {uv_val:.1f} ({uv_name}). {adv}" if is_ru else f"UV Index: {uv_val:.1f} ({uv_name}). {adv}")

    def _on_wind_scrub(self, data: dict):
        if not data.get('active'):
            if hasattr(self, 'lbl_hero_time'):
                self.lbl_hero_time.set_visible(False)
            self._refresh_selected_day()
            return

        is_ru = (get_current_language() == 'ru')
        time_str = data.get('time_str', '')
        spd = data.get('speed', 0)
        gust = data.get('gust', 0)
        dir_deg = data.get('direction', 0)

        dirs_ru = ['С', 'ССВ', 'СВ', 'ВСВ', 'В', 'ВЮВ', 'ЮВ', 'ЮЮВ', 'Ю', 'ЮЮЗ', 'ЮЗ', 'ЗЮЗ', 'З', 'ЗСЗ', 'СЗ', 'ССЗ']
        dirs_en = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        c_idx = int((dir_deg + 11.25) / 22.5) % 16
        cardinal = dirs_ru[c_idx] if is_ru else dirs_en[c_idx]

        if hasattr(self, 'lbl_hero_time'):
            self.lbl_hero_time.set_label(time_str)
            self.lbl_hero_time.set_visible(True)

        self.lbl_hero_main.set_label(f"{spd} км/ч" if is_ru else f"{spd} km/h")
        self.lbl_hero_sub.set_label(f"{cardinal} ({dir_deg}°) • Порывы до {gust} км/ч" if is_ru else f"{cardinal} ({dir_deg}°) • Gusts to {gust} km/h")

        if hasattr(self, 'wind_compass_area') and self.wind_compass_area:
            self.wind_compass_area.update_data(spd, gust, dir_deg)

        if hasattr(self, 'lbl_wind_sum_time'):
            self.lbl_wind_sum_time.set_label(f"В {time_str}" if is_ru else f"At {time_str}")
            b_desc = _get_beaufort_desc(spd, is_ru)
            self.lbl_wind_sum_text.set_label(f"Ветер {spd} км/ч ({b_desc}), порывы до {gust} км/ч. Направление: {cardinal} ({dir_deg}°)." if is_ru else f"Wind {spd} km/h ({b_desc}), gusts up to {gust} km/h. Direction: {cardinal} ({dir_deg}°).")

    def _on_precip_scrub(self, data: dict):
        if not data.get('active'):
            if hasattr(self, 'lbl_hero_time'):
                self.lbl_hero_time.set_visible(False)
            self._refresh_selected_day()
            return

        is_ru = (get_current_language() == 'ru')
        time_str = data.get('time_str', '')
        vol = data.get('precip', 0.0)
        prob = data.get('prob', 0)

        if hasattr(self, 'lbl_hero_time'):
            self.lbl_hero_time.set_label(time_str)
            self.lbl_hero_time.set_visible(True)

        self.lbl_hero_main.set_label(f"{vol:.1f} мм" if is_ru else f"{vol:.1f} mm")
        self.lbl_hero_sub.set_label(f"Вероятность {prob}%" if is_ru else f"Probability {prob}%")

        if hasattr(self, 'lbl_precip_sum_time'):
            self.lbl_precip_sum_time.set_label(f"В {time_str}" if is_ru else f"At {time_str}")
            p_desc = _get_precip_desc(vol, prob, is_ru)
            self.lbl_precip_sum_text.set_label(f"Интенсивность: {vol:.1f} мм/ч, вероятность {prob}%. {p_desc}" if is_ru else f"Rate: {vol:.1f} mm/h, chance {prob}%. {p_desc}")

    def _on_humidity_scrub(self, data: dict):
        if not data.get('active'):
            if hasattr(self, 'lbl_hero_time'):
                self.lbl_hero_time.set_visible(False)
            self._refresh_selected_day()
            return

        is_ru = (get_current_language() == 'ru')
        time_str = data.get('time_str', '')
        hum = data.get('humidity', 0)
        raw_dew = data.get('dew_point', 0)
        dew = convert_temp(raw_dew, self.temp_unit)
        dew_unit_sym = "°F" if self.temp_unit == "fahrenheit" else "°C"

        if hasattr(self, 'lbl_hero_time'):
            self.lbl_hero_time.set_label(time_str)
            self.lbl_hero_time.set_visible(True)

        self.lbl_hero_main.set_label(f"{hum}%")
        self.lbl_hero_sub.set_label(f"Точка росы {dew}{dew_unit_sym}" if is_ru else f"Dew point {dew}{dew_unit_sym}")

        if hasattr(self, 'lbl_hum_sum_time'):
            self.lbl_hum_sum_time.set_label(f"В {time_str}" if is_ru else f"At {time_str}")
            c_desc = _get_dew_comfort(raw_dew, is_ru)
            self.lbl_hum_sum_text.set_label(f"Относительная влажность: {hum}%, точка росы {dew}{dew_unit_sym}. {c_desc}" if is_ru else f"Relative humidity: {hum}%, dew point {dew}{dew_unit_sym}. {c_desc}")

    def _on_vis_scrub(self, data: dict):
        if not data.get('active'):
            if hasattr(self, 'lbl_hero_time'):
                self.lbl_hero_time.set_visible(False)
            self._refresh_selected_day()
            return

        is_ru = (get_current_language() == 'ru')
        time_str = data.get('time_str', '')
        vis = data.get('visibility', 10.0)

        if hasattr(self, 'lbl_hero_time'):
            self.lbl_hero_time.set_label(time_str)
            self.lbl_hero_time.set_visible(True)

        self.lbl_hero_main.set_label(f"{vis:.1f} км" if is_ru else f"{vis:.1f} km")
        if vis >= 10.0:
            quality = 'Отличная' if is_ru else 'Excellent'
        elif vis >= 4.0:
            quality = 'Хорошая' if is_ru else 'Moderate'
        elif vis >= 1.0:
            quality = 'Сниженная (дымка)' if is_ru else 'Reduced (Mist)'
        else:
            quality = 'Густой туман' if is_ru else 'Dense Fog'
        self.lbl_hero_sub.set_label(f"{quality} видимость" if is_ru else f"{quality} visibility")

        if hasattr(self, 'lbl_vis_sum_time'):
            self.lbl_vis_sum_time.set_label(f"В {time_str}" if is_ru else f"At {time_str}")
            v_desc = _get_vis_desc(vis, is_ru)
            self.lbl_vis_sum_text.set_label(f"Видимость: {vis:.1f} км ({quality}). {v_desc}" if is_ru else f"Visibility: {vis:.1f} km ({quality}). {v_desc}")

    def _on_press_scrub(self, data: dict):
        if not data.get('active'):
            if hasattr(self, 'lbl_hero_time'):
                self.lbl_hero_time.set_visible(False)
            self._refresh_selected_day()
            return

        is_ru = (get_current_language() == 'ru')
        time_str = data.get('time_str', '')
        p_val = data.get('pressure_mm', 750)
        p_hpa = data.get('pressure_hpa', 1000)

        if hasattr(self, 'lbl_hero_time'):
            self.lbl_hero_time.set_label(time_str)
            self.lbl_hero_time.set_visible(True)

        self.lbl_hero_main.set_label(f"{p_val} мм" if is_ru else f"{p_val} mmHg")
        if p_val < 745:
            stat = 'Пониженное' if is_ru else 'Low'
        elif p_val <= 765:
            stat = 'Нормальное' if is_ru else 'Normal'
        else:
            stat = 'Повышенное' if is_ru else 'High'
        self.lbl_hero_sub.set_label(f"{stat} • {p_hpa} гПа" if is_ru else f"{stat} • {p_hpa} hPa")

        if hasattr(self, 'pressure_gauge_area') and self.pressure_gauge_area:
            self.pressure_gauge_area.update_data(p_val, p_hpa)

        if hasattr(self, 'lbl_press_sum_time'):
            self.lbl_press_sum_time.set_label(f"В {time_str}" if is_ru else f"At {time_str}")
            self.lbl_press_sum_text.set_label(f"Давление: {p_val} мм рт. ст. ({p_hpa} гПа) — {stat}. Атмосфера стабильна." if is_ru else f"Pressure: {p_val} mmHg ({p_hpa} hPa) — {stat}. Atmosphere is stable.")

    def _build_uv_view(self):
        build_uv_view(self)

    def _build_wind_view(self):
        build_wind_view(self)

    def _build_precipitation_view(self):
        build_precipitation_view(self)

    def _build_humidity_view(self):
        build_humidity_view(self)

    def _build_visibility_view(self):
        build_visibility_view(self)

    def _build_pressure_view(self):
        build_pressure_view(self)

    def _refresh_selected_day(self):
        if self.current_mode == 'averages':
            self._refresh_averages_view()
            return
        if self.current_mode == 'sun':
            self._refresh_sun_view()
            return
        if self.current_mode == 'moon':
            self._refresh_moon_view()
            return

        if not self.days_detailed or self.selected_day_idx >= len(self.days_detailed):
            return

        if hasattr(self, 'lbl_hero_time'):
            self.lbl_hero_time.set_visible(False)

        cur_day = self.days_detailed[self.selected_day_idx]
        lang = get_current_language()
        is_ru = (lang == 'ru')
        is_today = cur_day.get('is_today', False) or (self.selected_day_idx == 0)

        # Toggle day comparison card: ONLY visible on Today (self.selected_day_idx == 0)
        show_comp = is_today
        for card_attr in ['comp_card', 'uv_comp_card', 'wind_comp_card', 'precip_comp_card', 'hum_comp_card', 'vis_comp_card', 'press_comp_card']:
            c = getattr(self, card_attr, None)
            if c:
                c.set_visible(show_comp)

        # 1. Date Subtitle
        date_str = cur_day.get('date_str')
        dt = None
        if date_str:
            try:
                dt = datetime.strptime(date_str.split('T')[0], "%Y-%m-%d")
            except (ValueError, TypeError) as e:
                logger.debug("Failed parsing date %s: %s", date_str, e)
        if dt is None:
            dt = datetime.now() + timedelta(days=self.selected_day_idx)

        self.lbl_date_sub.set_label(format_full_date(dt, lang))

        utc_off = self.data.get('utc_offset_seconds', 0)
        from datetime import timezone as dt_timezone
        utc_now = datetime.now(dt_timezone.utc)
        city_now = utc_now + timedelta(seconds=utc_off)
        cur_city_hour = city_now.hour if is_today else -1
        h_idx = max(0, min(23, cur_city_hour if cur_city_hour >= 0 else 12))
        cur_time_str = city_now.strftime('%H:%M')

        if is_today:
            sum_time_hdr = t('weather_time_now_hdr', time=cur_time_str)
        else:
            w_idx = dt.weekday()
            from providers.weather import get_weekday_name
            w_short = get_weekday_name(w_idx, lang=lang)
            sum_time_hdr = t('weather_time_allday_hdr', day=w_short)

        # 2. Dynamic Hero Row for current mode
        cur_hour = cur_city_hour
        h_idx = max(0, min(23, cur_hour if cur_hour >= 0 else 12))

        if self.current_mode == 'conditions':
            main_t_c = self.data.get('temp', cur_day.get('max', 20)) if is_today else cur_day.get('max', 20)
            main_temp = convert_temp(main_t_c, self.temp_unit)
            self.lbl_hero_main.set_label(f"{main_temp}°")
            t_min = convert_temp(cur_day.get('min', 0), self.temp_unit)
            t_max = convert_temp(cur_day.get('max', 0), self.temp_unit)
            self.lbl_hero_sub.set_label(f"↓ {t_min}° ↑ {t_max}°")
            icon_file = cur_day.get('icon_file')
            if icon_file and os.path.exists(icon_file):
                self.hero_icon.set_from_file(icon_file)
            else:
                self.hero_icon.set_from_icon_name('weather-clear-symbolic')

        elif self.current_mode == 'uv':
            h_uvs = cur_day.get('hourly_uvs', [0.0] * 24)
            uv_val = self.data.get('uv_index', h_uvs[h_idx]) if is_today else cur_day.get('uv_max', max(h_uvs))
            self.lbl_hero_main.set_label(f"{uv_val:.1f}")
            if uv_val <= 2.9:
                uv_name = 'Низкий' if is_ru else 'Low'
            elif uv_val <= 5.9:
                uv_name = 'Умеренный' if is_ru else 'Moderate'
            elif uv_val <= 7.9:
                uv_name = 'Высокий' if is_ru else 'High'
            elif uv_val <= 10.9:
                uv_name = 'Очень высокий' if is_ru else 'Very High'
            else:
                uv_name = 'Экстремальный' if is_ru else 'Extreme'
            peak_val = cur_day.get('uv_max', max(h_uvs))
            self.lbl_hero_sub.set_label(f"{uv_name} • Пик {peak_val:.1f}" if is_ru else f"{uv_name} • Peak {peak_val:.1f}")
            svg_p = _get_icon_path('sun-uv.svg')
            if svg_p:
                self.hero_icon.set_from_file(svg_p)
            else:
                self.hero_icon.set_from_icon_name('weather-clear-symbolic')

        elif self.current_mode == 'wind':
            h_winds = cur_day.get('hourly_winds', [10] * 24)
            w_spd = self.data.get('wind_speed', h_winds[h_idx]) if is_today else cur_day.get('wind_max', max(h_winds))
            self.lbl_hero_main.set_label(f"{w_spd} км/ч" if is_ru else f"{w_spd} km/h")
            cardinal = cur_day.get('dominant_wind_cardinal', 'СЗ')
            gust = cur_day.get('gust_max', max(cur_day.get('hourly_gusts', [w_spd + 8])))
            self.lbl_hero_sub.set_label(f"{cardinal} • Порывы до {gust} км/ч" if is_ru else f"{cardinal} • Gusts to {gust} km/h")
            svg_p = _get_icon_path('wind.svg')
            if svg_p:
                self.hero_icon.set_from_file(svg_p)
            else:
                self.hero_icon.set_from_icon_name('weather-windy-symbolic')

        elif self.current_mode == 'precipitation':
            p_sum = cur_day.get('precip_sum', 0.0)
            p_prob = cur_day.get('precip_prob_max', 0)
            self.lbl_hero_main.set_label(f"{p_sum:.1f} мм" if is_ru else f"{p_sum:.1f} mm")
            self.lbl_hero_sub.set_label(f"Вероятность {p_prob}%" if is_ru else f"Probability {p_prob}%")
            svg_p = _get_icon_path('umbrella.svg')
            if svg_p:
                self.hero_icon.set_from_file(svg_p)
            else:
                self.hero_icon.set_from_icon_name('weather-showers-symbolic')

        elif self.current_mode == 'humidity':
            h_hums = cur_day.get('hourly_hums', [60] * 24)
            h_val = self.data.get('humidity', h_hums[h_idx]) if is_today else round(sum(h_hums) / len(h_hums))
            h_dews = cur_day.get('hourly_dews', [10] * 24)
            raw_dew = self.data.get('dew_point', h_dews[h_idx]) if is_today else round(sum(h_dews) / len(h_dews))
            dew = convert_temp(raw_dew, self.temp_unit)
            unit_sym = "°F" if self.temp_unit == "fahrenheit" else "°C"
            self.lbl_hero_main.set_label(f"{h_val}%")
            self.lbl_hero_sub.set_label(f"Точка росы {dew}{unit_sym}" if is_ru else f"Dew point {dew}{unit_sym}")
            svg_p = _get_icon_path('droplet.svg')
            if svg_p:
                self.hero_icon.set_from_file(svg_p)
            else:
                self.hero_icon.set_from_icon_name('weather-fog-symbolic')

        elif self.current_mode == 'visibility':
            h_vis = cur_day.get('hourly_vis_km', [10.0] * 24)
            v_val = self.data.get('visibility_km', h_vis[h_idx]) if is_today else cur_day.get('min_visibility_km', 10.0)
            self.lbl_hero_main.set_label(f"{v_val:.0f} км" if is_ru else f"{v_val:.0f} km")
            quality = ('Отличная' if v_val >= 10.0 else ('Хорошая' if v_val >= 4.0 else 'Дымка/Туман')) if is_ru else ('Excellent' if v_val >= 10.0 else ('Good' if v_val >= 4.0 else 'Haze/Fog'))
            self.lbl_hero_sub.set_label(f"{quality} видимость" if is_ru else f"{quality} visibility")
            svg_p = _get_icon_path('eye.svg')
            if svg_p:
                self.hero_icon.set_from_file(svg_p)
            else:
                self.hero_icon.set_from_icon_name('find-location-symbolic')

        elif self.current_mode == 'pressure':
            h_press = cur_day.get('hourly_press_mm', [752] * 24)
            p_val = self.data.get('pressure_mm', h_press[h_idx]) if is_today else round(sum(h_press) / len(h_press))
            self.lbl_hero_main.set_label(f"{p_val} мм" if is_ru else f"{p_val} mmHg")
            stat = ('Нормальное' if 745 <= p_val <= 765 else ('Пониженное' if p_val < 745 else 'Повышенное')) if is_ru else ('Normal' if 745 <= p_val <= 765 else ('Low' if p_val < 745 else 'High'))
            self.lbl_hero_sub.set_label(f"{stat} • {round(p_val / 0.75006)} гПа" if is_ru else f"{stat} • {round(p_val / 0.75006)} hPa")
            svg_p = _get_icon_path('gauge.svg')
            if svg_p:
                self.hero_icon.set_from_file(svg_p)
            else:
                self.hero_icon.set_from_icon_name('speedometer-symbolic')

        # 3. Update view-specific widgets
        # A. Conditions
        main_t = self.data.get('temp', cur_day.get('max', 20)) if is_today else cur_day.get('max', 20)
        raw_temps = cur_day.get('hourly_temps', [main_t] * 24)
        raw_apparent = cur_day.get('hourly_apparent', [main_t] * 24)
        h_temps = [convert_temp(t, self.temp_unit) for t in raw_temps]
        h_apparent = [convert_temp(t, self.temp_unit) for t in raw_apparent]
        self.spline_area.update_data(
            temps=h_temps,
            apparent=h_apparent,
            codes=cur_day.get('hourly_codes', [0] * 24),
            is_days=cur_day.get('hourly_is_days', [1] * 24),
            is_today=is_today,
            cur_hour=cur_city_hour,
            show_feels_like=self.show_feels_like,
            bg_class=self.bg_class
        )
        p_prob = cur_day.get('precip_prob_max', 0)
        self.lbl_pr_sub.set_label(t('weather_precip_chance_today', prob=p_prob))
        self.precip_prob_area.update_data(cur_day.get('hourly_probs', [0] * 24))
        p_sum = cur_day.get('precip_sum', 0.0)
        p_unit = 'мм' if is_ru or lang in ('uk', 'kk') else 'mm'
        self.lbl_v1_val.set_label(f"{p_sum} {p_unit}")
        y_comp = self.data.get('yesterday_comp', {})
        prev_day = self.days_detailed[self.selected_day_idx - 1] if self.selected_day_idx > 0 else None
        if is_today:
            cur_comp_lbl = t('weather_word_today')
            prev_comp_lbl = t('weather_word_yesterday')
            c_cur_min = convert_temp(cur_day.get('min', 10), self.temp_unit)
            c_cur_max = convert_temp(cur_day.get('max', 25), self.temp_unit)
            c_prev_min = convert_temp(y_comp.get('yesterday_min', cur_day.get('min', 10) - 1), self.temp_unit)
            c_prev_max = convert_temp(y_comp.get('yesterday_max', cur_day.get('max', 25)), self.temp_unit)
            diff_c = c_cur_max - c_prev_max
            if diff_c == 0:
                c_sub = t('weather_comp_today_same')
            elif diff_c > 0:
                c_sub = t('weather_comp_today_warmer', diff=diff_c)
            else:
                c_sub = t('weather_comp_today_cooler', diff=abs(diff_c))
        else:
            w_idx = dt.weekday()
            from providers.weather import get_weekday_name
            cur_comp_lbl = get_weekday_name(w_idx, lang=lang)
            prev_dt = dt - timedelta(days=1)
            prev_comp_lbl = get_weekday_name(prev_dt.weekday(), lang=lang)
            c_cur_min = convert_temp(cur_day.get('min', 10), self.temp_unit)
            c_cur_max = convert_temp(cur_day.get('max', 25), self.temp_unit)
            c_prev_min = convert_temp(prev_day.get('min', cur_day.get('min', 10)) if prev_day else cur_day.get('min', 10), self.temp_unit)
            c_prev_max = convert_temp(prev_day.get('max', cur_day.get('max', 25)) if prev_day else cur_day.get('max', 25), self.temp_unit)
            diff_c = c_cur_max - c_prev_max
            p_name = prev_comp_lbl.lower()
            if diff_c == 0:
                c_sub = t('weather_comp_other_same', prev=p_name)
            elif diff_c > 0:
                c_sub = t('weather_comp_other_warmer', diff=diff_c, prev=p_name)
            else:
                c_sub = t('weather_comp_other_cooler', diff=abs(diff_c), prev=p_name)

        self.lbl_comp_sub.set_label(c_sub)
        self.comp_bar.update_single('conditions', cur_comp_lbl, prev_comp_lbl, c_cur_max, c_prev_max, '°', 0)
        if hasattr(self, 'lbl_cond_sum_time'):
            self.lbl_cond_sum_time.set_label(sum_time_hdr)
            c_summary = get_smart_day_summary(
                cur_day,
                lang=lang,
                is_today=is_today,
                temp_unit=self.temp_unit,
                current_temp=main_t
            )
            t_min = convert_temp(cur_day.get('min', 0), self.temp_unit)
            t_max = convert_temp(cur_day.get('max', 0), self.temp_unit)
            main_t_disp = convert_temp(main_t, self.temp_unit)
            if is_today:
                eod_txt = t('weather_cond_summary_end_of_day', temp=main_t_disp, min=t_min)
                c_txt = f"{c_summary} {eod_txt}".strip()
            else:
                c_txt = c_summary
            self.lbl_cond_sum_text.set_label(c_txt)
            if hasattr(self, 'lbl_summary_text'):
                self.lbl_summary_text.set_label(c_summary)

        # B. UV
        h_uvs = cur_day.get('hourly_uvs', [0.0] * 24)
        peak_uv = cur_day.get('uv_max', max(h_uvs) if h_uvs else 0.0)
        self.uv_hourly_area.update_data(h_uvs, cur_city_hour, is_today)
        self.lbl_uv_val.set_label(f"{peak_uv:.1f}")
        if peak_uv <= 2.9:
            uv_lvl = 'Низкий' if is_ru else 'Low'
            advice = (
                'Защита от солнца не требуется. Вы можете безопасно находиться на открытом воздухе без риска солнечных ожогов.' if is_ru else
                'No sun protection required. You can safely stay outdoors without risk of sunburn.'
            )
        elif peak_uv <= 5.9:
            uv_lvl = 'Умеренный' if is_ru else 'Moderate'
            advice = (
                'Требуется защита от солнца. В полуденные часы (с 11:00 до 16:00) наносите солнцезащитный крем SPF 30+, надевайте панаму и солнцезащитные очки.' if is_ru else
                'Protection needed. Between 11:00 and 16:00, use SPF 30+ sunscreen, wear a hat and sunglasses.'
            )
        elif peak_uv <= 7.9:
            uv_lvl = 'Высокий' if is_ru else 'High'
            advice = (
                'Высокий уровень УФ-излучения! Старайтесь оставаться в тени в середине дня. Обязателен солнцезащитный крем SPF 50+, головной убор и солнцезащитные очки.' if is_ru else
                'High UV radiation level! Stay in shade during midday. SPF 50+ sunscreen, hat, and sunglasses are essential.'
            )
        else:
            uv_lvl = 'Очень высокий' if is_ru else 'Very High'
            advice = (
                'Опасный уровень УФ-излучения! Избегайте прямого солнца. Кожа может обгореть за 10–15 минут. Используйте максимальную фотозащиту.' if is_ru else
                'Hazardous UV level! Avoid direct sunlight. Sunburn can occur in 10-15 minutes. Use maximum sun protection.'
            )
        self.lbl_uv_level.set_label(uv_lvl)
        self.lbl_uv_advice.set_label(advice)

        if hasattr(self, 'lbl_uv_sum_time'):
            self.lbl_uv_sum_time.set_label(sum_time_hdr)
            if is_today:
                rem_uv = [u for u in h_uvs[h_idx:] if u >= 0.2]
                if not rem_uv:
                    uv_fut = "Остается 0 до конца дня." if is_ru else "Remains 0 for the rest of the day."
                else:
                    zero_h = next((i for i in range(h_idx, 24) if h_uvs[i] < 0.2), 20)
                    uv_fut = f"Остается выше 0 до {zero_h:02d}:00." if is_ru else f"Remains above 0 until {zero_h:02d}:00."
            else:
                uv_fut = f"Максимальный УФ-индекс за день составит {peak_uv:.1f}." if is_ru else f"Peak UV index for the day will be {peak_uv:.1f}."

            mod_hours = [i for i, u in enumerate(h_uvs) if u >= 3.0]
            if mod_hours:
                h_start = mod_hours[0]
                h_end = min(23, mod_hours[-1] + 1)
                if peak_uv >= 8.0:
                    lvl_name = "очень высоким или выше" if is_ru else "very high or higher"
                elif peak_uv >= 6.0:
                    lvl_name = "высоким или выше" if is_ru else "high or higher"
                else:
                    lvl_name = "умеренным или выше" if is_ru else "moderate or higher"
                uv_retro = f"С {h_start:02d}:00 до {h_end:02d}:00 уровень был {lvl_name}." if is_ru else f"From {h_start:02d}:00 to {h_end:02d}:00 level was {lvl_name}."
            else:
                uv_retro = f"В течение всего дня уровень остается низким (до {peak_uv:.1f})." if is_ru else f"Level remains low throughout the day (up to {peak_uv:.1f})."

            self.lbl_uv_sum_text.set_label(f"{uv_fut} {uv_retro}")

        if hasattr(self, 'uv_comp_bar'):
            if is_today:
                uv_cur_val = cur_day.get('uv_max', 3.0)
                uv_prev_val = y_comp.get('yesterday_uv_max', uv_cur_val)
                target_w = "вчера" if is_ru else "yesterday"
            else:
                uv_cur_val = cur_day.get('uv_max', 3.0)
                uv_prev_val = prev_day.get('uv_max', uv_cur_val) if prev_day else uv_cur_val
                target_w = prev_comp_lbl.lower() if is_ru else prev_comp_lbl
            diff_uv = round(uv_cur_val - uv_prev_val, 1)
            if abs(diff_uv) < 0.2:
                uv_comp_sub = f"УФ-индекс на том же уровне, что и {target_w} ({uv_cur_val:.1f})." if is_ru else f"UV index is similar to {target_w} ({uv_cur_val:.1f})."
            elif diff_uv > 0:
                uv_comp_sub = f"Максимальный УФ-индекс на {diff_uv:.1f} выше, чем {target_w}." if is_ru else f"Peak UV index is {diff_uv:.1f} higher than {target_w}."
            else:
                uv_comp_sub = f"Максимальный УФ-индекс на {abs(diff_uv):.1f} ниже, чем {target_w}." if is_ru else f"Peak UV index is {abs(diff_uv):.1f} lower than {target_w}."
            self.lbl_uv_comp_sub.set_label(uv_comp_sub)
            self.uv_comp_bar.update_single('uv', cur_comp_lbl, prev_comp_lbl, uv_cur_val, uv_prev_val, '', 1)

        # C. Wind
        h_winds = cur_day.get('hourly_winds', [10] * 24)
        h_gusts = cur_day.get('hourly_gusts', [18] * 24)
        h_dirs = cur_day.get('hourly_wind_dirs', [270] * 24)
        cur_spd = self.data.get('wind_speed', h_winds[h_idx]) if is_today else cur_day.get('wind_max', max(h_winds))
        cur_gust = self.data.get('wind_gusts', h_gusts[h_idx]) if is_today else cur_day.get('gust_max', max(h_gusts))
        cur_dir = self.data.get('wind_direction', h_dirs[h_idx]) if is_today else cur_day.get('dominant_wind_dir', 270)
        self.wind_compass_area.update_data(cur_spd, cur_gust, cur_dir)
        card_dir = cur_day.get('dominant_wind_cardinal', 'СЗ')
        desc_dir = cur_day.get('dominant_wind_desc', 'Северо-западный ветер')
        self.lbl_compass_desc.set_label(f"{desc_dir} ({cur_dir}°) • Порывы до {cur_gust} км/ч" if is_ru else f"{card_dir} wind ({cur_dir}°) • Gusts to {cur_gust} km/h")
        self.wind_hourly_area.update_data(h_winds, h_gusts, h_dirs, cur_city_hour, is_today)
        self.lbl_wind_max.set_label(f"{cur_day.get('wind_max', max(h_winds))} км/ч" if is_ru else f"{cur_day.get('wind_max', max(h_winds))} km/h")
        self.lbl_wind_gusts_max.set_label(f"{cur_day.get('gust_max', max(h_gusts))} км/ч" if is_ru else f"{cur_day.get('gust_max', max(h_gusts))} km/h")
        self.lbl_wind_dir_name.set_label(f"{card_dir} ({desc_dir})")

        if hasattr(self, 'lbl_wind_sum_time'):
            self.lbl_wind_sum_time.set_label(sum_time_hdr)
            rem_winds = h_winds[h_idx:] if (is_today and h_idx < 24) else h_winds
            max_rem = max(rem_winds) if rem_winds else cur_spd
            min_rem = min(rem_winds) if rem_winds else cur_spd
            if max_rem >= cur_spd + 5:
                w_fut = f"Ожидается усиление ветра до {max_rem} км/ч к вечеру." if is_ru else f"Wind expected to strengthen up to {max_rem} km/h by evening."
            elif min_rem <= cur_spd - 5:
                w_fut = f"Ожидается ослабление ветра до {min_rem} км/ч к концу дня." if is_ru else f"Wind expected to ease to {min_rem} km/h toward end of day."
            else:
                w_fut = f"Скорость ветра останется на уровне ~{cur_spd} км/ч до конца дня." if is_ru else f"Wind speed will remain around {cur_spd} km/h through end of day."
            w_retro = f"Ранее сегодня порывы ветра достигали {cur_gust} км/ч при направлении {card_dir}." if is_ru else f"Earlier today gusts reached {cur_gust} km/h from {card_dir}."
            self.lbl_wind_sum_text.set_label(f"{w_fut} {w_retro}")

        if hasattr(self, 'wind_comp_bar'):
            if is_today:
                w_cur_val = cur_day.get('wind_max', 15.0)
                w_prev_val = y_comp.get('yesterday_wind_max', w_cur_val)
                target_w = "вчера" if is_ru else "yesterday"
            else:
                w_cur_val = cur_day.get('wind_max', 15.0)
                w_prev_val = prev_day.get('wind_max', w_cur_val) if prev_day else w_cur_val
                target_w = prev_comp_lbl.lower() if is_ru else prev_comp_lbl
            diff_w = round(w_cur_val - w_prev_val)
            if abs(diff_w) < 2:
                wind_comp_sub = f"Скорость ветра практически такая же, как {target_w} ({round(w_cur_val)} км/ч)." if is_ru else f"Wind speed is about the same as {target_w} ({round(w_cur_val)} km/h)."
            elif diff_w > 0:
                w_pref = "сегодня " if is_today else ""
                wind_comp_sub = f"Порывы и скорость ветра {w_pref}на {diff_w} км/ч сильнее, чем {target_w}." if is_ru else f"Wind speed {w_pref}is {diff_w} km/h stronger than {target_w}."
            else:
                w_pref = "сегодня " if is_today else ""
                wind_comp_sub = f"Ветер {w_pref}на {abs(diff_w)} км/ч слабее, чем {target_w}." if is_ru else f"Wind speed {w_pref}is {abs(diff_w)} km/h lighter than {target_w}."
            self.lbl_wind_comp_sub.set_label(wind_comp_sub)
            self.wind_comp_bar.update_single('wind', cur_comp_lbl, prev_comp_lbl, w_cur_val, w_prev_val, ' км/ч' if is_ru else ' km/h', 0)

        # D. Precipitation
        h_precips = cur_day.get('hourly_precips', [0.0] * 24)
        h_probs = cur_day.get('hourly_probs', [0] * 24)
        self.precip_hourly_area.update_data(h_precips, h_probs, cur_city_hour, is_today)
        self.lbl_pr_day_vol.set_label(f"{cur_day.get('precip_sum', 0.0):.1f} мм" if is_ru else f"{cur_day.get('precip_sum', 0.0):.1f} mm")
        self.lbl_pr_day_prob.set_label(f"{cur_day.get('precip_prob_max', 0)}%")

        if hasattr(self, 'lbl_precip_sum_time'):
            self.lbl_precip_sum_time.set_label(sum_time_hdr)
            rem_precips = h_precips[h_idx:] if (is_today and h_idx < 24) else h_precips
            rem_probs = h_probs[h_idx:] if (is_today and h_idx < 24) else h_probs
            if sum(rem_precips) < 0.1 and (not rem_probs or max(rem_probs) < 20):
                p_fut = "Осадки не ожидаются до конца дня." if is_ru else "No precipitation expected through the end of the day."
            else:
                rain_h = next((i for i in range(h_idx, 24) if h_precips[i] >= 0.1 or h_probs[i] >= 30), None)
                if rain_h is not None:
                    p_fut = f"Ожидаются осадки около {rain_h:02d}:00 (вероятность {h_probs[rain_h]}%)." if is_ru else f"Precipitation expected around {rain_h:02d}:00 ({h_probs[rain_h]}% chance)."
                else:
                    p_fut = "Возможны незначительные кратковременные осадки." if is_ru else "Slight brief showers possible."
            if cur_day.get('precip_sum', 0.0) >= 0.5:
                p_retro = f"С утра выпало {cur_day.get('precip_sum', 0.0):.1f} мм осадков." if is_ru else f"{cur_day.get('precip_sum', 0.0):.1f} mm of precipitation has fallen since morning."
            else:
                p_retro = "За прошедшую часть дня существенных осадков не зафиксировано." if is_ru else "No significant precipitation recorded earlier today."
            self.lbl_precip_sum_text.set_label(f"{p_fut} {p_retro}")

        if hasattr(self, 'precip_comp_bar'):
            if is_today:
                p_cur_val = cur_day.get('precip_sum', 0.0)
                p_prev_val = y_comp.get('yesterday_precip_sum', 0.0)
                target_w = "вчера" if is_ru else "yesterday"
            else:
                p_cur_val = cur_day.get('precip_sum', 0.0)
                p_prev_val = prev_day.get('precip_sum', 0.0) if prev_day else 0.0
                target_w = prev_comp_lbl.lower() if is_ru else prev_comp_lbl
            diff_p = round(p_cur_val - p_prev_val, 1)
            if p_cur_val == 0.0 and p_prev_val == 0.0:
                precip_comp_sub = f"Без осадков {'сегодня и вчера' if is_today else 'в эти дни'}." if is_ru else f"No precipitation {'today or yesterday' if is_today else 'on both days'}."
            elif abs(diff_p) < 0.2:
                precip_comp_sub = f"Количество осадков примерно такое же, как {target_w} ({p_cur_val:.1f} мм)." if is_ru else f"Precipitation amount is similar to {target_w} ({p_cur_val:.1f} mm)."
            elif diff_p > 0:
                precip_comp_sub = f"Ожидается на {diff_p:.1f} мм больше осадков, чем {target_w}." if is_ru else f"{diff_p:.1f} mm more precipitation expected than {target_w}."
            else:
                precip_comp_sub = f"Ожидается на {abs(diff_p):.1f} мм меньше осадков, чем {target_w}." if is_ru else f"{abs(diff_p):.1f} mm less precipitation expected than {target_w}."
            self.lbl_precip_comp_sub.set_label(precip_comp_sub)
            self.precip_comp_bar.update_single('precipitation', cur_comp_lbl, prev_comp_lbl, p_cur_val, p_prev_val, ' мм' if is_ru else ' mm', 1)

        # E. Humidity
        h_hums = cur_day.get('hourly_hums', [60] * 24)
        h_dews = cur_day.get('hourly_dews', [10] * 24)
        self.humidity_hourly_area.update_data(h_hums, h_dews, cur_city_hour, is_today)
        raw_dew = self.data.get('dew_point', h_dews[h_idx]) if is_today else round(sum(h_dews) / len(h_dews))
        cur_dew = convert_temp(raw_dew, self.temp_unit)
        dew_unit_sym = "°F" if self.temp_unit == "fahrenheit" else "°C"
        self.lbl_hum_dew.set_label(f"{cur_dew}{dew_unit_sym}")
        if raw_dew < 10:
            sens = 'Сухой и свежий' if is_ru else 'Dry and fresh'
            s_desc = 'Воздух сухой и бодрящий, испарение влаги происходит легко.' if is_ru else 'Crisp, fresh air with effortless evaporation.'
        elif raw_dew <= 15:
            sens = 'Комфортный' if is_ru else 'Comfortable'
            s_desc = 'Оптимальное содержание влаги в воздухе, идеально для дыхания.' if is_ru else 'Pleasant humidity level, ideal for human comfort.'
        elif raw_dew <= 18:
            sens = 'Умеренно влажный' if is_ru else 'Moderately humid'
            s_desc = 'Ощущается легкая влажность, в теплую погоду может казаться душно.' if is_ru else 'Noticeable humidity, may feel warm outdoors.'
        else:
            sens = 'Душный' if is_ru else 'Muggy'
            s_desc = 'Высокая точка росы вызывает ощущение духоты и липкости.' if is_ru else 'Oppressive humidity, significant mugginess.'
        self.lbl_hum_sensation.set_label(sens)
        self.lbl_hum_dew_desc.set_label(s_desc)

        if hasattr(self, 'lbl_hum_sum_time'):
            self.lbl_hum_sum_time.set_label(sum_time_hdr)
            h_fut = f"Влажность сейчас {self.data.get('humidity', h_hums[h_idx]) if is_today else round(sum(h_hums) / len(h_hums))}%, точка росы {cur_dew}{dew_unit_sym} ({sens})." if is_ru else f"Humidity currently {self.data.get('humidity', h_hums[h_idx]) if is_today else round(sum(h_hums) / len(h_hums))}%, dew point {cur_dew}{dew_unit_sym} ({sens})."
            h_retro = f"Суточный диапазон влажности: от {min(h_hums)}% до {max(h_hums)}%. {s_desc}" if is_ru else f"Daily humidity range: {min(h_hums)}% to {max(h_hums)}%. {s_desc}"
            self.lbl_hum_sum_text.set_label(f"{h_fut} {h_retro}")

        if hasattr(self, 'hum_comp_bar'):
            if is_today:
                h_cur_val = round(sum(cur_day.get('hourly_hums', [60]*24)) / 24)
                h_prev_val = y_comp.get('yesterday_avg_humidity', h_cur_val)
                target_w = "вчера" if is_ru else "yesterday"
            else:
                h_cur_val = round(sum(cur_day.get('hourly_hums', [60]*24)) / 24)
                h_prev_val = round(sum(prev_day.get('hourly_hums', [60]*24)) / 24) if prev_day else h_cur_val
                target_w = prev_comp_lbl.lower() if is_ru else prev_comp_lbl
            diff_h = h_cur_val - h_prev_val
            if abs(diff_h) < 3:
                hum_comp_sub = f"Средняя влажность воздуха примерно как {target_w} ({h_cur_val}%)." if is_ru else f"Average humidity is similar to {target_w} ({h_cur_val}%)."
            elif diff_h > 0:
                hum_comp_sub = f"Влажность в среднем на {diff_h}% выше, чем {target_w}." if is_ru else f"Humidity is {diff_h}% higher than {target_w}."
            else:
                hum_comp_sub = f"Влажность в среднем на {abs(diff_h)}% ниже, чем {target_w}." if is_ru else f"Humidity is {abs(diff_h)}% lower than {target_w}."
            self.lbl_hum_comp_sub.set_label(hum_comp_sub)
            self.hum_comp_bar.update_single('humidity', cur_comp_lbl, prev_comp_lbl, h_cur_val, h_prev_val, '%', 0)

        # F. Visibility
        h_vis = cur_day.get('hourly_vis_km', [10.0] * 24)
        self.visibility_hourly_area.update_data(h_vis, cur_city_hour, is_today)
        cur_vis = self.data.get('visibility_km', h_vis[h_idx]) if is_today else cur_day.get('min_visibility_km', 10.0)
        self.lbl_vis_km_val.set_label(f"{cur_vis:.1f} км" if is_ru else f"{cur_vis:.1f} km")
        if cur_vis >= 10.0:
            v_q = 'Отличная' if is_ru else 'Excellent'
            v_d = 'Атмосфера прозрачна, видимость горизонта не ограничена.' if is_ru else 'Clear atmosphere, unobstructed horizon.'
        elif cur_vis >= 4.0:
            v_q = 'Умеренная' if is_ru else 'Moderate'
            v_d = 'Небольшая дымка или рассеянный свет в воздухе.' if is_ru else 'Slight haze or atmospheric scattering.'
        elif cur_vis >= 1.0:
            v_q = 'Сниженная (дымка)' if is_ru else 'Reduced (Mist)'
            v_d = 'Заметная дымка или слабый туман ограничивают видимость.' if is_ru else 'Haze or light fog reducing distant landmarks.'
        else:
            v_q = 'Густой туман' if is_ru else 'Dense Fog'
            v_d = 'Плотный туман, требуется повышенная осторожность на дорогах.' if is_ru else 'Heavy fog, extreme driving caution advised.'
        self.lbl_vis_quality.set_label(v_q)
        self.lbl_vis_desc.set_label(v_d)

        if hasattr(self, 'lbl_vis_sum_time'):
            self.lbl_vis_sum_time.set_label(sum_time_hdr)
            min_vis = min(h_vis) if h_vis else cur_vis
            v_fut = f"Видимость сейчас составляет {cur_vis:.1f} км ({v_q.lower()})." if is_ru else f"Visibility is currently {cur_vis:.1f} km ({v_q.lower()})."
            if min_vis < 5.0:
                v_retro = f"Ранее сегодня видимость временно снижалась до {min_vis:.1f} км из-за тумана или дымки." if is_ru else f"Earlier today visibility dropped to {min_vis:.1f} km due to fog or mist."
            else:
                v_retro = "Отличная прозрачность атмосферы сохраняется на протяжении всего дня." if is_ru else "Clear atmospheric visibility maintained throughout the day."
            self.lbl_vis_sum_text.set_label(f"{v_fut} {v_retro}")

        if hasattr(self, 'vis_comp_bar'):
            if is_today:
                v_cur_val = cur_day.get('min_visibility_km', 10.0)
                v_prev_val = y_comp.get('yesterday_min_visibility_km', v_cur_val)
                target_w = "вчера" if is_ru else "yesterday"
            else:
                v_cur_val = cur_day.get('min_visibility_km', 10.0)
                v_prev_val = prev_day.get('min_visibility_km', v_cur_val) if prev_day else v_cur_val
                target_w = prev_comp_lbl.lower() if is_ru else prev_comp_lbl
            diff_v = round(v_cur_val - v_prev_val, 1)
            if v_cur_val >= 10.0 and v_prev_val >= 10.0:
                vis_comp_sub = f"Отличная видимость (10 км), как и {target_w}." if is_ru else f"Clear visibility (10 km), same as {target_w}."
            elif abs(diff_v) < 0.5:
                vis_comp_sub = f"Видимость практически такая же, как {target_w} ({v_cur_val:.0f} км)." if is_ru else f"Visibility is about the same as {target_w} ({v_cur_val:.0f} km)."
            elif diff_v > 0:
                vis_comp_sub = f"Видимость лучше, чем {target_w} (на {diff_v:.1f} км дальше)." if is_ru else f"Visibility is {diff_v:.1f} km clearer than {target_w}."
            else:
                vis_comp_sub = f"Видимость хуже, чем {target_w} (на {abs(diff_v):.1f} км меньше)." if is_ru else f"Visibility is {abs(diff_v):.1f} km lower than {target_w}."
            self.lbl_vis_comp_sub.set_label(vis_comp_sub)
            self.vis_comp_bar.update_single('visibility', cur_comp_lbl, prev_comp_lbl, v_cur_val, v_prev_val, ' км' if is_ru else ' km', 0)

        # G. Pressure
        h_press = cur_day.get('hourly_press_mm', [752] * 24)
        h_press_hpa = cur_day.get('hourly_press_hpa', [1003] * 24)
        self.pressure_hourly_area.update_data(h_press, cur_city_hour, is_today)
        cur_press = self.data.get('pressure_mm', h_press[h_idx]) if is_today else round(sum(h_press) / len(h_press))
        cur_hpa = round(cur_press / 0.75006)
        self.pressure_gauge_area.update_data(cur_press, cur_hpa)
        if cur_press < 745:
            p_st = 'Пониженное давление (циклон)' if is_ru else 'Low pressure (Cyclone)'
        elif cur_press <= 765:
            p_st = 'Нормальное атмосферное давление' if is_ru else 'Normal atmospheric pressure'
        else:
            p_st = 'Повышенное давление (антициклон)' if is_ru else 'High pressure (Anticyclone)'
        self.lbl_press_status_sub.set_label(p_st)
        self.lbl_press_val_mm.set_label(f"{cur_press} мм рт. ст." if is_ru else f"{cur_press} mmHg")
        self.lbl_press_val_hpa.set_label(f"{cur_hpa} гПа" if is_ru else f"{cur_hpa} hPa")

        # Trend over last 3 hours
        if len(h_press) >= 4:
            p_diff = h_press[min(23, h_idx)] - h_press[max(0, h_idx - 3)]
            if p_diff > 1:
                tr_txt = f"↗ Растет (+{p_diff} мм за 3ч)" if is_ru else f"↗ Rising (+{p_diff} mmHg / 3h)"
            elif p_diff < -1:
                tr_txt = f"↘ Падает ({p_diff} мм за 3ч)" if is_ru else f"↘ Falling ({p_diff} mmHg / 3h)"
            else:
                tr_txt = "→ Стабильное" if is_ru else "→ Steady"
        else:
            tr_txt = "→ Стабильное" if is_ru else "→ Steady"
        self.lbl_press_trend_desc.set_label(tr_txt)

        if hasattr(self, 'lbl_press_sum_time'):
            self.lbl_press_sum_time.set_label(sum_time_hdr)
            delta = h_press[-1] - cur_press
            if delta >= 2:
                pr_fut = f"Давление повышается до {h_press[-1]} мм рт. ст. к ночи." if is_ru else f"Pressure rising to {h_press[-1]} mmHg by nightfall."
            elif delta <= -2:
                pr_fut = f"Давление снижается до {h_press[-1]} мм рт. ст. к концу суток." if is_ru else f"Pressure dropping to {h_press[-1]} mmHg by end of day."
            else:
                pr_fut = f"Давление остается стабильным на уровне ~{cur_press} мм рт. ст. ({p_st})." if is_ru else f"Pressure remains steady around {cur_press} mmHg ({p_st})."
            pr_retro = f"Суточный диапазон: от {min(h_press)} до {max(h_press)} мм рт. ст." if is_ru else f"Daily range: {min(h_press)} to {max(h_press)} mmHg."
            self.lbl_press_sum_text.set_label(f"{pr_fut} {pr_retro}")

        if hasattr(self, 'press_comp_bar'):
            if is_today:
                p_cur_min = min(h_press) if h_press else cur_press
                p_cur_max = max(h_press) if h_press else cur_press
                p_prev_min = y_comp.get('yesterday_min_pressure_mm', p_cur_min)
                p_prev_max = y_comp.get('yesterday_max_pressure_mm', p_cur_max)
                target_w = "вчера" if is_ru else "yesterday"
            else:
                p_cur_min = min(h_press) if h_press else cur_press
                p_cur_max = max(h_press) if h_press else cur_press
                prev_h_press = prev_day.get('hourly_press_mm', [752]*24) if prev_day else []
                p_prev_min = min(prev_h_press) if prev_h_press else p_cur_min
                p_prev_max = max(prev_h_press) if prev_h_press else p_cur_max
                target_w = prev_comp_lbl.lower() if is_ru else prev_comp_lbl
            cur_p_avg = round((p_cur_min + p_cur_max) / 2)
            prev_p_avg = round((p_prev_min + p_prev_max) / 2)
            diff_press = cur_p_avg - prev_p_avg
            if abs(diff_press) < 2:
                press_comp_sub = f"Атмосферное давление стабильно и близко к уровню {target_w} ({cur_p_avg} мм)." if is_ru else f"Barometric pressure is stable and close to {target_w} ({cur_p_avg} mmHg)."
            elif diff_press > 0:
                press_comp_sub = f"Давление в среднем на {diff_press} мм рт. ст. выше, чем {target_w}." if is_ru else f"Pressure is {diff_press} mmHg higher on average than {target_w}."
            else:
                press_comp_sub = f"Давление в среднем на {abs(diff_press)} мм рт. ст. ниже, чем {target_w}." if is_ru else f"Pressure is {abs(diff_press)} mmHg lower on average than {target_w}."
            self.lbl_press_comp_sub.set_label(press_comp_sub)
            self.press_comp_bar.update_single('pressure', cur_comp_lbl, prev_comp_lbl, cur_p_avg, prev_p_avg, ' мм' if is_ru else ' mmHg', 0)



    def _set_averages_subtab(self, subtab: str):
        self.current_averages_subtab = subtab
        if subtab == 'temp':
            self.btn_avg_temp.add_css_class('segmented-btn-active')
            self.btn_avg_precip.remove_css_class('segmented-btn-active')
            self.averages_stack.set_visible_child_name('temp')
        else:
            self.btn_avg_precip.add_css_class('segmented-btn-active')
            self.btn_avg_temp.remove_css_class('segmented-btn-active')
            self.averages_stack.set_visible_child_name('precip')

    def _build_averages_view(self):
        build_averages_view(self)

    def _refresh_averages_view(self):
        c_data = self.data.get('climate_averages')
        if not c_data:
            from providers.weather import calculate_climate_averages
            lat = self.data.get('lat', 55.75)
            lon = self.data.get('lon', 37.61)
            t_max = self.data.get('temp_max', 20)
            t_min = self.data.get('temp_min', 10)
            c_data = calculate_climate_averages(lat, lon, t_max, t_min, lang=get_current_language())
            self.data['climate_averages'] = c_data

        # 1. Temperature Tab
        cur_day = self.days_detailed[0] if self.days_detailed else {}
        utc_off = self.data.get('utc_offset_seconds', 0)
        from datetime import timezone as dt_timezone
        city_now = datetime.now(dt_timezone.utc) + timedelta(seconds=utc_off)
        cur_hour = city_now.hour

        if self.temp_unit == "fahrenheit":
            diff_f = convert_temp_diff(c_data.get('temp_diff', 0), 'fahrenheit')
            avg_max_f = convert_temp(c_data.get('temp_avg_max', 20), 'fahrenheit')
            avg_label = t("weather_climate_average_label")
            if diff_f > 0:
                temp_diff_str = f"+{diff_f}° > {avg_label}"
            elif diff_f < 0:
                temp_diff_str = f"{diff_f}° < {avg_label}"
            else:
                temp_diff_str = t("weather_climate_near_norm")
            temp_sub_str = t("weather_climate_avg_high", val=avg_max_f)
            self.lbl_avg_temp_hero.set_label(temp_diff_str)
            self.lbl_avg_temp_sub.set_label(temp_sub_str)

            hourly_temps = [convert_temp(t, 'fahrenheit') for t in cur_day.get('hourly_temps', [self.data.get('temp', 20)] * 24)]
            p10 = convert_temp(c_data.get('temp_normal_p10', 10), 'fahrenheit')
            p90 = convert_temp(c_data.get('temp_normal_p90', 24), 'fahrenheit')
            band = [(convert_temp(b[0], 'fahrenheit'), convert_temp(b[1], 'fahrenheit')) for b in c_data.get('hourly_normal_band', [(p10, p90)] * 24)]
            today_max = convert_temp(c_data.get('temp_today_max', 20), 'fahrenheit')
            self.climate_temp_chart.update_data(hourly_temps, p10, p90, band, today_max, cur_hour)

            monthly_f = [{
                'name': m['name'],
                'temp_min': convert_temp(m['temp_min'], 'fahrenheit'),
                'temp_max': convert_temp(m['temp_max'], 'fahrenheit')
            } for m in c_data.get('monthly_temp', [])]
            self.climate_temp_table.update_data(monthly_f, c_data.get('current_month_idx', 0))
        else:
            self.lbl_avg_temp_hero.set_label(c_data.get('temp_diff_str', '0°'))
            self.lbl_avg_temp_sub.set_label(c_data.get('temp_sub_str', ''))
            hourly_temps = cur_day.get('hourly_temps', [self.data.get('temp', 20)] * 24)
            p10 = c_data.get('temp_normal_p10', 10)
            p90 = c_data.get('temp_normal_p90', 24)
            band = c_data.get('hourly_normal_band', [(p10, p90)] * 24)
            today_max = c_data.get('temp_today_max', 20)
            self.climate_temp_chart.update_data(hourly_temps, p10, p90, band, today_max, cur_hour)
            self.climate_temp_table.update_data(c_data.get('monthly_temp', []), c_data.get('current_month_idx', 0))

        self.lbl_avg_temp_summary.set_label(c_data.get('summary_temp', ''))
        self.lbl_avg_temp_month_sub.set_label(c_data.get('monthly_temp_sub', ''))

        # 2. Precipitation Tab
        self.lbl_avg_precip_hero.set_label(c_data.get('precip_diff_str', '0 мм'))
        self.lbl_avg_precip_sub.set_label(c_data.get('precip_sub_str', ''))
        self.lbl_avg_precip_summary.set_label(c_data.get('summary_precip', ''))
        self.lbl_avg_precip_month_sub.set_label(c_data.get('monthly_precip_sub', ''))

        series = c_data.get('precip_30d_series', [0.0] * 31)
        avg_30d = c_data.get('precip_avg_30d', 50)
        actual_30d = c_data.get('precip_actual_30d', 50)
        dates = c_data.get('precip_30d_dates', [])

        self.climate_precip_chart.update_data(series, avg_30d, actual_30d, dates)
        self.climate_precip_table.update_data(c_data.get('monthly_precip', []), c_data.get('current_month_idx', 0))


    def _create_sun_metric_row(self, title: str, value: str):
        return create_sun_metric_row(title, value)

    def _build_sun_view(self):
        build_sun_view(self)

    def _on_sun_scrub(self, hour_frac, time_str, elevation_deg, is_scrubbing):
        is_ru = (get_current_language() == 'ru')
        if is_scrubbing and time_str:
            self.lbl_sun_hero_time.set_text(time_str)
            if elevation_deg is not None:
                elev_str = f"{elevation_deg:+.1f}°"
                if elevation_deg > 0:
                    state = "День" if is_ru else "Daylight"
                elif elevation_deg >= -6.0:
                    state = "Сумерки" if is_ru else "Twilight"
                else:
                    state = "Ночь" if is_ru else "Night"
                self.lbl_sun_hero_sub.set_text(f"{state} • Высота солнца: {elev_str}" if is_ru else f"{state} • Solar elevation: {elev_str}")
        else:
            sd = self.data.get('solar_details') or {}
            sr_val = sd.get('sunrise', '06:40')
            self.lbl_sun_hero_time.set_text(sr_val)
            dl_val = sd.get('daylight_str', '12 ч 52 мин')
            self.lbl_sun_hero_sub.set_text(f"{t('weather_daylight_duration')}: {dl_val}")

    def _refresh_sun_view(self):
        sd = self.data.get('solar_details')
        lat = self.data.get('lat', 53.7557)
        lon = self.data.get('lon', 87.1099)
        utc_off = self.data.get('utc_offset_seconds', 0) / 3600.0
        cur_lang = get_current_language()
        from datetime import timezone as dt_timezone
        city_date = (datetime.now(dt_timezone.utc) + timedelta(hours=utc_off)).date()

        if not sd:
            from providers.weather import calculate_annual_solar_table, calculate_solar_details
            sd = calculate_solar_details(lat, lon, city_date, utc_off, lang=cur_lang)
            sd['annual_table'] = calculate_annual_solar_table(lat, lon, utc_off, lang=cur_lang)
            self.data['solar_details'] = sd
        elif 'annual_table' not in sd:
            from providers.weather import calculate_annual_solar_table
            sd['annual_table'] = calculate_annual_solar_table(lat, lon, utc_off, lang=cur_lang)

        # 1. Hero
        sr_val = sd.get('sunrise', '06:40')
        dl_val = sd.get('daylight_str', '12 ч 52 мин')
        self.lbl_sun_hero_time.set_text(sr_val)
        self.lbl_sun_hero_sub.set_text(f"{t('weather_daylight_duration')}: {dl_val}")

        # 2. Chart
        utc_off = self.data.get('utc_offset_seconds', 0)
        from datetime import timezone as dt_timezone
        utc_now = datetime.now(dt_timezone.utc)
        city_now = utc_now + timedelta(seconds=utc_off)
        cur_hour_frac = city_now.hour + city_now.minute / 60.0 + city_now.second / 3600.0

        self.sun_arc_chart.set_solar_data(sd, cur_hour_frac)

        # 3. Metrics card
        self.lbl_first_light_val.set_text(sd.get('first_light', '--:--'))
        self.lbl_sunrise_val.set_text(sd.get('sunrise', '--:--'))
        self.lbl_sunset_val.set_text(sd.get('sunset', '--:--'))
        self.lbl_last_light_val.set_text(sd.get('last_light', '--:--'))
        self.lbl_daylight_val.set_text(dl_val)

        # 4. Annual table
        ann = sd.get('annual_table', {})
        self.lbl_ann_longest_day.set_text(ann.get('longest_day_str', ''))
        self.climate_sun_table.update_data(ann, current_m_idx=city_now.month - 1)


    # -------------------------------------------------------------------------
    # Moon View Methods
    # -------------------------------------------------------------------------
    def _create_moon_metric_row(self, title: str, value: str):
        return create_moon_metric_row(title, value)

    def _build_moon_view(self):
        build_moon_view(self)

    def _on_moon_ruler_scrub(self, offset_hours: float, target_dt: datetime):
        is_scrubbed = abs(offset_hours) > 0.1
        self.btn_moon_reset.set_visible(is_scrubbed)

        lat = self.data.get('lat', 53.7557)
        lon = self.data.get('lon', 87.1099)
        utc_off = self.data.get('utc_offset_seconds', 0) / 3600.0
        cur_lang = get_current_language()

        from providers.weather import calculate_detailed_moon
        d_moon = calculate_detailed_moon(lat, lon, target_dt, utc_off, lang=cur_lang)

        self.moon_sphere.set_phase(d_moon['cycle_fraction'], d_moon['illumination'], d_moon['tilt_deg'])
        self.lbl_moon_hero_title.set_label(d_moon['phase_name'])

        if is_scrubbed:
            from i18n import format_day_month
            date_str = format_day_month(target_dt.day, target_dt.month, lang=cur_lang)
            self.lbl_moon_hero_sub.set_label(f"{date_str} · {t('weather_moon_illumination')}: {d_moon['illumination']}%")
        else:
            self.lbl_moon_hero_sub.set_label(f"{t('weather_moon_illumination')}: {d_moon['illumination']}%")

        self.lbl_m_illum_val.set_label(f"{d_moon['illumination']}%")
        self.lbl_m_rise_val.set_label(d_moon['moonrise'])
        self.lbl_m_set_val.set_label(d_moon['moonset'])
        self.lbl_m_full_val.set_label(t('weather_in_n_days').format(n=d_moon['days_to_full']))
        self.lbl_m_dist_val.set_label(d_moon['distance_str'])

        if target_dt.year == self.moon_calendar.year and target_dt.month == self.moon_calendar.month:
            self.moon_calendar.set_selected_day(target_dt.day)

    def _on_moon_reset_clicked(self):
        self.moon_ruler.reset_to_now()
        self._refresh_moon_view()

    def _on_moon_calendar_day_selected(self, year: int, month: int, day: int):
        target_dt = datetime(year, month, day, 12, 0)
        utc_off = self.data.get('utc_offset_seconds', 0)
        from datetime import timezone as dt_timezone
        utc_now = datetime.now(dt_timezone.utc)
        city_now = utc_now + timedelta(seconds=utc_off)
        diff_hours = (target_dt - city_now.replace(tzinfo=None)).total_seconds() / 3600.0
        self.moon_ruler.set_offset_hours(diff_hours, trigger_callback=True)

    def _refresh_moon_view(self):
        d_moon = self.data.get('detailed_moon')
        lat = self.data.get('lat', 53.7557)
        lon = self.data.get('lon', 87.1099)
        utc_off = self.data.get('utc_offset_seconds', 0) / 3600.0
        cur_lang = get_current_language()

        from datetime import timezone as dt_timezone
        utc_now = datetime.now(dt_timezone.utc)
        city_now = utc_now + timedelta(seconds=self.data.get('utc_offset_seconds', 0))

        if not d_moon:
            from providers.weather import calculate_detailed_moon
            d_moon = calculate_detailed_moon(lat, lon, city_now, utc_off, lang=cur_lang)
            self.data['detailed_moon'] = d_moon

        # Set base datetime on ruler and reset
        self.moon_ruler.set_base_datetime(city_now.replace(tzinfo=None))
        self.moon_ruler.reset_to_now()

        # Update hero
        self.lbl_moon_hero_title.set_label(d_moon.get('phase_name', ''))
        self.lbl_moon_hero_sub.set_label(f"{t('weather_moon_illumination')}: {d_moon.get('illumination', 0)}%")
        self.btn_moon_reset.set_visible(False)

        # Update sphere
        self.moon_sphere.set_phase(d_moon.get('cycle_fraction', 0.0), d_moon.get('illumination', 0), d_moon.get('tilt_deg', 0.0))

        # Update metrics card
        self.lbl_m_illum_val.set_label(f"{d_moon.get('illumination', 0)}%")
        self.lbl_m_rise_val.set_label(d_moon.get('moonrise', '--:--'))
        self.lbl_m_set_val.set_label(d_moon.get('moonset', '--:--'))
        self.lbl_m_full_val.set_label(t('weather_in_n_days').format(n=d_moon.get('days_to_full', 0)))
        self.lbl_m_dist_val.set_label(d_moon.get('distance_str', ''))

        # Update calendar to today's month & day
        self.moon_calendar.update_location(lat, lon, utc_off)
        self.moon_calendar.year = city_now.year
        self.moon_calendar.month = city_now.month
        self.moon_calendar.set_selected_day(city_now.day)
