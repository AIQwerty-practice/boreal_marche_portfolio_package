# Data boundary and reproduction

Only safe metadata and manifests are committed. Raw transaction data, customer-level intermediate files, and generated feature tables are excluded from Git because they are source-controlled locally and may contain sensitive customer-level information.

To create a local development dataset after cloning, follow [`../docs/LOCAL_SETUP.md`](../docs/LOCAL_SETUP.md) and run the documented ingestion command. The source, licence, transformations, limitations, and field definitions are described in [`../DATA_CARD.md`](../DATA_CARD.md).

This repository does not use DVC. Reproducibility is provided through the documented public-source ingestion process, pinned application dependencies, manifests, and automated tests.
