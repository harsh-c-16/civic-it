.PHONY: install run dev test seed clean

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uvicorn app.main:app --reload --port 8000

test:
	pytest -q

seed:
	python -c "import json; print(len(json.load(open('seed_data.json'))), 'records')"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -f *.db
	rm -rf .pytest_cache
