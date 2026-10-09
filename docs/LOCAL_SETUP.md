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
