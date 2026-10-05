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


def test_weather_overview_view_build(weather_provider, monkeypatch):
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from weather_detail_sheet import TempCapsuleBarArea
    from weather_overview_view import (
        MiniClimateNormGauge,
        MiniHumidityGauge,
        MiniPressureGauge,
        MiniSunCurve,
        MiniUVArc,
        MiniWindCompass,
        WeatherOverviewView,
    )

    monkeypatch.setattr(weather_provider, "_fetch_forecast_sync", lambda *args, **kwargs: None)
    res = weather_provider.search("москва", limit=1)
    data = res[0].preview_data

    opened_modes = []
    opened_days = []

    def on_mode(mode_id):
        opened_modes.append(mode_id)

    def on_day(day_idx):
        opened_days.append(day_idx)

    view = WeatherOverviewView(
        data=data,
        temp_unit="celsius",
        on_open_mode_callback=on_mode,
        on_open_day_callback=on_day,
    )

    assert isinstance(view, Gtk.Box)
    assert view.temp_unit == "celsius"
    assert hasattr(view, "content_box")

    # Test unit change
    view.set_temp_unit("fahrenheit")
    assert view.temp_unit == "fahrenheit"


    # Test callback invocation
    view._open_mode("uv")
    assert opened_modes == ["uv"]

    view._open_day(2)
    assert opened_days == [2]

    # Test TempCapsuleBarArea with current_temp
    capsule = TempCapsuleBarArea(t_min=10, t_max=20, global_min=5, global_max=25, current_temp=15)
    assert capsule.current_temp == 15
    capsule.update_data(t_min=12, t_max=22, global_min=5, global_max=25, current_temp=18)
    assert capsule.current_temp == 18

    # Test Bento Cairo mini widgets
    uv_arc = MiniUVArc(uv_index=4.5)
    assert isinstance(uv_arc, Gtk.DrawingArea)
    assert uv_arc.uv_index == 4.5

    sun_curve = MiniSunCurve(sunrise_str="05:30", sunset_str="20:45", is_day=1)
    assert isinstance(sun_curve, Gtk.DrawingArea)
    assert sun_curve.is_day is True

    wind_compass = MiniWindCompass(wind_dir=180)
    assert isinstance(wind_compass, Gtk.DrawingArea)
    assert wind_compass.wind_dir == 180

    press_gauge = MiniPressureGauge(pressure_mm=755)
    assert isinstance(press_gauge, Gtk.DrawingArea)
    assert press_gauge.pressure_mm == 755

    hum_gauge = MiniHumidityGauge(humidity=65)
    assert isinstance(hum_gauge, Gtk.DrawingArea)
    assert hum_gauge.humidity == 65

    norm_gauge = MiniClimateNormGauge(avg_diff_str="+3° к норме")
    assert isinstance(norm_gauge, Gtk.DrawingArea)
    assert norm_gauge.avg_diff_str == "+3° к норме"
