"""Export the per-frame OCR decision for a programmable camera."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from camera import OCRLine
from settings import MIN_OCR_CONFIDENCE, Screen


def encode_card(lines: Sequence[str]) -> list[int]:
    """256 ends each line, including the last. All other symbols are UTF-8 bytes."""
    symbols: list[int] = []
    for line in lines:
        symbols.extend(line.encode("utf-8"))
        symbols.append(256)
    return symbols


def model_inputs(lines: Sequence[OCRLine], width: int) -> dict[str, np.ndarray]:
    """An overlong observation is unmatchable. Never truncate command text."""
    symbols = encode_card([line["text"] for line in lines])
    encoded = np.full(width, -1, dtype=np.int32)
    if len(symbols) <= width:
        encoded[:len(symbols)] = symbols
    scores = [line["confidence"] for line in lines]
    confidence = min(scores) if scores and all(0 <= score <= 1 for score in scores) else 0
    return {"symbols": encoded, "confidence": np.asarray([confidence], dtype=np.float64)}


def export(screen: Screen, output: Path) -> None:
    import onnx  # ty: ignore[import-not-found]
    from onnx import TensorProto, helper, numpy_helper  # ty: ignore[import-not-found]

    cards = list(dict.fromkeys(tuple(card) for card in [screen.prompt_lines, *screen.additional_prompt_lines]))
    rows = [encode_card(card) for card in cards]
    width = max(map(len, rows))
    patterns = np.asarray([row + [-1] * (width - len(row)) for row in rows], dtype=np.int32)
    constants = {
        "patterns": patterns,
        "ids": np.arange(1, len(rows) + 1, dtype=np.int32),
        "minimum": np.asarray([MIN_OCR_CONFIDENCE], dtype=np.float64),
        "zero": np.asarray([0], dtype=np.int32),
    }
    node = helper.make_node
    graph = helper.make_graph(
        [
            node("Equal", ["symbols", "patterns"], ["equal"]),
            node("Cast", ["equal"], ["bits"], to=TensorProto.INT32),
            node("ReduceMin", ["bits"], ["matched"], axes=[1], keepdims=0),
            node("Mul", ["ids", "matched"], ["matched_ids"]),
            node("ReduceMax", ["matched_ids"], ["best_id"], axes=[0], keepdims=1),
            node("GreaterOrEqual", ["confidence", "minimum"], ["legible"]),
            node("Where", ["legible", "best_id", "zero"], ["card_id"]),
        ],
        "exact_permission_card",
        [helper.make_tensor_value_info("symbols", TensorProto.INT32, [width]),
         helper.make_tensor_value_info("confidence", TensorProto.DOUBLE, [1])],
        [helper.make_tensor_value_info("card_id", TensorProto.INT32, [1])],
        initializer=[numpy_helper.from_array(value, name) for name, value in constants.items()],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)], ir_version=8)
    onnx.checker.check_model(model, full_check=True)
    onnx.save(model, str(output))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    export(Screen.model_validate(json.loads(args.config.read_text())["screen"]), args.output)
