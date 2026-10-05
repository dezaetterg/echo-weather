"""
Тесты для модуля небесной механики и астрономии services.astronomy.
Проверка точности расчетов NOAA, фаз Луны, восходов, заходов и УФ-индекса.
"""

from datetime import date, datetime, timezone

from services.astronomy import (
    calculate_annual_solar_table,
    calculate_detailed_moon,
    calculate_lunar_distance_km,
    calculate_month_moon_calendar,
    calculate_moon_phase,
    calculate_moonrise_moonset,
    calculate_solar_details,
    compute_solar_uv,
)


def test_calculate_moon_phase_bounds():
    dt = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    phase = calculate_moon_phase(dt)

    assert 0.0 <= phase["cycle_fraction"] <= 1.0
    assert 0.0 <= phase["illumination"] <= 100.0
    assert 0.0 <= phase["age_days"] <= 30.0
    assert phase["phase_name"] != ""
    assert phase["phase_name_en"] != ""


def test_calculate_solar_details_novokuznetsk():
    lat = 53.75
    lon = 87.1
    dt = date(2026, 10, 1)
    solar = calculate_solar_details(lat, lon, dt=dt, utc_offset_hours=7.0, is_ru=True)

    assert "sunrise" in solar
    assert "sunset" in solar
    assert "first_light" in solar
    assert "last_light" in solar
    assert len(solar["curve_points"]) == 97
    assert 0.0 < solar["daylight_min"] < 1440.0
    assert "ч" in solar["daylight_str"]


def test_calculate_annual_solar_table():
    lat = 53.75
    lon = 87.1
    table = calculate_annual_solar_table(lat, lon, utc_offset_hours=7.0, is_ru=True)

    assert len(table["months"]) == 12
    assert "Самый длинный световой день" in table["longest_day_str"]
    june_row = table["months"][5]
    assert june_row["month"] == 6
    assert june_row["daylight_min"] > 900.0


def test_calculate_lunar_distance_physical_bounds():
    # Лунная орбита варьируется от перигея (~356 000 км) до апогея (~407 000 км)
    dt = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    dist = calculate_lunar_distance_km(dt)

    assert 350000 <= dist <= 410000


def test_calculate_moonrise_moonset():
    lat = 55.75
    lon = 37.62
    dt_day = date(2026, 10, 1)
    rise_str, set_str = calculate_moonrise_moonset(lat, lon, dt_day, utc_offset_hours=3.0)

    assert isinstance(rise_str, str)
    assert isinstance(set_str, str)
    assert len(rise_str) == 5
    assert len(set_str) == 5


def test_calculate_detailed_moon_completeness():
    lat = 53.75
    lon = 87.1
    target_dt = datetime(2026, 10, 1, 15, 30)
    detailed = calculate_detailed_moon(lat, lon, target_dt, utc_offset_hours=7.0, is_ru=True)

    assert "cycle_fraction" in detailed
    assert "illumination" in detailed
    assert "phase_name_ru" in detailed
    assert "phase_name_en" in detailed
    assert "distance_km" in detailed
    assert "км" in detailed["distance_str"]
    assert "tilt_deg" in detailed
    assert "next_full_moon_date_str" in detailed


def test_calculate_month_moon_calendar():
    cal = calculate_month_moon_calendar(2026, 10, is_ru=True)

    assert cal["year"] == 2026
    assert cal["month"] == 10
    assert cal["num_days"] == 31
    assert len(cal["days"]) == 31
    assert "октябрь" in cal["title"].lower()


def test_compute_solar_uv_physics():
    lat = 53.75

    # Ночь: солнце глубоко под горизонтом, УФ = 0
    night_dt = datetime(2026, 7, 1, 0, 0)
    uv_night = compute_solar_uv(lat, night_dt, cloud_pct=0.0)
    assert uv_night == 0.0

    # Полдень летом в ясную погоду: УФ индекс положительный
    noon_dt = datetime(2026, 7, 1, 13, 0)
    uv_clear = compute_solar_uv(lat, noon_dt, cloud_pct=0.0)
    assert uv_clear > 3.0

    # Облачность 100% снижает УФ индекс
    uv_overcast = compute_solar_uv(lat, noon_dt, cloud_pct=100.0)
    assert uv_overcast < uv_clear
