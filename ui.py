"""
Echo Weather - Desktop Application Window
Standalone GTK4 meteorological application with atmospheric effects and detailed analysis.
"""

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from config_manager import ConfigManager
from data.wmo_conditions import MAJOR_CITIES
from i18n import SUPPORTED_LANGUAGES, get_current_language, i18n, t
from logger import get_logger
from providers.weather import WeatherProvider
from utils import trim_memory
from weather_atmosphere import AtmosphericCapsuleBox, WeatherAtmosphereBox
from weather_detail_sheet import WeatherDetailSheet
from weather_overview_view import WeatherOverviewView

logger = get_logger("ui")

SUPPORTED_LANGUAGES_DATA = [
    ("ru", "Русский", "Русский язык (Россия)", "network-workgroup-symbolic"),
    ("en", "English", "English (United States, UK, Global)", "network-workgroup-symbolic"),
    ("es", "Español", "Español (España, América Latina)", "network-workgroup-symbolic"),
    ("de", "Deutsch", "Deutsch (Deutschland, Österreich)", "network-workgroup-symbolic"),
    ("fr", "Français", "Français (France, Belgique)", "network-workgroup-symbolic"),
    ("zh", "中文 (简体)", "简体中文 (中国大陆, 新加坡)", "network-workgroup-symbolic"),
    ("ja", "日本語", "日本語 (日本)", "network-workgroup-symbolic"),
    ("it", "Italiano", "Italiano (Italia, Svizzera)", "network-workgroup-symbolic"),
    ("pt", "Português", "Português (Brasil, Portugal)", "network-workgroup-symbolic"),
    ("tr", "Türkçe", "Türkçe (Türkiye)", "network-workgroup-symbolic"),
    ("uk", "Українська", "Українська мова (Україна)", "network-workgroup-symbolic"),
    ("kk", "Қазақша", "Қазақ тілі (Қазақстан)", "network-workgroup-symbolic"),
    ("ar", "العربية", "اللغة العربية (العالم العربي)", "network-workgroup-symbolic"),
]


class EchoWeatherWindow(Gtk.ApplicationWindow):
    def __init__(self, app, initial_city: str = None, config_manager = None):
        super().__init__(application=app, title="Echo Weather")

        self.config_manager = config_manager or ConfigManager()
        cfg_lang = self.config_manager.get("language", "en")
        if cfg_lang:
            i18n.set_language(cfg_lang)

        self.weather_provider = WeatherProvider(self.config_manager)
        self.weather_provider.on_data_updated = self._on_weather_provider_updated

        saved_cities = self.config_manager.get("saved_cities", None)
        main_city = (self.config_manager.get("main_city", "") or "").strip()

        if initial_city is not None:
            self.current_city = initial_city
        elif main_city:
            self.current_city = main_city
        else:
            self.current_city = ""

        self.current_weather_data = None
        self.temp_unit = self.config_manager.get("temperature_unit", "celsius")

        self.nav_stack = None
        self.overview_view = None
        self.detail_sheet = None
        self.atmosphere_box = None
        self._empty_anim_timer_id = None
        self._lang_popover_buttons = {}
        self._empty_chip_widgets = []

        # Window properties
        self.set_default_size(
            self.config_manager.get("window_width", 650),
            self.config_manager.get("window_height", 560)
        )
        self.add_css_class("weather-window")

        self._setup_css()
        self._build_ui()
        self._setup_shortcuts()

        # Request generation counter and executor to prevent race conditions
        self._current_request_id = 0
        self._fetch_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="WeatherFetch")
        self.connect("close-request", self._on_close_request)
        self.connect("notify::is-active", self._on_window_active_changed)
        self.connect("notify::visible", self._on_window_visible_changed)

        # Load initial city if available, otherwise show empty state
        if self.current_city:
            self.load_city(self.current_city)
        else:
            self._show_empty_state()

    def _setup_css(self):
        css_provider = Gtk.CssProvider()
        css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css")
        if os.path.exists(css_path):
            try:
                css_provider.load_from_path(css_path)
                display = Gdk.Display.get_default()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
            except Exception as e:
                logger.error("Failed to load CSS: %s", e)

    def _build_ui(self):
        # Main layout box - full atmospheric canvas with live Cairo particle & cloud physics
        self.main_box = AtmosphericCapsuleBox(config_manager=self.config_manager, corner_radius=0.0)
        self.main_box.set_vexpand(True)
        self.main_box.set_hexpand(True)
        self.set_child(self.main_box)

        # 1. Custom HeaderBar / Toolbar
        header_bar = Gtk.HeaderBar()
        header_bar.add_css_class("weather-headerbar")
        self.set_titlebar(header_bar)

        # App title & icon (Clickable button navigating to empty state)
        self.home_nav_btn = Gtk.Button()
        self.home_nav_btn.add_css_class("weather-title-btn")
        self.home_nav_btn.set_tooltip_text(t("weather_home_nav_tooltip"))
        self.home_nav_btn.connect("clicked", lambda _: self._show_empty_state())

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box.set_valign(Gtk.Align.CENTER)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons", "weather", "clear-day.svg")
        if os.path.exists(icon_path):
            icon_img = Gtk.Image.new_from_file(icon_path)
            icon_img.set_pixel_size(20)
            title_box.append(icon_img)

        app_title = Gtk.Label(label="Echo Weather")
        app_title.add_css_class("weather-app-title")
        title_box.append(app_title)

        self.home_nav_btn.set_child(title_box)
        header_bar.pack_start(self.home_nav_btn)

        # City Search Entry (Centered in HeaderBar)
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_box.set_valign(Gtk.Align.CENTER)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text(t("weather_search_placeholder"))
        self.search_entry.add_css_class("weather-search-entry")
        self.search_entry.connect("activate", self._on_search_activate)
        search_box.append(self.search_entry)

        self.search_btn = Gtk.Button()
        self.search_btn.add_css_class("weather-refresh-btn")
        search_icon = Gtk.Image.new_from_icon_name("system-search-symbolic")
        search_icon.set_pixel_size(14)
        self.search_btn.set_child(search_icon)
        self.search_btn.set_tooltip_text(t("weather_search_tooltip"))
        self.search_btn.connect("clicked", lambda _: self._on_search_activate(self.search_entry))
        search_box.append(self.search_btn)

        # Pin / Unpin Button (actions moved to hero card & context menus, preserved as controller)
        self.pin_btn = Gtk.Button()
        self.pin_btn.add_css_class("weather-refresh-btn")
        self.pin_btn.add_css_class("weather-pin-btn")
        self.pin_btn_icon = Gtk.Image.new_from_icon_name("view-pin-symbolic")
        self.pin_btn_icon.set_pixel_size(14)
        self.pin_btn.set_child(self.pin_btn_icon)
        self.pin_btn.set_tooltip_text(t("weather_pin_tooltip"))
        self.pin_btn.connect("clicked", self._on_pin_toggle)

        # Main City (Home) Button (actions moved to hero card & context menus, preserved as controller)
        self.home_btn = Gtk.Button()
        self.home_btn.add_css_class("weather-refresh-btn")
        self.home_btn.add_css_class("weather-home-btn")
        self.home_btn_icon = Gtk.Image.new_from_icon_name("user-home-symbolic")
        self.home_btn_icon.set_pixel_size(14)
        self.home_btn.set_child(self.home_btn_icon)
        self.home_btn.set_tooltip_text(t("weather_main_city_btn_set"))
        self.home_btn.connect("clicked", self._on_home_toggle)

        header_bar.set_title_widget(search_box)
        self._setup_search_autocomplete()

        # Right actions: Source & Model Selector, Unit Toggle (°C / °F), Refresh
        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        right_box.set_valign(Gtk.Align.CENTER)

        # Source / Model Selector Button
        self.source_btn = Gtk.Button()
        self.source_btn.add_css_class("unit-toggle-btn")
        self.source_btn.add_css_class("source-toggle-btn")
        self._setup_source_popover()
        self._update_source_button()
        right_box.append(self.source_btn)

        # Unit Toggle Button
        self.unit_btn = Gtk.Button()
        self.unit_btn.add_css_class("unit-toggle-btn")
        unit_label = "°C" if self.temp_unit == "celsius" else "°F"
        self.unit_btn.set_label(unit_label)
        self.unit_btn.set_tooltip_text(t("weather_unit_tooltip"))
        self.unit_btn.connect("clicked", self._on_unit_toggle)
        right_box.append(self.unit_btn)


        # Refresh Button
        self.refresh_btn = Gtk.Button()
        self.refresh_btn.add_css_class("weather-refresh-btn")
        refresh_icon = Gtk.Image.new_from_icon_name("view-refresh-symbolic")
        refresh_icon.set_pixel_size(14)
        self.refresh_btn.set_child(refresh_icon)
        self.refresh_btn.set_tooltip_text(t("weather_refresh_tooltip"))
        self.refresh_btn.connect("clicked", lambda _: self.load_city(self.current_city, force_refresh=True))
        right_box.append(self.refresh_btn)

        header_bar.pack_end(right_box)

        # 2. Saved Cities Strip (Quick switcher inside horizontal ScrolledWindow)
        self.cities_scroll = Gtk.ScrolledWindow()
        self.cities_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.cities_scroll.set_has_frame(False)
        self.cities_scroll.set_hexpand(True)
        self.cities_scroll.set_vexpand(False)
        self.cities_scroll.add_css_class("weather-cities-scroll")

        # Scroll event controller for horizontal scrolling via vertical mouse wheel
        scroll_ctrl = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll_ctrl.connect("scroll", self._on_cities_strip_scroll)
        self.cities_scroll.add_controller(scroll_ctrl)

        self.cities_strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.cities_strip.add_css_class("weather-cities-strip")
        self.cities_strip.set_margin_start(16)
        self.cities_strip.set_margin_end(16)
        self.cities_strip.set_margin_top(4)
        self.cities_strip.set_margin_bottom(6)
        self.cities_scroll.set_child(self.cities_strip)
        self.main_box.append(self.cities_scroll)
        self._refresh_cities_strip()

        # 3. Content Stack (Loading vs Weather View)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(250)
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)
        self.main_box.append(self.stack)

        # Loading view
        loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        loading_box.set_valign(Gtk.Align.CENTER)
        loading_box.set_halign(Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(40, 40)
        loading_box.append(self.spinner)
        self.loading_label = Gtk.Label(label=t("weather_loading"))
        self.loading_label.add_css_class("weather-loading-text")
        loading_box.append(self.loading_label)
        self.stack.add_named(loading_box, "loading")

        # Weather content view placeholder
        self.weather_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.weather_container.set_vexpand(True)
        self.weather_container.set_hexpand(True)
        self.stack.add_named(self.weather_container, "weather")

        # Empty state view placeholder
        self.empty_container = self._build_empty_state_view()
        self.stack.add_named(self.empty_container, "empty")

    def _build_empty_state_view(self) -> Gtk.Widget:
        empty_root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        empty_root.set_valign(Gtk.Align.CENTER)
        empty_root.set_halign(Gtk.Align.CENTER)
        empty_root.set_vexpand(True)
        empty_root.set_hexpand(True)
        empty_root.add_css_class("weather-empty-root")

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.set_valign(Gtk.Align.CENTER)
        card.set_halign(Gtk.Align.CENTER)
        card.add_css_class("weather-empty-card")

        # Top bar with Language Selector
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        top_bar.set_halign(Gtk.Align.END)
        top_bar.set_hexpand(True)

        self.empty_lang_btn = Gtk.Button()
        self.empty_lang_btn.add_css_class("weather-empty-lang-btn")
        lang_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lang_btn_box.set_halign(Gtk.Align.CENTER)
        lang_btn_box.set_valign(Gtk.Align.CENTER)

        globe_icon = Gtk.Image.new_from_icon_name("network-workgroup-symbolic")
        globe_icon.set_pixel_size(13)
        lang_btn_box.append(globe_icon)

        curr_lang = i18n.get_language()
        lang_name = SUPPORTED_LANGUAGES.get(curr_lang, "Русский")
        lang_prefix = t("weather_lang_prefix")
        if not lang_prefix or lang_prefix == "weather_lang_prefix":
            lang_prefix = "Язык"
        self.empty_lang_label = Gtk.Label(label=f"{lang_prefix}: {lang_name}")
        lang_btn_box.append(self.empty_lang_label)

        arrow_icon = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        arrow_icon.set_pixel_size(10)
        lang_btn_box.append(arrow_icon)

        self.empty_lang_btn.set_child(lang_btn_box)
        top_bar.append(self.empty_lang_btn)
        card.append(top_bar)

        self._setup_language_popover()

        # 1. Animated weather icon stack without circle badge
        self.weather_icon_stack = Gtk.Stack()
        self.weather_icon_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.weather_icon_stack.set_transition_duration(600)
        self.weather_icon_stack.set_halign(Gtk.Align.CENTER)
        self.weather_icon_stack.set_valign(Gtk.Align.CENTER)
        self.weather_icon_stack.add_css_class("weather-empty-icon-stack")

        base_icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons", "weather")
        icon_specs = [
            ("clear", "clear-day.svg"),
            ("clouds", "partly-cloudy-day.svg"),
            ("rain", "rain.svg"),
            ("storm", "thunderstorm.svg"),
            ("snow", "snow.svg"),
        ]
        self._empty_icon_keys = [spec[0] for spec in icon_specs]
        self._empty_icon_idx = 0

        for key, fname in icon_specs:
            fpath = os.path.join(base_icons_dir, fname)
            if os.path.exists(fpath):
                img = Gtk.Image.new_from_file(fpath)
            else:
                img = Gtk.Image.new_from_icon_name("weather-clear-symbolic")
            img.set_pixel_size(84)
            img.add_css_class("weather-empty-animated-icon")
            img.set_halign(Gtk.Align.CENTER)
            img.set_valign(Gtk.Align.CENTER)
            self.weather_icon_stack.add_named(img, key)

        self.weather_icon_stack.set_visible_child_name("clear")
        card.append(self.weather_icon_stack)

        # 2. Title and description
        self.empty_title_label = Gtk.Label(label=t("weather_empty_title"))
        self.empty_title_label.add_css_class("weather-empty-title")
        card.append(self.empty_title_label)

        self.empty_desc_label = Gtk.Label(label=t("weather_empty_subtitle"))
        self.empty_desc_label.set_wrap(True)
        self.empty_desc_label.set_max_width_chars(46)
        self.empty_desc_label.set_justify(Gtk.Justification.CENTER)
        self.empty_desc_label.add_css_class("weather-empty-subtitle")
        card.append(self.empty_desc_label)

        # 3. Action button: "Выбрать ваш основной город"
        action_btn = Gtk.Button()
        action_btn.add_css_class("weather-empty-search-btn")
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_valign(Gtk.Align.CENTER)
        search_icon = Gtk.Image.new_from_icon_name("edit-find-symbolic")
        search_icon.set_pixel_size(15)
        btn_box.append(search_icon)
        self.empty_action_label = Gtk.Label(label=t("weather_choose_main_city"))
        btn_box.append(self.empty_action_label)
        action_btn.set_child(btn_box)
        action_btn.connect("clicked", lambda _: self._focus_search_entry())
        action_btn.set_halign(Gtk.Align.CENTER)
        card.append(action_btn)

        # 4. Quick suggestions chips with world famous cities
        chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        chips_box.set_halign(Gtk.Align.CENTER)
        chips_box.set_valign(Gtk.Align.CENTER)
        chips_box.set_margin_top(8)
        chips_box.add_css_class("weather-empty-chips-box")
        self.empty_chips_box = chips_box

        world_cities = [
            ("Токио", "Tokyo"),
            ("Лондон", "London"),
            ("Нью-Йорк", "New York"),
            ("Париж", "Paris"),
            ("Дубай", "Dubai"),
            ("Москва", "Moscow"),
        ]
        self._empty_chip_widgets = []
        for c_ru, c_en in world_cities:
            disp_name = c_en if curr_lang != "ru" else c_ru
            chip = Gtk.Button(label=disp_name)
            chip.add_css_class("weather-empty-chip")
            chip.set_tooltip_text(f"{disp_name} ({t('weather_main_city_btn_set')})")

            def _make_city_handler(target_name):
                def _handler(_):
                    if not self.config_manager.get("main_city"):
                        self.config_manager.set("main_city", target_name)
                        saved = list(self.config_manager.get("saved_cities", []))
                        if not any(c.strip().lower() == target_name.strip().lower() for c in saved):
                            saved.insert(0, target_name)
                            self.config_manager.set("saved_cities", saved)
                        self.config_manager.save()
                        self._update_home_btn()
                        self._refresh_cities_strip()
                    self.load_city(target_name)
                return _handler

            chip.connect("clicked", _make_city_handler(disp_name))
            chips_box.append(chip)
            self._empty_chip_widgets.append((chip, c_ru, c_en))

        card.append(chips_box)
        empty_root.append(card)
        return empty_root

    def _setup_language_popover(self):
        self.lang_popover = Gtk.Popover()
        self.lang_popover.add_css_class("weather-metric-popover")
        self.lang_popover.add_css_class("weather-bg-clear-day")
        self.lang_popover.set_parent(self.empty_lang_btn)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_max_content_height(340)
        scrolled.set_propagate_natural_height(True)
        scrolled.add_css_class("weather-lang-popover-scrolled")

        popover_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        popover_list.add_css_class("weather-popover-list")

        self._lang_popover_buttons = {}

        for lang_code, title_txt, desc_txt, icon_name in SUPPORTED_LANGUAGES_DATA:
            btn_item = Gtk.Button()
            btn_item.add_css_class("weather-popover-item")

            item_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

            img = Gtk.Image.new_from_icon_name(icon_name)
            img.set_pixel_size(18)
            item_box.append(img)

            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text_box.set_hexpand(True)
            text_box.set_halign(Gtk.Align.START)

            lbl_title = Gtk.Label(label=title_txt)
            lbl_title.add_css_class("weather-popover-title")
            lbl_title.set_xalign(0.0)
            text_box.append(lbl_title)

            lbl_desc = Gtk.Label(label=desc_txt)
            lbl_desc.add_css_class("weather-popover-desc")
            lbl_desc.set_xalign(0.0)
            text_box.append(lbl_desc)

            item_box.append(text_box)
            btn_item.set_child(item_box)

            def _make_lang_handler(l_code):
                return lambda _: self._on_language_selected(l_code)

            btn_item.connect("clicked", _make_lang_handler(lang_code))
            popover_list.append(btn_item)
            self._lang_popover_buttons[lang_code] = btn_item

        scrolled.set_child(popover_list)
        self.lang_popover.set_child(scrolled)
        self.empty_lang_btn.connect("clicked", lambda _: self.lang_popover.popup())
        self._update_language_button()

    def _update_language_button(self):
        curr_lang = i18n.get_language()
        lang_name = SUPPORTED_LANGUAGES.get(curr_lang, "Русский")
        prefix = t("weather_lang_prefix")
        if not prefix or prefix == "weather_lang_prefix":
            prefix = "Язык"
        if hasattr(self, "empty_lang_label") and self.empty_lang_label:
            self.empty_lang_label.set_label(f"{prefix}: {lang_name}")
        if hasattr(self, "empty_lang_btn") and self.empty_lang_btn:
            self.empty_lang_btn.set_tooltip_text(f"{prefix}: {lang_name} (выбор языка)")

        if hasattr(self, "_lang_popover_buttons"):
            for l_code, btn in self._lang_popover_buttons.items():
                if l_code == curr_lang:
                    btn.add_css_class("weather-popover-item-active")
                else:
                    btn.remove_css_class("weather-popover-item-active")

    def _on_language_selected(self, lang_code: str):
        i18n.set_language(lang_code)
        self.config_manager.set("language", lang_code)
        self.config_manager.save()
        if hasattr(self, "lang_popover") and self.lang_popover:
            self.lang_popover.popdown()
        self._update_all_translations()

    def _update_all_translations(self):
        # HeaderBar elements
        if hasattr(self, "home_nav_btn") and self.home_nav_btn:
            self.home_nav_btn.set_tooltip_text(t("weather_home_nav_tooltip"))
        if hasattr(self, "search_entry") and self.search_entry:
            self.search_entry.set_placeholder_text(t("weather_search_placeholder"))
        if hasattr(self, "search_btn") and self.search_btn:
            self.search_btn.set_tooltip_text(t("weather_search_tooltip"))
        if hasattr(self, "unit_btn") and self.unit_btn:
            self.unit_btn.set_tooltip_text(t("weather_unit_tooltip"))
        if hasattr(self, "refresh_btn") and self.refresh_btn:
            self.refresh_btn.set_tooltip_text(t("weather_refresh_tooltip"))

        self._update_pin_button()
        self._update_home_btn()
        self._update_source_button()
        self._update_source_popover_texts()
        self._update_language_button()
        self._update_empty_state_texts()
        self._refresh_cities_strip()

        if hasattr(self, "loading_label") and self.loading_label:
            if self.current_city:
                self.loading_label.set_label(t("weather_loading_city", city=self.current_city))
            else:
                self.loading_label.set_label(t("weather_loading"))

        # If weather overview is currently shown, rebuild it with new language
        if hasattr(self, "overview_view") and self.overview_view and self.current_weather_data:
            self.overview_view.update_data(self.current_weather_data, self.temp_unit)

    def _update_empty_state_texts(self):
        if hasattr(self, "empty_title_label") and self.empty_title_label:
            self.empty_title_label.set_label(t("weather_empty_title"))
        if hasattr(self, "empty_desc_label") and self.empty_desc_label:
            self.empty_desc_label.set_label(t("weather_empty_subtitle"))
        if hasattr(self, "empty_action_label") and self.empty_action_label:
            self.empty_action_label.set_label(t("weather_choose_main_city"))
        if hasattr(self, "_empty_chip_widgets"):
            curr_lang = i18n.get_language()
            for chip, name_ru, name_en in self._empty_chip_widgets:
                disp_name = name_en if curr_lang != "ru" else name_ru
                chip.set_label(disp_name)
                chip.set_tooltip_text(f"{disp_name} ({t('weather_main_city_btn_set')})")

    def _setup_search_autocomplete(self):
        self.search_popover = Gtk.Popover()
        self.search_popover.add_css_class("weather-metric-popover")
        self.search_popover.add_css_class("weather-search-popover")
        self.search_popover.set_parent(self.search_entry)
        self.search_popover.set_position(Gtk.PositionType.BOTTOM)
        self.search_popover.set_has_arrow(True)
        # Disable autohide to prevent Wayland xdg_popup from taking exclusive keyboard grab
        self.search_popover.set_autohide(False)
        self.search_popover.set_focusable(False)
        self.search_popover.set_can_focus(False)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_max_content_height(280)
        scrolled.set_propagate_natural_height(True)
        scrolled.add_css_class("weather-search-popover-scrolled")
        scrolled.set_focusable(False)
        scrolled.set_can_focus(False)

        self.search_results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.search_results_box.add_css_class("weather-popover-list")
        self.search_results_box.set_focusable(False)
        self.search_results_box.set_can_focus(False)
        scrolled.set_child(self.search_results_box)
        self.search_popover.set_child(scrolled)

        self._search_suggestion_items = []
        self._active_suggestion_idx = -1
        self.search_popover.connect("closed", self._on_search_popover_closed)

        # Key controller on search_entry for arrow navigation and Escape
        self._search_key_ctrl = Gtk.EventControllerKey()
        self._search_key_ctrl.connect("key-pressed", self._on_search_entry_key_pressed)
        self.search_entry.add_controller(self._search_key_ctrl)

        # Focus controller on search_entry to dismiss non-autohide popover when focus leaves
        self._search_focus_ctrl = Gtk.EventControllerFocus()
        def _on_search_focus_leave(_):
            if hasattr(self, "search_popover") and self.search_popover and self.search_popover.get_visible():
                self.search_popover.popdown()
        self._search_focus_ctrl.connect("leave", _on_search_focus_leave)
        self.search_entry.add_controller(self._search_focus_ctrl)

        self.search_entry.connect("changed", self._on_search_entry_changed)

    def _on_search_popover_closed(self, popover):
        self._active_suggestion_idx = -1
        for btn, _ in self._search_suggestion_items:
            btn.remove_css_class("weather-popover-item-active")

    def _on_search_entry_key_pressed(self, ctrl, keyval, keycode, state):
        if not hasattr(self, "search_popover") or not self.search_popover:
            return False

        if keyval == Gdk.KEY_Escape:
            if self.search_popover.get_visible():
                self.search_popover.popdown()
                return True

        if keyval in (Gdk.KEY_Down, Gdk.KEY_Up):
            if self.search_popover.get_visible() and self._search_suggestion_items:
                n = len(self._search_suggestion_items)
                if keyval == Gdk.KEY_Down:
                    self._active_suggestion_idx = min(n - 1, self._active_suggestion_idx + 1)
                else:
                    self._active_suggestion_idx = max(-1, self._active_suggestion_idx - 1)

                for i, (btn, target_city) in enumerate(self._search_suggestion_items):
                    if i == self._active_suggestion_idx:
                        btn.add_css_class("weather-popover-item-active")
                    else:
                        btn.remove_css_class("weather-popover-item-active")
                return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if (
                self.search_popover.get_visible()
                and 0 <= self._active_suggestion_idx < len(self._search_suggestion_items)
            ):
                btn, _ = self._search_suggestion_items[self._active_suggestion_idx]
                btn.emit("clicked")
                return True

        return False

    def _show_search_suggestions(self):
        query = self.search_entry.get_text().strip()
        if query:
            self._on_search_entry_changed(self.search_entry)
            return

        curr_lang = get_current_language()
        is_ru = (curr_lang == "ru")
        world_cities = [
            ("токио", "Токио", "Tokyo"),
            ("лондон", "Лондон", "London"),
            ("нью-йорк", "Нью-Йорк", "New York"),
            ("париж", "Париж", "Paris"),
            ("дубай", "Дубай", "Dubai"),
            ("москва", "Москва", "Moscow"),
        ]
        top_matches = []
        for city_k, name_ru, name_en in world_cities:
            info = MAJOR_CITIES.get(city_k, {})
            disp_name = name_ru if is_ru else name_en
            disp_country = info.get("country_ru" if is_ru else "country_en", "")
            lat = info.get("lat", 0.0)
            lon = info.get("lon", 0.0)
            top_matches.append((disp_name, disp_country, lat, lon, city_k))

        self._render_search_suggestions(top_matches)

    def _on_search_entry_changed(self, entry):
        query = entry.get_text().strip().lower()
        if not query or len(query) < 1:
            if hasattr(self, "search_popover") and self.search_popover:
                self.search_popover.popdown()
            return

        curr_lang = get_current_language()
        is_ru = (curr_lang == "ru")

        matches = []
        for city_k, info in MAJOR_CITIES.items():
            name_ru = info.get("name_ru", "")
            name_en = info.get("name_en", "")
            keywords = info.get("keywords", [])
            country_ru = info.get("country_ru", "")
            country_en = info.get("country_en", "")
            lat = info.get("lat", 0.0)
            lon = info.get("lon", 0.0)

            score = 0
            if name_ru.lower().startswith(query) or name_en.lower().startswith(query) or city_k.startswith(query):
                score = 3
            elif any(kw.startswith(query) for kw in keywords):
                score = 2
            elif query in name_ru.lower() or query in name_en.lower() or query in city_k or any(query in kw for kw in keywords):
                score = 1

            if score > 0:
                disp_name = name_ru if is_ru else name_en
                disp_country = country_ru if is_ru else country_en
                matches.append((score, disp_name, disp_country, lat, lon, city_k))

        matches.sort(key=lambda x: (-x[0], x[1]))
        top_matches = [(m[1], m[2], m[3], m[4], m[5]) for m in matches[:5]]

        if not top_matches:
            if hasattr(self, "search_popover") and self.search_popover:
                self.search_popover.popdown()
            return

        self._render_search_suggestions(top_matches)

    def _render_search_suggestions(self, suggestions):
        if not hasattr(self, "search_results_box") or not self.search_results_box:
            return

        while child := self.search_results_box.get_first_child():
            self.search_results_box.remove(child)

        self._search_suggestion_items = []
        self._active_suggestion_idx = -1

        for disp_name, disp_country, lat, lon, _city_k in suggestions:
            btn_item = Gtk.Button()
            btn_item.add_css_class("weather-popover-item")
            btn_item.set_focusable(False)
            btn_item.set_focus_on_click(False)

            item_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            item_box.set_focusable(False)
            item_box.set_can_focus(False)

            img = Gtk.Image.new_from_icon_name("mark-location-symbolic")
            img.set_pixel_size(18)
            img.set_focusable(False)
            img.set_can_focus(False)
            item_box.append(img)

            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text_box.set_hexpand(True)
            text_box.set_halign(Gtk.Align.START)
            text_box.set_focusable(False)
            text_box.set_can_focus(False)

            lbl_title = Gtk.Label(label=disp_name)
            lbl_title.add_css_class("weather-popover-title")
            lbl_title.set_xalign(0.0)
            lbl_title.set_focusable(False)
            lbl_title.set_can_focus(False)
            text_box.append(lbl_title)

            lat_str = f"{abs(lat):.2f}° {'N' if lat >= 0 else 'S'}"
            lon_str = f"{abs(lon):.2f}° {'E' if lon >= 0 else 'W'}"
            coord_str = f"{disp_country} • {lat_str}, {lon_str}"
            lbl_desc = Gtk.Label(label=coord_str)
            lbl_desc.add_css_class("weather-popover-desc")
            lbl_desc.set_xalign(0.0)
            lbl_desc.set_focusable(False)
            lbl_desc.set_can_focus(False)
            text_box.append(lbl_desc)

            item_box.append(text_box)
            btn_item.set_child(item_box)

            def _make_select_handler(target_city):
                def _handler(_):
                    if hasattr(self, "search_popover") and self.search_popover:
                        self.search_popover.popdown()
                    self.search_entry.set_text(target_city)
                    if not self.config_manager.get("main_city"):
                        self.config_manager.set("main_city", target_city)
                        saved = list(self.config_manager.get("saved_cities", []))
                        if not any(c.strip().lower() == target_city.strip().lower() for c in saved):
                            saved.insert(0, target_city)
                            self.config_manager.set("saved_cities", saved)
                        self.config_manager.save()
                        self._update_home_btn()
                        self._refresh_cities_strip()
                    self.load_city(target_city)
                return _handler

            btn_item.connect("clicked", _make_select_handler(disp_name))
            self.search_results_box.append(btn_item)
            self._search_suggestion_items.append((btn_item, disp_name))

        if hasattr(self, "search_popover") and self.search_popover:
            if not self.search_popover.get_visible():
                self.search_popover.popup()

    def _cycle_empty_weather_icon(self):
        if not hasattr(self, "weather_icon_stack") or not self.weather_icon_stack:
            return False
        if hasattr(self, "stack") and self.stack and self.stack.get_visible_child_name() != "empty":
            return True
        self._empty_icon_idx = (self._empty_icon_idx + 1) % len(self._empty_icon_keys)
        self.weather_icon_stack.set_visible_child_name(self._empty_icon_keys[self._empty_icon_idx])
        return True

    def _start_empty_icon_animation(self):
        if getattr(self, "_empty_anim_timer_id", None) is None:
            self._empty_anim_timer_id = GLib.timeout_add(2200, self._cycle_empty_weather_icon)

    def _stop_empty_icon_animation(self):
        if getattr(self, "_empty_anim_timer_id", None) is not None:
            GLib.source_remove(self._empty_anim_timer_id)
            self._empty_anim_timer_id = None

    def _focus_search_entry(self):
        if hasattr(self, "search_entry") and self.search_entry:
            self.search_entry.grab_focus()
            self._show_search_suggestions()

    def _show_empty_state(self):
        if self.is_detail_open():
            self.open_overview()
        self.current_city = ""
        self.current_weather_data = None
        if hasattr(self, "search_entry") and self.search_entry:
            self.search_entry.set_text("")
        if hasattr(self, "pin_btn") and self.pin_btn:
            self.pin_btn.remove_css_class("active")
            self.pin_btn.set_sensitive(False)
            self.pin_btn.set_tooltip_text(t("weather_pin_tooltip"))
        if hasattr(self, "home_btn") and self.home_btn:
            self.home_btn.remove_css_class("active")
            self.home_btn.set_sensitive(False)
            self.home_btn.set_tooltip_text(t("weather_main_city_btn_set"))
        self._refresh_cities_strip()
        if hasattr(self, "stack") and self.stack:
            self.stack.set_visible_child_name("empty")

        canvas_classes = [
            "weather-canvas-active", "weather-canvas-empty", "weather-canvas-clear-day", "weather-canvas-clear-dusk",
            "weather-canvas-clear-night", "weather-canvas-clouds-day", "weather-canvas-clouds-night",
            "weather-canvas-rain-day", "weather-canvas-rain-night", "weather-canvas-drizzle-day",
            "weather-canvas-drizzle-night", "weather-canvas-storm-day", "weather-canvas-storm-night",
            "weather-canvas-snow-day", "weather-canvas-snow-night", "weather-canvas-fog-day",
            "weather-canvas-fog-night", "weather-night-mode", "weather-dusk-mode"
        ]
        for c in canvas_classes:
            self.remove_css_class(c)
        self.add_css_class("weather-canvas-empty")
        self.add_css_class("weather-canvas-clear-day")

        sunny_atmosphere = {
            "bg_class": "weather-bg-clear-day",
            "time_of_day": "day",
            "is_day": 1,
        }
        if hasattr(self, "main_box") and self.main_box:
            self.main_box.set_weather_atmosphere(sunny_atmosphere)

        if hasattr(self, "lang_popover") and self.lang_popover:
            for c in canvas_classes:
                self.lang_popover.remove_css_class(c)
            self.lang_popover.add_css_class("weather-bg-clear-day")

        self._start_empty_icon_animation()
        self._update_language_button()
        self._update_empty_state_texts()

    def _on_cities_strip_scroll(self, ctrl, dx, dy):
        if not hasattr(self, "cities_scroll") or not self.cities_scroll:
            return False
        hadj = self.cities_scroll.get_hadjustment()
        if hadj and dy != 0:
            step = 50.0
            new_val = max(hadj.get_lower(), min(hadj.get_upper() - hadj.get_page_size(), hadj.get_value() + dy * step))
            hadj.set_value(new_val)
            return True
        return False

    def _scroll_pill_to_view(self, btn):
        if not hasattr(self, "cities_scroll") or not self.cities_scroll:
            return False
        hadj = self.cities_scroll.get_hadjustment()
        if not hadj:
            return False
        alloc = btn.get_allocation()
        x = alloc.x
        w = alloc.width
        val = hadj.get_value()
        page_size = hadj.get_page_size()
        if page_size <= 0:
            return False
        if x < val:
            hadj.set_value(max(hadj.get_lower(), x - 10))
        elif x + w > val + page_size:
            hadj.set_value(min(hadj.get_upper() - page_size, x + w - page_size + 10))
        return False

    def _on_pin_toggle(self, _=None):
        target_name = self.current_city
        if self.current_weather_data and self.current_weather_data.get("city_name"):
            target_name = self.current_weather_data.get("city_name")

        if not target_name:
            return

        saved = list(self.config_manager.get("saved_cities", []))
        t_lower = target_name.strip().lower()
        is_already_pinned = any(c.strip().lower() == t_lower for c in saved)

        if is_already_pinned:
            new_saved = [c for c in saved if c.strip().lower() != t_lower]
            self.config_manager.set("saved_cities", new_saved)
        else:
            saved.append(target_name)
            self.config_manager.set("saved_cities", saved)

        self.config_manager.save()
        self._update_pin_button()
        self._refresh_cities_strip()

        if self.current_weather_data:
            self.current_weather_data["is_pinned"] = not is_already_pinned
            if hasattr(self, "overview_view") and self.overview_view:
                self.overview_view.update_data(self.current_weather_data, self.temp_unit)

    def _unpin_city(self, city_name: str):
        saved = list(self.config_manager.get("saved_cities", []))
        c_lower = city_name.strip().lower()
        new_saved = [c for c in saved if c.strip().lower() != c_lower]
        self.config_manager.set("saved_cities", new_saved)
        self.config_manager.save()
        self._update_pin_button()
        self._refresh_cities_strip()

        if self.current_weather_data:
            curr_c = (self.current_weather_data.get("city_name") or self.current_city or "").strip().lower()
            if curr_c == c_lower:
                self.current_weather_data["is_pinned"] = False
                if hasattr(self, "overview_view") and self.overview_view:
                    self.overview_view.update_data(self.current_weather_data, self.temp_unit)

    def _update_pin_button(self):
        if not hasattr(self, "pin_btn") or not self.pin_btn:
            return

        target_name = self.current_city
        if self.current_weather_data and self.current_weather_data.get("city_name"):
            target_name = self.current_weather_data.get("city_name")

        if not target_name:
            self.pin_btn.set_sensitive(False)
            self.pin_btn.remove_css_class("active")
            self.pin_btn.set_tooltip_text(t("weather_pin_tooltip"))
            return

        self.pin_btn.set_sensitive(True)
        saved = list(self.config_manager.get("saved_cities", []))
        t_lower = target_name.strip().lower()
        is_pinned = any(c.strip().lower() == t_lower for c in saved)

        if is_pinned:
            if not self.pin_btn.has_css_class("active"):
                self.pin_btn.add_css_class("active")
            self.pin_btn.set_tooltip_text(f"{t('weather_unpin_tooltip')}: «{target_name}»")
        else:
            self.pin_btn.remove_css_class("active")
            self.pin_btn.set_tooltip_text(f"{t('weather_pin_tooltip')}: «{target_name}»")

    def _on_home_toggle(self, _=None):
        target_name = self.current_city
        if self.current_weather_data and self.current_weather_data.get("city_name"):
            target_name = self.current_weather_data.get("city_name")

        if not target_name:
            return

        current_main = self.config_manager.get("main_city", "")
        t_lower = target_name.strip().lower()
        cm_lower = (current_main or "").strip().lower()

        if cm_lower == t_lower:
            self.config_manager.set("main_city", "")
        else:
            self.config_manager.set("main_city", target_name)
            saved = list(self.config_manager.get("saved_cities", []))
            if not any(c.strip().lower() == t_lower for c in saved):
                saved.insert(0, target_name)
                self.config_manager.set("saved_cities", saved)

        self.config_manager.save()
        self._update_home_btn()
        self._refresh_cities_strip()

        if self.current_weather_data:
            is_main = (self.config_manager.get("main_city", "").strip().lower() == t_lower)
            self.current_weather_data["is_main_city"] = is_main
            if hasattr(self, "overview_view") and self.overview_view:
                self.overview_view.update_data(self.current_weather_data, self.temp_unit)

    def _update_home_btn(self):
        if not hasattr(self, "home_btn") or not self.home_btn:
            return

        target_name = self.current_city
        if self.current_weather_data and self.current_weather_data.get("city_name"):
            target_name = self.current_weather_data.get("city_name")

        if not target_name:
            self.home_btn.set_sensitive(False)
            self.home_btn.remove_css_class("active")
            self.home_btn.set_tooltip_text(t("weather_main_city_btn_set"))
            return

        self.home_btn.set_sensitive(True)
        main_c = (self.config_manager.get("main_city", "") or "").strip().lower()
        t_lower = target_name.strip().lower()
        is_main = (main_c == t_lower)

        if is_main:
            if not self.home_btn.has_css_class("active"):
                self.home_btn.add_css_class("active")
            self.home_btn.set_tooltip_text(f"{target_name}: {t('weather_main_city_btn_active')}")
        else:
            self.home_btn.remove_css_class("active")
            self.home_btn.set_tooltip_text(f"{target_name}: {t('weather_main_city_btn_set')}")

    def _refresh_cities_strip(self):
        if not hasattr(self, "cities_strip") or not self.cities_strip:
            return

        # Clear existing buttons
        while child := self.cities_strip.get_first_child():
            self.cities_strip.remove(child)

        saved = list(self.config_manager.get("saved_cities", ["Moscow", "Saint Petersburg", "Novokuznetsk", "New York"]))
        main_c = (self.config_manager.get("main_city", "") or "").strip().lower()

        if hasattr(self, "cities_scroll") and self.cities_scroll:
            self.cities_scroll.set_visible(len(saved) > 0)

        cur_lower = (self.current_city or "").strip().lower()
        active_btn = None

        for city in saved:
            btn = Gtk.Button()
            btn.add_css_class("city-pill-btn")
            is_main = (city.strip().lower() == main_c)
            if is_main:
                btn.add_css_class("is-main-city")

            pill_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            if is_main:
                home_icon = Gtk.Image.new_from_icon_name("user-home-symbolic")
                home_icon.set_pixel_size(12)
                home_icon.add_css_class("weather-main-city-icon")
                pill_box.append(home_icon)

            lbl = Gtk.Label(label=city)
            pill_box.append(lbl)
            btn.set_child(pill_box)

            if city.strip().lower() == cur_lower:
                btn.add_css_class("active")
                active_btn = btn

            hint = t("weather_main_city_strip_hint")
            if is_main:
                badge = t("weather_main_city_badge")
                btn.set_tooltip_text(f"{city} ({badge})\n({hint})")
            else:
                btn.set_tooltip_text(f"{city}\n({hint})")

            btn.connect("clicked", lambda _, c=city: self.load_city(c))

            # Right click shows context menu (Set Main City / Unpin), Middle click directly unpins
            def _show_pill_menu(btn_target, target_city, is_curr_main):
                pop = Gtk.Popover()
                pop.set_parent(btn_target)
                pop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                pop_box.add_css_class("weather-popover-list")

                btn_toggle_main = Gtk.Button()
                btn_toggle_main.add_css_class("weather-popover-item")
                m_txt = t("weather_main_city_btn_active") if is_curr_main else t("weather_main_city_btn_set")
                btn_toggle_main.set_label(f"🏠 {m_txt}")
                def _do_toggle_main(_):
                    pop.popdown()
                    if is_curr_main:
                        self.config_manager.set("main_city", "")
                    else:
                        self.config_manager.set("main_city", target_city)
                    self.config_manager.save()
                    self._update_home_btn()
                    self._refresh_cities_strip()
                    if self.current_weather_data:
                        t_lower = target_city.strip().lower()
                        curr_lower = (self.current_weather_data.get("city_name") or self.current_city or "").strip().lower()
                        if curr_lower == t_lower:
                            self.current_weather_data["is_main_city"] = not is_curr_main
                            if hasattr(self, "overview_view") and self.overview_view:
                                self.overview_view.update_data(self.current_weather_data, self.temp_unit)
                btn_toggle_main.connect("clicked", _do_toggle_main)
                pop_box.append(btn_toggle_main)

                btn_unpin = Gtk.Button()
                btn_unpin.add_css_class("weather-popover-item")
                btn_unpin.set_label(f"❌ {t('weather_unpin_tooltip')}")
                def _do_unpin(_):
                    pop.popdown()
                    self._unpin_city(target_city)
                btn_unpin.connect("clicked", _do_unpin)
                pop_box.append(btn_unpin)

                pop.set_child(pop_box)
                pop.popup()

            click_gesture = Gtk.GestureClick.new()
            click_gesture.set_button(0)
            def _on_pill_clicked(gesture, n_press, x, y, c=city, m=is_main, b=btn):
                btn_num = gesture.get_current_button()
                if btn_num == 3:
                    _show_pill_menu(b, c, m)
                elif btn_num == 2:
                    self._unpin_city(c)
            click_gesture.connect("pressed", _on_pill_clicked)
            btn.add_controller(click_gesture)

            self.cities_strip.append(btn)

        if active_btn and hasattr(self, "cities_scroll") and self.cities_scroll:
            GLib.idle_add(self._scroll_pill_to_view, active_btn)

        self._update_pin_button()
        self._update_home_btn()

    def _setup_shortcuts(self):
        self.key_controller = Gtk.EventControllerKey()
        self.key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(self.key_controller)

    def _on_key_pressed(self, ctrl, keyval, keycode, state):
        if keyval in (Gdk.KEY_F5,):
            self.load_city(self.current_city, force_refresh=True)
            return True
        if (state & Gdk.ModifierType.CONTROL_MASK) and keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self.load_city(self.current_city, force_refresh=True)
            return True
        if (state & Gdk.ModifierType.CONTROL_MASK) and keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self.search_entry.grab_focus()
            return True
        if keyval in (Gdk.KEY_Escape,):
            if self.is_detail_open():
                self.open_overview()
                return True
        if (state & Gdk.ModifierType.ALT_MASK) and keyval in (Gdk.KEY_Left,):
            if self.is_detail_open():
                self.open_overview()
                return True
        if hasattr(Gdk, "KEY_Back") and keyval == Gdk.KEY_Back:
            if self.is_detail_open():
                self.open_overview()
                return True
        return False

    def _on_search_activate(self, entry):
        if hasattr(self, "search_popover") and self.search_popover:
            self.search_popover.popdown()
        text = entry.get_text().strip()
        if text:
            if not self.config_manager.get("main_city"):
                self.config_manager.set("main_city", text)
                saved = list(self.config_manager.get("saved_cities", []))
                if not any(c.strip().lower() == text.strip().lower() for c in saved):
                    saved.insert(0, text)
                    self.config_manager.set("saved_cities", saved)
                self.config_manager.save()
                self._update_home_btn()
                self._refresh_cities_strip()
            self.load_city(text)
        elif not self.current_city or not self.current_weather_data:
            self._show_empty_state()

    def _on_unit_toggle(self, btn):
        if self.temp_unit == "celsius":
            self.temp_unit = "fahrenheit"
        else:
            self.temp_unit = "celsius"

        self.config_manager.set("temperature_unit", self.temp_unit)
        self.unit_btn.set_label("°C" if self.temp_unit == "celsius" else "°F")

        if self.overview_view:
            self.overview_view.set_temp_unit(self.temp_unit)
        if self.detail_sheet:
            self.detail_sheet.set_temp_unit(self.temp_unit)


    def _setup_source_popover(self):
        self.source_popover = Gtk.Popover()
        self.source_popover.add_css_class("weather-metric-popover")
        self.source_popover.set_parent(self.source_btn)

        popover_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        popover_list.add_css_class("weather-popover-list")

        self._source_popover_buttons = {}
        self._source_popover_items = []

        sources = [
            (
                "consensus",
                "weather_source_consensus_title",
                "weather_source_consensus_desc",
                "network-workgroup-symbolic",
                "Мультимодельный консенсус",
                "ECMWF IFS + ICON + MET Norway (высокая точность)",
            ),
            (
                "ecmwf",
                "weather_source_ecmwf_title",
                "weather_source_ecmwf_desc",
                "weather-few-clouds-symbolic",
                "ECMWF IFS (Европа)",
                "Флагманская численная модель высокого разрешения",
            ),
            (
                "icon",
                "weather_source_icon_title",
                "weather_source_icon_desc",
                "weather-overcast-symbolic",
                "DWD ICON (Германия)",
                "Высокодетализированная физическая модель",
            ),
            (
                "met_norway",
                "weather_source_met_title",
                "weather_source_met_desc",
                "weather-clear-symbolic",
                "MET Norway (Скандинавия)",
                "Официальный прогноз Норвежского метеоинститута",
            ),
            (
                "open_meteo",
                "weather_source_om_title",
                "weather_source_om_desc",
                "system-search-symbolic",
                "Open-Meteo Auto",
                "Автоматический подбор оптимальной модели по региону",
            ),
        ]

        for src_id, title_k, desc_k, icon_name, title_fb, desc_fb in sources:
            btn_item = Gtk.Button()
            btn_item.add_css_class("weather-popover-item")

            item_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

            img = Gtk.Image.new_from_icon_name(icon_name)
            img.set_pixel_size(18)
            item_box.append(img)

            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text_box.set_hexpand(True)
            text_box.set_halign(Gtk.Align.START)

            title_txt = t(title_k)
            if title_txt == title_k:
                title_txt = title_fb
            lbl_title = Gtk.Label(label=title_txt)
            lbl_title.add_css_class("weather-popover-title")
            lbl_title.set_xalign(0.0)
            text_box.append(lbl_title)

            desc_txt = t(desc_k)
            if desc_txt == desc_k:
                desc_txt = desc_fb
            lbl_desc = Gtk.Label(label=desc_txt)
            lbl_desc.add_css_class("weather-popover-desc")
            lbl_desc.set_xalign(0.0)
            text_box.append(lbl_desc)

            item_box.append(text_box)
            btn_item.set_child(item_box)

            def _make_handler(s_id):
                return lambda _: self._on_source_selected(s_id)

            btn_item.connect("clicked", _make_handler(src_id))
            popover_list.append(btn_item)
            self._source_popover_buttons[src_id] = btn_item
            self._source_popover_items.append((src_id, lbl_title, lbl_desc, title_k, desc_k, title_fb, desc_fb))

        self.source_popover.set_child(popover_list)
        self.source_btn.connect("clicked", lambda _: self.source_popover.popup())

    def _update_source_button(self):
        curr = self.config_manager.get("forecast_source", "consensus")
        consensus_lbl = t("weather_model_btn_consensus")
        if consensus_lbl == "weather_model_btn_consensus":
            consensus_lbl = "Consensus"
        short_names = {
            "consensus": consensus_lbl,
            "ecmwf": "ECMWF",
            "icon": "ICON",
            "met_norway": "MET Norway",
            "open_meteo": "Open-Meteo",
        }
        lbl = short_names.get(curr, consensus_lbl)
        btn_txt = t("weather_model_btn_label", name=lbl)
        if "{name}" in btn_txt or btn_txt == "weather_model_btn_label":
            btn_txt = f"Model: {lbl}"
        self.source_btn.set_label(btn_txt)

        tt_txt = t("weather_model_tooltip", name=lbl)
        if "{name}" in tt_txt or tt_txt == "weather_model_tooltip":
            tt_txt = f"Forecast model: {lbl}"
        self.source_btn.set_tooltip_text(tt_txt)

        if hasattr(self, "_source_popover_buttons"):
            for s_id, btn in self._source_popover_buttons.items():
                if s_id == curr:
                    btn.add_css_class("weather-popover-item-active")
                else:
                    btn.remove_css_class("weather-popover-item-active")

    def _update_source_popover_texts(self):
        if not hasattr(self, "_source_popover_items"):
            return
        for _src_id, lbl_title, lbl_desc, title_k, desc_k, title_fb, desc_fb in self._source_popover_items:
            t_txt = t(title_k)
            if t_txt == title_k:
                t_txt = title_fb
            lbl_title.set_label(t_txt)

            d_txt = t(desc_k)
            if d_txt == desc_k:
                d_txt = desc_fb
            lbl_desc.set_label(d_txt)

    def _on_source_selected(self, source_id: str):
        self.config_manager.set("forecast_source", source_id)
        self.config_manager.save()
        if hasattr(self, "source_popover"):
            self.source_popover.popdown()
        self._update_source_button()
        if self.current_weather_data:
            self.current_weather_data["forecast_source"] = source_id
            curr_lang = get_current_language()
            is_ru = (curr_lang == "ru")
            source_display_names = {
                "consensus": "Консенсус (ECMWF + ICON + MET Norway)" if is_ru else "Consensus (ECMWF + ICON + MET Norway)",
                "ecmwf": "ECMWF IFS (Европа)" if is_ru else "ECMWF IFS (Europe)",
                "icon": "DWD ICON (Германия)" if is_ru else "DWD ICON (Germany)",
                "met_norway": "MET Norway",
                "open_meteo": "Open-Meteo",
            }
            self.current_weather_data["source_name"] = source_display_names.get(source_id, source_id)
            if hasattr(self, "overview_view") and self.overview_view:
                self.overview_view.update_data(self.current_weather_data, self.temp_unit)
        if self.current_city:
            self.load_city(self.current_city, force_refresh=True)

    def open_detail(self, mode: str = "conditions", day_idx: int = 0):
        """Navigate to Level 2 Detail Sheet in specified mode and day."""
        if self.detail_sheet:
            self.detail_sheet.set_mode(mode)
            self.detail_sheet.select_day(day_idx)
        if self.nav_stack:
            self.nav_stack.set_visible_child_name("detail")
        if hasattr(self, "cities_strip") and self.cities_strip:
            self.cities_strip.set_visible(False)
        if hasattr(self, "cities_scroll") and self.cities_scroll:
            self.cities_scroll.set_visible(False)

    def open_overview(self):
        """Navigate back to Level 1 Overview screen."""
        if self.nav_stack:
            self.nav_stack.set_visible_child_name("overview")
        if hasattr(self, "cities_strip") and self.cities_strip:
            self.cities_strip.set_visible(True)
        if hasattr(self, "cities_scroll") and self.cities_scroll:
            self.cities_scroll.set_visible(True)
        trim_memory()

    def is_detail_open(self) -> bool:
        """Check if Level 2 Detail Sheet is currently active."""
        if self.nav_stack:
            return self.nav_stack.get_visible_child_name() == "detail"
        return False

    def is_overview_open(self) -> bool:
        """Check if Level 1 Overview screen is currently active."""
        if self.nav_stack:
            return self.nav_stack.get_visible_child_name() == "overview"
        return False

    def _on_window_active_changed(self, window, param_spec):
        """Pause or resume atmospheric physics based on active focus state to conserve CPU and battery."""
        is_active = self.is_active()
        self._sync_atmosphere_animation_state(is_active)

    def _on_window_visible_changed(self, window, param_spec):
        """Pause atmospheric physics when window is hidden or minimized."""
        is_visible = self.is_visible()
        self._sync_atmosphere_animation_state(is_visible and self.is_active())

    def _sync_atmosphere_animation_state(self, active: bool):
        if hasattr(self, "main_box") and self.main_box:
            if active:
                self.main_box.resume_animation()
            else:
                self.main_box.pause_animation()
        if hasattr(self, "atmosphere_box") and self.atmosphere_box:
            if active:
                self.atmosphere_box.resume_animation()
            else:
                self.atmosphere_box.pause_animation()
        if not active:
            trim_memory()

    def _on_close_request(self, window):
        """Cleanly shutdown fetch threadpool and animations on window close."""
        self._sync_atmosphere_animation_state(False)
        if hasattr(self, "_fetch_executor"):
            self._fetch_executor.shutdown(wait=False, cancel_futures=True)
        return False

    def _on_weather_provider_updated(self):
        """Handle background weather cache updates by refreshing current city if needed."""
        if self.current_city and (self.current_weather_data is None or self.stack.get_visible_child_name() == "loading"):
            self.load_city(self.current_city)

    def load_city(self, city_name: str, force_refresh: bool = False):
        if not city_name or not city_name.strip():
            self._show_empty_state()
            return

        self._stop_empty_icon_animation()
        self.current_city = city_name
        self._current_request_id += 1
        request_id = self._current_request_id
        self._refresh_cities_strip()

        # Show loading
        self.spinner.start()
        self.loading_label.set_label(t("weather_loading_city", city=city_name))
        self.stack.set_visible_child_name("loading")

        def _fetch_worker(req_id: int, target_city: str):
            try:
                if force_refresh and hasattr(self, "weather_provider") and self.weather_provider:
                    self.weather_provider.invalidate_city(target_city)
                results = self.weather_provider.search(target_city, limit=1, category_filter="Weather", force_refresh=force_refresh)
                data = results[0].preview_data if results else None
            except Exception as e:
                logger.error("Weather fetch failed for %s: %s", target_city, e)
                data = None

            GLib.idle_add(self._on_weather_fetched, data, target_city, req_id)

        self._fetch_executor.submit(_fetch_worker, request_id, city_name)

    def _on_weather_fetched(self, data: dict, city_name: str, request_id: int | None = None):
        # Ignore responses from stale requests to eliminate race conditions
        if request_id is not None and request_id != self._current_request_id:
            logger.debug(
                "Discarding stale weather result for %s (req %s != cur %s)",
                city_name,
                request_id,
                self._current_request_id,
            )
            return False

        if self.current_city and city_name != self.current_city:
            logger.debug(
                "Discarding mismatched city result: %s != current %s",
                city_name,
                self.current_city,
            )
            return False

        self.spinner.stop()
        if not data:
            self.loading_label.set_label(t("weather_load_failed", city=city_name))
            return False

        main_c = (self.config_manager.get("main_city", "") or "").strip().lower()
        target_name = data.get("city_name") or city_name
        data["is_main_city"] = (main_c == target_name.strip().lower())
        saved = list(self.config_manager.get("saved_cities", []))
        data["is_pinned"] = any(c.strip().lower() == target_name.strip().lower() for c in saved)
        curr_src = self.config_manager.get("forecast_source", "consensus")
        data["forecast_source"] = curr_src
        curr_lang = get_current_language()
        is_ru = (curr_lang == "ru")
        source_display_names = {
            "consensus": "Консенсус (ECMWF + ICON + MET Norway)" if is_ru else "Consensus (ECMWF + ICON + MET Norway)",
            "ecmwf": "ECMWF IFS (Европа)" if is_ru else "ECMWF IFS (Europe)",
            "icon": "DWD ICON (Германия)" if is_ru else "DWD ICON (Germany)",
            "met_norway": "MET Norway",
            "open_meteo": "Open-Meteo",
        }
        data["source_name"] = source_display_names.get(curr_src, curr_src)

        self.current_weather_data = data
        self._render_weather_data(data)
        self.stack.set_visible_child_name("weather")

        self._update_pin_button()
        self._update_home_btn()
        self._refresh_cities_strip()

    def _render_weather_data(self, data: dict):
        # Update main window atmospheric canvas and particle physics
        self.main_box.set_weather_atmosphere(data)

        # Update window theme CSS classes for header bar glass adaptation
        bg = data.get('bg_class', 'weather-bg-clear-day')
        cond = bg.replace('weather-bg-', '')
        is_night = (data.get("time_of_day") == "night" or "night" in bg or data.get("is_day") == 0)
        is_rain = (
            "rain" in bg or data.get("grad_type") == "rain" or
            int(data.get("weather_code") or 0) in (61, 63, 65, 66, 67, 80, 81, 82) or
            ("дождь" in str(data.get("condition_text", "")).lower() and "изморось" not in str(data.get("condition_text", "")).lower()) or
            "ливень" in str(data.get("condition_text", "")).lower()
        )
        if is_rain and is_night and cond not in ("rain-night", "rain_night"):
            cond = "rain-night"
        canvas_classes = [
            "weather-canvas-active", "weather-canvas-empty", "weather-canvas-clear-day", "weather-canvas-clear-dusk",
            "weather-canvas-clear-night", "weather-canvas-clouds-day", "weather-canvas-clouds-night",
            "weather-canvas-rain-day", "weather-canvas-rain-night", "weather-canvas-drizzle-day",
            "weather-canvas-drizzle-night", "weather-canvas-storm-day", "weather-canvas-storm-night",
            "weather-canvas-snow-day", "weather-canvas-snow-night", "weather-canvas-fog-day",
            "weather-canvas-fog-night", "weather-night-mode", "weather-dusk-mode"
        ]
        for c in canvas_classes:
            self.remove_css_class(c)
        self.add_css_class("weather-canvas-active")
        self.add_css_class(f"weather-canvas-{cond}")
        if data.get("time_of_day") == "night" or "night" in bg or data.get("is_day") == 0:
            self.add_css_class("weather-night-mode")
        if data.get("time_of_day") in ("dusk", "dawn") or "dusk" in bg or "dawn" in bg:
            self.add_css_class("weather-dusk-mode")

        if hasattr(self, "source_popover") and self.source_popover:
            for c in canvas_classes:
                self.source_popover.remove_css_class(c)
            self.source_popover.add_css_class(bg)

        if hasattr(self, "lang_popover") and self.lang_popover:
            for c in canvas_classes:
                self.lang_popover.remove_css_class(c)
            self.lang_popover.add_css_class(bg)

        # Clear previous weather container
        while child := self.weather_container.get_first_child():
            if hasattr(child, "_stop_animation"):
                child._stop_animation()
            self.weather_container.remove(child)

        # Root box with dynamic atmospheric particle canvas
        self.atmosphere_box = WeatherAtmosphereBox(data=data, config_manager=self.config_manager, corner_radius=0.0)
        self.atmosphere_box.set_vexpand(True)
        self.atmosphere_box.set_hexpand(True)

        # Two-level navigation stack with sliding animation (280ms duration)
        self.nav_stack = Gtk.Stack()
        self.nav_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.nav_stack.set_transition_duration(280)
        self.nav_stack.set_interpolate_size(True)
        self.nav_stack.set_vexpand(True)
        self.nav_stack.set_hexpand(True)

        # Level 1: Overview screen
        self.overview_view = WeatherOverviewView(
            data=data,
            temp_unit=self.temp_unit,
            on_open_mode_callback=lambda m: self.open_detail(mode=m, day_idx=0),
            on_open_day_callback=lambda d_idx: self.open_detail(mode="conditions", day_idx=d_idx),
            on_toggle_home_callback=self._on_home_toggle,
            on_toggle_pin_callback=self._on_pin_toggle,
        )

        # Level 2: Detailed analytical sheet
        self.detail_sheet = WeatherDetailSheet(
            data=data,
            on_back_callback=self.open_overview,
            initial_day_idx=0,
            initial_mode="conditions",
            temp_unit=self.temp_unit,
        )
        if hasattr(self.detail_sheet, "btn_back"):
            self.detail_sheet.btn_back.set_visible(True)

        self.nav_stack.add_named(self.overview_view, "overview")
        self.nav_stack.add_named(self.detail_sheet, "detail")
        self.nav_stack.set_visible_child_name("overview")
        if hasattr(self, "cities_strip") and self.cities_strip:
            self.cities_strip.set_visible(True)
        if hasattr(self, "cities_scroll") and self.cities_scroll:
            self.cities_scroll.set_visible(True)

        self.atmosphere_box.append(self.nav_stack)
        self.weather_container.append(self.atmosphere_box)
        if hasattr(self.atmosphere_box, "_stop_animation") and self.atmosphere_box._has_capsule_atmosphere():
            self.atmosphere_box._stop_animation()

    def destroy(self):
        """Cleanly shutdown fetch threadpool and animations when window is destroyed."""
        self._stop_empty_icon_animation()
        if hasattr(self, "lang_popover") and hasattr(self.lang_popover, "unparent"):
            self.lang_popover.unparent()
        if hasattr(self, "source_popover") and hasattr(self.source_popover, "unparent"):
            self.source_popover.unparent()
        if hasattr(self, "main_box") and hasattr(self.main_box, "_stop_animation"):
            self.main_box._stop_animation()
        if hasattr(self, "atmosphere_box") and hasattr(self.atmosphere_box, "_stop_animation"):
            self.atmosphere_box._stop_animation()
        if hasattr(self, "_fetch_executor"):
            self._fetch_executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
