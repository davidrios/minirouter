import logging
from datetime import datetime

from PIL import Image, ImageDraw
from statemachine import State, StateMachine

from .images import WIFI_SIGNALS

log = logging.getLogger(__name__)


class StatusUi(StateMachine):
    showing_page1 = State(initial=True)
    showing_page2 = State()

    cycle = showing_page1.to(showing_page2) | showing_page2.to(showing_page1)

    def __init__(self, display_size, font, statuses):
        self.display_size = display_size
        self.font = font
        self.statuses = statuses
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

        interfaces = self.statuses["interfaces"]
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
        status = "online" if self.statuses["dns"] else "offline"

        draw.text(
            (0, 6),
            f"dns: {status}",
            font=self.font,
            fill=1,
        )

    def draw_wan(self, draw):
        status = self.statuses["wan_ip"] or "offline"

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
