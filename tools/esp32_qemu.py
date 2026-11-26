"""Build a mock-I/O ESP32 flash image and cold-boot it in Espressif QEMU."""

from __future__ import annotations

import argparse
import json
import os
import select
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "firmware" / "esp32"


@contextmanager
def emulator(executable: str, image: Path):
    command = [executable, "-machine", "esp32", "-nographic", "-monitor", "none",
               "-no-reboot", "-nic", "none", "-drive", f"file={image},if=mtd,format=raw"]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        if proc.stdin:
            proc.stdin.close()
        if proc.stdout:
            proc.stdout.close()


def read_until(proc: subprocess.Popen, marker: bytes, timeout: float = 30) -> bytes:
    assert proc.stdout is not None
    output = bytearray()
    deadline = time.monotonic() + timeout
    while not output.endswith(marker):
        if not select.select([proc.stdout], [], [], max(0, deadline - time.monotonic()))[0]:
            raise TimeoutError(f"ESP32 serial timeout: {bytes(output[-1200:])!r}")
        chunk = os.read(proc.stdout.fileno(), 4096)
        if not chunk:
            raise RuntimeError(f"QEMU exited: {bytes(output[-1200:])!r}")
        output.extend(chunk)
    return bytes(output)


def send(proc: subprocess.Popen, data: bytes) -> None:
    assert proc.stdin is not None
    proc.stdin.write(data)
    proc.stdin.flush()


def execute(proc: subprocess.Popen, source: str) -> None:
    send(proc, source.encode() + b"\x04")
    reply = read_until(proc, b"\x04>")
    if not reply.startswith(b"OK") or not reply.endswith(b"\x04\x04>"):
        raise RuntimeError(f"ESP32 program failed: {reply!r}")


def install(proc: subprocess.Popen, name: str, data: bytes) -> None:
    execute(proc, f"f = open({name!r}, 'wb')")
    # Small acknowledged writes fit the simulated UART receive buffer.
    for start in range(0, len(data), 128):
        execute(proc, f"f.write({data[start:start + 128]!r})")
    execute(proc, "f.close()")


def build(qemu: str, firmware: Path, output: Path, scenario: Path | None) -> None:
    binary = firmware.read_bytes()
    flash_size = 4 * 1024 * 1024
    if binary[:1] != b"\xe9" or binary[0x7000:0x7002] != b"\xaa\x50" or len(binary) > flash_size - 4096:
        raise ValueError("Expected a 4 MiB ESP32_GENERIC combined firmware binary for offset 0x1000.")
    if output.resolve() == firmware.resolve():
        raise ValueError("Choose separate input firmware and output image paths.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as folder:
        image = Path(folder) / "flash.img"
        flash = bytearray(b"\xff" * flash_size)
        flash[4096:4096 + len(binary)] = binary
        image.write_bytes(flash)
        with emulator(qemu, image) as proc:
            read_until(proc, b">>> ")
            send(proc, b"\x01")
            read_until(proc, b"\n>")
            for name in ("controller.py", "bench.py", "main.py"):
                install(proc, name, (SOURCE / name).read_bytes())
            if scenario:
                data = json.dumps(json.loads(scenario.read_text())).encode()
                install(proc, "scenario.json", data)
            execute(proc, "import os; os.sync()")
        with emulator(qemu, image) as proc:
            boot = read_until(proc, b">>> ").decode(errors="replace")
            print(boot[boot.find("Bench target:"):].strip())
            for marker in ("Bench target: esp32", "ESP32 BENCH PASS", "BOOT TEST COMPLETE"):
                if marker not in boot:
                    raise RuntimeError(f"Missing {marker!r} in ESP32 boot output: {boot[-1600:]}")
            if scenario and "CUSTOM REPLAY PASS" not in boot:
                raise RuntimeError("The custom replay did not pass on the ESP32.")
        image.replace(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", default="qemu-system-xtensa")
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(".build/esp32/bench.img"))
    parser.add_argument("--scenario", type=Path)
    args = parser.parse_args()
    build(args.qemu, args.firmware, args.output, args.scenario)
