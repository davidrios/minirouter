from PIL import Image, ImageDraw
from statemachine import State, StateMachine


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
