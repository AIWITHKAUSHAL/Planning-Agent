.PHONY: install run demo test

install:
	python -m pip install -r requirements-dev.txt

run:
	uvicorn app.api:app --reload

demo:
	DEMO_MODE=true uvicorn app.api:app --reload

test:
	pytest -q

