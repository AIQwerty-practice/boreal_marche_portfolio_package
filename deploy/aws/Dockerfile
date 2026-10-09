FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

RUN addgroup --system boreal && adduser --system --ingroup boreal boreal

COPY pyproject.toml README.md ./
COPY DATA_CARD.md MODEL_CARD.md ./
COPY src ./src
COPY docs/corpus ./docs/corpus
COPY reports/d2/figures/system_architecture.png ./reports/d2/figures/system_architecture.png
COPY tests/assistant_golden_set.json tests/assistant_adversarial_set.json ./tests/
COPY scripts/compare_assistant_providers.py ./scripts/compare_assistant_providers.py
COPY scripts/smoke_ollama.py ./scripts/smoke_ollama.py

RUN python -m pip install --upgrade pip \
    && python -m pip install \
        "anyio>=4,<4.15" \
        "fastapi>=0.115,<1" \
        "httpx>=0.27,<1" \
        "pandas>=2.2,<3" \
        "pyarrow>=17,<22" \
        "pydantic>=2,<3" \
        "scikit-learn==1.9.0" \
        "catboost>=1.2,<2" \
        "uvicorn>=0.34,<1" \
    && python -m pip install --no-deps .

COPY frontend ./frontend

RUN mkdir -p /app/artifacts /app/data/processed /app/reports/d3/provider_comparison \
    && chown -R boreal:boreal /app

USER boreal

EXPOSE 8000

CMD ["uvicorn", "boreal_marche.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
