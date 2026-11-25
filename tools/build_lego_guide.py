"""Generate the illustrated NXT keyboard presser assembly booklet."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from math import atan2, cos, sin
from pathlib import Path

from reportlab.lib.colors import HexColor  # ty: ignore[import-not-found]
from reportlab.pdfgen.canvas import Canvas  # ty: ignore[import-not-found]

PAGE = (612, 792)
INK = "#17283B"
MUTED = "#506880"
BLUE = "#2067A8"
PALE = "#EAF5FC"
PAPER = "#FFFFFF"
LINE = "#CADDEB"
GRAY = "#B8C6D1"
SHADE = "#8298AA"
ORANGE = "#F6A342"
YELLOW = "#FFE099"
TEAL = "#4EB8AE"
DARK = "#354A5D"
A_COLOR = "#1561A3"
B_COLOR = "#08786C"


@dataclass(frozen=True)
class Part:
    key: str
    label: str
    description: str
    count: int


PARTS = (
    Part("frame", "5 × 7 Technic frame", "Two upright cheeks per module", 4),
    Part("rail", "15L thick liftarm", "Four feet and four motor supports", 8),
    Part("lever", "9L thick liftarm", "One moving lever per module", 2),
    Part("crank", "2L axle-hole crank", "Axle hole and adjacent round hole", 2),
    Part("link", "4L liftarm", "Try 3L or 5L if your mount needs it", 2),
    Part("pin", "2L friction pin", "Fixed joints, including two for each stop", 24),
    Part("free", "Low-friction pin", "Two rotating linkage joints per module", 4),
    Part("axle", "8L axle", "Three per module for ties and pivot", 6),
    Part("shaft", "3L axle", "One crank shaft per motor, if needed", 2),
    Part("bush", "Full bush", "Axle retainers and pivot spacers", 18),
    Part("angle", "Right-angle connector", "Two mount adapters and one stop per module", 6),
    Part("motor", "NXT servo motor", "One for Option and one for Enter", 2),
    Part("band", "Light elastic band", "Returns each lever toward its rest position", 2),
    Part("pad", "Soft rubber or foam pad", "One for each key contact", 2),
)

Point = tuple[float, float]


def fill(pdf: Canvas, color: str) -> None:
    pdf.setFillColor(HexColor(color))


def stroke(pdf: Canvas, color: str, weight: float = 1) -> None:
    pdf.setStrokeColor(HexColor(color))
    pdf.setLineWidth(weight)


def text(pdf: Canvas, x: float, y: float, value: str, size: float = 12,
         color: str = INK, bold: bool = False) -> None:
    fill(pdf, color)
    pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    pdf.drawString(x, y, value)


def wrap(pdf: Canvas, x: float, y: float, value: str, width: float, size: float = 12,
         color: str = INK) -> None:
    line: list[str] = []
    for word in value.split():
        candidate = " ".join([*line, word])
        if line and pdf.stringWidth(candidate, "Helvetica", size) > width:
            text(pdf, x, y, " ".join(line), size, color)
            y -= size + 5
            line.clear()
        line.append(word)
    if line:
        text(pdf, x, y, " ".join(line), size, color)


def box(pdf: Canvas, x: float, y: float, w: float, h: float, color: str,
        outline: str | None = None, radius: float = 8) -> None:
    fill(pdf, color)
    if outline:
        stroke(pdf, outline)
    pdf.roundRect(x, y, w, h, radius, fill=1, stroke=int(outline is not None))


def dot(pdf: Canvas, x: float, y: float, radius: float, color: str, outline: str | None = None) -> None:
    fill(pdf, color)
    if outline:
        stroke(pdf, outline)
    pdf.circle(x, y, radius, fill=1, stroke=int(outline is not None))


def line(pdf: Canvas, a: Point, b: Point, color: str = DARK, weight: float = 1) -> None:
    stroke(pdf, color, weight)
    pdf.line(*a, *b)


def arrow(pdf: Canvas, a: Point, b: Point, color: str = BLUE) -> None:
    line(pdf, a, b, color, 2.5)
    angle = atan2(b[1] - a[1], b[0] - a[0])
    for delta in (-0.48, 0.48):
        point = (b[0] - 9 * cos(angle + delta), b[1] - 9 * sin(angle + delta))
        line(pdf, b, point, color, 2.5)


def beam(pdf: Canvas, start: Point, end: Point, holes: int, color: str = GRAY, width: float = 18) -> None:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = (dx * dx + dy * dy) ** 0.5
    radius = width / 2
    pdf.saveState()
    pdf.translate(*start)
    pdf.rotate(atan2(dy, dx) * 180 / 3.141592653589793)
    box(pdf, -radius + 3, -radius - 4, length + width, width, SHADE, DARK, radius)
    box(pdf, -radius, -radius, length + width, width, color, DARK, radius)
    for index in range(holes):
        x = index * length / (holes - 1)
        dot(pdf, x, 0, width * 0.24, "#F7FBFF", DARK)
        line(pdf, (x - width * 0.13, 1.7), (x + width * 0.10, 1.7), SHADE, 0.5)
    pdf.restoreState()


def frame(pdf: Canvas, x: float, y: float, color: str = GRAY) -> None:
    box(pdf, x - 6, y - 6, 133, 96, SHADE, DARK, 9)
    box(pdf, x - 9, y - 2, 133, 96, color, DARK, 9)
    box(pdf, x + 9, y + 14, 97, 61, PALE, DARK, 5)
    for pos in (0, 19, 38, 57, 76, 95, 114):
        dot(pdf, x + pos, y + 85, 4, "#F7FBFF", DARK)
        dot(pdf, x + pos, y + 5, 4, "#F7FBFF", DARK)
    for pos in (25, 45, 65):
        dot(pdf, x, y + pos, 4, "#F7FBFF", DARK)
        dot(pdf, x + 114, y + pos, 4, "#F7FBFF", DARK)


def servo(pdf: Canvas, x: float, y: float, color: str = GRAY) -> None:
    box(pdf, x + 5, y - 5, 142, 52, SHADE, DARK, 17)
    box(pdf, x, y, 142, 52, color, DARK, 17)
    box(pdf, x + 3, y + 12, 24, 27, "#E5EDF3", DARK, 4)
    for dx in (15, 39, 60):
        dot(pdf, x + dx, y + 25, 4, PAPER, DARK)
    dot(pdf, x + 114, y + 24, 24, "#D9813C", DARK)
    dot(pdf, x + 114, y + 24, 16, ORANGE, DARK)
    axle_hole(pdf, x + 114, y + 24)


def axle_hole(pdf: Canvas, x: float, y: float) -> None:
    line(pdf, (x - 4, y), (x + 4, y), DARK, 2.7)
    line(pdf, (x, y - 4), (x, y + 4), DARK, 2.7)


def pin(pdf: Canvas, start: Point, end: Point, color: str) -> None:
    line(pdf, start, end, DARK, 8)
    line(pdf, start, end, color, 5)
    dot(pdf, *start, 4, color, DARK)
    dot(pdf, *end, 4, color, DARK)


def piece(pdf: Canvas, key: str) -> None:
    if key == "frame":
        pdf.scale(0.55, 0.55)
        frame(pdf, 3, -39, TEAL)
    elif key == "motor":
        pdf.scale(0.53, 0.53)
        servo(pdf, 0, -23)
    elif key in ("rail", "lever", "crank", "link"):
        holes, length, color = {
            "rail": (15, 70, GRAY), "lever": (9, 65, ORANGE),
            "crank": (2, 26, ORANGE), "link": (4, 47, TEAL),
        }[key]
        beam(pdf, (5, 0), (5 + length, 0), holes, color, 8 if key == "rail" else 12)
        if key == "crank":
            axle_hole(pdf, 5, 0)
    elif key in ("pin", "free"):
        pin(pdf, (12, -5), (42, 7), DARK if key == "pin" else BLUE)
    elif key in ("axle", "shaft"):
        length = 55 if key == "axle" else 29
        pin(pdf, (8, -3), (8 + length, 6), SHADE if key == "axle" else "#A463AC")
    elif key == "bush":
        dot(pdf, 25, 0, 10, YELLOW, DARK)
        axle_hole(pdf, 25, 0)
    elif key == "angle":
        beam(pdf, (12, 0), (32, 0), 2, GRAY, 11)
        beam(pdf, (32, 0), (32, 17), 2, GRAY, 11)
    elif key == "band":
        stroke(pdf, "#6B53AD", 3)
        pdf.ellipse(9, -9, 63, 9, fill=0)
    elif key == "pad":
        box(pdf, 12, -7, 43, 13, DARK, None, 3)


def icon(pdf: Canvas, key: str, x: float, y: float, scale: float = 1) -> None:
    pdf.saveState()
    pdf.translate(x, y)
    pdf.scale(scale, scale)
    piece(pdf, key)
    pdf.restoreState()


def footer(pdf: Canvas, page: int, section: str) -> None:
    line(pdf, (38, 52), (574, 52), LINE)
    text(pdf, 38, 32, "NXT KEYBOARD PRESSER  /  " + section.upper(), 8, MUTED, True)
    text(pdf, 559, 32, f"{page:02}", 10, INK, True)
    pdf.showPage()


def inventory(pdf: Canvas) -> None:
    box(pdf, 38, 646, 536, 108, PALE)
    text(pdf, 57, 730, "MINDSTORMS NXT  /  ASSEMBLY BOOKLET", 10, BLUE, True)
    text(pdf, 57, 690, "Keyboard presser", 36, INK, True)
    text(pdf, 58, 665, "Two Technic lever modules for Option and Enter", 14, MUTED)
    text(pdf, 38, 611, "Piece inventory", 25, INK, True)
    text(pdf, 39, 589, "Quantities are for both modules. Use the hole count to identify liftarms.", 11, MUTED)
    for index, part in enumerate(PARTS):
        row, column = divmod(index, 2)
        x, y = 38 + column * 273, 521 - row * 58
        box(pdf, x, y, 263, 51, "#F3F8FC", LINE, 6)
        icon(pdf, part.key, x + 11, y + 27, 0.73)
        text(pdf, x + 72, y + 30, f"{part.count}×  {part.label}", 11, INK, True)
        text(pdf, x + 72, y + 14, part.description, 8, MUTED)
    text(pdf, 39, 146, "Also gather", 15, INK, True)
    wrap(pdf, 39, 125, "1 powered NXT brick, 2 NXT motor cables, 1 NXT USB data cable, "
         "1 external Mac-compatible keyboard, a non-slip mat, and removable ties or clamps.", 514, 11)
    wrap(pdf, 39, 81, "Build two copies through Step 6. Fit the axle lengths and motor adapters to your parts before powering up.",
         514, 10, MUTED)
    footer(pdf, 1, "Inventory")


def feet(pdf: Canvas, fresh: bool) -> None:
    color = TEAL if fresh else GRAY
    beam(pdf, (34, 55), (194, 55), 15, color, 12)
    beam(pdf, (51, 25), (211, 25), 15, color, 12)


def module(pdf: Canvas, step: int) -> None:
    feet(pdf, step == 1)
    if step == 1:
        arrow(pdf, (106, 115), (106, 66))
        arrow(pdf, (142, 110), (142, 37))
        text(pdf, 89, 130, "Parallel feet", 14, BLUE, True)
        line(pdf, (194, 54), (211, 25), BLUE, 1.5)
        arrow(pdf, (285, 62), (217, 43))
        text(pdf, 291, 58, "Front ends even", 13, BLUE, True)
        return

    frame(pdf, 66, 50, TEAL if step == 2 else GRAY)
    for x, y in ((66, 135), (142, 55)):
        pin(pdf, (x, y), (x + 21, y - 25), BLUE if step == 2 else SHADE)
    frame(pdf, 87, 25, TEAL if step == 2 else GRAY)
    for x in (96, 126):
        dot(pdf, x, 30, 5, DARK, INK)
    for x, y in ((87, 110), (163, 30)):
        dot(pdf, x, y, 5, YELLOW, DARK)
    if step == 2:
        arrow(pdf, (110, 154), (90, 117))
        text(pdf, 78, 166, "Keep the cheeks parallel", 13, BLUE, True)
        arrow(pdf, (71, 13), (93, 26))
        text(pdf, 9, 3, "Fixed pins", 12, BLUE, True)
        arrow(pdf, (248, 71), (170, 32))
        text(pdf, 255, 64, "Cross axles", 12, BLUE, True)
        return

    pivot = (191, 122)
    pin(pdf, (180, 135), (201, 110), SHADE)
    dot(pdf, 201, 110, 5, YELLOW, DARK)
    beam(pdf, pivot, (371, 122), 9, ORANGE if step == 3 else GRAY, 17)
    dot(pdf, *pivot, 7, YELLOW, DARK)
    axle_hole(pdf, *pivot)
    box(pdf, 250, 104, 18, 8, DARK, None, 2)
    if step == 3:
        arrow(pdf, (195, 179), (191, 132))
        text(pdf, 146, 190, "Pivot axle", 13, BLUE, True)
        arrow(pdf, (259, 79), (259, 102))
        text(pdf, 222, 68, "Pad at hole 4", 13, BLUE, True)
        return

    mount_color = TEAL if step == 4 else GRAY
    beam(pdf, (107, 138), (107, 177), 3, mount_color, 13)
    beam(pdf, (124, 110), (124, 159), 4, mount_color, 13)
    beam(pdf, (94, 177), (322, 177), 15, mount_color, 13)
    beam(pdf, (111, 159), (339, 159), 15, mount_color, 13)
    servo(pdf, 188, 162, "#CFDDE7" if step == 4 else GRAY)
    beam(pdf, (302, 186), (326, 186), 2, ORANGE if step == 4 else GRAY, 15)
    axle_hole(pdf, 302, 186)
    if step == 4:
        arrow(pdf, (367, 220), (332, 192))
        text(pdf, 292, 232, "One-hole offset", 13, BLUE, True)
        return

    beam(pdf, (326, 126), (326, 186), 4, TEAL if step == 5 else GRAY, 14)
    for x, y in ((326, 126), (326, 186)):
        dot(pdf, x, y, 5, BLUE, DARK)
    if step == 5:
        arrow(pdf, (382, 155), (338, 155))
        text(pdf, 340, 168, "Free pivots", 13, BLUE, True)
        return

    line(pdf, (214, 158), (229, 126), "#7358B6", 4)
    line(pdf, (218, 157), (233, 126), "#7358B6", 2.5)
    beam(pdf, (200, 86), (225, 86), 2, ORANGE, 12)
    box(pdf, 216, 86, 13, 23, ORANGE, DARK, 3)
    box(pdf, 242, 83, 40, 16, "#D9E6ED", DARK, 4)
    line(pdf, (231, 83), (303, 83), SHADE, 2)
    arrow(pdf, (269, 48), (269, 77))
    text(pdf, 229, 34, "Clear gap at rest", 13, BLUE, True)
    arrow(pdf, (174, 69), (212, 94))
    text(pdf, 125, 56, "Travel stop", 13, BLUE, True)


def keyboard(pdf: Canvas, x: float, y: float) -> None:
    box(pdf, x + 3, y - 5, 315, 124, SHADE, DARK, 12)
    box(pdf, x, y, 315, 124, "#D6E3EB", DARK, 12)
    for row in range(4):
        for column in range(12):
            box(pdf, x + 10 + column * 24, y + 12 + row * 26, 20, 20, "#F8FBFD", LINE, 3)
    box(pdf, x + 33, y + 12, 36, 20, A_COLOR, None, 3)
    box(pdf, x + 255, y + 38, 44, 20, B_COLOR, None, 3)


def brick(pdf: Canvas, x: float, y: float) -> None:
    box(pdf, x, y, 100, 127, "#E2EAF0", DARK, 13)
    box(pdf, x + 13, y + 64, 74, 43, "#AFBFAD", DARK, 4)
    text(pdf, x + 30, y + 79, "NXT", 17, DARK, True)
    dot(pdf, x + 50, y + 42, 11, ORANGE, DARK)
    for offset, label in ((18, "A"), (42, "B"), (66, "C")):
        box(pdf, x + offset, y + 119, 15, 9, DARK, None, 2)
        text(pdf, x + offset + 4, y + 135, label, 10, DARK, True)


def system_diagram(pdf: Canvas, step: int) -> None:
    if step == 7:
        keyboard(pdf, 52, 64)
        for x in (78, 128):
            beam(pdf, (x, 16), (x, 53), 4, GRAY, 9)
        box(pdf, 81, 22, 44, 20, A_COLOR, DARK, 5)
        text(pdf, 99, 28, "A", 10, PAPER, True)
        beam(pdf, (103, 49), (103, 86), 4, ORANGE, 9)
        dot(pdf, 103, 86, 3, DARK)
        for x in (303, 357):
            beam(pdf, (x, 206), (x, 240), 4, GRAY, 9)
        box(pdf, 308, 216, 44, 20, B_COLOR, DARK, 5)
        text(pdf, 326, 222, "B", 10, PAPER, True)
        beam(pdf, (330, 206), (330, 113), 9, ORANGE, 9)
        dot(pdf, 330, 113, 3, DARK)
        arrow(pdf, (173, 42), (112, 84), A_COLOR)
        text(pdf, 179, 39, "Option pad", 12, A_COLOR, True)
        arrow(pdf, (387, 154), (339, 117), B_COLOR)
        text(pdf, 369, 164, "Enter pad", 12, B_COLOR, True)
        text(pdf, 56, 205, "Top view", 11, MUTED, True)
        return
    if step == 8:
        brick(pdf, 170, 56)
        box(pdf, 10, 183, 115, 37, A_COLOR)
        text(pdf, 26, 196, "Option motor", 13, PAPER, True)
        box(pdf, 313, 183, 112, 37, B_COLOR)
        text(pdf, 333, 196, "Enter motor", 13, PAPER, True)
        arrow(pdf, (129, 198), (193, 183), A_COLOR)
        arrow(pdf, (309, 201), (221, 183), B_COLOR)
        box(pdf, 307, 27, 119, 40, PAPER, LINE)
        text(pdf, 322, 43, "Linux computer", 12, INK, True)
        arrow(pdf, (272, 87), (306, 65))
        text(pdf, 274, 88, "USB", 10, BLUE, True)
        text(pdf, 10, 28, "Keyboard paired with Mac", 10, MUTED)
        return

    for index, (label, color) in enumerate((
        ("Option down", A_COLOR), ("Enter down", B_COLOR), ("Enter up", B_COLOR), ("Option up", A_COLOR),
    )):
        x = 13 + index * 105
        dot(pdf, x + 34, 182, 20, color)
        text(pdf, x + 29, 177, str(index + 1), 15, PAPER, True)
        text(pdf, x, 146, label, 12, color, True)
        if index < 3:
            arrow(pdf, (x + 59, 182), (x + 105, 182))
    box(pdf, 12, 16, 408, 98, PAPER, LINE)
    text(pdf, 26, 93, "Linux bench commands", 12, INK, True)
    for index, command in enumerate((
        "python clicker.py brick",
        "python clicker.py jog option 10",
        "python clicker.py jog enter -10",
        "python clicker.py chord local.json",
    )):
        fill(pdf, DARK)
        pdf.setFont("Courier", 11)
        pdf.drawString(26, 74 - 14 * index, command)


@dataclass(frozen=True)
class Step:
    title: str
    instruction: str
    check: str
    pieces: tuple[tuple[str, int], ...] = ()


STEPS = (
    Step("Lay out the feet",
         "Set two 15L liftarms parallel on the non-slip mat. Turn their round holes sideways. Keep the "
         "front ends even and the keyboard out of the way while you assemble the stand.",
         "Leave room between the feet for the two upright frames and the centered lever.",
         (("rail", 2),)),
    Step("Pin the upright frames",
         "Put one 5 × 7 frame just inside each foot with its long edge along the foot. "
         "Use two friction pins per side at spaced holes to stop the frames from tilting. "
         "Run two axles across matching frame holes, away from the lever pivot and the lever's path, "
         "and fit a bush outside each cheek on both axles.",
         "Viewed from the front, the frames should be parallel and spaced wide enough for the lever and its two inner bushes.",
         (("frame", 2), ("pin", 4), ("axle", 2), ("bush", 4))),
    Step("Fit the moving lever",
         "Slide the pivot axle through an upper front hole, a bush, the end hole of the 9L lever, "
         "another bush, and the matching hole in the other frame. Bush both outer ends. "
         "Fix a soft pad underneath hole 4 when counting from the pivot as hole 1.",
         "The lever must swing freely. Leave a small amount of side clearance between its bushes.",
         (("lever", 1), ("axle", 1), ("bush", 4), ("pad", 1))),
    Step("Mount the motor and crank",
         "Overlap two 15L support beams with the tops of the frames. Use two pins per beam. "
         "Attach the motor across the supports at two of its mounting points. Use the angle connectors "
         "to align the motor as needed. Fit the crank to the output and retain it with a bush where the shaft allows.",
         "With the lever level, place the crank nearly horizontal. Its free hole should sit above lever hole 7. "
         "Verify the motor body and mount clear the lever and link.",
         (("rail", 2), ("motor", 1), ("crank", 1), ("shaft", 1), ("bush", 1), ("angle", 2), ("pin", 6))),
    Step("Connect the linkage",
         "Place the link between the crank's free hole and lever hole 7. Push in one low-friction pin "
         "at each joint. If the 4L link will not reach with the lever level, move the motor mount "
         "or choose a link length that matches the hole spacing.",
         "Disconnect the link at one end and check that the lever and link move freely. Reconnect it and, "
         "during the slow bench jog, check that the crank and link stay away from a straight line.",
         (("link", 1), ("free", 2))),
    Step("Add the return band and stop",
         "Hook a light band from a fixed support to the lever so the pad lifts at rest. "
         "Use a fixed angle connector and two pins as a stop under the lever. Disconnect the motor link "
         "and set the stop by hand with the keyboard in place.",
         "The key should register just before the lever meets the stop. At rest, leave visible clearance "
         "above the released key. Adjust the stop position to suit your key travel.",
         (("angle", 1), ("pin", 2), ("band", 1))),
    Step("Build the second module",
         "Repeat Steps 1-6, then place one pad over the tested Option key and one over the tested Enter "
         "or Return key. Rotate or mirror each stand to fit. Secure the base feet with removable ties "
         "or clamps to keep them from walking on the mat.",
         "Keep the pads centered over the keys. Check that the keyboard can slide out or the modules can lift off.",
    ),
    Step("Wire the brick",
         "Connect the Option motor to port A and the Enter motor to port B. Route the motor cables clear "
         "of the cranks with slack near the motors. Connect the NXT brick by USB to the Linux computer. "
         "The keyboard stays paired with the Mac.",
         "Keep both keys released before the first test.",
    ),
    Step("Calibrate and bench-test",
         "In the project environment, identify the brick and jog the motors unloaded. Re-couple one "
         "at a time. Find the shortest reliable release-to-press travel in a keyboard event viewer "
         "and record each signed angle and power under motors in local.json.",
         "Run the chord in the keyboard test window. Confirm the four events above and that both pads "
         "lift clear. The assembly dimensions are starting points for a physical fit check.",
    ),
)

PART_BY_KEY = {part.key: part for part in PARTS}
SHORT_LABELS = {
    "rail": "15L liftarm",
    "lever": "9L liftarm",
    "motor": "NXT motor",
    "crank": "2L crank",
    "angle": "Angle connector",
    "free": "Free pin",
    "pad": "Soft pad",
}


def step_page(pdf: Canvas, index: int, step: Step) -> None:
    stage = "One module" if index < 7 else "Two modules" if index < 9 else "Bench test"
    text(pdf, 39, 748, stage.upper(), 9, BLUE, True)
    dot(pdf, 62, 707, 24, BLUE)
    text(pdf, 55, 698, str(index), 24, PAPER, True)
    text(pdf, 99, 698, step.title, 28, INK, True)

    if step.pieces:
        box(pdf, 38, 583, 536, 74, "#F3F8FC", LINE)
        text(pdf, 49, 641, "ADD IN THIS STEP", 8, MUTED, True)
        for column, (key, count) in enumerate(step.pieces):
            x = 50 + column * ((516 / len(step.pieces)))
            icon(pdf, key, x + 2, 614, 0.59)
            label = SHORT_LABELS.get(key, PART_BY_KEY[key].label)
            text(pdf, x, 591, f"{count}× {label}", 7.1, INK, True)

    box(pdf, 38, 257, 536, 307, PALE)
    pdf.saveState()
    pdf.translate(63, 285)
    pdf.scale(1.11, 1.11)
    if index < 7:
        module(pdf, index)
    else:
        system_diagram(pdf, index)
    pdf.restoreState()

    wrap(pdf, 39, 228, step.instruction, 526, 13)
    box(pdf, 38, 68, 536, 69, "#F3F8FC", LINE)
    text(pdf, 50, 117, "CHECK", 9, BLUE, True)
    wrap(pdf, 50, 99, step.check, 505, 11)
    footer(pdf, index + 1, stage)


def build(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = Canvas(str(output), pagesize=PAGE, invariant=True)
    pdf.setTitle("Mindstorms NXT Keyboard Presser - Assembly Booklet")
    pdf.setSubject("Illustrated assembly instructions and parts inventory")
    pdf.setAuthor("Devin Mindstorms permission clicker project")
    pdf.setLineCap(1)
    inventory(pdf)
    for index, step in enumerate(STEPS, start=1):
        step_page(pdf, index, step)
    pdf.save()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=Path("output/pdf/nxt-keyboard-presser.pdf"))
    build(parser.parse_args().output)


if __name__ == "__main__":
    main()
