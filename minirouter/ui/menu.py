import logging
import threading
from itertools import islice
from subprocess import check_call
from time import time

import sdbus
from PIL import Image, ImageDraw
from sdbus_block.networkmanager import (
    ActiveConnection,
    DeviceType,
    NetworkConnectionSettings,
    NetworkDeviceWireless,
    NetworkManager,
    NetworkManagerSettings,
)

log = logging.getLogger(__name__)


def batched(iterable, n, *, strict=False):
    # batched('ABCDEFG', 3) → ABC DEF G
    if n < 1:
        raise ValueError("n must be at least one")
    iterator = iter(iterable)
    while batch := tuple(islice(iterator, n)):
        if strict and len(batch) != n:
            raise ValueError("batched(): incomplete batch")
        yield batch


class BaseMenu:
    has_go_back = False
    max_lines = 4
    options = []
    submenus = {}

    def __init__(self, display_size, font):
        self.display_size = display_size
        self.font = font
        self.highlighted = 0
        self.in_submenu = None
        self.submenus = {idx: c(display_size, font) for idx, c in self.submenus.items()}

    def _get_options(self):
        options = self.options[:]
        if self.has_go_back:
            options.append("voltar")
        return options

    def _get_options_pages(self):
        return list(batched(self._get_options(), self.max_lines))

    def do_action(self, option):
        log.debug("%s: selected option %s", self.__class__.__name__, option)

    def reset(self):
        self.highlighted = 0
        if self.in_submenu is not None:
            self.in_submenu.reset()
            self.in_submenu = None

    def press_a(self):
        if self.has_go_back and self.highlighted == len(self._get_options()) - 1:
            self.highlighted = 0
            return True

        if self.in_submenu is not None:
            if self.in_submenu.press_a():
                self.in_submenu = None
            return

        if self.in_submenu is None:
            self.in_submenu = self.submenus.get(self.highlighted)
            if self.in_submenu is not None:
                return

        return self.do_action(self.highlighted)

    def press_b(self):
        if self.in_submenu is not None:
            return self.in_submenu.press_b()

        new_highlighted = self.highlighted + 1
        if new_highlighted > len(self._get_options()) - 1:
            new_highlighted = 0
        self.highlighted = new_highlighted

    def draw_options(self, draw):
        pages = self._get_options_pages()
        try:
            page = pages[int(self.highlighted / self.max_lines)]
        except IndexError:
            page = pages[0]
            self.highlighted = 0

        for idx, opt in enumerate(page):
            draw.text(
                (0, -2 + (idx * 8)),
                f"  {opt}",
                font=self.font,
                fill=1,
            )

    def draw(self):
        if self.in_submenu is not None:
            return self.in_submenu.draw()

        image = Image.new("1", self.display_size)

        draw = ImageDraw.Draw(image)

        # clear display
        draw.rectangle((0, 0, *self.display_size), outline=0, fill=0, width=0)

        self.draw_options(draw)

        cursor_pos = self.highlighted % self.max_lines

        draw.text(
            (0, -2 + (cursor_pos * 8)),
            ">",
            font=self.font,
            fill=1,
        )

        return image


class AnotherMenu(BaseMenu):
    has_go_back = True
    options = ["hello"]


class BigMenu(BaseMenu):
    has_go_back = True
    options = [f"option {i}" for i in range(6)]
    submenus = {0: AnotherMenu}


class WifiConnectMenu(BaseMenu):
    has_go_back = True

    def __init__(self, display_size, font):
        super().__init__(display_size, font)
        self.is_updating = False
        self.is_updated = False
        self.wifis = []
        self.wifis_paths = []
        self.message_drawer = MessageDrawer(display_size, font)

    @property
    def options(self):
        options = self.wifis[:]
        if not self.is_updating:
            options.append("-atualizar-")
        return options

    def start_updating(self):
        if self.is_updating:
            return

        self.message_drawer.set_message(["carregando..."])
        self.is_updating = True
        threading.Thread(
            target=self.update_wifis,
        ).start()

    def update_wifis(self):
        log.debug("loading wifi list")
        self.wifis = []

        sdbus.set_default_bus(sdbus.sd_bus_open_system())
        settings_manager = NetworkManagerSettings()

        wifis = []
        wifis_paths = []
        for conn_path in settings_manager.list_connections():
            conn_settings = NetworkConnectionSettings(conn_path)
            settings = conn_settings.get_settings()

            conn_info = settings.get("connection", {})
            if conn_info.get("type")[1] != "802-11-wireless":
                continue

            wifis.append(conn_info.get("id")[1])
            wifis_paths.append(conn_path)

        self.wifis = wifis
        self.wifis_paths = wifis_paths
        self.is_updated = True
        self.is_updating = False
        self.message_drawer.clear_message()

    def _connect_wifi(self, path):
        self.message_drawer.set_message(["conectando..."])
        try:
            sdbus.set_default_bus(sdbus.sd_bus_open_system())
            network_manager = NetworkManager()
            wifi = [
                wifi
                for path in network_manager.devices
                if DeviceType((wifi := NetworkDeviceWireless(path)).device_type) is DeviceType.WIFI
            ][0]
        except IndexError:
            self.message_drawer.set_message(["erro:", "wifi desabilitado"], 5)
            return

        if len(wifi.active_connection) > 1:
            ac = ActiveConnection(wifi.active_connection)
            if path == ac.connection:
                self.message_drawer.set_message(["já connectado!"], 5)
                return

        try:
            connection_id = NetworkConnectionSettings(path).get_settings()["connection"]["id"][1]
            check_call(["/opt/minirouter/bin/wificonnect", connection_id])
            self.message_drawer.set_message(["conectado!"], 3)
        except Exception:
            log.exception("failed to connect")
            self.message_drawer.set_message(["erro!"], 3)

    def connect_wifi(self, path):
        threading.Thread(
            target=self._connect_wifi,
            args=(path,),
        ).start()

    def press_a(self):
        if self.message_drawer.has_message:
            return
        return super().press_a()

    def press_b(self):
        if self.message_drawer.has_message:
            return
        return super().press_b()

    def do_action(self, option):
        if option == len(self.wifis):
            if not self.is_updating:
                self.start_updating()
        else:
            wifi = self.wifis[option]
            if wifi != "-error-":
                log.debug("connect to wifi %s", wifi)
                self.connect_wifi(self.wifis_paths[option])

    def draw(self):
        if not self.is_updated and not self.is_updating:
            self.start_updating()

        drew_message = self.message_drawer.draw_message()

        if drew_message is not None:
            return drew_message
        else:
            return super().draw()


class MainMenu(BaseMenu):
    has_go_back = True
    options = ["connectar wifi", "reiniciar"]
    submenus = {0: WifiConnectMenu}

    def do_action(self, option):
        if option == self.options.index("reiniciar"):
            check_call(["sudo", "/sbin/reboot"])


class MessageDrawer:
    def __init__(self, display_size, font):
        self.display_size = display_size
        self.font = font
        self.lines = []
        self.timeout = 5
        self.image = None
        self.has_message = False
        self.last_draw = 0

    def set_message(self, lines, timeout=60):
        self.lines = lines
        self.timeout = timeout
        self.image = None
        self.has_message = True
        self.last_draw = time()

    def clear_message(self):
        self.has_message = False

    def draw_message(self):
        if not self.has_message:
            return

        if time() - self.last_draw >= self.timeout:
            self.has_message = False
            return

        if self.image is None:
            image = Image.new("1", self.display_size)

            draw = ImageDraw.Draw(image)

            # clear display
            draw.rectangle((0, 0, *self.display_size), outline=0, fill=0, width=0)

            for idx, line in enumerate(self.lines):
                draw.text(
                    (0, -2 + (idx * 8)),
                    line,
                    font=self.font,
                    fill=1,
                )

            self.image = image

        return self.image
