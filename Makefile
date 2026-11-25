.PHONY: test demo model-demo typecheck

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

test:
	$(PYTHON) -m unittest -v

typecheck:
	$(PYTHON) -m ty check

demo:
	$(PYTHON) clicker.py check-image demo/config.json demo/other-card.png || test $$? -eq 3
	$(PYTHON) clicker.py simulate demo/config.json demo/other-card.png demo/matching-card.png demo/matching-card.png demo/matching-card.png

model-demo:
	$(PYTHON) demo/model_samples.py .build/model-demo
	$(PYTHON) card_model.py train .build/model-demo/manifest.json .build/model-demo/card-model.xml
	$(PYTHON) card_model.py predict .build/model-demo/card-model.xml .build/model-demo/permission-6.png
