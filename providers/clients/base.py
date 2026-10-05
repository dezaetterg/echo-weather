"""
Базовый интерфейс для метеорологических сетевых клиентов.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseWeatherClient(ABC):
    """Абстрактный класс поставщика метеорологических данных."""

    @abstractmethod
    def fetch_forecast(
        self,
        lat: float,
        lon: float,
        city_info: dict[str, Any] | None = None,
        timeout: float = 4.0,
        **kwargs: Any
    ) -> dict[str, Any] | None:
        """Получение сырого или частично обработанного прогноза от внешнего API."""
        pass
