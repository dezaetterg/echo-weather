"""
Тесты для провайдера погоды WeatherProvider и метеорологических утилит.
"""

import datetime
import json
import urllib.request

from providers.weather import (
    WeatherProvider,
    apply_seasonal_norm,
    get_geo_timezone_offset_seconds,
    met_symbol_to_wmo,
)


def test_apply_seasonal_norm_autumn_novokuznetsk():
    base_data = {
        "temp": 26,
        "temp_min": 18,
        "temp_max": 27,
        "time_of_day": "day",
        "is_day": 1,
        "daily": [
            {"date": "2026-10-01", "min": 18, "max": 27},
            {"date": "2026-10-02", "min": 17, "max": 26},
        ],
        "hourly": [
            {"time": "12:00", "temp": 26, "is_day": 1},
            {"time": "03:00", "temp": 18, "is_day": 0},
        ],
        "days_detailed": [],
    }

    adjusted = apply_seasonal_norm(base_data, 53.75, 87.1, lang="ru")

    assert adjusted is not None
    assert adjusted["temp"] < 20
    assert adjusted["temp"] > -5
    assert adjusted["temp_max"] < 20
    assert adjusted["daily"][0]["max"] < 20
    assert adjusted["hourly"][0]["temp"] < 20


def test_apply_seasonal_norm_winter_siberia():
    base_data = {
        "temp": 25,
        "temp_min": 15,
        "temp_max": 25,
        "time_of_day": "night",
        "is_day": 0,
        "daily": [{"date": "2026-01-15", "min": 15, "max": 25}],
        "hourly": [{"time": "02:00", "temp": 25, "is_day": 0}],
        "days_detailed": [],
    }

    adjusted = apply_seasonal_norm(base_data, 53.75, 87.1, lang="ru")
    assert adjusted is not None
    assert "temp" in adjusted


def test_met_symbol_to_wmo_mapping():
    wmo_code, is_day = met_symbol_to_wmo("clearsky_day")
    assert wmo_code == 0
    assert is_day == 1

    wmo_code_night, is_day_night = met_symbol_to_wmo("clearsky_night")
    assert wmo_code_night == 0
    assert is_day_night == 0

    wmo_fair, _ = met_symbol_to_wmo("fair_day")
    assert wmo_fair == 1

    wmo_cloudy, _ = met_symbol_to_wmo("cloudy")
    assert wmo_cloudy == 3

    wmo_rain, _ = met_symbol_to_wmo("rain")
    assert wmo_rain == 63

    wmo_heavyrain, _ = met_symbol_to_wmo("heavyrain")
    assert wmo_heavyrain == 65

    wmo_snow, _ = met_symbol_to_wmo("snow")
    assert wmo_snow == 73

    wmo_unknown, _ = met_symbol_to_wmo("unknown_symbol")
    assert wmo_unknown == 0


def test_timezone_offset_calculation():
    offset_seconds = get_geo_timezone_offset_seconds(53.75, 87.1)
    offset_hours = offset_seconds / 3600.0
    assert 5.0 <= offset_hours <= 8.0


def test_weather_provider_search_live_or_fallback():
    provider = WeatherProvider()
    results = provider.search("Новокузнецк")

    assert len(results) == 1
    search_res = results[0]
    data = search_res.preview_data

    assert data is not None
    assert data["city_name"] == "Новокузнецк"
    assert "temp" in data
    assert "daily" in data
    assert len(data["daily"]) >= 7

    now = datetime.datetime.now()
    if now.month in (10, 11, 12, 1, 2, 3):
        assert data["temp"] < 22


def test_blend_forecast_consensus():
    provider = WeatherProvider()
    om_mock = {
        "city_name": "Тест",
        "temp": 10,
        "feels_like": 8,
        "humidity": 80,
        "dew_point": 6,
        "pressure_mm": 750,
        "wind_speed": 4.0,
        "wind_gusts": 7.0,
        "temp_min": 5,
        "temp_max": 15,
        "precip_nowcast": "Осадки начнутся через 15 мин",
        "days_detailed": [
            {
                "date_str": "2026-10-02",
                "hourly_temps": [10] * 24,
                "hourly_apparent": [8] * 24,
                "hourly_winds": [4.0] * 24,
                "hourly_hums": [80] * 24,
                "hourly_press_mm": [750] * 24,
            }
        ],
        "daily": [{"date": "2026-10-02", "min": 5, "max": 15}],
        "hourly": [{"time": "12:00", "temp": 10}],
    }
    met_mock = {
        "city_name": "Тест",
        "temp": 12,
        "feels_like": 11,
        "humidity": 70,
        "dew_point": 8,
        "pressure_mm": 760,
        "wind_speed": 6.0,
        "wind_gusts": 9.0,
        "temp_min": 7,
        "temp_max": 17,
        "days_detailed": [
            {
                "date_str": "2026-10-02",
                "hourly_temps": [14] * 24,
                "hourly_apparent": [12] * 24,
                "hourly_winds": [6.0] * 24,
                "hourly_hums": [70] * 24,
                "hourly_press_mm": [760] * 24,
            }
        ],
        "daily": [{"date": "2026-10-02", "min": 7, "max": 17}],
        "hourly": [{"time": "12:00", "temp": 14}],
    }

    blended = provider._blend_forecast_consensus(om_mock, met_mock)

    assert blended is not None
    # 0.55 * 10 + 0.45 * 12 = 5.5 + 5.4 = 10.9 -> 11
    assert blended["temp"] == 11
    # 0.55 * 8 + 0.45 * 11 = 4.4 + 4.95 = 9.35 -> 9
    assert blended["feels_like"] == 9
    assert blended["humidity"] == 75
    assert blended["pressure_mm"] == 755
    assert blended["wind_speed"] == 5.0
    assert blended["wind_gusts"] == 8.0
    assert blended["temp_min"] == 6
    assert blended["temp_max"] == 16
    assert blended["is_consensus"] is True
    assert blended["sources_count"] == 2
    assert "Consensus" in blended["weather_model"]
    assert blended["precip_nowcast"] == "Осадки начнутся через 15 мин"

    # Проверка почасового ансамблирования
    # 0.55 * 10 + 0.45 * 14 = 5.5 + 6.3 = 11.8 -> 12
    assert blended["days_detailed"][0]["hourly_temps"][0] == 12
    assert blended["hourly"][0]["temp"] == 12
    assert blended["daily"][0]["min"] == 6
    assert blended["daily"][0]["max"] == 16


def test_fetch_forecast_sync_source_dispatch(monkeypatch):
    from config_manager import ConfigManager
    cfg = ConfigManager()
    provider = WeatherProvider(config_manager=cfg)

    calls = []

    def mock_open_meteo(lat, lon, city_info, timeout=3.0, model=None):
        calls.append(("open_meteo", model))
        return {"temp": 10, "city_name": "Test"}

    def mock_met_norway(lat, lon, city_info, timeout=3.5):
        calls.append(("met_norway", None))
        return {"temp": 12, "city_name": "Test"}

    monkeypatch.setattr(provider, "_fetch_open_meteo", mock_open_meteo)
    monkeypatch.setattr(provider, "_fetch_met_norway", mock_met_norway)

    # 1. Consensus: опрашивает оба источника
    cfg.set("forecast_source", "consensus")
    calls.clear()
    res_cons = provider._fetch_forecast_sync(55.75, 37.61, {"name_ru": "Москва"})
    assert res_cons is not None
    assert any(c[0] == "open_meteo" for c in calls)
    assert any(c[0] == "met_norway" for c in calls)

    # 2. ECMWF: опрашивает open_meteo с моделью ecmwf_ifs025
    cfg.set("forecast_source", "ecmwf")
    calls.clear()
    res_ecmwf = provider._fetch_forecast_sync(55.75, 37.61, {"name_ru": "Москва"})
    assert res_ecmwf is not None
    assert ("open_meteo", "ecmwf_ifs025") in calls

    # 3. ICON: опрашивает open_meteo с моделью icon_seamless
    cfg.set("forecast_source", "icon")
    calls.clear()
    res_icon = provider._fetch_forecast_sync(55.75, 37.61, {"name_ru": "Москва"})
    assert res_icon is not None
    assert ("open_meteo", "icon_seamless") in calls

    # 4. MET Norway: опрашивает met_norway первым приоритетом
    cfg.set("forecast_source", "met_norway")
    calls.clear()
    res_met = provider._fetch_forecast_sync(55.75, 37.61, {"name_ru": "Москва"})
    assert res_met is not None
    assert calls[0][0] == "met_norway"


def test_weather_provider_karaganda_resolution():
    provider = WeatherProvider()

    # 1. Exact match
    info_exact = provider._resolve_city_info("караганда")
    assert info_exact is not None
    assert info_exact["name_ru"] == "Караганда"
    assert info_exact["country_ru"] == "Казахстан"
    assert round(info_exact["lat"], 2) == 49.80
    assert round(info_exact["lon"], 2) == 73.10

    # 2. Case insensitive
    info_cap = provider._resolve_city_info("Караганда")
    assert info_cap is not None
    assert info_cap["name_ru"] == "Караганда"

    # 3. Prepositional form
    info_prep = provider._resolve_city_info("в Караганде")
    assert info_prep is not None
    assert info_prep["name_ru"] == "Караганда"

    # 4. Colloquial keyword
    info_kw = provider._resolve_city_info("крг")
    assert info_kw is not None
    assert info_kw["name_ru"] == "Караганда"


def test_weather_provider_extended_cities_registry():
    provider = WeatherProvider()
    test_cities = [
        ("шымкент", "Казахстан"),
        ("актобе", "Казахстан"),
        ("брест", "Беларусь"),
        ("гомель", "Беларусь"),
        ("бишкек", "Кыргызстан"),
        ("прокопьевск", "Россия"),
        ("анкара", "Турция"),
        ("рейкьявик", "Исландия"),
    ]
    for city_query, expected_country in test_cities:
        info = provider._resolve_city_info(city_query)
        assert info is not None, f"City '{city_query}' failed to resolve"
        assert info["country_ru"] == expected_country


def test_weather_provider_synchronous_geocoding(monkeypatch, tmp_path):
    from providers.cache import WeatherCacheManager

    provider = WeatherProvider()
    provider.cache_dir = tmp_path
    provider.cache_manager = WeatherCacheManager(tmp_path)

    fake_response_data = {
        "results": [
            {
                "id": 999999,
                "name": "ТестовыйГород",
                "latitude": 51.5,
                "longitude": 39.2,
                "elevation": 150.0,
                "country": "ТестоваяСтрана",
                "timezone": "Europe/Moscow",
            }
        ]
    }

    class FakeHttpResponse:
        def __init__(self, data):
            self._data = json.dumps(data).encode("utf-8")

        def read(self):
            return self._data

        def decode(self, *args, **kwargs):
            return self._data.decode(*args, **kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def fake_urlopen(req, timeout=None):
        return FakeHttpResponse(fake_response_data)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    # Resolve previously unseen city with network allowed
    info = provider._resolve_city_info("ТестовыйГород", allow_network=True)
    assert info is not None
    assert info["name_ru"] == "ТестовыйГород"
    assert info["lat"] == 51.5
    assert info["lon"] == 39.2

    # Verify it is saved in cache
    cached = provider.cache_manager.find_geocache_candidate("тестовыйгород")
    assert cached is not None
    assert cached["name_ru"] == "ТестовыйГород"

    # Search method should succeed with geocoding
    monkeypatch.setattr(provider, "_fetch_forecast_sync", lambda lat, lon, city_info: {"temp": 15, "city_name": "ТестовыйГород", "daily": [{}], "days_detailed": [{}]})
    results = provider.search("ТестовыйГород", category_filter="Weather")
    assert len(results) == 1
    assert results[0].title.startswith("ТестовыйГород")

