import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import cv2
import numpy as np
from cv2.typing import MatLike

from card_layout import CardLocator
from clicker import MatchGate, read_screen, recognized_text
from settings import CardAnchor, Screen

WIDTH, HEIGHT = 1040, 940
REFERENCE_X, REFERENCE_Y = 110, 112
CARD_WIDTH, CARD_HEIGHT, LINE_HEIGHT = 740, 141, 31
HEADING, ALLOW = "Run a command?", "Allow"
SHORT = ("echo alpha",)
LONG = (
    "echo alpha beta gamma delta epsilon zeta eta theta",
    "echo second",
    "echo third",
    "echo fourth",
    "echo fifth",
    "echo sixth",
    "echo seventh",
    "echo eighth",
)


def fraction(x: int, y: int, width: int, height: int) -> list[float]:
    return [x / WIDTH, y / HEIGHT, width / WIDTH, height / HEIGHT]


def draw_text(frame: MatLike, x: int, y: int, text: str, size: float = 0.76) -> None:
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, (24, 24, 24), 2, cv2.LINE_AA)


def panel() -> MatLike:
    frame = np.full((HEIGHT, WIDTH, 3), 230, dtype=np.uint8)
    cv2.rectangle(frame, (30, 25), (1000, 905), (251, 251, 251), -1)
    return frame


def draw_card(frame: MatLike, x: int, y: int, commands: tuple[str, ...]) -> None:
    extra = LINE_HEIGHT * (len(commands) - 1)
    cv2.rectangle(frame, (x, y), (x + CARD_WIDTH - 1, y + CARD_HEIGHT + extra - 1), (255, 255, 255), -1)
    draw_text(frame, x + 19, y + 33, HEADING)
    for index, command in enumerate(commands):
        draw_text(frame, x + 23, y + 70 + index * LINE_HEIGHT, command)
    left, top = x + 580, y + 91 + extra
    cv2.rectangle(frame, (left, top), (left + 123, top + 37), (220, 236, 252), -1)
    cv2.rectangle(frame, (left, top), (left + 123, top + 37), (109, 138, 180), 1)
    draw_text(frame, left + 30, top + 27, ALLOW)


def fingerprint(commands: tuple[str, ...]) -> tuple[str, ...]:
    return (HEADING, *commands, ALLOW)


class CardLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        x, y = REFERENCE_X, REFERENCE_Y
        self.anchor = CardAnchor(
            image="reference.png",
            panel=fraction(30, 25, 971, 881),
            heading=fraction(x + 14, y + 10, 240, 33),
            allow=fraction(x + 577, y + 88, 131, 43),
        )
        self.screen = Screen(
            crop=fraction(x, y, CARD_WIDTH, CARD_HEIGHT),
            ocr_regions=[
                fraction(x + 12, y + 10, 250, 34),
                fraction(x + 16, y + 46, 690, 39),
                fraction(x + 604, y + 94, 88, 33),
            ],
            anchor=self.anchor,
            prompt_lines=list(fingerprint(SHORT)),
            additional_prompt_lines=[list(fingerprint(commands)) for commands in (LONG[:2], LONG[:4], LONG)],
            clear_lines=[],
        )
        reference = panel()
        draw_card(reference, x, y, SHORT)
        with TemporaryDirectory() as directory:
            config_dir = Path(directory)
            self.assertTrue(cv2.imwrite(str(config_dir / self.anchor.image), reference))
            locator = CardLocator.load(self.screen, config_dir)
        assert locator is not None
        self.locator = locator

    def test_card_location_and_exact_ocr_with_varied_panel_and_command_text(self) -> None:
        cases = (
            (48, 64, 0, 2, SHORT),
            (230, 270, 8, 10, LONG[:2]),
            (93, 615, 20, 2, LONG[:4]),
            (205, 485, 14, 1, LONG),
            (55, 105, 2, 13, LONG),
        )
        for x, y, before, after, commands in cases:
            with self.subTest(x=x, y=y, before=before, after=after, commands=len(commands)):
                height = CARD_HEIGHT + LINE_HEIGHT * (len(commands) - 1)
                frame = panel()
                for index in range(before):
                    text = "Read the status from a local file" if index % 2 else "Checking the workspace"
                    draw_text(frame, 50, 47 + 28 * index, text, 0.59)
                for index in range(after):
                    draw_text(frame, 50, y + height + 23 + index * 27, "More text in the panel", 0.59)
                draw_card(frame, x, y, commands)
                layout = self.locator.locate(frame, self.screen)
                assert layout is not None
                for actual, expected in zip(layout.crop, fraction(x, y, CARD_WIDTH, height), strict=True):
                    self.assertAlmostEqual(actual, expected)
                lines = read_screen(frame, self.screen, self.locator)
                self.assertEqual(recognized_text(lines), fingerprint(commands))
                gate = MatchGate(self.screen)
                self.assertIsNone(gate.observe(lines))
                self.assertEqual(gate.observe(lines), fingerprint(commands))

    def test_changed_last_command_line_does_not_match(self) -> None:
        commands = (*LONG[:-1], "echo extra")
        frame = panel()
        draw_card(frame, 210, 395, commands)
        lines = read_screen(frame, self.screen, self.locator)
        self.assertEqual(recognized_text(lines), fingerprint(commands))
        gate = MatchGate(self.screen)
        self.assertIsNone(gate.observe(lines))
        self.assertIsNone(gate.observe(lines))

    def test_missing_and_duplicate_anchors_do_not_match(self) -> None:
        frame = panel()
        draw_text(frame, 55, 100, "Preparing a command")
        self.assertEqual(read_screen(frame, self.screen, self.locator), [])
        draw_card(frame, 58, 130, SHORT)
        draw_card(frame, 190, 475, LONG)
        self.assertEqual(read_screen(frame, self.screen, self.locator), [])

    def test_visual_check_receives_relocated_full_card(self) -> None:
        frame = panel()
        draw_card(frame, 235, 405, LONG)
        reject_card = Mock(return_value=False)
        self.assertEqual(read_screen(frame, self.screen, self.locator, reject_card), [])
        reject_card.assert_called_once()
        image = reject_card.call_args.args[0]
        self.assertEqual(image.shape[:2], (CARD_HEIGHT + LINE_HEIGHT * (len(LONG) - 1), CARD_WIDTH))
