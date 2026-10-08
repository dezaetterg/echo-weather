import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Graphene', '1.0')
import math
import os
import random
import time

import cairo
from gi.repository import Gdk, GLib, Graphene, Gtk

from logger import get_logger

logger = get_logger("weather_atmosphere")

WEATHER_ICONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'assets', 'icons', 'weather'))

class DrizzleParticle:
    __slots__ = ('x', 'y', 'length', 'speed', 'alpha', 'line_w', 'wind_ratio', 'layer')
    def __init__(self, x: float, y: float, w_width: float, w_height: float):
        self.reset(x, y, w_width, w_height, initial=True)

    def reset(self, x: float, y: float, w_width: float, w_height: float, initial: bool = False):
        self.layer = random.choices([0, 1, 2], weights=[0.45, 0.35, 0.20])[0]
        if self.layer == 0:
            # Distant mist/drizzle: tiny, slow, faint
            self.length = random.uniform(5.0, 8.0)
            self.speed = random.uniform(160.0, 230.0)
            self.alpha = random.uniform(0.14, 0.22)
            self.line_w = 0.75
        elif self.layer == 1:
            # Midground: standard drizzle
            self.length = random.uniform(9.0, 13.0)
            self.speed = random.uniform(240.0, 320.0)
            self.alpha = random.uniform(0.22, 0.34)
            self.line_w = 0.95
        else:
            # Foreground: larger droplets near glass
            self.length = random.uniform(14.0, 18.0)
            self.speed = random.uniform(340.0, 420.0)
            self.alpha = random.uniform(0.32, 0.44)
            self.line_w = 1.20

        # Wind ratio: ~10.5 degrees slant down-left matching ~5-7 m/s wind
        self.wind_ratio = random.uniform(0.16, 0.21)

        self.x = x
        self.y = y if initial else random.uniform(-30.0, -5.0)

    @property
    def wind_dx(self) -> float:
        return -self.speed * self.wind_ratio


class CometParticle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'length', 'life', 'max_life', 'alpha', 'color_rgb')

    def __init__(self, start_x: float, start_y: float, speed: float = 820.0, angle_deg: float = 208.0):
        self.x = start_x
        self.y = start_y
        rad = math.radians(angle_deg)
        self.vx = math.cos(rad) * speed
        self.vy = math.sin(rad) * speed
        self.length = random.uniform(85.0, 130.0)
        self.max_life = random.uniform(0.70, 1.05)
        self.life = self.max_life
        self.alpha = 0.0
        self.color_rgb = random.choice([
            (0.85, 0.94, 1.0),
            (0.92, 0.96, 1.0),
            (1.0, 1.0, 1.0)
        ])

    def update(self, dt: float) -> bool:
        self.life -= dt
        if self.life <= 0:
            return False
        self.x += self.vx * dt
        self.y += self.vy * dt
        progress = 1.0 - (self.life / self.max_life)
        if progress < 0.2:
            self.alpha = progress / 0.2
        else:
            self.alpha = max(0.0, (1.0 - progress) / 0.8)
        return True


class StarParticle:
    __slots__ = ('x', 'y', 'radius', 'base_alpha', 'speed', 'phase', 'has_halo', 'color_rgb', 'u', 'v')

    def __init__(self, x: float, y: float, radius: float, base_alpha: float, speed: float, phase: float, has_halo: bool, color_rgb: tuple, u: float = 0.0, v: float = 0.0):
        self.x = x
        self.y = y
        self.radius = radius
        self.base_alpha = base_alpha
        self.speed = speed
        self.phase = phase
        self.has_halo = has_halo
        self.color_rgb = color_rgb
        self.u = u
        self.v = v



class RainParticle:
    __slots__ = ('x', 'y', 'length', 'speed', 'alpha', 'line_w', 'wind_ratio', 'layer')
    def __init__(self, x: float, y: float, w_width: float, w_height: float):
        self.reset(x, y, w_width, w_height, initial=True)

    def reset(self, x: float, y: float, w_width: float, w_height: float, initial: bool = False):
        self.layer = random.choices([0, 1, 2], weights=[0.40, 0.40, 0.20])[0]
        if self.layer == 0:
            # Distant rain
            self.length = random.uniform(16.0, 22.0)
            self.speed = random.uniform(550.0, 680.0)
            self.alpha = random.uniform(0.18, 0.26)
            self.line_w = 0.85
        elif self.layer == 1:
            # Midground rain
            self.length = random.uniform(24.0, 32.0)
            self.speed = random.uniform(700.0, 840.0)
            self.alpha = random.uniform(0.26, 0.38)
            self.line_w = 1.10
        else:
            # Foreground heavy drops
            self.length = random.uniform(34.0, 42.0)
            self.speed = random.uniform(860.0, 980.0)
            self.alpha = random.uniform(0.35, 0.48)
            self.line_w = 1.45

        # Wind ratio: ~13-15 degrees slant down-left matching ~8 m/s wind in SPb screenshot
        self.wind_ratio = random.uniform(0.20, 0.25)

        self.x = x
        self.y = y if initial else random.uniform(-40.0, -5.0)

    @property
    def wind_dx(self) -> float:
        return -self.speed * self.wind_ratio


# Pre-defined color stops for cached atmosphere sky gradients
NIGHT_STOPS = (
    (0.00, 0.024, 0.035, 0.075),
    (0.35, 0.047, 0.075, 0.141),
    (0.70, 0.075, 0.118, 0.204),
    (1.00, 0.098, 0.153, 0.251),
)

RAIN_STOPS = (
    (0.00, 0.55, 0.61, 0.71),
    (0.35, 0.44, 0.52, 0.62),
    (0.70, 0.32, 0.41, 0.51),
    (1.00, 0.22, 0.30, 0.39),
)

RAIN_NIGHT_STOPS = (
    (0.00, 0.047, 0.071, 0.098),
    (0.40, 0.075, 0.110, 0.149),
    (0.75, 0.110, 0.153, 0.208),
    (1.00, 0.137, 0.192, 0.259),
)

DRIZZLE_STOPS = (
    (0.00, 0.42, 0.50, 0.59),
    (0.35, 0.35, 0.42, 0.51),
    (0.70, 0.27, 0.35, 0.43),
    (1.00, 0.21, 0.27, 0.34),
)

DRIZZLE_NIGHT_STOPS = (
    (0.00, 0.094, 0.133, 0.180),
    (0.45, 0.125, 0.173, 0.235),
    (0.85, 0.165, 0.227, 0.306),
    (1.00, 0.204, 0.275, 0.369),
)

OVERCAST_STOPS = (
    (0.00, 0.486, 0.659, 0.761),
    (0.35, 0.576, 0.737, 0.831),
    (0.65, 0.635, 0.776, 0.863),
    (1.00, 0.522, 0.671, 0.753),
)

DUSK_STOPS = (
    (0.00, 0.090, 0.216, 0.369),
    (0.20, 0.161, 0.259, 0.435),
    (0.40, 0.259, 0.306, 0.471),
    (0.60, 0.345, 0.333, 0.506),
    (0.80, 0.455, 0.392, 0.463),
    (1.00, 0.604, 0.427, 0.416),
)

MOSTLY_CLOUDY_STOPS = (
    (0.00, 0.48, 0.56, 0.67),
    (0.20, 0.24, 0.48, 0.72),
    (0.55, 0.09, 0.43, 0.75),
    (1.00, 0.06, 0.36, 0.68),
)

CLEAR_DAY_STOPS = (
    (0.00, 0.102, 0.451, 0.910),
    (0.35, 0.180, 0.529, 0.941),
    (0.70, 0.278, 0.627, 0.969),
    (1.00, 0.408, 0.710, 0.992),
)

MOON_GLOW_STOPS = (
    (0.0, 0.72, 0.84, 1.0, 0.19),
    (0.5, 0.60, 0.75, 0.95, 0.07),
    (1.0, 0.0, 0.0, 0.0, 0.0),
)

DUSK_HORIZON_STOPS = (
    (0.00, 0.68, 0.44, 0.40, 0.35),
    (0.40, 0.60, 0.40, 0.45, 0.18),
    (1.00, 0.35, 0.30, 0.45, 0.00),
)

SUN_HALO_CLOUDY_STOPS = (
    (0.00, 1.00, 0.99, 0.93, 0.82),
    (0.20, 0.98, 0.96, 1.00, 0.38),
    (0.55, 0.65, 0.82, 1.00, 0.12),
    (1.00, 0.45, 0.70, 1.00, 0.00),
)

SUN_HALO_CLEAR_STOPS = (
    (0.00, 1.00, 0.99, 0.94, 0.45),
    (0.25, 0.95, 0.96, 1.00, 0.22),
    (0.60, 0.70, 0.85, 1.00, 0.08),
    (1.00, 0.50, 0.75, 1.00, 0.00),
)

DRIZZLE_PULSE_NIGHT_STOPS = (
    (0.00, 0.80, 0.90, 1.00, 0.040),
    (0.45, 0.70, 0.82, 0.96, 0.016),
    (1.00, 0.15, 0.25, 0.40, 0.000),
)

DRIZZLE_PULSE_DAY_STOPS = (
    (0.00, 1.00, 0.98, 0.92, 0.055),
    (0.45, 0.95, 0.98, 1.00, 0.022),
    (1.00, 0.80, 0.85, 0.95, 0.000),
)



class AtmosphericCapsuleBox(Gtk.Box):
    """
    Full-window atmospheric canvas for Echo Weather.
    Renders dynamic full-bleed weather environments (drifting cumulus/overcast clouds,
    falling rain/drizzle, radiant sun flare, or deep starry night sky with moon glow)
    across the entire capsule.
    """

    ALL_CANVAS_CLASSES = [
        'weather-canvas-active',
        'weather-canvas-clear-day', 'weather-canvas-clear-dusk', 'weather-canvas-clear-night',
        'weather-canvas-clouds-day', 'weather-canvas-clouds-night',
        'weather-canvas-rain-day', 'weather-canvas-rain-night',
        'weather-canvas-drizzle-day', 'weather-canvas-drizzle-night',
        'weather-canvas-storm-day', 'weather-canvas-storm-night',
        'weather-canvas-snow-day', 'weather-canvas-snow-night',
        'weather-canvas-fog-day', 'weather-canvas-fog-night',
    ]

    def __init__(self, config_manager=None, corner_radius: float = 0.0):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.config_manager = config_manager
        self.corner_radius = float(corner_radius)
        self.add_css_class('capsule-window-ui')
        self.set_overflow(Gtk.Overflow.HIDDEN)

        self._weather_data = None
        self._drizzle_surface = None
        self._stars_surface = None
        self._cumulus_surface = None
        self._overcast_surface = None
        self._rain_clouds_surface = None
        self._cirrus_surface = None
        self._night_clouds_surface = None

        self._stars_w = 1070.0
        self._stars_h = 560.0
        self._stars = self._generate_stars(self._stars_w, self._stars_h)
        self._comets = []
        self._comet_spawn_timer = random.uniform(3.0, 7.0)

        self._tick_id = None
        self._last_time = None
        self._pulse_phase = random.uniform(0, math.pi * 2)
        self._cloud_shift = random.uniform(0, 1800.0)
        self._particles = []
        self._particle_mode = None
        self._initialized_particles = False

        self._load_textures()
        self._halo_surface = self._create_halo_surface()
        self._cached_moon_glow = None
        self._cached_moon_glow_w = 0.0
        self._cached_linear_grads = {}
        self._cached_radial_grads = {}
        self._cloud_patterns = {}
        self._dusk_stars = []
        self._dusk_stars_w = 0.0
        self._dusk_stars_h = 0.0
        self._accumulated_dt = 0.0
        self._cached_bg_surface = None
        self._cached_bg_key = None
        self._is_paused = False

        self.connect('map', self._on_map)
        self.connect('unmap', self._on_unmap)

    def _load_textures(self):
        base_dir = os.path.dirname(__file__)

        def _try_load(filename):
            path = os.path.join(base_dir, 'assets', filename)
            if os.path.exists(path):
                try:
                    return cairo.ImageSurface.create_from_png(path)
                except Exception as e:
                    logger.warning("AtmosphericCapsuleBox: error loading %s: %s", filename, e)
            return None

        self._drizzle_surface = _try_load('weather_drizzle_bg.png')
        self._stars_surface = _try_load('weather_night_stars.png')
        self._cumulus_surface = _try_load('weather_clouds_cumulus.png')
        self._overcast_surface = _try_load('weather_clouds_overcast.png')
        self._night_clouds_surface = _try_load('weather_clouds_night.png')
        self._rain_clouds_surface = _try_load('weather_clouds_rain.png')
        self._cirrus_surface = _try_load('weather_clouds_cirrus.png')
    def _create_halo_surface(self) -> cairo.ImageSurface:
        """Pre-bake normalized radial halo for star twinkling to eliminate per-frame allocations."""
        size = 64
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        cr = cairo.Context(surf)
        grad = cairo.RadialGradient(size / 2.0, size / 2.0, 2.0, size / 2.0, size / 2.0, size / 2.0)
        grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.45)
        grad.add_color_stop_rgba(0.4, 0.75, 0.88, 1.0, 0.20)
        grad.add_color_stop_rgba(1.0, 0.4, 0.6, 1.0, 0.0)
        cr.set_source(grad)
        cr.paint()
        return surf

    def _get_cached_linear_grad(self, key: str, h: float, stops: tuple) -> cairo.LinearGradient:
        rounded_h = round(h, 1)
        cache_key = (key, rounded_h)
        grad = self._cached_linear_grads.get(cache_key)
        if grad is None:
            grad = cairo.LinearGradient(0, 0, 0, rounded_h)
            for stop, r, g, b in stops:
                grad.add_color_stop_rgb(stop, r, g, b)
            if len(self._cached_linear_grads) > 30:
                self._cached_linear_grads.clear()
            self._cached_linear_grads[cache_key] = grad
        return grad

    def _get_cached_radial_grad(self, key: str, params: tuple, stops: tuple) -> cairo.RadialGradient:
        cache_key = (key, params)
        grad = self._cached_radial_grads.get(cache_key)
        if grad is None:
            cx0, cy0, r0, cx1, cy1, r1 = params
            grad = cairo.RadialGradient(cx0, cy0, r0, cx1, cy1, r1)
            for stop, r, g, b, a in stops:
                grad.add_color_stop_rgba(stop, r, g, b, a)
            if len(self._cached_radial_grads) > 30:
                self._cached_radial_grads.clear()
            self._cached_radial_grads[cache_key] = grad
        return grad

    def _get_cached_cloud_pattern(self, surface: cairo.ImageSurface) -> cairo.SurfacePattern:
        pattern = self._cloud_patterns.get(surface)
        if pattern is None:
            pattern = cairo.SurfacePattern(surface)
            pattern.set_filter(cairo.FILTER_BILINEAR)
            pattern.set_extend(cairo.EXTEND_REPEAT)
            self._cloud_patterns[surface] = pattern
        return pattern

    def _ensure_dusk_stars(self, w: float, h: float) -> list:
        if not self._dusk_stars or abs(self._dusk_stars_w - w) > 5.0 or abs(self._dusk_stars_h - h) > 5.0:
            rng = random.Random(42)
            stars = []
            for _ in range(65):
                sx = rng.uniform(20.0, w - 20.0)
                sy = rng.uniform(15.0, h * 0.55)
                s_r = rng.uniform(0.65, 1.25)
                alpha = rng.uniform(0.30, 0.75) * (1.0 - (sy / (h * 0.55)) * 0.7)
                stars.append((sx, sy, s_r, alpha))
            self._dusk_stars = stars
            self._dusk_stars_w = w
            self._dusk_stars_h = h
        return self._dusk_stars


    def _generate_stars(self, w: float = 1070.0, h: float = 560.0) -> list:
        w = max(400.0, float(w))
        h = max(300.0, float(h))
        count = int(max(180, min(1200, (w * h) / 3400.0)))
        rng = random.Random(2026)
        stars = []
        for _ in range(count):
            u = rng.uniform(0.008, 0.992)
            v = rng.uniform(0.012, 0.985)
            sx = u * w
            sy = v * h
            sr = rng.uniform(0.75, 2.1)
            base_alpha = rng.uniform(0.35, 0.85)
            speed = rng.uniform(1.2, 3.2)
            phase = rng.uniform(0.0, math.pi * 2)
            has_halo = sr > 1.65
            color_rgb = rng.choice([
                (0.92, 0.96, 1.0),
                (0.88, 0.93, 1.0),
                (1.0, 0.98, 0.92),
                (0.95, 0.97, 1.0),
            ])
            stars.append(StarParticle(sx, sy, sr, base_alpha, speed, phase, has_halo, color_rgb, u=u, v=v))
        return stars

    def _ensure_stars(self, w: float, h: float):
        w = max(400.0, float(w))
        h = max(300.0, float(h))
        if not self._stars or abs(self._stars_w - w) > 2.0 or abs(self._stars_h - h) > 2.0:
            self._stars = self._generate_stars(w, h)
            self._stars_w = w
            self._stars_h = h

    def _spawn_comet(self, w: float, h: float):
        start_x = random.uniform(w * 0.20, w + 40.0)
        start_y = random.uniform(5.0, h * 0.40)
        speed = random.uniform(750.0, 950.0)
        angle = random.uniform(198.0, 218.0)
        self._comets.append(CometParticle(start_x, start_y, speed=speed, angle_deg=angle))


    def _draw_comet(self, cr, comet: CometParticle):
        if comet.alpha <= 0.01:
            return
        v_norm = math.hypot(comet.vx, comet.vy)
        if v_norm < 1e-3:
            return
        dx = -(comet.vx / v_norm) * comet.length
        dy = -(comet.vy / v_norm) * comet.length
        tail_x = comet.x + dx
        tail_y = comet.y + dy

        cr.save()
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        grad = cairo.LinearGradient(comet.x, comet.y, tail_x, tail_y)
        r, g, b = comet.color_rgb
        grad.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, comet.alpha * 0.95)
        grad.add_color_stop_rgba(0.25, r, g, b, comet.alpha * 0.70)
        grad.add_color_stop_rgba(0.65, r * 0.7, g * 0.8, b, comet.alpha * 0.25)
        grad.add_color_stop_rgba(1.0, 0.2, 0.4, 0.8, 0.0)

        cr.set_source(grad)
        cr.set_line_width(2.0)
        cr.move_to(tail_x, tail_y)
        cr.line_to(comet.x, comet.y)
        cr.stroke()

        head_glow = cairo.RadialGradient(comet.x, comet.y, 0.5, comet.x, comet.y, 4.5)
        head_glow.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, comet.alpha)
        head_glow.add_color_stop_rgba(0.35, r, g, b, comet.alpha * 0.75)
        head_glow.add_color_stop_rgba(1.0, 0.3, 0.5, 0.9, 0.0)
        cr.set_source(head_glow)
        cr.arc(comet.x, comet.y, 4.5, 0, 2 * math.pi)
        cr.fill()
        cr.restore()

    def _get_w_code(self) -> int:
        if not self._weather_data:
            return 0
        try:
            code = self._weather_data.get('weather_code')
            if code is None:
                code = self._weather_data.get('condition_code', 0)
            return int(code)
        except (ValueError, TypeError):
            return 0

    def _is_night(self) -> bool:
        if not self._weather_data:
            return False
        tod = self._weather_data.get('time_of_day', '')
        bg = self._weather_data.get('bg_class', '')
        return tod == 'night' or 'night' in bg or self._weather_data.get('is_day') == 0

    def _is_dusk(self) -> bool:
        if not self._weather_data:
            return False
        tod = self._weather_data.get('time_of_day', '')
        bg = self._weather_data.get('bg_class', '')
        return tod in ('dusk', 'dawn') or 'dusk' in bg or 'dawn' in bg

    def _is_drizzle(self) -> bool:
        if not self._weather_data:
            return False
        bg = self._weather_data.get('bg_class', '')
        grad = self._weather_data.get('grad_type', '')
        cond = self._weather_data.get('condition_text', '').lower()
        code = self._get_w_code()
        return 'drizzle' in bg or grad == 'drizzle' or code in (51, 53, 55, 56, 57) or 'изморось' in cond

    def _is_rain(self) -> bool:
        if not self._weather_data:
            return False
        bg = self._weather_data.get('bg_class', '')
        grad = self._weather_data.get('grad_type', '')
        cond = self._weather_data.get('condition_text', '').lower()
        code = self._get_w_code()
        return ('rain' in bg or grad == 'rain' or code in (61, 63, 65, 66, 67, 80, 81, 82) or
                ('дождь' in cond and 'изморось' not in cond) or 'ливень' in cond)

    def _is_mostly(self) -> bool:
        if not self._weather_data:
            return False
        if self._weather_data.get('is_mostly'):
            return True
        cond = self._weather_data.get('condition_text', '').lower()
        code = self._get_w_code()
        return 'в основном' in cond or 'преимущественно' in cond or 'mostly' in cond or code in (1, 2)

    def _is_mostly_cloudy(self) -> bool:
        if not self._weather_data:
            return False
        cond = self._weather_data.get('condition_text', '').lower()
        code = self._get_w_code()
        grad = self._weather_data.get('grad_type', '')
        return (grad == 'mostly_cloudy' or code == 2 or
                ('в основном' in cond and 'облачн' in cond) or
                'переменная облачность' in cond)

    def _is_mostly_clear(self) -> bool:
        if not self._weather_data:
            return False
        cond = self._weather_data.get('condition_text', '').lower()
        code = self._get_w_code()
        return (code == 1 or ('в основном' in cond and 'ясно' in cond) or
                ('преимущественно' in cond and 'ясно' in cond))

    def _is_overcast(self) -> bool:
        if not self._weather_data:
            return False
        if self._is_rain() or self._is_drizzle() or self._is_mostly_cloudy():
            return False
        cond = self._weather_data.get('condition_text', '').lower()
        code = self._get_w_code()
        bg = self._weather_data.get('bg_class', '')
        grad = self._weather_data.get('grad_type', '')
        return (code == 3 or cond == 'облачно' or 'пасмурно' in cond or
                grad == 'clouds' or ('clouds' in bg and not self._is_mostly()))

    def _is_clear(self) -> bool:
        if not self._weather_data:
            return False
        bg = self._weather_data.get('bg_class', '')
        grad = self._weather_data.get('grad_type', '')
        cond = self._weather_data.get('condition_text', '').lower()
        return ('clear' in bg or grad in ('clear', 'mostly_clear') or
                'ясно' in cond or 'солнечно' in cond)

    def _has_active_animation(self) -> bool:
        if not self._weather_data:
            return False
        # Any precipitation or cloud movement or sunbeam/dusk animation or night sky atmosphere
        return (self._is_drizzle() or self._is_rain() or self._is_mostly() or
                self._is_mostly_cloudy() or self._is_overcast() or self._is_night() or self._is_dusk())

    def set_weather_atmosphere(self, data: dict | None):
        self._weather_data = data
        self.invalidate_background_cache()
        for cls in self.ALL_CANVAS_CLASSES:
            self.remove_css_class(cls)

        if data:
            self.add_css_class('weather-canvas-active')
            bg = data.get('bg_class', 'weather-bg-clear-day')
            cond = bg.replace('weather-bg-', '')
            if self._is_rain() and self._is_night():
                if cond not in ('rain-night', 'rain_night'):
                    cond = 'rain-night'
            elif self._is_drizzle() and self._is_night():
                if cond not in ('drizzle-night', 'drizzle_night'):
                    cond = 'drizzle-night'
            self.add_css_class(f'weather-canvas-{cond}')

            if self._is_night():
                self.add_css_class('weather-night-mode')
            else:
                self.remove_css_class('weather-night-mode')

            if self._is_dusk():
                self.add_css_class('weather-dusk-mode')
            else:
                self.remove_css_class('weather-dusk-mode')

            w = max(1070.0, float(self.get_width() or 1070))
            h = max(560.0, float(self.get_height() or 560))

            if self._is_night() and not self._is_rain() and not self._is_drizzle():
                self._ensure_stars(w, h)

            target_mode = 'rain' if self._is_rain() else ('drizzle' if self._is_drizzle() else None)
            if target_mode != self._particle_mode or not self._initialized_particles:
                self._init_particles(w, h, mode=target_mode)

            if self._has_active_animation():
                self._start_animation_if_needed()
            else:
                self._stop_animation()
        else:
            self.remove_css_class('weather-night-mode')
            self.remove_css_class('weather-dusk-mode')
            self._stop_animation()
            self._particles = []
            self._particle_mode = None
            self._initialized_particles = False

        self.queue_draw()

    set_weather_data = set_weather_atmosphere

    def pause_animation(self):
        """Pause atmospheric animation loop to conserve CPU and battery."""
        self._is_paused = True
        self._stop_animation()

    def resume_animation(self):
        """Resume atmospheric animation loop when window is active and visible."""
        self._is_paused = False
        self._start_animation_if_needed()

    def is_animation_paused(self) -> bool:
        return getattr(self, '_is_paused', False)

    def invalidate_background_cache(self):
        """Invalidate pre-rendered static background Cairo image surface cache."""
        self._cached_bg_surface = None
        self._cached_bg_key = None

    def _get_target_frame_interval(self) -> float:
        """
        Dynamic adaptive frame interval according to atmospheric physical dynamics and power modes:
        - performance (standalone default): 0.016s (~60 FPS) for rain/drizzle, 0.033s (~30 FPS) for clouds/stars.
        - balanced (app config default): 0.028s (~35 FPS) for rain/drizzle, 0.045s (~22 FPS) for clouds/stars.
        - power_saver: 0.040s (~25 FPS) for rain/drizzle, 0.066s (~15 FPS) for clouds/stars.
        """
        if not self._weather_data:
            return 0.033

        power_mode = "performance"
        if self.config_manager and hasattr(self.config_manager, "get"):
            power_mode = self.config_manager.get("power_mode", "balanced")
            if self.config_manager.get("power_save", False):
                power_mode = "power_saver"

        if power_mode == "power_saver":
            if self._is_rain() or self._is_drizzle() or bool(self._comets):
                return 0.040
            if (self._is_night() or self._is_dusk() or self._is_overcast() or
                    self._is_mostly_cloudy() or self._is_mostly() or self._is_mostly_clear()):
                return 0.066
            return 0.100

        elif power_mode == "balanced":
            if self._is_rain() or self._is_drizzle() or bool(self._comets):
                return 0.028
            if (self._is_night() or self._is_dusk() or self._is_overcast() or
                    self._is_mostly_cloudy() or self._is_mostly() or self._is_mostly_clear()):
                return 0.045
            return 0.066

        else:
            if self._is_rain() or self._is_drizzle() or bool(self._comets):
                return 0.016
            if (self._is_night() or self._is_dusk() or self._is_overcast() or
                    self._is_mostly_cloudy() or self._is_mostly() or self._is_mostly_clear()):
                return 0.033
            return 0.066

    def _get_weather_mode_signature(self) -> str:
        """Return canonical weather classification for static background rendering."""
        if not self._weather_data:
            return 'empty'
        if self._is_rain():
            return 'rain_night' if self._is_night() else 'rain'
        if self._is_drizzle():
            return 'drizzle_night' if self._is_night() else 'drizzle'
        if self._is_night():
            return 'night'
        if self._is_overcast():
            return 'overcast'
        if self._is_clear() or self._is_mostly_cloudy():
            if self._is_dusk():
                return 'dusk'
            if self._is_mostly_cloudy():
                return 'mostly_cloudy'
            return 'clear_day'
        return 'clear_day'

    def _render_static_bg(self, weather_mode: str, w: float, h: float) -> cairo.ImageSurface:
        int_w = max(1, int(w))
        int_h = max(1, int(h))
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int_w, int_h)
        cr = cairo.Context(surf)

        if weather_mode == 'rain_night':
            grad = self._get_cached_linear_grad('rain_night', h, RAIN_NIGHT_STOPS)
            cr.set_source(grad)
            cr.paint()

            glow_params = (round(w * 0.70, 1), 0.0, 10.0, round(w * 0.70, 1), 60.0, round(w * 0.45, 1))
            rain_night_glow_stops = (
                (0.00, 0.40, 0.55, 0.75, 0.12),
                (0.50, 0.25, 0.38, 0.55, 0.05),
                (1.00, 0.05, 0.08, 0.12, 0.00),
            )
            rain_glow = self._get_cached_radial_grad('rain_night_glow', glow_params, rain_night_glow_stops)
            cr.set_source(rain_glow)
            cr.paint()

        elif weather_mode == 'drizzle_night':
            grad = self._get_cached_linear_grad('drizzle_night', h, DRIZZLE_NIGHT_STOPS)
            cr.set_source(grad)
            cr.paint()

            sh_params = (round(w * 0.75, 1), round(h * 0.12, 1), 5.0, round(w * 0.75, 1), round(h * 0.12, 1), 400.0)
            drizzle_glow_stops = (
                (0.00, 0.70, 0.80, 0.92, 0.15),
                (0.45, 0.60, 0.72, 0.88, 0.06),
                (1.00, 0.20, 0.30, 0.40, 0.00),
            )
            drizzle_glow = self._get_cached_radial_grad('drizzle_night_glow', sh_params, drizzle_glow_stops)
            cr.set_source(drizzle_glow)
            cr.paint()

        elif weather_mode == 'night':
            grad = self._get_cached_linear_grad('night', h, NIGHT_STOPS)
            cr.set_source(grad)
            cr.paint()

            moon_glow_radius = max(460.0, min(800.0, w * 0.35))
            mg_params = (round(w * 0.78, 1), 0.0, 10.0, round(w * 0.78, 1), 80.0, round(moon_glow_radius, 1))
            moon_glow = self._get_cached_radial_grad('moon_glow', mg_params, MOON_GLOW_STOPS)
            cr.set_source(moon_glow)
            cr.paint()

        elif weather_mode == 'rain':
            grad = self._get_cached_linear_grad('rain', h, RAIN_STOPS)
            cr.set_source(grad)
            cr.paint()

        elif weather_mode == 'drizzle':
            if self._drizzle_surface:
                tex_w = self._drizzle_surface.get_width()
                tex_h = self._drizzle_surface.get_height()
                scale = max(w / tex_w, h / tex_h)
                ox = (w - tex_w * scale) * 0.5
                oy = 0.0

                cr.save()
                pattern = self._get_cached_cloud_pattern(self._drizzle_surface)
                matrix = cairo.Matrix()
                matrix.translate(-ox, -oy)
                matrix.scale(1.0 / scale, 1.0 / scale)
                pattern.set_matrix(matrix)
                cr.set_source(pattern)
                cr.paint()
                cr.restore()
            else:
                grad = self._get_cached_linear_grad('drizzle', h, DRIZZLE_STOPS)
                cr.set_source(grad)
                cr.paint()

        elif weather_mode == 'overcast':
            grad = self._get_cached_linear_grad('overcast', h, OVERCAST_STOPS)
            cr.set_source(grad)
            cr.paint()

        elif weather_mode == 'dusk':
            grad = self._get_cached_linear_grad('dusk', h, DUSK_STOPS)
            cr.set_source(grad)
            cr.paint()

            hg_params = (round(w * 0.50, 1), round(h * 1.05, 1), 10.0, round(w * 0.50, 1), round(h * 0.90, 1), round(w * 0.75, 1))
            horizon_glow = self._get_cached_radial_grad('dusk_horizon', hg_params, DUSK_HORIZON_STOPS)
            cr.set_source(horizon_glow)
            cr.paint()

            dusk_stars = self._ensure_dusk_stars(w, h)
            cr.save()
            for sx, sy, s_r, alpha in dusk_stars:
                cr.set_source_rgba(0.95, 0.96, 1.0, alpha)
                cr.arc(sx, sy, s_r, 0, math.pi * 2)
                cr.fill()
            cr.restore()

        elif weather_mode == 'mostly_cloudy':
            grad = self._get_cached_linear_grad('mostly_cloudy', h, MOSTLY_CLOUDY_STOPS)
            cr.set_source(grad)
            cr.paint()

            sh_params = (round(w * 0.86, 1), round(h * 0.06, 1), 5.0, round(w * 0.86, 1), round(h * 0.06, 1), 440.0)
            sun_halo = self._get_cached_radial_grad('sun_cloudy', sh_params, SUN_HALO_CLOUDY_STOPS)
            cr.set_source(sun_halo)
            cr.paint()

        else:
            grad = self._get_cached_linear_grad('clear_day', h, CLEAR_DAY_STOPS)
            cr.set_source(grad)
            cr.paint()

            sh_params = (round(w * 0.82, 1), round(h * 0.08, 1), 5.0, round(w * 0.82, 1), round(h * 0.08, 1), 420.0)
            sun_halo = self._get_cached_radial_grad('sun_clear', sh_params, SUN_HALO_CLEAR_STOPS)
            cr.set_source(sun_halo)
            cr.paint()

        return surf

    def _get_or_render_static_bg(self, w: float, h: float) -> cairo.ImageSurface:
        """
        Layer Caching: pre-renders heavy multi-stop linear gradients, radial celestial halos,
        dusk horizons, and static twilight stars once into a cached cairo.ImageSurface.
        """
        int_w = max(1, int(w))
        int_h = max(1, int(h))
        mode = self._get_weather_mode_signature()
        cache_key = (mode, int_w, int_h)

        if self._cached_bg_key == cache_key and self._cached_bg_surface is not None:
            return self._cached_bg_surface

        if self._cached_bg_surface is not None:
            try:
                self._cached_bg_surface.finish()
            except Exception:
                pass
            self._cached_bg_surface = None

        surf = self._render_static_bg(mode, w, h)
        self._cached_bg_surface = surf
        self._cached_bg_key = cache_key
        return surf

    def _init_particles(self, width: float, height: float, mode: str | None = None):
        self._particles = []
        self._particle_mode = mode
        if mode == 'rain':
            count = 125
            for _ in range(count):
                rx = random.uniform(-40.0, width + 60.0)
                ry = random.uniform(0.0, height)
                self._particles.append(RainParticle(rx, ry, width, height))
            self._initialized_particles = True
        elif mode == 'drizzle':
            count = 85
            for _ in range(count):
                rx = random.uniform(-30.0, width + 60.0)
                ry = random.uniform(0.0, height)
                self._particles.append(DrizzleParticle(rx, ry, width, height))
            self._initialized_particles = True
        else:
            self._initialized_particles = True

    def _start_animation_if_needed(self):
        if getattr(self, '_is_paused', False):
            return
        if hasattr(self, 'is_visible') and not self.is_visible():
            return
        animations_on = True
        if self.config_manager and hasattr(self.config_manager, 'get'):
            animations_on = self.config_manager.get('animations', True)

        if animations_on and self._has_active_animation():
            self._last_time = time.monotonic()
            if self._tick_id is None:
                self._tick_id = self.add_tick_callback(self._on_tick)

    def _stop_animation(self):
        if self._tick_id is not None:
            self.remove_tick_callback(self._tick_id)
            self._tick_id = None
        self._last_time = None
        self._accumulated_dt = 0.0

    def _on_map(self, widget):
        self._start_animation_if_needed()

    def _on_unmap(self, widget):
        self._stop_animation()

    def _on_tick(self, widget, frame_clock):
        if getattr(self, '_is_paused', False):
            return GLib.SOURCE_CONTINUE
        if hasattr(self, 'is_visible') and not self.is_visible():
            return GLib.SOURCE_CONTINUE

        now = time.monotonic()
        if self._last_time is None:
            self._last_time = now
            self._accumulated_dt = 0.0
            return GLib.SOURCE_CONTINUE

        raw_dt = now - self._last_time
        self._last_time = now

        if raw_dt > 0.1:
            raw_dt = 0.1

        self._accumulated_dt += raw_dt
        target_interval = self._get_target_frame_interval()
        if self._accumulated_dt < target_interval:
            return GLib.SOURCE_CONTINUE

        dt = self._accumulated_dt
        self._accumulated_dt = 0.0

        width = float(self.get_width() or 1070)
        height = float(self.get_height() or 560)
        if width <= 10 or height <= 10:
            return GLib.SOURCE_CONTINUE

        target_mode = 'rain' if self._is_rain() else ('drizzle' if self._is_drizzle() else None)
        if target_mode != self._particle_mode or not self._initialized_particles:
            self._init_particles(width, height, mode=target_mode)

        self._pulse_phase += dt * 0.7

        # Drift clouds leftwards (translating texture matrix positive by speed * dt)
        cloud_speed = 14.0 if self._is_overcast() else 20.0
        self._cloud_shift = (self._cloud_shift + cloud_speed * dt) % 1800.0

        # Update comets & comet spawning at night
        if self._is_night() and not self._is_rain() and not self._is_drizzle():
            self._ensure_stars(width, height)
            self._comet_spawn_timer -= dt
            if self._comet_spawn_timer <= 0.0:
                self._spawn_comet(width, height)
                self._comet_spawn_timer = random.uniform(7.0, 14.0)

            alive_comets = []
            for c in self._comets:
                if c.update(dt):
                    alive_comets.append(c)
            self._comets = alive_comets

        # Update falling rain or drizzle particles
        for p in self._particles:
            p.x += p.wind_dx * dt
            p.y += p.speed * dt
            if p.y > height + 30.0 or p.x < -50.0:
                p.reset(random.uniform(-10.0, width + 60.0), 0.0, width, height, initial=False)

        # For overcast or clouds without active precipitation, skip redraw on micro sub-pixel shifts
        if not (self._is_rain() or self._is_drizzle() or self._is_night() or bool(self._comets)):
            last_shift = getattr(self, "_last_drawn_shift", -999.0)
            if abs(self._cloud_shift - last_shift) < 0.85:
                return GLib.SOURCE_CONTINUE
            self._last_drawn_shift = self._cloud_shift

        self.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _draw_cloud_layer(self, cr, surface: cairo.ImageSurface, w: float, h: float, alpha: float = 1.0):
        if not surface:
            return
        tex_w = surface.get_width()
        tex_h = surface.get_height()
        scale = max(w / tex_w, h / tex_h)

        cr.save()
        pattern = self._get_cached_cloud_pattern(surface)

        matrix = cairo.Matrix()
        # Horizontal shift moves texture leftwards seamlessly
        matrix.translate(self._cloud_shift, 0.0)
        matrix.scale(1.0 / scale, 1.0 / scale)
        pattern.set_matrix(matrix)

        cr.set_source(pattern)
        if alpha < 0.999:
            cr.paint_with_alpha(alpha)
        else:
            cr.paint()
        cr.restore()

    def do_snapshot(self, snapshot):
        w = float(self.get_width() or 1070)
        h = float(self.get_height() or 560)

        if w > 0 and h > 0 and self._weather_data:
            bounds = Graphene.Rect().init(0, 0, w, h)
            cr = snapshot.append_cairo(bounds)

            # 1. Clip to rounded capsule window if corner radius is specified
            r = getattr(self, "corner_radius", 0.0)
            if r > 0.0:
                cr.new_sub_path()
                cr.arc(w - r, r, r, -math.pi / 2, 0)
                cr.arc(w - r, h - r, r, 0, math.pi / 2)
                cr.arc(r, h - r, r, math.pi / 2, math.pi)
                cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
                cr.close_path()
                cr.clip()

            # 2. Render Layer 1: Cached Static Sky Background & Celestial Halos
            static_bg = self._get_or_render_static_bg(w, h)
            if static_bg:
                cr.set_source_surface(static_bg, 0, 0)
                cr.paint()

            # 3. Render Layer 2: Dynamic Atmospheric Overlays
            if self._is_rain():
                is_night = self._is_night()
                # Drifting Rain Clouds
                rain_cloud_surface = self._rain_clouds_surface or (self._night_clouds_surface if is_night else self._overcast_surface)
                cloud_alpha = 0.78 if is_night else 0.92
                self._draw_cloud_layer(cr, rain_cloud_surface, w, h, alpha=cloud_alpha)

                # Fast Rain Drops across entire window
                if not self._initialized_particles:
                    self._init_particles(w, h, mode='rain')

                cr.save()
                cr.set_line_cap(cairo.LINE_CAP_ROUND)
                l0, l1, l2 = [], [], []
                for p in self._particles:
                    layer = getattr(p, "layer", 1)
                    if layer == 0:
                        l0.append(p)
                    elif layer == 2:
                        l2.append(p)
                    else:
                        l1.append(p)

                base_r, base_g, base_b = (0.76, 0.86, 0.98) if is_night else (0.88, 0.94, 1.0)
                layer_defs = (
                    (l0, 0.85, 0.22 if not is_night else 0.24),
                    (l1, 1.10, 0.32 if not is_night else 0.35),
                    (l2, 1.45, 0.42 if not is_night else 0.46),
                )

                for pts, w_line, alpha in layer_defs:
                    if not pts:
                        continue
                    cr.set_source_rgba(base_r, base_g, base_b, alpha)
                    cr.set_line_width(w_line)
                    for p in pts:
                        dx = p.wind_dx * (p.length / p.speed)
                        cr.move_to(p.x, p.y)
                        cr.line_to(p.x + dx, p.y + p.length)
                    cr.stroke()
                cr.restore()

            elif self._is_drizzle():
                is_night = self._is_night()
                src_x = round(w * 0.82, 1)
                src_y = round(h * 0.08, 1)
                pulse_mult = 0.70 + 0.30 * math.sin(self._pulse_phase)

                # Ambient glow using cached radial gradient
                params = (src_x, src_y, 10.0, src_x - 140.0, src_y + 360.0, 480.0)
                if is_night:
                    glow = self._get_cached_radial_grad('drizzle_pulse_night', params, DRIZZLE_PULSE_NIGHT_STOPS)
                else:
                    glow = self._get_cached_radial_grad('drizzle_pulse_day', params, DRIZZLE_PULSE_DAY_STOPS)

                cr.save()
                cr.set_source(glow)
                cr.paint_with_alpha(pulse_mult)
                cr.restore()

                # Animated Drizzle Drops
                if not self._initialized_particles:
                    self._init_particles(w, h, mode='drizzle')

                cr.save()
                cr.set_line_cap(cairo.LINE_CAP_ROUND)
                beam_origin_x = w * 0.82
                beam_origin_y = h * 0.08

                l0, l1, l2 = [], [], []
                l_beam = []
                for p in self._particles:
                    if not is_night and (p.x > w * 0.60 and p.y < h * 0.70 and
                               abs((p.x - beam_origin_x) + (p.y - beam_origin_y) * 0.70) < 220):
                        l_beam.append(p)
                    else:
                        layer = getattr(p, "layer", 1)
                        if layer == 0:
                            l0.append(p)
                        elif layer == 2:
                            l2.append(p)
                        else:
                            l1.append(p)

                base_r, base_g, base_b = (0.78, 0.88, 1.0) if is_night else (0.86, 0.92, 1.0)
                drizzle_defs = (
                    (l0, 0.75, 0.18 if not is_night else 0.20),
                    (l1, 0.95, 0.28 if not is_night else 0.32),
                    (l2, 1.20, 0.38 if not is_night else 0.42),
                )

                for pts, w_line, alpha in drizzle_defs:
                    if not pts:
                        continue
                    cr.set_source_rgba(base_r, base_g, base_b, alpha)
                    cr.set_line_width(w_line)
                    for p in pts:
                        dx = p.wind_dx * (p.length / p.speed)
                        cr.move_to(p.x, p.y)
                        cr.line_to(p.x + dx, p.y + p.length)
                    cr.stroke()

                if l_beam:
                    cr.set_source_rgba(1.0, 0.98, 0.91, 0.50)
                    cr.set_line_width(1.05)
                    for p in l_beam:
                        dx = p.wind_dx * (p.length / p.speed)
                        cr.move_to(p.x, p.y)
                        cr.line_to(p.x + dx, p.y + p.length)
                    cr.stroke()

                cr.restore()

            elif self._is_night():
                self._ensure_stars(w, h)

                # Twinkling Procedural Starfield with pre-baked halo surface
                now_mono = time.monotonic()
                cr.save()

                # Pass 1: Halos for brightest stars
                for s in self._stars:
                    twinkle = 0.60 + 0.40 * math.sin(now_mono * s.speed + s.phase)
                    cur_alpha = max(0.0, min(1.0, s.base_alpha * twinkle))
                    if s.has_halo and cur_alpha > 0.45:
                        halo_r = s.radius * 3.5
                        scale = (halo_r * 2.0) / 64.0
                        cr.save()
                        cr.translate(s.x - halo_r, s.y - halo_r)
                        cr.scale(scale, scale)
                        cr.set_source_surface(self._halo_surface, 0, 0)
                        cr.paint_with_alpha(cur_alpha * 0.40)
                        cr.restore()

                # Pass 2: Star cores batched by color and quantized brightness band
                star_bins = {}
                for s in self._stars:
                    twinkle = 0.60 + 0.40 * math.sin(now_mono * s.speed + s.phase)
                    cur_alpha = max(0.0, min(1.0, s.base_alpha * twinkle))
                    if cur_alpha < 0.08:
                        continue
                    q_alpha = 0.20 if cur_alpha < 0.32 else (0.45 if cur_alpha < 0.58 else (0.70 if cur_alpha < 0.82 else 0.95))
                    bin_key = (s.color_rgb, q_alpha)
                    if bin_key not in star_bins:
                        star_bins[bin_key] = []
                    star_bins[bin_key].append(s)

                for (color_rgb, alpha), s_list in star_bins.items():
                    cr.set_source_rgba(color_rgb[0], color_rgb[1], color_rgb[2], alpha)
                    for s in s_list:
                        cr.new_sub_path()
                        cr.arc(s.x, s.y, s.radius, 0, 2 * math.pi)
                    cr.fill()

                cr.restore()

                # Shooting Stars / Comets
                for comet in self._comets:
                    self._draw_comet(cr, comet)

                # Modular Clouds at Night:
                # Uses daytime overcast cloud deck adapted to deep night palette
                if self._is_mostly_cloudy() or self._is_overcast():
                    self._draw_cloud_layer(cr, self._night_clouds_surface or self._overcast_surface, w, h, alpha=0.90)
                elif self._is_mostly_clear():
                    self._draw_cloud_layer(cr, self._cirrus_surface, w, h, alpha=0.25)

            elif self._is_overcast():
                # Drifting Overcast Cloud Deck (Tangible grey stratocumulus clouds)
                self._draw_cloud_layer(cr, self._overcast_surface, w, h, alpha=0.92)

            elif self._is_clear() or self._is_mostly_cloudy():
                if self._is_dusk():
                    # Modular Wispy Cirrus Clouds for Ontario 'В основном ясно'
                    if self._is_mostly() or self._is_mostly_clear():
                        self._draw_cloud_layer(cr, self._cirrus_surface, w, h, alpha=0.48)

                elif self._is_mostly_cloudy():
                    # Volumetric Cumulus Clouds drifting to the LEFT
                    self._draw_cloud_layer(cr, self._cumulus_surface, w, h, alpha=0.90)

                else:
                    # Modular clouds if 'mostly clear' in daytime
                    if self._is_mostly_clear():
                        self._draw_cloud_layer(cr, self._cirrus_surface, w, h, alpha=0.40)

        # Render child widgets (header, search bar, list, preview) on top
        child = self.get_first_child()
        while child:
            self.snapshot_child(child, snapshot)
            child = child.get_next_sibling()


class WeatherAtmosphereBox(AtmosphericCapsuleBox):
    """
    Atmospheric container for preview and standalone app views.
    If placed inside another AtmosphericCapsuleBox, delegates full-window background
    rendering to the parent and simply snapshots child widgets.
    Otherwise, renders full living sky, cloud drift, falling rain drops, drizzle, stars, and comets.
    """

    def __init__(self, data: dict = None, config_manager = None, corner_radius: float = 0.0):
        super().__init__(config_manager=config_manager, corner_radius=corner_radius)
        self.data = data or {}
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.add_css_class('preview-weather-full-bg')
        self.connect('notify::parent', self._on_parent_changed)
        if data:
            self.set_weather_atmosphere(data)
            if self._has_capsule_atmosphere():
                self._stop_animation()

    def _has_capsule_atmosphere(self) -> bool:
        p = self.get_parent()
        while p:
            if isinstance(p, AtmosphericCapsuleBox) and p is not self:
                return True
            p = p.get_parent()
        return False

    def _on_parent_changed(self, *args):
        if self._has_capsule_atmosphere():
            self._stop_animation()

    def _on_map(self, widget):
        if self._has_capsule_atmosphere():
            self._stop_animation()
            return
        super()._on_map(widget)

    def _on_tick(self, widget, frame_clock):
        if self._has_capsule_atmosphere():
            self._stop_animation()
            return GLib.SOURCE_REMOVE
        return super()._on_tick(widget, frame_clock)

    def set_weather_data(self, data: dict):
        self.data = data or {}
        self.set_weather_atmosphere(data)
        if self._has_capsule_atmosphere():
            self._stop_animation()

    def _start_animation_if_needed(self):
        if self._has_capsule_atmosphere():
            self._stop_animation()
            return
        super()._start_animation_if_needed()

    def do_snapshot(self, snapshot):
        if self._has_capsule_atmosphere():
            child = self.get_first_child()
            while child:
                self.snapshot_child(child, snapshot)
                child = child.get_next_sibling()
        else:
            super().do_snapshot(snapshot)


class MoonSphereArea(Gtk.DrawingArea):
    """Photorealistic 3D Moon sphere with Cairo surface texture, mathematical terminator, and ambient earthshine."""

    def __init__(self, size=230):
        super().__init__()
        self.size = size
        self.cycle_fraction = 0.05
        self.illumination = 3
        self.tilt_deg = -15.0
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.set_draw_func(self._draw, None)

        self.texture_surface = None
        tex_path = os.path.join(WEATHER_ICONS_DIR, 'moon_surface.png')
        if os.path.exists(tex_path):
            try:
                self.texture_surface = cairo.ImageSurface.create_from_png(tex_path)
            except Exception as e:
                logger.warning("Error loading moon texture: %s", e)

    def set_phase(self, cycle_fraction: float, illumination: int, tilt_deg: float = 0.0):
        self.cycle_fraction = cycle_fraction % 1.0
        self.illumination = max(0, min(100, illumination))
        self.tilt_deg = tilt_deg
        self.queue_draw()

    def _draw(self, area, cr, width, height, user_data):
        cx = width / 2.0
        cy = height / 2.0
        r = min(width, height) * 0.44
        f = self.cycle_fraction

        # Outer ambient glow behind moon
        cr.save()
        glow = cairo.RadialGradient(cx, cy, r * 0.85, cx, cy, r * 1.25)
        glow.add_color_stop_rgba(0.0, 0.7, 0.85, 1.0, 0.12)
        glow.add_color_stop_rgba(0.5, 0.4, 0.6, 0.9, 0.04)
        glow.add_color_stop_rgba(1.0, 0.0, 0.0, 0.0, 0.0)
        cr.set_source(glow)
        cr.arc(cx, cy, r * 1.25, 0, 2 * math.pi)
        cr.fill()
        cr.restore()

        # Transform to sphere center & apply tilt
        cr.save()
        cr.translate(cx, cy)
        cr.rotate(math.radians(self.tilt_deg))

        # Base sphere clip
        cr.arc(0, 0, r, 0, 2 * math.pi)
        cr.clip()

        # Part A: Dark side (Earthshine + base craters)
        if self.texture_surface:
            tw = self.texture_surface.get_width()
            th = self.texture_surface.get_height()
            cr.save()
            cr.scale((2 * r) / tw, (2 * r) / th)
            cr.set_source_surface(self.texture_surface, -tw / 2.0, -th / 2.0)
            cr.paint_with_alpha(0.28)
            cr.restore()
        else:
            cr.set_source_rgb(0.08, 0.09, 0.12)
            cr.paint()

        # Dark side spherical shadow (edge shading)
        dark_shade = cairo.RadialGradient(0, 0, 0, 0, 0, r)
        dark_shade.add_color_stop_rgba(0.0, 0.0, 0.0, 0.0, 0.0)
        dark_shade.add_color_stop_rgba(0.7, 0.0, 0.0, 0.0, 0.45)
        dark_shade.add_color_stop_rgba(1.0, 0.0, 0.0, 0.0, 0.88)
        cr.set_source(dark_shade)
        cr.paint()

        # Part B: Sunlit side (Terminator + Full texture + 3D light)
        if self.illumination > 0:
            cr.save()
            cr.new_path()
            if self.illumination >= 99:
                cr.arc(0, 0, r, 0, 2 * math.pi)
            elif f <= 0.5:
                # Waxing: illuminated on the right
                cr.arc(0, 0, r, -math.pi / 2.0, math.pi / 2.0)
                steps = 64
                for i in range(steps + 1):
                    theta = (math.pi / 2.0) - (math.pi * i / steps)
                    x = r * math.cos(2 * math.pi * f) * math.cos(theta)
                    y = r * math.sin(theta)
                    cr.line_to(x, y)
                cr.close_path()
            else:
                # Waning: illuminated on the left
                cr.arc(0, 0, r, math.pi / 2.0, 3 * math.pi / 2.0)
                steps = 64
                for i in range(steps + 1):
                    theta = (-math.pi / 2.0) + (math.pi * i / steps)
                    x = -r * math.cos(2 * math.pi * f) * math.cos(theta)
                    y = r * math.sin(theta)
                    cr.line_to(x, y)
                cr.close_path()

            cr.clip()

            if self.texture_surface:
                tw = self.texture_surface.get_width()
                th = self.texture_surface.get_height()
                cr.save()
                cr.scale((2 * r) / tw, (2 * r) / th)
                cr.set_source_surface(self.texture_surface, -tw / 2.0, -th / 2.0)
                cr.paint_with_alpha(1.0)
                cr.restore()
            else:
                cr.set_source_rgb(0.92, 0.94, 0.98)
                cr.paint()

            # 3D sun highlight gradient
            light_x = (0.4 * r) if f <= 0.5 else (-0.4 * r)
            sun_highlight = cairo.RadialGradient(light_x, -0.15 * r, r * 0.1, light_x, -0.15 * r, r * 1.3)
            sun_highlight.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.28)
            sun_highlight.add_color_stop_rgba(0.6, 0.9, 0.95, 1.0, 0.08)
            sun_highlight.add_color_stop_rgba(1.0, 0.0, 0.0, 0.0, 0.45)
            cr.set_source(sun_highlight)
            cr.paint()

            cr.restore()

        # Part C: Subtle rim edge highlight
        rim = cairo.RadialGradient(0, 0, r * 0.94, 0, 0, r)
        rim.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.0)
        rim.add_color_stop_rgba(1.0, 0.85, 0.92, 1.0, 0.15)
        cr.set_source(rim)
        cr.arc(0, 0, r, 0, 2 * math.pi)
        cr.fill()

        cr.restore()
