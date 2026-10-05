import json
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from logger import get_logger

logger = get_logger("weather_cache")

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "echo-search" / "weather"


class WeatherCacheManager:
    """Thread-safe, atomic disk-backed cache manager for meteorological forecasts and geocoding."""

    def __init__(self, cache_dir: Path | str | None = None, cache_filename: str = "cache.json"):
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_file = self.cache_dir / cache_filename
        self._lock = threading.Lock()
        self._cache = {"geocache": {}, "forecasts": {}}
        self._load_cache()

    def _load_cache(self):
        with self._lock:
            if not self.cache_file.exists():
                return
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._cache["geocache"] = data.get("geocache", {})
                        self._cache["forecasts"] = data.get("forecasts", {})
                self._purge_stale_forecasts_locked()
            except Exception as e:
                logger.warning("Failed to load weather cache from %s: %s", self.cache_file, e)
                self._cache = {"geocache": {}, "forecasts": {}}

    def _purge_stale_forecasts_locked(self):
        """Remove outdated forecasts from previous calendar days or incomplete payloads."""
        utc_now = datetime.now(timezone.utc)
        to_remove = []
        for k, v in self._cache["forecasts"].items():
            if not isinstance(v, dict) or "days_detailed" not in v or not v.get("days_detailed"):
                to_remove.append(k)
                continue

            first_day = v["days_detailed"][0]
            if not isinstance(first_day, dict) or "min" not in first_day:
                to_remove.append(k)
                continue

            offset = v.get("utc_offset_seconds", 0)
            city_today = (utc_now + timedelta(seconds=offset)).strftime("%Y-%m-%d")
            first_date = first_day.get("date_str")
            fc_date = v.get("forecast_date")
            if not fc_date or fc_date != city_today or (first_date and first_date < city_today):
                to_remove.append(k)

        for k in to_remove:
            self._cache["forecasts"].pop(k, None)

    def _save_cache_locked(self):
        """Atomically persist cache using temporary file and atomic replace."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Create temp file in same filesystem directory for atomic os.replace
            fd, tmp_path = tempfile.mkstemp(dir=self.cache_dir, prefix="weather_cache_", suffix=".tmp")
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.cache_file)
        except Exception as e:
            logger.warning("Failed to atomically save weather cache: %s", e)

    def get_forecast(self, key: str) -> dict | None:
        with self._lock:
            val = self._cache["forecasts"].get(key)
            return dict(val) if isinstance(val, dict) else None

    def set_forecast(self, key: str, data: Any):
        payload = data.to_dict() if hasattr(data, "to_dict") else data
        if not isinstance(payload, dict):
            return
        with self._lock:
            self._cache["forecasts"][key] = payload
            self._save_cache_locked()

    def invalidate_forecast(self, key: str):
        with self._lock:
            if key in self._cache.get("forecasts", {}):
                del self._cache["forecasts"][key]
                self._save_cache_locked()

    def get_geocache(self, key: str) -> dict | None:
        with self._lock:
            val = self._cache["geocache"].get(key)
            return dict(val) if isinstance(val, dict) else None

    def set_geocache(self, key: str, info: dict):
        if not isinstance(info, dict):
            return
        with self._lock:
            self._cache["geocache"][key] = info
            self._save_cache_locked()

    def find_geocache_candidate(self, query: str) -> dict | None:
        """Search in cached geolocations by exact or prefix matches."""
        q = query.lower().strip()
        with self._lock:
            if q in self._cache["geocache"]:
                return self._cache["geocache"][q]

            for c_q, info in self._cache["geocache"].items():
                if not isinstance(info, dict):
                    continue
                name_ru = info.get("name_ru", "").lower()
                name_en = info.get("name_en", "").lower()
                if q == name_ru or q == name_en:
                    return info
                for cand in [c_q, name_ru, name_en]:
                    if cand and len(cand) >= 3 and (cand.startswith(q) or q.startswith(cand)):
                        return info
        return None

    def clear(self):
        with self._lock:
            self._cache = {"geocache": {}, "forecasts": {}}
            self._save_cache_locked()
