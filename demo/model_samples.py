"""Draw small, fictional cards for an offline training smoke test."""

import json
import sys
from pathlib import Path

import cv2
import numpy as np


def draw(label, number):
    frame = np.full((220, 480, 3), 30 + number * 6, dtype=np.uint8)
    x = 20 + number * 3
    cv2.rectangle(frame, (x, 30), (460, 190), (53, 53, 53), -1)
    if label == "permission":
        items = [("Permission requested", 64), (f"printf sample-{number}", 105), ("Allow once", 164)]
        cv2.rectangle(frame, (x + 18, 137), (x + 170, 177), (186, 86, 32), -1)
    else:
        items = [("Workspace", 64), (f"Opening notes-{number}", 105), ("Preview ready", 164)]
        cv2.rectangle(frame, (300, 138), (440, 177), (89, 89, 89), -1)
    for line, y in items:
        cv2.putText(frame, line, (x + 25, y), cv2.FONT_HERSHEY_SIMPLEX, 0.64,
                    (236, 236, 236), 1, cv2.LINE_AA)
    return frame


output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
manifest = []
for number in range(1, 7):
    for label in ("permission", "other"):
        filename = f"{label}-{number}.png"
        if not cv2.imwrite(str(output / filename), draw(label, number)):
            raise RuntimeError(f"Could not write {filename}")
        manifest.append({"image": filename, "label": label, "group": f"fictional-{number}",
                         "split": "train" if number < 5 else "test"})
(output / "manifest.json").write_text(json.dumps(manifest, indent=2))
