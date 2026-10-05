import json
import math
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Re-export all WMO mappings, climate data, and formatting helpers
from data.wmo_conditions import (
    MAJOR_CITIES,
    MET_SYMBOL_TO_WMO,
    WEEKDAY_LETTERS,
    WMO_INFO,
    apply_seasonal_norm,
    calculate_climate_averages,
    convert_temp,
    convert_temp_diff,
    determine_solar_time_of_day,
    ensure_days_detailed,
    format_full_date,
    format_temp,
    get_condition_text,
    get_fallback_data,
    get_geo_timezone_offset_seconds,
    get_smart_day_summary,
    get_weekday_name,
    get_wind_direction_info,
    met_symbol_to_wmo,
)
from i18n import get_current_language, t
from logger import get_logger
from models.weather import WeatherForecastData
from providers.cache import WeatherCacheManager
from providers.clients import MetNorwayClient, OpenMeteoClient, WttrClient

# Re-export all astronomical functions for backwards compatibility
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
from utils import set_clipboard_text

from .base import BaseProvider, SearchResult

logger = get_logger("weather")

CACHE_DIR = Path(os.path.expanduser("~/.cache/echo_weather"))
CACHE_FILE = CACHE_DIR / "weather.json"
ICONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "weather"))

WEATHER_PREFIXES = (
    "погода в ", "погода ", "прогноз в ", "прогноз ", "weather in ", "weather ", "forecast in ", "forecast "
)


class WeatherProvider(BaseProvider):
    """Meteorological data coordinator managing caching, API clients, and forecast normalization."""

    def __init__(self, history_manager=None, config_manager=None, auto_refresh: bool = True):
        super().__init__(history_manager)
        self.config_manager = config_manager
        self.cache_dir = CACHE_DIR
        self.cache_file = CACHE_FILE
        self.cache_manager = WeatherCacheManager(self.cache_dir)
        self._in_flight = set()
        self._lock = threading.Lock()
        self.on_data_updated = None
        self._open_meteo_client = OpenMeteoClient()
        self._met_norway_client = MetNorwayClient()
        self._wttr_client = WttrClient()

        if auto_refresh and "pytest" not in sys.modules:
            threading.Thread(target=self._initial_refresh, daemon=True).start()

    @property
    def _cache(self) -> dict:
        """Backwards compatibility property exposing cache dictionary view."""
        return self.cache_manager._cache

    def invalidate_city(self, city_name: str):
        info = self._resolve_city_info(city_name)
        if info and "lat" in info and "lon" in info:
            key = f"{info['lat']:.4f},{info['lon']:.4f}"
            self.cache_manager.invalidate_forecast(key)

    def _get_default_city_name(self) -> str:
        if self.config_manager:
            return self.config_manager.get("weather_default_city", "Нью-Йорк")
        return "Нью-Йорк"

    def _initial_refresh(self):
        try:
            default_name = self._get_default_city_name().lower().strip()
            info = self._resolve_city_info(default_name)
            if info:
                self._fetch_forecast_sync(info.get("lat"), info.get("lon"), info)
            for c in ["нью-йорк", "москва", "новокузнецк", "санкт-петербург"]:
                c_info = MAJOR_CITIES.get(c)
                if c_info:
                    time.sleep(0.15)
                    self._fetch_forecast_sync(c_info["lat"], c_info["lon"], c_info)
            if callable(getattr(self, "on_data_updated", None)):
                try:
                    from gi.repository import GLib
                    GLib.idle_add(self.on_data_updated)
                except Exception as e:
                    logger.debug("GLib.idle_add on_data_updated failed: %s", e)
        except Exception as e:
            logger.debug("Initial refresh background thread interrupted: %s", e)

    def _geocode_sync(self, query_city: str, timeout: float = 3.0) -> dict | None:
        """
        Synchronously query Open-Meteo geocoding API and persist result in geocache.
        """
        q_clean = query_city.lower().strip()
        if not q_clean:
            return None
        try:
            url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(q_clean)}&count=1&language=ru&format=json"
            req = urllib.request.Request(url, headers={"User-Agent": "EchoWeather/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                if results:
                    first = results[0]
                    city_id = first.get("id")
                    name_ru = first.get("name")
                    country_ru = first.get("country", "")
                    name_en = name_ru
                    country_en = country_ru

                    if city_id:
                        try:
                            en_url = f"https://geocoding-api.open-meteo.com/v1/get?id={city_id}"
                            en_req = urllib.request.Request(en_url, headers={"User-Agent": "EchoWeather/1.0"})
                            with urllib.request.urlopen(en_req, timeout=min(timeout, 2.0)) as en_resp:
                                en_data = json.loads(en_resp.read().decode("utf-8"))
                                if en_data.get("name"):
                                    name_en = en_data.get("name")
                                if en_data.get("country"):
                                    country_en = en_data.get("country")
                        except Exception:
                            pass

                    kw = []
                    if name_ru:
                        kw.append(name_ru.lower())
                    if name_en and name_en.lower() != (name_ru or "").lower():
                        kw.append(name_en.lower())

                    info = {
                        "name_ru": name_ru,
                        "name_en": name_en,
                        "lat": float(first.get("latitude", 0.0)),
                        "lon": float(first.get("longitude", 0.0)),
                        "elevation": float(first.get("elevation")) if first.get("elevation") is not None else None,
                        "country_ru": country_ru,
                        "country_en": country_en,
                        "timezone": first.get("timezone", "auto"),
                        "keywords": kw
                    }
                    self.cache_manager.set_geocache(q_clean, info)
                    if name_ru:
                        self.cache_manager.set_geocache(name_ru.lower().strip(), info)
                    if name_en:
                        self.cache_manager.set_geocache(name_en.lower().strip(), info)

                    logger.info("Geocoded '%s' -> %s (lat=%s, lon=%s)", query_city, name_ru, info["lat"], info["lon"])
                    return info
        except Exception as e:
            logger.debug("Geocoding failed for '%s': %s", query_city, e)
        return None

    def _geocode_bg(self, query_city: str):
        try:
            info = self._geocode_sync(query_city, timeout=3.5)
            if info and callable(getattr(self, "on_data_updated", None)):
                try:
                    from gi.repository import GLib
                    GLib.idle_add(self.on_data_updated)
                except Exception as e:
                    logger.debug("GLib.idle_add after geocode failed: %s", e)
        finally:
            self._in_flight.discard(query_city)

    def _resolve_city_info(self, query_city: str, allow_network: bool = False, timeout: float = 2.5) -> dict | None:
        q = query_city.lower().strip()
        if not q:
            return None

        # Prepositional normalization: "в Караганде" -> "караганде", "in London" -> "london"
        q_norm = q
        if q_norm.startswith("в ") and len(q_norm) > 4:
            q_norm = q_norm[2:].strip()
        elif q_norm.startswith("in ") and len(q_norm) > 5:
            q_norm = q_norm[3:].strip()

        # 1. Exact match in MAJOR_CITIES
        if q_norm in MAJOR_CITIES:
            return MAJOR_CITIES[q_norm]
        if q in MAJOR_CITIES:
            return MAJOR_CITIES[q]

        # 2. Match by name_ru, name_en, or keywords
        for test_q in (q_norm, q):
            for key, data in MAJOR_CITIES.items():
                if test_q == data.get("name_ru", "").lower() or test_q == data.get("name_en", "").lower():
                    return data
                for kw in data.get("keywords", []):
                    if test_q == kw.lower():
                        return data

        # 3. Stem / prefix matching
        for test_q in (q_norm, q):
            for key, data in MAJOR_CITIES.items():
                candidates = [key, data.get("name_ru", "").lower(), data.get("name_en", "").lower()] + [kw.lower() for kw in data.get("keywords", [])]
                for cand in candidates:
                    if not cand:
                        continue
                    stem = cand[:-1] if cand[-1] in ("а", "я", "ь", "й", "е", "о", "ы", "и") else cand
                    min_len = 2 if len(cand) <= 3 else 3
                    if len(stem) >= min_len and (test_q.startswith(stem) or stem.startswith(test_q)):
                        return data

        # 4. Local disk-backed geocache
        for test_q in (q_norm, q):
            cached_match = self.cache_manager.find_geocache_candidate(test_q)
            if cached_match:
                return cached_match

        # 5. Synchronous network geocoding if permitted
        if allow_network and len(q_norm) >= 2:
            geocoded = self._geocode_sync(q_norm, timeout=timeout)
            if geocoded:
                return geocoded

        # 6. Background geocoding if synchronous network not permitted
        if not allow_network and len(q_norm) >= 3 and q_norm not in self._in_flight:
            self._in_flight.add(q_norm)
            threading.Thread(target=self._geocode_bg, args=(q_norm,), daemon=True).start()

        return None

    def _fetch_open_meteo(self, lat: float, lon: float, city_info: dict, timeout: float = 3.0, model: str | None = None) -> dict | None:
        return self._open_meteo_client.fetch_forecast(lat=lat, lon=lon, city_info=city_info, timeout=timeout, model=model)

    def _fetch_met_norway(self, lat: float, lon: float, city_info: dict, timeout: float = 3.5) -> dict | None:
        return self._met_norway_client.fetch_forecast(lat=lat, lon=lon, city_info=city_info, timeout=timeout)

    def _fetch_wttr_in(self, lat: float, lon: float, city_info: dict, timeout: float = 3.5) -> dict | None:
        return self._wttr_client.fetch_forecast(lat=lat, lon=lon, city_info=city_info, timeout=timeout)

    def _blend_forecast_consensus(self, om_dict: dict, met_dict: dict) -> dict:
        """
        Ансамблирование метеорологических данных Open-Meteo и MET Norway.
        Взвешенное усреднение текущих и суточных параметров, сглаживание выбросов,
        объединение почасовых прогнозов с сохранением высокоточного 15-минутного радара.
        """
        def _blend_num(v1, v2, w1=0.5, w2=0.5, ndigits=0):
            if v1 is None and v2 is None:
                return None
            if v1 is None:
                return v2
            if v2 is None:
                return v1
            try:
                val = float(v1) * w1 + float(v2) * w2
                return round(val) if ndigits == 0 else round(val, ndigits)
            except (ValueError, TypeError):
                return v1

        # Базовая структура от Open-Meteo (содержит minutely_15, топографию и радар)
        res = dict(om_dict)
        if isinstance(om_dict.get("days_detailed"), list):
            res["days_detailed"] = [dict(d) for d in om_dict["days_detailed"]]
        if isinstance(om_dict.get("daily"), list):
            res["daily"] = [dict(d) for d in om_dict["daily"]]
        if isinstance(om_dict.get("hourly"), list):
            res["hourly"] = [dict(h) for h in om_dict["hourly"]]

        # 1. Ансамблирование текущих условий
        b_temp = _blend_num(om_dict.get("temp"), met_dict.get("temp"), 0.55, 0.45)
        b_fl = _blend_num(om_dict.get("feels_like"), met_dict.get("feels_like"), 0.55, 0.45)
        b_press = _blend_num(om_dict.get("pressure_mm"), met_dict.get("pressure_mm"), 0.5, 0.5)
        b_hum = _blend_num(om_dict.get("humidity"), met_dict.get("humidity"), 0.5, 0.5)
        b_dew = _blend_num(om_dict.get("dew_point"), met_dict.get("dew_point"), 0.5, 0.5)
        b_wind = _blend_num(om_dict.get("wind_speed"), met_dict.get("wind_speed"), 0.5, 0.5, ndigits=1)
        b_gust = _blend_num(om_dict.get("wind_gusts"), met_dict.get("wind_gusts"), 0.5, 0.5, ndigits=1)
        b_min = _blend_num(om_dict.get("temp_min"), met_dict.get("temp_min"), 0.5, 0.5)
        b_max = _blend_num(om_dict.get("temp_max"), met_dict.get("temp_max"), 0.5, 0.5)

        res["temp"] = b_temp
        res["feels_like"] = b_fl
        res["pressure_mm"] = b_press
        res["humidity"] = b_hum
        res["dew_point"] = b_dew
        res["wind_speed"] = b_wind
        res["wind_gusts"] = b_gust
        res["temp_min"] = b_min
        res["temp_max"] = b_max
        if "overall_min" in om_dict and "overall_min" in met_dict:
            res["overall_min"] = _blend_num(om_dict.get("overall_min"), met_dict.get("overall_min"), 0.5, 0.5)
        if "overall_max" in om_dict and "overall_max" in met_dict:
            res["overall_max"] = _blend_num(om_dict.get("overall_max"), met_dict.get("overall_max"), 0.5, 0.5)

        # 2. Ансамблирование суточных детальных прогнозов (days_detailed)
        met_days = met_dict.get("days_detailed", [])
        met_days_by_date = {
            d.get("date_str"): d
            for d in met_days
            if isinstance(d, dict) and d.get("date_str")
        }

        for d_idx, om_day in enumerate(res.get("days_detailed", [])):
            if not isinstance(om_day, dict):
                continue
            date_k = om_day.get("date_str")
            met_day = met_days_by_date.get(date_k)
            if not met_day and d_idx < len(met_days) and isinstance(met_days[d_idx], dict):
                met_day = met_days[d_idx]

            if met_day:
                om_ht = om_day.get("hourly_temps")
                met_ht = met_day.get("hourly_temps")
                if isinstance(om_ht, list) and isinstance(met_ht, list) and len(om_ht) == len(met_ht):
                    blended_ht = [
                        round(0.55 * float(t1) + 0.45 * float(t2))
                        for t1, t2 in zip(om_ht, met_ht)
                    ]
                    om_day["hourly_temps"] = blended_ht
                    if blended_ht:
                        om_day["min"] = min(blended_ht)
                        om_day["max"] = max(blended_ht)
                        om_day["t_min"] = om_day["min"]
                        om_day["t_max"] = om_day["max"]

                om_ha = om_day.get("hourly_apparent")
                met_ha = met_day.get("hourly_apparent")
                if isinstance(om_ha, list) and isinstance(met_ha, list) and len(om_ha) == len(met_ha):
                    blended_ha = [
                        round(0.55 * float(a1) + 0.45 * float(a2))
                        for a1, a2 in zip(om_ha, met_ha)
                    ]
                    om_day["hourly_apparent"] = blended_ha
                    if blended_ha:
                        om_day["apparent_min"] = min(blended_ha)
                        om_day["apparent_max"] = max(blended_ha)

                om_hw = om_day.get("hourly_winds")
                met_hw = met_day.get("hourly_winds")
                if isinstance(om_hw, list) and isinstance(met_hw, list) and len(om_hw) == len(met_hw):
                    om_day["hourly_winds"] = [
                        round(0.5 * float(w1) + 0.5 * float(w2), 1)
                        for w1, w2 in zip(om_hw, met_hw)
                    ]

                om_hh = om_day.get("hourly_hums")
                met_hh = met_day.get("hourly_hums")
                if isinstance(om_hh, list) and isinstance(met_hh, list) and len(om_hh) == len(met_hh):
                    om_day["hourly_hums"] = [
                        round(0.5 * float(h1) + 0.5 * float(h2))
                        for h1, h2 in zip(om_hh, met_hh)
                    ]

                om_hp = om_day.get("hourly_press_mm")
                met_hp = met_day.get("hourly_press_mm")
                if isinstance(om_hp, list) and isinstance(met_hp, list) and len(om_hp) == len(met_hp):
                    om_day["hourly_press_mm"] = [
                        round(0.5 * float(p1) + 0.5 * float(p2))
                        for p1, p2 in zip(om_hp, met_hp)
                    ]

        # 3. Ансамблирование среза daily
        met_daily = met_dict.get("daily", [])
        for d_idx, om_d in enumerate(res.get("daily", [])):
            if not isinstance(om_d, dict):
                continue
            if d_idx < len(met_daily) and isinstance(met_daily[d_idx], dict):
                met_d = met_daily[d_idx]
                om_d["min"] = _blend_num(om_d.get("min"), met_d.get("min"), 0.5, 0.5)
                om_d["max"] = _blend_num(om_d.get("max"), met_d.get("max"), 0.5, 0.5)
                om_d["t_min"] = om_d["min"]
                om_d["t_max"] = om_d["max"]

        # 4. Ансамблирование среза hourly (для горизонтального скролла на первом экране)
        met_hourly = met_dict.get("hourly", [])
        if isinstance(res.get("hourly"), list) and isinstance(met_hourly, list):
            n_hours = min(len(res["hourly"]), len(met_hourly))
            for i in range(n_hours):
                h1 = res["hourly"][i]
                h2 = met_hourly[i]
                if isinstance(h1, dict) and isinstance(h2, dict):
                    h1["temp"] = _blend_num(h1.get("temp"), h2.get("temp"), 0.55, 0.45)

        # 5. Метаданные ансамбля
        res["weather_model"] = "Multi-Model Consensus (ECMWF/ICON + MET Norway)"
        res["forecast_source"] = "consensus"
        res["is_consensus"] = True
        res["sources_count"] = 2
        return res

    def _fetch_forecast_sync(self, lat: float, lon: float, city_info: dict) -> WeatherForecastData | None:
        cache_key = f"{lat:.4f},{lon:.4f}"
        weather_dict = None

        source = "consensus"
        model_name = "best_match"
        if self.config_manager:
            source = self.config_manager.get("forecast_source", "consensus")
            model_name = self.config_manager.get("weather_model", "best_match")

        if source == "consensus":
            om_res = None
            met_res = None
            wttr_res = None
            try:
                with ThreadPoolExecutor(max_workers=3, thread_name_prefix="ConsensusPool") as ex:
                    fut_om = ex.submit(self._fetch_open_meteo, lat, lon, city_info, 2.0)
                    fut_met = ex.submit(self._fetch_met_norway, lat, lon, city_info, 3.5)
                    fut_wttr = ex.submit(self._fetch_wttr_in, lat, lon, city_info, 2.5)
                    try:
                        om_res = fut_om.result()
                    except Exception as e:
                        logger.debug("Consensus: Open-Meteo fetch failed for %s: %s", cache_key, e)
                    try:
                        met_res = fut_met.result()
                    except Exception as e:
                        logger.debug("Consensus: MET Norway fetch failed for %s: %s", cache_key, e)
                    try:
                        wttr_res = fut_wttr.result()
                    except Exception as e:
                        logger.debug("Consensus: wttr.in fetch failed for %s: %s", cache_key, e)
            except RuntimeError:
                try:
                    om_res = self._fetch_open_meteo(lat, lon, city_info, 2.0)
                except Exception:
                    pass
                try:
                    met_res = self._fetch_met_norway(lat, lon, city_info, 3.5)
                except Exception:
                    pass
                try:
                    wttr_res = self._fetch_wttr_in(lat, lon, city_info, 2.5)
                except Exception:
                    pass

            if om_res and met_res:
                weather_dict = self._blend_forecast_consensus(om_res, met_res)
                logger.info("Consensus forecast formed (Open-Meteo + MET Norway) for %s (%s)", cache_key, city_info.get("name_ru"))
            elif met_res and wttr_res:
                weather_dict = self._blend_forecast_consensus(met_res, wttr_res)
                weather_dict["weather_model"] = "Multi-Model Consensus (MET Norway + WWO)"
                logger.info("Consensus forecast formed (MET Norway + wttr.in) for %s (%s)", cache_key, city_info.get("name_ru"))
            elif om_res and wttr_res:
                weather_dict = self._blend_forecast_consensus(om_res, wttr_res)
                weather_dict["weather_model"] = "Multi-Model Consensus (Open-Meteo + WWO)"
                logger.info("Consensus forecast formed (Open-Meteo + wttr.in) for %s (%s)", cache_key, city_info.get("name_ru"))
            elif met_res:
                weather_dict = met_res
                logger.info("Consensus fallback to single MET Norway source for %s (%s)", cache_key, city_info.get("name_ru"))
            elif om_res:
                weather_dict = om_res
                logger.info("Consensus fallback to single Open-Meteo source for %s (%s)", cache_key, city_info.get("name_ru"))
            elif wttr_res:
                weather_dict = wttr_res
                logger.info("Consensus fallback to single wttr.in source for %s (%s)", cache_key, city_info.get("name_ru"))
            else:
                try:
                    weather_dict = self._fetch_wttr_in(lat, lon, city_info, timeout=3.5)
                except Exception as e:
                    logger.debug("wttr.in fallback failed for %s: %s", cache_key, e)

        elif source == "ecmwf":
            try:
                weather_dict = self._fetch_open_meteo(lat, lon, city_info, timeout=2.0, model="ecmwf_ifs025")
            except Exception as e:
                logger.debug("ECMWF fetch failed for %s: %s", cache_key, e)
            if not weather_dict:
                weather_dict = self._fetch_met_norway(lat, lon, city_info, timeout=3.5) or self._fetch_wttr_in(lat, lon, city_info, timeout=3.5)

        elif source == "icon":
            try:
                weather_dict = self._fetch_open_meteo(lat, lon, city_info, timeout=2.0, model="icon_seamless")
            except Exception as e:
                logger.debug("ICON fetch failed for %s: %s", cache_key, e)
            if not weather_dict:
                weather_dict = self._fetch_met_norway(lat, lon, city_info, timeout=3.5) or self._fetch_wttr_in(lat, lon, city_info, timeout=3.5)

        elif source == "met_norway":
            try:
                weather_dict = self._fetch_met_norway(lat, lon, city_info, timeout=3.5)
            except Exception as e:
                logger.debug("MET Norway fetch failed for %s: %s", cache_key, e)
            if not weather_dict:
                weather_dict = self._fetch_open_meteo(lat, lon, city_info, timeout=2.0) or self._fetch_wttr_in(lat, lon, city_info, timeout=3.5)

        elif source == "open_meteo":
            target_model = model_name if model_name in ("best_match", "ecmwf_ifs025", "icon_seamless") else "best_match"
            try:
                weather_dict = self._fetch_open_meteo(lat, lon, city_info, timeout=2.0, model=target_model)
            except Exception as e:
                logger.debug("Open-Meteo fetch failed for %s: %s", cache_key, e)
            if not weather_dict:
                weather_dict = self._fetch_met_norway(lat, lon, city_info, timeout=3.5) or self._fetch_wttr_in(lat, lon, city_info, timeout=3.5)

        else:
            try:
                weather_dict = self._fetch_open_meteo(lat, lon, city_info, timeout=2.0)
            except Exception:
                pass
            if not weather_dict:
                weather_dict = self._fetch_met_norway(lat, lon, city_info, timeout=3.5) or self._fetch_wttr_in(lat, lon, city_info, timeout=3.5)

        if weather_dict:
            lang = get_current_language()
            is_ru = (lang == "ru")
            source_display_names = {
                "consensus": "Консенсус (ECMWF + ICON + MET Norway)" if is_ru else "Consensus (ECMWF + ICON + MET Norway)",
                "ecmwf": "ECMWF IFS (Европа)" if is_ru else "ECMWF IFS (Europe)",
                "icon": "DWD ICON (Германия)" if is_ru else "DWD ICON (Germany)",
                "met_norway": "MET Norway",
                "open_meteo": "Open-Meteo",
            }
            active_src = self.config_manager.get("forecast_source", "consensus") if self.config_manager else "consensus"
            weather_dict["source_name"] = source_display_names.get(active_src, active_src)
            weather_dict["forecast_source"] = active_src
            try:
                weather_model = WeatherForecastData.from_dict(weather_dict)
            except Exception as e:
                logger.debug("WeatherForecastData normalization warning: %s", e)
                weather_model = weather_dict
            self.cache_manager.set_forecast(cache_key, weather_model)
            return weather_model

        return None

    def search(self, query: str, limit: int = 5, category_filter: str = None, force_refresh: bool = False) -> list[SearchResult]:
        if category_filter not in (None, "All", "Weather"):
            return []

        if not query:
            if category_filter == "Weather":
                has_weather_prefix = True
                target_city_name = ""
                raw_q = ""
            else:
                return []
        else:
            raw_q = query.lower().strip()
            has_weather_prefix = False
            target_city_name = ""

        lang = get_current_language()
        is_ru = (lang == "ru")
        score = 880

        for pref in WEATHER_PREFIXES:
            if raw_q.startswith(pref):
                has_weather_prefix = True
                target_city_name = raw_q[len(pref):].strip()
                break

        if not has_weather_prefix:
            if raw_q in ("погода", "weather", "прогноз"):
                has_weather_prefix = True
                target_city_name = ""

        city_info = None
        if not has_weather_prefix:
            if len(raw_q) < 3:
                return []
            city_info = self._resolve_city_info(raw_q, allow_network=False)
            if city_info is not None:
                target_city_name = raw_q
                score = 80
            elif category_filter == "Weather":
                city_info = self._resolve_city_info(raw_q, allow_network=True, timeout=2.5)
                if city_info is not None:
                    target_city_name = raw_q
                    score = 80
                else:
                    return []
            else:
                if re.match(r"^[A-Za-zА-Яа-яЁё\s\-]+$", raw_q):
                    city_info = self._resolve_city_info(raw_q, allow_network=True, timeout=2.5)
                    if city_info is not None:
                        target_city_name = raw_q
                        score = 80
                    else:
                        return []
                else:
                    return []

        if not target_city_name:
            target_city_name = self._get_default_city_name()

        if not city_info:
            city_info = self._resolve_city_info(target_city_name, allow_network=True, timeout=2.5)
        if not city_info:
            return []

        lat = city_info.get("lat")
        lon = city_info.get("lon")
        if lat is None or lon is None:
            return []

        cache_key = f"{lat:.4f},{lon:.4f}"
        cached_raw = self.cache_manager.get_forecast(cache_key)
        weather_data = WeatherForecastData.from_dict(cached_raw) if cached_raw else None

        utc_now = datetime.now(timezone.utc)
        city_offset = (weather_data.get("utc_offset_seconds", 0) if weather_data else 0)
        city_today_str = (utc_now + timedelta(seconds=city_offset)).strftime("%Y-%m-%d")

        is_date_stale = False
        source = self.config_manager.get("forecast_source", "consensus") if self.config_manager else "consensus"
        if weather_data:
            fc_date = weather_data.get("forecast_date")
            first_d_str = weather_data.get("days_detailed", [{}])[0].get("date_str") if weather_data.get("days_detailed") else None
            if not fc_date or fc_date != city_today_str or (first_d_str and first_d_str < city_today_str):
                is_date_stale = True
            if weather_data.get("forecast_source") and weather_data.get("forecast_source") != source:
                is_date_stale = True

        now = time.time()
        if not weather_data or is_date_stale or force_refresh:
            fresh = self._fetch_forecast_sync(lat, lon, city_info)
            if fresh:
                weather_data = fresh
            elif not weather_data:
                fallback_dict = get_fallback_data(target_city_name, lang)
                weather_data = WeatherForecastData.from_dict(fallback_dict)
                if cache_key not in self._in_flight:
                    self._in_flight.add(cache_key)
                    threading.Thread(
                        target=self._fetch_and_release,
                        args=(lat, lon, city_info, cache_key),
                        daemon=True
                    ).start()
                return [self._create_search_result(weather_data, score)]

        if now - weather_data.get("cached_at", 0) > 1200:
            if cache_key not in self._in_flight:
                self._in_flight.add(cache_key)
                threading.Thread(
                    target=self._fetch_and_release,
                    args=(lat, lon, city_info, cache_key),
                    daemon=True
                ).start()

        w_code = weather_data.get("weather_code", 0)
        is_day = bool(weather_data.get("is_day", 1))
        weather_data["condition_text"] = get_condition_text(w_code, lang=lang, is_day=is_day)
        city_display = city_info.get("name_ru" if is_ru else "name_en", weather_data.get("city_name", ""))
        weather_data["city_name"] = city_display
        weather_data["name_ru"] = city_info.get("name_ru", city_display)
        weather_data["name_en"] = city_info.get("name_en", city_display)
        country_display = city_info.get("country_ru" if is_ru else "country_en", weather_data.get("country", ""))
        weather_data["country"] = country_display

        if "solar_details" not in weather_data or not weather_data.get("solar_details"):
            utc_off = weather_data.get("utc_offset_seconds", 0) / 3600.0
            c_date = (utc_now + timedelta(hours=utc_off)).date()
            sd = calculate_solar_details(lat, lon, c_date, utc_off, is_ru=is_ru)
            sd["annual_table"] = calculate_annual_solar_table(lat, lon, utc_off, is_ru=is_ru)
            weather_data["solar_details"] = sd

        if "detailed_moon" not in weather_data or not weather_data.get("detailed_moon"):
            utc_off = weather_data.get("utc_offset_seconds", 0) / 3600.0
            c_now = datetime.now(timezone.utc) + timedelta(hours=utc_off)
            weather_data["detailed_moon"] = calculate_detailed_moon(lat, lon, c_now, utc_off, is_ru=is_ru)

        max_gust = round(weather_data.get("wind_gusts", round(weather_data.get("wind_speed", 0))))
        if is_day and w_code in (0, 1):
            weather_data["summary"] = t("weather_summary_clear_day", gust=max_gust)
        elif not is_day and w_code in (0, 1):
            weather_data["summary"] = t("weather_summary_clear_night", gust=max_gust)
        elif w_code in (51, 53, 55, 56, 57) or weather_data.get("grad_type") == "drizzle":
            weather_data["summary"] = t("weather_summary_drizzle", gust=max_gust)
        else:
            weather_data["summary"] = t("weather_summary_generic", gust=max_gust, condition=weather_data["condition_text"])

        return [self._create_search_result(weather_data, score)]

    def _fetch_and_release(self, lat: float, lon: float, city_info: dict, cache_key: str):
        try:
            self._fetch_forecast_sync(lat, lon, city_info)
            if callable(getattr(self, "on_data_updated", None)):
                try:
                    from gi.repository import GLib
                    GLib.idle_add(self.on_data_updated)
                except Exception:
                    try:
                        self.on_data_updated()
                    except Exception as e:
                        logger.debug("Direct on_data_updated failed: %s", e)
        finally:
            self._in_flight.discard(cache_key)

    def _create_search_result(self, data: WeatherForecastData | dict, score: float) -> SearchResult:
        from config_manager import ConfigManager
        if self.config_manager:
            temp_unit = self.config_manager.get("temperature_unit", "celsius")
        else:
            temp_unit = ConfigManager().get("temperature_unit", "celsius")
        data["temp_unit"] = temp_unit

        city_name = data.get("city_name", "Погода")
        temp = data.get("temp", 0)
        temp_disp = convert_temp(temp, temp_unit)
        temp_str = f"{temp_disp:+d}°" if temp_disp != 0 else "0°"
        cond_text = data.get("condition_text", "Ясно")
        t_min = convert_temp(data.get("temp_min", temp), temp_unit)
        t_max = convert_temp(data.get("temp_max", temp), temp_unit)

        title = f"{city_name}: {temp_str}"
        feels_like = convert_temp(data.get("feels_like", temp), temp_unit)
        feels_str = f"{feels_like:+d}°" if feels_like != 0 else "0°"
        feels_prefix = t("weather_feels_like_prefix", temp=feels_str)
        subtitle = f"{cond_text} · {feels_prefix} · ↓ {t_min}° ↑ {t_max}°"

        icon_file = data.get("icon_file", os.path.join(ICONS_DIR, "clear-night.svg"))

        copy_text = f"{city_name}: {temp_str}, {cond_text} (↓ {t_min}° ↑ {t_max}°)"

        def copy_action():
            set_clipboard_text(copy_text)

        res = SearchResult(
            id=f"weather_{city_name}",
            title=title,
            subtitle=subtitle,
            icon=icon_file,
            score=score,
            category="Weather",
            provider="WeatherProvider",
            preview_data=data,
            action_execute=copy_action,
            action_copy=copy_action
        )
        res._action_copy = True
        res.copy_value = copy_text
        return res
