.PHONY: test demo model-demo typecheck lego-guide esp32-test esp32-qemu

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PDF_PYTHON ?= $(PYTHON)
ESP32_QEMU ?= .build/esp32/qemu/bin/qemu-system-xtensa
ESP32_FIRMWARE ?= .build/esp32/micropython.bin
ESP32_SCENARIO ?= demo/esp32-replay.json

esp32-test:
	$(PYTHON) firmware/esp32/bench.py

esp32-qemu:
	$(PYTHON) tools/esp32_qemu.py --qemu "$(ESP32_QEMU)" --firmware "$(ESP32_FIRMWARE)" --scenario "$(ESP32_SCENARIO)"

test:
	$(PYTHON) -m unittest -v

typecheck:
	$(PYTHON) -m ty check

lego-guide:
	$(PDF_PYTHON) tools/build_lego_guide.py

demo:
	$(PYTHON) clicker.py check-image demo/config.json demo/other-card.png || test $$? -eq 3
	$(PYTHON) clicker.py simulate demo/config.json demo/other-card.png demo/matching-card.png demo/matching-card.png demo/matching-card.png

model-demo:
	$(PYTHON) demo/model_samples.py .build/model-demo
	$(PYTHON) card_model.py train .build/model-demo/manifest.json .build/model-demo/card-model.xml
	$(PYTHON) card_model.py predict .build/model-demo/card-model.xml .build/model-demo/permission-6.png
