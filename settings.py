"""Validation for the camera, screen, and motor settings."""

from dataclasses import dataclass
from math import isfinite
from typing import Annotated, Optional, Union

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    model_validator,
)


def validate_crop(crop: list[float]) -> list[float]:
    if (not isinstance(crop, list) or len(crop) != 4
            or any(type(value) not in (int, float) or not isfinite(value) or value < 0 for value in crop)):
        raise ValueError("Set crop to [left, top, width, height] fractions.")
    left, top, width, height = crop
    if width == 0 or height == 0 or left + width > 1 or top + height > 1:
        raise ValueError("Keep the crop inside the camera frame.")
    return crop


Crop = Annotated[list[float], AfterValidator(validate_crop)]


@dataclass(frozen=True)
class Stroke:
    degrees: StrictInt
    power: StrictInt

    def __post_init__(self) -> None:
        if type(self.degrees) is not int or not 5 <= abs(self.degrees) <= 120:
            raise ValueError("Set signed motor travel to 5–120 degrees after calibration.")
        if type(self.power) is not int or not 10 <= self.power <= 60:
            raise ValueError("Set motor power to an integer from 10 to 60.")


class Motors(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    option: Stroke
    enter: Stroke


class CameraSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    device: Union[str, int]
    width: int = Field(default=1920, gt=0)
    height: int = Field(default=1080, gt=0)
    fps: int = Field(default=30, gt=0)
    pixel_format: Optional[str] = Field(default=None, min_length=4, max_length=4)


class CardAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    image: str = Field(min_length=1)
    panel: Crop
    heading: Crop
    allow: Crop
    minimum_score: float = Field(default=0.85, gt=0, le=1)


class ScreenView(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    crop: Crop
    ocr_regions: list[Crop] = Field(default_factory=list)
    anchor: Optional[CardAnchor] = None

    @model_validator(mode="after")
    def verify_anchor_regions(self) -> "ScreenView":
        if self.anchor is not None and len(self.ocr_regions) != 3:
            raise ValueError("An anchored card needs three OCR regions for heading, command, and Allow.")
        return self


class Screen(ScreenView):
    model_config = ConfigDict(extra="forbid")

    prompt_lines: list[str]
    clear_lines: list[str]
    additional_prompt_lines: list[list[str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def verify_lines(self) -> "Screen":
        cards = [self.prompt_lines, *self.additional_prompt_lines]
        if any(not line.strip() for lines in [*cards, self.clear_lines] for line in lines):
            raise ValueError("Set each OCR fingerprint to a list of nonempty lines.")
        if any(len(set(lines)) < 2 for lines in cards):
            raise ValueError("Provide the exact OCR lines of the card, including the action and approval control.")
        if self.anchor is not None and any(len(lines) < 3 for lines in cards):
            raise ValueError("An anchored card fingerprint needs a heading, command, and Allow line.")
        if self.anchor is None and self.ocr_regions and any(len(lines) != len(self.ocr_regions) for lines in cards):
            raise ValueError("Provide one OCR region per line of every configured permission card.")
        if tuple(self.clear_lines) in self.approved_cards:
            raise ValueError("The visible and cleared card fingerprints must differ.")
        return self

    @property
    def approved_cards(self) -> set[tuple[str, ...]]:
        return {tuple(lines) for lines in (self.prompt_lines, *self.additional_prompt_lines)}
