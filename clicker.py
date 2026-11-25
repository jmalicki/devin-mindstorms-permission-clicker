"""External camera recognition and USB control of a physical NXT key presser."""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
import time
from collections.abc import Callable, Generator, Iterable, Sequence
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, ContextManager, Protocol

from camera import Camera, OCRLine, crop_frame, read_image, recognize, recognize_card
from settings import CameraSettings, Motors, Screen, ScreenView, Stroke

if TYPE_CHECKING:
    from cv2.typing import MatLike
    from nxt.brick import Brick

PROJECT = Path(__file__).resolve().parent


class TachoReading(Protocol):
    @property
    def rotation_count(self) -> int: ...


class MotorIO(Protocol):
    def get_tacho(self) -> TachoReading: ...
    def weak_turn(self, power: int, tacho_units: int, /) -> None: ...
    def brake(self) -> None: ...
    def idle(self) -> None: ...


class Key(Protocol):
    def held(self) -> ContextManager[None]: ...


class Axis:
    def __init__(self, motor: MotorIO, stroke: Stroke) -> None:
        self.motor = motor
        self.stroke = stroke
        self.home = self.position()

    def position(self) -> int:
        return self.motor.get_tacho().rotation_count

    def move(self, target: int) -> None:
        start = self.position()
        distance = target - start
        tolerance = max(1, min(3, abs(self.stroke.degrees) // 10))
        if abs(distance) <= tolerance:
            return
        if abs(distance) > abs(self.stroke.degrees) + tolerance:
            raise RuntimeError("Motor position is outside its calibrated travel. Check the lever.")
        direction = 1 if distance > 0 else -1
        deadline = time.monotonic() + 2
        self.motor.weak_turn(direction * self.stroke.power, abs(distance))
        while direction * (target - self.position()) > tolerance:
            if time.monotonic() >= deadline:
                raise RuntimeError("Motor failed to reach its target. Check for a blocked lever.")
            time.sleep(0.02)
        self.motor.brake()
        if abs(self.position() - target) > tolerance:
            raise RuntimeError("Motor missed its target. Reduce power or adjust the linkage.")

    @contextmanager
    def held(self) -> Generator[None, None, None]:
        if abs(self.position() - self.home) > 3:
            raise RuntimeError("Motor is away from its starting position. Reset the lever by hand.")
        try:
            self.move(self.home + self.stroke.degrees)
            yield
        finally:
            try:
                self.move(self.home)
            finally:
                self.motor.idle()


def chord(option: Key, enter: Key, confirm_prompt: Callable[[], bool] = lambda: True) -> bool:
    with option.held():
        if not confirm_prompt():
            return False
        with enter.held():
            time.sleep(0.06)
    return True


@contextmanager
def open_brick() -> Generator[Brick, None, None]:
    from nxt.locator import BrickNotFoundError, find

    with (PROJECT / ".nxt.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another clicker process is using the NXT.") from error
        try:
            brick = find(backends=["usb"], config=None)
        except BrickNotFoundError as error:
            raise RuntimeError("No NXT found. Power it on and connect its USB data cable.") from error
        with brick:
            yield brick


def axes(brick: Brick, settings: Motors) -> tuple[Axis, Axis]:
    from nxt.motor import Port

    return Axis(brick.get_motor(Port.A), settings.option), Axis(brick.get_motor(Port.B), settings.enter)


def recognized_text(lines: Sequence[OCRLine] | None) -> tuple[str, ...] | None:
    if not lines or any(line["confidence"] < 0.70 for line in lines):
        return None
    return tuple(line["text"] for line in lines)


def read_screen(frame: MatLike, screen: Screen) -> list[OCRLine]:
    lines = recognize_card(frame, screen.crop, screen.ocr_regions)
    if screen.ocr_regions and screen.clear_lines and recognized_text(lines) not in screen.approved_cards:
        cleared = recognize(frame, screen.crop)
        if recognized_text(cleared) == tuple(screen.clear_lines):
            return cleared
    return lines


class MatchGate:
    """Require two consecutive exact observations and an explicit clear before repeating."""

    def __init__(self, screen: Screen) -> None:
        self.prompts = screen.approved_cards
        self.clear = tuple(screen.clear_lines)
        self.previous: tuple[str, ...] | None = None
        self.latched = False

    def observe(self, lines: Sequence[OCRLine] | None) -> tuple[str, ...] | None:
        text = recognized_text(lines)
        stable = text is not None and self.previous == text
        self.previous = text
        if not stable:
            return None
        if self.latched:
            if self.clear and text == self.clear:
                self.latched = False
            return None
        if text in self.prompts:
            self.latched = True
            return text
        return None


def watch(screen: Screen, sample: Callable[[], Sequence[OCRLine] | None],
          actuator: Callable[[tuple[str, ...]], bool], repeat: bool = False, seconds: int = 300) -> int:
    gate = MatchGate(screen)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        matched = gate.observe(sample())
        if matched is not None:
            if not actuator(matched):
                print("The card changed or became unreadable. Enter was skipped.", flush=True)
                return 1
            if not repeat:
                return 0
        time.sleep(0.35)
    print("Watch timed out.", flush=True)
    return 0


def sample_frame(camera: Camera, screen: Screen,
                 visual_check: Callable[[MatLike], bool] | None = None) -> list[OCRLine]:
    capture = camera.frame()
    if capture is None:
        return []
    frame = capture.frame
    try:
        lines = read_screen(frame, screen)
    except subprocess.TimeoutExpired:
        return []
    if visual_check is not None and recognized_text(lines) in screen.approved_cards:
        if not visual_check(crop_frame(frame, screen.crop)):
            return []
    return lines if time.monotonic() - capture.received_at <= 2 else []


class SimulatedKey:
    def __init__(self, name: str) -> None:
        self.name = name

    @contextmanager
    def held(self) -> Generator[None, None, None]:
        print(f"{self.name} down")
        try:
            yield
        finally:
            print(f"{self.name} up")


def simulate(screen: Screen, images: Iterable[Path]) -> int:
    frames = iter(images)
    gate = MatchGate(screen)
    for path in frames:
        matched = gate.observe(read_screen(read_image(path), screen))
        if matched is not None:
            print("Matched permission card in replay.")

            def confirm() -> bool:
                next_path = next(frames, None)
                return next_path is not None and recognized_text(read_screen(read_image(next_path), screen)) == matched

            if chord(SimulatedKey("Option"), SimulatedKey("Enter"), confirm):
                return 0
            print("Replay confirmation changed or was missing. Enter was skipped.")
            return 1
    print("No configured permission card matched.")
    return 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("brick", help="read the USB brick identity without moving motors")
    jog = commands.add_parser("jog", help="move one lever and return it to its starting position")
    jog.add_argument("key", choices=["option", "enter"])
    jog.add_argument("degrees", type=int)
    jog.add_argument("--power", type=int, default=25)
    test = commands.add_parser("chord", help="manually trigger one calibrated Option–Enter press")
    test.add_argument("config", type=Path)
    for name, description in (("inspect-image", "read the configured crop of an image"),
                              ("check-image", "test card recognition on a saved camera image"),
                              ("snapshot", "save one camera frame for alignment and calibration")):
        image_command = commands.add_parser(name, help=description)
        image_command.add_argument("config", type=Path)
        image_command.add_argument("image", type=Path)
    replay = commands.add_parser("simulate", help="replay camera images and simulate the chord")
    replay.add_argument("config", type=Path)
    replay.add_argument("images", nargs="+", type=Path)
    monitor = commands.add_parser("watch", help="watch for the configured prompt in dry-run mode")
    monitor.add_argument("config", type=Path)
    monitor.add_argument("--live", action="store_true", help="use the physical NXT motors on a match")
    monitor.add_argument("--repeat", action="store_true", help="rearm after a verified clear state")
    monitor.add_argument("--seconds", type=int, default=300)
    monitor.add_argument("--card-model", type=Path, help="also require the local visual model to identify the card")
    args = parser.parse_args()

    if args.command == "brick":
        with open_brick() as brick:
            print(brick.get_device_info()[0])
        return 0
    if args.command == "jog":
        from nxt.motor import Port

        stroke = Stroke(args.degrees, args.power)
        with open_brick() as brick:
            port = Port.A if args.key == "option" else Port.B
            with Axis(brick.get_motor(port), stroke).held():
                time.sleep(0.15)
        return 0

    config: dict[str, object] = json.loads(args.config.read_text())
    if args.command == "chord":
        strokes = Motors.model_validate(config["motors"])
        with open_brick() as brick:
            option, enter = axes(brick, strokes)
            print("Move focus to your test window. Pressing in 3 seconds.", flush=True)
            time.sleep(3)
            chord(option, enter)
        return 0

    if args.command == "snapshot":
        import cv2

        with Camera(CameraSettings.model_validate(config["camera"])) as camera:
            capture = camera.frame()
        if capture is None or not cv2.imwrite(str(args.image), capture.frame):
            raise RuntimeError("Could not save a frame from the camera.")
        height, width = capture.frame.shape[:2]
        print(f"Saved {width}×{height} frame to {args.image}")
        return 0

    if args.command == "inspect-image":
        view = ScreenView.model_validate(config["screen"])
        for line in recognize_card(read_image(args.image), view.crop, view.ocr_regions):
            print(f'{line["confidence"]:.2f}  {line["text"]}')
        return 0

    screen = Screen.model_validate(config["screen"])
    if args.command == "check-image":
        lines = read_screen(read_image(args.image), screen)
        for line in lines:
            print(f'{line["confidence"]:.2f}  {line["text"]}')
        matched = recognized_text(lines) in screen.approved_cards
        print("Permission card matched." if matched else "No configured permission card matched.")
        return 0 if matched else 3
    if args.command == "simulate":
        return simulate(screen, args.images)

    if args.repeat and not screen.clear_lines:
        parser.error("--repeat requires a verified screen.clear_lines fingerprint.")
    if args.seconds <= 0:
        parser.error("--seconds must be positive.")
    visual_check: Callable[[MatLike], bool] | None = None
    if args.card_model:
        import cv2

        from card_model import is_permission

        try:
            model = cv2.ml.SVM.load(str(args.card_model))
        except cv2.error as error:
            raise ValueError(f"Could not load card model {args.card_model}.") from error

        def matches_visual_model(image: MatLike) -> bool:
            return is_permission(model, image)

        visual_check = matches_visual_model

    camera_settings = CameraSettings.model_validate(config["camera"])
    strokes = Motors.model_validate(config["motors"]) if args.live else None
    with ExitStack() as stack:
        camera = stack.enter_context(Camera(camera_settings))
        motors = axes(stack.enter_context(open_brick()), strokes) if strokes is not None else None

        def sample() -> list[OCRLine]:
            return sample_frame(camera, screen, visual_check)

        def act(matched: tuple[str, ...]) -> bool:
            if motors is None:
                print("Matched the configured permission card. Dry run, no motors moved.", flush=True)
                return True
            fired = chord(*motors, confirm_prompt=lambda: recognized_text(sample()) == matched)
            if fired:
                print("Sent one physical Option–Enter chord.", flush=True)
            return fired

        print("Watching for the configured card.", flush=True)
        return watch(screen, sample, act, args.repeat, args.seconds)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError, subprocess.SubprocessError) as error:
        sys.exit(f"{type(error).__name__}: {error}")
