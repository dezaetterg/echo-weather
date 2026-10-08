"""
Клиент для взаимодействия с API Норвежского метеорологического института (MET Norway).
Высокоточный официальный источник для Европейской и Скандинавской метеорологии.
"""

from __future__ import annotations

import json
import math
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from i18n import get_current_language, t
from logger import get_logger
from providers.clients.base import BaseWeatherClient
from services.astronomy import calculate_annual_solar_table, calculate_detailed_moon, calculate_solar_details, compute_solar_uv

logger = get_logger("weather.met_norway")


class MetNorwayClient(BaseWeatherClient):
    """Сетевой клиент для официального метеорологического сервиса MET Norway."""

    def fetch_forecast(
        self,
        lat: float,
        lon: float,
        city_info: dict[str, Any] | None = None,
        timeout: float = 4.0,
        **kwargs: Any
    ) -> dict[str, Any] | None:
        if city_info is None:
            city_info = {}

        try:
            url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat:.4f}&lon={lon:.4f}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "EchoWeatherApp/1.0 (https://github.com/echo-weather; contact: local)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.debug(f"MET Norway HTTP request error for {lat},{lon}: {e}")
            return None

        return self.parse_forecast_data(data, lat, lon, city_info=city_info)

    def parse_forecast_data(
        self,
        data: dict[str, Any],
        lat: float,
        lon: float,
        city_info: dict[str, Any] | None = None,
        lang: str | None = None,
    ) -> dict[str, Any] | None:
        from providers.weather import (
            ICONS_DIR,
            WEEKDAY_LETTERS,
            WMO_INFO,
            calculate_climate_averages,
            format_full_date,
            get_condition_text,
            get_geo_timezone_offset_seconds,
            get_smart_day_summary,
            get_weekday_name,
            get_wind_direction_info,
            met_symbol_to_wmo,
        )

        if city_info is None:
            city_info = {}
        if lang is None:
            lang = get_current_language()

        timeseries = data.get("properties", {}).get("timeseries", [])
        if not timeseries:
            return None

        utc_offset = get_geo_timezone_offset_seconds(lat, lon)
        utc_now = datetime.now(timezone.utc)
        city_now = utc_now + timedelta(seconds=utc_offset)
        city_today_str = city_now.strftime("%Y-%m-%d")

        by_date: dict[str, list[dict[str, Any]]] = {}
        for entry in timeseries:
            time_iso = entry.get("time", "")
            try:
                dt_utc = datetime.fromisoformat(time_iso.replace("Z", "+00:00"))
                dt_local = dt_utc + timedelta(seconds=utc_offset)
                date_key = dt_local.strftime("%Y-%m-%d")
                if date_key not in by_date:
                    by_date[date_key] = []
                by_date[date_key].append({
                    "dt_local": dt_local,
                    "instant": entry.get("data", {}).get("instant", {}).get("details", {}),
                    "next_1h": entry.get("data", {}).get("next_1_hours", {}),
                    "next_6h": entry.get("data", {}).get("next_6_hours", {}),
                    "next_12h": entry.get("data", {}).get("next_12_hours", {}),
                })
            except Exception:
                continue

        first_entry = timeseries[0]
        cur_instant = first_entry.get("data", {}).get("instant", {}).get("details", {})
        cur_next1 = first_entry.get("data", {}).get("next_1_hours", {})
        cur_next6 = first_entry.get("data", {}).get("next_6_hours", {})
        cur_symbol = (
            cur_next1.get("summary", {}).get("symbol_code")
            or cur_next6.get("summary", {}).get("symbol_code")
            or "clearsky_day"
        )
        w_code, is_day = met_symbol_to_wmo(cur_symbol)

        temp = round(cur_instant.get("air_temperature", 0))
        wind = round(cur_instant.get("wind_speed", 0.0), 1)
        max_gust = round(cur_instant.get("wind_speed_of_gust", wind * 1.5))
        wind_dir = round(cur_instant.get("wind_from_direction", 0))
        humidity = round(cur_instant.get("relative_humidity", 50))
        dew_point = round(cur_instant.get("dew_point_temperature", temp - 3))
        press_hpa = cur_instant.get("air_pressure_at_sea_level", 1013.25)
        press_mm = round(press_hpa * 0.750062)
        curr_cloud = float(cur_instant.get("cloud_area_fraction", 0.0))

        solar_details = calculate_solar_details(lat, lon, city_now.date(), utc_offset / 3600.0, lang=lang)
        solar_details["annual_table"] = calculate_annual_solar_table(lat, lon, utc_offset / 3600.0, lang=lang)
        sr_str = solar_details.get("sunrise", "06:00")
        ss_str = solar_details.get("sunset", "19:00")
        sunrise_str = sr_str
        sunset_str = ss_str

        try:
            sr_h, sr_m = [int(x) for x in sr_str.split(":")]
            ss_h, ss_m = [int(x) for x in ss_str.split(":")]
            cur_min = city_now.hour * 60 + city_now.minute
            sr_min = sr_h * 60 + sr_m
            ss_min = ss_h * 60 + ss_m
            is_day = 1 if (sr_min <= cur_min < ss_min) else 0
        except Exception:
            pass

        lang = get_current_language()
        is_ru = (lang == "ru")

        feels_like = round(temp - (0.2 * (wind - 2.0)) if wind > 2.0 else temp)
        curr_uv = compute_solar_uv(lat, city_now, cloud_pct=curr_cloud)

        precipitation = round(cur_next1.get("details", {}).get("precipitation_amount", 0.0), 1)

        dates_sorted = sorted(by_date.keys())
        today_entries = by_date.get(city_today_str, [])
        if not today_entries and dates_sorted:
            today_entries = by_date[dates_sorted[0]]

        t_min = min((round(e["instant"].get("air_temperature", temp)) for e in today_entries), default=temp)
        t_max = max((round(e["instant"].get("air_temperature", temp)) for e in today_entries), default=temp)

        hourly_list = []
        now_entry_found = False
        for entry in timeseries[:48]:
            try:
                t_utc = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
                t_local = t_utc + timedelta(seconds=utc_offset)
                h_instant = entry.get("data", {}).get("instant", {}).get("details", {})
                h_next1 = entry.get("data", {}).get("next_1_hours", {})
                h_next6 = entry.get("data", {}).get("next_6_hours", {})
                h_sym = (
                    h_next1.get("summary", {}).get("symbol_code")
                    or h_next6.get("summary", {}).get("symbol_code")
                    or "clearsky_day"
                )
                h_code, h_is_day = met_symbol_to_wmo(h_sym)
                h_temp = round(h_instant.get("air_temperature", temp))
                h_precip = round(h_next1.get("details", {}).get("precipitation_amount", 0.0), 1)
                h_prob = round(h_next1.get("details", {}).get("probability_of_precipitation", 0.0))

                is_cur = False
                if not now_entry_found and (t_local.date() == city_now.date() and t_local.hour == city_now.hour):
                    is_cur = True
                    now_entry_found = True

                w_info_h = WMO_INFO.get(h_code, WMO_INFO[0])
                icon_h = w_info_h["icon_day"] if h_is_day else w_info_h["icon_night"]

                lbl = t("weather_now") if is_cur else f"{t_local.hour:02d}:00"
                hourly_list.append({
                    "time": lbl,
                    "hour_num": t_local.hour,
                    "is_now": is_cur,
                    "temp": h_temp,
                    "code": h_code,
                    "icon_name": icon_h,
                    "icon_file": os.path.join(ICONS_DIR, icon_h),
                    "precip_amount": h_precip,
                    "precip_prob": h_prob,
                    "is_day": h_is_day,
                })
                if len(hourly_list) >= 25:
                    break
            except Exception:
                continue

        if hourly_list and not any(h["is_now"] for h in hourly_list):
            hourly_list[0]["is_now"] = True
            hourly_list[0]["time"] = t("weather_now")

        daily_list = []
        days_detailed = []
        overall_min = t_min
        overall_max = t_max

        w_letters = WEEKDAY_LETTERS.get(lang, WEEKDAY_LETTERS["en"])

        for d_idx, d_str in enumerate(dates_sorted[:10]):
            entries_d = by_date[d_str]
            if not entries_d:
                continue
            dt_first = entries_d[0]["dt_local"]
            w_idx = dt_first.weekday()
            is_today_day = (d_str == city_today_str)
            lbl = t("weather_today") if is_today_day else get_weekday_name(w_idx, lang=lang)

            d_temps = [e["instant"].get("air_temperature", temp) for e in entries_d]
            d_min = round(min(d_temps))
            d_max = round(max(d_temps))
            overall_min = min(overall_min, d_min)
            overall_max = max(overall_max, d_max)

            mid_idx = len(entries_d) // 2
            d_sym = (
                entries_d[mid_idx]["next_6h"].get("summary", {}).get("symbol_code")
                or entries_d[mid_idx]["next_1h"].get("summary", {}).get("symbol_code")
                or "clearsky_day"
            )
            d_code, _ = met_symbol_to_wmo(d_sym)
            w_info_d = WMO_INFO.get(d_code, WMO_INFO[0])
            d_icon = w_info_d["icon_day"]

            daily_list.append({
                "day": lbl,
                "weekday_idx": w_idx,
                "min": d_min,
                "max": d_max,
                "t_min": d_min,
                "t_max": d_max,
                "code": d_code,
                "icon_name": d_icon,
                "icon_file": os.path.join(ICONS_DIR, d_icon),
            })

            h24_temps = [d_min] * 24
            h24_probs = [0] * 24
            h24_precips = [0.0] * 24
            h24_winds = [wind] * 24
            h24_gusts = [max_gust] * 24
            h24_wind_dirs = [wind_dir] * 24
            h24_hums = [humidity] * 24
            h24_dews = [dew_point] * 24
            h24_press_mm = [press_mm] * 24
            h24_press_hpa = [round(press_hpa)] * 24
            h24_codes = [d_code] * 24
            h24_is_days = [1] * 24
            h24_clouds = [curr_cloud] * 24

            for e in entries_d:
                hr = e["dt_local"].hour
                if 0 <= hr < 24:
                    inst = e["instant"]
                    nxt1 = e["next_1h"]
                    h24_temps[hr] = round(inst.get("air_temperature", d_min))
                    h24_winds[hr] = round(inst.get("wind_speed", wind), 1)
                    h24_gusts[hr] = round(inst.get("wind_speed_of_gust", h24_winds[hr] * 1.5), 1)
                    h24_wind_dirs[hr] = round(inst.get("wind_from_direction", wind_dir))
                    h24_hums[hr] = round(inst.get("relative_humidity", humidity))
                    h24_dews[hr] = round(inst.get("dew_point_temperature", dew_point))
                    p_hpa = inst.get("air_pressure_at_sea_level", press_hpa)
                    h24_press_hpa[hr] = round(p_hpa)
                    h24_press_mm[hr] = round(p_hpa * 0.750062)
                    h24_clouds[hr] = float(inst.get("cloud_area_fraction", curr_cloud))

                    sym_hr = nxt1.get("summary", {}).get("symbol_code") or d_sym
                    c_hr, is_day_hr = met_symbol_to_wmo(sym_hr)
                    h24_codes[hr] = c_hr
                    h24_is_days[hr] = is_day_hr
                    h24_precips[hr] = round(nxt1.get("details", {}).get("precipitation_amount", 0.0), 1)
                    h24_probs[hr] = round(nxt1.get("details", {}).get("probability_of_precipitation", 0.0))

            for hr in range(24):
                if h24_temps[hr] == d_min and hr > 0 and h24_temps[hr - 1] != d_min:
                    h24_temps[hr] = h24_temps[hr - 1]
                    h24_winds[hr] = h24_winds[hr - 1]
                    h24_gusts[hr] = h24_gusts[hr - 1]
                    h24_hums[hr] = h24_hums[hr - 1]
                    h24_dews[hr] = h24_dews[hr - 1]
                    h24_press_mm[hr] = h24_press_mm[hr - 1]
                    h24_press_hpa[hr] = h24_press_hpa[hr - 1]

            h24_uvs = []
            for hr in range(24):
                dt_h_d = datetime(dt_first.year, dt_first.month, dt_first.day, hr, 0)
                uv_h = compute_solar_uv(lat, dt_h_d, cloud_pct=h24_clouds[hr])
                h24_uvs.append(uv_h)

            h24_vis_km = []
            for hr in range(24):
                t_h = h24_temps[hr]
                dew_h = h24_dews[hr]
                hum_h = h24_hums[hr]
                pr_h = h24_precips[hr]
                code_h = h24_codes[hr]

                dd = max(0.0, t_h - dew_h)
                if code_h in (45, 48):
                    v = 0.4 + min(1.2, dd * 0.4)
                elif pr_h > 5.0 or code_h in (65, 82, 95, 96, 99):
                    v = 2.0 + max(0.0, 2.0 - pr_h * 0.1)
                elif pr_h > 1.0 or code_h in (63, 73, 75, 81):
                    v = 4.0 + min(3.0, dd * 0.5)
                elif pr_h > 0.0 or code_h in (51, 53, 55, 61, 71, 80):
                    v = 6.0 + min(3.0, dd * 0.5)
                else:
                    if hum_h >= 95 or dd <= 0.5:
                        v = 2.5 + dd * 2.0
                    elif hum_h >= 85 or dd <= 1.5:
                        v = 5.0 + dd * 2.0
                    elif hum_h >= 75 or dd <= 3.0:
                        v = 7.5 + dd * 1.0
                    else:
                        v = 10.0 + max(0.0, (80.0 - hum_h) * 0.05)
                v = round(max(0.3, min(14.0, v)), 1)
                h24_vis_km.append(v)

            day_min_vis = min(h24_vis_km)
            day_max_vis = max(h24_vis_km)

            cardinal_d, desc_d = get_wind_direction_info(h24_wind_dirs[12], lang=lang)

            day_item_live = {
                "code": d_code,
                "min": d_min,
                "max": d_max,
                "apparent_min": d_min,
                "apparent_max": d_max,
                "temp": temp,
                "humidity": humidity,
                "wind_speed": wind,
                "feels_like": feels_like,
                "precip_prob_max": max(h24_probs),
            }
            d_summary = get_smart_day_summary(day_item_live, lang=lang, is_today=is_today_day)

            days_detailed.append({
                "day_index": d_idx,
                "date_str": d_str,
                "day_num": dt_first.day,
                "weekday_letter": w_letters[w_idx % 7],
                "weekday_short": get_weekday_name(w_idx, lang=lang),
                "day": get_weekday_name(w_idx, lang=lang),
                "day_name": get_weekday_name(w_idx, lang=lang),
                "full_date": format_full_date(dt_first, lang),
                "min": d_min,
                "max": d_max,
                "t_min": d_min,
                "t_max": d_max,
                "apparent_min": d_min,
                "apparent_max": d_max,
                "code": d_code,
                "icon_name": d_icon,
                "icon_file": os.path.join(ICONS_DIR, d_icon),
                "precip_sum": round(sum(h24_precips), 1),
                "precip_prob_max": max(h24_probs),
                "is_today": is_today_day,
                "cur_hour": city_now.hour if is_today_day else -1,
                "hourly_temps": h24_temps,
                "hourly_apparent": list(h24_temps),
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
                "uv_max": max(h24_uvs),
                "wind_max": max(h24_winds),
                "gust_max": max(h24_gusts),
                "dominant_wind_dir": h24_wind_dirs[12],
                "dominant_wind_cardinal": cardinal_d,
                "dominant_wind_desc": desc_d,
                "min_humidity": min(h24_hums),
                "max_humidity": max(h24_hums),
                "min_visibility_km": day_min_vis,
                "max_visibility_km": day_max_vis,
                "min_pressure_mm": min(h24_press_mm),
                "max_pressure_mm": max(h24_press_mm),
                "summary": d_summary,
            })

        diff_yest = 0
        comp_summary = t("weather_comp_today_same")
        yesterday_comp = {
            "summary": comp_summary,
            "diff_max": diff_yest,
            "today_min": t_min,
            "today_max": t_max,
            "yesterday_min": t_min,
            "yesterday_max": t_max,
            "yesterday_uv_max": curr_uv,
            "yesterday_wind_max": wind,
            "yesterday_gust_max": max_gust,
            "yesterday_precip_sum": 0.0,
            "yesterday_min_humidity": humidity,
            "yesterday_max_humidity": humidity,
            "yesterday_avg_humidity": humidity,
            "yesterday_min_visibility_km": 10.0,
            "yesterday_max_visibility_km": 10.0,
            "yesterday_min_pressure_mm": press_mm,
            "yesterday_max_pressure_mm": press_mm,
            "yesterday_avg_pressure_mm": press_mm,
        }

        detailed_moon = calculate_detailed_moon(lat, lon, city_now, utc_offset / 3600.0, lang=lang)

        hourly_today_for_climate = [{"temp": h["temp"]} for h in hourly_list[:24]]
        climate_averages = calculate_climate_averages(lat, lon, t_max, t_min, hourly_today=hourly_today_for_climate, lang=lang)

        w_info = WMO_INFO.get(w_code, WMO_INFO[0])
        cond_text = get_condition_text(w_code, lang=lang, is_day=(is_day == 1))
        icon_name = w_info["icon_day"] if is_day else w_info["icon_night"]
        grad_type = w_info["grad"]
        time_of_day = "day" if is_day else "night"
        grad_class = f"weather-grad-{grad_type}-{time_of_day}"
        bg_class = f"weather-bg-{grad_type}-{time_of_day}"
        wind_cardinal, wind_desc = get_wind_direction_info(wind_dir, lang=lang)

        city_name = city_info.get("name_ru" if is_ru else "name_en", city_info.get("name", "Unknown"))
        country = city_info.get("country_ru" if is_ru else "country_en", city_info.get("country", ""))

        precip_sum = round(sum(d.get("precip_sum", 0.0) for d in days_detailed[:1]), 1)

        diff_val = climate_averages.get("temp_diff_str_short") or climate_averages.get("temp_diff_str") or "0°"
        cur_vis_km = days_detailed[0]["hourly_vis_km"][city_now.hour] if (days_detailed and len(days_detailed[0].get("hourly_vis_km", [])) > city_now.hour) else 10.0

        weather_dict = {
            "city_name": city_name,
            "country": country,
            "lat": lat,
            "lon": lon,
            "temp": temp,
            "feels_like": feels_like,
            "feels_like_desc": t("weather_feels_balanced"),
            "avg_diff_str": t("weather_climate_vs_norm", diff=diff_val),
            "avg_norm_max": climate_averages.get("temp_avg_max", t_max),
            "avg_desc": climate_averages.get("summary_temp") or t("weather_climate_near_norm"),
            "humidity": humidity,
            "dew_point": dew_point,
            "wind_speed": wind,
            "wind_gusts": max_gust,
            "wind_direction": wind_dir,
            "wind_cardinal": wind_cardinal,
            "wind_desc": wind_desc,
            "pressure_mm": press_mm,
            "pressure_desc": t("weather_pressure_normal"),
            "uv_index": curr_uv,
            "uv_level": t("weather_uv_moderate"),
            "uv_desc": t("weather_uv_moderate_desc"),
            "visibility_km": cur_vis_km,
            "visibility_desc": t("weather_visibility_clear"),
            "precipitation": precipitation,
            "precipitation_sum": precip_sum,
            "precip_desc": t("weather_precip_no_expected"),
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
            "summary": t("weather_summary_clear_day", gust=round(max_gust)) if is_day else t("weather_summary_clear_night", gust=round(max_gust)),
            "overall_min": overall_min,
            "overall_max": overall_max,
            "hourly": hourly_list,
            "daily": daily_list,
            "days_detailed": days_detailed,
            "yesterday_comp": yesterday_comp,
            "climate_averages": climate_averages,
            "solar_details": solar_details,
            "detailed_moon": detailed_moon,
            "forecast_date": city_today_str,
            "utc_offset_seconds": utc_offset,
            "timezone": "auto",
            "cached_at": time.time(),
        }

        return weather_dict
