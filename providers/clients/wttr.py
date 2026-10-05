"""
Сетевой клиент для резервного погодного сервиса wttr.in.
Используется как fallback при недоступности основных метеорологических API.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from i18n import get_current_language, t
from logger import get_logger
from providers.clients.base import BaseWeatherClient
from services.astronomy import (
    calculate_annual_solar_table,
    calculate_detailed_moon,
    calculate_moon_phase,
    calculate_solar_details,
)

logger = get_logger("weather.wttr")


class WttrClient(BaseWeatherClient):
    """Клиент для резервного сервиса погоды wttr.in."""

    def fetch_forecast(
        self,
        lat: float,
        lon: float,
        city_info: dict[str, Any] | None = None,
        timeout: float = 3.5,
        **kwargs: Any
    ) -> dict[str, Any] | None:
        from providers.weather import (
            ICONS_DIR,
            WMO_INFO,
            calculate_climate_averages,
            determine_solar_time_of_day,
            ensure_days_detailed,
            get_condition_text,
            get_geo_timezone_offset_seconds,
            get_weekday_name,
            get_wind_direction_info,
        )

        if city_info is None:
            city_info = {}

        try:
            url = f"https://wttr.in/{lat:.4f},{lon:.4f}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.88.1"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.debug(f"wttr.in HTTP error for {lat},{lon}: {e}")
            return None

        curr = data.get("current_condition", [{}])[0]
        weather_days = data.get("weather", [])
        if not curr or not weather_days:
            return None

        lang = get_current_language()
        is_ru = (lang == "ru")
        utc_offset = get_geo_timezone_offset_seconds(lat, lon)
        utc_now = datetime.now(timezone.utc)
        city_now = utc_now + timedelta(seconds=utc_offset)
        city_today_str = city_now.strftime("%Y-%m-%d")

        temp = round(float(curr.get("temp_C", 0)))
        feels_like = round(float(curr.get("FeelsLikeC", temp)))
        humidity = round(float(curr.get("humidity", 50)))
        wind = round(float(curr.get("windspeedKmph", 0)) / 3.6, 1)
        wind_dir = round(float(curr.get("winddirDegree", 0)))
        press_mm = round(float(curr.get("pressure", 1013)) * 0.750062)
        dew_point = round(temp - ((100 - max(0, min(100, humidity))) / 5))

        solar_details = calculate_solar_details(lat, lon, city_now.date(), utc_offset / 3600.0, is_ru=is_ru)
        solar_details["annual_table"] = calculate_annual_solar_table(lat, lon, utc_offset / 3600.0, is_ru=is_ru)
        detailed_moon = calculate_detailed_moon(lat, lon, city_now, utc_offset / 3600.0, is_ru=is_ru)
        sunrise_str = solar_details.get("sunrise", "06:00")
        sunset_str = solar_details.get("sunset", "19:00")

        try:
            sr_h, sr_m = [int(x) for x in sunrise_str.split(":")]
            ss_h, ss_m = [int(x) for x in sunset_str.split(":")]
            curr_min = city_now.hour * 60 + city_now.minute
            is_day = 1 if (sr_h * 60 + sr_m <= curr_min < ss_h * 60 + ss_m) else 0
        except Exception:
            is_day = 1 if (6 <= city_now.hour < 20) else 0

        wwo_code = int(curr.get("weatherCode", 113))
        if wwo_code == 113:
            w_code = 0
        elif wwo_code == 116:
            w_code = 2
        elif wwo_code in (119, 122):
            w_code = 3
        elif wwo_code in (143, 248, 260):
            w_code = 45
        elif wwo_code in (176, 263, 266, 293, 296):
            w_code = 61
        elif wwo_code in (299, 302, 305, 308):
            w_code = 63
        elif wwo_code in (179, 182, 185, 281, 284, 311, 314, 317, 350):
            w_code = 68
        elif wwo_code in (227, 230, 323, 326, 329, 332, 335, 338):
            w_code = 73
        elif wwo_code in (200, 386, 389, 392, 395):
            w_code = 95
        else:
            w_code = 1

        w_info = WMO_INFO.get(w_code, WMO_INFO[0])
        cond_text = get_condition_text(w_code, lang=lang, is_day=(is_day == 1))
        icon_name = w_info["icon_day"] if is_day else w_info["icon_night"]
        grad_type = w_info["grad"]
        tod, _ = determine_solar_time_of_day(lat, lon)
        time_of_day = tod
        grad_class = f"weather-grad-{grad_type}-{time_of_day}"
        bg_class = f"weather-bg-{grad_type}-{time_of_day}"

        today_weather = weather_days[0]
        t_min = round(float(today_weather.get("mintempC", temp - 4)))
        t_max = round(float(today_weather.get("maxtempC", temp + 4)))
        precipitation = round(float(curr.get("precipMM", 0.0)), 1)
        precip_sum = round(float(today_weather.get("totalSnow_cm", 0.0)) * 10 + precipitation, 1)

        daily_list = []
        overall_min = 999
        overall_max = -999

        for idx, d_item in enumerate(weather_days):
            d_min = round(float(d_item.get("mintempC", temp)))
            d_max = round(float(d_item.get("maxtempC", temp)))
            overall_min = min(overall_min, d_min)
            overall_max = max(overall_max, d_max)

            d_date_str = d_item.get("date", "")
            try:
                dt_d = datetime.fromisoformat(d_date_str)
                w_idx = dt_d.weekday()
                lbl = t("weather_today") if idx == 0 else get_weekday_name(w_idx, lang=lang)
            except Exception:
                w_idx = (city_now.weekday() + idx) % 7
                lbl = t("weather_today") if idx == 0 else get_weekday_name(w_idx, lang=lang)

            d_h = d_item.get("hourly", [{}])
            mid_h = d_h[len(d_h) // 2] if d_h else {}
            mid_code = int(mid_h.get("weatherCode", 113))
            d_code = 0 if mid_code == 113 else (2 if mid_code == 116 else (3 if mid_code in (119, 122) else (61 if mid_code in (176, 293, 296) else (73 if mid_code in (227, 323, 326) else 1))))
            d_inf = WMO_INFO.get(d_code, WMO_INFO[0])

            daily_list.append({
                "day": lbl,
                "weekday_idx": w_idx,
                "min": d_min,
                "max": d_max,
                "code": d_code,
                "icon_name": d_inf["icon_day"],
                "icon_file": os.path.join(ICONS_DIR, d_inf["icon_day"]),
            })

        hourly_list = []
        for idx, h in enumerate(today_weather.get("hourly", [])):
            h_time_raw = int(h.get("time", "0"))
            h_hr = h_time_raw // 100
            h_lbl = t("weather_now") if idx == 0 else f"{h_hr:02d}"
            h_temp = round(float(h.get("tempC", temp)))
            h_is_d = 1 if (sr_h * 60 <= h_hr * 60 < ss_h * 60) else 0
            h_wwo = int(h.get("weatherCode", 113))
            h_c = 0 if h_wwo == 113 else (2 if h_wwo == 116 else (3 if h_wwo in (119, 122) else 1))
            h_inf = WMO_INFO.get(h_c, WMO_INFO[0])
            h_ic = h_inf["icon_day"] if h_is_d else h_inf["icon_night"]
            hourly_list.append({
                "time": h_lbl,
                "hour_num": h_hr,
                "is_now": (idx == 0),
                "temp": h_temp,
                "code": h_c,
                "icon_name": h_ic,
                "icon_file": os.path.join(ICONS_DIR, h_ic),
            })

        climate_averages = calculate_climate_averages(lat, lon, t_max, t_min, is_ru=is_ru)
        avg_diff_str = climate_averages.get("temp_diff_str_short", "0°")
        avg_norm_max = climate_averages.get("temp_avg_max", t_max)
        diff_avg = climate_averages.get("temp_diff", 0)
        if diff_avg > 0:
            avg_desc = f"выше средней макс. температуры {avg_norm_max}° сегодня." if is_ru else f"above average high of {avg_norm_max}° today."
        elif diff_avg < 0:
            avg_desc = f"ниже средней макс. температуры {avg_norm_max}° сегодня." if is_ru else f"below average high of {avg_norm_max}° today."
        else:
            avg_desc = f"соответствует средней макс. температуре {avg_norm_max}° сегодня." if is_ru else f"matches average high of {avg_norm_max}° today."

        wind_cardinal, wind_desc = get_wind_direction_info(wind_dir, lang=lang)
        max_gust = round(float(curr.get("windspeedKmph", 0)) * 1.3 / 3.6, 1)

        city_name = city_info.get("name_ru" if is_ru else "name_en", city_info.get("name_ru", ""))
        country = city_info.get("country_ru" if is_ru else "country_en", "")

        yesterday_comp = {
            "summary": t("weather_comp_today_same"),
            "diff_max": 0,
            "today_min": t_min,
            "today_max": t_max,
            "yesterday_min": t_min,
            "yesterday_max": t_max,
            "yesterday_uv_max": 1.0,
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

        if is_day and w_code in (0, 1):
            summary = t("weather_summary_clear_day", gust=round(max_gust))
        elif not is_day and w_code in (0, 1):
            summary = t("weather_summary_clear_night", gust=round(max_gust))
        else:
            summary = t("weather_summary_generic", gust=round(max_gust), condition=cond_text)

        w_dict = {
            "city_name": city_name,
            "country": country,
            "lat": lat,
            "lon": lon,
            "temp": temp,
            "feels_like": feels_like,
            "feels_like_desc": "Похоже на фактическую температуру.",
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
            "pressure_desc": "Нормальное давление.",
            "uv_index": 1.0,
            "uv_level": "Низкий",
            "uv_desc": "Защита от солнца не требуется.",
            "visibility_km": round(float(curr.get("visibility", 10))),
            "visibility_desc": "Хорошая видимость.",
            "precipitation": precipitation,
            "precipitation_sum": precip_sum,
            "precip_desc": "Осадков не ожидается.",
            "sunrise_str": sunrise_str,
            "sunset_str": sunset_str,
            "moon_phase": calculate_moon_phase(),
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
            "days_detailed": [],
            "yesterday_comp": yesterday_comp,
            "climate_averages": climate_averages,
            "solar_details": solar_details,
            "detailed_moon": detailed_moon,
            "forecast_date": city_today_str,
            "utc_offset_seconds": utc_offset,
            "timezone": "auto",
            "cached_at": time.time(),
        }
        ensure_days_detailed(w_dict, lang=lang)
        return w_dict
