"""Locate a permission card within a calibrated panel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from camera import crop_frame, read_image
from settings import CardAnchor, ScreenView

if TYPE_CHECKING:
    from cv2.typing import MatLike


@dataclass(frozen=True)
class CardLayout:
    crop: list[float]
    ocr_regions: list[list[float]]


def contains(outer: list[float], inner: list[float]) -> bool:
    x, y, width, height = outer
    left, top, w, h = inner
    return (x <= left and y <= top and left + w <= x + width + 1e-9
            and top + h <= y + height + 1e-9 and w > 0 and h > 0)


def unique_match(panel: MatLike, template: MatLike, threshold: float) -> tuple[int, int] | None:
    import cv2

    height, width = template.shape[:2]
    if height > panel.shape[0] or width > panel.shape[1]:
        return None
    scores = cv2.matchTemplate(panel, template, cv2.TM_CCOEFF_NORMED)
    _, best, _, (x, y) = cv2.minMaxLoc(scores)
    if best < threshold:
        return None
    # Suppress neighbouring peaks from this same match before looking for a second card.
    scores[max(0, y - height // 2):y + height // 2 + 1,
           max(0, x - width // 2):x + width // 2 + 1] = -1
    return None if cv2.minMaxLoc(scores)[1] >= threshold else (x, y)


class CardLocator:
    def __init__(self, anchor: CardAnchor, reference: MatLike) -> None:
        import cv2

        self.anchor = anchor
        self.height, self.width = reference.shape[:2]
        if not all(contains(anchor.panel, region) for region in (anchor.heading, anchor.allow)):
            raise ValueError("Keep the heading and Allow anchors inside the search panel.")
        self.heading = cv2.cvtColor(crop_frame(reference, anchor.heading), cv2.COLOR_BGR2GRAY)
        self.allow = cv2.cvtColor(crop_frame(reference, anchor.allow), cv2.COLOR_BGR2GRAY)
        if min(self.heading.std(), self.allow.std()) < 1:
            raise ValueError("Each card anchor must contain visible detail.")

    @classmethod
    def load(cls, view: ScreenView, config_dir: Path) -> CardLocator | None:
        if view.anchor is None:
            return None
        return cls(view.anchor, read_image(config_dir / view.anchor.image))

    def locate(self, frame: MatLike, view: ScreenView) -> CardLayout | None:
        import cv2

        if frame.shape[:2] != (self.height, self.width):
            return None
        anchor = self.anchor
        panel = cv2.cvtColor(crop_frame(frame, anchor.panel), cv2.COLOR_BGR2GRAY)
        heading = unique_match(panel, self.heading, anchor.minimum_score)
        allow = unique_match(panel, self.allow, anchor.minimum_score)
        if heading is None or allow is None:
            return None
        panel_x = round(anchor.panel[0] * self.width)
        panel_y = round(anchor.panel[1] * self.height)
        dx = panel_x + heading[0] - round(anchor.heading[0] * self.width)
        dy = panel_y + heading[1] - round(anchor.heading[1] * self.height)
        allow_dx = panel_x + allow[0] - round(anchor.allow[0] * self.width)
        allow_dy = panel_y + allow[1] - round(anchor.allow[1] * self.height)
        if abs(dx - allow_dx) > max(2, self.width // 200) or allow[1] <= heading[1]:
            return None
        growth = (allow_dy - dy) / self.height
        heading_ocr, command_ocr, allow_ocr = view.ocr_regions

        def shift(region: list[float], offset_y: int, extra_height: float = 0) -> list[float]:
            x, y, w, h = region
            return [x + dx / self.width, y + offset_y / self.height, w, h + extra_height]

        card = shift(view.crop, dy, growth)
        regions = [shift(heading_ocr, dy), shift(command_ocr, dy, growth), shift(allow_ocr, allow_dy)]
        if not contains(anchor.panel, card) or not all(contains(card, region) for region in regions):
            return None
        if regions[1][1] + regions[1][3] > regions[2][1] + 1e-9:
            return None
        return CardLayout(card, regions)
