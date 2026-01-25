import json
import logging
import logging.config
import os
import threading
from collections import namedtuple
from datetime import datetime
from io import BytesIO
from pathlib import Path
from socket import gethostbyname
from time import sleep, time

import evdev
import requests
import requests.packages.urllib3.util.connection as urllib3_cn
import sdbus
import zmq
from PIL import Image, ImageDraw, ImageFont
from sdbus_block.networkmanager import (
    AccessPoint,
    DeviceState,
    DeviceType,
    IPv4Config,
    NetworkDeviceGeneric,
    NetworkDeviceWireless,
    NetworkManager,
)
from statemachine import State, StateMachine

from images import WIFI_SIGNALS

urllib3_cn.HAS_IPV6 = False

log = logging.getLogger("minirouter")


statuses = {
    "interfaces": None,
    "dns": None,
    "wan_ip": None,
    "time": None,
}


def get_interfaces(network_manager, interfaces=None):
    devices = {"devices": {}, "wifi": None}

    for path, device in sorted(
        [(path, NetworkDeviceGeneric(path)) for path in network_manager.devices], key=lambda item: item[1].interface
    ):
        if interfaces and device.interface not in interfaces:
            continue

        device_type = DeviceType(device.device_type)
        state = DeviceState(device.state)

        info = {
            "interface": device.interface,
            "state": state,
            "ip4": "-",
            "type": device_type,
            "ssid": "-",
        }

        if state is DeviceState.ACTIVATED:
            ip = IPv4Config(device.ip4_config)
            try:
                if ip.address_data:
                    ipa = ip.address_data[0]
                    info["ip4"] = f"{ipa['address'][1]}/{ipa['prefix'][1]}"

            except Exception as ex:
                log.info("error getting ip: %s", str(ex))
                info["ip4"] = "E"

            try:
                if device_type is DeviceType.WIFI:
                    devices["wifi"] = device.interface

                    wlan = NetworkDeviceWireless(path)
                    if wlan.active_access_point:
                        ap = AccessPoint(wlan.active_access_point)
                        info["ssid"] = ap.ssid.decode()
                        info["strength"] = ap.strength
                    else:
                        info["ssid"] = None
                        info["strength"] = None
            except Exception as ex:
                log.info("error getting ssid: %s", str(ex))
                info["ssid"] = "* error *"

        devices["devices"][device.interface] = info

    return devices


def run_interfaces_loop(interfaces, refresh):
    sdbus.set_default_bus(sdbus.sd_bus_open_system())
    network_manager = NetworkManager()

    while True:
        try:
            res = get_interfaces(network_manager, interfaces=interfaces)
            statuses["interfaces"] = res
        except Exception:
            log.exception("error in ips loop")
        sleep(refresh)


def check_dns_working(hostname):
    try:
        return gethostbyname(hostname)
    except Exception as ex:
        log.info("error checking dns: %s", str(ex))
        return None


def run_dns_loop(hostname, refresh):
    while True:
        try:
            is_dns_working = check_dns_working(hostname)
            statuses["dns"] = bool(is_dns_working)
        except Exception:
            log.exception("error in dns loop")
            statuses["dns"] = False
        sleep(refresh)


def get_wan_ip():
    is_ip = False
    if statuses["dns"]:
        res = requests.get("https://share.us.davidrios.dev/myip")
        is_ip = True
    else:
        res = requests.get("http://1.1.1.1")

    if res.status_code != 200:
        return "-error-"

    return res.content.decode() if is_ip else "online"


def run_wan_ip_loop(refresh):
    while True:
        try:
            wan_ip = get_wan_ip()
            statuses["wan_ip"] = wan_ip
        except Exception:
            log.exception("error in wan ip loop")
            statuses["wan_ip"] = "-error-"
        sleep(refresh)


class StatusUi(StateMachine):
    showing_page1 = State(initial=True)
    showing_page2 = State()

    cycle = showing_page1.to(showing_page2) | showing_page2.to(showing_page1)

    def __init__(self, display_size, font):
        self.display_size = display_size
        self.font = font
        super().__init__()

    def after_cycle(self):
        log.debug("cycled status")

    def press_a(self):
        self.cycle()

    def press_b(self):
        pass

    def draw(self):
        image = Image.new("1", self.display_size)

        draw = ImageDraw.Draw(image)

        # clear display
        draw.rectangle((0, 0, *self.display_size), outline=0, fill=0, width=0)

        if self.current_state.id == "showing_page1":
            signal = self.draw_wifi(draw)
            signal_image = WIFI_SIGNALS[signal]
            image.paste(signal_image, (108, 8))

            self.draw_dns(draw)
            self.draw_wan(draw)

            self.draw_time(draw)
        elif self.current_state.id == "showing_page2":
            draw.text(
                (0, -2),
                "page 2",
                font=self.font,
                fill=1,
            )

        return image

    def draw_wifi(self, draw):
        text = "wifi: "
        signal = None

        interfaces = statuses["interfaces"]
        if interfaces is None:
            text += "-"
        else:
            wifi = interfaces["devices"].get(interfaces["wifi"])

            if wifi is None:
                text += "-"
            else:
                text += wifi["ssid"]
                if wifi["strength"] <= 0:
                    signal = 0
                elif wifi["strength"] >= 100:
                    signal = 4
                else:
                    signal = int(wifi["strength"] / 25) + 1

        draw.text(
            (0, -2),
            text,
            font=self.font,
            fill=1,
        )

        return signal

    def draw_dns(self, draw):
        status = "online" if statuses["dns"] else "offline"

        draw.text(
            (0, 6),
            f"dns: {status}",
            font=self.font,
            fill=1,
        )

    def draw_wan(self, draw):
        status = statuses["wan_ip"] or "offline"

        draw.text(
            (0, 14),
            f"wan: {status}",
            font=self.font,
            fill=1,
        )

    def draw_time(self, draw):
        text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        draw.text(
            (0, 22),
            text,
            font=self.font,
            fill=1,
        )


class MenuUi(StateMachine):
    selected_opt1 = State(initial=True)
    selected_opt2 = State()
    selected_go_back = State()

    cycle_options = (
        selected_opt1.to(selected_opt2) | selected_opt2.to(selected_go_back) | selected_go_back.to(selected_opt1)
    )

    reset_options = (
        selected_opt1.to(selected_opt1) | selected_opt2.to(selected_opt1) | selected_go_back.to(selected_opt1)
    )

    def __init__(self, display_size, font):
        self.display_size = display_size
        self.font = font
        super().__init__()

    def press_a(self):
        if self.current_state.id == "selected_go_back":
            self.reset_options()
            return True

    def press_b(self):
        self.cycle_options()

    def draw_options(self, draw):
        for idx, opt in enumerate(("option 1", "option 2", "voltar")):
            draw.text(
                (0, -2 + (idx * 7)),
                f"  {opt}",
                font=self.font,
                fill=1,
            )

    def draw(self):
        image = Image.new("1", self.display_size)

        draw = ImageDraw.Draw(image)

        # clear display
        draw.rectangle((0, 0, *self.display_size), outline=0, fill=0, width=0)

        self.draw_options(draw)

        cursor_pos = -2

        if self.current_state.id == "selected_opt2":
            cursor_pos = -2 + 7
        elif self.current_state.id == "selected_go_back":
            cursor_pos = -2 + 7 + 7

        draw.text(
            (0, cursor_pos),
            ">",
            font=self.font,
            fill=1,
        )

        return image


Size = namedtuple("Size", "width height")


class Ui(StateMachine):
    initializing = State(initial=True)
    initialized = State()
    on_status = State()
    on_menu = State()

    initialize = initializing.to(initialized, cond="do_initialization")
    start_status = initialized.to(on_status)
    show_menu = on_status.to(on_menu)
    back_to_status = on_menu.to(on_status)

    def __init__(self, config):
        self.config = config
        self.display_size = Size(*self.config["display"]["size"])
        self.font = ImageFont.truetype("ProFontOTB.otb", config["display"]["font_size"])
        self.status_ui = StatusUi(self.display_size, self.font)
        self.menu_ui = MenuUi(self.display_size, self.font)
        self.last_draw = 0
        self.last_screen_refresh = 0
        self.last_data = None
        self.force_refresh_count = 0

        self.display_backend = None
        self.screen_refresh_rate = 5

        super().__init__()

    def do_initialization(self):
        log.debug("doing initialization")

        def listen_kbd(kbd):
            for event in kbd.read_loop():
                if event.value != 0:
                    continue

                try:
                    if event.code == evdev.ecodes.KEY_A:
                        self.press_a()
                    elif event.code == evdev.ecodes.KEY_S:
                        self.press_b()
                except Exception:
                    log.exception("error processing key press")

        kbds = [
            d
            for d in [evdev.InputDevice(path) for path in evdev.list_devices()]
            if evdev.ecodes.KEY_A in d.capabilities().get(evdev.events.EV_KEY, [])
        ]

        for kbd in kbds:
            threading.Thread(
                target=listen_kbd,
                args=(kbd,),
                daemon=True,
            ).start()

        if self.config["output"] == "web":
            from web_output import get_server

            def serve_web():
                get_server(lambda: self.last_data).serve_forever()

            threading.Thread(
                target=serve_web,
                daemon=True,
            ).start()

        buttons_server = self.config.get("buttons_server")
        if buttons_server:

            def buttons_server_loop():
                context = zmq.Context()
                subscriber = context.socket(zmq.SUB)

                subscriber.connect(buttons_server["address"])
                subscriber.setsockopt_string(zmq.SUBSCRIBE, "")

                log.info("Waiting for buttons server events...")

                try:
                    while True:
                        button = int(subscriber.recv_string())
                        button_num = abs(button)
                        is_pressed = button_num * buttons_server["direction"] == button

                        if is_pressed:
                            if button_num == buttons_server["button_a"]:
                                self.press_a()
                            elif button_num == buttons_server["button_b"]:
                                self.press_b()
                finally:
                    subscriber.close()
                    context.term()

            threading.Thread(
                target=buttons_server_loop,
                daemon=True,
            ).start()

        return True

    def after_initialize(self):
        self.start_status()

    def press_a(self):
        if self.current_state.id == "on_status":
            self.status_ui.press_a()
        elif self.current_state.id == "on_menu":
            if self.menu_ui.press_a():
                self.back_to_status()

        self.force_refresh()

    def press_b(self):
        if self.current_state.id == "on_status":
            self.show_menu()
        elif self.current_state.id == "on_menu":
            self.menu_ui.press_b()

        self.force_refresh()

    def force_refresh(self):
        self.force_refresh_count = 0
        self.last_screen_refresh = 0
        self.last_draw = 0

    def draw(self):
        if not ((time() - self.last_draw) < self.config["refresh"]):
            self.last_draw = time()
            image = None
            if self.current_state.id == "on_status":
                image = self.status_ui.draw()
            elif self.current_state.id == "on_menu":
                image = self.menu_ui.draw()
            else:
                image = self.draw_initializing()

            if self.config["output"] == "web":
                wrapper_size = [i + 3 for i in self.display_size]
                wrapper = Image.new("1", wrapper_size)
                draw = ImageDraw.Draw(wrapper)
                draw.rectangle((0, 0, *[i - 2 for i in wrapper_size]), outline=1, fill=1, width=1)
                wrapper.paste(image, (1, 1))
                scale = self.config.get("output_scale", 1)
                wrapper = wrapper.resize([i * scale for i in wrapper.size])
                image = wrapper

            data = BytesIO()
            image.save(data, "bmp")
            self.last_data = data

    def draw_initializing(self):
        image = Image.new("1", self.display_size)

        draw = ImageDraw.Draw(image)

        # clear display
        draw.rectangle((0, 0, *self.display_size), outline=0, fill=0, width=0)

        draw.text(
            (0, -2),
            "Initializing...",
            font=self.font,
            fill=1,
        )

        return image


def main():
    config = {}

    config_file = Path(os.environ.get("CONFIG_FILE", "config.json"))
    if config_file.is_file():
        with config_file.open() as fp:
            config.update(json.load(fp))

    logging.config.dictConfig(config.get("logging", {"version": 1}))

    log.info("starting")

    config["refresh"] = config.get("refresh", 1)

    refresh = config["refresh"]

    threading.Thread(
        target=run_interfaces_loop,
        args=(config.get("interfaces"), refresh),
        daemon=True,
    ).start()

    threading.Thread(
        target=run_dns_loop,
        args=(config.get("check_dns", "google.com"), refresh),
        daemon=True,
    ).start()

    threading.Thread(
        target=run_wan_ip_loop,
        args=(refresh,),
        daemon=True,
    ).start()

    ui = Ui(config)
    ui.initialize()

    last_debug = 0

    while True:
        if time() - last_debug > refresh:
            log.debug("statuses: %s", statuses)
            last_debug = time()

        ui.draw()
        sleep(0.01)


if __name__ == "__main__":
    main()
