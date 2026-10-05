import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config_manager import ConfigManager
from providers.weather import WeatherProvider


def test_ui_race_condition_protection(monkeypatch, tmp_path):
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from ui import EchoWeatherWindow

    cfg = ConfigManager(config_dir=tmp_path)
    provider = WeatherProvider(cfg)

    orig_load_city = EchoWeatherWindow.load_city
    # Prevent automatic background fetch on init
    monkeypatch.setattr(EchoWeatherWindow, "load_city", lambda self, city, force_refresh=False: None)

    app = Gtk.Application(application_id="com.echo.weather.race.test")
    win = EchoWeatherWindow(app=app, initial_city="Москва", config_manager=cfg)

    # Restore original load_city behavior without real network calls
    def mock_submit(fn, req_id, target_city):
        pass # manual execution in test

    win._fetch_executor.submit = mock_submit

    # Simulate user rapidly clicking between cities: Москва -> Лондон -> Париж
    # Calling actual load_city logic to increment generations
    orig_load_city(win, "Москва")
    assert win._current_request_id == 1
    assert win.current_city == "Москва"

    orig_load_city(win, "Лондон")
    assert win._current_request_id == 2
    assert win.current_city == "Лондон"

    orig_load_city(win, "Париж")
    assert win._current_request_id == 3
    assert win.current_city == "Париж"

    # Mock weather payload
    data_moscow = {"city_name": "Москва", "temp": 10, "bg_class": "weather-bg-clear-day"}
    data_london = {"city_name": "Лондон", "temp": 14, "bg_class": "weather-bg-clouds-day"}
    data_paris = {"city_name": "Париж", "temp": 18, "bg_class": "weather-bg-clear-day"}

    # Simulate late arrival of Moscow response (generation 1)
    res_stale_1 = win._on_weather_fetched(data_moscow, "Москва", request_id=1)
    assert res_stale_1 is False
    assert win.current_weather_data is None

    # Simulate late arrival of London response (generation 2)
    res_stale_2 = win._on_weather_fetched(data_london, "Лондон", request_id=2)
    assert res_stale_2 is False
    assert win.current_weather_data is None

    # Simulate fresh arrival of Paris response (generation 3)
    res_valid = win._on_weather_fetched(data_paris, "Париж", request_id=3)
    assert win.current_weather_data == data_paris
    assert win.current_city == "Париж"

    # Clean shutdown
    win.destroy()
