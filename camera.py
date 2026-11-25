"""External RGB camera input and on-host Tesseract LSTM inference."""

from __future__ import annotations

import csv
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from threading import Condition, Event, Thread
from time import monotonic
from types import TracebackType
from typing import TYPE_CHECKING, TypedDict

from settings import CameraSettings, validate_crop

if TYPE_CHECKING:
    from cv2 import VideoCapture
    from cv2.typing import MatLike


class OCRLine(TypedDict):
    text: str
    confidence: float


@dataclass(frozen=True)
class Capture:
    received_at: float
    frame: MatLike


def read_image(path: str | Path) -> MatLike:
    import cv2

    frame = cv2.imread(str(path))
    if frame is None:
        raise RuntimeError(f"Could not read image {path}.")
    return frame


def crop_frame(frame: MatLike, crop: list[float]) -> MatLike:
    validate_crop(crop)
    height, width = frame.shape[:2]
    x, y, w, h = crop
    view = frame[round(y * height):round((y + h) * height),
                 round(x * width):round((x + w) * width)]
    if not view.size:
        raise ValueError("The camera crop is too small for this frame.")
    return view


def recognize(frame: MatLike, crop: list[float], page_mode: int = 6) -> list[OCRLine]:
    import cv2

    view = crop_frame(frame, crop)
    gray = cv2.cvtColor(view, cv2.COLOR_BGR2GRAY)
    ok, png = cv2.imencode(".png", gray)
    if not ok:
        raise RuntimeError("Could not encode the camera crop.")
    result = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", "eng", "--oem", "1", "--psm", str(page_mode), "tsv"],
        input=png.tobytes(), capture_output=True, timeout=3,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or "Tesseract OCR failed.")
    return parse_tsv(result.stdout.decode())


def recognize_card(frame: MatLike, crop: list[float], regions: Sequence[list[float]] = ()) -> list[OCRLine]:
    if not regions:
        return recognize(frame, crop)
    lines: list[OCRLine] = []
    for region in regions:
        result = recognize(frame, region, page_mode=7)
        if len(result) != 1:
            return []
        lines.append(result[0])
    return lines


def parse_tsv(data: str) -> list[OCRLine]:
    grouped: dict[tuple[str, ...], list[tuple[str, float]]] = {}
    for row in csv.DictReader(StringIO(data), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row["level"] != "5" or not row["text"].strip():
            continue
        group = tuple(row[field] for field in ("page_num", "block_num", "par_num", "line_num"))
        grouped.setdefault(group, []).append((row["text"], float(row["conf"]) / 100))
    return [{"text": " ".join(word for word, _ in words),
             "confidence": min(confidence for _, confidence in words)}
            for words in grouped.values()]


class Camera:
    def __init__(self, settings: CameraSettings) -> None:
        self.settings = settings
        self.condition = Condition()
        self.stop = Event()
        self.latest: Capture | None = None

    def __enter__(self) -> Camera:
        import cv2

        settings = self.settings
        capture = cv2.VideoCapture(settings.device, cv2.CAP_V4L2)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Could not open V4L2 camera {settings.device}.")
        if settings.pixel_format:
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*settings.pixel_format))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.height)
        capture.set(cv2.CAP_PROP_FPS, settings.fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.reader = Thread(target=self._read, args=(capture,), daemon=True)
        self.reader.start()
        return self

    def _read(self, capture: VideoCapture) -> None:
        try:
            while not self.stop.is_set():
                ok, frame = capture.read()
                with self.condition:
                    self.latest = Capture(monotonic(), frame) if ok else None
                    self.condition.notify_all()
                if not ok:
                    self.stop.wait(0.1)
        finally:
            capture.release()

    def frame(self) -> Capture | None:
        requested = monotonic()
        with self.condition:
            if self.condition.wait_for(
                lambda: self.latest is not None and self.latest.received_at > requested, timeout=1
            ):
                return self.latest
        return None

    def __exit__(self, _error_type: type[BaseException] | None, _error: BaseException | None,
                 _traceback: TracebackType | None) -> None:
        self.stop.set()
        self.reader.join(timeout=1)
