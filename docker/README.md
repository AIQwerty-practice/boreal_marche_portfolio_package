# Docker and Compose layout

The canonical Dockerfile and Compose stack are maintained in [`../deploy/aws/`](../deploy/aws/), rather than duplicated here. That directory contains the API `Dockerfile`, the local/default Compose file, the public deployment Compose file, and the AWS deployment Compose file.

Keeping a single canonical copy prevents the deployment definition from drifting. Use [`../deploy/aws/README.md`](../deploy/aws/README.md) for the exact commands and environment-file requirements.
