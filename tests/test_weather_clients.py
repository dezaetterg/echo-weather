"""
Тесты для сетевых метеорологических клиентов (providers/clients).
"""

from __future__ import annotations

import pytest

from providers.clients.base import BaseWeatherClient
from providers.clients.met_norway import MetNorwayClient
from providers.clients.open_meteo import OpenMeteoClient
from providers.clients.wttr import WttrClient


def test_clients_inheritance_and_interface():
    clients = [OpenMeteoClient(), MetNorwayClient(), WttrClient()]
    for client in clients:
        assert isinstance(client, BaseWeatherClient)
        assert hasattr(client, "fetch_forecast")
        assert callable(client.fetch_forecast)


def test_client_handles_unreachable_endpoint():
    client = OpenMeteoClient()
    # Запрос с нулевым таймаутом или невалидными координатами не должен вызывать исключение
    res = client.fetch_forecast(
        lat=999.0,
        lon=999.0,
        city_info={"name_ru": "Тест", "name_en": "Test"},
        timeout=0.001
    )
    assert res is None


def test_open_meteo_url_parameters():
    client = OpenMeteoClient()

    # 1. По умолчанию: models=best_match, cell_selection=land, minutely_15
    url_default = client.build_forecast_url(
        lat=53.75,
        lon=87.1,
        city_info={"timezone": "Asia/Novokuznetsk"}
    )
    assert "models=best_match" in url_default
    assert "cell_selection=land" in url_default
    assert "minutely_15=precipitation,weather_code" in url_default
    assert "timezone=Asia/Novokuznetsk" in url_default or "timezone=Asia%2FNovokuznetsk" in url_default
    assert "elevation=" not in url_default

    # 2. С явной моделью ecmwf_ifs025 и высотой над уровнем моря
    url_ecmwf = client.build_forecast_url(
        lat=53.75,
        lon=87.1,
        city_info={"elevation": 238.0, "weather_model": "ecmwf_ifs025"}
    )
    assert "models=ecmwf_ifs025" in url_ecmwf
    assert "elevation=238.0" in url_ecmwf
    assert "cell_selection=land" in url_ecmwf

    # 3. Вызов без параметров city_info и с kwargs
    url_simple = client.build_forecast_url(lat=40.71, lon=-74.00, timezone="America/New_York", model="icon_seamless")
    assert "models=icon_seamless" in url_simple
    assert "cell_selection=land" in url_simple
    assert "timezone=America/New_York" in url_simple or "timezone=America%2FNew_York" in url_simple


def test_open_meteo_parse_forecast_with_nowcast():
    client = OpenMeteoClient()
    raw_mock = {
        "latitude": 53.75,
        "longitude": 87.1,
        "utc_offset_seconds": 25200,
        "timezone": "Asia/Novokuznetsk",
        "current": {
            "temperature_2m": 12.3,
            "apparent_temperature": 11.0,
            "relative_humidity_2m": 70,
            "surface_pressure": 1010.0,
            "wind_speed_10m": 4.5,
            "wind_direction_10m": 180,
            "precipitation": 0.0,
            "is_day": 1,
            "weather_code": 3,
            "uv_index": 2.0,
            "visibility": 10000.0,
        },
        "daily": {
            "time": ["2026-10-02"],
            "temperature_2m_max": [15.0],
            "temperature_2m_min": [5.0],
            "precipitation_sum": [1.2],
            "weather_code": [3],
            "sunrise": ["2026-10-02T06:30"],
            "sunset": ["2026-10-02T18:30"],
            "uv_index_max": [3.0],
        },
        "hourly": {
            "time": ["2026-10-02T12:00", "2026-10-02T13:00", "2026-10-02T14:00"],
            "temperature_2m": [12.0, 13.0, 14.0],
            "weather_code": [3, 3, 3],
            "apparent_temperature": [11.0, 12.0, 13.0],
            "precipitation": [0.0, 0.0, 0.0],
            "precipitation_probability": [20, 20, 30],
        },
        "minutely_15": {
            "time": ["2026-10-02T12:00", "2026-10-02T12:15", "2026-10-02T12:30", "2026-10-02T12:45"],
            "precipitation": [0.0, 0.0, 0.4, 1.2],
            "weather_code": [3, 3, 61, 61],
        }
    }

    city_info = {"name_ru": "Новокузнецк", "elevation": 238.0, "weather_model": "best_match"}
    parsed = client.parse_forecast_response(raw_mock, lat=53.75, lon=87.1, city_info=city_info, model_name="best_match")

    assert parsed is not None
    assert parsed["temp"] == 12
    assert parsed["weather_model"] == "best_match"
    assert parsed["cell_selection"] == "land"
    assert parsed["elevation"] == 238.0
    assert "minutely_15" in parsed
    assert "precip_nowcast" in parsed
    # Проверяем, что nowcast распознал приближение осадков через 30 минут
    assert "мин" in parsed["precip_nowcast"] or "min" in parsed["precip_nowcast"]
    assert parsed["precip_desc"] == parsed["precip_nowcast"]


def test_open_meteo_parse_rain_stopping():
    client = OpenMeteoClient()
    raw_mock = {
        "latitude": 53.75,
        "longitude": 87.1,
        "utc_offset_seconds": 0,
        "timezone": "UTC",
        "current": {
            "temperature_2m": 8.0,
            "apparent_temperature": 6.0,
            "relative_humidity_2m": 92,
            "surface_pressure": 1005.0,
            "wind_speed_10m": 5.0,
            "wind_direction_10m": 220,
            "precipitation": 1.8,
            "is_day": 1,
            "weather_code": 61,
            "uv_index": 1.0,
            "visibility": 6000.0,
        },
        "daily": {
            "time": ["2026-10-02"],
            "temperature_2m_max": [10.0],
            "temperature_2m_min": [4.0],
            "precipitation_sum": [5.0],
            "weather_code": [61],
            "sunrise": ["2026-10-02T06:00"],
            "sunset": ["2026-10-02T18:00"],
            "uv_index_max": [1.5],
        },
        "hourly": {
            "time": ["2026-10-02T12:00"],
            "temperature_2m": [8.0],
            "weather_code": [61],
        },
        "minutely_15": {
            "time": ["2026-10-02T00:00", "2026-10-02T00:15", "2026-10-02T00:30", "2026-10-02T00:45"],
            "precipitation": [1.8, 1.2, 0.4, 0.0],
            "weather_code": [61, 61, 61, 3],
        }
    }

    parsed = client.parse_forecast_response(raw_mock, lat=53.75, lon=87.1, city_info={"name_ru": "Тест"})
    assert "закончится" in parsed["precip_nowcast"] or "stopping" in parsed["precip_nowcast"]
    assert "45" in parsed["precip_nowcast"]


def test_met_norway_preserves_real_temperature_without_climatology():
    from providers.clients.met_norway import MetNorwayClient

    client = MetNorwayClient()
    mock_data = {
        "properties": {
            "timeseries": [
                {
                    "time": "2026-10-02T10:00:00Z",
                    "data": {
                        "instant": {
                            "details": {
                                "air_temperature": 17.6,
                                "air_pressure_at_sea_level": 1017.0,
                                "relative_humidity": 45.0,
                                "wind_speed": 3.0,
                                "wind_from_direction": 140.0,
                                "cloud_area_fraction": 10.0,
                            }
                        },
                        "next_1_hours": {
                            "summary": {"symbol_code": "clearsky_day"},
                            "details": {"precipitation_amount": 0.0, "probability_of_precipitation": 0.0},
                        },
                        "next_6_hours": {
                            "summary": {"symbol_code": "clearsky_day"},
                        },
                    },
                }
            ]
        }
    }

    parsed = client.parse_forecast_data(
        mock_data,
        lat=53.7557,
        lon=87.1099,
        city_info={"name_ru": "Новокузнецк", "name_en": "Novokuznetsk"},
        lang="ru",
    )

    assert parsed is not None
    # Проверяем, что реальная температура 17.6 округлена до 18 и не заменена климатической нормой 6
    assert parsed["temp"] == 18
    assert parsed["temp"] != 6
    assert "solar_details" in parsed
    assert "annual_table" in parsed["solar_details"]
    assert "months" in parsed["solar_details"]["annual_table"]


def test_met_norway_visibility_and_annual_solar_table():
    client = MetNorwayClient()
    mock_data = {
        "properties": {
            "timeseries": [
                {
                    "time": "2026-10-02T10:00:00Z",
                    "data": {
                        "instant": {
                            "details": {
                                "air_temperature": 15.0,
                                "dew_point_temperature": 14.5,
                                "air_pressure_at_sea_level": 1013.0,
                                "relative_humidity": 97.0,
                                "wind_speed": 2.0,
                                "wind_from_direction": 180.0,
                                "cloud_area_fraction": 90.0,
                            }
                        },
                        "next_1_hours": {
                            "summary": {"symbol_code": "fog"},
                            "details": {"precipitation_amount": 0.0, "probability_of_precipitation": 10.0},
                        },
                        "next_6_hours": {
                            "summary": {"symbol_code": "fog"},
                        },
                    },
                }
            ]
        }
    }

    parsed = client.parse_forecast_data(
        mock_data,
        lat=53.7557,
        lon=87.1099,
        city_info={"name_ru": "Новокузнецк", "name_en": "Novokuznetsk"},
        lang="ru",
    )

    assert parsed is not None
    assert "solar_details" in parsed
    assert "annual_table" in parsed["solar_details"]
    assert "months" in parsed["solar_details"]["annual_table"]
    assert "days_detailed" in parsed
    cur_day = parsed["days_detailed"][0]
    assert "hourly_vis_km" in cur_day
    # High humidity and fog should drop visibility well below 10 km
    assert cur_day["min_visibility_km"] < 5.0
    assert cur_day["hourly_vis_km"][10] < 5.0


