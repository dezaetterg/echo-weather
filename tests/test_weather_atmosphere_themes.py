import datetime
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import ConfigManager
from providers.weather import WeatherProvider, determine_solar_time_of_day, get_fallback_data


def test_determine_solar_time_of_day():
    # Moscow (lat 55.75, lon 37.61) on 2026-10-01 at 01:00 UTC (04:00 MSK - night)
    dt_night = datetime.datetime(2026, 10, 1, 1, 0, tzinfo=datetime.timezone.utc)
    tod_night, is_day_night = determine_solar_time_of_day(55.75, 37.61, dt_night)
    assert tod_night == "night"
    assert is_day_night == 0

    # Moscow on 2026-10-01 at 09:00 UTC (12:00 MSK - solar noon)
    dt_day = datetime.datetime(2026, 10, 1, 9, 0, tzinfo=datetime.timezone.utc)
    tod_day, is_day_day = determine_solar_time_of_day(55.75, 37.61, dt_day)
    assert tod_day == "day"
    assert is_day_day == 1

    # Sunrise around ~03:30 UTC for Moscow in early October
    dt_dawn = datetime.datetime(2026, 10, 1, 3, 30, tzinfo=datetime.timezone.utc)
    tod_dawn, is_day_dawn = determine_solar_time_of_day(55.75, 37.61, dt_dawn)
    assert tod_dawn in ("dusk", "dawn", "night", "day")


def test_fallback_data_has_dynamic_time_of_day():
    fallback = get_fallback_data("Москва")
    assert fallback is not None
    assert "time_of_day" in fallback
    assert fallback["time_of_day"] in ("day", "night", "dusk", "dawn")
    assert fallback["is_day"] in (0, 1)
    assert "bg_class" in fallback
    assert "grad_class" in fallback
    assert "weather-bg-" in fallback["bg_class"]


def test_weather_atmosphere_night_clear():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from weather_atmosphere import AtmosphericCapsuleBox

    box = AtmosphericCapsuleBox()
    data = {
        "weather_code": 0,
        "is_day": 0,
        "time_of_day": "night",
        "bg_class": "weather-bg-clear-night",
        "condition_text": "Ясно",
    }
    box.set_weather_atmosphere(data)

    assert box._is_night() is True
    assert box._is_dusk() is False
    assert box._is_mostly_clear() is False
    assert box._is_overcast() is False
    assert "weather-canvas-active" in box.get_css_classes()
    assert "weather-canvas-clear-night" in box.get_css_classes()
    assert "weather-night-mode" in box.get_css_classes()
    assert "weather-dusk-mode" not in box.get_css_classes()


def test_weather_atmosphere_night_mostly_clear():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from weather_atmosphere import AtmosphericCapsuleBox

    box = AtmosphericCapsuleBox()
    data = {
        "weather_code": 1,
        "is_day": 0,
        "time_of_day": "night",
        "bg_class": "weather-bg-clear-night",
        "condition_text": "В основном ясно",
    }
    box.set_weather_atmosphere(data)

    assert box._is_night() is True
    assert box._is_mostly_clear() is True
    assert box._is_overcast() is False
    assert "weather-night-mode" in box.get_css_classes()
    assert "weather-canvas-clear-night" in box.get_css_classes()


def test_weather_atmosphere_night_overcast():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from weather_atmosphere import AtmosphericCapsuleBox

    box = AtmosphericCapsuleBox()
    data = {
        "weather_code": 3,
        "is_day": 0,
        "time_of_day": "night",
        "bg_class": "weather-bg-clouds-night",
        "condition_text": "Пасмурно",
    }
    box.set_weather_atmosphere(data)

    assert box._is_night() is True
    assert box._is_overcast() is True
    assert "weather-night-mode" in box.get_css_classes()
    assert "weather-canvas-clouds-night" in box.get_css_classes()


def test_weather_atmosphere_night_rain():
    import gi
    gi.require_version("Gtk", "4.0")
    import cairo
    from gi.repository import Gtk
    Gtk.init()

    from weather_atmosphere import AtmosphericCapsuleBox

    box = AtmosphericCapsuleBox()
    data = {
        "city_name": "Онтарио",
        "weather_code": 65,
        "is_day": 0,
        "time_of_day": "night",
        "bg_class": "weather-bg-rain-night",
        "condition_text": "Сильный дождь",
    }
    box.set_weather_atmosphere(data)

    assert box._is_night() is True
    assert box._is_rain() is True
    assert box._is_drizzle() is False
    assert box._get_weather_mode_signature() == "rain_night"
    assert "weather-canvas-rain-night" in box.get_css_classes()
    assert "weather-night-mode" in box.get_css_classes()
    assert box._get_target_frame_interval() == 0.016
    assert box._particle_mode == "rain"
    assert len(box._particles) == 125

    surf = box._get_or_render_static_bg(1070.0, 560.0)
    assert isinstance(surf, cairo.ImageSurface)
    assert surf.get_width() == 1070
    assert surf.get_height() == 560


def test_weather_atmosphere_night_drizzle():
    import gi
    gi.require_version("Gtk", "4.0")
    import cairo
    from gi.repository import Gtk
    Gtk.init()

    from weather_atmosphere import AtmosphericCapsuleBox

    box = AtmosphericCapsuleBox()
    data = {
        "city_name": "Санкт-Петербург",
        "weather_code": 51,
        "is_day": 0,
        "time_of_day": "night",
        "bg_class": "weather-bg-drizzle-night",
        "condition_text": "Морось",
    }
    box.set_weather_atmosphere(data)

    assert box._is_night() is True
    assert box._is_drizzle() is True
    assert box._is_rain() is False
    assert box._get_weather_mode_signature() == "drizzle_night"
    assert "weather-canvas-drizzle-night" in box.get_css_classes()
    assert "weather-night-mode" in box.get_css_classes()
    assert box._get_target_frame_interval() == 0.016
    assert box._particle_mode == "drizzle"
    assert len(box._particles) == 85

    surf = box._get_or_render_static_bg(1070.0, 560.0)
    assert isinstance(surf, cairo.ImageSurface)
    assert surf.get_width() == 1070
    assert surf.get_height() == 560


def test_weather_atmosphere_dusk_modes():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from weather_atmosphere import AtmosphericCapsuleBox

    # 1. Dusk with clear sky
    box_clear = AtmosphericCapsuleBox()
    data_clear = {
        "weather_code": 0,
        "is_day": 1,
        "time_of_day": "dusk",
        "bg_class": "weather-bg-clear-dusk",
        "condition_text": "Ясно",
    }
    box_clear.set_weather_atmosphere(data_clear)
    assert box_clear._is_dusk() is True
    assert box_clear._is_night() is False
    assert "weather-dusk-mode" in box_clear.get_css_classes()
    assert "weather-night-mode" not in box_clear.get_css_classes()
    assert "weather-canvas-clear-dusk" in box_clear.get_css_classes()

    # 2. Dusk with mostly clear sky (Ontario pattern with cirrus clouds)
    box_mostly = AtmosphericCapsuleBox()
    data_mostly = {
        "weather_code": 1,
        "is_day": 1,
        "time_of_day": "dusk",
        "bg_class": "weather-bg-clear-dusk",
        "condition_text": "В основном ясно",
    }
    box_mostly.set_weather_atmosphere(data_mostly)
    assert box_mostly._is_dusk() is True
    assert box_mostly._is_mostly_clear() is True
    assert "weather-dusk-mode" in box_mostly.get_css_classes()
    assert "weather-canvas-clear-dusk" in box_mostly.get_css_classes()


def test_weather_atmosphere_daytime():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from weather_atmosphere import AtmosphericCapsuleBox

    box = AtmosphericCapsuleBox()
    data = {
        "weather_code": 0,
        "is_day": 1,
        "time_of_day": "day",
        "bg_class": "weather-bg-clear-day",
        "condition_text": "Ясно",
    }
    box.set_weather_atmosphere(data)

    assert box._is_night() is False
    assert box._is_dusk() is False
    assert box._is_clear() is True
    assert "weather-canvas-clear-day" in box.get_css_classes()
    assert "weather-night-mode" not in box.get_css_classes()
    assert "weather-dusk-mode" not in box.get_css_classes()


def test_weather_atmosphere_box_delegates_to_parent_capsule():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from weather_atmosphere import AtmosphericCapsuleBox, WeatherAtmosphereBox

    parent = AtmosphericCapsuleBox()
    child = WeatherAtmosphereBox()
    parent.append(child)

    assert child._has_capsule_atmosphere() is True


def test_echo_weather_window_theme_switching(tmp_path, monkeypatch):
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from ui import EchoWeatherWindow

    cfg = ConfigManager(config_dir=tmp_path)
    monkeypatch.setattr(EchoWeatherWindow, "load_city", lambda self, city, force_refresh=False: None)

    app = Gtk.Application(application_id="com.echo.weather.test.theme")
    win = EchoWeatherWindow(app=app, initial_city="Москва", config_manager=cfg)

    # 1. Night clear data
    night_data = {
        "city_name": "Москва",
        "weather_code": 0,
        "is_day": 0,
        "time_of_day": "night",
        "bg_class": "weather-bg-clear-night",
        "condition_text": "Ясно",
        "days_detailed": [],
    }
    win._render_weather_data(night_data)
    assert win.has_css_class("weather-night-mode") is True
    assert win.has_css_class("weather-dusk-mode") is False
    assert win.has_css_class("weather-canvas-clear-night") is True
    assert win.main_box.has_css_class("weather-night-mode") is True

    # 2. Dusk mostly clear data
    dusk_data = {
        "city_name": "Онтарио",
        "weather_code": 1,
        "is_day": 1,
        "time_of_day": "dusk",
        "bg_class": "weather-bg-clear-dusk",
        "condition_text": "В основном ясно",
        "days_detailed": [],
    }
    win._render_weather_data(dusk_data)
    assert win.has_css_class("weather-dusk-mode") is True
    assert win.has_css_class("weather-night-mode") is False
    assert win.has_css_class("weather-canvas-clear-dusk") is True
    assert win.main_box.has_css_class("weather-dusk-mode") is True

    # 3. Daytime clear data
    day_data = {
        "city_name": "Москва",
        "weather_code": 0,
        "is_day": 1,
        "time_of_day": "day",
        "bg_class": "weather-bg-clear-day",
        "condition_text": "Ясно",
        "days_detailed": [],
    }
    win._render_weather_data(day_data)
    assert win.has_css_class("weather-night-mode") is False
    assert win.has_css_class("weather-dusk-mode") is False
    assert win.has_css_class("weather-canvas-clear-day") is True
    assert win.main_box.has_css_class("weather-night-mode") is False

    # 4. Ontario night heavy rain data
    ontario_rain_night = {
        "city_name": "Онтарио",
        "weather_code": 65,
        "is_day": 0,
        "time_of_day": "night",
        "bg_class": "weather-bg-rain-night",
        "condition_text": "Сильный дождь",
        "days_detailed": [],
    }
    win._render_weather_data(ontario_rain_night)
    assert win.has_css_class("weather-night-mode") is True
    assert win.has_css_class("weather-canvas-rain-night") is True
    assert win.main_box.has_css_class("weather-night-mode") is True
    assert win.main_box.has_css_class("weather-canvas-rain-night") is True
    assert win.main_box._particle_mode == "rain"
    assert len(win.main_box._particles) == 125


def test_stars_scale_to_full_window_dimensions():
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from weather_atmosphere import AtmosphericCapsuleBox

    box = AtmosphericCapsuleBox()

    # 1. Full HD screen (1920x1080)
    box._ensure_stars(1920.0, 1080.0)
    assert len(box._stars) >= 500
    xs = [s.x for s in box._stars]
    ys = [s.y for s in box._stars]
    assert min(xs) < 100.0
    assert max(xs) > 1800.0
    assert min(ys) < 60.0
    assert max(ys) > 950.0

    # 2. 2K QHD screen (2560x1440)
    box._ensure_stars(2560.0, 1440.0)
    assert len(box._stars) >= 700
    xs_2k = [s.x for s in box._stars]
    ys_2k = [s.y for s in box._stars]
    assert max(xs_2k) > 2400.0
    assert max(ys_2k) > 1300.0

    # 3. Verify Comet spawns within screen bounds
    box._spawn_comet(1920.0, 1080.0)
    assert len(box._comets) >= 1
    c = box._comets[-1]
    assert c.x >= 0.0
    assert c.y >= 0.0


