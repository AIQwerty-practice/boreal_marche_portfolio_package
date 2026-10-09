# Local setup and reproducibility

This guide brings up a functional local Boreal Marche application from a clean clone without distributing private runtime data, model binaries, or cloud credentials.

## Prerequisites

- Python 3.11 or 3.12.
- `pip` and a virtual-environment tool.
- Internet access for the documented public-source-data ingestion step.

Optional hosted LLM providers require the environment-variable names in `.env.example` or `deploy/aws/.env.example`. Leave those values unset to run the local grounded assistant without an external provider.

## Clean-clone commands

```bash
git clone https://github.com/AIQwerty-practice/boreal_marche_portfolio_package.git
cd boreal_marche_portfolio_package
python -m venv .venv
```

Activate the environment for your operating system, then run:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m boreal_marche.data.ingest --root .
python -m boreal_marche.data.clean --root .
python -m boreal_marche.features.customer_snapshots --root .
python -m boreal_marche.modeling.screen --root .
python -m boreal_marche.modeling.tune --root .
python -m boreal_marche.modeling.balancing --root .
python -m boreal_marche.recommendation.recommend --root .
python -m pytest
```

These commands create the local runtime files that are intentionally excluded from Git, including the retention model, metadata, recommendation rules, and processed data. Do not commit any generated files.

## Start the application

```bash
python -m uvicorn boreal_marche.api.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` for the interface, `http://127.0.0.1:8000/docs` for the API contract, and `http://127.0.0.1:8000/ready` for the readiness response.

## Important boundary

The local pipeline rebuilds a functional development runtime from the documented public source data. It does not rerun the project’s one-time protected final evaluation or claim to recreate the original cloud environment, production certification, or final D3 artifact byte-for-byte. Record the results of any independent clean-machine run in `REPRODUCIBILITY.md` before treating the reproducibility requirement as complete.
