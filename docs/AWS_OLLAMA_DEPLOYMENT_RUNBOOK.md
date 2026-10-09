# AWS Canada Central Ollama Deployment Runbook

Status: local preparation only. No AWS resource has been created by this runbook.

## Fixed deployment posture

- Region: `ca-central-1` (Canada Central).
- Account mode: trial; engineering posture: production-like.
- D7 uses the same regional deployment; no second region is planned.
- Ollama must not be installed on local development computer.
- Production-like does not mean certified production or proof of complete Law 25 compliance.
- Remaining promotional credit reported by the account owner: USD 130 of USD 200. The exact credit and Free Plan expiration dates must be confirmed in Billing before launch.
- Expected use: one demonstration user; 5–15 second assistant responses are acceptable for the initial CPU trial.
- Portfolio preference: serve the D7 portfolio homepage from the new Canada Central environment so it does not depend on the older project server. Long-term static hosting remains a later cost-optimization option.
- Existing separate project: a stopped `c7i-flex.large` in US East with 2 vCPU, 4 GiB RAM, 10 GiB EBS, and an Elastic IP. It is not reused for Boreal.
- DNS remains with IONOS/1&1. The portfolio, fraud project, and Boreal project can use independent DNS records and subdomains pointing to different AWS regions or addresses.

## Decisions required before launch

1. Confirm the Ollama model and its measured memory/storage requirements.
2. Validate availability and current Canada Central price for the proposed CPU instance before launch.
3. Set a maximum experiment duration and dollar ceiling below the USD 130 remaining credit.
4. Confirm the exact Boreal and portfolio hostnames without sharing registrar credentials.
5. Confirm the persistence plan for model files, logs, evaluation evidence, and the portfolio homepage.

## Initial capacity decision

- Architecture: one EC2 instance for FastAPI, the portfolio page, and Ollama during the trial/demo.
- Compute starting point: 8 GiB RAM minimum. Compare `m7i-flex.large` (2 vCPU) and `c7i-flex.xlarge` (4 vCPU) in `ca-central-1`; prefer the lower-cost option first and upgrade only if measured 54-case latency is unacceptable.
- Accelerator: CPU first; no GPU instance until evidence shows it is necessary and a separate cost ceiling is approved.
- Storage: 20 GiB encrypted `gp3`, assuming the existing fraud project retains its 10 GiB volume and the owner's EC2 storage allowance is 30 GiB total.
- Ten GiB is not approved for Boreal: the operating system, Python environment, application, Ollama runtime, quantized model, update headroom, and logs would leave insufficient safety margin.
- Keep only one small quantized model on disk at a time; remove unused package caches and temporary model downloads after evidence collection.

## Security boundary

- Do not expose Ollama port `11434` to `0.0.0.0/0` or `::/0`.
- Prefer application-to-Ollama traffic on localhost or private VPC addresses.
- Permit Ollama ingress only from the application security group when services are separate.
- Use AWS Systems Manager Session Manager for administration; avoid public SSH when feasible.
- Store tokens in an approved secret store or protected deployment environment, never Git or screenshots.
- Send fictional policy and synthetic identifiers only; do not send unnecessary customer information.
- Encrypt attached storage and application transport; terminate public TLS at the approved entry point.

## Production-like operational controls

- IAM role with least privilege and no long-lived AWS access key on the instance.
- Pinned application image and recorded Ollama/model versions.
- Health, readiness, version, latency, error, memory, disk, and request-volume monitoring.
- Budget alarm and runtime ceiling confirmed before model download.
- Structured logs with secrets and customer identifiers redacted.
- Rollback procedure and deterministic-baseline fallback.
- Stop/terminate checklist executed immediately after evidence collection unless D7 persistence is approved.

## Deployment sequence

1. Select `ca-central-1` explicitly and capture the region in evidence.
2. Create or select the VPC, subnet, security groups, instance role, and SSM access.
3. For a deployment that requires encryption at rest, launch an approved EC2 configuration with encrypted storage and identifying cost tags. The existing Sprint 1 demonstration instance has an unencrypted 20 GiB root EBS volume. Its snapshot-copy migration to an encrypted replacement volume was documented but not executed because of Free Tier storage constraints. Do not claim that this existing host satisfies the encrypted-storage control. Keep real customer data and production credentials off this host; use only approved fictional data and controlled, short-lived demo credentials.
4. Patch the operating system and install a pinned Ollama version.
5. Bind Ollama only to the approved private interface and pull the approved model.
6. Configure `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `OLLAMA_BEARER_TOKEN` outside Git.
7. Run health checks, then the 54-case provider comparison once under the declared conditions.
8. Capture aggregate quality, failure, latency, token, memory, runtime, and cost evidence.
9. Compare with the deterministic and hosted providers without changing the frozen case sets.
10. Stop or terminate resources and confirm billing/monitoring state.

## Required evidence

- AWS region and timestamp
- Instance family/type, CPU/GPU, memory, storage, and operating-system image
- Ollama and model names/versions
- Security-group rules demonstrating that `11434` is private
- SSM/IAM and secret-handling evidence without revealing secrets
- Start/end times and estimated AWS cost
- 54-case aggregate provider report and error breakdown
- Monitoring screenshots and logs with sensitive fields redacted
- Stop/termination evidence and final cost check

## Abort conditions

- Region is not `ca-central-1`.
- Budget alarm or dollar ceiling is absent.
- Port `11434` is publicly reachable.
- Required model does not fit the approved instance.
- Secrets appear in files, logs, screenshots, or command history.
- Evaluation would use a changed golden or adversarial set.
- Costs or runtime exceed the approved ceiling.
