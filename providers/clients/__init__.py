"""
Пакет сетевых клиентов для получения метеорологических данных от различных провайдеров.
"""

from __future__ import annotations

from providers.clients.base import BaseWeatherClient
from providers.clients.met_norway import MetNorwayClient
from providers.clients.open_meteo import OpenMeteoClient
from providers.clients.wttr import WttrClient

__all__ = [
    "BaseWeatherClient",
    "OpenMeteoClient",
    "MetNorwayClient",
    "WttrClient",
]
