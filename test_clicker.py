import unittest
from dataclasses import dataclass
from unittest.mock import patch

from camera import OCRLine, parse_tsv
from clicker import Axis, MatchGate, chord, watch
from settings import Screen, Stroke


@dataclass(frozen=True)
class EncoderReading:
    rotation_count: int


class Motor:
    def __init__(self, name: str, events: list[tuple[str, str]]) -> None:
        self.name = name
        self.events = events
        self.fail_on_press = False
        self.angle = 0

    def weak_turn(self, power: int, distance: int) -> None:
        self.angle += distance if power > 0 else -distance
        is_down = self.angle != 0
        self.events.append((self.name, "down" if is_down else "up"))
        if is_down and self.fail_on_press:
            raise OSError("USB failed after movement began")

    def get_tacho(self) -> EncoderReading:
        return EncoderReading(self.angle)

    def brake(self) -> None:
        pass

    def idle(self) -> None:
        self.events.append((self.name, "idle"))


class ChordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.option = Axis(Motor("option", self.events), Stroke(15, 25))
        self.enter_motor = Motor("enter", self.events)
        self.enter = Axis(self.enter_motor, Stroke(-15, 25))

    def test_hold_tap_and_release_in_order(self):
        self.assertTrue(chord(self.option, self.enter))
        self.assertEqual(self.events, [
            ("option", "down"), ("enter", "down"), ("enter", "up"),
            ("enter", "idle"), ("option", "up"), ("option", "idle"),
        ])

    def test_prompt_change_releases_option_without_enter(self):
        self.assertFalse(chord(self.option, self.enter, lambda: False))
        self.assertEqual(self.events, [("option", "down"), ("option", "up"), ("option", "idle")])

    def test_error_after_partial_press_still_attempts_both_releases(self):
        self.enter_motor.fail_on_press = True
        with self.assertRaises(OSError):
            chord(self.option, self.enter)
        self.assertEqual(self.events[-4:], [
            ("enter", "up"), ("enter", "idle"), ("option", "up"), ("option", "idle"),
        ])


class WatchTests(unittest.TestCase):
    screen = Screen(crop=[0, 0, 1, 1], prompt_lines=["printf test", "Allow Once"],
                    clear_lines=["Waiting for input"])

    def snapshot(self, lines: list[str], confidence: float = 1.0) -> list[OCRLine]:
        return [{"text": line, "confidence": confidence} for line in lines]

    def test_nonmatching_and_uncertain_observations_never_fire(self):
        gate = MatchGate(self.screen)
        for observation in (
            self.snapshot(["printf other", "Allow Once"]),
            self.snapshot(["printf  test", "Allow Once"]),
            self.snapshot(["printf test", "Always Allow"]),
            self.snapshot(self.screen.prompt_lines + ["Another request"]),
            self.snapshot(self.screen.prompt_lines, confidence=0.3),
            self.snapshot([]),
            None,
        ):
            self.assertIsNone(gate.observe(observation))
            self.assertIsNone(gate.observe(observation))

    def test_camera_loss_or_unrelated_text_does_not_rearm(self):
        gate = MatchGate(self.screen)
        prompt = self.snapshot(self.screen.prompt_lines)
        clear = self.snapshot(self.screen.clear_lines)
        self.assertIsNone(gate.observe(prompt))
        self.assertEqual(gate.observe(prompt), tuple(self.screen.prompt_lines))
        unrelated = self.snapshot(["Different work"])
        for observation in (None, unrelated, unrelated, prompt, prompt, clear):
            self.assertIsNone(gate.observe(observation))
        self.assertIsNone(gate.observe(clear))
        self.assertIsNone(gate.observe(prompt))
        self.assertEqual(gate.observe(prompt), tuple(self.screen.prompt_lines))

    def test_single_watch_waits_for_second_exact_frame(self):
        wrong = self.snapshot(["printf other", "Allow Once"])
        correct = self.snapshot(self.screen.prompt_lines)
        frames = [wrong, correct, None, correct, correct]
        with patch("clicker.time.sleep"):
            seen: list[tuple[str, ...]] = []
            samples = iter(frames)

            def act(matched: tuple[str, ...]) -> bool:
                seen.append(matched)
                return True

            self.assertEqual(watch(self.screen, lambda: next(samples), act), 0)
            self.assertEqual(seen, [tuple(self.screen.prompt_lines)])
            self.assertIsNone(next(samples, None))

    def test_explicitly_taught_second_card_can_trigger(self):
        alternate = ["printf other", "Allow Once"]
        screen = Screen(crop=self.screen.crop, prompt_lines=self.screen.prompt_lines,
                        clear_lines=self.screen.clear_lines, additional_prompt_lines=[alternate])
        gate = MatchGate(screen)
        self.assertIsNone(gate.observe(self.snapshot(alternate)))
        self.assertEqual(gate.observe(self.snapshot(alternate)), tuple(alternate))


class OCRTests(unittest.TestCase):
    def test_groups_words_in_order_and_uses_lowest_confidence(self):
        rows = ("level\tpage_num\tblock_num\tpar_num\tline_num\tconf\ttext\n"
                "4\t1\t1\t1\t1\t-1\t\n"
                "5\t1\t1\t1\t1\t95\tRun\n"
                "5\t1\t1\t1\t1\t71\tcommand?\n"
                "5\t1\t1\t1\t2\t99\tprintf\n"
                "5\t1\t1\t1\t2\t97\ttest\n")
        self.assertEqual(parse_tsv(rows), [{"text": "Run command?", "confidence": 0.71},
                                           {"text": "printf test", "confidence": 0.97}])


if __name__ == "__main__":
    unittest.main()
