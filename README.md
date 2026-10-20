# Boreal Marche Customer Intelligence — Deliverables and Reproducibility Package

This public, replication-oriented deliverables package presents the Boreal Marche capstone system: retention prediction, basket recommendations, and a grounded bilingual assistant. It is built from a reviewed committed baseline rather than a local working directory.

## Current status

The portfolio package is a public, reproducibility-oriented companion to the completed capstone. It contains the runnable implementation and supporting technical documentation; final evidence, appendices, presentation files, and the release manifest are maintained in the separate release package. It is not a certified production release.

### Deliverable legend

This repository is intended for a classmate to clone on a clean machine and reproduce the system using documented commands. Environment variables are listed in [`.env.example`](.env.example) and [`deploy/aws/.env.example`](deploy/aws/.env.example); no secret values are committed. The teacher coordinates the final reproducibility review with students.

“D#” in a file name or document refers to the corresponding project deliverable above; it is not a version number or a production-readiness level.

## Reproducibility standard

This repository is intended for a classmate to clone on a clean machine and reproduce the system using documented commands. Environment variables are listed in [`.env.example`](.env.example) and [`deploy/aws/.env.example`](deploy/aws/.env.example); no secret values are committed. The instructor coordinates the final clean-clone check as a grading activity; the canonical release is the main project repository’s `v1.0` release.

## For a teammate: reproduce the local app

Start with the step-by-step [clean-clone guide](docs/LOCAL_SETUP.md). It gives Windows, macOS, and Linux activation commands; rebuilds the local runtime from the public source data; explains the required local drift baseline; and ends with exact browser and API checks. It also clearly separates the normal reproduction path from optional Ollama and staff-demo features.

The ingestion process retrieves the documented source dataset when needed. Raw and generated customer-level data are intentionally not distributed in this repository. A local rebuild is development evidence: it does not recreate the protected final evaluation or authorize production use.

## Use your own trained retention model (local development only)

The same guide includes a controlled [custom-model path](docs/LOCAL_SETUP.md#optional-use-your-own-trained-retention-model). It explains the required model interface, artifact bundle, schema checks, and local drift-baseline rebuild. Do not replace the model in a hosted deployment or use customer data without an approved privacy, security, and governance review.

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
