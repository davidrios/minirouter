import logging
import threading
from collections import namedtuple
from io import BytesIO
from pathlib import Path
from time import time

import evdev
import zmq
from PIL import Image, ImageDraw, ImageFont
from statemachine import State, StateMachine

from .menu import MenuUi
from .status import StatusUi

log = logging.getLogger(__name__)

FONT_FILE = Path(__file__).parent.parent / "data" / "ProFontOTB.otb"

Size = namedtuple("Size", "width height")


class MainUi(StateMachine):
    initializing = State(initial=True)
    initialized = State()
    on_status = State()
    on_menu = State()

    initialize = initializing.to(initialized, cond="do_initialization")
    start_status = initialized.to(on_status)
    show_menu = on_status.to(on_menu)
    back_to_status = on_menu.to(on_status)

    def __init__(self, config, statuses):
        self.config = config
        self.statuses = statuses
        self.display_size = Size(*self.config["display"]["size"])
        self.font = ImageFont.truetype(FONT_FILE, config["display"]["font_size"])
        self.status_ui = StatusUi(self.display_size, self.font, self.statuses)
        self.menu_ui = MenuUi(self.display_size, self.font)
        self.last_draw = 0
        self.last_display_refresh = 0
        self.last_data = None
        self.last_image = None

        self.display_backend = None
        self.display_refresh_rate = 5

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
            from ..web_output import get_server

            def serve_web():
                get_server(lambda: self.last_data).serve_forever()

            threading.Thread(
                target=serve_web,
                daemon=True,
            ).start()
        elif self.config["output"] == "display":
            ctx = zmq.Context()
            sock = ctx.socket(zmq.REQ)
            sock.connect(self.config["display_server"])
            self.display_server = sock

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
        self.last_display_refresh = 0
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
                scale = self.config.get("output_scale", 1)
                image = image.resize([i * scale for i in image.size])

                data = BytesIO()
                image.save(data, "bmp")
                self.last_data = data
            elif self.config["output"] == "display":
                self.last_data = bytearray(image.get_flattened_data())

            self.last_image = image

        if not ((time() - self.last_display_refresh) < self.display_refresh_rate):
            self.last_display_refresh = time()

            if self.config["output"] == "display" and self.last_image is not None:
                self.display_server.send(self.last_data)
                if self.display_server.recv() != b"a":
                    log.error("Received unexpected response from display server")

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

    def cleanup(self):
        if self.config["output"] == "display":
            self.display_server.send(b"\x00" * self.display_size[0] * self.display_size[1])
            self.display_server.recv()
