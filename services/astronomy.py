"""
Модуль небесной механики и астрономических расчетов Echo Weather.
Реализует алгоритмы NOAA для расчета положения Солнца, восходов, заходов,
сумерек, а также формулы фаз, освещенности, расстояния и восходов/заходов Луны.
"""

from __future__ import annotations

import calendar
import math
from datetime import date, datetime, timedelta, timezone

from i18n import (
    format_day_month,
    get_current_language,
    get_month_name,
    get_weekday_name,
    t,
)


def calculate_moon_phase(dt: datetime | None = None, is_ru: bool | None = None, lang: str | None = None) -> dict:
    """Вычисление базовой фазы Луны и возраста цикла."""
    target_lang = lang or (get_current_language() if is_ru is None else ('ru' if is_ru else 'en'))
    if dt is None:
        dt = datetime.now(timezone.utc)
    ref_new_moon = datetime(2024, 1, 11, 11, 57, tzinfo=timezone.utc)
    synodic_month = 29.53058867
    diff_days = (dt - ref_new_moon).total_seconds() / 86400.0
    cycles = diff_days / synodic_month
    cycle_frac = cycles - math.floor(cycles)
    age_days = cycle_frac * synodic_month
    illumination = 0.5 * (1.0 - math.cos(2 * math.pi * cycle_frac)) * 100.0
    if cycle_frac < 0.5:
        days_to_full = (0.5 - cycle_frac) * synodic_month
    else:
        days_to_full = (1.5 - cycle_frac) * synodic_month

    if cycle_frac < 0.03 or cycle_frac >= 0.97:
        phase_key = 'weather_moon_phase_new'
    elif cycle_frac < 0.22:
        phase_key = 'weather_moon_phase_waxing_crescent'
    elif cycle_frac < 0.28:
        phase_key = 'weather_moon_phase_first_quarter'
    elif cycle_frac < 0.47:
        phase_key = 'weather_moon_phase_waxing_gibbous'
    elif cycle_frac < 0.53:
        phase_key = 'weather_moon_phase_full'
    elif cycle_frac < 0.72:
        phase_key = 'weather_moon_phase_waning_gibbous'
    elif cycle_frac < 0.78:
        phase_key = 'weather_moon_phase_last_quarter'
    else:
        phase_key = 'weather_moon_phase_waning_crescent'

    phase_name = t(phase_key, lang=target_lang)
    p_ru = t(phase_key, lang='ru')
    p_en = t(phase_key, lang='en')

    return {
        'cycle_fraction': cycle_frac,
        'age_days': round(age_days, 1),
        'illumination': round(illumination),
        'days_to_full': max(0, round(days_to_full)),
        'phase_name': phase_name,
        'phase_name_ru': p_ru,
        'phase_name_en': p_en
    }


def calculate_solar_details(
    lat: float,
    lon: float,
    dt: date | None = None,
    utc_offset_hours: float = 0.0,
    is_ru: bool | None = None,
    lang: str | None = None,
) -> dict:
    """Расчет моментов первого света, восхода, захода, последнего света и высоты Солнца по NOAA."""
    if dt is None:
        dt = date.today()

    n_day = dt.timetuple().tm_yday
    gamma = 2.0 * math.pi / 365.0 * (n_day - 1 + 0.5)
    eqtime = (
        229.18 * (
            0.000075
            + 0.001868 * math.cos(gamma)
            - 0.032077 * math.sin(gamma)
            - 0.014615 * math.cos(2 * gamma)
            - 0.040849 * math.sin(2 * gamma)
        )
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )

    time_offset = eqtime + 4.0 * lon - 60.0 * utc_offset_hours
    t_noon_min = 720.0 - time_offset
    lat_rad = math.radians(lat)

    def get_ha_for_elevation(elev_deg: float) -> float | None:
        elev_rad = math.radians(elev_deg)
        denom = math.cos(lat_rad) * math.cos(decl)
        if abs(denom) < 1e-6:
            return 0.0
        cos_ha = (math.sin(elev_rad) - math.sin(lat_rad) * math.sin(decl)) / denom
        if cos_ha > 1.0 or cos_ha < -1.0:
            return None
        return math.degrees(math.acos(cos_ha))

    ha_sun = get_ha_for_elevation(-0.833)
    ha_twilight = get_ha_for_elevation(-6.0)

    if ha_sun is not None:
        sunrise_min = t_noon_min - ha_sun * 4.0
        sunset_min = t_noon_min + ha_sun * 4.0
        daylight_min = max(0.0, sunset_min - sunrise_min)
    else:
        if math.sin(lat_rad) * math.sin(decl) > 0:
            sunrise_min, sunset_min = 0.0, 1440.0
            daylight_min = 1440.0
        else:
            sunrise_min, sunset_min = 720.0, 720.0
            daylight_min = 0.0

    if ha_twilight is not None:
        dawn_min = t_noon_min - ha_twilight * 4.0
        dusk_min = t_noon_min + ha_twilight * 4.0
    else:
        dawn_min = sunrise_min
        dusk_min = sunset_min

    def fmt_time(m: float) -> str:
        m_mod = m % 1440.0
        h = int(m_mod // 60)
        mins = int(round(m_mod % 60))
        if mins == 60:
            mins = 0
            h = (h + 1) % 24
        return f'{h:02d}:{mins:02d}'

    dl_h = int(daylight_min // 60)
    dl_m = int(round(daylight_min % 60))
    target_lang = lang or (get_current_language() if is_ru is None else ('ru' if is_ru else 'en'))
    daylight_str = t('weather_sun_daylight_val', h=dl_h, m=dl_m, lang=target_lang)

    curve_points = []
    for step in range(97):
        h_frac = step * 0.25
        m_curr = h_frac * 60.0
        ha = (m_curr - t_noon_min) * 0.25
        sin_elev = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.cos(math.radians(ha))
        sin_elev = max(-1.0, min(1.0, sin_elev))
        elev = math.degrees(math.asin(sin_elev))
        curve_points.append((round(h_frac, 2), round(elev, 2)))

    return {
        'first_light': fmt_time(dawn_min),
        'sunrise': fmt_time(sunrise_min),
        'sunset': fmt_time(sunset_min),
        'last_light': fmt_time(dusk_min),
        'daylight_min': daylight_min,
        'daylight_str': daylight_str,
        't_noon_frac': round(t_noon_min / 60.0, 3),
        't_dawn_frac': round(dawn_min / 60.0, 3),
        't_sunrise_frac': round(sunrise_min / 60.0, 3),
        't_sunset_frac': round(sunset_min / 60.0, 3),
        't_dusk_frac': round(dusk_min / 60.0, 3),
        'curve_points': curve_points
    }


def calculate_annual_solar_table(
    lat: float,
    lon: float,
    utc_offset_hours: float = 0.0,
    is_ru: bool | None = None,
    lang: str | None = None,
) -> dict:
    """Расчет годовой таблицы восходов и заходов по месяцам, а также дня солнцестояния."""
    target_lang = lang or (get_current_language() if is_ru is None else ('ru' if is_ru else 'en'))
    month_names = [get_month_name(m, short=True, lang=target_lang) for m in range(1, 13)]

    cur_month = datetime.now().month
    year = datetime.now().year
    lat_rad = math.radians(lat)

    monthly_rows = []

    for m in range(1, 13):
        num_days = calendar.monthrange(year, m)[1]
        sr_sum = 0.0
        ss_sum = 0.0
        for d in range(1, num_days + 1):
            dt = date(year, m, d)
            n_day = dt.timetuple().tm_yday
            gamma = 2.0 * math.pi / 365.0 * (n_day - 1 + 0.5)
            eqtime = (
                229.18 * (
                    0.000075
                    + 0.001868 * math.cos(gamma)
                    - 0.032077 * math.sin(gamma)
                    - 0.014615 * math.cos(2 * gamma)
                    - 0.040849 * math.sin(2 * gamma)
                )
            )
            decl = (
                0.006918
                - 0.399912 * math.cos(gamma)
                + 0.070257 * math.sin(gamma)
                - 0.006758 * math.cos(2 * gamma)
                + 0.000907 * math.sin(2 * gamma)
                - 0.002697 * math.cos(3 * gamma)
                + 0.00148 * math.sin(3 * gamma)
            )
            time_offset = eqtime + 4.0 * lon - 60.0 * utc_offset_hours
            t_noon_min = 720.0 - time_offset

            denom = math.cos(lat_rad) * math.cos(decl)
            if abs(denom) > 1e-6:
                cos_ha = (math.sin(math.radians(-0.833)) - math.sin(lat_rad) * math.sin(decl)) / denom
                if cos_ha > 1.0:
                    sr, ss = 720.0, 720.0
                elif cos_ha < -1.0:
                    sr, ss = 0.0, 1440.0
                else:
                    ha = math.degrees(math.acos(cos_ha))
                    sr = t_noon_min - ha * 4.0
                    ss = t_noon_min + ha * 4.0
            else:
                sr, ss = 360.0, 1080.0
            sr_sum += sr
            ss_sum += ss

        sr_avg = sr_sum / num_days
        ss_avg = ss_sum / num_days

        def fmt(m_val: float) -> str:
            m_mod = m_val % 1440.0
            h = int(m_mod // 60)
            mins = int(round(m_mod % 60))
            if mins == 60:
                mins = 0
                h = (h + 1) % 24
            return f'{h:02d}:{mins:02d}'

        monthly_rows.append({
            'month': m,
            'name': month_names[m - 1],
            'sunrise_str': fmt(sr_avg),
            'sunset_str': fmt(ss_avg),
            'sunrise_frac': round(sr_avg / 60.0, 2),
            'sunset_frac': round(ss_avg / 60.0, 2),
            'daylight_min': max(0.0, ss_avg - sr_avg),
            'is_current': (m == cur_month)
        })

    solstice_date = date(year, 6, 21) if lat >= 0 else date(year, 12, 21)
    n_sol = solstice_date.timetuple().tm_yday
    gamma_sol = 2.0 * math.pi / 365.0 * (n_sol - 1 + 0.5)
    eqtime_sol = (
        229.18 * (
            0.000075
            + 0.001868 * math.cos(gamma_sol)
            - 0.032077 * math.sin(gamma_sol)
            - 0.014615 * math.cos(2 * gamma_sol)
            - 0.040849 * math.sin(2 * gamma_sol)
        )
    )
    decl_sol = (
        0.006918
        - 0.399912 * math.cos(gamma_sol)
        + 0.070257 * math.sin(gamma_sol)
        - 0.006758 * math.cos(2 * gamma_sol)
        + 0.000907 * math.sin(2 * gamma_sol)
        - 0.002697 * math.cos(3 * gamma_sol)
        + 0.00148 * math.sin(3 * gamma_sol)
    )
    t_noon_sol = 720.0 - (eqtime_sol + 4.0 * lon - 60.0 * utc_offset_hours)
    denom_sol = math.cos(lat_rad) * math.cos(decl_sol)
    cos_ha_sol = (math.sin(math.radians(-0.833)) - math.sin(lat_rad) * math.sin(decl_sol)) / denom_sol
    ha_sol = math.degrees(math.acos(max(-1.0, min(1.0, cos_ha_sol))))
    dl_sol_min = ha_sol * 8.0
    dl_sol_h = int(dl_sol_min // 60)
    dl_sol_m = int(round(dl_sol_min % 60))

    sol_date_str = format_day_month(21, 6 if lat >= 0 else 12, lang=target_lang)
    longest_day_str = t('weather_sun_longest_day', date=sol_date_str, h=dl_sol_h, m=dl_sol_m, lang=target_lang)

    return {
        'months': monthly_rows,
        'longest_day_str': longest_day_str
    }


def calculate_lunar_distance_km(dt: datetime) -> int:
    """Вычисление расстояния от Земли до Луны в километрах."""
    y, m = dt.year, dt.month
    day_frac = dt.day + dt.hour / 24.0 + dt.minute / 1440.0 + dt.second / 86400.0
    if m <= 2:
        y -= 1
        m += 12
    a_val = int(y / 100)
    b_val = 2 - a_val + int(a_val / 4)
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day_frac + b_val - 1524.5
    t_cen = (jd - 2451545.0) / 36525.0

    d_ang = math.radians((297.8501921 + 445267.1114034 * t_cen - 0.0018819 * (t_cen ** 2)) % 360)
    m_sun = math.radians((357.5291092 + 35999.0502909 * t_cen - 0.0001536 * (t_cen ** 2)) % 360)
    m_moon = math.radians((134.9633964 + 477198.8675055 * t_cen + 0.0087414 * (t_cen ** 2)) % 360)
    f_arg = math.radians((93.2720950 + 483202.0175233 * t_cen - 0.0036539 * (t_cen ** 2)) % 360)

    dist = 385000.56
    dist -= 20905.355 * math.cos(m_moon)
    dist -= 3699.111 * math.cos(2 * d_ang - m_moon)
    dist -= 2955.968 * math.cos(2 * d_ang)
    dist -= 569.925 * math.cos(2 * m_moon)
    dist += 48.888 * math.cos(m_sun)
    dist -= 3.149 * math.cos(2 * f_arg)
    dist += 246.158 * math.cos(2 * d_ang - 2 * m_moon)
    dist -= 152.138 * math.cos(2 * d_ang - m_sun - m_moon)
    dist -= 170.733 * math.cos(2 * d_ang + m_moon)
    dist -= 204.586 * math.cos(2 * d_ang - m_sun)
    dist -= 129.620 * math.cos(m_moon - m_sun)
    dist += 108.743 * math.cos(d_ang)
    dist += 104.755 * math.cos(m_moon + m_sun)
    dist += 79.661 * math.cos(2 * d_ang - 2 * f_arg)
    return int(round(dist))


def calculate_moonrise_moonset(
    lat: float,
    lon: float,
    dt_day: date,
    utc_offset_hours: float
) -> tuple[str, str]:
    """Расчет времени восхода и захода Луны для заданных координат и даты."""
    lat_r = math.radians(lat)

    def get_moon_alt(t_local_hour: float) -> float:
        t_utc_hour = t_local_hour - utc_offset_hours
        dt_utc = datetime(dt_day.year, dt_day.month, dt_day.day, tzinfo=timezone.utc) + timedelta(hours=t_utc_hour)
        y, m = dt_utc.year, dt_utc.month
        day_frac = dt_utc.day + dt_utc.hour / 24.0 + dt_utc.minute / 1440.0 + dt_utc.second / 86400.0
        if m <= 2:
            y -= 1
            m += 12
        a_val = int(y / 100)
        b_val = 2 - a_val + int(a_val / 4)
        jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day_frac + b_val - 1524.5
        t_cen = (jd - 2451545.0) / 36525.0

        lp = (218.3164477 + 481267.88123421 * t_cen) % 360
        d_ang = math.radians((297.8501921 + 445267.1114034 * t_cen) % 360)
        m_sun = math.radians((357.5291092 + 35999.0502909 * t_cen) % 360)
        m_moon = math.radians((134.9633964 + 477198.8675055 * t_cen) % 360)
        f_arg = math.radians((93.2720950 + 483202.0175233 * t_cen) % 360)

        lon_moon = (
            lp
            + 6.288774 * math.sin(m_moon)
            + 1.274027 * math.sin(2 * d_ang - m_moon)
            + 0.658314 * math.sin(2 * d_ang)
            + 0.213618 * math.sin(2 * m_moon)
            - 0.185116 * math.sin(m_sun)
            - 0.114332 * math.sin(2 * f_arg)
        )
        lat_moon = (
            5.128122 * math.sin(f_arg)
            + 0.280602 * math.sin(m_moon + f_arg)
            + 0.277693 * math.sin(m_moon - f_arg)
            + 0.173237 * math.sin(2 * d_ang - f_arg)
        )
        eps = math.radians(23.439291 - 0.0130042 * t_cen)

        lon_r = math.radians(lon_moon)
        lat_mr = math.radians(lat_moon)
        sin_dec = math.sin(lat_mr) * math.cos(eps) + math.cos(lat_mr) * math.sin(eps) * math.sin(lon_r)
        dec = math.asin(sin_dec)
        y_ra = math.sin(lon_r) * math.cos(eps) - math.tan(lat_mr) * math.sin(eps)
        x_ra = math.cos(lon_r)
        ra = math.atan2(y_ra, x_ra)

        gmst = (280.46061837 + 360.98564736629 * (jd - 2451545.0)) % 360
        lst = math.radians((gmst + lon) % 360)
        ha = lst - ra
        sin_alt = math.sin(lat_r) * math.sin(dec) + math.cos(lat_r) * math.cos(dec) * math.cos(ha)
        alt = math.asin(max(-1.0, min(1.0, sin_alt)))
        return math.degrees(alt) - 0.125

    rise_time, set_time = None, None
    prev_h = 0.0
    prev_alt = get_moon_alt(prev_h)
    for step in range(1, 97):
        h = step * 0.25
        alt = get_moon_alt(h)
        if prev_alt <= 0.0 and alt > 0.0 and rise_time is None:
            frac = (0.0 - prev_alt) / (alt - prev_alt)
            rise_time = prev_h + frac * 0.25
        elif prev_alt >= 0.0 and alt < 0.0 and set_time is None:
            frac = (0.0 - prev_alt) / (alt - prev_alt)
            set_time = prev_h + frac * 0.25
        prev_h, prev_alt = h, alt

    def fmt(h_val: float | None) -> str:
        if h_val is None:
            return '-:-'
        h_val = h_val % 24.0
        hh = int(h_val)
        mm = int(round((h_val - hh) * 60.0))
        if mm == 60:
            hh = (hh + 1) % 24
            mm = 0
        return f'{hh:02d}:{mm:02d}'

    return fmt(rise_time), fmt(set_time)


def calculate_detailed_moon(
    lat: float,
    lon: float,
    target_dt: datetime | None = None,
    utc_offset_hours: float = 0.0,
    is_ru: bool | None = None,
    lang: str | None = None,
) -> dict:
    """Полный расчет параметров Луны: фаза, освещенность, расстояние, время восхода/захода, наклон."""
    target_lang = lang or (get_current_language() if is_ru is None else ('ru' if is_ru else 'en'))
    if target_dt is None:
        target_dt = datetime.now(timezone.utc) + timedelta(hours=utc_offset_hours)

    if target_dt.tzinfo is None:
        dt_utc = target_dt - timedelta(hours=utc_offset_hours)
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    else:
        dt_utc = target_dt.astimezone(timezone.utc)

    ref_new_moon = datetime(2024, 1, 11, 11, 57, tzinfo=timezone.utc)
    synodic = 29.53058867
    diff_days = (dt_utc - ref_new_moon).total_seconds() / 86400.0
    cycles = diff_days / synodic
    cycle_frac = (cycles - int(cycles)) % 1.0
    age_days = cycle_frac * synodic

    illumination = 0.5 * (1.0 - math.cos(2 * math.pi * cycle_frac)) * 100.0

    if cycle_frac < 0.5:
        days_to_full = (0.5 - cycle_frac) * synodic
    else:
        days_to_full = (1.5 - cycle_frac) * synodic
    days_to_new = (1.0 - cycle_frac) * synodic

    if cycle_frac < 0.03 or cycle_frac >= 0.97:
        phase_key = 'weather_moon_phase_new'
    elif cycle_frac < 0.22:
        phase_key = 'weather_moon_phase_waxing_crescent'
    elif cycle_frac < 0.28:
        phase_key = 'weather_moon_phase_first_quarter'
    elif cycle_frac < 0.47:
        phase_key = 'weather_moon_phase_waxing_gibbous'
    elif cycle_frac < 0.53:
        phase_key = 'weather_moon_phase_full'
    elif cycle_frac < 0.72:
        phase_key = 'weather_moon_phase_waning_gibbous'
    elif cycle_frac < 0.78:
        phase_key = 'weather_moon_phase_last_quarter'
    else:
        phase_key = 'weather_moon_phase_waning_crescent'

    phase_name = t(phase_key, lang=target_lang)
    p_ru = t(phase_key, lang='ru')
    p_en = t(phase_key, lang='en')
    dist_km = calculate_lunar_distance_km(dt_utc)

    local_date = (dt_utc + timedelta(hours=utc_offset_hours)).date()
    rise_str, set_str = calculate_moonrise_moonset(lat, lon, local_date, utc_offset_hours)

    dt_full = target_dt + timedelta(days=days_to_full)
    dt_new = target_dt + timedelta(days=days_to_new)

    def fmt_d(d_val: datetime) -> str:
        d_str = get_weekday_name(d_val.weekday(), lang=target_lang)
        dm_str = format_day_month(d_val.day, d_val.month, lang=target_lang)
        return f'{d_str}, {dm_str}'

    full_moon_date_str = fmt_d(dt_full)
    new_moon_date_str = fmt_d(dt_new)

    h_frac = target_dt.hour + target_dt.minute / 60.0
    tilt_deg = 15.0 * math.sin(2 * math.pi * (cycle_frac - 0.25)) - 10.0 * math.cos(h_frac * math.pi / 12.0)

    dist_u = t('unit_km', lang=target_lang)

    return {
        'cycle_fraction': cycle_frac,
        'illumination': int(round(illumination)),
        'phase_name': phase_name,
        'phase_name_ru': p_ru,
        'phase_name_en': p_en,
        'age_days': round(age_days, 1),
        'days_to_full': max(0, int(round(days_to_full))),
        'distance_km': dist_km,
        'distance_str': f'{dist_km:,}'.replace(',', ' ') + f' {dist_u}',
        'moonrise': rise_str,
        'moonset': set_str,
        'next_full_moon_date_str': full_moon_date_str,
        'next_new_moon_date_str': new_moon_date_str,
        'tilt_deg': round(tilt_deg, 1)
    }


def calculate_month_moon_calendar(year: int, month: int, is_ru: bool | None = None, lang: str | None = None) -> dict:
    """Генерация лунного календаря на заданный месяц и год."""
    target_lang = lang or (get_current_language() if is_ru is None else ('ru' if is_ru else 'en'))
    ref_new_moon = datetime(2024, 1, 11, 11, 57, tzinfo=timezone.utc)
    synodic = 29.53058867

    first_weekday, num_days = calendar.monthrange(year, month)
    days = []

    for d in range(1, num_days + 1):
        dt = datetime(year, month, d, 12, 0, tzinfo=timezone.utc)
        diff_days = (dt - ref_new_moon).total_seconds() / 86400.0
        cycles = diff_days / synodic
        f = (cycles - int(cycles)) % 1.0
        illum = 0.5 * (1.0 - math.cos(2 * math.pi * f)) * 100.0

        days.append({
            'day': d,
            'weekday': dt.weekday(),
            'cycle_fraction': f,
            'illumination': int(round(illum)),
        })

    m_name = get_month_name(month, short=False, lang=target_lang).capitalize()
    if target_lang == 'ru':
        title = f'{m_name} {year} г.'
    elif target_lang in ('zh', 'ja'):
        title = f'{year}年{month}月'
    else:
        title = f'{m_name} {year}'

    return {
        'year': year,
        'month': month,
        'title': title,
        'first_weekday': first_weekday,
        'num_days': num_days,
        'days': days
    }


def compute_solar_uv(lat: float, dt: datetime, cloud_pct: float = 0.0) -> float:
    """
    Физический расчет ультрафиолетового индекса по зенитному углу Солнца и облачности.
    Основан на солнечной геометрии NOAA и эмпирической модели ослабления излучения облаками.
    """
    n_day = dt.timetuple().tm_yday
    gamma = 2.0 * math.pi / 365.0 * (n_day - 1 + 0.5)
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
    )
    h_angle = math.radians((dt.hour + dt.minute / 60.0 - 12.0) * 15.0)
    lat_rad = math.radians(lat)
    sin_elev = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.cos(h_angle)
    if sin_elev <= 0.05:
        return 0.0
    uv_clear = 9.5 * (sin_elev ** 1.7)
    cf = max(0.0, min(100.0, float(cloud_pct))) / 100.0
    uv_val = uv_clear * (1.0 - 0.72 * (cf ** 2.2))
    return max(0.0, round(uv_val, 1))
