# LEGO NXT Option–Enter keyboard presser

The [illustrated assembly booklet](output/pdf/nxt-keyboard-presser.pdf) opens with the complete piece inventory for both modules. It includes nine numbered steps, wiring, and a bench test.

To rebuild the PDF, install ReportLab into the project environment and run the build target. Set `PDF_PYTHON` to a different interpreter if it already has ReportLab installed.

```sh
.venv/bin/python -m pip install reportlab
make lego-guide
```

Make two independently adjustable Technic lever modules. Port **A** holds Option while port **B** taps Enter. The dimensions below are starting points in Technic holes. Fit the stands to your keyboard and check the travel on the bench.

## Parts

| Quantity | Part |
| ---: | --- |
| 1 | Mindstorms NXT brick, powered, with its USB data cable |
| 2 | NXT interactive servo motors and two NXT motor cables |
| 2 | Stiff Technic beams for the moving levers, each about 7–9 holes long |
| 2 | Short axle-mounted cranks, each with a connection one hole from the motor axle |
| 2 | Short liftarms or links to connect the cranks to the levers |
| 1 set | Long beams or plates for the base, uprights and cross braces, plus pins, axles and bushes |
| 2 each | Small rubber or foam pads, light rubber bands, adjustable stop blocks |
| 1 | External Mac-compatible keyboard |

The NXT servos include a rotation sensor. The controller uses its readings to check both the press and return positions. [LEGO NXT user guide](https://www.lego.com/cdn/product-assets/product.bi.core.pdf/4520736.pdf)

## 1. Locate the keys and build the base

1. Connect the external keyboard to the Mac. On a harmless Devin permission card, verify the exact Option and Return or Enter keys by hand and confirm the approval scope.
2. Lay two long beams alongside the keyboard. Tie them together with crossmembers outside the active key area. Add padded stops at two adjoining edges so the keyboard returns to the same position when removed. Keep the cable opening clear.
3. Mark the center of each target key. Leave access to one edge of the keyboard so you can slide it out from under the levers. Use removable pins where each module joins the base.

```text
Top view, placement varies by keyboard

   ┌──────────────── keyboard cradle ────────────────┐
   │  ┌───────────────────────────────┐   B stand   │
   │  │                               │      ↓      │
   │  │                          [Enter] ← B pad    │
   │  │                               │             │
   │  │    [Option]                   │             │
   │  └───────↑───────────────────────┘             │
   │       A pad                                    │
   └────── A stand ─────────────────────────────────┘
```

## 2. Assemble one lever module

1. Pin two uprights to the base and brace them so they cannot spread or rack. Run an axle through both uprights as the lever pivot. Add bushes on both sides so the lever stays centered while rotating freely.
2. Position the lever's soft pad over the middle of the key. Start about **three holes from the pivot**. Attach the linkage farther out, about **five or six holes from the pivot**. The pad will travel less than the linkage. Move the entire module or choose a different pivot hole to line up with the key.
3. Secure the motor to the stand using two mounting points. Mount the crank on the motor output. Link its off-center hole to the moving lever with pivots at both ends. At the start of the press, the crank should move the link mainly up or down. Keep it clear of the positions where the crank and link line up and can jam.
4. Fit a light rubber band that lifts the pad away from the key at rest. Add a stop block against the moving beam. With the motor link disconnected, move the lever by hand. Adjust the stop so the key registers before the stop makes contact. Leave a visible gap between the pad and the released key. Verify that the pivot, pad and linkage move freely throughout the stroke.

```text
Side view of one module

                      motor on the fixed stand
                                 ◉──o  short crank
                                    │
                                    │  pivoting link
  fixed pivot                       │
       ●──────────────┬─────────────o  moving beam
                      ▪ soft pad
                      ↓
  keyboard ──────── [ key ] ──────────────────────
                 stop mounted on the stand

  Move the stop to meet the moving beam after the key registers.
```

## 3. Duplicate and wire

Build the second module using the same arrangement. Rotate or mirror it to reach the second key. Route cables outside both linkages and give each cable slack at its motor. Connect **Option to A**, **Enter to B**, and the brick's USB cable to the separate Linux computer. The keyboard stays paired with the Mac. Motor direction can differ between modules. Calibrate each independently.

## 4. Calibrate and test

1. With both modules clear of the keyboard, run `.venv/bin/python clicker.py brick`. Jog each motor before coupling it to its lever. The examples below are for unloaded motors.

   ```sh
   .venv/bin/python clicker.py jog option 10
   .venv/bin/python clicker.py jog enter -10
   ```

2. Couple one module at a time. Use a keyboard event viewer to find the shortest repeatable stroke that presses and releases its key without reaching the hard stop. Adjust the fixture or lever ratio if small angle changes cause excessive travel. Record each signed angle and power in the `motors` section of `local.json`. Set the mechanism to both keys released before each new program run.
3. Run `.venv/bin/python clicker.py chord local.json` on the Linux computer. Keep the Mac focused on the keyboard test window. Expect **Option down → Enter down → Enter up → Option up** once after a three-second delay. Repeat the bench test and confirm both pads clear the keys each time.
4. Test that you can lift the modules or slide out the keyboard with both motors unpowered. If a lever can trap a key, revise the linkage or make the module easier to remove. Then use the [software guide](README.md#teach-the-watcher-your-permission-cards) to verify the screen detector before combining it with the motors.

These instructions cover the mechanism and bench test. Final beam lengths, motor angles and clearances depend on your keyboard and require a physical fit check.
