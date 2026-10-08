"""Meteorological WMO condition mappings, localized descriptions, and climate averages."""
import json
import math
import os
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from i18n import format_day_month, get_current_language, get_month_name, t
from logger import get_logger
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

logger = get_logger("wmo_conditions")
ICONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "icons", "weather"))


def convert_temp(celsius: float | int, unit: str = "celsius") -> int:
    """Convert Celsius temperature to the specified unit (celsius or fahrenheit)."""
    try:
        c_val = float(celsius)
    except (TypeError, ValueError):
        return 0
    if unit == "fahrenheit":
        return round(c_val * 1.8 + 32.0)
    return round(c_val)


def convert_temp_diff(celsius_diff: float | int, unit: str = "celsius") -> int:
    """Convert temperature difference/delta to the specified unit."""
    try:
        d_val = float(celsius_diff)
    except (TypeError, ValueError):
        return 0
    if unit == "fahrenheit":
        return round(d_val * 1.8)
    return round(d_val)


def format_temp(celsius: float | int, unit: str = "celsius", show_sign: bool = False, show_unit: bool = False) -> str:
    """Format temperature in target unit with optional sign and unit symbol."""
    val = convert_temp(celsius, unit)
    unit_sym = "°F" if (show_unit and unit == "fahrenheit") else ("°C" if show_unit else "°")
    if show_sign and val > 0:
        return f"+{val}{unit_sym}"
    return f"{val}{unit_sym}"


MAJOR_CITIES = {
    'нью-йорк': {'name_ru': 'Нью-Йорк', 'name_en': 'New York', 'lat': 40.7128, 'lon': -74.0060, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['ny', 'new york', 'нью йорк']},
    'новокузнецк': {'name_ru': 'Новокузнецк', 'name_en': 'Novokuznetsk', 'lat': 53.7557, 'lon': 87.1099, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['кузня', 'nvkz']},
    'москва': {'name_ru': 'Москва', 'name_en': 'Moscow', 'lat': 55.7520, 'lon': 37.6178, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['мск', 'moscow']},
    'санкт-петербург': {'name_ru': 'Санкт-Петербург', 'name_en': 'Saint Petersburg', 'lat': 59.9386, 'lon': 30.3141, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['питер', 'спб']},
    'новосибирск': {'name_ru': 'Новосибирск', 'name_en': 'Novosibirsk', 'lat': 55.0415, 'lon': 82.9346, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['нск', 'сиб']},
    'екатеринбург': {'name_ru': 'Екатеринбург', 'name_en': 'Yekaterinburg', 'lat': 56.8389, 'lon': 60.6057, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['екб']},
    'казань': {'name_ru': 'Казань', 'name_en': 'Kazan', 'lat': 55.7887, 'lon': 49.1221, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['kzn']},
    'нижний новгород': {'name_ru': 'Нижний Новгород', 'name_en': 'Nizhny Novgorod', 'lat': 56.3269, 'lon': 44.0059, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['нн']},
    'челябинск': {'name_ru': 'Челябинск', 'name_en': 'Chelyabinsk', 'lat': 55.1644, 'lon': 61.4368, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['члб']},
    'самара': {'name_ru': 'Самара', 'name_en': 'Samara', 'lat': 53.2001, 'lon': 50.1500, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'омск': {'name_ru': 'Омск', 'name_en': 'Omsk', 'lat': 54.9885, 'lon': 73.3242, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'ростов-на-дону': {'name_ru': 'Ростов-на-Дону', 'name_en': 'Rostov-on-Don', 'lat': 47.2357, 'lon': 39.7015, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['ростов']},
    'уфа': {'name_ru': 'Уфа', 'name_en': 'Ufa', 'lat': 54.7388, 'lon': 55.9721, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'красноярск': {'name_ru': 'Красноярск', 'name_en': 'Krasnoyarsk', 'lat': 56.0153, 'lon': 92.8932, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['крск']},
    'воронеж': {'name_ru': 'Воронеж', 'name_en': 'Voronezh', 'lat': 51.6720, 'lon': 39.1843, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'пермь': {'name_ru': 'Пермь', 'name_en': 'Perm', 'lat': 58.0105, 'lon': 56.2502, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'волгоград': {'name_ru': 'Волгоград', 'name_en': 'Volgograd', 'lat': 48.7080, 'lon': 44.5133, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'краснодар': {'name_ru': 'Краснодар', 'name_en': 'Krasnodar', 'lat': 45.0355, 'lon': 38.9753, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['крд']},
    'саратов': {'name_ru': 'Саратов', 'name_en': 'Saratov', 'lat': 51.5406, 'lon': 46.0086, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'тюмень': {'name_ru': 'Тюмень', 'name_en': 'Tyumen', 'lat': 57.1522, 'lon': 65.5272, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'тольятти': {'name_ru': 'Тольятти', 'name_en': 'Tolyatti', 'lat': 53.5303, 'lon': 49.3461, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'барнаул': {'name_ru': 'Барнаул', 'name_en': 'Barnaul', 'lat': 53.3606, 'lon': 83.7636, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'ижевск': {'name_ru': 'Ижевск', 'name_en': 'Izhevsk', 'lat': 56.8498, 'lon': 53.2045, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'ульяновск': {'name_ru': 'Ульяновск', 'name_en': 'Ulyanovsk', 'lat': 54.3282, 'lon': 48.3866, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'иркутск': {'name_ru': 'Иркутск', 'name_en': 'Irkutsk', 'lat': 52.2978, 'lon': 104.2964, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'хабаровск': {'name_ru': 'Хабаровск', 'name_en': 'Khabarovsk', 'lat': 48.4827, 'lon': 135.0838, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'ярославль': {'name_ru': 'Ярославль', 'name_en': 'Yaroslavl', 'lat': 57.6261, 'lon': 39.8845, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'владивосток': {'name_ru': 'Владивосток', 'name_en': 'Vladivostok', 'lat': 43.1155, 'lon': 131.8855, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['вдк']},
    'томск': {'name_ru': 'Томск', 'name_en': 'Tomsk', 'lat': 56.4977, 'lon': 84.9744, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'кемерово': {'name_ru': 'Кемерово', 'name_en': 'Kemerovo', 'lat': 55.3333, 'lon': 86.0833, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'сочи': {'name_ru': 'Сочи', 'name_en': 'Sochi', 'lat': 43.6028, 'lon': 39.7342, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'калининград': {'name_ru': 'Калининград', 'name_en': 'Kaliningrad', 'lat': 54.7104, 'lon': 20.4522, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['клд']},
    'онтарио': {'name_ru': 'Онтарио', 'name_en': 'Ontario', 'lat': 43.6532, 'lon': -79.3832, 'country_ru': 'Канада', 'country_en': 'Canada', 'keywords': ['ontario']},
    'лондон': {'name_ru': 'Лондон', 'name_en': 'London', 'lat': 51.5074, 'lon': -0.1278, 'country_ru': 'Великобритания', 'country_en': 'UK', 'keywords': ['london']},
    'париж': {'name_ru': 'Париж', 'name_en': 'Paris', 'lat': 48.8566, 'lon': 2.3522, 'country_ru': 'Франция', 'country_en': 'France', 'keywords': ['paris']},
    'токио': {'name_ru': 'Токио', 'name_en': 'Tokyo', 'lat': 35.6762, 'lon': 139.6503, 'country_ru': 'Япония', 'country_en': 'Japan', 'keywords': ['tokyo']},
    'берлин': {'name_ru': 'Берлин', 'name_en': 'Berlin', 'lat': 52.5200, 'lon': 13.4050, 'country_ru': 'Германия', 'country_en': 'Germany', 'keywords': ['berlin']},
    'рим': {'name_ru': 'Рим', 'name_en': 'Rome', 'lat': 41.9028, 'lon': 12.4964, 'country_ru': 'Италия', 'country_en': 'Italy', 'keywords': ['rome']},
    'дубай': {'name_ru': 'Дубай', 'name_en': 'Dubai', 'lat': 25.2048, 'lon': 55.2708, 'country_ru': 'ОАЭ', 'country_en': 'UAE', 'keywords': ['dubai']},
    'минск': {'name_ru': 'Минск', 'name_en': 'Minsk', 'lat': 53.9045, 'lon': 27.5615, 'country_ru': 'Беларусь', 'country_en': 'Belarus', 'keywords': ['minsk']},
    'алматы': {'name_ru': 'Алматы', 'name_en': 'Almaty', 'lat': 43.2220, 'lon': 76.8512, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['almaty', 'алмата']},
    'астана': {'name_ru': 'Астана', 'name_en': 'Astana', 'lat': 51.1694, 'lon': 71.4491, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['astana']},
    'ташкент': {'name_ru': 'Ташкент', 'name_en': 'Tashkent', 'lat': 41.2995, 'lon': 69.2401, 'country_ru': 'Узбекистан', 'country_en': 'Uzbekistan', 'keywords': ['tashkent']},
    'тбилиси': {'name_ru': 'Тбилиси', 'name_en': 'Tbilisi', 'lat': 41.7151, 'lon': 44.8271, 'country_ru': 'Грузия', 'country_en': 'Georgia', 'keywords': ['tbilisi']},
    'ереван': {'name_ru': 'Ереван', 'name_en': 'Yerevan', 'lat': 40.1792, 'lon': 44.4991, 'country_ru': 'Армения', 'country_en': 'Armenia', 'keywords': ['yerevan']},
    'стамбул': {'name_ru': 'Стамбул', 'name_en': 'Istanbul', 'lat': 41.0082, 'lon': 28.9784, 'country_ru': 'Турция', 'country_en': 'Turkey', 'keywords': ['istanbul']},
    'пекин': {'name_ru': 'Пекин', 'name_en': 'Beijing', 'lat': 39.9042, 'lon': 116.4074, 'country_ru': 'Китай', 'country_en': 'China', 'keywords': ['beijing']},
    'сеул': {'name_ru': 'Сеул', 'name_en': 'Seoul', 'lat': 37.5665, 'lon': 126.9780, 'country_ru': 'Южная Корея', 'country_en': 'South Korea', 'keywords': ['seoul']},
    'бангкок': {'name_ru': 'Бангкок', 'name_en': 'Bangkok', 'lat': 13.7563, 'lon': 100.5018, 'country_ru': 'Таиланд', 'country_en': 'Thailand', 'keywords': ['bangkok']},
    'пхукет': {'name_ru': 'Пхукет', 'name_en': 'Phuket', 'lat': 7.8804, 'lon': 98.3923, 'country_ru': 'Таиланд', 'country_en': 'Thailand', 'keywords': ['phuket']},
    'лос-анджелес': {'name_ru': 'Лос-Анджелес', 'name_en': 'Los Angeles', 'lat': 34.0522, 'lon': -118.2437, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['la', 'los angeles']},
    'вашингтон': {'name_ru': 'Вашингтон', 'name_en': 'Washington D.C.', 'lat': 38.8951, 'lon': -77.0364, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['washington', 'dc', 'd.c.', 'вашингтон']},
    'чикаго': {'name_ru': 'Чикаго', 'name_en': 'Chicago', 'lat': 41.8781, 'lon': -87.6298, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['chicago', 'чикаго']},
    'майами': {'name_ru': 'Майами', 'name_en': 'Miami', 'lat': 25.7617, 'lon': -80.1918, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['miami', 'майами']},
    'сан-франциско': {'name_ru': 'Сан-Франциско', 'name_en': 'San Francisco', 'lat': 37.7749, 'lon': -122.4194, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['sf', 'san francisco', 'сан франциско']},
    'бостон': {'name_ru': 'Бостон', 'name_en': 'Boston', 'lat': 42.3601, 'lon': -71.0589, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['boston', 'бостон']},
    'сиэтл': {'name_ru': 'Сиэтл', 'name_en': 'Seattle', 'lat': 47.6062, 'lon': -122.3321, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['seattle', 'сиэтл']},
    'лас-вегас': {'name_ru': 'Лас-Вегас', 'name_en': 'Las Vegas', 'lat': 36.1716, 'lon': -115.1391, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['vegas', 'las vegas', 'вегас', 'лас вегас']},
    'хьюстон': {'name_ru': 'Хьюстон', 'name_en': 'Houston', 'lat': 29.7604, 'lon': -95.3698, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['houston', 'хьюстон']},
    'даллас': {'name_ru': 'Даллас', 'name_en': 'Dallas', 'lat': 32.7767, 'lon': -96.7970, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['dallas', 'даллас']},
    'атланта': {'name_ru': 'Атланта', 'name_en': 'Atlanta', 'lat': 33.7490, 'lon': -84.3880, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['atlanta', 'атланта']},
    'филадельфия': {'name_ru': 'Филадельфия', 'name_en': 'Philadelphia', 'lat': 39.9526, 'lon': -75.1652, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['philly', 'philadelphia', 'филадельфия']},
    'сан-диего': {'name_ru': 'Сан-Диего', 'name_en': 'San Diego', 'lat': 32.7157, 'lon': -117.1611, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['san diego', 'сан диего']},
    'денвер': {'name_ru': 'Денвер', 'name_en': 'Denver', 'lat': 39.7392, 'lon': -104.9903, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['denver', 'денвер']},
    'остин': {'name_ru': 'Остин', 'name_en': 'Austin', 'lat': 30.2672, 'lon': -97.7431, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['austin', 'остин']},
    'финикс': {'name_ru': 'Финикс', 'name_en': 'Phoenix', 'lat': 33.4484, 'lon': -112.0740, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['phoenix', 'финикс']},
    'орландо': {'name_ru': 'Орландо', 'name_en': 'Orlando', 'lat': 28.5383, 'lon': -81.3792, 'country_ru': 'США', 'country_en': 'USA', 'keywords': ['orlando', 'орландо']},
    'торонто': {'name_ru': 'Торонто', 'name_en': 'Toronto', 'lat': 43.6532, 'lon': -79.3832, 'country_ru': 'Канада', 'country_en': 'Canada', 'keywords': ['toronto', 'торонто']},
    'ванкувер': {'name_ru': 'Ванкувер', 'name_en': 'Vancouver', 'lat': 49.2827, 'lon': -123.1207, 'country_ru': 'Канада', 'country_en': 'Canada', 'keywords': ['vancouver', 'ванкувер']},
    'монреаль': {'name_ru': 'Монреаль', 'name_en': 'Montreal', 'lat': 45.5017, 'lon': -73.5673, 'country_ru': 'Канада', 'country_en': 'Canada', 'keywords': ['montreal', 'монреаль']},
    'сидней': {'name_ru': 'Сидней', 'name_en': 'Sydney', 'lat': -33.8688, 'lon': 151.2093, 'country_ru': 'Австралия', 'country_en': 'Australia', 'keywords': ['sydney', 'сидней']},
    'мельбурн': {'name_ru': 'Мельбурн', 'name_en': 'Melbourne', 'lat': -37.8136, 'lon': 144.9631, 'country_ru': 'Австралия', 'country_en': 'Australia', 'keywords': ['melbourne', 'мельбурн']},
    'мадрид': {'name_ru': 'Мадрид', 'name_en': 'Madrid', 'lat': 40.4168, 'lon': -3.7038, 'country_ru': 'Испания', 'country_en': 'Spain', 'keywords': ['madrid', 'мадрид']},
    'барселона': {'name_ru': 'Барселона', 'name_en': 'Barcelona', 'lat': 41.3879, 'lon': 2.1699, 'country_ru': 'Испания', 'country_en': 'Spain', 'keywords': ['barcelona', 'барселона']},
    'амстердам': {'name_ru': 'Амстердам', 'name_en': 'Amsterdam', 'lat': 52.3676, 'lon': 4.9041, 'country_ru': 'Нидерланды', 'country_en': 'Netherlands', 'keywords': ['amsterdam', 'амстердам']},
    'вена': {'name_ru': 'Вена', 'name_en': 'Vienna', 'lat': 48.2082, 'lon': 16.3738, 'country_ru': 'Австрия', 'country_en': 'Austria', 'keywords': ['vienna', 'вена']},
    'прага': {'name_ru': 'Прага', 'name_en': 'Prague', 'lat': 50.0755, 'lon': 14.4378, 'country_ru': 'Чехия', 'country_en': 'Czech Republic', 'keywords': ['prague', 'прага']},
    'варшава': {'name_ru': 'Варшава', 'name_en': 'Warsaw', 'lat': 52.2297, 'lon': 21.0122, 'country_ru': 'Польша', 'country_en': 'Poland', 'keywords': ['warsaw', 'варшава']},
    'лиссабон': {'name_ru': 'Лиссабон', 'name_en': 'Lisbon', 'lat': 38.7223, 'lon': -9.1393, 'country_ru': 'Португалия', 'country_en': 'Portugal', 'keywords': ['lisbon', 'лиссабон', 'lissabon']},
    # Казахстан
    'караганда': {'name_ru': 'Караганда', 'name_en': 'Karaganda', 'lat': 49.8019, 'lon': 73.1021, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['karaganda', 'крг', 'караганды']},
    'шымкент': {'name_ru': 'Шымкент', 'name_en': 'Shymkent', 'lat': 42.3417, 'lon': 69.5901, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['shymkent', 'чимкент']},
    'актобе': {'name_ru': 'Актобе', 'name_en': 'Aktobe', 'lat': 50.2839, 'lon': 57.1670, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['aktobe', 'актюбинск']},
    'тараз': {'name_ru': 'Тараз', 'name_en': 'Taraz', 'lat': 42.9000, 'lon': 71.3667, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['taraz', 'джамбул']},
    'павлодар': {'name_ru': 'Павлодар', 'name_en': 'Pavlodar', 'lat': 52.2878, 'lon': 76.9674, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['pavlodar']},
    'усть-каменогорск': {'name_ru': 'Усть-Каменогорск', 'name_en': 'Oskemen', 'lat': 49.9714, 'lon': 82.6059, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['ука', 'оскемен', 'oskemen', 'ust-kamenogorsk']},
    'семей': {'name_ru': 'Семей', 'name_en': 'Semey', 'lat': 50.4111, 'lon': 80.2275, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['semey', 'семипалатинск']},
    'атырау': {'name_ru': 'Атырау', 'name_en': 'Atyrau', 'lat': 47.1167, 'lon': 51.8833, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['atyrau', 'гурьев']},
    'костанай': {'name_ru': 'Костанай', 'name_en': 'Kostanay', 'lat': 53.2144, 'lon': 63.6246, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['kostanay', 'кустанай']},
    'кызылорда': {'name_ru': 'Кызылорда', 'name_en': 'Kyzylorda', 'lat': 44.8528, 'lon': 65.5092, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['kyzylorda', 'кзыл-орда']},
    'уральск': {'name_ru': 'Уральск', 'name_en': 'Oral', 'lat': 51.2333, 'lon': 51.3667, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['oral', 'uralsk']},
    'петропавловск': {'name_ru': 'Петропавловск', 'name_en': 'Petropavl', 'lat': 54.8753, 'lon': 69.1636, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['petropavl']},
    'актау': {'name_ru': 'Актау', 'name_en': 'Aktau', 'lat': 43.6500, 'lon': 51.1667, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['aktau', 'шевченко']},
    'темиртау': {'name_ru': 'Темиртау', 'name_en': 'Temirtau', 'lat': 50.0549, 'lon': 72.9646, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['temirtau']},
    'туркестан': {'name_ru': 'Туркестан', 'name_en': 'Turkistan', 'lat': 43.2974, 'lon': 68.2518, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['turkistan']},
    'кокшетау': {'name_ru': 'Кокшетау', 'name_en': 'Kokshetau', 'lat': 53.2833, 'lon': 69.3833, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['kokshetau', 'кокчетав']},
    'талдыкорган': {'name_ru': 'Талдыкорган', 'name_en': 'Taldykorgan', 'lat': 45.0167, 'lon': 78.3667, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['taldykorgan']},
    'экибастуз': {'name_ru': 'Экибастуз', 'name_en': 'Ekibastuz', 'lat': 51.7231, 'lon': 75.3228, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['ekibastuz']},
    'рудный': {'name_ru': 'Рудный', 'name_en': 'Rudny', 'lat': 52.9628, 'lon': 63.1292, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['rudny']},
    'жезказган': {'name_ru': 'Жезказган', 'name_en': 'Zhezkazgan', 'lat': 47.7833, 'lon': 67.7667, 'country_ru': 'Казахстан', 'country_en': 'Kazakhstan', 'keywords': ['zhezkazgan', 'джезказган']},
    # Беларусь
    'гомель': {'name_ru': 'Гомель', 'name_en': 'Gomel', 'lat': 52.4345, 'lon': 30.9754, 'country_ru': 'Беларусь', 'country_en': 'Belarus', 'keywords': ['gomel']},
    'могилев': {'name_ru': 'Могилев', 'name_en': 'Mogilev', 'lat': 53.8981, 'lon': 30.3325, 'country_ru': 'Беларусь', 'country_en': 'Belarus', 'keywords': ['mogilev', 'магілёў']},
    'витебск': {'name_ru': 'Витебск', 'name_en': 'Vitebsk', 'lat': 55.1904, 'lon': 30.2049, 'country_ru': 'Беларусь', 'country_en': 'Belarus', 'keywords': ['vitebsk', 'віцебск']},
    'гродно': {'name_ru': 'Гродно', 'name_en': 'Grodno', 'lat': 53.6884, 'lon': 23.8258, 'country_ru': 'Беларусь', 'country_en': 'Belarus', 'keywords': ['grodno', 'гродна']},
    'брест': {'name_ru': 'Брест', 'name_en': 'Brest', 'lat': 52.0976, 'lon': 23.7341, 'country_ru': 'Беларусь', 'country_en': 'Belarus', 'keywords': ['brest']},
    'бобруйск': {'name_ru': 'Бобруйск', 'name_en': 'Babruysk', 'lat': 53.1384, 'lon': 29.2214, 'country_ru': 'Беларусь', 'country_en': 'Belarus', 'keywords': ['bobruisk', 'babruysk']},
    'барановичи': {'name_ru': 'Барановичи', 'name_en': 'Baranovichi', 'lat': 53.1327, 'lon': 26.0139, 'country_ru': 'Беларусь', 'country_en': 'Belarus', 'keywords': ['baranovichi']},
    'пинск': {'name_ru': 'Пинск', 'name_en': 'Pinsk', 'lat': 52.1153, 'lon': 26.1031, 'country_ru': 'Беларусь', 'country_en': 'Belarus', 'keywords': ['pinsk']},
    'борисов': {'name_ru': 'Борисов', 'name_en': 'Barysaw', 'lat': 54.2276, 'lon': 28.5050, 'country_ru': 'Беларусь', 'country_en': 'Belarus', 'keywords': ['borisov', 'barysaw']},
    # СНГ и Закавказье
    'бишкек': {'name_ru': 'Бишкек', 'name_en': 'Bishkek', 'lat': 42.8746, 'lon': 74.5698, 'country_ru': 'Кыргызстан', 'country_en': 'Kyrgyzstan', 'keywords': ['bishkek', 'фрунзе']},
    'ош': {'name_ru': 'Ош', 'name_en': 'Osh', 'lat': 40.5140, 'lon': 72.8161, 'country_ru': 'Кыргызстан', 'country_en': 'Kyrgyzstan', 'keywords': ['osh']},
    'душанбе': {'name_ru': 'Душанбе', 'name_en': 'Dushanbe', 'lat': 38.5598, 'lon': 68.7870, 'country_ru': 'Таджикистан', 'country_en': 'Tajikistan', 'keywords': ['dushanbe', 'сталинабад']},
    'худжанд': {'name_ru': 'Худжанд', 'name_en': 'Khujand', 'lat': 40.2826, 'lon': 69.6222, 'country_ru': 'Таджикистан', 'country_en': 'Tajikistan', 'keywords': ['khujand', 'ленинабад']},
    'самарканд': {'name_ru': 'Самарканд', 'name_en': 'Samarkand', 'lat': 39.6542, 'lon': 66.9597, 'country_ru': 'Узбекистан', 'country_en': 'Uzbekistan', 'keywords': ['samarkand']},
    'бухара': {'name_ru': 'Бухара', 'name_en': 'Bukhara', 'lat': 39.7747, 'lon': 64.4286, 'country_ru': 'Узбекистан', 'country_en': 'Uzbekistan', 'keywords': ['bukhara']},
    'андижан': {'name_ru': 'Андижан', 'name_en': 'Andijan', 'lat': 40.7821, 'lon': 72.3442, 'country_ru': 'Узбекистан', 'country_en': 'Uzbekistan', 'keywords': ['andijan']},
    'ашхабад': {'name_ru': 'Ашхабад', 'name_en': 'Ashgabat', 'lat': 37.9601, 'lon': 58.3261, 'country_ru': 'Туркменистан', 'country_en': 'Turkmenistan', 'keywords': ['ashgabat']},
    'баку': {'name_ru': 'Баку', 'name_en': 'Baku', 'lat': 40.4093, 'lon': 49.8671, 'country_ru': 'Азербайджан', 'country_en': 'Azerbaijan', 'keywords': ['baku']},
    'гянджа': {'name_ru': 'Гянджа', 'name_en': 'Ganja', 'lat': 40.6828, 'lon': 46.3606, 'country_ru': 'Азербайджан', 'country_en': 'Azerbaijan', 'keywords': ['ganja', 'кировабад']},
    'батуми': {'name_ru': 'Батуми', 'name_en': 'Batumi', 'lat': 41.6416, 'lon': 41.6359, 'country_ru': 'Грузия', 'country_en': 'Georgia', 'keywords': ['batumi']},
    'кутаиси': {'name_ru': 'Кутаиси', 'name_en': 'Kutaisi', 'lat': 42.2679, 'lon': 42.6946, 'country_ru': 'Грузия', 'country_en': 'Georgia', 'keywords': ['kutaisi']},
    'гюмри': {'name_ru': 'Гюмри', 'name_en': 'Gyumri', 'lat': 40.7929, 'lon': 43.8465, 'country_ru': 'Армения', 'country_en': 'Armenia', 'keywords': ['gyumri', 'ленинакан']},
    # Регионы России
    'прокопьевск': {'name_ru': 'Прокопьевск', 'name_en': 'Prokopyevsk', 'lat': 53.8833, 'lon': 86.7167, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['прокопа']},
    'бийск': {'name_ru': 'Бийск', 'name_en': 'Biysk', 'lat': 52.5364, 'lon': 85.2072, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'братск': {'name_ru': 'Братск', 'name_en': 'Bratsk', 'lat': 56.1325, 'lon': 101.6142, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'ангарск': {'name_ru': 'Ангарск', 'name_en': 'Angarsk', 'lat': 52.5444, 'lon': 103.8882, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'абакан': {'name_ru': 'Абакан', 'name_en': 'Abakan', 'lat': 53.7156, 'lon': 91.4292, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'чита': {'name_ru': 'Чита', 'name_en': 'Chita', 'lat': 52.0317, 'lon': 113.5009, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'улан-удэ': {'name_ru': 'Улан-Удэ', 'name_en': 'Ulan-Ude', 'lat': 51.8348, 'lon': 107.5845, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['уланудэ']},
    'якутск': {'name_ru': 'Якутск', 'name_en': 'Yakutsk', 'lat': 62.0355, 'lon': 129.6755, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'южно-сахалинск': {'name_ru': 'Южно-Сахалинск', 'name_en': 'Yuzhno-Sakhalinsk', 'lat': 46.9541, 'lon': 142.7360, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['сахалин', 'южный']},
    'петропавловск-камчатский': {'name_ru': 'Петропавловск-Камчатский', 'name_en': 'Petropavlovsk-Kamchatsky', 'lat': 53.0452, 'lon': 158.6508, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['камчатка', 'пк']},
    'магадан': {'name_ru': 'Магадан', 'name_en': 'Magadan', 'lat': 59.5638, 'lon': 150.8036, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'норильск': {'name_ru': 'Норильск', 'name_en': 'Norilsk', 'lat': 69.3535, 'lon': 88.2027, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'сургут': {'name_ru': 'Сургут', 'name_en': 'Surgut', 'lat': 61.2500, 'lon': 73.4167, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'нижневартовск': {'name_ru': 'Нижневартовск', 'name_en': 'Nizhnevartovsk', 'lat': 60.9344, 'lon': 76.5585, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['вартовск']},
    'курган': {'name_ru': 'Курган', 'name_en': 'Kurgan', 'lat': 55.4411, 'lon': 65.3411, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'магнитогорск': {'name_ru': 'Магнитогорск', 'name_en': 'Magnitogorsk', 'lat': 53.4186, 'lon': 58.9703, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['магнитка']},
    'нижний тагил': {'name_ru': 'Нижний Тагил', 'name_en': 'Nizhny Tagil', 'lat': 57.9194, 'lon': 59.9650, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['тагил']},
    'стерлитамак': {'name_ru': 'Стерлитамак', 'name_en': 'Sterlitamak', 'lat': 53.6333, 'lon': 55.9500, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'оренбург': {'name_ru': 'Оренбург', 'name_en': 'Orenburg', 'lat': 51.7727, 'lon': 55.0988, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'сызрань': {'name_ru': 'Сызрань', 'name_en': 'Syzran', 'lat': 53.1558, 'lon': 48.4681, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'энгельс': {'name_ru': 'Энгельс', 'name_en': 'Engels', 'lat': 51.5033, 'lon': 46.1219, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'волжский': {'name_ru': 'Волжский', 'name_en': 'Volzhsky', 'lat': 48.7858, 'lon': 44.7797, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'астрахань': {'name_ru': 'Астрахань', 'name_en': 'Astrakhan', 'lat': 46.3497, 'lon': 48.0408, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'таганрог': {'name_ru': 'Таганрог', 'name_en': 'Taganrog', 'lat': 47.2362, 'lon': 38.8969, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'шахты': {'name_ru': 'Шахты', 'name_en': 'Shakhty', 'lat': 47.7086, 'lon': 40.2161, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'новочеркасск': {'name_ru': 'Новочеркасск', 'name_en': 'Novocherkassk', 'lat': 47.4222, 'lon': 40.0928, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'новороссийск': {'name_ru': 'Новороссийск', 'name_en': 'Novorossiysk', 'lat': 44.7239, 'lon': 37.7689, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'армавир': {'name_ru': 'Армавир', 'name_en': 'Armavir', 'lat': 44.9892, 'lon': 41.1233, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'ставрополь': {'name_ru': 'Ставрополь', 'name_en': 'Stavropol', 'lat': 45.0448, 'lon': 41.9690, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'пятигорск': {'name_ru': 'Пятигорск', 'name_en': 'Pyatigorsk', 'lat': 44.0486, 'lon': 43.0594, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'кисловодск': {'name_ru': 'Кисловодск', 'name_en': 'Kislovodsk', 'lat': 43.9133, 'lon': 42.7208, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'нальчик': {'name_ru': 'Нальчик', 'name_en': 'Nalchik', 'lat': 43.4981, 'lon': 43.6189, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'владикавказ': {'name_ru': 'Владикавказ', 'name_en': 'Vladikavkaz', 'lat': 43.0367, 'lon': 44.6678, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'грозный': {'name_ru': 'Грозный', 'name_en': 'Grozny', 'lat': 43.3178, 'lon': 45.6983, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'махачкала': {'name_ru': 'Махачкала', 'name_en': 'Makhachkala', 'lat': 42.9831, 'lon': 47.5047, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'севастополь': {'name_ru': 'Севастополь', 'name_en': 'Sevastopol', 'lat': 44.6167, 'lon': 33.5254, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'симферополь': {'name_ru': 'Симферополь', 'name_en': 'Simferopol', 'lat': 44.9521, 'lon': 34.1024, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'белгород': {'name_ru': 'Белгород', 'name_en': 'Belgorod', 'lat': 50.5954, 'lon': 36.5873, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'старый оскол': {'name_ru': 'Старый Оскол', 'name_en': 'Stary Oskol', 'lat': 51.2969, 'lon': 37.8344, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['оскол']},
    'курск': {'name_ru': 'Курск', 'name_en': 'Kursk', 'lat': 51.7374, 'lon': 36.1874, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'липецк': {'name_ru': 'Липецк', 'name_en': 'Lipetsk', 'lat': 52.6103, 'lon': 39.5947, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'тамбов': {'name_ru': 'Тамбов', 'name_en': 'Tambov', 'lat': 52.7317, 'lon': 41.4433, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'рязань': {'name_ru': 'Рязань', 'name_en': 'Ryazan', 'lat': 54.6269, 'lon': 39.6916, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'тула': {'name_ru': 'Тула', 'name_en': 'Tula', 'lat': 54.1961, 'lon': 37.6182, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'калуга': {'name_ru': 'Калуга', 'name_en': 'Kaluga', 'lat': 54.5293, 'lon': 36.2754, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'брянск': {'name_ru': 'Брянск', 'name_en': 'Bryansk', 'lat': 53.2521, 'lon': 34.3717, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'орел': {'name_ru': 'Орел', 'name_en': 'Oryol', 'lat': 52.9651, 'lon': 36.0785, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['орёл']},
    'смоленск': {'name_ru': 'Смоленск', 'name_en': 'Smolensk', 'lat': 54.7818, 'lon': 32.0401, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'тверь': {'name_ru': 'Тверь', 'name_en': 'Tver', 'lat': 56.8587, 'lon': 35.9176, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'владимир': {'name_ru': 'Владимир', 'name_en': 'Vladimir', 'lat': 56.1290, 'lon': 40.4066, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'иваново': {'name_ru': 'Иваново', 'name_en': 'Ivanovo', 'lat': 56.9972, 'lon': 40.9714, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'кострома': {'name_ru': 'Кострома', 'name_en': 'Kostroma', 'lat': 57.7679, 'lon': 40.9269, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'рыбинск': {'name_ru': 'Рыбинск', 'name_en': 'Rybinsk', 'lat': 58.0483, 'lon': 38.8583, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'вологда': {'name_ru': 'Вологда', 'name_en': 'Vologda', 'lat': 59.2239, 'lon': 39.8840, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'череповец': {'name_ru': 'Череповец', 'name_en': 'Cherepovets', 'lat': 59.1328, 'lon': 37.9094, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'архангельск': {'name_ru': 'Архангельск', 'name_en': 'Arkhangelsk', 'lat': 64.5401, 'lon': 40.5433, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'северодвинск': {'name_ru': 'Северодвинск', 'name_en': 'Severodvinsk', 'lat': 64.5635, 'lon': 39.8302, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'мурманск': {'name_ru': 'Мурманск', 'name_en': 'Murmansk', 'lat': 68.9585, 'lon': 33.0827, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'петрозаводск': {'name_ru': 'Петрозаводск', 'name_en': 'Petrozavodsk', 'lat': 61.7849, 'lon': 34.3469, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['птз']},
    'великий новгород': {'name_ru': 'Великий Новгород', 'name_en': 'Veliky Novgorod', 'lat': 58.5213, 'lon': 31.2710, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['новгород']},
    'псков': {'name_ru': 'Псков', 'name_en': 'Pskov', 'lat': 57.8136, 'lon': 28.3496, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'чебоксары': {'name_ru': 'Чебоксары', 'name_en': 'Cheboksary', 'lat': 56.1322, 'lon': 47.2519, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'йошкар-ола': {'name_ru': 'Йошкар-Ола', 'name_en': 'Yoshkar-Ola', 'lat': 56.6344, 'lon': 47.8999, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'саранск': {'name_ru': 'Саранск', 'name_en': 'Saransk', 'lat': 54.1838, 'lon': 45.1838, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'пенза': {'name_ru': 'Пенза', 'name_en': 'Penza', 'lat': 53.2007, 'lon': 45.0183, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'киров': {'name_ru': 'Киров', 'name_en': 'Kirov', 'lat': 58.6035, 'lon': 49.6679, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['вятка']},
    'сыктывкар': {'name_ru': 'Сыктывкар', 'name_en': 'Syktyvkar', 'lat': 61.6688, 'lon': 50.8354, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'набережные челны': {'name_ru': 'Набережные Челны', 'name_en': 'Naberezhnye Chelny', 'lat': 55.7436, 'lon': 52.4078, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['челны']},
    'нижнекамск': {'name_ru': 'Нижнекамск', 'name_en': 'Nizhnekamsk', 'lat': 55.6358, 'lon': 51.8214, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'комсомольск-на-амуре': {'name_ru': 'Комсомольск-на-Амуре', 'name_en': 'Komsomolsk-on-Amur', 'lat': 50.5503, 'lon': 137.0094, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['комсомольск']},
    'благовещенск': {'name_ru': 'Благовещенск', 'name_en': 'Blagoveshchensk', 'lat': 50.2796, 'lon': 127.5405, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': []},
    'горно-алтайск': {'name_ru': 'Горно-Алтайск', 'name_en': 'Gorno-Altaysk', 'lat': 51.9583, 'lon': 85.9603, 'country_ru': 'Россия', 'country_en': 'Russia', 'keywords': ['алтай']},
    # Международные города
    'анталья': {'name_ru': 'Анталья', 'name_en': 'Antalya', 'lat': 36.8841, 'lon': 30.7056, 'country_ru': 'Турция', 'country_en': 'Turkey', 'keywords': ['antalya']},
    'анкара': {'name_ru': 'Анкара', 'name_en': 'Ankara', 'lat': 39.9334, 'lon': 32.8597, 'country_ru': 'Турция', 'country_en': 'Turkey', 'keywords': ['ankara']},
    'абу-даби': {'name_ru': 'Абу-Даби', 'name_en': 'Abu Dhabi', 'lat': 24.4539, 'lon': 54.3773, 'country_ru': 'ОАЭ', 'country_en': 'UAE', 'keywords': ['abu dhabi']},
    'доха': {'name_ru': 'Доха', 'name_en': 'Doha', 'lat': 25.2854, 'lon': 51.5310, 'country_ru': 'Катар', 'country_en': 'Qatar', 'keywords': ['doha']},
    'милан': {'name_ru': 'Милан', 'name_en': 'Milan', 'lat': 45.4642, 'lon': 9.1900, 'country_ru': 'Италия', 'country_en': 'Italy', 'keywords': ['milan', 'milano']},
    'стокгольм': {'name_ru': 'Стокгольм', 'name_en': 'Stockholm', 'lat': 59.3293, 'lon': 18.0686, 'country_ru': 'Швеция', 'country_en': 'Sweden', 'keywords': ['stockholm']},
    'осло': {'name_ru': 'Осло', 'name_en': 'Oslo', 'lat': 59.9139, 'lon': 10.7522, 'country_ru': 'Норвегия', 'country_en': 'Norway', 'keywords': ['oslo']},
    'хельсинки': {'name_ru': 'Хельсинки', 'name_en': 'Helsinki', 'lat': 60.1699, 'lon': 24.9384, 'country_ru': 'Финляндия', 'country_en': 'Finland', 'keywords': ['helsinki']},
    'копенгаген': {'name_ru': 'Копенгаген', 'name_en': 'Copenhagen', 'lat': 55.6761, 'lon': 12.5683, 'country_ru': 'Дания', 'country_en': 'Denmark', 'keywords': ['copenhagen']},
    'рейкьявик': {'name_ru': 'Рейкьявик', 'name_en': 'Reykjavik', 'lat': 64.1466, 'lon': -21.9426, 'country_ru': 'Исландия', 'country_en': 'Iceland', 'keywords': ['reykjavik']}
}

WMO_INFO = {
    0: {'ru': 'Солнечно', 'en': 'Clear', 'icon_day': 'clear-day.svg', 'icon_night': 'clear-night.svg', 'grad': 'clear'},
    1: {'ru': 'В основном ясно', 'en': 'Mainly clear', 'icon_day': 'clear-day.svg', 'icon_night': 'clear-night.svg', 'grad': 'clear'},
    2: {'ru': 'В основном облачно', 'en': 'Partly cloudy', 'icon_day': 'partly-cloudy-day.svg', 'icon_night': 'partly-cloudy-night.svg', 'grad': 'clouds'},
    3: {'ru': 'Облачно', 'en': 'Overcast', 'icon_day': 'cloudy.svg', 'icon_night': 'cloudy.svg', 'grad': 'clouds'},
    45: {'ru': 'Туман', 'en': 'Fog', 'icon_day': 'fog.svg', 'icon_night': 'fog.svg', 'grad': 'fog'},
    48: {'ru': 'Туман с изморозью', 'en': 'Rime fog', 'icon_day': 'fog.svg', 'icon_night': 'fog.svg', 'grad': 'fog'},
    51: {'ru': 'Изморось', 'en': 'Light drizzle', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'drizzle'},
    53: {'ru': 'Умеренная изморось', 'en': 'Moderate drizzle', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'drizzle'},
    55: {'ru': 'Плотная изморось', 'en': 'Dense drizzle', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'drizzle'},
    56: {'ru': 'Ледяная изморось', 'en': 'Freezing drizzle', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'drizzle'},
    57: {'ru': 'Плотная ледяная изморось', 'en': 'Freezing drizzle', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'drizzle'},
    61: {'ru': 'Небольшой дождь', 'en': 'Slight rain', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'rain'},
    63: {'ru': 'Дождь', 'en': 'Rain', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'rain'},
    65: {'ru': 'Сильный дождь', 'en': 'Heavy rain', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'rain'},
    66: {'ru': 'Ледяной дождь', 'en': 'Freezing rain', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'rain'},
    67: {'ru': 'Сильный ледяной дождь', 'en': 'Freezing rain', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'rain'},
    71: {'ru': 'Небольшой снег', 'en': 'Slight snow', 'icon_day': 'snow.svg', 'icon_night': 'snow.svg', 'grad': 'snow'},
    73: {'ru': 'Снегопад', 'en': 'Snow fall', 'icon_day': 'snow.svg', 'icon_night': 'snow.svg', 'grad': 'snow'},
    75: {'ru': 'Сильный снегопад', 'en': 'Heavy snow', 'icon_day': 'snow.svg', 'icon_night': 'snow.svg', 'grad': 'snow'},
    77: {'ru': 'Снежные зерна', 'en': 'Snow grains', 'icon_day': 'snow.svg', 'icon_night': 'snow.svg', 'grad': 'snow'},
    80: {'ru': 'Ливень', 'en': 'Rain showers', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'rain'},
    81: {'ru': 'Умеренный ливень', 'en': 'Moderate showers', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'rain'},
    82: {'ru': 'Сильный ливень', 'en': 'Violent showers', 'icon_day': 'rain.svg', 'icon_night': 'rain.svg', 'grad': 'rain'},
    85: {'ru': 'Снегопад', 'en': 'Snow showers', 'icon_day': 'snow.svg', 'icon_night': 'snow.svg', 'grad': 'snow'},
    86: {'ru': 'Метель', 'en': 'Heavy snow showers', 'icon_day': 'snow.svg', 'icon_night': 'snow.svg', 'grad': 'snow'},
    95: {'ru': 'Гроза', 'en': 'Thunderstorm', 'icon_day': 'thunderstorm.svg', 'icon_night': 'thunderstorm.svg', 'grad': 'storm'},
    96: {'ru': 'Гроза с градом', 'en': 'Thunderstorm with hail', 'icon_day': 'thunderstorm.svg', 'icon_night': 'thunderstorm.svg', 'grad': 'storm'},
    99: {'ru': 'Сильная гроза с градом', 'en': 'Thunderstorm with heavy hail', 'icon_day': 'thunderstorm.svg', 'icon_night': 'thunderstorm.svg', 'grad': 'storm'}
}


CONDITION_NAMES = {
    0: {
        'ru': ('Солнечно', 'Ясно'),
        'en': ('Sunny', 'Clear'),
        'es': ('Soleado', 'Despejado'),
        'de': ('Sonnig', 'Klar'),
        'fr': ('Ensoleillé', 'Dégagé'),
        'zh': ('晴朗', '晴朗'),
        'ja': ('快晴', '快晴'),
        'it': ('Soleggiato', 'Sereno'),
        'pt': ('Ensolarado', 'Limpo'),
        'tr': ('Güneşli', 'Açık'),
        'uk': ('Сонячно', 'Ясно'),
        'kk': ('Ашық', 'Ашық'),
        'ar': ('مشمس', 'صافٍ'),
    },
    1: {
        'ru': 'В основном ясно', 'en': 'Mainly clear', 'es': 'Mayormente despejado', 'de': 'Überwiegend klar',
        'fr': 'Généralement dégagé', 'zh': '大部晴朗', 'ja': '概ね快晴', 'it': 'Prevalentemente sereno',
        'pt': 'Predominantemente limpo', 'tr': 'Çoğunlukla açık', 'uk': 'Переважно ясно', 'kk': 'Негізінен ашық', 'ar': 'صافٍ في معظمه'
    },
    2: {
        'ru': 'В основном облачно', 'en': 'Partly cloudy', 'es': 'Parcialmente nublado', 'de': 'Teilweise bewölkt',
        'fr': 'Partiellement nuageux', 'zh': '多云', 'ja': '晴れ時々曇り', 'it': 'Parzialmente nuvoloso',
        'pt': 'Parcialmente nublado', 'tr': 'Parçalı bulutlu', 'uk': 'Мінлива хмарність', 'kk': 'Ауыспалы бұлттылық', 'ar': 'غائم جزئياً'
    },
    3: {
        'ru': 'Облачно', 'en': 'Overcast', 'es': 'Nublado', 'de': 'Bedeckt',
        'fr': 'Couvert', 'zh': '阴天', 'ja': '曇り', 'it': 'Coperto',
        'pt': 'Nublado', 'tr': 'Kapalı', 'uk': 'Хмарно', 'kk': 'Бұлтты', 'ar': 'غائم'
    },
    45: {
        'ru': 'Туман', 'en': 'Fog', 'es': 'Niebla', 'de': 'Nebel',
        'fr': 'Brouillard', 'zh': '大雾', 'ja': '霧', 'it': 'Nebbia',
        'pt': 'Nevoeiro', 'tr': 'Sisli', 'uk': 'Туман', 'kk': 'Тұман', 'ar': 'ضباب'
    },
    48: {
        'ru': 'Туман с изморозью', 'en': 'Rime fog', 'es': 'Niebla escarchada', 'de': 'Nebelfrost',
        'fr': 'Brouillard givrant', 'zh': '雾凇', 'ja': '着氷性の霧', 'it': 'Nebbia con brina',
        'pt': 'Nevoeiro com geada', 'tr': 'Kırağı sisi', 'uk': 'Туман з памороззю', 'kk': 'Қыраулы тұман', 'ar': 'ضباب صقيعي'
    },
    51: {
        'ru': 'Изморось', 'en': 'Light drizzle', 'es': 'Llovizna ligera', 'de': 'Leichter Nieselregen',
        'fr': 'Bruine légère', 'zh': '微量毛毛雨', 'ja': '弱い霧雨', 'it': 'Pioviggine leggera',
        'pt': 'Garoa leve', 'tr': 'Hafif çiseleme', 'uk': 'Легка мряка', 'kk': 'Жеңіл сіркіреме', 'ar': 'رذاذ خفيف'
    },
    53: {
        'ru': 'Умеренная изморось', 'en': 'Moderate drizzle', 'es': 'Llovizna moderada', 'de': 'Mäßiger Nieselregen',
        'fr': 'Bruine modérée', 'zh': '中度毛毛雨', 'ja': '霧雨', 'it': 'Pioviggine moderata',
        'pt': 'Garoa moderada', 'tr': 'Orta çiseleme', 'uk': 'Помірна мряка', 'kk': 'Орташа сіркіреме', 'ar': 'رذاذ معتدل'
    },
    55: {
        'ru': 'Плотная изморось', 'en': 'Dense drizzle', 'es': 'Llovizna densa', 'de': 'Dichter Nieselregen',
        'fr': 'Bruine dense', 'zh': '浓密毛毛雨', 'ja': '濃い霧雨', 'it': 'Pioviggine fitta',
        'pt': 'Garoa densa', 'tr': 'Yoğun çiseleme', 'uk': 'Щільна мряка', 'kk': 'Қалың сіркіреме', 'ar': 'رذاذ كثيف'
    },
    56: {
        'ru': 'Ледяная изморось', 'en': 'Freezing drizzle', 'es': 'Llovizna helada', 'de': 'Gefrierender Nieselregen',
        'fr': 'Bruine verglaçante', 'zh': '冻毛毛雨', 'ja': '着氷性の霧雨', 'it': 'Pioviggine gelata',
        'pt': 'Garoa congelante', 'tr': 'Dondurucu çiseleme', 'uk': 'Крижана мряка', 'kk': 'Мұзды сіркіреме', 'ar': 'رذاذ متجمد'
    },
    57: {
        'ru': 'Плотная ледяная изморось', 'en': 'Freezing drizzle', 'es': 'Llovizna helada densa', 'de': 'Dichter gefrierender Nieselregen',
        'fr': 'Bruine verglaçante dense', 'zh': '浓冻毛毛雨', 'ja': '激しい着氷性の霧雨', 'it': 'Pioviggine gelata fitta',
        'pt': 'Garoa congelante densa', 'tr': 'Yoğun dondurucu çiseleme', 'uk': 'Щільна крижана мряка', 'kk': 'Қалың мұзды сіркіреме', 'ar': 'رذاذ متجمد كثيف'
    },
    61: {
        'ru': 'Небольшой дождь', 'en': 'Slight rain', 'es': 'Lluvia ligera', 'de': 'Leichter Regen',
        'fr': 'Pluie légère', 'zh': '小雨', 'ja': '小雨', 'it': 'Pioggia leggera',
        'pt': 'Chuva fraca', 'tr': 'Hafif yağmur', 'uk': 'Невеликий дощ', 'kk': 'Шамалы жаңбыр', 'ar': 'مطر خفيف'
    },
    63: {
        'ru': 'Дождь', 'en': 'Rain', 'es': 'Lluvia', 'de': 'Regen',
        'fr': 'Pluie', 'zh': '中雨', 'ja': '雨', 'it': 'Pioggia',
        'pt': 'Chuva', 'tr': 'Yağmur', 'uk': 'Дощ', 'kk': 'Жаңбыр', 'ar': 'مطر'
    },
    65: {
        'ru': 'Сильный дождь', 'en': 'Heavy rain', 'es': 'Lluvia fuerte', 'de': 'Starker Regen',
        'fr': 'Forte pluie', 'zh': '大雨', 'ja': '大雨', 'it': 'Pioggia forte',
        'pt': 'Chuva forte', 'tr': 'Kuvvetli yağmur', 'uk': 'Сильний дощ', 'kk': 'Қатты жаңбыр', 'ar': 'مطر غزير'
    },
    66: {
        'ru': 'Ледяной дождь', 'en': 'Freezing rain', 'es': 'Lluvia helada', 'de': 'Gefrierender Regen',
        'fr': 'Pluie verglaçante', 'zh': '冻雨', 'ja': '着氷性の雨', 'it': 'Pioggia congelantesi',
        'pt': 'Chuva congelante', 'tr': 'Dondurucu yağmur', 'uk': 'Крижаний дощ', 'kk': 'Мұзды жаңбыр', 'ar': 'مطر متجمد'
    },
    67: {
        'ru': 'Сильный ледяной дождь', 'en': 'Freezing rain', 'es': 'Lluvia helada fuerte', 'de': 'Starker gefrierender Regen',
        'fr': 'Forte pluie verglaçante', 'zh': '暴冻雨', 'ja': '激しい着氷性の雨', 'it': 'Forte pioggia gelata',
        'pt': 'Chuva congelante forte', 'tr': 'Şiddetli dondurucu yağmur', 'uk': 'Сильний крижаний дощ', 'kk': 'Қатты мұзды жаңбыр', 'ar': 'مطر متجمد غزير'
    },
    71: {
        'ru': 'Небольшой снег', 'en': 'Slight snow', 'es': 'Nieve ligera', 'de': 'Leichter Schneefall',
        'fr': 'Neige légère', 'zh': '小雪', 'ja': '小雪', 'it': 'Neve debole',
        'pt': 'Neve fraca', 'tr': 'Hafif kar', 'uk': 'Невеликий сніг', 'kk': 'Шамалы қар', 'ar': 'ثلج خفيف'
    },
    73: {
        'ru': 'Снегопад', 'en': 'Snow fall', 'es': 'Nevada', 'de': 'Schneefall',
        'fr': 'Chute de neige', 'zh': '降雪', 'ja': '雪', 'it': 'Nevicata',
        'pt': 'Nevasca', 'tr': 'Kar yağışı', 'uk': 'Снігопад', 'kk': 'Қар жауу', 'ar': 'تساقط الثلوج'
    },
    75: {
        'ru': 'Сильный снегопад', 'en': 'Heavy snow', 'es': 'Nieve intensa', 'de': 'Starker Schneefall',
        'fr': 'Forte chute de neige', 'zh': '大雪', 'ja': '大雪', 'it': 'Forte nevicata',
        'pt': 'Neve intensa', 'tr': 'Yoğun kar', 'uk': 'Сильний снігопад', 'kk': 'Қалың қар', 'ar': 'ثلج كثيف'
    },
    77: {
        'ru': 'Снежные зерна', 'en': 'Snow grains', 'es': 'Cinarra', 'de': 'Schneegriesel',
        'fr': 'Neige en grains', 'zh': '雪粒', 'ja': '霧雪', 'it': 'Neve granulosa',
        'pt': 'Grãos de neve', 'tr': 'Kar taneleri', 'uk': 'Снігові зерна', 'kk': 'Қар түйіршіктері', 'ar': 'حبيبات ثلجية'
    },
    80: {
        'ru': 'Ливень', 'en': 'Rain showers', 'es': 'Chubasco', 'de': 'Regenschauer',
        'fr': 'Averses de pluie', 'zh': '阵雨', 'ja': 'にわか雨', 'it': 'Rovescio di pioggia',
        'pt': 'Pancadas de chuva', 'tr': 'Sağanak yağış', 'uk': 'Злива', 'kk': 'Нөсер', 'ar': 'زخات مطر'
    },
    81: {
        'ru': 'Умеренный ливень', 'en': 'Moderate showers', 'es': 'Chubasco moderado', 'de': 'Mäßige Regenschauer',
        'fr': 'Averses modérées', 'zh': '中度阵雨', 'ja': '中程度のにわか雨', 'it': 'Rovesci moderati',
        'pt': 'Pancadas moderadas', 'tr': 'Orta şiddette sağanak', 'uk': 'Помірна злива', 'kk': 'Орташа нөсер', 'ar': 'زخات مطر معتدلة'
    },
    82: {
        'ru': 'Сильный ливень', 'en': 'Violent showers', 'es': 'Chubasco violento', 'de': 'Heftige Schauer',
        'fr': 'Violentes averses', 'zh': '暴雨', 'ja': '激しいにわか雨', 'it': 'Forti rovesci',
        'pt': 'Pancadas violentas', 'tr': 'Şiddetli sağanak', 'uk': 'Сильна злива', 'kk': 'Қатты нөсер', 'ar': 'زخات مطر عنيفة'
    },
    85: {
        'ru': 'Снегопад', 'en': 'Snow showers', 'es': 'Chubasco de nieve', 'de': 'Schneeschauer',
        'fr': 'Averses de neige', 'zh': '阵雪', 'ja': 'にわか雪', 'it': 'Rovesci di neve',
        'pt': 'Pancadas de neve', 'tr': 'Kar sağanağı', 'uk': 'Снігові зливи', 'kk': 'Қарлы нөсер', 'ar': 'زخات ثلجية'
    },
    86: {
        'ru': 'Метель', 'en': 'Heavy snow showers', 'es': 'Nevada fuerte', 'de': 'Starke Schneeschauer',
        'fr': 'Fortes averses de neige', 'zh': '暴雪', 'ja': '激しいにわか雪', 'it': 'Forti rovesci di neve',
        'pt': 'Pancadas de neve fortes', 'tr': 'Yoğun kar sağanağı', 'uk': 'Хуртовина', 'kk': 'Бұрқасын', 'ar': 'عاصفة ثلجية'
    },
    95: {
        'ru': 'Гроза', 'en': 'Thunderstorm', 'es': 'Tormenta', 'de': 'Gewitter',
        'fr': 'Orage', 'zh': '雷暴', 'ja': '雷雨', 'it': 'Temporale',
        'pt': 'Trovoada', 'tr': 'Gök gürültülü fırtına', 'uk': 'Гроза', 'kk': 'Найзағай', 'ar': 'عاصفة رعدية'
    },
    96: {
        'ru': 'Гроза с градом', 'en': 'Thunderstorm with hail', 'es': 'Tormenta con granizo', 'de': 'Gewitter mit Hagel',
        'fr': 'Orage avec grêle', 'zh': '雷暴伴有冰雹', 'ja': '雹を伴う雷雨', 'it': 'Temporale con grandine',
        'pt': 'Trovoada com granizo', 'tr': 'Dolu fırtınası', 'uk': 'Гроза з градом', 'kk': 'Бұршақты найзағай', 'ar': 'عاصفة رعدية مع بَرَد'
    },
    99: {
        'ru': 'Сильная гроза с градом', 'en': 'Thunderstorm with heavy hail', 'es': 'Tormenta fuerte con granizo', 'de': 'Schweres Gewitter mit Hagel',
        'fr': 'Orage violent avec grêle', 'zh': '强雷暴伴有冰雹', 'ja': '激しい雹を伴う雷雨', 'it': 'Forte temporale con grandine',
        'pt': 'Trovoada violenta com granizo', 'tr': 'Şiddetli dolulu fırtına', 'uk': 'Сильна гроза з градом', 'kk': 'Қатты бұршақты найзағай', 'ar': 'عاصفة رعدية شديدة مع بَرَد'
    }
}

def get_condition_text(code: int, lang: str = 'en', is_day: bool = True) -> str:
    if not lang:
        lang = 'en'
    data = CONDITION_NAMES.get(code, CONDITION_NAMES[0])
    val = data.get(lang, data.get('en', 'Clear'))
    if isinstance(val, tuple):
        return val[0] if is_day else val[1]
    return val

FALLBACK_NEWYORK = {
    'name_ru': 'Нью-Йорк',
    'name_en': 'New York',
    'country_ru': 'США',
    'country_en': 'USA',
    'city_name': 'New York',
    'country': 'USA',
    'lat': 40.7128,
    'lon': -74.0060,
    'temp': 24,
    'feels_like': 24,
    'humidity': 55,
    'wind_speed': 5.2,
    'wind_gusts': 6.0,
    'pressure_mm': 762,
    'dew_point': 12,
    'wind_direction': 225,
    'wind_cardinal': 'ЮЗ',
    'wind_desc': 'Юго-западный ветер',
    'feels_like_desc': 'Похоже на фактическую температуру.',
    'avg_diff_str': '+1°',
    'avg_norm_max': 23,
    'avg_desc': 'выше средней макс. температуры 23° сегодня.',
    'uv_index': 4.0,
    'uv_level': 'Умеренный',
    'uv_desc': 'Умеренный уровень на протяжении остальной части дня.',
    'visibility_km': 10,
    'visibility_desc': 'Отличная видимость.',
    'precipitation': 0.0,
    'precipitation_sum': 0.0,
    'precip_desc': 'Осадки не ожидаются.',
    'sunrise_str': '05:45',
    'sunset_str': '19:42',
    'pressure_desc': 'Нормальное давление.',
    'is_day': 1,
    'weather_code': 0,
    'condition_text': 'Солнечно',
    'temp_min': 9,
    'temp_max': 25,
    'grad_type': 'clear',
    'time_of_day': 'day',
    'grad_class': 'weather-grad-clear-day',
    'bg_class': 'weather-bg-clear-day',
    'icon_name': 'clear-day.svg',
    'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg'),
    'summary': 'Порывы ветра до 6 м/с. Солнечно до конца дня.',
    'overall_min': 8,
    'overall_max': 28,
    'hourly': [
        {'time': 'Сейчас', 'temp': 24, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'time': '16', 'temp': 25, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'time': '17', 'temp': 25, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'time': '18', 'temp': 24, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'time': '19', 'temp': 22, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'time': '20', 'temp': 20, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-night.svg')},
        {'time': '21', 'temp': 19, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-night.svg')},
        {'time': '22', 'temp': 18, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-night.svg')},
    ],
    'daily': [
        {'day': 'Сегодня', 'min': 9, 'max': 25, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'day': 'Ср', 'min': 8, 'max': 27, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'day': 'Чт', 'min': 9, 'max': 28, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'day': 'Пт', 'min': 11, 'max': 26, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
        {'day': 'Сб', 'min': 14, 'max': 24, 'code': 61, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'day': 'Вс', 'min': 13, 'max': 22, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'day': 'Пн', 'min': 12, 'max': 23, 'code': 1, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'day': 'Вт', 'min': 13, 'max': 25, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'day': 'Ср', 'min': 14, 'max': 26, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
        {'day': 'Чт', 'min': 15, 'max': 25, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
    ],
    'cached_at': time.time()
}

FALLBACK_MOSCOW = {
    'name_ru': 'Москва',
    'name_en': 'Moscow',
    'country_ru': 'Россия',
    'country_en': 'Russia',
    'city_name': 'Moscow',
    'country': 'Russia',
    'lat': 55.7522,
    'lon': 37.6156,
    'temp': 13,
    'feels_like': 11,
    'humidity': 72,
    'wind_speed': 4.2,
    'wind_gusts': 6.8,
    'pressure_mm': 752,
    'dew_point': 8,
    'wind_direction': 240,
    'wind_cardinal': 'ЮЗ',
    'wind_desc': 'Юго-западный ветер',
    'feels_like_desc': 'Прохладнее из-за влажности.',
    'avg_diff_str': '-1°',
    'avg_norm_max': 14,
    'avg_desc': 'около климатической нормы.',
    'uv_index': 1.5,
    'uv_level': 'Низкий',
    'uv_desc': 'Защита от солнца не требуется.',
    'visibility_km': 10,
    'visibility_desc': 'Хорошая видимость.',
    'precipitation': 0.0,
    'precipitation_sum': 0.2,
    'precip_desc': 'Без существенных осадков.',
    'sunrise_str': '06:35',
    'sunset_str': '18:50',
    'pressure_desc': 'Давление в пределах нормы.',
    'is_day': 1,
    'weather_code': 3,
    'condition_text': 'Пасмурно',
    'temp_min': 8,
    'temp_max': 14,
    'grad_type': 'clouds',
    'time_of_day': 'day',
    'grad_class': 'weather-grad-clouds-day',
    'bg_class': 'weather-bg-clouds-day',
    'icon_name': 'cloudy.svg',
    'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg'),
    'summary': 'Сплошная облачность. Температура днем до 14°.',
    'overall_min': 6,
    'overall_max': 16,
    'hourly': [
        {'time': 'Сейчас', 'temp': 13, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '16', 'temp': 14, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '17', 'temp': 13, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '18', 'temp': 12, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '19', 'temp': 11, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '20', 'temp': 10, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '21', 'temp': 9, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '22', 'temp': 8, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
    ],
    'daily': [
        {'day': 'Сегодня', 'min': 8, 'max': 14, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'day': 'Ср', 'min': 7, 'max': 13, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'day': 'Чт', 'min': 6, 'max': 12, 'code': 61, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'day': 'Пт', 'min': 7, 'max': 14, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
        {'day': 'Сб', 'min': 9, 'max': 15, 'code': 1, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'day': 'Вс', 'min': 8, 'max': 14, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
        {'day': 'Пн', 'min': 7, 'max': 13, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'day': 'Вт', 'min': 6, 'max': 12, 'code': 61, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'day': 'Ср', 'min': 5, 'max': 11, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'day': 'Чт', 'min': 6, 'max': 12, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
    ],
    'cached_at': time.time()
}

FALLBACK_NOVOKUZNETSK = {
    'name_ru': 'Новокузнецк',
    'name_en': 'Novokuznetsk',
    'country_ru': 'Россия',
    'country_en': 'Russia',
    'city_name': 'Novokuznetsk',
    'country': 'Russia',
    'lat': 53.7557,
    'lon': 87.1099,
    'temp': 25,
    'feels_like': 25,
    'humidity': 48,
    'wind_speed': 2.0,
    'wind_gusts': 2.0,
    'pressure_mm': 754,
    'dew_point': 12,
    'wind_direction': 180,
    'wind_cardinal': 'Ю',
    'wind_desc': 'Южный ветер',
    'feels_like_desc': 'Похоже на фактическую температуру.',
    'avg_diff_str': '+3°',
    'avg_norm_max': 22,
    'avg_desc': 'выше средней макс. температуры 22° сегодня.',
    'uv_index': 3.0,
    'uv_level': 'Умеренный',
    'uv_desc': 'Умеренный уровень на протяжении остальной части дня.',
    'visibility_km': 10,
    'visibility_desc': 'Отличная видимость.',
    'precipitation': 0.0,
    'precipitation_sum': 0.0,
    'precip_desc': 'Осадков не ожидается.',
    'sunrise_str': '06:40',
    'sunset_str': '19:32',
    'pressure_desc': 'Нормальное давление.',
    'is_day': 1,
    'weather_code': 2,
    'condition_text': 'В основном облачно',
    'temp_min': 9,
    'temp_max': 27,
    'grad_type': 'mostly_cloudy',
    'time_of_day': 'day',
    'grad_class': 'weather-grad-clouds-day',
    'bg_class': 'weather-bg-clouds-day',
    'icon_name': 'partly-cloudy-day.svg',
    'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg'),
    'summary': 'Порывы ветра до 2 м/с. Облачная погода до конца дня.',
    'is_mostly': True,
    'overall_min': 9,
    'overall_max': 27,
    'hourly': [
        {'time': 'Сейчас', 'temp': 25, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
        {'time': '19', 'temp': 23, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
        {'time': '19:32', 'temp': 22, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'sunset.svg'), 'is_sunset': True},
        {'time': '20', 'temp': 21, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-night.svg')},
        {'time': '21', 'temp': 20, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-night.svg')},
        {'time': '22', 'temp': 18, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-night.svg')},
        {'time': '23', 'temp': 17, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-night.svg')},
        {'time': '00', 'temp': 15, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-night.svg')},
    ],
    'daily': [
        {'day': 'Сегодня', 'min': 9, 'max': 27, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
        {'day': 'Пн', 'min': 12, 'max': 24, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'day': 'Вт', 'min': 13, 'max': 20, 'code': 61, 'prob': 70, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'day': 'Ср', 'min': 11, 'max': 21, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
        {'day': 'Чт', 'min': 10, 'max': 22, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'day': 'Пт', 'min': 11, 'max': 23, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
        {'day': 'Сб', 'min': 12, 'max': 24, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'day': 'Вс', 'min': 10, 'max': 20, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'day': 'Пн', 'min': 9, 'max': 19, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'day': 'Вт', 'min': 10, 'max': 21, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
    ],
    'cached_at': time.time()
}

FALLBACK_KALININGRAD = {
    'name_ru': 'Калининград',
    'name_en': 'Kaliningrad',
    'country_ru': 'Россия',
    'country_en': 'Russia',
    'city_name': 'Kaliningrad',
    'country': 'Russia',
    'lat': 54.7104,
    'lon': 20.4522,
    'temp': 18,
    'feels_like': 18,
    'humidity': 68,
    'wind_speed': 4.0,
    'wind_gusts': 6.0,
    'pressure_mm': 758,
    'dew_point': 11,
    'wind_direction': 260,
    'wind_cardinal': 'З',
    'wind_desc': 'Западный ветер',
    'feels_like_desc': 'Похоже на фактическую температуру.',
    'avg_diff_str': '+1°',
    'avg_norm_max': 17,
    'avg_desc': 'около средней макс. температуры 17° сегодня.',
    'uv_index': 2.0,
    'uv_level': 'Низкий',
    'uv_desc': 'Низкий уровень на протяжении остальной части дня.',
    'visibility_km': 10,
    'visibility_desc': 'Хорошая видимость.',
    'precipitation': 0.1,
    'precipitation_sum': 0.5,
    'precip_desc': 'Ожидается дождливая погода около 13:00.',
    'sunrise_str': '06:48',
    'sunset_str': '19:55',
    'pressure_desc': 'Нормальное давление.',
    'is_day': 1,
    'weather_code': 3,
    'condition_text': 'Облачно',
    'temp_min': 11,
    'temp_max': 19,
    'grad_type': 'clouds',
    'time_of_day': 'day',
    'grad_class': 'weather-grad-clouds-day',
    'bg_class': 'weather-bg-clouds-day',
    'icon_name': 'cloudy.svg',
    'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg'),
    'summary': 'Ожидается дождливая погода около 13:00. Порывы ветра до 6 м/с.',
    'overall_min': 11,
    'overall_max': 20,
    'hourly': [
        {'time': 'Сейчас', 'temp': 18, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '13', 'temp': 18, 'code': 61, 'prob': 15, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'time': '14', 'temp': 19, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '15', 'temp': 19, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '16', 'temp': 19, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '17', 'temp': 18, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'time': '18', 'temp': 17, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
    ],
    'daily': [
        {'day': 'Сегодня', 'min': 11, 'max': 19, 'code': 61, 'prob': 45, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'day': 'Пн', 'min': 13, 'max': 20, 'code': 61, 'prob': 60, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'day': 'Вт', 'min': 13, 'max': 18, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'day': 'Ср', 'min': 12, 'max': 18, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'day': 'Чт', 'min': 11, 'max': 17, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
        {'day': 'Пт', 'min': 10, 'max': 17, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'day': 'Сб', 'min': 11, 'max': 18, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
    ],
    'cached_at': time.time()
}

FALLBACK_SPB = {
    'name_ru': 'Санкт-Петербург',
    'name_en': 'Saint Petersburg',
    'country_ru': 'Россия',
    'country_en': 'Russia',
    'city_name': 'Saint Petersburg',
    'country': 'Russia',
    'lat': 59.9386,
    'lon': 30.3141,
    'temp': 16,
    'feels_like': 15,
    'humidity': 86,
    'wind_speed': 5.5,
    'wind_gusts': 8.0,
    'pressure_mm': 755,
    'dew_point': 13,
    'wind_direction': 240,
    'wind_cardinal': 'ЮЗ',
    'wind_desc': 'Юго-западный ветер',
    'feels_like_desc': 'Из-за ветра ощущается прохладнее.',
    'avg_diff_str': '+1°',
    'avg_norm_max': 15,
    'avg_desc': 'около средней макс. температуры 15° сегодня.',
    'uv_index': 1.0,
    'uv_level': 'Низкий',
    'uv_desc': 'Низкий уровень на протяжении остальной части дня.',
    'visibility_km': 9,
    'visibility_desc': 'Хорошая видимость.',
    'precipitation': 2.4,
    'precipitation_sum': 7.8,
    'precip_desc': 'Дождливая погода до конца дня.',
    'sunrise_str': '06:22',
    'sunset_str': '19:40',
    'pressure_desc': 'Нормальное давление.',
    'is_day': 1,
    'weather_code': 63,
    'condition_text': 'Дождь',
    'temp_min': 12,
    'temp_max': 16,
    'grad_type': 'rain',
    'time_of_day': 'day',
    'grad_class': 'weather-grad-rain-day',
    'bg_class': 'weather-bg-rain-day',
    'icon_name': 'rain.svg',
    'icon_file': os.path.join(ICONS_DIR, 'rain.svg'),
    'summary': 'Порывы ветра до 8 м/с. Дождливая погода до конца дня.',
    'overall_min': 9,
    'overall_max': 16,
    'hourly': [
        {'time': 'Сейчас', 'temp': 16, 'code': 63, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'time': '15', 'temp': 16, 'code': 63, 'prob': 55, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'time': '16', 'temp': 16, 'code': 63, 'prob': 60, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'time': '17', 'temp': 15, 'code': 63, 'prob': 60, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'time': '18', 'temp': 15, 'code': 63, 'prob': 55, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'time': '19', 'temp': 14, 'code': 63, 'prob': 50, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'time': '20', 'temp': 13, 'code': 61, 'prob': 40, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
    ],
    'daily': [
        {'day': 'Сегодня', 'min': 12, 'max': 16, 'code': 63, 'prob': 90, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'day': 'Пн', 'min': 11, 'max': 16, 'code': 63, 'prob': 55, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'day': 'Вт', 'min': 9, 'max': 15, 'code': 2, 'icon_file': os.path.join(ICONS_DIR, 'partly-cloudy-day.svg')},
        {'day': 'Ср', 'min': 8, 'max': 14, 'code': 3, 'icon_file': os.path.join(ICONS_DIR, 'cloudy.svg')},
        {'day': 'Чт', 'min': 9, 'max': 16, 'code': 1, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
    ],
    'cached_at': time.time()
}

FALLBACK_DRIZZLE = {
    'name_ru': 'Санкт-Петербург',
    'name_en': 'Saint Petersburg',
    'country_ru': 'Россия',
    'country_en': 'Russia',
    'city_name': 'Saint Petersburg',
    'country': 'Russia',
    'lat': 59.9386,
    'lon': 30.3141,
    'temp': 15,
    'feels_like': 14,
    'humidity': 84,
    'wind_speed': 4.8,
    'wind_gusts': 7.0,
    'pressure_mm': 757,
    'dew_point': 12,
    'wind_direction': 240,
    'wind_cardinal': 'ЮЗ',
    'wind_desc': 'Юго-западный ветер',
    'feels_like_desc': 'Похоже на фактическую температуру.',
    'avg_diff_str': '+1°',
    'avg_norm_max': 15,
    'avg_desc': 'около нормы для этого времени года.',
    'uv_index': 1.0,
    'uv_level': 'Низкий',
    'uv_desc': 'Низкий уровень на протяжении остальной части дня.',
    'visibility_km': 10,
    'visibility_desc': 'Хорошая видимость.',
    'precipitation': 0.8,
    'precipitation_sum': 2.4,
    'precip_desc': 'Ожидается моросящий дождь весь день.',
    'sunrise_str': '06:22',
    'sunset_str': '19:40',
    'pressure_desc': 'Нормальное давление.',
    'is_day': 1,
    'weather_code': 51,
    'condition_text': 'Изморось',
    'temp_min': 11,
    'temp_max': 16,
    'grad_type': 'drizzle',
    'time_of_day': 'day',
    'grad_class': 'weather-grad-drizzle-day',
    'bg_class': 'weather-bg-drizzle-day',
    'icon_name': 'rain.svg',
    'icon_file': os.path.join(ICONS_DIR, 'rain.svg'),
    'summary': 'Порывы ветра до 7 м/с. Моросящий дождь весь день.',
    'overall_min': 9,
    'overall_max': 16,
    'hourly': [
        {'time': 'Сейчас', 'temp': 15, 'code': 51, 'prob': 40, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'time': '11', 'temp': 15, 'code': 51, 'prob': 40, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'time': '12', 'temp': 16, 'code': 51, 'prob': 50, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
    ],
    'daily': [
        {'day': 'Сегодня', 'min': 11, 'max': 16, 'code': 51, 'prob': 90, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'day': 'Пн', 'min': 11, 'max': 16, 'code': 51, 'prob': 55, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
    ],
    'cached_at': time.time()
}

FALLBACK_ONTARIO = {
    'name_ru': 'Онтарио',
    'name_en': 'Ontario',
    'country_ru': 'Канада',
    'country_en': 'Canada',
    'city_name': 'Ontario',
    'country': 'Canada',
    'lat': 43.6532,
    'lon': -79.3832,
    'temp': 9,
    'feels_like': 8,
    'humidity': 72,
    'wind_speed': 3.8,
    'wind_gusts': 6.0,
    'pressure_mm': 760,
    'dew_point': 4,
    'wind_direction': 310,
    'wind_cardinal': 'СЗ',
    'wind_desc': 'Северо-западный ветер',
    'feels_like_desc': 'Похоже на фактическую температуру.',
    'avg_diff_str': '-1°',
    'avg_norm_max': 10,
    'avg_desc': 'около нормы для этого времени года.',
    'uv_index': 0.0,
    'uv_level': 'Низкий',
    'uv_desc': 'Низкий уровень на протяжении остальной части дня.',
    'visibility_km': 10,
    'visibility_desc': 'Отличная видимость.',
    'precipitation': 0.0,
    'precipitation_sum': 0.0,
    'precip_desc': 'Осадков не ожидается.',
    'sunrise_str': '07:17',
    'sunset_str': '19:35',
    'pressure_desc': 'Нормальное давление.',
    'is_day': 1,
    'weather_code': 1,
    'condition_text': 'В основном ясно',
    'temp_min': 8,
    'temp_max': 13,
    'grad_type': 'clear',
    'time_of_day': 'dusk',
    'grad_class': 'weather-grad-clear-dusk',
    'bg_class': 'weather-bg-clear-dusk',
    'icon_name': 'clear-day.svg',
    'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg'),
    'summary': 'Ожидается дождливая погода около 13:00. Порывы ветра до 6 м/с.',
    'is_mostly': True,
    'overall_min': 6,
    'overall_max': 18,
    'hourly': [
        {'time': 'Сейчас', 'temp': 9, 'code': 1, 'icon_file': os.path.join(ICONS_DIR, 'clear-night.svg')},
        {'time': '07:17', 'temp': 9, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'sunrise.svg'), 'is_sunrise': True},
        {'time': '08', 'temp': 9, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'time': '09', 'temp': 10, 'code': 1, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'time': '10', 'temp': 11, 'code': 1, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
    ],
    'daily': [
        {'day': 'Сегодня', 'min': 8, 'max': 13, 'code': 61, 'prob': 35, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
        {'day': 'Пн', 'min': 6, 'max': 18, 'code': 0, 'icon_file': os.path.join(ICONS_DIR, 'clear-day.svg')},
        {'day': 'Вт', 'min': 11, 'max': 18, 'code': 61, 'prob': 80, 'icon_file': os.path.join(ICONS_DIR, 'rain.svg')},
    ],
    'cached_at': time.time()
}


WEEKDAY_NAMES = {
    'ru': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
    'en': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    'es': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
    'de': ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'],
    'fr': ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
    'zh': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
    'ja': ['月', '火', '水', '木', '金', '土', '日'],
    'it': ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'],
    'pt': ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'],
    'tr': ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'],
    'uk': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд'],
    'kk': ['Дс', 'Сс', 'Ср', 'Бс', 'Жм', 'Сн', 'Жс'],
    'ar': ['الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
}


WEEKDAY_LETTERS = {
    'ru': ['П', 'В', 'С', 'Ч', 'П', 'С', 'В'],
    'en': ['M', 'T', 'W', 'T', 'F', 'S', 'S'],
    'es': ['L', 'M', 'X', 'J', 'V', 'S', 'D'],
    'de': ['M', 'D', 'M', 'D', 'F', 'S', 'S'],
    'fr': ['L', 'M', 'M', 'J', 'V', 'S', 'D'],
    'zh': ['一', '二', '三', '四', '五', '六', '日'],
    'ja': ['月', '火', '水', '木', '金', '土', '日'],
    'it': ['L', 'M', 'M', 'G', 'V', 'S', 'D'],
    'pt': ['S', 'T', 'Q', 'Q', 'S', 'S', 'D'],
    'tr': ['P', 'S', 'Ç', 'P', 'C', 'C', 'P'],
    'uk': ['П', 'В', 'С', 'Ч', 'П', 'С', 'Н'],
    'kk': ['Д', 'С', 'С', 'Б', 'Ж', 'С', 'Ж'],
    'ar': ['ن', 'ث', 'ر', 'خ', 'ج', 'س', 'ح']
}

WEEKDAY_FULL = {
    'ru': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
    'en': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
    'es': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'],
    'de': ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'],
    'fr': ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'],
    'zh': ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'],
    'ja': ['月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日', '日曜日'],
    'it': ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica'],
    'pt': ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo'],
    'tr': ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar'],
    'uk': ['Понеділок', 'Вівторок', 'Середа', 'Четвер', "П'ятниця", 'Субота', 'Неділя'],
    'kk': ['Дүйсенбі', 'Сейсенбі', 'Сәрсенбі', 'Бейсенбі', 'Жұма', 'Сенбі', 'Жексенбі'],
    'ar': ['الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
}

MONTH_NAMES_GENITIVE = {
    'ru': ['', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
    'en': ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    'es': ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'],
    'de': ['', 'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
    'fr': ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
    'zh': ['', '1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
    'ja': ['', '1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
    'it': ['', 'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'octobre', 'novembre', 'dicembre'],
    'pt': ['', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'],
    'tr': ['', 'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'],
    'uk': ['', 'січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня'],
    'kk': ['', 'қаңтар', 'ақпан', 'наурыз', 'сәуір', 'мамыр', 'маусым', 'шілде', 'тамыз', 'қыркүйек', 'қазан', 'қараша', 'желтоқсан'],
    'ar': ['', 'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
}


def format_full_date(dt: datetime, lang: str = 'en') -> str:
    if not lang or lang not in WEEKDAY_FULL:
        lang = 'en'
    w_idx = dt.weekday()
    w_full = WEEKDAY_FULL.get(lang, WEEKDAY_FULL['en'])[w_idx % 7]
    m_list = MONTH_NAMES_GENITIVE.get(lang, MONTH_NAMES_GENITIVE['en'])
    m_name = m_list[dt.month if 1 <= dt.month <= 12 else 1]

    if lang == 'ru':
        return f"{w_full}, {dt.day} {m_name} {dt.year} г."
    elif lang == 'uk':
        return f"{w_full}, {dt.day} {m_name} {dt.year} р."
    elif lang == 'kk':
        return f"{w_full}, {dt.year} жылғы {dt.day} {m_name}"
    elif lang in ('zh', 'ja'):
        return f"{dt.year}年{m_name}{dt.day}日 {w_full}"
    elif lang in ('es', 'pt'):
        return f"{w_full}, {dt.day} de {m_name} de {dt.year}"
    elif lang == 'de':
        return f"{w_full}, {dt.day}. {m_name} {dt.year}"
    elif lang in ('fr', 'it'):
        return f"{w_full} {dt.day} {m_name} {dt.year}"
    elif lang == 'tr':
        return f"{dt.day} {m_name} {dt.year} {w_full}"
    elif lang == 'ar':
        return f"{w_full}، {dt.day} {m_name} {dt.year}"
    else:
        return f"{w_full}, {m_name} {dt.day}, {dt.year}"


def get_smart_day_summary(
    day_info: dict,
    lang: str = 'en',
    is_today: bool = False,
    temp_unit: str = 'celsius',
    current_temp: int = None
) -> str:
    if not lang:
        lang = get_current_language()

    code = day_info.get('code', day_info.get('weather_code', 0))
    cond_text = get_condition_text(code, lang=lang, is_day=True)

    t_min = convert_temp(day_info.get('min', day_info.get('temp_min', 0)), temp_unit)
    t_max = convert_temp(day_info.get('max', day_info.get('temp_max', 0)), temp_unit)
    app_min = convert_temp(day_info.get('apparent_min', day_info.get('min', 0)), temp_unit)
    app_max = convert_temp(day_info.get('apparent_max', day_info.get('max', 0)), temp_unit)

    if is_today:
        if current_temp is not None:
            now_t = convert_temp(current_temp, temp_unit)
        else:
            now_t = convert_temp(day_info.get('temp', day_info.get('max', 20)), temp_unit)

        hum = day_info.get('humidity', 50)
        wind = day_info.get('wind_speed', 10)
        feels_like = convert_temp(day_info.get('feels_like', now_t), temp_unit)

        if hum >= 65 and feels_like > now_t:
            feels_desc = t('weather_feels_humidity_warmer')
        elif wind >= 15 and feels_like < now_t:
            feels_desc = t('weather_feels_wind_cooler')
        elif feels_like < now_t - 1:
            feels_desc = t('weather_feels_cooler')
        elif feels_like > now_t + 1:
            feels_desc = t('weather_feels_warmer')
        else:
            feels_desc = t('weather_feels_similar')

        s_now = t('weather_summary_now_cond', temp=now_t, cond=cond_text.lower())
        s_range = t('weather_summary_range_today', min=t_min, max=t_max, app_min=app_min, app_max=app_max)
        return f"{s_now} {feels_desc} {s_range}".strip()
    else:
        p_prob = day_info.get('precip_prob_max', day_info.get('precipitation_probability', 0))
        return t('weather_summary_future', cond=cond_text.lower(), min=t_min, max=t_max, app_min=app_min, app_max=app_max, prob=p_prob)


COMPASS_CARDINALS_4: dict[str, tuple[str, str, str, str]] = {
    "ru": ("С", "В", "Ю", "З"),
    "en": ("N", "E", "S", "W"),
    "es": ("N", "E", "S", "O"),
    "de": ("N", "O", "S", "W"),
    "fr": ("N", "E", "S", "O"),
    "zh": ("北", "东", "南", "西"),
    "ja": ("北", "東", "南", "西"),
    "it": ("N", "E", "S", "O"),
    "pt": ("N", "L", "S", "O"),
    "tr": ("K", "D", "G", "B"),
    "uk": ("Пн", "Сх", "Пд", "Зх"),
    "kk": ("С", "Ш", "О", "Б"),
    "ar": ("ش", "ق", "ج", "غ"),
}

WIND_DIRECTIONS_8: dict[str, list[tuple[str, str]]] = {
    "ru": [
        ("С", "Северный ветер"),
        ("СВ", "Северо-восточный ветер"),
        ("В", "Восточный ветер"),
        ("ЮВ", "Юго-восточный ветер"),
        ("Ю", "Южный ветер"),
        ("ЮЗ", "Юго-западный ветер"),
        ("З", "Западный ветер"),
        ("СЗ", "Северо-западный ветер"),
    ],
    "en": [
        ("N", "North wind"),
        ("NE", "Northeast wind"),
        ("E", "East wind"),
        ("SE", "Southeast wind"),
        ("S", "South wind"),
        ("SW", "Southwest wind"),
        ("W", "West wind"),
        ("NW", "Northwest wind"),
    ],
    "es": [
        ("N", "Viento del norte"),
        ("NE", "Viento del noreste"),
        ("E", "Viento del este"),
        ("SE", "Viento del sureste"),
        ("S", "Viento del sur"),
        ("SW", "Viento del suroeste"),
        ("W", "Viento del oeste"),
        ("NW", "Viento del noroeste"),
    ],
    "de": [
        ("N", "Nordwind"),
        ("NO", "Nordostwind"),
        ("O", "Ostwind"),
        ("SO", "Südostwind"),
        ("S", "Südwind"),
        ("SW", "Südwestwind"),
        ("W", "Westwind"),
        ("NW", "Nordwestwind"),
    ],
    "fr": [
        ("N", "Vent du nord"),
        ("NE", "Vent du nord-est"),
        ("E", "Vent de l'est"),
        ("SE", "Vent du sud-est"),
        ("S", "Vent du sud"),
        ("SW", "Vent du sud-ouest"),
        ("O", "Vent de l'ouest"),
        ("NO", "Vent du nord-ouest"),
    ],
    "zh": [
        ("北", "北风"),
        ("东北", "东北风"),
        ("东", "东风"),
        ("东南", "东南风"),
        ("南", "南风"),
        ("西南", "西南风"),
        ("西", "西风"),
        ("西北", "西北风"),
    ],
    "ja": [
        ("北", "北風"),
        ("北東", "北東の風"),
        ("東", "東風"),
        ("南東", "南東の風"),
        ("南", "南風"),
        ("南西", "南西の風"),
        ("西", "西風"),
        ("北西", "北西の風"),
    ],
    "it": [
        ("N", "Vento da nord"),
        ("NE", "Vento da nord-est"),
        ("E", "Vento da est"),
        ("SE", "Vento da sud-est"),
        ("S", "Vento da sud"),
        ("SW", "Vento da sud-ovest"),
        ("O", "Vento da ovest"),
        ("NO", "Vento da nord-ovest"),
    ],
    "pt": [
        ("N", "Vento do norte"),
        ("NE", "Vento do nordeste"),
        ("L", "Vento do leste"),
        ("SE", "Vento do sudeste"),
        ("S", "Vento do sul"),
        ("SO", "Vento do sudoeste"),
        ("O", "Vento do oeste"),
        ("NO", "Vento do noroeste"),
    ],
    "tr": [
        ("K", "Kuzey rüzgarı"),
        ("KD", "Kuzeydoğu rüzgarı"),
        ("D", "Doğu rüzgarı"),
        ("GD", "Güneydoğu rüzgarı"),
        ("G", "Güney rüzgarı"),
        ("GB", "Güneybatı rüzgarı"),
        ("B", "Batı rüzgarı"),
        ("KB", "Kuzeybatı rüzgarı"),
    ],
    "uk": [
        ("Пн", "Північний вітер"),
        ("Пн-Сх", "Північно-східний вітер"),
        ("Сх", "Східний вітер"),
        ("Пд-Сх", "Південно-східний вітер"),
        ("Пд", "Південний вітер"),
        ("Пд-Зх", "Південно-західний вітер"),
        ("Зх", "Західний вітер"),
        ("Пн-Зх", "Північно-західний вітер"),
    ],
    "kk": [
        ("С", "Солтүстік желі"),
        ("СШ", "Солтүстік-шығыс желі"),
        ("Ш", "Шығыс желі"),
        ("ОШ", "Оңтүстік-шығыс желі"),
        ("О", "Оңтүстік желі"),
        ("ОБ", "Оңтүстік-батыс желі"),
        ("Б", "Батыс желі"),
        ("СБ", "Солтүстік-батыс желі"),
    ],
    "ar": [
        ("ش", "رياح شمالية"),
        ("ش.ش", "رياح شمالية شرقية"),
        ("ق", "رياح شرقية"),
        ("ج.ش", "رياح جنوبية شرقية"),
        ("ج", "رياح جنوبية"),
        ("ج.غ", "رياح جنوبية غربية"),
        ("غ", "رياح غربية"),
        ("ش.غ", "رياح شمالية غربية"),
    ],
}

WIND_DIRECTIONS_16: dict[str, list[str]] = {
    "ru": ["С", "ССВ", "СВ", "ВСВ", "В", "ВЮВ", "ЮВ", "ЮЮВ", "Ю", "ЮЮЗ", "ЮЗ", "ЗЮЗ", "З", "ЗСЗ", "СЗ", "ССЗ"],
    "en": ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"],
    "es": ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"],
    "de": ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"],
    "fr": ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"],
    "zh": ["北", "北东北", "东北", "东东北", "东", "东东南", "东南", "南东南", "南", "南西南", "西南", "西西南", "西", "西西北", "西北", "北西北"],
    "ja": ["北", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東", "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西"],
    "it": ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"],
    "pt": ["N", "NNE", "NE", "ENE", "L", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"],
    "tr": ["K", "KKD", "KD", "DKD", "D", "DGD", "GD", "GGD", "G", "GGB", "GB", "BGB", "B", "BKB", "KB", "KKB"],
    "uk": ["Пн", "Пн-Пн-Сх", "Пн-Сх", "Сх-Пн-Сх", "Сх", "Сх-Пд-Сх", "Пд-Сх", "Пд-Пд-Сх", "Пд", "Пд-Пд-Зх", "Пд-Зх", "Зх-Пд-Зх", "Зх", "Зх-Пн-Зх", "Пн-Зх", "Пн-Пн-Зх"],
    "kk": ["С", "ССШ", "СШ", "ШСШ", "Ш", "ШОШ", "ОШ", "ООШ", "О", "ООБ", "ОБ", "БОБ", "Б", "БСБ", "СБ", "ССБ"],
    "ar": ["ش", "ش.ش.ش", "ش.ش", "ش.ش.ق", "ق", "ق.ج.ش", "ج.ش", "ج.ج.ش", "ج", "ج.ج.غ", "ج.غ", "غ.ج.غ", "غ", "غ.ش.غ", "ش.غ", "ش.ش.غ"],
}


def get_wind_direction_info(deg: float, lang: str = 'ru') -> tuple[str, str]:
    deg = (float(deg) % 360 + 360) % 360
    if not lang:
        lang = 'ru'
    dirs = WIND_DIRECTIONS_8.get(lang, WIND_DIRECTIONS_8.get('en', WIND_DIRECTIONS_8['ru']))
    idx = int((deg + 22.5) // 45) % 8
    return dirs[idx][0], dirs[idx][1]

def get_weekday_name(weekday_idx: int, lang: str = 'en') -> str:
    if not lang:
        lang = 'en'
    names = WEEKDAY_NAMES.get(lang, WEEKDAY_NAMES.get('en', ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']))
    return names[weekday_idx % 7]


def ensure_days_detailed(data: dict, lang: str = "ru") -> dict:
    if data.get("days_detailed") and data.get("yesterday_comp") and len(data["days_detailed"]) > 0 and "hourly_uvs" in data["days_detailed"][0] and "min" in data["days_detailed"][0]:
        first_date = data["days_detailed"][0].get("date_str")
        offset = data.get("utc_offset_seconds", 0)
        from datetime import timezone as dt_timezone
        city_today = (datetime.now(dt_timezone.utc) + timedelta(seconds=offset)).strftime("%Y-%m-%d")
        if not first_date or first_date == city_today:
            return data

    today_dt = datetime.now()
    today_w = today_dt.weekday()
    temp = data.get("temp", 20)
    t_min = data.get("temp_min", temp - 5)
    t_max = data.get("temp_max", temp + 5)

    yesterday_min = t_min - 1
    yesterday_max = t_max
    diff_yesterday = t_max - yesterday_max

    if abs(diff_yesterday) < 0.5:
        comp_summary = t("weather_comp_today_same", lang=lang)
    elif diff_yesterday > 0:
        comp_summary = t("weather_comp_today_warmer", diff=round(abs(diff_yesterday)), lang=lang)
    else:
        comp_summary = t("weather_comp_today_cooler", diff=round(abs(diff_yesterday)), lang=lang)

    data["yesterday_comp"] = {
        "summary": comp_summary,
        "diff_max": diff_yesterday,
        "today_min": t_min,
        "today_max": t_max,
        "yesterday_min": yesterday_min,
        "yesterday_max": yesterday_max,
        "yesterday_uv_max": data.get("uv_index", 3.5),
        "yesterday_wind_max": data.get("wind_speed", 12),
        "yesterday_gust_max": data.get("wind_gust", 18),
        "yesterday_precip_sum": 0.0,
        "yesterday_min_humidity": max(20, data.get("humidity", 55) - 15),
        "yesterday_max_humidity": min(100, data.get("humidity", 55) + 15),
        "yesterday_avg_humidity": data.get("humidity", 55),
        "yesterday_min_visibility_km": 10.0,
        "yesterday_max_visibility_km": 10.0,
        "yesterday_min_pressure_mm": data.get("pressure_mm", 752) - 2,
        "yesterday_max_pressure_mm": data.get("pressure_mm", 752) + 2,
        "yesterday_avg_pressure_mm": data.get("pressure_mm", 752),
    }

    days_detailed = []
    daily_items = data.get("daily", [])
    w_letters = WEEKDAY_LETTERS.get(lang, WEEKDAY_LETTERS["en"])

    for i in range(max(7, len(daily_items))):
        d_item = daily_items[i] if i < len(daily_items) else {}
        d_offset = i
        cur_dt = today_dt + timedelta(days=i)
        w_idx = cur_dt.weekday()
        w_letter = w_letters[w_idx % 7]

        d_min = d_item.get("min", t_min + (i % 3) - 1)
        d_max = d_item.get("max", t_max + (i % 4) - 2)
        app_min = d_min - 1
        app_max = d_max + 1
        w_code = d_item.get("code", data.get("weather_code", 0))

        full_date_str = format_full_date(cur_dt, lang)

        # 24 hour synthetic curve
        h24_temps = []
        h24_apps = []
        h24_probs = []
        h24_precips = []
        h24_codes = []
        h24_is_days = []
        h24_winds = []
        h24_wind_dirs = []
        h24_gusts = []
        h24_uvs = []
        h24_hums = []
        h24_dews = []
        h24_vis_km = []
        h24_press_mm = []
        h24_press_hpa = []

        for h in range(24):
            # Diurnal temperature cycle: peak around 15:00, trough around 05:00
            diurnal = math.sin((h - 9) / 24.0 * 2 * math.pi) # -1 at 3am, +1 at 3pm
            val = round(d_min + (d_max - d_min) * (diurnal + 1.0) / 2.0)
            h24_temps.append(val)
            h24_apps.append(val + (1 if h in range(11, 17) else -1))
            h24_probs.append(0 if w_code < 50 else min(100, (w_code - 40) * 15))
            h24_precips.append(0.0 if w_code < 50 else 0.5)
            h24_codes.append(w_code)
            h24_is_days.append(1 if 6 <= h < 21 else 0)

            # Synthetic 24h metrics for detailed analysis modes
            uv_val = round(max(0.0, math.sin(max(0, h - 6) / 14.0 * math.pi) * (3.2 + (i % 3) * 0.8)), 1) if 6 <= h <= 19 else 0.0
            h24_uvs.append(uv_val)
            w_spd = round(10 + 5 * math.sin((h - 4) / 24.0 * 2 * math.pi) + (i % 3))
            h24_winds.append(max(2, w_spd))
            h24_gusts.append(max(5, w_spd + 8 + (i % 4)))
            h24_wind_dirs.append(int((280 + h * 3 + i * 25) % 360))
            hum_val = round(68 - 20 * math.sin((h - 9) / 24.0 * 2 * math.pi) + (i % 5))
            h24_hums.append(max(20, min(98, hum_val)))
            h24_dews.append(round(val - (100 - hum_val) / 5.0))
            h24_vis_km.append(10.0)
            p_val = round(752 + 3 * math.sin((h - 5) / 24.0 * 2 * math.pi) - i)
            h24_press_mm.append(p_val)
            h24_press_hpa.append(round(p_val / 0.75006))

        day_item_tmp = {
            'code': w_code,
            'min': d_min,
            'max': d_max,
            'apparent_min': app_min,
            'apparent_max': app_max,
            'temp': temp,
            'humidity': data.get('humidity', 50),
            'wind_speed': data.get('wind_speed', 10),
            'feels_like': data.get('feels_like', temp),
            'precip_prob_max': 0
        }
        summary_text = get_smart_day_summary(day_item_tmp, lang=lang, is_today=(i == 0))

        days_detailed.append({
            "day_index": i,
            "date_str": cur_dt.strftime("%Y-%m-%d"),
            "day_num": cur_dt.day,
            "weekday_letter": w_letter,
            "weekday_short": get_weekday_name(w_idx, lang=lang),
            "full_date": full_date_str,
            "min": d_min,
            "max": d_max,
            "apparent_min": app_min,
            "apparent_max": app_max,
            "code": w_code,
            "icon_name": d_item.get("icon_name", "clear-day.svg"),
            "icon_file": d_item.get("icon_file", os.path.join(ICONS_DIR, "clear-day.svg")),
            "precip_sum": 0.0,
            "precip_prob_max": 0,
            "is_today": (i == 0),
            "cur_hour": today_dt.hour if i == 0 else -1,
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
            "uv_max": max(h24_uvs) if h24_uvs else 0.0,
            "wind_max": max(h24_winds) if h24_winds else 10,
            "gust_max": max(h24_gusts) if h24_gusts else 18,
            "dominant_wind_dir": h24_wind_dirs[12] if len(h24_wind_dirs) > 12 else 270,
            "dominant_wind_cardinal": get_wind_direction_info(h24_wind_dirs[12] if len(h24_wind_dirs) > 12 else 270, lang=lang)[0],
            "dominant_wind_desc": get_wind_direction_info(h24_wind_dirs[12] if len(h24_wind_dirs) > 12 else 270, lang=lang)[1],
            "min_humidity": min(h24_hums) if h24_hums else 40,
            "max_humidity": max(h24_hums) if h24_hums else 80,
            "min_visibility_km": 10.0,
            "max_visibility_km": 10.0,
            "min_pressure_mm": min(h24_press_mm) if h24_press_mm else 748,
            "max_pressure_mm": max(h24_press_mm) if h24_press_mm else 756,
            "summary": summary_text
        })

    data["days_detailed"] = days_detailed
    return data


def determine_solar_time_of_day(lat: float, lon: float, utc_dt: datetime = None) -> tuple[str, int]:
    """
    Dynamically determines (time_of_day, is_day) based on astronomical solar geometry.
    Returns:
        ('dusk', 1) - Dawn (first light to sunrise + 40m) or Dusk (sunset - 50m to last light + 30m)
        ('day', 1)  - Broad daylight
        ('night', 0) - Deep night sky
    """
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)
    elif utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    utc_offset_hours = round(lon / 15.0)
    city_local_ts = utc_dt.timestamp() + utc_offset_hours * 3600
    local_dt = datetime.fromtimestamp(city_local_ts, timezone.utc)
    local_min = local_dt.hour * 60 + local_dt.minute

    N = local_dt.timetuple().tm_yday
    gamma = 2 * math.pi / 365.0 * (N - 1 + 0.5)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma) - 0.014615 * math.cos(2*gamma) - 0.040849 * math.sin(2*gamma))
    decl = 0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma) - 0.006758 * math.cos(2*gamma) + 0.000907 * math.sin(2*gamma) - 0.002697 * math.cos(3*gamma) + 0.00148 * math.sin(3*gamma)

    time_offset = eqtime + 4 * lon - 60 * utc_offset_hours
    t_noon_min = 720 - time_offset
    lat_rad = math.radians(lat)

    def get_ha(elev_deg):
        elev_rad = math.radians(elev_deg)
        denom = math.cos(lat_rad) * math.cos(decl)
        if abs(denom) < 1e-6:
            return 0.0
        cos_ha = (math.sin(elev_rad) - math.sin(lat_rad) * math.sin(decl)) / denom
        if cos_ha > 1.0 or cos_ha < -1.0:
            return None
        return math.degrees(math.acos(cos_ha))

    ha_sun = get_ha(-0.833) or 90.0
    ha_twi = get_ha(-6.0) or 96.0

    sunrise_min = t_noon_min - ha_sun * 4
    sunset_min = t_noon_min + ha_sun * 4
    dawn_min = t_noon_min - ha_twi * 4
    dusk_min = t_noon_min + ha_twi * 4

    if (dawn_min - 20 <= local_min <= sunrise_min + 40) or (sunset_min - 50 <= local_min <= dusk_min + 30):
        return ('dusk', 1)
    elif sunrise_min + 40 < local_min < sunset_min - 50:
        return ('day', 1)
    else:
        return ('night', 0)


def apply_seasonal_norm(data: dict, lat: float, lon: float, lang: str = 'ru'):
    today = datetime.now()
    cur_m = today.month
    m_idx = cur_m - 1

    months_temp_min = [-12, -11, -5, 2, 8, 12, 14, 12, 7, 2, -4, -9]
    months_temp_max = [-6, -4, 2, 11, 19, 23, 25, 23, 16, 8, 0, -5]

    base_min = months_temp_min[m_idx]
    base_max = months_temp_max[m_idx]

    lat_diff = (55.0 - lat) * 0.7
    cont_diff = 0
    if 60 <= lon <= 110 and lat > 50:
        if cur_m in (11, 12, 1, 2):
            cont_diff = -7
        elif cur_m in (10, 3):
            cont_diff = -2
        elif cur_m in (6, 7, 8):
            cont_diff = 1
    elif lat < 45:
        lat_diff = (55.0 - lat) * 1.1

    norm_min = round(base_min + lat_diff + cont_diff)
    norm_max = round(base_max + lat_diff + cont_diff)
    if norm_min >= norm_max:
        norm_max = norm_min + 4

    tod = data.get('time_of_day', 'day')
    is_day = data.get('is_day', 1)
    if tod == 'night':
        curr_temp = norm_min + 1
    elif tod == 'day':
        curr_temp = norm_max - 1
    else:
        curr_temp = round((norm_min + norm_max) / 2)

    data['temp'] = curr_temp
    data['feels_like'] = curr_temp
    data['temp_min'] = norm_min
    data['temp_max'] = norm_max
    data['overall_min'] = norm_min - 2
    data['overall_max'] = norm_max + 3

    if data.get('hourly'):
        for h in data['hourly']:
            h_is_d = h.get('is_day', is_day)
            if h_is_d:
                h['temp'] = round(curr_temp + (norm_max - curr_temp) * 0.7)
            else:
                h['temp'] = round(curr_temp - (curr_temp - norm_min) * 0.7)

    daily_variations = [0, 1, -1, 2, -1, 0, 1, -2, 0, 1]
    if data.get('daily'):
        for i, d in enumerate(data['daily']):
            v = daily_variations[i % len(daily_variations)]
            d['min'] = norm_min + v
            d['max'] = norm_max + v

    if norm_max < 0 and data.get('grad_type') in ('rain', 'drizzle'):
        data['grad_type'] = 'snow'
        data['weather_code'] = 73
        data['condition_text'] = 'Снег' if lang == 'ru' else 'Snow'
        data['icon_name'] = 'snow.svg'
        data['icon_file'] = os.path.join(ICONS_DIR, 'snow.svg')
        data['bg_class'] = f"weather-bg-snow-{tod}"
        data['grad_class'] = f"weather-grad-snow-{tod}"
    return data


def get_fallback_data(city_key: str = 'newyork', lang: str = 'en') -> dict:
    import copy
    from datetime import datetime
    ck = str(city_key).lower().strip()
    if ck in ('spb', 'санкт-петербург', 'saint petersburg'):
        base = FALLBACK_SPB
    elif ck in ('piter', 'питер', 'london', 'лондон'):
        base = FALLBACK_DRIZZLE
    elif ck in ('moscow', 'москва', 'мск'):
        base = FALLBACK_MOSCOW
    elif ck in ('novokuznetsk', 'новокузнецк', 'кузня'):
        base = FALLBACK_NOVOKUZNETSK
    elif ck in ('kaliningrad', 'калининград'):
        base = FALLBACK_KALININGRAD
    elif ck in ('ontario', 'онтарио', 'sochi', 'сочи'):
        base = FALLBACK_ONTARIO
    else:
        # Deterministic assignment across diverse weather bases for other cities
        available_bases = [
            FALLBACK_MOSCOW,        # clouds-day
            FALLBACK_SPB,           # rain-day
            FALLBACK_DRIZZLE,       # drizzle-day
            FALLBACK_NOVOKUZNETSK,  # mostly cloudy
            FALLBACK_KALININGRAD,   # overcast clouds
            FALLBACK_ONTARIO,       # clear dusk
            FALLBACK_NEWYORK,       # clear day
        ]
        base = available_bases[abs(hash(ck)) % len(available_bases)]
    data = copy.deepcopy(base)
    is_ru = (lang == 'ru')
    if ck not in ('spb', 'санкт-петербург', 'saint petersburg', 'piter', 'питер', 'novokuznetsk', 'новокузнецк', 'kaliningrad', 'калининград', 'ontario', 'онтарио', 'newyork', 'нью-йорк', 'moscow', 'москва'):
        formatted = str(city_key).strip().capitalize()
        data['city_name'] = formatted
        data['name_ru'] = formatted
        data['name_en'] = formatted
    else:
        data['city_name'] = data['name_ru'] if is_ru else data['name_en']
    data['country'] = data['country_ru'] if is_ru else data['country_en']
    w_code = data.get('weather_code', 0)

    c_lat = data.get('lat', 40.7128)
    c_lon = data.get('lon', -74.0060)
    utc_offset_hours = round(c_lon / 15.0)

    if ck not in ('ontario', 'онтарио', 'sochi', 'сочи'):
        tod, is_day = determine_solar_time_of_day(c_lat, c_lon)
        data['time_of_day'] = tod
        data['is_day'] = is_day
    else:
        is_day = data.get('is_day', 1)
        tod = data.get('time_of_day', 'dusk')

    grad_type = data.get('grad_type', 'clear')
    data['bg_class'] = f'weather-bg-{grad_type}-{tod}'
    data['grad_class'] = f'weather-grad-{grad_type}-{tod}'

    w_info = WMO_INFO.get(w_code, WMO_INFO[0])
    if not is_day:
        data['icon_name'] = w_info['icon_night']
        data['icon_file'] = f"{w_info['icon_night']}"
    else:
        data['icon_name'] = w_info['icon_day']
        data['icon_file'] = f"{w_info['icon_day']}"

    if tod == 'dusk' and w_code == 0:
        data['condition_text'] = 'Ясно' if is_ru else 'Clear'
    elif tod == 'dusk' and w_code == 1:
        data['condition_text'] = 'В основном ясно' if is_ru else 'Mainly clear'
    elif not is_day and w_code == 0:
        data['condition_text'] = 'Ясно' if is_ru else 'Clear'
    elif not is_day and w_code == 1:
        data['condition_text'] = 'В основном ясно' if is_ru else 'Mainly clear'
    elif base.get('condition_text') and is_ru:
        data['condition_text'] = base['condition_text']
    else:
        data['condition_text'] = get_condition_text(w_code, lang=lang, is_day=(is_day == 1))

    today_w = datetime.now().weekday()
    for i, d in enumerate(data.get('daily', [])):
        d['weekday_idx'] = (today_w + i) % 7
        if i == 0:
            d['day'] = t('weather_today')
        else:
            d['day'] = get_weekday_name(d['weekday_idx'], lang=lang)

    fb_solar = calculate_solar_details(c_lat, c_lon, datetime.now().date(), utc_offset_hours, is_ru=(lang == 'ru'))
    sr_str = fb_solar.get('sunrise', '06:00')
    ss_str = fb_solar.get('sunset', '19:00')
    data['sunrise_str'] = sr_str
    data['sunset_str'] = ss_str
    try:
        sr_h = int(sr_str.split(':')[0])
        ss_h = int(ss_str.split(':')[0])
    except Exception:
        sr_h, ss_h = 6, 19

    if data.get('hourly'):
        for idx, h in enumerate(data.get('hourly', [])):
            if idx == 0:
                h['time'] = t('weather_now')
                h['is_now'] = True
            else:
                h['is_now'] = False
            h_time_str = h.get('time', '')
            try:
                if ':' in h_time_str:
                    h_val = int(h_time_str.split(':')[0])
                    h_is_day = 1 if sr_h <= h_val < ss_h else 0
                    h['is_day'] = h_is_day
                    h_code = h.get('weather_code', w_code)
                    h_info = WMO_INFO.get(h_code, WMO_INFO[0])
                    h_icon = h_info['icon_day'] if h_is_day else h_info['icon_night']
                    h['icon_name'] = h_icon
                    h['icon_file'] = f"{h_icon}"
            except Exception:
                pass

    max_gust = round(data.get('wind_gusts', 6))
    if base.get('summary') and is_ru:
        data['summary'] = base['summary']
    elif tod == 'dusk' and w_code in (0, 1):
        data['summary'] = f"Порывы ветра до {max_gust} м/с. Ясная погода до конца дня." if is_ru else f"Wind gusts up to {max_gust} m/s. Clear skies for the rest of the day."
    elif is_day and w_code in (0, 1):
        data['summary'] = t('weather_summary_clear_day', gust=max_gust)
    elif not is_day and w_code in (0, 1):
        data['summary'] = t('weather_summary_clear_night', gust=max_gust)
    elif w_code in (51, 53, 55, 56, 57) or data.get('grad_type') == 'drizzle':
        data['summary'] = t('weather_summary_drizzle', gust=max_gust)
    else:
        data['summary'] = t('weather_summary_generic', gust=max_gust, condition=data['condition_text'])

    fb_solar['annual_table'] = calculate_annual_solar_table(c_lat, c_lon, utc_offset_hours, is_ru=(lang == 'ru'))
    data['solar_details'] = fb_solar
    data['detailed_moon'] = calculate_detailed_moon(c_lat, c_lon, datetime.now(), utc_offset_hours, is_ru=(lang == 'ru'))
    data['moon_phase'] = calculate_moon_phase()
    apply_seasonal_norm(data, c_lat, c_lon, lang=lang)
    ensure_days_detailed(data, lang=lang)
    return data

WEATHER_PREFIXES = [
    'погода в городе ', 'погода в г. ', 'погода в г ', 'погода в ', 'погода во ', 'погода на ', 'погода ',
    'прогноз погоды в ', 'прогноз в ', 'прогноз погоды ', 'прогноз ',
    'температура в ', 'температура ',
    'weather in ', 'weather for ', 'weather at ', 'weather ',
    'forecast in ', 'forecast for ', 'forecast '
]


MONTHS_RU_SHORT = ['янв.', 'февр.', 'март', 'апр.', 'май', 'июнь', 'июль', 'авг.', 'сент.', 'окт.', 'нояб.', 'дек.']
MONTHS_RU_GENITIVE = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
MONTHS_RU_PREP = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
MONTHS_EN_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

_climate_fetch_in_progress = set()

def calculate_climate_averages(
    lat: float,
    lon: float,
    t_max: float,
    t_min: float,
    hourly_today: list = None,
    is_ru: bool | None = None,
    lang: str | None = None,
) -> dict:
    active_lang = lang or (get_current_language() if is_ru is None else ("ru" if is_ru else "en"))
    today = datetime.now().date()
    cur_m = today.month  # 1..12
    cur_m_idx = cur_m - 1
    today_str_md = today.strftime('%m-%d')

    today_formatted = format_day_month(today.day, today.month, lang=active_lang)
    date_30d_ago = today - timedelta(days=30)
    date_30d_formatted = format_day_month(date_30d_ago.day, date_30d_ago.month, lang=active_lang)

    cache_dir = Path(os.path.expanduser('~/.cache/echo_weather'))
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = f"climate_{round(lat, 2)}_{round(lon, 2)}.json"
    cache_file = cache_dir / cache_key

    climate_norm = None
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                climate_norm = json.load(f)
        except Exception:
            climate_norm = None

    if not climate_norm:
        # Generate graceful baseline immediately so UI never blocks
        months_temp_min = [-10, -9, -4, 3, 9, 13, 15, 13, 8, 3, -2, -7]
        months_temp_max = [-5, -4, 2, 11, 19, 23, 25, 23, 16, 9, 1, -3]
        months_precip = [42, 36, 35, 44, 51, 75, 85, 77, 65, 59, 53, 46]
        monthly_list = []
        for m in range(1, 13):
            monthly_list.append({
                'month': m,
                'name': get_month_name(m, short=True, lang=active_lang),
                'temp_min': months_temp_min[m - 1],
                'temp_max': months_temp_max[m - 1],
                'precip_mm': months_precip[m - 1]
            })
        climate_norm = {
            'monthly': monthly_list,
            'doy_stats': {
                today_str_md: {
                    'p10': months_temp_min[cur_m_idx] + 1,
                    'p90': months_temp_max[cur_m_idx] + 5,
                    'avg_max': months_temp_max[cur_m_idx],
                    'avg_min': months_temp_min[cur_m_idx]
                }
            }
        }

        # Spawn background fetch if not already in progress
        coord_key = (round(lat, 2), round(lon, 2))
        if coord_key not in _climate_fetch_in_progress:
            _climate_fetch_in_progress.add(coord_key)
            def _bg_fetch_climate(c_lat, c_lon, c_file, c_key):
                try:
                    url_climate = f"https://climate-api.open-meteo.com/v1/climate?latitude={c_lat}&longitude={c_lon}&start_date=1991-01-01&end_date=2020-12-31&models=EC_Earth3P_HR&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
                    req = urllib.request.urlopen(url_climate, timeout=12)
                    d = json.loads(req.read().decode())
                    daily = d.get('daily', {})
                    times = daily.get('time', [])
                    t_maxs = daily.get('temperature_2m_max', [])
                    t_mins = daily.get('temperature_2m_min', [])
                    precips = daily.get('precipitation_sum', [])

                    m_tmin = {m: [] for m in range(1, 13)}
                    m_tmax = {m: [] for m in range(1, 13)}
                    m_precip_annual = {m: {} for m in range(1, 13)}
                    doy_tmax = {}
                    doy_tmin = {}

                    for dt, tmx, tmn, p in zip(times, t_maxs, t_mins, precips):
                        yr = dt[:4]
                        m = int(dt[5:7])
                        md = dt[5:10]
                        if tmx is not None:
                            m_tmax[m].append(tmx)
                            doy_tmax.setdefault(md, []).append(tmx)
                        if tmn is not None:
                            m_tmin[m].append(tmn)
                            doy_tmin.setdefault(md, []).append(tmn)
                        if p is not None:
                            m_precip_annual[m][yr] = m_precip_annual[m].get(yr, 0.0) + p

                    monthly_data = []
                    for m in range(1, 13):
                        avg_min = round(sum(m_tmin[m]) / max(1, len(m_tmin[m])))
                        avg_max = round(sum(m_tmax[m]) / max(1, len(m_tmax[m])))
                        avg_p = round(sum(m_precip_annual[m].values()) / max(1, len(m_precip_annual[m])))
                        monthly_data.append({
                            'month': m,
                            'name': get_month_name(m, short=True, lang=active_lang),
                            'temp_min': avg_min,
                            'temp_max': avg_max,
                            'precip_mm': avg_p
                        })

                    doy_stats = {}
                    for md in doy_tmax:
                        tmx_s = sorted(doy_tmax[md])
                        tmn_s = sorted(doy_tmin.get(md, []))
                        if tmx_s and tmn_s:
                            doy_stats[md] = {
                                'p10': round(tmn_s[int(len(tmn_s) * 0.10)]),
                                'p90': round(tmx_s[int(len(tmx_s) * 0.90)]),
                                'avg_max': round(sum(tmx_s) / len(tmx_s)),
                                'avg_min': round(sum(tmn_s) / len(tmn_s))
                            }

                    with open(c_file, 'w', encoding='utf-8') as out_f:
                        json.dump({'monthly': monthly_data, 'doy_stats': doy_stats}, out_f, ensure_ascii=False)
                except Exception as e:
                    logger.debug("Background climate fetch/cache failed: %s", e)
                finally:
                    _climate_fetch_in_progress.discard(c_key)

            threading.Thread(target=_bg_fetch_climate, args=(lat, lon, cache_file, coord_key), daemon=True).start()

    # Extract today DOY stats
    doy = climate_norm.get('doy_stats', {}).get(today_str_md)
    if not doy:
        m_row = climate_norm['monthly'][cur_m_idx]
        doy = {
            'p10': m_row['temp_min'] + 1,
            'p90': m_row['temp_max'] + 5,
            'avg_max': m_row['temp_max'],
            'avg_min': m_row['temp_min']
        }

    p10 = doy.get('p10', 5)
    p90 = doy.get('p90', 21)
    avg_max = doy.get('avg_max', 16)
    avg_min = doy.get('avg_min', 9)

    temp_diff = round(t_max - avg_max)
    temp_diff_str_short = f"+{temp_diff}°" if temp_diff > 0 else (f"{temp_diff}°" if temp_diff < 0 else "0°")
    avg_label = t("weather_climate_average_label", _lang=active_lang)
    if temp_diff > 0:
        temp_diff_str = f"+{temp_diff}° > {avg_label}"
    elif temp_diff < 0:
        temp_diff_str = f"{temp_diff}° < {avg_label}"
    else:
        temp_diff_str = t("weather_climate_near_norm", _lang=active_lang)

    temp_sub_str = t("weather_climate_avg_high", _lang=active_lang, val=avg_max)

    # 24-hour diurnal envelope for normal range
    hourly_normal_band = []
    for h in range(24):
        cycle = 0.5 - 0.5 * math.cos(math.pi * (h - 5) / 12.0) if 5 <= h <= 17 else (
            0.5 - 0.5 * math.cos(math.pi * ((h + 24 - 5) % 24) / 12.0)
        )
        h_min = round(p10 + cycle * 4.0)
        h_max = round(p10 + (p90 - p10) * (0.6 + 0.4 * cycle))
        hourly_normal_band.append((h_min, h_max))

    # 30-day precipitation archive
    precip_30d_cache = cache_dir / f"precip30d_{round(lat, 2)}_{round(lon, 2)}_{today}.json"
    precip_30d_series = []
    precip_30d_dates = []
    actual_30d_total = 0.0

    if precip_30d_cache.exists():
        try:
            with open(precip_30d_cache, 'r', encoding='utf-8') as f:
                p_data = json.load(f)
                precip_30d_series = p_data.get('series', [])
                precip_30d_dates = p_data.get('dates', [])
                actual_30d_total = p_data.get('total', 0.0)
        except Exception as e:
            logger.debug("Failed reading precip 30d cache: %s", e)

    if not precip_30d_series:
        try:
            url_archive = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={date_30d_ago}&end_date={today}&daily=precipitation_sum&timezone=auto"
            with urllib.request.urlopen(url_archive, timeout=2.5) as r:
                d = json.loads(r.read().decode())
                daily_p = d.get('daily', {})
                raw_sums = [p or 0.0 for p in daily_p.get('precipitation_sum', [])]
                precip_30d_dates = daily_p.get('time', [])
                cum = 0.0
                for val in raw_sums:
                    cum += val
                    precip_30d_series.append(round(cum, 1))
                actual_30d_total = round(cum)
                with open(precip_30d_cache, 'w', encoding='utf-8') as f:
                    json.dump({'series': precip_30d_series, 'dates': precip_30d_dates, 'total': actual_30d_total}, f)
        except Exception:
            cum = 0.0
            for d_idx in range(31):
                day_val = 2.0 if d_idx % 4 == 0 else 0.0
                cum += day_val
                precip_30d_series.append(round(cum, 1))
            actual_30d_total = round(cum)

    # 30-day baseline accumulation
    avg_30d_total = 0.0
    for day_offset in range(30):
        dt = date_30d_ago + timedelta(days=day_offset)
        m_val = climate_norm['monthly'][dt.month - 1]['precip_mm']
        avg_30d_total += m_val / 30.0
    avg_30d_total = round(avg_30d_total)

    precip_diff = round(actual_30d_total - avg_30d_total)
    precip_u = t("weather_climate_precip_unit", _lang=active_lang)
    if precip_diff > 0:
        precip_diff_str = f"+{precip_diff} {precip_u} > {avg_label}"
    elif precip_diff < 0:
        precip_diff_str = f"{precip_diff} {precip_u} < {avg_label}"
    else:
        precip_diff_str = t("weather_climate_precip_near_norm", _lang=active_lang)

    precip_sub_str = t("weather_climate_precip_avg_30d", _lang=active_lang, val=avg_30d_total, unit=precip_u)

    cur_m_name = get_month_name(cur_m, short=False, lang=active_lang)
    cur_m_name_gen = get_month_name(cur_m, short=False, lang=active_lang, genitive=True)
    cur_m_min = climate_norm['monthly'][cur_m_idx]['temp_min']
    cur_m_max = climate_norm['monthly'][cur_m_idx]['temp_max']
    cur_m_precip = climate_norm['monthly'][cur_m_idx]['precip_mm']

    if temp_diff > 0:
        temp_comparison_word = t("weather_climate_temp_above", _lang=active_lang, diff=temp_diff)
    elif temp_diff < 0:
        temp_comparison_word = t("weather_climate_temp_below", _lang=active_lang, diff=abs(temp_diff))
    else:
        temp_comparison_word = t("weather_climate_temp_exact", _lang=active_lang)

    summary_temp = t(
        "weather_climate_summary_temp",
        _lang=active_lang,
        date=today_formatted,
        p10=p10,
        p90=p90,
        avg_max=avg_max,
        t_max=t_max,
        comparison=temp_comparison_word,
    )

    monthly_temp_sub = t(
        "weather_climate_monthly_temp_sub",
        _lang=active_lang,
        month=cur_m_name_gen,
        min=cur_m_min,
        max=cur_m_max,
    )

    if precip_diff > 0:
        precip_comparison_word = t("weather_climate_precip_above", _lang=active_lang, diff=precip_diff)
    elif precip_diff < 0:
        precip_comparison_word = t("weather_climate_precip_below", _lang=active_lang, diff=abs(precip_diff))
    else:
        precip_comparison_word = t("weather_climate_precip_exact", _lang=active_lang)

    summary_precip = t(
        "weather_climate_summary_precip",
        _lang=active_lang,
        start_date=date_30d_formatted,
        end_date=today_formatted,
        avg_precip=avg_30d_total,
        actual_precip=actual_30d_total,
        comparison=precip_comparison_word,
    )

    monthly_precip_sub = t(
        "weather_climate_monthly_precip_sub",
        _lang=active_lang,
        month=cur_m_name,
        precip=cur_m_precip,
    )

    # Normalize monthly lists to ensure localized month names
    normalized_monthly = []
    for m_idx, m_item in enumerate(climate_norm['monthly']):
        m_num = m_item.get('month', m_idx + 1)
        m_copy = dict(m_item)
        m_copy['month'] = m_num
        m_copy['name'] = get_month_name(m_num, short=True, lang=active_lang)
        normalized_monthly.append(m_copy)

    return {
        'temp_diff': temp_diff,
        'temp_diff_str': temp_diff_str,
        'temp_diff_str_short': temp_diff_str_short,
        'temp_sub_str': temp_sub_str,
        'temp_today_max': t_max,
        'temp_avg_max': avg_max,
        'temp_normal_p10': p10,
        'temp_normal_p90': p90,
        'hourly_normal_band': hourly_normal_band,
        'summary_temp': summary_temp,
        'monthly_temp_sub': monthly_temp_sub,
        'monthly_temp': normalized_monthly,

        'precip_diff': precip_diff,
        'precip_diff_str': precip_diff_str,
        'precip_sub_str': precip_sub_str,
        'precip_actual_30d': actual_30d_total,
        'precip_avg_30d': avg_30d_total,
        'precip_30d_series': precip_30d_series,
        'precip_30d_dates': precip_30d_dates,
        'summary_precip': summary_precip,
        'monthly_precip_sub': monthly_precip_sub,
        'monthly_precip': normalized_monthly,

        'current_month_idx': cur_m_idx,
        'today_formatted': today_formatted,
        'date_30d_formatted': date_30d_formatted
    }


# Примечание: Астрономические функции и расчеты NOAA вынесены в модуль services.astronomy
# и импортируются в начале файла для обратной совместимости.


MET_SYMBOL_TO_WMO = {
    'clearsky_day': (0, 1),
    'clearsky_night': (0, 0),
    'fair_day': (1, 1),
    'fair_night': (1, 0),
    'partlycloudy_day': (2, 1),
    'partlycloudy_night': (2, 0),
    'cloudy': (3, 1),
    'fog': (45, 1),
    'lightrainshowers_day': (80, 1),
    'lightrainshowers_night': (80, 0),
    'rainshowers_day': (81, 1),
    'rainshowers_night': (81, 0),
    'heavyrainshowers_day': (82, 1),
    'heavyrainshowers_night': (82, 0),
    'lightrain': (61, 1),
    'rain': (63, 1),
    'heavyrain': (65, 1),
    'lightrainshowersandthunder_day': (95, 1),
    'heavyrainshowersandthunder_day': (95, 1),
    'rainandthunder': (95, 1),
    'lightsleet': (68, 1),
    'sleet': (68, 1),
    'heavysleet': (68, 1),
    'lightsnow': (71, 1),
    'snow': (73, 1),
    'heavysnow': (75, 1),
    'lightsnowshowers_day': (85, 1),
    'lightsnowshowers_night': (85, 0),
    'snowshowers_day': (86, 1),
    'snowshowers_night': (86, 0),
    'snowandthunder': (95, 1),
}


def met_symbol_to_wmo(sym: str, default_is_day: int = 1) -> tuple[int, int]:
    if not sym:
        return (0, default_is_day)
    clean_sym = sym.split('?')[0].lower()
    if clean_sym in MET_SYMBOL_TO_WMO:
        code, is_d = MET_SYMBOL_TO_WMO[clean_sym]
        if clean_sym in ('cloudy', 'fog', 'rain', 'lightrain', 'heavyrain', 'snow', 'lightsnow', 'heavysnow', 'rainandthunder'):
            return (code, default_is_day)
        return (code, is_d)
    if 'night' in clean_sym:
        is_d = 0
    elif 'day' in clean_sym:
        is_d = 1
    else:
        is_d = default_is_day
    if 'thunder' in clean_sym:
        return (95, is_d)
    if 'snow' in clean_sym:
        return (73, is_d)
    if 'sleet' in clean_sym:
        return (68, is_d)
    if 'rain' in clean_sym:
        return (63, is_d)
    if 'fog' in clean_sym:
        return (45, is_d)
    if 'partly' in clean_sym:
        return (2, is_d)
    if 'cloud' in clean_sym:
        return (3, is_d)
    return (0, is_d)


def get_geo_timezone_offset_seconds(lat: float, lon: float) -> int:
    is_russia = (lat > 41 and 19 <= lon <= 190)
    if is_russia:
        if lon < 21.0:
            return 2 * 3600
        elif lon < 49.5:
            return 3 * 3600
        elif lon < 55.0:
            return 4 * 3600
        elif lon < 69.0:
            return 5 * 3600
        elif lon < 78.0:
            return 6 * 3600
        elif lon < 93.0:
            return 7 * 3600
        elif lon < 108.0:
            return 8 * 3600
        elif lon < 122.0:
            return 9 * 3600
        elif lon < 137.0:
            return 10 * 3600
        elif lon < 152.0:
            return 11 * 3600
        else:
            return 12 * 3600
    return int(round(lon / 15.0) * 3600)


