# Echo Weather 🌦️

<div align="center">

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?logo=python&logoColor=white)
![GTK 4.0](https://img.shields.io/badge/GTK-4.0-4B89AC.svg?logo=gnome&logoColor=white)
![Cairo Graphics](https://img.shields.io/badge/Graphics-Cairo-D22630.svg)
![Version](https://img.shields.io/badge/Release-v1.0.0-success.svg)
![Platform](https://img.shields.io/badge/Platform-Linux-FCC624.svg?logo=linux&logoColor=black)

**Atmospheric meteorological desktop application for Linux with liquid glass aesthetics, real-time particle physics, and professional weather analytics.**

*Атмосферное метеорологическое десктоп-приложение для Linux с эстетикой Liquid Glass, физикой частиц реального времени и глубокой аналитикой.*

</div>

---

## ✨ Features

- **💎 Liquid Glass & Bento Design**:
  - Translucent frosted glass containers with subtle inner borders and adaptive ambient shadows.
  - 14 dynamic color atmospheres reflecting the live solar cycle (Dawn, Daytime, Golden Hour, Twilight, Night) and current weather conditions.
  - Native GTK4 styling with smooth transitions and high-DPI scaling.

- **🌌 Atmospheric Particle Canvas**:
  - Built-in Cairo physics engine running at up to 60 FPS with adaptive frame throttling for low CPU/battery consumption.
  - Rain with dynamic wind drift angle and impact splashes.
  - Floating drizzle and mist.
  - Twinkling night sky starfield with variable brightness and sporadic shooting stars (comets).

- **🔬 10 Meteorological Deep-Dive Modules**:
  1. **Conditions**: Interactive cubic Bezier spline hourly temperature chart with gesture scrubbing, min/max ranges, and 10-day overview.
  2. **UV Index**: Live ultraviolet radiation curve, peak exposure time, and WHO skin protection guidelines.
  3. **Wind & Gusts**: 360° circular compass with wind vector pointer, peak gusts, and interactive Beaufort scale reference table.
  4. **Precipitation**: Hourly volume histogram (mm/h), probability distribution, intensity categories, and next-hour nowcast.
  5. **Solar Cycles**: Solar arc diagram calculating solar elevation, golden hour, civil/nautical/astronomical twilight, and annual daylight tables.
  6. **Moon & Lunar Astronomy**: Simulated 3D lunar sphere with illumination percentage, lunar distance (apogee/perigee), moonrise/moonset times, and 30-day lunar calendar.
  7. **Humidity & Dew Point**: Hourly moisture spline, dew point calculation, and comfort rating.
  8. **Visibility**: Atmospheric transparency assessment and fog/haze safety classifications.
  9. **Pressure & Barometer**: Circular gauge barometer dial tracking trends in mmHg and hPa.
  10. **Climate Averages**: Comparison of current temperatures against 30-year climatological norms with monthly historical distribution.

- **🌐 Multi-Model Weather Engine**:
  - **Open-Meteo**: Global ensemble forecasts with high-resolution precipitation nowcasting.
  - **ECMWF IFS**: European Centre for Medium-Range Weather Forecasts (industry gold standard).
  - **DWD ICON**: Deutscher Wetterdienst high-precision model.
  - **MET Norway**: High-latitude meteorological modeling.
  - **Consensus Blending**: Intelligent weighted average across multiple models.
  - **Diurnal Fallback Engine**: Realistic offline fallback simulation when disconnected.

- **🌍 City Management & Localization**:
  - Instant city search with autocompletion and offline cache of major global cities.
  - Pinning favorite cities and setting a primary Home City (`🏠`).
  - Full localization in Russian and English with automatic language detection.
  - Configurable units: Celsius / Fahrenheit, km/h / m/s / mph, mmHg / hPa.

---

## 🚀 Installation

### System Dependencies

Echo Weather is built natively on **GTK4**, **Libadwaita** (optional, recommended), **PyGObject**, and **Cairo**.

#### Arch Linux / Manjaro
```bash
sudo pacman -S gtk4 libadwaita python-gobject python-cairo
```

#### Fedora / RHEL
```bash
sudo dnf install gtk4 libadwaita python3-gobject python3-cairo
```

#### Ubuntu 24.04+ / Debian 12+
```bash
sudo apt update
sudo apt install libgtk-4-1 gir1.2-gtk-4.0 gir1.2-adw-1 python3-gi python3-gi-cairo
```

---

### Installing Echo Weather

1. **Clone the repository:**
   ```bash
   git clone https://github.com/demid/echo-weather.git
   cd echo-weather
   ```

2. **Run the installer:**
   ```bash
   ./install.sh
   ```
   The installer copies application files to `~/.local/share/echo-weather`, places the executable in `~/.local/bin/echo-weather`, installs the `.desktop` launcher, and updates desktop caches.

3. **Launch the app:**
   - From your application menu: search for **Echo Weather**.
   - Or from terminal:
     ```bash
     echo-weather
     ```

### Running Directly Without Installing
You can run Echo Weather directly from the cloned repository:
```bash
./echo-weather
# Or with a specific city:
./echo-weather "Novokuznetsk"
```

---

## ⌨️ Shortcuts & Controls

| Action | Control / Shortcut |
| :--- | :--- |
| **City Search** | Click search bar or press `Ctrl + F` |
| **Inspect Hourly Metric** | Click & drag across the hourly chart / spline |
| **Open Detail Sheet** | Click any Bento summary card on the overview |
| **Close Detail Sheet** | Click `< Назад` (Back) button or press `Escape` |
| **Set as Home City** | Click `🏠 Основной город` under city name or use context menu |
| **Pin / Unpin City** | Click `📌 Закрепить` or right-click city chip in top bar |
| **Switch Forecast Provider** | Open Settings (`⚙️`) and select Weather Model |

---

## 🛠️ Development & Testing

Echo Weather includes an automated test suite covering meteorological calculations, astronomy formulas, UI models, and rendering pipelines.

### Setup Virtual Environment
```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements-dev.txt
```
*(Note: `--system-site-packages` allows the virtual environment to access system GTK4 / PyGObject bindings).*

### Running Tests
```bash
PYTHONPATH=. pytest
```

### Running Linter
```bash
ruff check .
```

---

## 📚 Technical Documentation

For developers interested in the internal architecture and meteorological algorithms:
- **[SPECIFICATION.md](SPECIFICATION.md)**: Exhaustive architectural specification (state management, rendering pipeline, custom Cairo widgets, WMO weather code mapping).
- **[REFACTORING_PLAN.md](REFACTORING_PLAN.md)**: Comprehensive refactoring roadmap and design patterns.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
