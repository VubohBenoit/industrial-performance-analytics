PY ?= python3

.PHONY: install data pipeline test notebook scenarios all clean-outputs

install:
	$(PY) -m pip install -r requirements.txt

data:
	$(PY) -m src.ingestion.generate_synthetic

pipeline:
	$(PY) -m src.pipeline --source synthetic

test:
	$(PY) -m pytest

notebook:
	$(PY) scripts/build_notebook.py

scenarios:
	$(PY) scripts/scenarios.py

all: pipeline test scenarios notebook

clean-outputs:
	rm -rf data/processed reports/figures reports/sql_results dashboard/powerbi_data
