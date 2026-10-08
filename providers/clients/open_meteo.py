"""
Клиент для взаимодействия с API Open-Meteo.
Парсит текущие показатели, почасовые и суточные массивы, рассчитывает сравнительные метрики.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from i18n import get_current_language, t
from logger import get_logger
from providers.clients.base import BaseWeatherClient
from services.astronomy import calculate_annual_solar_table, calculate_detailed_moon, calculate_solar_details

logger = get_logger("weather.open_meteo")


class OpenMeteoClient(BaseWeatherClient):
    """Сетевой клиент для метеорологического сервиса Open-Meteo."""

    def build_forecast_url(
        self,
        lat: float,
        lon: float,
        city_info: dict[str, Any] | None = None,
        model: str | None = None,
        **kwargs: Any
    ) -> str:
        """Формирование оптимизированного URL запроса к API Open-Meteo с флагманскими моделями и топографией."""
        if city_info is None:
            city_info = {}
        tz = kwargs.get("timezone") or city_info.get("timezone") or "auto"
        tz_param = urllib.parse.quote(str(tz))

        # Модели численного прогноза: best_match, ecmwf_ifs025, icon_seamless, etc.
        model_name = model or city_info.get("weather_model") or city_info.get("model") or "best_match"
        model_param = urllib.parse.quote(str(model_name))

        elevation = city_info.get("elevation") if city_info.get("elevation") is not None else city_info.get("altitude")
        elevation_param = f"&elevation={float(elevation)}" if elevation is not None else ""

        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m,surface_pressure,dew_point_2m,precipitation,uv_index,visibility"
            f"&hourly=temperature_2m,apparent_temperature,precipitation_probability,precipitation,weather_code,is_day,wind_speed_10m,wind_direction_10m,wind_gusts_10m,uv_index,relative_humidity_2m,dew_point_2m,visibility,surface_pressure"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,sunrise,sunset,uv_index_max,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant"
            f"&minutely_15=precipitation,weather_code"
            f"&models={model_param}"
            f"&cell_selection=land"
            f"{elevation_param}"
            f"&past_days=1&timezone={tz_param}&forecast_days=10"
        )
        return url

    def fetch_forecast(
        self,
        lat: float,
        lon: float,
        city_info: dict[str, Any] | None = None,
        timeout: float = 2.0,
        model: str | None = None,
        **kwargs: Any
    ) -> dict[str, Any] | None:
        if city_info is None:
            city_info = {}
        model_name = model or city_info.get("weather_model") or city_info.get("model") or "best_match"
        cache_key = f"{lat:.4f},{lon:.4f}"
        try:
            url = self.build_forecast_url(lat, lon, city_info=city_info, model=model_name, **kwargs)
            req = urllib.request.Request(url, headers={"User-Agent": "EchoWeatherApp/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                return self.parse_forecast_response(raw, lat=lat, lon=lon, city_info=city_info, model_name=model_name)
        except Exception as e:
            logger.debug(f"Fetch open meteo error for {cache_key}: {e}")
            return None

    def parse_forecast_response(
        self,
        raw: dict[str, Any],
        lat: float,
        lon: float,
        city_info: dict[str, Any] | None = None,
        model_name: str = "best_match"
    ) -> dict[str, Any]:
        """Парсинг ответа Open-Meteo с обогащением 15-минутным радарным прогнозом осадков."""
        from providers.weather import (
            ICONS_DIR,
            WEEKDAY_LETTERS,
            WMO_INFO,
            calculate_climate_averages,
            format_full_date,
            get_condition_text,
            get_smart_day_summary,
            get_weekday_name,
            get_wind_direction_info,
        )

        if city_info is None:
            city_info = {}

        current = raw.get("current", {})
        hourly = raw.get("hourly", {})
        daily = raw.get("daily", {})

        temp = round(current.get("temperature_2m", 0))
        feels_like = round(current.get("apparent_temperature", temp))
        humidity = round(current.get("relative_humidity_2m", 0))
        dew_point = round(current.get("dew_point_2m", temp - ((100 - max(0, min(100, humidity))) / 5)))
        wind = round(current.get("wind_speed_10m", 0), 1)
        wind_dir = current.get("wind_direction_10m", 0)

        press_hpa = current.get("surface_pressure", 1013)
        press_mm = round(press_hpa * 0.750062)

        utc_offset = raw.get("utc_offset_seconds", 0)
        utc_now = datetime.now(timezone.utc)
        city_now = utc_now + timedelta(seconds=utc_offset)
        city_today_str = city_now.strftime("%Y-%m-%d")

        d_times = daily.get("time", [])
        if city_today_str in d_times:
            today_d_idx = d_times.index(city_today_str)
        else:
            today_d_idx = 1 if len(d_times) > 1 else 0

        has_yesterday = (today_d_idx > 0)
        yesterday_d_idx = today_d_idx - 1 if has_yesterday else 0

        max_list = daily.get("temperature_2m_max", [temp])
        min_list = daily.get("temperature_2m_min", [temp])
        t_max = round(max_list[today_d_idx]) if len(max_list) > today_d_idx else temp
        t_min = round(min_list[today_d_idx]) if len(min_list) > today_d_idx else temp

        d_uv_maxs = daily.get("uv_index_max", [0.0] * len(d_times))
        uv_index = float(current.get("uv_index", (d_uv_maxs[today_d_idx] if len(d_uv_maxs) > today_d_idx else 0)))
        visibility_m = current.get("visibility", 10000.0)
        vis_km = round(visibility_m / 1000.0)

        precipitation = round(current.get("precipitation", 0.0), 1)
        d_precip_sums = daily.get("precipitation_sum", [0.0] * len(d_times))
        precip_sum = round(float(d_precip_sums[today_d_idx]), 1) if len(d_precip_sums) > today_d_idx else 0.0

        sr_list = daily.get("sunrise", [])
        ss_list = daily.get("sunset", [])
        sr_raw = sr_list[today_d_idx] if len(sr_list) > today_d_idx else ""
        ss_raw = ss_list[today_d_idx] if len(ss_list) > today_d_idx else ""
        sunrise_str = sr_raw.split("T")[-1][:5] if "T" in sr_raw else sr_raw
        sunset_str = ss_raw.split("T")[-1][:5] if "T" in ss_raw else ss_raw

        is_day = current.get("is_day", 1)
        w_code = current.get("weather_code", 0)

        w_info = WMO_INFO.get(w_code, WMO_INFO[0])
        lang = get_current_language()
        is_ru = (lang == "ru")
        cond_text = get_condition_text(w_code, lang=lang, is_day=(is_day == 1))
        icon_name = w_info["icon_day"] if is_day else w_info["icon_night"]
        grad_type = w_info["grad"]
        time_of_day = "day" if is_day else "night"
        if grad_type == "clear":
            city_curr_naive = city_now.replace(tzinfo=None)
            try:
                if ss_raw and "T" in ss_raw:
                    sunset_dt = datetime.fromisoformat(ss_raw)
                    diff_ss = (city_curr_naive - sunset_dt).total_seconds() / 60.0
                    if -60 <= diff_ss <= 45:
                        time_of_day = "dusk"
                if sr_raw and "T" in sr_raw and time_of_day != "dusk":
                    sunrise_dt = datetime.fromisoformat(sr_raw)
                    diff_sr = (city_curr_naive - sunrise_dt).total_seconds() / 60.0
                    if -45 <= diff_sr <= 45:
                        time_of_day = "dusk"
            except (ValueError, TypeError) as e:
                logger.debug("Error computing dusk/dawn: %s", e)
        grad_class = f"weather-grad-{grad_type}-{time_of_day}"
        bg_class = f"weather-bg-{grad_type}-{time_of_day}"

        wind_cardinal, wind_desc = get_wind_direction_info(wind_dir, lang=lang)

        if uv_index < 3:
            uv_level = t("weather_uv_low")
            uv_desc = t("weather_uv_low_desc")
        elif uv_index < 6:
            uv_level = t("weather_uv_moderate")
            uv_desc = t("weather_uv_moderate_desc")
        elif uv_index < 8:
            uv_level = t("weather_uv_high")
            uv_desc = t("weather_uv_high_desc")
        elif uv_index < 11:
            uv_level = t("weather_uv_very_high")
            uv_desc = t("weather_uv_very_high_desc")
        else:
            uv_level = t("weather_uv_extreme")
            uv_desc = t("weather_uv_extreme_desc")

        if press_mm < 745:
            pressure_desc = t("weather_pressure_low")
        elif press_mm > 765:
            pressure_desc = t("weather_pressure_high")
        else:
            pressure_desc = t("weather_pressure_normal")

        # 15-минутный радарный прогноз осадков (nowcasting)
        minutely_15 = raw.get("minutely_15", {})
        m_times = minutely_15.get("time", [])
        m_precips = minutely_15.get("precipitation", [])

        precip_nowcast = ""
        if m_times and m_precips:
            cur_m_idx = 0
            now_iso = city_now.strftime("%Y-%m-%dT%H:%M")
            for m_idx, mt_str in enumerate(m_times):
                if mt_str >= now_iso:
                    cur_m_idx = m_idx
                    break
            horizon = m_precips[cur_m_idx:cur_m_idx + 8]
            is_raining_now = (precipitation > 0) or (len(horizon) > 0 and horizon[0] > 0.05)
            if is_raining_now:
                end_minutes = None
                for h_i, p_val in enumerate(horizon):
                    if p_val <= 0.05:
                        end_minutes = h_i * 15
                        break
                if end_minutes is not None and end_minutes > 0:
                    precip_nowcast = f"Дождь закончится примерно через {end_minutes} мин." if is_ru else f"Rain stopping in ~{end_minutes} min."
                else:
                    precip_nowcast = "Дождь продолжится в течение ближайших 2 часов." if is_ru else "Rain continuing for the next 2 hours."
            else:
                start_minutes = None
                for h_i, p_val in enumerate(horizon):
                    if p_val > 0.05:
                        start_minutes = h_i * 15
                        break
                if start_minutes is not None:
                    if start_minutes == 0:
                        precip_nowcast = "Начинаются небольшие осадки." if is_ru else "Light precipitation starting now."
                    else:
                        precip_nowcast = f"Осадки начнутся примерно через {start_minutes} мин." if is_ru else f"Precipitation starting in ~{start_minutes} min."
                else:
                    precip_nowcast = "В ближайшие 2 часа осадков не ожидается." if is_ru else "No precipitation in next 2 hours."

        if precip_nowcast:
            precip_desc = precip_nowcast
        elif precip_sum > 0 or precipitation > 0:
            p_val = precipitation if precipitation > 0 else precip_sum
            precip_desc = f"Ожидается около {p_val} мм осадков." if is_ru else f"Expected around {p_val} mm precipitation."
        else:
            precip_desc = "В ближайшее время осадков не ожидается." if is_ru else "No precipitation expected in the near future."

        city_name = city_info.get("name_ru" if is_ru else "name_en", city_info.get("name", "Unknown"))
        country = city_info.get("country_ru" if is_ru else "country_en", city_info.get("country", ""))

        h_times = hourly.get("time", [])
        cur_h_idx = -1
        for idx, t_str in enumerate(h_times):
            try:
                dt = datetime.fromisoformat(t_str)
                if dt.date() == city_now.date() and dt.hour == city_now.hour:
                    cur_h_idx = idx
                    break
            except Exception:
                pass
        if cur_h_idx == -1 and h_times:
            cur_h_idx = 0

        h_temps = hourly.get("temperature_2m", [])
        h_codes = hourly.get("weather_code", [])
        h_is_days = hourly.get("is_day", [])
        h_gusts = hourly.get("wind_gusts_10m", [])
        h_precips = hourly.get("precipitation", [])
        h_winds = hourly.get("wind_speed_10m", [])
        h_wind_dirs = hourly.get("wind_direction_10m", [])
        h_uvs = hourly.get("uv_index", [])
        h_hums = hourly.get("relative_humidity_2m", [])
        h_dews = hourly.get("dew_point_2m", [])
        h_vis = hourly.get("visibility", [])
        h_press = hourly.get("surface_pressure", [])

        solar_details = calculate_solar_details(lat, lon, city_now.date(), utc_offset / 3600.0, lang=lang)
        solar_details["annual_table"] = calculate_annual_solar_table(lat, lon, utc_offset / 3600.0, lang=lang)
        detailed_moon = calculate_detailed_moon(lat, lon, city_now, utc_offset / 3600.0, lang=lang)

        hourly_today_for_climate = []
        today_start_h = today_d_idx * 24
        today_end_h = today_start_h + 24
        if len(h_temps) >= today_end_h:
            for h_i in range(today_start_h, today_end_h):
                hourly_today_for_climate.append({"temp": round(h_temps[h_i])})

        climate_averages = calculate_climate_averages(lat, lon, t_max, t_min, hourly_today=hourly_today_for_climate, lang=lang)
        diff_val = climate_averages.get("temp_diff_str_short") or climate_averages.get("temp_diff_str") or "0°"
        if not diff_val.endswith("°"):
            diff_val = f"{diff_val}°"
        avg_diff_str = t("weather_climate_vs_norm", diff=diff_val)
        avg_norm_max = climate_averages.get("temp_avg_max", t_max)
        avg_desc = climate_averages.get("summary_temp") or (
            t("weather_climate_near_norm")
        )

        hourly_list = []
        max_gust = round(current.get("wind_gusts_10m", 0))

        for i in range(cur_h_idx, min(cur_h_idx + 25, len(h_times))):
            t_str = h_times[i]
            is_cur = (i == cur_h_idx)
            try:
                dt = datetime.fromisoformat(t_str)
                lbl = t("weather_now") if is_cur else f"{dt.hour:02d}:00"
                h_num = dt.hour
            except Exception:
                lbl = f"{i:02d}:00"
                h_num = i % 24

            code_i = h_codes[i] if i < len(h_codes) else w_code
            is_day_i = h_is_days[i] if i < len(h_is_days) else 1
            w_inf_i = WMO_INFO.get(code_i, WMO_INFO[0])
            icon_i = w_inf_i["icon_day"] if is_day_i else w_inf_i["icon_night"]

            if i < len(h_gusts) and h_gusts[i] is not None:
                max_gust = max(max_gust, round(h_gusts[i]))

            hourly_list.append({
                "time": lbl,
                "hour_num": h_num,
                "is_now": is_cur,
                "temp": round(h_temps[i]) if i < len(h_temps) else temp,
                "code": code_i,
                "icon_name": icon_i,
                "icon_file": os.path.join(ICONS_DIR, icon_i)
            })

        d_codes = daily.get("weather_code", [])
        d_mins = daily.get("temperature_2m_min", [])
        d_maxs = daily.get("temperature_2m_max", [])
        d_apps_min = daily.get("apparent_temperature_min", d_mins)
        d_apps_max = daily.get("apparent_temperature_max", d_maxs)
        d_precip_sums = daily.get("precipitation_sum", [0] * len(d_times))
        d_precip_probs = daily.get("precipitation_probability_max", [0] * len(d_times))

        h_apps = hourly.get("apparent_temperature", h_temps)
        h_probs = hourly.get("precipitation_probability", [0] * len(h_times))
        d_wind_maxs = daily.get("wind_speed_10m_max", [0.0] * len(d_times))
        d_gust_maxs = daily.get("wind_gusts_10m_max", [0.0] * len(d_times))
        d_wind_dirs = daily.get("wind_direction_10m_dominant", [0] * len(d_times))

        today_max = round(d_maxs[today_d_idx]) if len(d_maxs) > today_d_idx else temp
        today_min = round(d_mins[today_d_idx]) if len(d_mins) > today_d_idx else temp
        yesterday_max = round(d_maxs[yesterday_d_idx]) if has_yesterday and len(d_maxs) > yesterday_d_idx else today_max
        yesterday_min = round(d_mins[yesterday_d_idx]) if has_yesterday and len(d_mins) > yesterday_d_idx else today_min

        diff_yesterday = today_max - yesterday_max
        if abs(diff_yesterday) == 0:
            comp_summary = t("weather_comp_today_same")
        elif diff_yesterday > 0:
            comp_summary = t("weather_comp_today_warmer", diff=diff_yesterday)
        else:
            comp_summary = t("weather_comp_today_cooler", diff=abs(diff_yesterday))

        y_start = yesterday_d_idx * 24
        y_end = y_start + 24
        y_h_hums = h_hums[y_start:y_end] if (has_yesterday and len(h_hums) >= y_end) else []
        y_h_vis = h_vis[y_start:y_end] if (has_yesterday and len(h_vis) >= y_end) else []
        y_h_press = h_press[y_start:y_end] if (has_yesterday and len(h_press) >= y_end) else []

        yesterday_uv_max = round(float(d_uv_maxs[yesterday_d_idx]), 1) if (has_yesterday and len(d_uv_maxs) > yesterday_d_idx) else round(float(uv_index), 1)
        yesterday_wind_max = round(float(d_wind_maxs[yesterday_d_idx]), 1) if (has_yesterday and len(d_wind_maxs) > yesterday_d_idx) else wind
        yesterday_gust_max = round(float(d_gust_maxs[yesterday_d_idx]), 1) if (has_yesterday and len(d_gust_maxs) > yesterday_d_idx) else max_gust
        yesterday_precip_sum = round(float(d_precip_sums[yesterday_d_idx]), 1) if (has_yesterday and len(d_precip_sums) > yesterday_d_idx) else 0.0
        yesterday_min_hum = min(y_h_hums) if y_h_hums else humidity
        yesterday_max_hum = max(y_h_hums) if y_h_hums else humidity
        yesterday_avg_hum = round(sum(y_h_hums)/len(y_h_hums)) if y_h_hums else humidity
        yesterday_min_vis = round(min(y_h_vis) / 1000.0, 1) if y_h_vis else vis_km
        yesterday_max_vis = round(max(y_h_vis) / 1000.0, 1) if y_h_vis else vis_km
        yesterday_min_press = round(min(y_h_press) * 0.750062) if y_h_press else press_mm
        yesterday_max_press = round(max(y_h_press) * 0.750062) if y_h_press else press_mm
        yesterday_avg_press = round(sum(y_h_press)/len(y_h_press) * 0.750062) if y_h_press else press_mm

        yesterday_comp = {
            "summary": comp_summary,
            "diff_max": diff_yesterday,
            "today_min": today_min,
            "today_max": today_max,
            "yesterday_min": yesterday_min,
            "yesterday_max": yesterday_max,
            "yesterday_uv_max": yesterday_uv_max,
            "yesterday_wind_max": yesterday_wind_max,
            "yesterday_gust_max": yesterday_gust_max,
            "yesterday_precip_sum": yesterday_precip_sum,
            "yesterday_min_humidity": yesterday_min_hum,
            "yesterday_max_humidity": yesterday_max_hum,
            "yesterday_avg_humidity": yesterday_avg_hum,
            "yesterday_min_visibility_km": yesterday_min_vis,
            "yesterday_max_visibility_km": yesterday_max_vis,
            "yesterday_min_pressure_mm": yesterday_min_press,
            "yesterday_max_pressure_mm": yesterday_max_press,
            "yesterday_avg_pressure_mm": yesterday_avg_press,
        }

        daily_list = []
        overall_min = 999
        overall_max = -999
        days_detailed = []

        for i in range(today_d_idx, len(d_times)):
            day_offset = i - today_d_idx
            try:
                dt = datetime.fromisoformat(d_times[i])
                w_idx = dt.weekday()
                lbl = t("weather_today") if day_offset == 0 else get_weekday_name(w_idx, lang=lang)
            except Exception:
                w_idx = (datetime.now().weekday() + day_offset) % 7
                lbl = f"Day {day_offset + 1}"
                dt = datetime.now()

            code_i = d_codes[i] if i < len(d_codes) else w_code
            w_inf_i = WMO_INFO.get(code_i, WMO_INFO[0])
            icon_i = w_inf_i["icon_day"]

            t_min_i = round(d_mins[i]) if i < len(d_mins) else temp
            t_max_i = round(d_maxs[i]) if i < len(d_maxs) else temp
            app_min_i = round(d_apps_min[i]) if i < len(d_apps_min) else t_min_i
            app_max_i = round(d_apps_max[i]) if i < len(d_apps_max) else t_max_i
            p_sum_i = round(float(d_precip_sums[i]), 1) if i < len(d_precip_sums) else 0.0
            p_prob_i = round(float(d_precip_probs[i])) if i < len(d_precip_probs) else 0

            overall_min = min(overall_min, t_min_i)
            overall_max = max(overall_max, t_max_i)

            daily_list.append({
                "day": lbl,
                "weekday_idx": w_idx,
                "min": t_min_i,
                "max": t_max_i,
                "t_min": t_min_i,
                "t_max": t_max_i,
                "code": code_i,
                "icon_name": icon_i,
                "icon_file": os.path.join(ICONS_DIR, icon_i)
            })

            start_h = i * 24
            end_h = start_h + 24
            h24_temps = [round(x) for x in h_temps[start_h:end_h]] if len(h_temps) >= end_h else [temp] * 24
            h24_apps = [round(x) for x in h_apps[start_h:end_h]] if len(h_apps) >= end_h else h24_temps
            h24_probs = [round(x) for x in h_probs[start_h:end_h]] if len(h_probs) >= end_h else [0] * 24
            h24_precips = [round(float(x), 1) for x in h_precips[start_h:end_h]] if len(h_precips) >= end_h else [0.0] * 24
            h24_codes = h_codes[start_h:end_h] if len(h_codes) >= end_h else [code_i] * 24
            h24_is_days = h_is_days[start_h:end_h] if len(h_is_days) >= end_h else [1] * 24

            h24_winds = [round(float(x), 1) for x in h_winds[start_h:end_h]] if len(h_winds) >= end_h else [wind] * 24
            h24_wind_dirs = [round(x) for x in h_wind_dirs[start_h:end_h]] if len(h_wind_dirs) >= end_h else [wind_dir] * 24
            h24_gusts = [round(float(x), 1) for x in h_gusts[start_h:end_h]] if len(h_gusts) >= end_h else h24_winds
            h24_uvs = [round(float(x), 1) for x in h_uvs[start_h:end_h]] if len(h_uvs) >= end_h else [0.0] * 24
            h24_hums = [round(x) for x in h_hums[start_h:end_h]] if len(h_hums) >= end_h else [humidity] * 24
            h24_dews = [round(x) for x in h_dews[start_h:end_h]] if len(h_dews) >= end_h else [dew_point] * 24
            h24_vis_km = [round(float(x) / 1000.0, 1) for x in h_vis[start_h:end_h]] if len(h_vis) >= end_h else [vis_km] * 24
            h24_press_mm = [round(float(x) * 0.750062) for x in h_press[start_h:end_h]] if len(h_press) >= end_h else [press_mm] * 24
            h24_press_hpa = [round(float(x)) for x in h_press[start_h:end_h]] if len(h_press) >= end_h else [round(press_hpa)] * 24

            day_uv_max = round(float(d_uv_maxs[i]), 1) if i < len(d_uv_maxs) else (max(h24_uvs) if h24_uvs else uv_index)
            day_wind_max = round(float(d_wind_maxs[i]), 1) if i < len(d_wind_maxs) else (max(h24_winds) if h24_winds else wind)
            day_gust_max = round(float(d_gust_maxs[i]), 1) if i < len(d_gust_maxs) else (max(h24_gusts) if h24_gusts else day_wind_max)
            day_wind_dir = round(float(d_wind_dirs[i])) if i < len(d_wind_dirs) else wind_dir
            day_wind_cardinal, day_wind_desc = get_wind_direction_info(day_wind_dir, lang=lang)
            day_min_hum = min(h24_hums) if h24_hums else humidity
            day_max_hum = max(h24_hums) if h24_hums else humidity
            day_min_vis = min(h24_vis_km) if h24_vis_km else vis_km
            day_max_vis = max(h24_vis_km) if h24_vis_km else vis_km
            day_min_press = min(h24_press_mm) if h24_press_mm else press_mm
            day_max_press = max(h24_press_mm) if h24_press_mm else press_mm

            cur_hour_idx = datetime.now().hour if day_offset == 0 else -1

            w_letters = WEEKDAY_LETTERS.get(lang, WEEKDAY_LETTERS["en"])
            w_letter = w_letters[w_idx % 7]
            full_date_str = format_full_date(dt, lang)

            day_item_live = {
                "code": code_i,
                "min": t_min_i,
                "max": t_max_i,
                "apparent_min": app_min_i,
                "apparent_max": app_max_i,
                "temp": temp,
                "humidity": humidity,
                "wind_speed": wind,
                "feels_like": feels_like,
                "precip_prob_max": p_prob_i
            }
            day_summary = get_smart_day_summary(day_item_live, lang=lang, is_today=(day_offset == 0))

            days_detailed.append({
                "day_index": day_offset,
                "date_str": d_times[i],
                "day_num": dt.day,
                "weekday_letter": w_letter,
                "weekday_short": get_weekday_name(w_idx, lang=lang),
                "day": get_weekday_name(w_idx, lang=lang),
                "day_name": get_weekday_name(w_idx, lang=lang),
                "full_date": full_date_str,
                "min": t_min_i,
                "max": t_max_i,
                "t_min": t_min_i,
                "t_max": t_max_i,
                "apparent_min": app_min_i,
                "apparent_max": app_max_i,
                "code": code_i,
                "icon_name": icon_i,
                "icon_file": os.path.join(ICONS_DIR, icon_i),
                "precip_sum": p_sum_i,
                "precip_prob_max": p_prob_i,
                "is_today": (day_offset == 0),
                "cur_hour": cur_hour_idx,
                "hourly_temps": h24_temps,
                "hourly_apparent": h24_apps,
                "hourly_probs": h24_probs,
                "hourly_precips": h24_precips,
                "hourly_codes": h24_codes,
                "hourly_is_days": h24_is_days,
                "hourly_winds": h24_winds,
                "hourly_wind_dirs": h24_wind_dirs,
                "hourly_gusts": h24_gusts,
                "hourly_uvs": h24_uvs,
                "hourly_hums": h24_hums,
                "hourly_dews": h24_dews,
                "hourly_vis_km": h24_vis_km,
                "hourly_press_mm": h24_press_mm,
                "hourly_press_hpa": h24_press_hpa,
                "uv_max": day_uv_max,
                "wind_max": day_wind_max,
                "gust_max": day_gust_max,
                "dominant_wind_dir": day_wind_dir,
                "dominant_wind_cardinal": day_wind_cardinal,
                "dominant_wind_desc": day_wind_desc,
                "min_humidity": day_min_hum,
                "max_humidity": day_max_hum,
                "min_visibility_km": day_min_vis,
                "max_visibility_km": day_max_vis,
                "min_pressure_mm": day_min_press,
                "max_pressure_mm": day_max_press,
                "summary": day_summary
            })

        if overall_min >= overall_max:
            overall_min = temp - 5
            overall_max = temp + 5

        if is_day and w_code in (0, 1):
            summary = t("weather_summary_clear_day", gust=max_gust)
        elif not is_day and w_code in (0, 1):
            summary = t("weather_summary_clear_night", gust=max_gust)
        else:
            summary = t("weather_summary_generic", gust=max_gust, condition=cond_text)

        weather_dict = {
            "city_name": city_name,
            "country": country,
            "lat": lat,
            "lon": lon,
            "temp": temp,
            "feels_like": feels_like,
            "feels_like_desc": t("weather_feels_balanced"),
            "avg_diff_str": avg_diff_str,
            "avg_norm_max": avg_norm_max,
            "avg_desc": avg_desc,
            "humidity": humidity,
            "dew_point": dew_point,
            "wind_speed": wind,
            "wind_gusts": max_gust,
            "wind_direction": wind_dir,
            "wind_cardinal": wind_cardinal,
            "wind_desc": wind_desc,
            "pressure_mm": press_mm,
            "pressure_desc": pressure_desc,
            "uv_index": uv_index,
            "uv_level": uv_level,
            "uv_desc": uv_desc,
            "visibility_km": vis_km,
            "visibility_desc": t("weather_visibility_clear"),
            "precipitation": precipitation,
            "precipitation_sum": precip_sum,
            "precip_desc": precip_desc,
            "sunrise_str": sunrise_str,
            "sunset_str": sunset_str,
            "is_day": is_day,
            "weather_code": w_code,
            "condition_text": cond_text,
            "temp_min": t_min,
            "temp_max": t_max,
            "grad_type": grad_type,
            "time_of_day": time_of_day,
            "grad_class": grad_class,
            "bg_class": bg_class,
            "icon_name": icon_name,
            "icon_file": os.path.join(ICONS_DIR, icon_name),
            "summary": summary,
            "overall_min": overall_min,
            "overall_max": overall_max,
            "hourly": hourly_list,
            "daily": daily_list,
            "days_detailed": days_detailed,
            "yesterday_comp": yesterday_comp,
            "climate_averages": climate_averages,
            "solar_details": solar_details,
            "detailed_moon": detailed_moon,
            "weather_model": model_name,
            "cell_selection": "land",
            "elevation": float(city_info["elevation"]) if city_info.get("elevation") is not None else None,
            "precip_nowcast": precip_nowcast,
            "minutely_15": minutely_15,
            "forecast_date": city_today_str,
            "utc_offset_seconds": utc_offset,
            "timezone": raw.get("timezone", ""),
            "cached_at": time.time()
        }

        return weather_dict
