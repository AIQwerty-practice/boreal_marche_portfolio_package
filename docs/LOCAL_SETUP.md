# Local setup and reproducibility

This guide brings up a functional local Boreal Marche application from a clean clone without distributing private runtime data, model binaries, or cloud credentials.

## Before you start

This is a local-development rebuild. It uses public source data and creates local generated files; it does not recreate the protected final test results, connect to the project AWS account, or grant production authorization.

## Prerequisites

- Python 3.11 or 3.12.
- `pip` and a virtual-environment tool.
- Internet access for the documented public-source-data ingestion step.
- Git, to obtain the repository.

Optional hosted LLM providers require the environment-variable names in `.env.example` or `deploy/aws/.env.example`. Leave those values unset to run the local grounded assistant without an external provider.

## Clean-clone commands

Clone the portfolio package, open it, and create an isolated Python environment:

```bash
git clone https://github.com/AIQwerty-practice/boreal_marche_portfolio_package.git
cd boreal_marche_portfolio_package
python -m venv .venv
```

Activate it once. Use the command matching your shell:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS, Linux, or Git Bash
source .venv/bin/activate
```

Install, rebuild, and test in the listed order:

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
python scripts/build_drift_baseline.py
python -m pytest
```

These commands create the local runtime files that are intentionally excluded from Git, including the retention model, metadata, recommendation rules, processed data, and an aggregate development-only drift baseline. The baseline step matters: it aligns the local model’s checksum with its local reference and uses only the train/validation snapshots, never protected-test rows. Do not commit generated files or replace the official baseline in a shared deployment.

## Start the application

```bash
python -m uvicorn boreal_marche.api.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` for the interface, `http://127.0.0.1:8000/docs` for the API contract, and `http://127.0.0.1:8000/ready` for the readiness response.

In another terminal, use either check to confirm the service:

```bash
curl -fsS http://127.0.0.1:8000/ready
curl -fsS http://127.0.0.1:8000/version
```

The ready response should report `head_a`, `head_b`, and `head_c` as `true`. A locally rebuilt model reports `protected_test_evaluated: false`; that is expected because the protected final evaluation is not part of this public package.

## Optional: use your own trained retention model

This option is for local experimentation only. Do not use real customer data or replace a deployed model without approval, validation, a privacy/security review, and a deployment change process.

The safest route is to use your own public or authorized transaction data with the supplied pipeline. Update only a copy of the configuration if needed, then run the same clean, snapshot, screen, tune, and baseline commands above. The tuning step writes the expected bundle:

- `artifacts/retention_model.joblib`: a trusted local `joblib` artifact with `predict_proba` and `feature_names_in_`.
- `artifacts/retention_model_meta.json`: metadata produced by the tuning command, including the artifact SHA-256, selected threshold, and `protected_test_evaluated: false`.
- `src/boreal_marche/monitoring/development_baseline.json`: a development-only aggregate baseline rebuilt with `python scripts/build_drift_baseline.py` after the model changes.

The API sends feature values in exactly the order named by `model.feature_names_in_`; it rejects missing or extra values. Keep `primary_country` as the one categorical field expected by the supplied pipeline, and retain all other engineered feature names unless you also adapt and test the API contract. Never load an untrusted serialized `joblib` file: Python model deserialization can execute code. Run this only on a model bundle you trained or received from a trusted source, and then run `python -m pytest` plus the `/ready` and `/version` checks before using the local interface.

## Optional: local Ollama question routing

Heads A and B and the grounded baseline assistant work after the rebuild above. To enable the Ollama question-routing choice locally, install Ollama separately, pull a supported model, and run its local service. For example:

```bash
ollama pull qwen3:4b
ollama serve
```

In a second terminal, set the following values before starting the API. Do not commit them.

PowerShell:

```powershell
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "qwen3:4b"
$env:BOREAL_LLM_ACCESS_TOKEN = "choose-a-local-demo-token"
python -m uvicorn boreal_marche.api.app:app --host 127.0.0.1 --port 8000
```

Bash:

```bash
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_MODEL="qwen3:4b"
export BOREAL_LLM_ACCESS_TOKEN="choose-a-local-demo-token"
python -m uvicorn boreal_marche.api.app:app --host 127.0.0.1 --port 8000
```

Enter the same local demo token in the browser’s LLM-access-token field and select Ollama. Ollama only routes the fictional question; approved local retrieval and typed tools still produce the displayed answer and citations.

## Optional: local staff-demo assistant

The staff path is configured separately from the customer assistant. Set a unique local username and password in the same terminal before starting the API:

```powershell
$env:BOREAL_DEMO_STAFF_USERNAME = "staff-demo"
$env:BOREAL_DEMO_STAFF_PASSWORD = "choose-a-unique-local-password"
```

The interface will then support the restricted staff sign-in and its short-lived HTTP-only session. These values are for a local demonstration only; they are not employee identity management and must not be committed, shared publicly, or used as production credentials.

## Important boundary

The local pipeline rebuilds a functional development runtime from the documented public source data. It does not rerun the project’s one-time protected final evaluation or claim to recreate the original cloud environment, production certification, or final D3 artifact byte-for-byte. Record the results of any independent clean-machine run in `REPRODUCIBILITY.md` before treating the reproducibility requirement as complete.
