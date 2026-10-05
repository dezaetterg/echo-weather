# Changelog

All notable changes to **Echo Weather** will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-05

### Added
- **Liquid Glass Visual System**:
  - Translucent frosted glass containers, dynamic gradient backdrops, and modern typography tailored for GTK4 on Linux.
  - 14 real-time atmospheric visual themes adapting dynamically to solar cycle (Dawn, Daytime, Golden Hour, Twilight, Night) and live weather conditions.
  - Cairo-driven physics particle engine: rain with realistic wind deflection and ground splashes, floating mist/drizzle, twinkling night sky stars, and comets.
- **10 Specialized Meteorological Deep-Dive Modules**:
  - **Conditions**: Interactive Bezier spline hourly temperature chart with gesture scrubbing and 10-day overview.
  - **UV Index**: Diurnal UV curves, burn-time estimation, and World Health Organization skin protection recommendations.
  - **Wind**: Dynamic 360° circular compass with wind vector, Beaufort wind scale reference, peak gust tracking, and multi-day comparison.
  - **Precipitation**: Hourly precipitation volume (mm/h) and probability histogram, intensity categories, and next-hour nowcast.
  - **Sun & Solar Cycles**: Real-time solar arc diagram showing sun elevation, golden hour, civil/nautical/astronomical twilight, and annual daylight tables.
  - **Moon & Lunar Astronomy**: Simulated 3D lunar sphere with phase illumination, lunar distance in kilometers, moonrise/moonset times, and full monthly moon phase calendar.
  - **Humidity & Air Comfort**: Hourly humidity spline, dew point calculation, and mugginess comfort index.
  - **Visibility**: Atmospheric transparency assessment and fog/haze safety ratings.
  - **Pressure & Barometer**: Circular gauge barometer dial displaying trends in mmHg and hPa.
  - **Climate Averages**: Comparison of current observations against 30-year climatological norms, monthly temperature spreads, and precipitation variances.
- **Weather Engine & Multi-Model Forecasting**:
  - Multiple global weather forecast providers: Open-Meteo, ECMWF IFS (European Centre for Medium-Range Weather Forecasts), DWD ICON (Germany), and MET Norway.
  - Multi-model consensus blending mode that aggregates predictions from multiple models for maximum reliability.
  - Global city search with instant suggestions and offline-ready geocoding cache.
  - Offline fallback dataset generator with realistic diurnal temperature simulation.
- **Desktop & Configuration Integration**:
  - Russian and English full interface localization.
  - Temperature unit switching (Celsius / Fahrenheit), wind units, and pressure units.
  - City bookmarking, primary home city assignment, and empty state guidance.
  - Desktop integration files (`com.echo.weather.desktop`, scalable SVG icon, `install.sh`, `uninstall.sh`).
