# Generated model artifacts

This folder is created locally by the documented training and preparation workflow. It is intentionally excluded from Git: it can contain serialized models, derived rules, retrieval indexes, MLflow state, and other generated outputs.

Expected development outputs include the retention model and metadata, recommendation rules, and retrieval/index metadata. Do not copy artifacts from another environment unless their source data, package versions, and metadata have been reviewed. Use the clean-clone instructions in [`../docs/LOCAL_SETUP.md`](../docs/LOCAL_SETUP.md) to recreate a local development runtime.
