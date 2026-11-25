"""Train and evaluate a local visual classifier for permission cards."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import cv2
import numpy as np
from pydantic import BaseModel, Field, TypeAdapter

from camera import crop_frame, read_image
from settings import Crop

if TYPE_CHECKING:
    from cv2.typing import MatLike
    from numpy.typing import NDArray

SIZE = (192, 96)
HOG = cv2.HOGDescriptor(SIZE, (16, 16), (8, 8), (8, 8), 9)
LABELS = {"other": -1, "permission": 1}
Split = Literal["train", "test"]
Label = Literal["other", "permission"]
Sample = tuple["MatLike", int]


class CaptureRecord(BaseModel):
    image: str
    group: str = Field(min_length=1)
    split: Split
    label: Label
    crop: Crop = Field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])


def features(image: MatLike) -> NDArray[np.float32]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, SIZE, interpolation=cv2.INTER_AREA)
    return np.asarray(HOG.compute(resized), dtype=np.float32).ravel()


def variants(image: MatLike) -> Iterator[MatLike]:
    """Known, mild camera distortions. Apply only to training frames."""
    yield image
    yield cv2.GaussianBlur(image, (5, 5), 0)
    yield cv2.convertScaleAbs(image, alpha=0.78, beta=20)
    height, width = image.shape[:2]
    corners = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    for sign in (-1, 1):
        offset = np.array([[0.025 * sign * width, 0], [0, 0.025 * height],
                           [0.025 * sign * width, 0], [0, -0.025 * height]], dtype=np.float32)
        warp = cv2.getPerspectiveTransform(corners, corners + offset)
        yield cv2.warpPerspective(image, warp, (width, height), borderMode=cv2.BORDER_REPLICATE)


def load_manifest(path: Path) -> Iterator[tuple[Split, Path, Label, list[float]]]:
    rows = TypeAdapter(list[CaptureRecord]).validate_json(path.read_bytes())
    groups: dict[str, Split] = {}
    hashes: set[bytes] = set()
    for row in rows:
        if groups.setdefault(row.group, row.split) != row.split:
            raise ValueError(f"Capture group {row.group} appears in both splits.")
        image_path = path.parent / row.image
        digest = hashlib.sha256(image_path.read_bytes()).digest()
        if digest in hashes:
            raise ValueError(f"Duplicate image: {image_path}")
        hashes.add(digest)
        yield row.split, image_path, row.label, row.crop


def load_samples(path: Path) -> dict[Split, list[Sample]]:
    samples: dict[Split, list[Sample]] = {"train": [], "test": []}
    for split, image_path, label, crop in load_manifest(path):
        samples[split].append((crop_frame(read_image(image_path), crop), LABELS[label]))
    for split, rows in samples.items():
        if {label for _, label in rows} != set(LABELS.values()):
            raise ValueError(f"The {split} split needs both permission and other images.")
    return samples


def train(samples: Sequence[Sample]) -> cv2.ml.SVM:
    model = cv2.ml.SVM.create()
    model.setType(cv2.ml.SVM_C_SVC)
    model.setKernel(cv2.ml.SVM_LINEAR)
    model.setC(1)
    rows = [(features(variant), label) for image, label in samples for variant in variants(image)]
    model.train(np.asarray([row for row, _ in rows], dtype=np.float32), cv2.ml.ROW_SAMPLE,
                np.asarray([label for _, label in rows], dtype=np.int32))
    return model


def is_permission(model: cv2.ml.SVM, image: MatLike) -> bool:
    _, labels = model.predict(features(image).reshape(1, -1))
    return int(labels[0, 0]) == LABELS["permission"]


def evaluate(model: cv2.ml.SVM, samples: Sequence[Sample]) -> dict[str, int]:
    counts = {"true_positive": 0, "false_positive": 0, "true_negative": 0, "false_negative": 0}
    for image, label in samples:
        positive = is_permission(model, image)
        correct = positive == (label == LABELS["permission"])
        key = ("true" if correct else "false") + ("_positive" if positive else "_negative")
        counts[key] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fit = commands.add_parser("train", help="fit on train captures and report held-out results")
    fit.add_argument("manifest", type=Path)
    fit.add_argument("model", type=Path)
    check = commands.add_parser("predict", help="classify one image or crop")
    check.add_argument("model", type=Path)
    check.add_argument("image", type=Path)
    check.add_argument("--crop", type=float, nargs=4, default=[0, 0, 1, 1])
    args = parser.parse_args()
    if args.command == "train":
        samples = load_samples(args.manifest)
        model = train(samples["train"])
        model.save(str(args.model))
        print(json.dumps(evaluate(model, samples["test"]), sort_keys=True))
        return 0
    model = cv2.ml.SVM.load(str(args.model))
    image = crop_frame(read_image(args.image), args.crop)
    print("permission" if is_permission(model, image) else "other")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, cv2.error) as error:
        sys.exit(f"{type(error).__name__}: {error}")
