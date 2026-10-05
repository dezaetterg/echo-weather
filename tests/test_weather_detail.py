import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import ConfigManager
from providers.weather import WeatherProvider


@pytest.fixture
def weather_provider(tmp_path):
    cfg = ConfigManager(config_dir=tmp_path)
    return WeatherProvider(cfg)


def test_weather_detail_sheet_units(weather_provider, monkeypatch):
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from weather_detail_sheet import WeatherDetailSheet

    monkeypatch.setattr(weather_provider, "_fetch_forecast_sync", lambda *args, **kwargs: None)
    res = weather_provider.search("москва", limit=1)
    data = res[0].preview_data

    sheet = WeatherDetailSheet(data=data, on_back_callback=lambda: None, temp_unit="fahrenheit")
    assert sheet.temp_unit == "fahrenheit"

    # Verify switching mode and switching unit
    sheet.set_mode("averages")
    sheet.set_temp_unit("celsius")
    assert sheet.temp_unit == "celsius"
    sheet.set_temp_unit("fahrenheit")
    assert sheet.temp_unit == "fahrenheit"

    # Verify smooth transition properties
    assert sheet.mode_stack.get_interpolate_size() is True
    assert sheet.mode_stack.get_transition_duration() == 280
    assert sheet.averages_stack.get_interpolate_size() is True
    assert sheet.averages_stack.get_transition_duration() == 280


def test_weather_popover_descriptions_localization():
    from i18n import i18n, t
    modes = ['conditions', 'uv', 'wind', 'precipitation', 'sun', 'moon', 'humidity', 'visibility', 'pressure', 'averages']

    i18n.set_language('ru')
    for m in modes:
        desc = t(f'weather_mode_desc_{m}')
        assert desc != f'weather_mode_desc_{m}', f'Missing RU translation for mode {m}'
        assert len(desc) > 0

    i18n.set_language('en')
    for m in modes:
        desc = t(f'weather_mode_desc_{m}')
        assert desc != f'weather_mode_desc_{m}', f'Missing EN translation for mode {m}'
        assert len(desc) > 0

    i18n.set_language('ru')


def test_base_weather_hourly_area_hierarchy():
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from weather_detail_sheet import (
        BaseWeatherHourlyArea,
        HumidityHourlyArea,
        PrecipitationHourlyArea,
        PressureHourlyArea,
        UVHourlyArea,
        VisibilityHourlyArea,
        WindHourlyArea,
    )

    area_classes = [
        UVHourlyArea,
        WindHourlyArea,
        PrecipitationHourlyArea,
        HumidityHourlyArea,
        VisibilityHourlyArea,
        PressureHourlyArea,
    ]

    for cls in area_classes:
        assert issubclass(cls, BaseWeatherHourlyArea)
        instance = cls()
        assert isinstance(instance, BaseWeatherHourlyArea)
        assert isinstance(instance, Gtk.DrawingArea)
        assert hasattr(instance, "drag_gesture")
        assert hasattr(instance, "_calc_frac_h")
        assert instance.is_scrubbing is False
        assert instance.cur_hour == 12
        # Verify frac_h clamp helper
        assert instance._calc_frac_h(0, 20, 100) == 0.0
        assert instance._calc_frac_h(120, 20, 100) == 23.0
        assert 0.0 <= instance._calc_frac_h(70, 20, 100) <= 23.0


def test_atmospheric_capsule_and_weather_atmosphere_box():
    from weather_atmosphere import AtmosphericCapsuleBox, WeatherAtmosphereBox

    # Test standalone AtmosphericCapsuleBox with zero corner radius
    capsule = AtmosphericCapsuleBox(corner_radius=0.0)
    assert capsule.corner_radius == 0.0
    assert capsule._weather_data is None

    # Test setting rain weather data
    rain_data = {
        "condition_code": 61,
        "is_day": 1,
        "bg_class": "weather-bg-rain-day",
        "time_of_day": "day",
        "temperature": 14.0,
    }
    capsule.set_weather_atmosphere(rain_data)
    assert capsule._is_rain() is True
    assert capsule._is_drizzle() is False
    assert capsule._is_night() is False
    assert capsule.has_css_class("weather-canvas-rain-day")

    # Test rain particles initialization
    capsule._init_particles(960.0, 720.0, mode="rain")
    assert capsule._particle_mode == "rain"
    assert len(capsule._particles) >= 100

    # Test mostly clear / partly cloudy condition ("в основном")
    mostly_clear_data = {
        "condition_code": 1,
        "is_day": 1,
        "bg_class": "weather-bg-clear-day",
        "time_of_day": "day",
        "temperature": 21.0,
    }
    capsule.set_weather_atmosphere(mostly_clear_data)
    assert capsule._is_mostly_clear() is True
    assert capsule._is_rain() is False

    mostly_cloudy_data = {
        "condition_code": 2,
        "is_day": 1,
        "bg_class": "weather-bg-clouds-day",
        "time_of_day": "day",
        "temperature": 18.0,
    }
    capsule.set_weather_atmosphere(mostly_cloudy_data)
    assert capsule._is_mostly_cloudy() is True

    # Test WeatherAtmosphereBox subclassing and nesting delegation
    sub_box = WeatherAtmosphereBox(data=rain_data, corner_radius=0.0)
    assert isinstance(sub_box, AtmosphericCapsuleBox)
    assert sub_box._is_rain() is True

    # When nested inside another AtmosphericCapsuleBox, it delegates full rendering to parent
    capsule.append(sub_box)
    assert sub_box._has_capsule_atmosphere() is True

