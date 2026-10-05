"""
Пакет сервисов приложения Echo Weather.
"""

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

__all__ = [
    "calculate_moon_phase",
    "calculate_solar_details",
    "calculate_annual_solar_table",
    "calculate_lunar_distance_km",
    "calculate_moonrise_moonset",
    "calculate_detailed_moon",
    "calculate_month_moon_calendar",
    "compute_solar_uv",
]
