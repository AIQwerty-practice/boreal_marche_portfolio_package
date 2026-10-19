# Boreal Marche Customer Intelligence — Deliverables and Reproducibility Package

This public, replication-oriented deliverables package presents the Boreal Marche capstone system: retention prediction, basket recommendations, and a grounded bilingual assistant. It is built from a reviewed committed baseline rather than a local working directory.

## Current status

The portfolio package is a public, reproducibility-oriented companion to the completed capstone. It contains the runnable implementation and supporting technical documentation; final evidence, appendices, presentation files, and the release manifest are maintained in the separate release package. It is not a certified production release.

## Week 11 reproducibility standard

This repository is intended for a classmate to clone on a clean machine and reproduce the system using documented commands. Environment variables are listed in [`.env.example`](.env.example) and [`deploy/aws/.env.example`](deploy/aws/.env.example); no secret values are committed. The teacher coordinates the final reproducibility review with students.

## For a teammate

Use Python 3.11 or 3.12, then run:

```bash
python -m venv .venv
# Activate the environment for your shell.
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m boreal_marche.data.ingest --root .
python -m pytest
```

The ingestion process retrieves the documented source dataset when needed. Raw and generated customer-level data are intentionally not distributed in this repository. A successful test run and documented local API start are the current reproducibility checks; the final clean-machine outcome remains a D7 release requirement.

## Included

- Application source, tests, frontend, configuration, and safe example deployment files.
- Architecture, model, data, governance, and local setup documentation.
- One standalone generated architecture diagram used by the application’s About page.
- Reproduction, quality-check, and safe configuration guidance.

## Deliberately excluded

Secrets, `.env` files, tokens, account identifiers, raw/interim/processed customer data, screenshots, reports/PDFs, presentation/video links, unredacted operational evidence, local logs, and internal project-management material are excluded. Configure a separate AWS account and use the example configuration files for any deployment.

## Boundaries

The AWS environment documented here is a controlled grading/demo deployment. It is not a production certification, rollback drill, durable monitoring platform, or encrypted-at-rest-storage claim. Hosted-provider comparisons remain optional and are not evidence of the deterministic, retrieval-grounded control.

For setup, begin with [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md). For technical context, see [ARCHITECTURE.md](ARCHITECTURE.md), [MODEL_CARD.md](MODEL_CARD.md), [DATA_CARD.md](DATA_CARD.md), and [deploy/aws/README.md](deploy/aws/README.md). The visible course-layout guides are [`docker/`](docker/), [`data/`](data/), [`artifacts/`](artifacts/), [`notebooks/`](notebooks/), and [`reports/`](reports/).
