"""Boot the mock-I/O acceptance bench on a generic ESP32."""

import json
import sys

from bench import Bench, exercise

print("Bench target:", sys.platform)
exercise()
try:
    scenario = open("scenario.json")
except OSError:
    scenario = None
if scenario:
    with scenario:
        case = json.load(scenario)
    bench = Bench(case["cards"])
    for event in case["events"]:
        bench.event(*event)
    print("Simulated keys:", bench.brick.keys)
    assert bench.brick.keys == case["expected_keys"]
    print("CUSTOM REPLAY PASS")
print("BOOT TEST COMPLETE")
