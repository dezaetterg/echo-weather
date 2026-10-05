import os
import re
import sys

from logger import get_logger

logger = get_logger("utils")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, GdkPixbuf, GLib, Gtk
except ValueError as e:
    logger.critical(f"GTK/LayerShell version error: {e}")
    sys.exit(1)

# In-memory LRU Pixbuf Cache for ultra-fast icon loading
_PIXBUF_CACHE = {}
_MAX_CACHE_SIZE = 256

def set_icon_safe(widget: Gtk.Image, icon_ref: str, fallback_icon: str = "application-x-executable", pixel_size: int = None, is_paintable: bool = False, raw_pixbuf=None):
    if pixel_size:
        widget.set_pixel_size(pixel_size)

    if raw_pixbuf is not None:
        try:
            if is_paintable:
                try:
                    texture = Gdk.Texture.new_for_pixbuf(raw_pixbuf)
                    widget.set_from_paintable(texture)
                    return
                except Exception as e:
                    logger.debug("Texture from pixbuf failed: %s", e)
            widget.set_from_pixbuf(raw_pixbuf)
            return
        except Exception as e:
            logger.debug("Set from raw pixbuf failed: %s", e)

    if icon_ref and os.path.isabs(icon_ref):
        cache_key = (icon_ref, pixel_size)
        cached_pixbuf = _PIXBUF_CACHE.get(cache_key)
        if cached_pixbuf:
            widget.set_from_pixbuf(cached_pixbuf)
            return

        if os.path.exists(icon_ref):
            try:
                if pixel_size:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_ref, pixel_size, pixel_size, True)
                else:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file(icon_ref)

                if len(_PIXBUF_CACHE) >= _MAX_CACHE_SIZE:
                    _PIXBUF_CACHE.pop(next(iter(_PIXBUF_CACHE)))
                _PIXBUF_CACHE[cache_key] = pixbuf

                widget.set_from_pixbuf(pixbuf)
                return
            except Exception as e:
                logger.debug("Load file icon failed: %s", e)

    if icon_ref and not os.path.isabs(icon_ref):
        try:
            widget.set_from_icon_name(icon_ref)
            return
        except Exception as e:
            logger.debug("Load icon name failed: %s", e)

    if fallback_icon:
        try:
            widget.set_from_icon_name(fallback_icon)
            return
        except Exception as e:
            logger.debug("Load fallback icon failed: %s", e)

    try:
        widget.set_from_icon_name("application-x-executable")
    except Exception as e:
        logger.debug("Load generic fallback failed: %s", e)


def matches_shortcut(keyval: int, state: int, shortcut: str) -> bool:
    if not shortcut:
        return False
    s = shortcut.strip()
    if not s:
        return False

    modifiers = {m.lower() for m in re.findall(r"<([^>]+)>", s)}
    req_ctrl = bool({"ctrl", "control"} & modifiers)
    req_alt = "alt" in modifiers
    req_shift = "shift" in modifiers
    req_super = bool({"super", "mod4"} & modifiers)

    clean_modifiers = (
        Gdk.ModifierType.CONTROL_MASK |
        Gdk.ModifierType.ALT_MASK |
        Gdk.ModifierType.SHIFT_MASK |
        Gdk.ModifierType.SUPER_MASK
    )
    clean_state = state & clean_modifiers

    if bool(clean_state & Gdk.ModifierType.CONTROL_MASK) != req_ctrl:
        return False
    if bool(clean_state & Gdk.ModifierType.ALT_MASK) != req_alt:
        return False
    if bool(clean_state & Gdk.ModifierType.SHIFT_MASK) != req_shift:
        return False
    if bool(clean_state & Gdk.ModifierType.SUPER_MASK) != req_super:
        return False

    base_key = re.sub(r"<[^>]+>", "", s).strip().lower()
    if not base_key:
        return False

    key_name = (Gdk.keyval_name(keyval) or "").lower()
    if base_key in ("space", "пробел"):
        return keyval in (Gdk.KEY_space, Gdk.KEY_KP_Space) or key_name in ("space", "kp_space")
    elif base_key in ("return", "enter", "ввод"):
        return keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) or key_name in ("return", "kp_enter")
    elif base_key in ("tab", "таб"):
        return keyval in (Gdk.KEY_Tab, Gdk.KEY_KP_Tab, Gdk.KEY_ISO_Left_Tab) or key_name in ("tab", "kp_tab", "iso_left_tab")
    elif base_key in ("escape", "esc"):
        return keyval == Gdk.KEY_Escape or key_name in ("escape", "esc")
    else:
        return key_name == base_key


def format_shortcut_display(shortcut: str, lang: str = "en") -> str:
    if not shortcut:
        return "-"
    s = shortcut.strip()
    if not s:
        return "-"

    mods = re.findall(r"<([^>]+)>", s)
    base_key = re.sub(r"<[^>]+>", "", s).strip()

    parts = []
    found_mods = {m.lower() for m in mods}

    if "super" in found_mods or "mod4" in found_mods:
        parts.append("Super")
    if "ctrl" in found_mods or "control" in found_mods:
        parts.append("Ctrl")
    if "alt" in found_mods:
        parts.append("Alt")
    if "shift" in found_mods:
        parts.append("Shift")

    if base_key:
        bk_lower = base_key.lower()
        if bk_lower in ("space", "пробел"):
            if lang in ("ru", "kk"):
                parts.append("Пробел")
            elif lang == "uk":
                parts.append("Пробіл")
            else:
                parts.append("Space")
        elif bk_lower in ("return", "enter", "ввод"):
            parts.append("Enter")
        elif bk_lower in ("tab", "таб"):
            parts.append("Tab")
        elif bk_lower in ("escape", "esc"):
            parts.append("Esc")
        else:
            parts.append(base_key.capitalize())

    return " + ".join(parts) if parts else "-"


def set_clipboard_text(text: str) -> bool:
    """Safely set text into the default GDK clipboard."""
    if text is None:
        return False
    try:
        display = Gdk.Display.get_default()
        if display:
            clipboard = display.get_clipboard()
            if clipboard:
                clipboard.set(str(text))
                return True
    except Exception as e:
        logger.warning("Failed to set clipboard text: %s", e)
    return False


def normalize_theme_mode(theme_name: str | None) -> str:
    """Normalize a theme name to one of the 3 base modes: 'light', 'aura_glow', or 'dark'."""
    raw = (theme_name or "").strip().lower()
    if raw in ("light", "light_glass"):
        return "light"
    elif raw == "aura_glow":
        return "aura_glow"
    return "dark"


