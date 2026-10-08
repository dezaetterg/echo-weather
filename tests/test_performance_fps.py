import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.weather import (
    CurrentConditions,
    DailyForecast,
    DayDetailedForecast,
    DetailedMoon,
    HourlyForecast,
    SolarDetails,
    WeatherForecastData,
)
from providers.weather import get_fallback_data
from weather_atmosphere import (
    MOON_GLOW_STOPS,
    NIGHT_STOPS,
    AtmosphericCapsuleBox,
)


def test_weather_data_fast_access_benchmark():
    raw = get_fallback_data("Москва")
    weather = WeatherForecastData.from_dict(raw)
    assert isinstance(weather, WeatherForecastData)

    # 100,000 lookups simulating 60 FPS animation over multiple frames
    start_time = time.monotonic()
    for _ in range(100000):
        _ = weather.get("temp")
        _ = weather["humidity"]
        _ = "pressure_mm" in weather
        _ = weather.get("weather_code")
        _ = weather.get("city")
    duration = time.monotonic() - start_time

    # Must complete 500,000 dict operations in less than 0.20 seconds (O(1) access)
    assert duration < 0.20, f"Dictionary access too slow: {duration:.4f}s for 100k iterations"


def test_atmospheric_capsule_gradient_caching():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    box = AtmosphericCapsuleBox()

    # Linear gradient caching identity test
    grad1 = box._get_cached_linear_grad("night", 560.0, NIGHT_STOPS)
    grad2 = box._get_cached_linear_grad("night", 560.0, NIGHT_STOPS)
    assert grad1 is grad2, "LinearGradient must be cached and reused across frames"

    # Radial gradient caching identity test
    params = (800.0, 0.0, 10.0, 800.0, 80.0, 350.0)
    r_grad1 = box._get_cached_radial_grad("moon_glow", params, MOON_GLOW_STOPS)
    r_grad2 = box._get_cached_radial_grad("moon_glow", params, MOON_GLOW_STOPS)
    assert r_grad1 is r_grad2, "RadialGradient must be cached and reused across frames"

    # Dusk stars caching test
    dusk1 = box._ensure_dusk_stars(1070.0, 560.0)
    dusk2 = box._ensure_dusk_stars(1070.0, 560.0)
    assert dusk1 is dusk2, "Dusk stars list must be cached and reused"
    assert len(dusk1) == 65


def test_frame_throttling_accumulation():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk
    Gtk.init()

    box = AtmosphericCapsuleBox()
    data = get_fallback_data("Москва")
    # Test with rain (fast dynamic motion, ~60 FPS / 0.016s target interval)
    rain_data = dict(data, weather_code=61, condition_text="Дождь", bg_class="weather-bg-rain-day")
    box.set_weather_atmosphere(rain_data)

    # Initial tick
    res = box._on_tick(box, None)
    assert res == GLib.SOURCE_CONTINUE

    # Rapid second tick under 16ms threshold
    box._last_time = time.monotonic() - 0.005  # 5ms passed
    res = box._on_tick(box, None)
    assert res == GLib.SOURCE_CONTINUE
    # Accumulated dt should hold the 5ms
    assert 0.004 <= box._accumulated_dt <= 0.010

    # Third tick bringing total past 16ms threshold (5ms + 12ms = 17ms)
    box._last_time = time.monotonic() - 0.012  # another 12ms passed
    res = box._on_tick(box, None)
    assert res == GLib.SOURCE_CONTINUE
    # Threshold met: accumulated dt reset
    assert box._accumulated_dt == 0.0


def test_adaptive_framerate_by_weather_condition():
    box = AtmosphericCapsuleBox()

    # Rain and drizzle -> 60 FPS (~0.016s)
    box.set_weather_atmosphere({"weather_code": 61, "condition_text": "Дождь", "bg_class": "weather-bg-rain-day"})
    assert box._get_target_frame_interval() == 0.016

    box.set_weather_atmosphere({"weather_code": 51, "condition_text": "Морось", "bg_class": "weather-bg-drizzle-day"})
    assert box._get_target_frame_interval() == 0.016

    # Night, Overcast, Clouds, Dusk -> 30 FPS (~0.033s)
    box.set_weather_atmosphere({"weather_code": 0, "is_day": 0, "time_of_day": "night", "condition_text": "Ясно", "bg_class": "weather-bg-clear-night"})
    assert box._get_target_frame_interval() == 0.033

    box.set_weather_atmosphere({"weather_code": 3, "condition_text": "Пасмурно", "bg_class": "weather-bg-clouds-day"})
    assert box._get_target_frame_interval() == 0.033

    box.set_weather_atmosphere({"weather_code": 2, "condition_text": "Переменная облачность", "bg_class": "weather-bg-clouds-day"})
    assert box._get_target_frame_interval() == 0.033

    box.set_weather_atmosphere({"weather_code": 1, "time_of_day": "dusk", "condition_text": "В основном ясно", "bg_class": "weather-bg-clear-dusk"})
    assert box._get_target_frame_interval() == 0.033

    # Clear day without particles or clouds -> low motion (~0.066s)
    box.set_weather_atmosphere({"weather_code": 0, "is_day": 1, "time_of_day": "day", "condition_text": "Ясно", "bg_class": "weather-bg-clear-day"})
    assert box._get_target_frame_interval() == 0.066


def test_power_modes_frame_intervals():
    class DummyConfig:
        def __init__(self, mode="balanced", power_save=False):
            self._data = {"power_mode": mode, "power_save": power_save}

        def get(self, key, default=None):
            return self._data.get(key, default)

    # Balanced mode
    box_b = AtmosphericCapsuleBox(config_manager=DummyConfig("balanced"))
    box_b.set_weather_atmosphere({"weather_code": 61, "condition_text": "Дождь", "bg_class": "weather-bg-rain-day"})
    assert box_b._get_target_frame_interval() == 0.028

    box_b.set_weather_atmosphere({"weather_code": 3, "condition_text": "Пасмурно", "bg_class": "weather-bg-clouds-day"})
    assert box_b._get_target_frame_interval() == 0.045

    # Power saver mode
    box_ps = AtmosphericCapsuleBox(config_manager=DummyConfig("power_saver"))
    box_ps.set_weather_atmosphere({"weather_code": 61, "condition_text": "Дождь", "bg_class": "weather-bg-rain-day"})
    assert box_ps._get_target_frame_interval() == 0.040

    box_ps.set_weather_atmosphere({"weather_code": 3, "condition_text": "Пасмурно", "bg_class": "weather-bg-clouds-day"})
    assert box_ps._get_target_frame_interval() == 0.066

    # Performance mode explicitly
    box_perf = AtmosphericCapsuleBox(config_manager=DummyConfig("performance"))
    box_perf.set_weather_atmosphere({"weather_code": 61, "condition_text": "Дождь", "bg_class": "weather-bg-rain-day"})
    assert box_perf._get_target_frame_interval() == 0.016


def test_pause_and_resume_animation():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk
    Gtk.init()

    box = AtmosphericCapsuleBox()
    data = {"weather_code": 61, "condition_text": "Дождь", "bg_class": "weather-bg-rain-day"}
    box.set_weather_atmosphere(data)

    assert box.is_animation_paused() is False

    # Pause animation
    box.pause_animation()
    assert box.is_animation_paused() is True
    assert box._tick_id is None

    # Ticking while paused should not advance accumulated dt
    box._accumulated_dt = 0.0
    res = box._on_tick(box, None)
    assert res == GLib.SOURCE_CONTINUE
    assert box._accumulated_dt == 0.0

    # Resume animation
    box.resume_animation()
    assert box.is_animation_paused() is False


def test_static_layer_background_caching():
    import gi
    gi.require_version("Gtk", "4.0")
    import cairo
    from gi.repository import Gtk
    Gtk.init()

    box = AtmosphericCapsuleBox()
    data = {"weather_code": 0, "is_day": 0, "time_of_day": "night", "condition_text": "Ясно", "bg_class": "weather-bg-clear-night"}
    box.set_weather_atmosphere(data)

    surf1 = box._get_or_render_static_bg(1070.0, 560.0)
    assert isinstance(surf1, cairo.ImageSurface)
    assert surf1.get_width() == 1070
    assert surf1.get_height() == 560

    # Cache hit returns identical surface object
    surf2 = box._get_or_render_static_bg(1070.0, 560.0)
    assert surf1 is surf2

    # Invalidation clears cache
    box.invalidate_background_cache()
    surf3 = box._get_or_render_static_bg(1070.0, 560.0)
    assert surf3 is not surf1
    assert isinstance(surf3, cairo.ImageSurface)

    # Size change invalidates cache automatically
    surf_resized = box._get_or_render_static_bg(800.0, 400.0)
    assert surf_resized.get_width() == 800
    assert surf_resized.get_height() == 400
    assert surf_resized is not surf3



def test_stress_animation_loop_cpu():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk
    Gtk.init()

    box = AtmosphericCapsuleBox()
    data = get_fallback_data("Санкт-Петербург")
    box.set_weather_atmosphere(data)

    t0 = time.monotonic()
    for _ in range(300):
        box._last_time = time.monotonic() - 0.017  # 17ms per frame (60 FPS)
        box._on_tick(box, None)
    total_elapsed = time.monotonic() - t0

    # 300 animation steps should take negligible CPU time (< 0.25s total)
    assert total_elapsed < 0.25, f"300 animation ticks took too long: {total_elapsed:.4f}s"
    box._stop_animation()
    assert box._tick_id is None


def test_weather_button_styles():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    css_path = Path(__file__).parent.parent / "style.css"
    assert css_path.exists(), "style.css must exist"

    provider = Gtk.CssProvider()
    provider.load_from_path(str(css_path))

    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify universal button reset and specific button classes
    assert "window.weather-window button" in content
    assert "button.city-pill-btn" in content
    assert "button.unit-toggle-btn" in content
    assert "button.weather-refresh-btn" in content
    assert "headerbar windowcontrols button" in content
    assert "button.weather-back-btn" in content
    assert "button.weather-moon-reset-btn" in content
    assert "button.weather-cal-nav-btn" in content
    assert "button.weather-day-pill" in content
    assert "button.segmented-btn" in content
    assert "rgba(255, 255, 255" in content
