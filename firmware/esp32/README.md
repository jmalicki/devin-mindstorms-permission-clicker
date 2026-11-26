# ESP32 decision firmware and replay bench

The target is a Luxonis OAK-D-IoT camera paired with an NXT. The Myriad X would run card localization and text recognition. The camera's ESP32 runs the exact text comparison, frame checks and one-shot approval decision. The NXT would handle encoder-calibrated motion and release the keys on its own deadline.

The executable bench boots the original Xtensa ESP32 in Espressif QEMU, using MicroPython's generic ESP32 firmware. The mocked vision chip supplies decoded OCR results. A simulated brick accepts commands and records key transitions. Both doubles run inside the emulated ESP32, so this exercises the actual MicroPython port and decision code. The simulation uses virtual event times. Camera optics, inference speed, SPI, Bluetooth Classic pairing, NXT encoders and physical timing require hardware tests.

## Run

For a fast development check, run `make esp32-test` in the repo root. To run the same tests on an emulated chip, download [Espressif's QEMU Xtensa build](https://github.com/espressif/qemu/releases/tag/esp-develop-9.2.2-20261109) for your OS and the [ESP32_GENERIC v1.29.0 combined firmware](https://micropython.org/resources/firmware/ESP32_GENERIC-20260824-v1.29.0.bin). Keep the extracted QEMU distribution together with its ROM files. On Apple silicon the official binary also needs the Homebrew libraries pixman, libgcrypt and sdl2-compat.

From the repo root, run the builder on Linux or macOS with the downloaded paths.

```sh
python3 tools/esp32_qemu.py --qemu /path/to/qemu/bin/qemu-system-xtensa \
    --firmware /path/to/ESP32_GENERIC-20260824-v1.29.0.bin \
    --scenario demo/esp32-replay.json
```

The builder provisions the simulated flash over the emulated UART, terminates that emulator, then starts a new one and checks the boot-time test output. Success produces a 4 MiB QEMU flash image at `.build/esp32/bench.img`. To boot it again independently, run the command below. Exit the serial console with Ctrl-A then X when using the default multiplexed monitor.

```sh
/path/to/qemu/bin/qemu-system-xtensa -machine esp32 -nographic -nic none \
    -drive file=.build/esp32/bench.img,if=mtd,format=raw
```

## Decision and motor protocol

Each arming is a single transaction. The transport must agree on a fresh session token with the brick before arming. The bench uses a fixed token to make replay repeatable.

1. The ESP32 looks for two consecutive, fresh observations of the same configured card. Each line, including the complete command and approval label, must match, and every line must reach 700/1000 confidence. Mark ambiguous, clipped or unreadable cards incomplete.
2. The ESP32 sends `hold(session)`. The brick holds Option and replies `held(session)` once the movement completes. In the bench, that acknowledgment can be delayed or dropped.
3. The ESP32 requires another matching frame captured after it received the acknowledgment. It then sends `tap(session)`. The brick taps Enter, releases Enter and releases Option. A changed or incomplete card cancels the hold.
4. A brick-side watchdog releases Option if the tap never arrives. The ESP32 also expires pending transactions. Duplicate packets cannot generate another keypress. Re-arming requires a new session.

## Supply model outputs

Copy [the sample scenario](../../demo/esp32-replay.json), change the card list or events, and pass its path to `--scenario`. The builder checks your expected key sequence on cold boot. A frame event has the following fields in order.

```text
[delivery_ms, "frame", sequence, captured_ms, complete, [[line_text, confidence_per_mille], ...]]
```

The source increments the sequence for each new observation. Capture and delivery times use the same monotonic millisecond clock relative to arming. The adapter must preserve capture time across buffering. An `ack` event delivers the pending brick acknowledgment. A `tick` event advances the timers without delivering a frame. These event arrays are a test interface. Production needs a Myriad-to-ESP32 SPI adapter, an ESP32 Classic Bluetooth SPP transport, and a brick program implementing the acknowledgment, motion and watchdog. The bench runs stock MicroPython for simulation. The board integration must provide Classic SPP, for example through ESP-IDF.

[Luxonis ESP32 SPI reference](https://github.com/luxonis/esp32-spi-message-demo) · [Espressif ESP32 QEMU documentation](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/tools/qemu.html)
