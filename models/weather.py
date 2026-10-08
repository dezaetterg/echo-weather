"""
Модели данных прогноза погоды Echo Weather.
Строгая типизация для метеорологических структур с поддержкой обратной совместимости через Mapping.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HourlyForecast:
    """Почасовой срез погоды."""
    time: str = ""
    hour_num: int = 0
    is_now: bool = False
    temp: int | float = 0
    code: int = 0
    icon_name: str = ""
    icon_file: str = ""
    is_day: int = 1
    precip_prob: int | float = 0
    precip_amount: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HourlyForecast:
        return cls(
            time=str(data.get("time", "")),
            hour_num=int(data.get("hour_num", 0)),
            is_now=bool(data.get("is_now", False)),
            temp=data.get("temp", 0),
            code=int(data.get("code", 0)),
            icon_name=str(data.get("icon_name", "")),
            icon_file=str(data.get("icon_file", "")),
            is_day=int(data.get("is_day", 1)),
            precip_prob=data.get("precip_prob", 0),
            precip_amount=float(data.get("precip_amount", 0.0)),
        )


@dataclass
class DailyForecast:
    """Краткий суточный прогноз для 10-дневной шкалы."""
    day: str = ""
    weekday_idx: int = 0
    min: int | float = 0
    max: int | float = 0
    code: int = 0
    icon_name: str = ""
    icon_file: str = ""
    precip_sum: float = 0.0
    precip_prob_max: int | float = 0

    @property
    def t_min(self) -> int | float:
        return self.min

    @property
    def t_max(self) -> int | float:
        return self.max

    def to_dict(self) -> dict[str, Any]:
        res = dict(self.__dict__)
        res["t_min"] = self.min
        res["t_max"] = self.max
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DailyForecast:
        min_val = data.get("min", data.get("t_min", 0))
        max_val = data.get("max", data.get("t_max", 0))
        return cls(
            day=str(data.get("day", "")),
            weekday_idx=int(data.get("weekday_idx", 0)),
            min=min_val,
            max=max_val,
            code=int(data.get("code", 0)),
            icon_name=str(data.get("icon_name", "")),
            icon_file=str(data.get("icon_file", "")),
            precip_sum=float(data.get("precip_sum", 0.0)),
            precip_prob_max=data.get("precip_prob_max", 0),
        )


@dataclass
class DayDetailedForecast:
    """Подробный суточный прогноз с 24-часовыми массивами параметров."""
    day_index: int = 0
    date_str: str = ""
    day_num: int = 0
    weekday_letter: str = ""
    weekday_short: str = ""
    full_date: str = ""
    min: int | float = 0
    max: int | float = 0
    apparent_min: int | float = 0
    apparent_max: int | float = 0
    code: int = 0
    icon_name: str = ""
    icon_file: str = ""
    precip_sum: float = 0.0
    precip_prob_max: int | float = 0
    is_today: bool = False
    cur_hour: int = -1
    hourly_temps: list[int | float] = field(default_factory=list)
    hourly_apparent: list[int | float] = field(default_factory=list)
    hourly_probs: list[int | float] = field(default_factory=list)
    hourly_precips: list[float] = field(default_factory=list)
    hourly_codes: list[int] = field(default_factory=list)
    hourly_is_days: list[int] = field(default_factory=list)
    hourly_winds: list[float] = field(default_factory=list)
    hourly_wind_dirs: list[int | float] = field(default_factory=list)
    hourly_gusts: list[float] = field(default_factory=list)
    hourly_uvs: list[float] = field(default_factory=list)
    hourly_hums: list[int | float] = field(default_factory=list)
    hourly_dews: list[int | float] = field(default_factory=list)
    hourly_vis_km: list[float] = field(default_factory=list)
    hourly_press_mm: list[int | float] = field(default_factory=list)
    hourly_press_hpa: list[int | float] = field(default_factory=list)
    uv_max: float = 0.0
    wind_max: float = 0.0
    gust_max: float = 0.0
    dominant_wind_dir: float | int = 0
    dominant_wind_cardinal: str = ""
    dominant_wind_desc: str = ""
    min_humidity: int | float = 0
    max_humidity: int | float = 0
    min_visibility_km: float = 10.0
    max_visibility_km: float = 10.0
    min_pressure_mm: int | float = 750
    max_pressure_mm: int | float = 750
    summary: str = ""

    @property
    def t_min(self) -> int | float:
        return self.min

    @property
    def t_max(self) -> int | float:
        return self.max

    @property
    def day(self) -> str:
        return self.weekday_short

    @property
    def day_name(self) -> str:
        return self.weekday_short

    def to_dict(self) -> dict[str, Any]:
        res = dict(self.__dict__)
        res["t_min"] = self.min
        res["t_max"] = self.max
        res["day"] = self.weekday_short
        res["day_name"] = self.weekday_short
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DayDetailedForecast:
        min_val = data.get("min", data.get("t_min", 0))
        max_val = data.get("max", data.get("t_max", 0))
        short_name = str(data.get("weekday_short", data.get("day", data.get("day_name", ""))))
        return cls(
            day_index=int(data.get("day_index", 0)),
            date_str=str(data.get("date_str", "")),
            day_num=int(data.get("day_num", 0)),
            weekday_letter=str(data.get("weekday_letter", "")),
            weekday_short=short_name,
            full_date=str(data.get("full_date", "")),
            min=min_val,
            max=max_val,
            apparent_min=data.get("apparent_min", min_val),
            apparent_max=data.get("apparent_max", max_val),
            code=int(data.get("code", 0)),
            icon_name=str(data.get("icon_name", "")),
            icon_file=str(data.get("icon_file", "")),
            precip_sum=float(data.get("precip_sum", 0.0)),
            precip_prob_max=data.get("precip_prob_max", 0),
            is_today=bool(data.get("is_today", False)),
            cur_hour=int(data.get("cur_hour", -1)),
            hourly_temps=list(data.get("hourly_temps", [])),
            hourly_apparent=list(data.get("hourly_apparent", [])),
            hourly_probs=list(data.get("hourly_probs", [])),
            hourly_precips=list(data.get("hourly_precips", [])),
            hourly_codes=list(data.get("hourly_codes", [])),
            hourly_is_days=list(data.get("hourly_is_days", [])),
            hourly_winds=list(data.get("hourly_winds", [])),
            hourly_wind_dirs=list(data.get("hourly_wind_dirs", [])),
            hourly_gusts=list(data.get("hourly_gusts", [])),
            hourly_uvs=list(data.get("hourly_uvs", [])),
            hourly_hums=list(data.get("hourly_hums", [])),
            hourly_dews=list(data.get("hourly_dews", [])),
            hourly_vis_km=list(data.get("hourly_vis_km", [])),
            hourly_press_mm=list(data.get("hourly_press_mm", [])),
            hourly_press_hpa=list(data.get("hourly_press_hpa", [])),
            uv_max=float(data.get("uv_max", 0.0)),
            wind_max=float(data.get("wind_max", 0.0)),
            gust_max=float(data.get("gust_max", 0.0)),
            dominant_wind_dir=data.get("dominant_wind_dir", 0),
            dominant_wind_cardinal=str(data.get("dominant_wind_cardinal", "")),
            dominant_wind_desc=str(data.get("dominant_wind_desc", "")),
            min_humidity=data.get("min_humidity", 0),
            max_humidity=data.get("max_humidity", 0),
            min_visibility_km=float(data.get("min_visibility_km", 10.0)),
            max_visibility_km=float(data.get("max_visibility_km", 10.0)),
            min_pressure_mm=data.get("min_pressure_mm", 750),
            max_pressure_mm=data.get("max_pressure_mm", 750),
            summary=str(data.get("summary", "")),
        )


@dataclass
class SolarDetails:
    """Астрономические параметры светового дня."""
    first_light: str = "00:00"
    sunrise: str = "00:00"
    sunset: str = "00:00"
    last_light: str = "00:00"
    daylight_min: float = 0.0
    daylight_str: str = ""
    t_noon_frac: float = 12.0
    t_dawn_frac: float = 6.0
    t_sunrise_frac: float = 6.5
    t_sunset_frac: float = 18.5
    t_dusk_frac: float = 19.0
    curve_points: list[tuple[float, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SolarDetails:
        return cls(
            first_light=str(data.get("first_light", "00:00")),
            sunrise=str(data.get("sunrise", "00:00")),
            sunset=str(data.get("sunset", "00:00")),
            last_light=str(data.get("last_light", "00:00")),
            daylight_min=float(data.get("daylight_min", 0.0)),
            daylight_str=str(data.get("daylight_str", "")),
            t_noon_frac=float(data.get("t_noon_frac", 12.0)),
            t_dawn_frac=float(data.get("t_dawn_frac", 6.0)),
            t_sunrise_frac=float(data.get("t_sunrise_frac", 6.5)),
            t_sunset_frac=float(data.get("t_sunset_frac", 18.5)),
            t_dusk_frac=float(data.get("t_dusk_frac", 19.0)),
            curve_points=[tuple(p) for p in data.get("curve_points", [])],
        )


@dataclass
class DetailedMoon:
    """Параметры Луны и лунного цикла."""
    cycle_fraction: float = 0.0
    illumination: int = 0
    phase_name: str = ""
    phase_name_ru: str = ""
    phase_name_en: str = ""
    age_days: float = 0.0
    days_to_full: int = 0
    distance_km: int = 384400
    distance_str: str = ""
    moonrise: str = ""
    moonset: str = ""
    next_full_moon_date_str: str = ""
    next_new_moon_date_str: str = ""
    tilt_deg: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DetailedMoon:
        return cls(
            cycle_fraction=float(data.get("cycle_fraction", 0.0)),
            illumination=int(data.get("illumination", 0)),
            phase_name=str(data.get("phase_name", "")),
            phase_name_ru=str(data.get("phase_name_ru", "")),
            phase_name_en=str(data.get("phase_name_en", "")),
            age_days=float(data.get("age_days", 0.0)),
            days_to_full=int(data.get("days_to_full", 0)),
            distance_km=int(data.get("distance_km", 384400)),
            distance_str=str(data.get("distance_str", "")),
            moonrise=str(data.get("moonrise", "")),
            moonset=str(data.get("moonset", "")),
            next_full_moon_date_str=str(data.get("next_full_moon_date_str", "")),
            next_new_moon_date_str=str(data.get("next_new_moon_date_str", "")),
            tilt_deg=float(data.get("tilt_deg", 0.0)),
        )


@dataclass
class YesterdayComparison:
    """Сравнение сегодняшних показателей со вчерашними сутками."""
    summary: str = ""
    diff_max: int | float = 0
    today_min: int | float = 0
    today_max: int | float = 0
    yesterday_min: int | float = 0
    yesterday_max: int | float = 0
    yesterday_uv_max: float = 0.0
    yesterday_wind_max: float = 0.0
    yesterday_gust_max: float = 0.0
    yesterday_precip_sum: float = 0.0
    yesterday_min_humidity: int | float = 0
    yesterday_max_humidity: int | float = 0
    yesterday_avg_humidity: int | float = 0
    yesterday_min_visibility_km: float = 10.0
    yesterday_max_visibility_km: float = 10.0
    yesterday_min_pressure_mm: int | float = 750
    yesterday_max_pressure_mm: int | float = 750
    yesterday_avg_pressure_mm: int | float = 750

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> YesterdayComparison:
        return cls(
            summary=str(data.get("summary", "")),
            diff_max=data.get("diff_max", 0),
            today_min=data.get("today_min", 0),
            today_max=data.get("today_max", 0),
            yesterday_min=data.get("yesterday_min", 0),
            yesterday_max=data.get("yesterday_max", 0),
            yesterday_uv_max=float(data.get("yesterday_uv_max", 0.0)),
            yesterday_wind_max=float(data.get("yesterday_wind_max", 0.0)),
            yesterday_gust_max=float(data.get("yesterday_gust_max", 0.0)),
            yesterday_precip_sum=float(data.get("yesterday_precip_sum", 0.0)),
            yesterday_min_humidity=data.get("yesterday_min_humidity", 0),
            yesterday_max_humidity=data.get("yesterday_max_humidity", 0),
            yesterday_avg_humidity=data.get("yesterday_avg_humidity", 0),
            yesterday_min_visibility_km=float(data.get("yesterday_min_visibility_km", 10.0)),
            yesterday_max_visibility_km=float(data.get("yesterday_max_visibility_km", 10.0)),
            yesterday_min_pressure_mm=data.get("yesterday_min_pressure_mm", 750),
            yesterday_max_pressure_mm=data.get("yesterday_max_pressure_mm", 750),
            yesterday_avg_pressure_mm=data.get("yesterday_avg_pressure_mm", 750),
        )


@dataclass
class CurrentConditions:
    """Текущее состояние атмосферы."""
    temp: int | float = 0
    feels_like: int | float = 0
    feels_like_desc: str = ""
    humidity: int | float = 0
    dew_point: int | float = 0
    wind_speed: float = 0.0
    wind_gusts: float = 0.0
    wind_direction: float | int = 0
    wind_cardinal: str = ""
    wind_desc: str = ""
    pressure_mm: int | float = 750
    pressure_desc: str = ""
    uv_index: float = 0.0
    uv_level: str = ""
    uv_desc: str = ""
    visibility_km: float = 10.0
    visibility_desc: str = ""
    precipitation: float = 0.0
    precipitation_sum: float = 0.0
    precip_desc: str = ""
    sunrise_str: str = "06:00"
    sunset_str: str = "18:00"
    is_day: int = 1
    weather_code: int = 0
    condition_text: str = ""
    temp_min: int | float = 0
    temp_max: int | float = 0
    grad_type: str = "clear_day"
    time_of_day: str = "day"
    grad_class: str = "grad-clear-day"
    bg_class: str = "weather-clear-day"
    icon_name: str = "sun.svg"
    icon_file: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class WeatherForecastData(MutableMapping):
    """
    Полный агрегат прогноза погоды.
    Реализует интерфейс MutableMapping для полной обратной совместимости с существующим кодом UI (data['temp'], data['key'] = val).
    """
    city_name: str = ""
    country: str = ""
    lat: float = 0.0
    lon: float = 0.0

    current: CurrentConditions = field(default_factory=CurrentConditions)

    avg_diff_str: str = ""
    avg_norm_max: float | int | None = None
    avg_desc: str = ""

    overall_min: int | float = 0
    overall_max: int | float = 0

    hourly: list[HourlyForecast] = field(default_factory=list)
    daily: list[DailyForecast] = field(default_factory=list)
    days_detailed: list[DayDetailedForecast] = field(default_factory=list)

    yesterday_comp: YesterdayComparison = field(default_factory=YesterdayComparison)
    solar_details: SolarDetails = field(default_factory=SolarDetails)
    detailed_moon: DetailedMoon = field(default_factory=DetailedMoon)

    climate_averages: dict[str, Any] | None = None
    moon_phase: dict[str, Any] = field(default_factory=dict)

    forecast_date: str = ""
    utc_offset_seconds: int = 0
    timezone: str = "auto"
    cached_at: float = 0.0

    weather_model: str = "best_match"
    cell_selection: str = "land"
    elevation: float | None = None
    precip_nowcast: str = ""
    minutely_15: dict[str, Any] = field(default_factory=dict)
    forecast_source: str = "consensus"
    is_consensus: bool = False
    sources_count: int = 1
    source_name: str = ""
    is_fallback: bool = False
    fallback_reason: str = ""

    raw_extra: dict[str, Any] = field(default_factory=dict)
    _cached_dict: dict[str, Any] | None = field(default=None, init=False, repr=False)

    def invalidate_cache(self) -> None:
        self._cached_dict = None

    def _get_dict(self) -> dict[str, Any]:
        if self._cached_dict is None:
            self._cached_dict = self.to_dict()
        return self._cached_dict

    def to_dict(self) -> dict[str, Any]:
        """Преобразование модели в словарь, полностью совместимый с существующим UI."""
        res: dict[str, Any] = dict(self.raw_extra)

        def _to_data(val: Any) -> Any:
            if hasattr(val, "to_dict"):
                return val.to_dict()
            return val

        res.update({
            "city_name": self.city_name,
            "country": self.country,
            "lat": self.lat,
            "lon": self.lon,
            "avg_diff_str": self.avg_diff_str,
            "avg_norm_max": self.avg_norm_max,
            "avg_desc": self.avg_desc,
            "overall_min": self.overall_min,
            "overall_max": self.overall_max,
            "forecast_date": self.forecast_date,
            "utc_offset_seconds": self.utc_offset_seconds,
            "timezone": self.timezone,
            "cached_at": self.cached_at,
            "weather_model": self.weather_model,
            "cell_selection": self.cell_selection,
            "elevation": self.elevation,
            "precip_nowcast": self.precip_nowcast,
            "minutely_15": self.minutely_15,
            "forecast_source": self.forecast_source,
            "is_consensus": self.is_consensus,
            "sources_count": self.sources_count,
            "source_name": self.source_name,
            "climate_averages": self.climate_averages,
            "moon_phase": self.moon_phase,
            "yesterday_comp": _to_data(self.yesterday_comp),
            "source_name": self.source_name,
            "is_fallback": self.is_fallback,
            "fallback_reason": self.fallback_reason,
            "solar_details": _to_data(self.solar_details),
            "detailed_moon": _to_data(self.detailed_moon),
            "hourly": [_to_data(h) for h in self.hourly] if isinstance(self.hourly, list) else self.hourly,
            "daily": [_to_data(d) for d in self.daily] if isinstance(self.daily, list) else self.daily,
            "days_detailed": [_to_data(dd) for dd in self.days_detailed] if isinstance(self.days_detailed, list) else self.days_detailed,
        })

        if hasattr(self.current, "to_dict"):
            res.update(self.current.to_dict())
        elif isinstance(self.current, dict):
            res.update(self.current)
        self._cached_dict = res
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeatherForecastData:
        """Создание строго типизированной модели из словаря."""
        known_keys = {
            "city_name", "country", "lat", "lon", "avg_diff_str", "avg_norm_max", "avg_desc",
            "overall_min", "overall_max", "forecast_date", "utc_offset_seconds", "timezone",
            "cached_at", "climate_averages", "moon_phase", "yesterday_comp", "solar_details",
            "detailed_moon", "hourly", "daily", "days_detailed",
            "weather_model", "cell_selection", "elevation", "precip_nowcast", "minutely_15",
            "forecast_source", "is_consensus", "sources_count", "source_name", "is_fallback", "fallback_reason"
        }
        current_keys = {f.name for f in CurrentConditions.__dataclass_fields__.values()}
        all_handled_keys = known_keys | current_keys

        raw_extra = {k: v for k, v in data.items() if k not in all_handled_keys}

        current_dict = {k: data[k] for k in current_keys if k in data}
        current = CurrentConditions(**current_dict) if current_dict else CurrentConditions()

        hourly = [
            h if isinstance(h, HourlyForecast) else HourlyForecast.from_dict(h)
            for h in data.get("hourly", [])
        ]
        daily = [
            d if isinstance(d, DailyForecast) else DailyForecast.from_dict(d)
            for d in data.get("daily", [])
        ]
        days_detailed = [
            dd if isinstance(dd, DayDetailedForecast) else DayDetailedForecast.from_dict(dd)
            for dd in data.get("days_detailed", [])
        ]

        yc_raw = data.get("yesterday_comp", {})
        yesterday_comp = yc_raw if isinstance(yc_raw, YesterdayComparison) else YesterdayComparison.from_dict(yc_raw)

        sd_raw = data.get("solar_details", {})
        solar_details = sd_raw if isinstance(sd_raw, SolarDetails) else SolarDetails.from_dict(sd_raw)

        dm_raw = data.get("detailed_moon", {})
        detailed_moon = dm_raw if isinstance(dm_raw, DetailedMoon) else DetailedMoon.from_dict(dm_raw)

        return cls(
            city_name=str(data.get("city_name", "")),
            country=str(data.get("country", "")),
            lat=float(data.get("lat", 0.0)),
            lon=float(data.get("lon", 0.0)),
            current=current,
            avg_diff_str=str(data.get("avg_diff_str", "")),
            avg_norm_max=data.get("avg_norm_max"),
            avg_desc=str(data.get("avg_desc", "")),
            overall_min=data.get("overall_min", 0),
            overall_max=data.get("overall_max", 0),
            hourly=hourly,
            daily=daily,
            days_detailed=days_detailed,
            yesterday_comp=yesterday_comp,
            solar_details=solar_details,
            detailed_moon=detailed_moon,
            climate_averages=data.get("climate_averages"),
            moon_phase=data.get("moon_phase", {}),
            forecast_date=str(data.get("forecast_date", "")),
            utc_offset_seconds=int(data.get("utc_offset_seconds", 0)),
            timezone=str(data.get("timezone", "auto")),
            cached_at=float(data.get("cached_at", 0.0)),
            weather_model=str(data.get("weather_model", "best_match")),
            cell_selection=str(data.get("cell_selection", "land")),
            elevation=float(data["elevation"]) if data.get("elevation") is not None else None,
            precip_nowcast=str(data.get("precip_nowcast", "")),
            minutely_15=dict(data.get("minutely_15", {})),
            forecast_source=str(data.get("forecast_source", "consensus")),
            is_consensus=bool(data.get("is_consensus", False)),
            sources_count=int(data.get("sources_count", 1)),
            source_name=str(data.get("source_name", "")),
            is_fallback=bool(data.get("is_fallback", False)),
            fallback_reason=str(data.get("fallback_reason", "")),
            raw_extra=raw_extra,
        )

    # Реализация MutableMapping для прозрачного доступа и мутации по ключам data["temp"], data.get(...), data["k"] = v
    def __getitem__(self, key: str) -> Any:
        return self._get_dict()[key]

    def __setitem__(self, key: str, value: Any):
        self._cached_dict = None
        if hasattr(self, key):
            setattr(self, key, value)
        elif hasattr(self.current, key):
            setattr(self.current, key, value)
        else:
            self.raw_extra[key] = value

    def __delitem__(self, key: str):
        self._cached_dict = None
        if key in self.raw_extra:
            del self.raw_extra[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._get_dict())

    def __len__(self) -> int:
        return len(self._get_dict())

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return key in self._get_dict()

    def get(self, key: str, default: Any = None) -> Any:
        return self._get_dict().get(key, default)
