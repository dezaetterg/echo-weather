"""
Тесты для строгих моделей данных погоды Echo Weather.
Проверка сериализации, десериализации, гарантии ключей и интерфейса Mapping.
"""

from models.weather import (
    CurrentConditions,
    DailyForecast,
    DayDetailedForecast,
    DetailedMoon,
    HourlyForecast,
    SolarDetails,
    WeatherForecastData,
    YesterdayComparison,
)


def test_hourly_forecast_model():
    raw = {
        "time": "14:00",
        "hour_num": 14,
        "is_now": True,
        "temp": 12,
        "code": 1,
        "icon_name": "sun.svg",
        "icon_file": "/path/to/sun.svg",
        "is_day": 1,
        "precip_prob": 10,
        "precip_amount": 0.0,
    }
    hourly = HourlyForecast.from_dict(raw)
    assert hourly.time == "14:00"
    assert hourly.hour_num == 14
    assert hourly.is_now is True
    assert hourly.temp == 12

    dump = hourly.to_dict()
    assert dump["time"] == "14:00"
    assert dump["is_now"] is True


def test_daily_forecast_key_guarantee():
    # Проверка работы при наличии только t_min и t_max
    raw_with_t_keys = {
        "day": "Пт",
        "weekday_idx": 4,
        "t_min": 3,
        "t_max": 18,
        "code": 0,
        "icon_name": "sun.svg",
    }
    daily_from_t = DailyForecast.from_dict(raw_with_t_keys)
    assert daily_from_t.min == 3
    assert daily_from_t.max == 18
    assert daily_from_t.t_min == 3
    assert daily_from_t.t_max == 18

    # Проверка работы при наличии только min и max
    raw_with_min_max = {
        "day": "Сб",
        "weekday_idx": 5,
        "min": 8,
        "max": 19,
    }
    daily_from_min_max = DailyForecast.from_dict(raw_with_min_max)
    assert daily_from_min_max.min == 8
    assert daily_from_min_max.max == 19
    assert daily_from_min_max.t_min == 8
    assert daily_from_min_max.t_max == 19

    # to_dict гарантирует наличие обоих наборов ключей
    dump = daily_from_min_max.to_dict()
    assert dump["min"] == 8
    assert dump["max"] == 19
    assert dump["t_min"] == 8
    assert dump["t_max"] == 19


def test_day_detailed_forecast_aliases():
    raw = {
        "day_index": 1,
        "day_name": "Пятница",
        "weekday_short": "Пт",
        "t_min": 4,
        "t_max": 17,
        "apparent_min": 2,
        "apparent_max": 16,
    }
    item = DayDetailedForecast.from_dict(raw)
    assert item.min == 4
    assert item.max == 17
    assert item.t_min == 4
    assert item.t_max == 17
    assert item.day == "Пт"
    assert item.day_name == "Пт"

    dump = item.to_dict()
    assert dump["min"] == 4
    assert dump["t_min"] == 4
    assert dump["day"] == "Пт"
    assert dump["day_name"] == "Пт"


def test_weather_forecast_data_mapping_and_roundtrip():
    raw_data = {
        "city_name": "Новокузнецк",
        "country": "Россия",
        "lat": 53.75,
        "lon": 87.1,
        "temp": 11,
        "feels_like": 10,
        "humidity": 65,
        "wind_speed": 3.2,
        "pressure_mm": 752,
        "uv_index": 2.1,
        "hourly": [
            {"time": "12:00", "temp": 11, "code": 1},
            {"time": "13:00", "temp": 12, "code": 1},
        ],
        "daily": [
            {"day": "Сегодня", "min": 5, "max": 12, "code": 1},
            {"day": "Пт", "min": 3, "max": 18, "code": 0},
        ],
        "days_detailed": [
            {"day_index": 0, "weekday_short": "Сегодня", "min": 5, "max": 12},
        ],
        "solar_details": {
            "sunrise": "06:45",
            "sunset": "18:30",
            "daylight_min": 705.0,
        },
        "detailed_moon": {
            "cycle_fraction": 0.45,
            "illumination": 88,
            "phase_name": "Прибывающая луна",
        },
        "custom_legacy_extension_field": 12345,
    }

    model = WeatherForecastData.from_dict(raw_data)

    # Проверка прямого доступа к атрибутам
    assert model.city_name == "Новокузнецк"
    assert model.current.temp == 11
    assert model.current.humidity == 65
    assert len(model.hourly) == 2
    assert len(model.daily) == 2
    assert model.solar_details.sunrise == "06:45"
    assert model.detailed_moon.illumination == 88

    # Проверка работы интерфейса Mapping (совместимость со словарем)
    assert model["temp"] == 11
    assert model["feels_like"] == 10
    assert model["city_name"] == "Новокузнецк"
    assert model.get("humidity") == 65
    assert model.get("non_existent_key", "default_val") == "default_val"
    assert "temp" in model
    assert "city_name" in model
    assert model["custom_legacy_extension_field"] == 12345

    # Проверка сериализации обратно в словарь
    dumped = model.to_dict()
    assert dumped["city_name"] == "Новокузнецк"
    assert dumped["temp"] == 11
    assert dumped["custom_legacy_extension_field"] == 12345
    assert len(dumped["daily"]) == 2
    assert dumped["daily"][0]["min"] == 5
    assert dumped["daily"][0]["t_min"] == 5


def test_weather_forecast_data_stage1_precision_fields():
    raw_data = {
        "city_name": "Новокузнецк",
        "temp": 14,
        "weather_model": "ecmwf_ifs025",
        "cell_selection": "land",
        "elevation": 238.0,
        "precip_nowcast": "Осадки начнутся примерно через 30 мин.",
        "minutely_15": {
            "time": ["2026-10-02T14:00", "2026-10-02T14:15"],
            "precipitation": [0.0, 0.4],
        }
    }
    model = WeatherForecastData.from_dict(raw_data)
    assert model.weather_model == "ecmwf_ifs025"
    assert model.cell_selection == "land"
    assert model.elevation == 238.0
    assert model.precip_nowcast == "Осадки начнутся примерно через 30 мин."
    assert "2026-10-02T14:00" in model.minutely_15["time"]

    # Проверка доступа как к словарю
    assert model["weather_model"] == "ecmwf_ifs025"
    assert model["cell_selection"] == "land"
    assert model["elevation"] == 238.0
    assert model["precip_nowcast"] == "Осадки начнутся примерно через 30 мин."

    # Проверка to_dict
    dumped = model.to_dict()
    assert dumped["weather_model"] == "ecmwf_ifs025"
    assert dumped["cell_selection"] == "land"
    assert dumped["elevation"] == 238.0
    assert dumped["precip_nowcast"] == "Осадки начнутся примерно через 30 мин."

