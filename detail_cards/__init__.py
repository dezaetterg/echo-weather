"""
Пакет карточек детального анализа погоды.
"""

from __future__ import annotations

from detail_cards.base import BaseWeatherHourlyArea
from detail_cards.climate_card import (
    ClimateMonthlyPrecipTable,
    ClimateMonthlyTempTable,
    ClimatePrecipChartArea,
    ClimateTempChartArea,
    PrecipCapsuleBarArea,
    TempCapsuleBarArea,
    build_averages_view,
)
from detail_cards.comparison_bar import ComparisonBarArea, DayComparisonBarArea
from detail_cards.conditions_card import (
    PrecipitationBarArea,
    WeatherSplineArea,
    build_conditions_view,
)
from detail_cards.humidity_card import HumidityHourlyArea, build_humidity_view
from detail_cards.moon_card import (
    MiniMoonIcon,
    MoonCalendarCard,
    MoonTimelineRuler,
    build_moon_view,
    create_moon_metric_row,
)
from detail_cards.precipitation_card import (
    PrecipitationHourlyArea,
    build_precipitation_view,
)
from detail_cards.pressure_card import (
    PressureGaugeArea,
    PressureHourlyArea,
    build_pressure_view,
)
from detail_cards.sun_card import (
    ClimateSunYearTable,
    SunArcChartArea,
    SunDaylightBar,
    build_sun_view,
    create_sun_metric_row,
)
from detail_cards.uv_card import UVHourlyArea, build_uv_view
from detail_cards.visibility_card import VisibilityHourlyArea, build_visibility_view
from detail_cards.wind_card import (
    WindCompassArea,
    WindHourlyArea,
    build_wind_view,
)

__all__ = [
    "BaseWeatherHourlyArea",
    "DayComparisonBarArea",
    "ComparisonBarArea",
    "WeatherSplineArea",
    "PrecipitationBarArea",
    "build_conditions_view",
    "UVHourlyArea",
    "build_uv_view",
    "WindCompassArea",
    "WindHourlyArea",
    "build_wind_view",
    "PrecipitationHourlyArea",
    "build_precipitation_view",
    "HumidityHourlyArea",
    "build_humidity_view",
    "VisibilityHourlyArea",
    "build_visibility_view",
    "PressureGaugeArea",
    "PressureHourlyArea",
    "build_pressure_view",
    "SunDaylightBar",
    "ClimateSunYearTable",
    "SunArcChartArea",
    "create_sun_metric_row",
    "build_sun_view",
    "MoonTimelineRuler",
    "MiniMoonIcon",
    "MoonCalendarCard",
    "create_moon_metric_row",
    "build_moon_view",
    "TempCapsuleBarArea",
    "PrecipCapsuleBarArea",
    "ClimateMonthlyTempTable",
    "ClimateMonthlyPrecipTable",
    "ClimateTempChartArea",
    "ClimatePrecipChartArea",
    "build_averages_view",
]
