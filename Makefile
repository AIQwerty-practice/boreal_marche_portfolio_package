.PHONY: help setup etl rules spotcheck tune balance assistant-eval mlflow-demo mlflow-ui train index api openapi test up

help:
	@echo "Available targets: setup etl rules spotcheck tune balance assistant-eval mlflow-demo mlflow-ui train index api openapi test up"

setup:
	python -m pip install -e ".[dev]"

etl:
	python -m boreal_marche.data.ingest --root .
	python -m boreal_marche.data.clean --root .

rules:
	python -m boreal_marche.recommendation.recommend --root .

spotcheck:
	python -m boreal_marche.modeling.screen --root .

tune:
	python -m boreal_marche.modeling.tune --root .

balance:
	python -m boreal_marche.modeling.balancing --root .

assistant-eval:
	python scripts/evaluate_assistant.py --root .

mlflow-demo:
	python scripts/demo_mlflow.py --root .

mlflow-ui:
	powershell -ExecutionPolicy Bypass -File scripts/start_mlflow.ps1

train:
	python -m boreal_marche.features.customer_snapshots --root .

index:
	python scripts/evaluate_assistant.py --root .

test:
	python -m pytest

api:
	python -m uvicorn boreal_marche.api.app:app --host 127.0.0.1 --port 8000

openapi:
	python scripts/export_openapi.py

up: api
