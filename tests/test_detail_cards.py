"""
Тесты модульной системы карточек детального анализа погоды detail_cards.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk

Gtk.init()

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
)


def test_detail_cards_widget_instantiation():
    """Проверка создания и начальных состояний виджетов карточек."""
    # 1. Base and hourly scrubbers
    spline = WeatherSplineArea()
    assert isinstance(spline, Gtk.DrawingArea)
    assert spline.is_scrubbing is False

    uv = UVHourlyArea()
    assert isinstance(uv, BaseWeatherHourlyArea)

    wind = WindHourlyArea()
    assert isinstance(wind, BaseWeatherHourlyArea)

    precip = PrecipitationHourlyArea()
    assert isinstance(precip, BaseWeatherHourlyArea)

    hum = HumidityHourlyArea()
    assert isinstance(hum, BaseWeatherHourlyArea)

    vis = VisibilityHourlyArea()
    assert isinstance(vis, BaseWeatherHourlyArea)

    press = PressureHourlyArea()
    assert isinstance(press, BaseWeatherHourlyArea)

    # 2. Comparison bars
    comp_day = DayComparisonBarArea()
    assert isinstance(comp_day, Gtk.DrawingArea)

    comp_std = ComparisonBarArea()
    assert isinstance(comp_std, Gtk.DrawingArea)

    # 3. Special visual widgets
    compass = WindCompassArea()
    assert isinstance(compass, Gtk.DrawingArea)

    gauge = PressureGaugeArea()
    assert isinstance(gauge, Gtk.DrawingArea)

    sun_bar = SunDaylightBar()
    assert isinstance(sun_bar, Gtk.DrawingArea)

    sun_arc = SunArcChartArea()
    assert isinstance(sun_arc, Gtk.DrawingArea)

    moon_ruler = MoonTimelineRuler()
    assert isinstance(moon_ruler, Gtk.DrawingArea)

    moon_icon = MiniMoonIcon(0.5)
    assert isinstance(moon_icon, Gtk.DrawingArea)

    # 4. Tables and calendar boxes
    sun_table = ClimateSunYearTable()
    assert isinstance(sun_table, Gtk.Box)

    temp_table = ClimateMonthlyTempTable()
    assert isinstance(temp_table, Gtk.Box)

    precip_table = ClimateMonthlyPrecipTable()
    assert isinstance(precip_table, Gtk.Box)

    moon_cal = MoonCalendarCard(lat=55.75, lon=37.61, utc_offset_hours=3.0)
    assert isinstance(moon_cal, Gtk.Box)


def test_detail_cards_hourly_calc_frac():
    """Проверка математики интерполяции часов в скрубберах."""
    uv = UVHourlyArea()
    # Left bound clamp
    assert uv._calc_frac_h(10, 20, 100) == 0.0
    # Right bound clamp
    assert uv._calc_frac_h(150, 20, 100) == 23.0
    # Exact midpoint
    mid = uv._calc_frac_h(70, 20, 100)
    assert 11.0 <= mid <= 12.0
