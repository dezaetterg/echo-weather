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


def test_echo_weather_window_navigation(weather_provider, monkeypatch, tmp_path):
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, Gtk
    Gtk.init()

    from ui import EchoWeatherWindow

    cfg = ConfigManager(config_dir=tmp_path)
    monkeypatch.setattr(weather_provider, "_fetch_forecast_sync", lambda *args, **kwargs: None)
    res = weather_provider.search("москва", limit=1)
    data = res[0].preview_data
    data["days_detailed"] = [
        {"min": 10, "max": 20, "weekday_short": f"D{i}", "hourly_temps": [15] * 24}
        for i in range(10)
    ]

    # Prevent load_city during init to manually render mock data
    monkeypatch.setattr(EchoWeatherWindow, "load_city", lambda self, city, force_refresh=False: None)

    app = Gtk.Application(application_id="com.echo.weather.test")
    win = EchoWeatherWindow(app=app, initial_city="Москва", config_manager=cfg)
    win.current_weather_data = data
    win._render_weather_data(data)

    # 1. Verify two-level navigation stack configuration
    assert win.nav_stack is not None
    assert win.nav_stack.get_transition_type() == Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
    assert win.nav_stack.get_transition_duration() == 280
    assert win.nav_stack.get_visible_child_name() == "overview"
    assert win.is_detail_open() is False
    assert win.is_overview_open() is True
    assert win.cities_strip.get_visible() is True

    # 2. Test navigation to detail mode and cities_strip hiding
    win.open_detail(mode="pressure", day_idx=3)
    assert win.nav_stack.get_visible_child_name() == "detail"
    assert win.is_detail_open() is True
    assert win.is_overview_open() is False
    assert win.detail_sheet.current_mode == "pressure"
    assert win.detail_sheet.selected_day_idx == 3
    assert win.cities_strip.get_visible() is False

    # 3. Test back navigation via on_back_callback and cities_strip restoring
    win.detail_sheet._on_back()
    assert win.nav_stack.get_visible_child_name() == "overview"
    assert win.is_detail_open() is False
    assert win.is_overview_open() is True
    assert win.cities_strip.get_visible() is True

    # 4. Test unit toggle in both overview and detail views
    assert win.temp_unit == "celsius"
    win._on_unit_toggle(win.unit_btn)
    assert win.temp_unit == "fahrenheit"
    assert win.overview_view.temp_unit == "fahrenheit"
    assert win.detail_sheet.temp_unit == "fahrenheit"

    # 4.1 Test source & model selector button and popover
    assert win.source_btn is not None
    assert ("Consensus" in win.source_btn.get_label() or "Консенсус" in win.source_btn.get_label())
    assert win.source_popover is not None
    assert "consensus" in win._source_popover_buttons
    assert "ecmwf" in win._source_popover_buttons
    assert "icon" in win._source_popover_buttons
    assert "met_norway" in win._source_popover_buttons
    assert "open_meteo" in win._source_popover_buttons

    win._on_source_selected("ecmwf")
    assert cfg.get("forecast_source") == "ecmwf"
    assert "ECMWF" in win.source_btn.get_label()
    win._on_source_selected("consensus")
    assert cfg.get("forecast_source") == "consensus"
    assert ("Consensus" in win.source_btn.get_label() or "Консенсус" in win.source_btn.get_label())


    # 5. Test overview Bento card click triggers navigation to detail
    win.open_overview()
    assert win.is_detail_open() is False
    win.overview_view._open_mode("wind")
    assert win.is_detail_open() is True
    assert win.detail_sheet.current_mode == "wind"

    # 6. Test overview day click triggers navigation to detail with day
    win.open_overview()
    assert win.is_detail_open() is False
    win.overview_view._open_day(4)
    assert win.is_detail_open() is True
    assert win.detail_sheet.selected_day_idx == 4

    # 7. Test Escape key returns to overview
    assert win.is_detail_open() is True
    handled_esc = win._on_key_pressed(None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0))
    assert handled_esc is True
    assert win.is_detail_open() is False
    assert win.is_overview_open() is True

    # 8. Test Alt + Left key shortcut returns to overview
    win.open_detail(mode="uv", day_idx=1)
    assert win.is_detail_open() is True
    handled_alt = win._on_key_pressed(None, Gdk.KEY_Left, 0, Gdk.ModifierType.ALT_MASK)
    assert handled_alt is True
    assert win.is_detail_open() is False
    assert win.is_overview_open() is True

    # 9. Test window active state syncs atmospheric animation pause/resume
    win._sync_atmosphere_animation_state(False)
    assert win.main_box.is_animation_paused() is True
    if win.atmosphere_box:
        assert win.atmosphere_box.is_animation_paused() is True

    win._sync_atmosphere_animation_state(True)
    assert win.main_box.is_animation_paused() is False
    if win.atmosphere_box:
        assert win.atmosphere_box.is_animation_paused() is False


def test_city_pinning_and_horizontal_scroll(tmp_path):
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from ui import EchoWeatherWindow

    cfg = ConfigManager(config_dir=tmp_path)
    cfg.set("saved_cities", ["Москва", "Санкт-Петербург"])

    app = Gtk.Application(application_id="com.echo.weather.test.pins")
    win = EchoWeatherWindow(app=app, initial_city="Москва", config_manager=cfg)

    # 1. Verify ScrolledWindow container exists and wraps cities_strip
    assert isinstance(win.cities_scroll, Gtk.ScrolledWindow)
    scroll_child = win.cities_scroll.get_child()
    assert (scroll_child is win.cities_strip) or (isinstance(scroll_child, Gtk.Viewport) and scroll_child.get_child() is win.cities_strip)

    # 2. Verify pin_btn reflects pinned state for initial city Москва
    assert win.pin_btn is not None
    assert win.pin_btn.has_css_class("active") is True

    # 3. Switching to a new unpinned city does NOT auto-pin it
    new_data = {
        "city_name": "Караганда",
        "temp": 12,
        "weather_code": 3,
        "condition_text": "Пасмурно",
        "bg_class": "weather-bg-clouds-day",
        "days_detailed": [],
    }
    win.current_city = "Караганда"
    win._on_weather_fetched(new_data, "Караганда", win._current_request_id)

    saved = cfg.get("saved_cities", [])
    assert "Караганда" not in saved, "City should not be auto-pinned on view"
    assert win.pin_btn.has_css_class("active") is False

    # 4. Explicitly toggle pin button pins Караганда
    win._on_pin_toggle(win.pin_btn)
    saved = cfg.get("saved_cities", [])
    assert "Караганда" in saved
    assert win.pin_btn.has_css_class("active") is True

    # 5. Clicking pin button again unpins Караганда
    win._on_pin_toggle(win.pin_btn)
    saved = cfg.get("saved_cities", [])
    assert "Караганда" not in saved
    assert win.pin_btn.has_css_class("active") is False

    # 6. Unpinning directly from strip
    win._unpin_city("Санкт-Петербург")
    saved = cfg.get("saved_cities", [])
    assert "Санкт-Петербург" not in saved
    assert saved == ["Москва"]


def test_empty_state_display_and_transition(tmp_path):
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from ui import EchoWeatherWindow

    cfg = ConfigManager(config_dir=tmp_path)
    cfg.set("saved_cities", [])

    app = Gtk.Application(application_id="com.echo.weather.test.empty")
    win = EchoWeatherWindow(app=app, initial_city=None, config_manager=cfg)

    # 1. When saved_cities is empty and no initial city, empty view is shown
    assert win.stack.get_visible_child_name() == "empty"
    assert win.empty_container is not None
    assert win.cities_scroll.get_visible() is False
    assert win.pin_btn.get_sensitive() is False

    # 2. Searching a city triggers loading and shows weather without auto-pinning
    weather_data = {
        "city_name": "Сочи",
        "temp": 24,
        "weather_code": 0,
        "condition_text": "Ясно",
        "bg_class": "weather-bg-clear-day",
        "days_detailed": [],
    }
    win.current_city = "Сочи"
    win._on_weather_fetched(weather_data, "Сочи", win._current_request_id)

    assert win.stack.get_visible_child_name() == "weather"
    assert win.current_city == "Сочи"
    assert win.pin_btn.get_sensitive() is True
    assert win.pin_btn.has_css_class("active") is False
    # Cities strip remains hidden until at least one city is pinned
    assert win.cities_scroll.get_visible() is False

    # 3. Pinning Сочи makes cities strip visible
    win._on_pin_toggle(win.pin_btn)
    assert win.pin_btn.has_css_class("active") is True
    assert win.cities_scroll.get_visible() is True
    saved = cfg.get("saved_cities", [])
    assert saved == ["Сочи"]

    # 4. Explicitly returning to empty state
    win._show_empty_state()
    assert win.stack.get_visible_child_name() == "empty"
    assert win.has_css_class("weather-canvas-empty") is True
    assert win.has_css_class("weather-canvas-clear-day") is True

    # 5. Verify animated weather icons stack (no circle badge, cycling 5 conditions)
    assert hasattr(win, "weather_icon_stack") and win.weather_icon_stack is not None
    assert win.weather_icon_stack.get_visible_child_name() == "clear"
    win._cycle_empty_weather_icon()
    assert win.weather_icon_stack.get_visible_child_name() == "clouds"

    # 6. Verify 13 languages popover and language switching
    assert hasattr(win, "lang_popover") and win.lang_popover is not None
    assert len(win._lang_popover_buttons) == 13
    assert "ru" in win._lang_popover_buttons
    assert "en" in win._lang_popover_buttons
    assert "ja" in win._lang_popover_buttons
    assert "ar" in win._lang_popover_buttons

    # Switch to English
    win._on_language_selected("en")
    assert win.empty_action_label.get_label() == "Select your main city"
    assert "Tokyo" in [w[0].get_label() for w in win._empty_chip_widgets]

    # Switch back to Russian
    win._on_language_selected("ru")
    assert win.empty_action_label.get_label() == "Выбрать ваш основной город"
    chip_labels = [w[0].get_label() for w in win._empty_chip_widgets]
    assert "Токио" in chip_labels
    assert "Лондон" in chip_labels
    assert "Нью-Йорк" in chip_labels
    assert "Париж" in chip_labels
    assert "Дубай" in chip_labels
    assert "Москва" in chip_labels


def test_echo_weather_title_click_and_main_city_mechanics(tmp_path):
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    Gtk.init()

    from config_manager import ConfigManager
    from ui import EchoWeatherWindow

    cfg = ConfigManager(config_dir=tmp_path)
    cfg.set("saved_cities", ["Tokyo", "London"])
    cfg.set("main_city", "")

    app = Gtk.Application(application_id="com.echo.weather.test.maincity")
    win = EchoWeatherWindow(app=app, initial_city="Tokyo", config_manager=cfg)

    # 1. Test clicking Echo Weather title button returns to empty state
    assert win.home_nav_btn is not None
    win._show_empty_state()
    assert win.stack.get_visible_child_name() == "empty"
    assert win.current_city == ""

    # 2. Test search autocomplete popover and suggestions
    assert win.search_popover is not None
    assert win.search_popover.get_focusable() is False
    win.search_entry.set_text("par")
    win._on_search_entry_changed(win.search_entry)
    # Check that search results box has children
    first_suggestion = win.search_results_box.get_first_child()
    assert first_suggestion is not None
    assert first_suggestion.get_focusable() is False
    assert first_suggestion.get_focus_on_click() is False
    win.search_popover.popdown()

    # 3. Test setting main city via home_btn
    weather_data = {
        "city_name": "Tokyo",
        "temp": 18,
        "weather_code": 0,
        "condition_text": "Sunny",
        "bg_class": "weather-bg-clear-day",
        "days_detailed": [],
    }
    win.current_city = "Tokyo"
    win._on_weather_fetched(weather_data, "Tokyo", win._current_request_id)
    assert win.stack.get_visible_child_name() == "weather"
    assert win.home_btn.get_sensitive() is True
    assert win.home_btn.has_css_class("active") is False

    # Click home button to make Tokyo the main city
    win._on_home_toggle(win.home_btn)
    assert cfg.get("main_city") == "Tokyo"
    assert win.home_btn.has_css_class("active") is True
    assert win.current_weather_data.get("is_main_city") is True

    # 4. Verify main city shows on startup
    win_restarted = EchoWeatherWindow(app=app, initial_city=None, config_manager=cfg)
    assert win_restarted.current_city == "Tokyo"

    # 5. Toggle off main city
    win._on_home_toggle(win.home_btn)
    assert cfg.get("main_city") == ""
    assert win.home_btn.has_css_class("active") is False

    # 6. Verify unpinned main city leads to empty state on next startup
    win_unpinned = EchoWeatherWindow(app=app, initial_city=None, config_manager=cfg)
    assert win_unpinned.current_city == ""
    assert win_unpinned.stack.get_visible_child_name() == "empty"

    # 7. Verify zero-arg toggle calls (from hero card pills)
    win._on_home_toggle()
    assert cfg.get("main_city") == "Tokyo"
    win._on_home_toggle()
    assert cfg.get("main_city") == ""

    # Tokyo was initially in saved_cities; toggle unpins it, next toggle pins it back
    win._on_pin_toggle()
    assert "Tokyo" not in cfg.get("saved_cities")
    win._on_pin_toggle()
    assert "Tokyo" in cfg.get("saved_cities")

    # 8. Verify search popover autohide is disabled to eliminate Wayland grab
    assert win.search_popover.get_autohide() is False


