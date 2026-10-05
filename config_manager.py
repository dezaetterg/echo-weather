"""
Configuration manager for Echo Weather.
Handles persistent settings in ~/.config/echo-weather/config.json.
"""

import json
import os
from pathlib import Path

from logger import get_logger

logger = get_logger("config")


class ConfigManager:
    def __init__(self, config_dir=None):
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path(os.path.expanduser("~/.config/echo-weather"))
        self.config_file = self.config_dir / "config.json"

        self.defaults = {
            "default_city": "Moscow",
            "saved_cities": ["Moscow", "Saint Petersburg", "Novokuznetsk", "New York"],
            "temperature_unit": "celsius",
            "theme": "dark",
            "language": "en",
            "animations": True,
            "window_width": 650,
            "window_height": 560,
            "forecast_source": "consensus",
            "weather_model": "best_match",
            "power_mode": "balanced",
            "main_city": "",
        }

        self.config = {}
        self.load()

    def load(self):
        self.config = self.defaults.copy()
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    for key, val in user_config.items():
                        if key in self.defaults:
                            self.config[key] = val
            except Exception as e:
                logger.error("Error loading config: %s", e)
        else:
            self.save()

    def save(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error("Error saving config: %s", e)

    def get(self, key, default=None):
        val = self.config.get(key)
        if val is not None:
            return val
        if default is not None:
            return default
        return self.defaults.get(key)

    def set(self, key, value):
        self.config[key] = value
        self.save()
