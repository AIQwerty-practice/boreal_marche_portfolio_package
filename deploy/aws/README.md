# Boreal Marche — AWS Canada Central deployment

Author: Barbara Plascencia

Target: one production-like capstone demonstration instance in AWS `ca-central-1`

This folder is the version-controlled deployment package. The repository is cloned to
`/opt/boreal-marche` on the server. Approved model artifacts and credentials are transferred or
created separately and are never committed to GitHub.

## What this package runs

- `api`: the typed FastAPI service for Heads A, B, and C, available only on server localhost at
  `127.0.0.1:8000` unless the HTTPS overlay is enabled.
- `ollama`: a private Docker-network service. Port `11434` is not published to the internet.
- `provider-evaluation`: a one-time job for the frozen golden and adversarial Head C comparison.
- `proxy`: optional Caddy HTTPS entry point, enabled only after the real subdomain is ready.

The application does not train models during prediction. It loads the approved artifacts from
`/opt/boreal-marche/artifacts`.

## Required private runtime files

Place these files in `/opt/boreal-marche/artifacts` after cloning the repository:

1. `retention_model.joblib`
2. `retention_model_meta.json`
3. `recommendation_rules.json`

Also place `transactions_clean.parquet` in `/opt/boreal-marche/data/processed`. The API reads only
its stock-code and description columns to construct the product lookup catalog. Its local size is
approximately 6.2 MiB, so transferring it is acceptable for the 20 GiB server.

Do not upload the raw UCI dataset, the SSH private key, `.env`, MLflow database, or private working records.

## 1. AWS and security prerequisites

- Region is `ca-central-1` (Canada Central).
- The selected EC2 host has 2 vCPU, 8 GiB RAM, a 20 GiB **unencrypted** root EBS volume, and Ubuntu. Storage encryption is a documented Sprint 1 exception, not a completed control; see `reports/d4/README.md`.
  This is an unverified capacity target for the D4 Ollama test, not a guarantee that
  Qwen3 4B will load alongside the API. Check free memory and disk before pulling;
  do not resize the instance or storage without a cost review.
- The Elastic IP is associated with this instance.
- SSH port `22` is restricted to Barbara's current public IP.
- Do not add inbound rules for `8000` or `11434`.
- Add inbound TCP `80` and `443` from the internet only when enabling the public HTTPS proxy.
- Confirm the budget alarm and intended experiment time limit before downloading an Ollama model.

## 2. Create the server checkout

Run on the EC2 instance:

```bash
sudo mkdir -p /opt/boreal-marche
sudo chown ubuntu:ubuntu /opt/boreal-marche
git clone https://github.com/AIQwerty-practice/boreal-marche-customer-intelligence.git /opt/boreal-marche
cd /opt/boreal-marche
mkdir -p artifacts data/processed reports/d3/provider_comparison
```

For later updates, use `git pull --ff-only` from `/opt/boreal-marche` after confirming that no
server-only file has accidentally been placed under source control.

## 3. Generate, verify, and transfer the approved runtime files

The runtime files are generated on an authorized development workstation from the versioned source,
configuration, and verified UCI dataset. The executed notebook is a readable evidence record with
embedded outputs; it is not the production artifact-build mechanism.

From the root of a fresh local repository clone, create an isolated Python 3.11 or 3.12 environment
and run the deterministic pipeline stages:

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell instead uses:
# .\.venv\Scripts\Activate.ps1

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

Ingestion downloads the source only when absent, verifies the recorded checksum, and writes the
provenance manifest. Cleaning produces `data/processed/transactions_clean.parquet`; feature
generation creates the point-in-time snapshots; tuning creates the calibrated retention pipeline and
metadata sidecar; recommendation mining creates the indexed static rules. The balancing command
produces controlled comparison evidence and does not silently replace the approved artifact.

Do not rerun `boreal_marche.modeling.final_evaluate` as part of reproduction. The protected test was
evaluated once after all choices were frozen; its existing report is immutable evaluation evidence.

Before transfer, require these generated files:

```bash
python -c "from pathlib import Path; required=[Path('artifacts/retention_model.joblib'),Path('artifacts/retention_model_meta.json'),Path('artifacts/recommendation_rules.json'),Path('data/processed/transactions_clean.parquet')]; missing=[str(p) for p in required if not p.is_file()]; print('runtime files ready' if not missing else f'missing: {missing}'); raise SystemExit(bool(missing))"
```

Transfer them from the authorized workstation using its own SSH key and the deployment hostname or
Elastic IP. For example, in Windows PowerShell from the repository root:

```powershell
$KeyPath = "<PATH_TO_EC2_PRIVATE_KEY>"
$Server = "ubuntu@<ELASTIC_IP_OR_HOSTNAME>"

scp -i $KeyPath `
  ".\artifacts\retention_model.joblib" `
  ".\artifacts\retention_model_meta.json" `
  ".\artifacts\recommendation_rules.json" `
  "${Server}:/opt/boreal-marche/artifacts/"

scp -i $KeyPath `
  ".\data\processed\transactions_clean.parquet" `
  "${Server}:/opt/boreal-marche/data/processed/"
```

Never copy an EC2 private key into the repository or onto the EC2 instance. Then verify filenames,
permissions, and checksums on the server without displaying file contents:

```bash
cd /opt/boreal-marche
ls -lh artifacts
ls -lh data/processed/transactions_clean.parquet
chmod 644 artifacts/retention_model.joblib artifacts/retention_model_meta.json artifacts/recommendation_rules.json
chmod 644 data/processed/transactions_clean.parquet
sha256sum artifacts/retention_model.joblib artifacts/retention_model_meta.json \
  artifacts/recommendation_rules.json data/processed/transactions_clean.parquet
```

Compare those SHA-256 values with hashes calculated on the authorized workstation. A mismatch stops
deployment; do not start the API with unverified files.

## 4. Create protected runtime configuration

Run on the server:

```bash
cd /opt/boreal-marche/deploy/aws
cp .env.example .env
chmod 600 .env
token="$(openssl rand -hex 32)"
sed -i "s/^BOREAL_API_TOKEN=.*/BOREAL_API_TOKEN=${token}/" .env
unset token
```

For the restricted staff demonstration, set `BOREAL_DEMO_STAFF_USERNAME=staff-demo` and a unique,
privately generated `BOREAL_DEMO_STAFF_PASSWORD` in this server-only `.env`. Give the credentials
only to authorized demonstrators through an approved password manager or equivalent secure channel.
The Head C staff form uses these credentials to obtain a 30-minute HTTP-only session cookie; it
does not ask staff to enter `BOREAL_API_TOKEN`. The latter remains a separate server-to-server
credential for protected tool routes. This demo sign-in is not employee identity management: do
not publicly expose staff functionality until company SSO, roles, and audit controls replace it.

Edit only the remaining placeholders required for the current step. Never print, photograph, or
commit the completed `.env` file. Confirm that Git ignores it with:

```bash
git check-ignore -v deploy/aws/.env
```

## 5. Build and start the private services

From `/opt/boreal-marche/deploy/aws`:

```bash
docker compose config --quiet
docker compose build api
docker compose up -d api ollama
docker compose ps
bash smoke_test.sh
```

The expected results are HTTP 200 responses from `/health`, `/ready`, and `/version`, with all three
heads ready.

Useful operational checks:

```bash
docker compose logs --tail=100 api
docker compose logs --tail=100 ollama
docker stats --no-stream
df -h /
```

Do not include secrets, customer identifiers, or raw provider responses in screenshots.

## 6. Pull one Ollama model and run the comparison

Set `OLLAMA_MODEL=qwen3:4b` in the private `deploy/aws/.env`. This is the
Q4_K_M model used for the earlier D3 comparison. On the instance, verify the
budget alarm, intended test window, and `free -h` / `df -h /` before pulling.
Ollama stays on the private Docker network; do not publish port `11434`.
Run one bounded fictional smoke check before the 54-case comparison:

```bash
cd /opt/boreal-marche/deploy/aws
docker compose exec ollama ollama pull "$(sed -n 's/^OLLAMA_MODEL=//p' .env)"
docker compose exec ollama ollama list
docker compose exec api python scripts/smoke_ollama.py --timeout 300
docker stats --no-stream
df -h /
```

The smoke check prints only model, routing decision, token counts, and latency;
it never prints a raw answer or secret. Success requires exit code 0,
`ready: true`, `intent: policy_search`, and `refused: false`. If it times out,
fails JSON validation, or exhausts memory, keep the Ollama selector disabled,
capture sanitized logs, and stop the services. The 8 GiB Windows Docker test
timed out at both 120 and 300 seconds during model loading; AWS/Linux may differ,
but this is a real capacity warning, not evidence of a successful local run.
Only after the smoke check succeeds and resource/cost use is acceptable, run:

```bash
docker compose --profile evaluation run --rm provider-evaluation
```

The evaluation writes aggregate and case-level files to
`reports/d3/provider_comparison`. Review the output for secrets before transferring it back to the
local project. The frozen golden and adversarial case files must not be edited during comparison.

The hosted provider is optional until its endpoint, model, and key are entered in `.env`. If those
fields are blank, the harness evaluates only Ollama. Run `--dry-run` inside the API image to confirm
configuration without making an external call:

```bash
docker compose run --rm api python scripts/compare_assistant_providers.py --root /app --dry-run
```

## 7. Enable the real subdomain and HTTPS later

Do this only after the DNS `A` record for the chosen Boreal subdomain points to the instance Elastic
IP and inbound ports `80` and `443` are approved. Set the real `BOREAL_DOMAIN` in `.env`, then run:

```bash
docker compose -f compose.yaml -f compose.public.yaml up -d
docker compose -f compose.yaml -f compose.public.yaml ps
curl -fsS "https://${BOREAL_DOMAIN}/health"
```

Caddy obtains and renews TLS certificates. Keep ports `8000` and `11434` closed in the AWS security
group; public traffic reaches the API only through the proxy.

## 8. D4 GitHub OIDC deployment

The `deploy-d4.yml` workflow builds the API and same-origin frontend, pushes an immutable
`GITHUB_SHA` tag to Amazon ECR, and invokes the EC2 deployment through AWS Systems Manager. GitHub
stores no long-lived AWS access key. Configure the `d4-demo` GitHub environment with repository or
environment variables—not secrets printed in workflow logs:

- `AWS_REGION` (expected `ca-central-1`)
- `AWS_ROLE_ARN` for the narrowly scoped GitHub OIDC role
- `ECR_REPOSITORY`
- `EC2_INSTANCE_ID`
- optional `PUBLIC_BASE_URL` for the post-deploy HTTPS smoke test

The GitHub role should be restricted to pushing the one approved ECR repository and sending the
approved Systems Manager command to the one demonstration instance. The EC2 instance profile needs
read access to that ECR repository, Systems Manager permissions, and no GitHub credential.

The deployment overlay is `compose.deploy.yaml`. On the server, `deploy_ssm.sh` checks out the exact
commit, pulls its SHA-tagged image, starts only the API without rebuilding, runs health/readiness/
version smoke tests, and prints the image digest and size for evidence. A deployment is successful
only when the workflow, SSM command, and smoke tests all pass.

### Rollback

Choose a previously verified commit whose ECR image still exists, then execute `rollback_ssm.sh`
through Systems Manager with `ROLLBACK_COMMIT`, `BOREAL_ECR_IMAGE`, and `AWS_REGION`. Rollback uses
the same immutable-image and smoke-test path; never rebuild an old source tree under an existing tag.

### D4 security and cost controls

- Keep EC2 application and Ollama ports private; expose only Caddy on `80/443` when required.
- Use IMDSv2, Systems Manager instead of public SSH where feasible, and a least-privilege instance
  profile. The selected root EBS volume is unencrypted. AWS requires snapshot-copy migration to an
  encrypted replacement volume; this was deferred during Sprint 1 due to Free Tier storage
  constraints. Do not claim encryption at rest or production readiness for this demonstration host.
  Keep real customer data and production credentials off its root volume; use only approved fictional
  data and controlled, short-lived demo credentials. Reassess capacity and cost before
  migrating or using the host for a deployment that requires encryption.
- Keep model artifacts, processed data, `.env`, AWS identifiers, and tokens outside Git.
- Retain CSP and the additional response headers in `Caddyfile`; do not add permissive CORS.
- Configure an AWS Budget and billing alert before deployment; record EC2, EBS, Elastic IP, ECR,
  CloudWatch, and data-transfer costs at the end-of-month review.
- Stop the instance when the live demonstration is not needed. Stopped instances can still incur
  EBS and Elastic IP charges; deleting containers alone does not stop EC2 billing.

## 9. Evidence for D4

Retain redacted evidence of:

- AWS region, instance specification, operating system, storage, and timestamp;
- security-group rules showing that `11434` and `8000` are not public;
- Docker and Compose versions plus service health;
- exact application image digest, Ollama image, and model name/version;
- application, API docs, normal dashboard, shifted traffic, and active alert screenshots;
- the 54-case aggregate quality, failure, and latency results;
- green CI/CD run, OIDC role session, deployed commit, image tag, digest, and size;
- runtime, memory, disk use, and estimated cost;
- authenticated internal tool-call success and rejection of a bad token;
- shutdown state and a final billing check.

## 10. Stop, restart, update, and remove

```bash
# Stop containers while preserving the Ollama model volume
docker compose stop

# Restart
docker compose up -d api ollama

# Update application source and rebuild
git pull --ff-only
docker compose build api
docker compose up -d api

# Remove containers but preserve named volumes
docker compose down
```

Do not use `docker compose down -v` unless the Ollama model volume is intentionally being deleted.
Stopping Docker does not stop EC2 billing. Stop the EC2 instance in AWS after evidence collection if
the demonstration does not need to remain online, and confirm the Elastic IP and storage charges.

## Head C provider selection (restricted demonstration)

The customer assistant offers four **question-routing** choices: the local keyword baseline,
OpenAI, Hugging Face Inference Providers, and Ollama. The selected LLM returns a strict intent/refusal decision; the local approved
catalog and policy tools still produce the displayed answer and citations. The staff-only retention
assistant remains on its separate authenticated baseline and never sends its internal policy to a
hosted provider. This is not a free-form LLM answer generator or a live-stock service.

All LLM choices require a separate `BOREAL_LLM_ACCESS_TOKEN` in the private `.env`; a browser user
enters that demo token for each session. It is **not** the OpenAI API key or the internal staff token.
OpenAI additionally requires `BOREAL_ENABLE_OPENAI=1`, `OPENAI_API_KEY`, and a deliberately chosen
`OPENAI_MODEL` compatible with the chat-completions JSON response contract. Ollama requires a
reachable private service and an installed `OLLAMA_MODEL`. The UI disables unconfigured choices.
Hugging Face requires `BOREAL_ENABLE_HUGGINGFACE=1`, `HF_TOKEN` with Inference Providers
permission, and an exact `HF_MODEL` that supports chat completions and JSON output. Validate
that model/provider pairing with fictional cases before enabling it for a demonstration. Its
token is distinct from an OpenAI API key; possessing one does not configure OpenAI or Ollama.
Never put provider secrets in the repository, frontend, screenshots, or client handoff package.
The `.env` approach is for the controlled course demo; use a secret manager, proper identity,
rate limits, a spending cap, and data-residency review before any public deployment.

Hosted OpenAI and Hugging Face selection require the user to confirm that the question has no personal/customer data;
the API also rejects obvious identifiers. This is a safeguard, **not** a guarantee that arbitrary
text has been fully de-identified. Do not use actual customer questions or transaction records in
the hosted comparison. The provider evaluation uses the frozen fictional 54-case suite:

```bash
python scripts/compare_assistant_providers.py --provider openai --dry-run
python scripts/compare_assistant_providers.py --provider openai
```

Run the second command only after checking the selected model, API budget, key scope, and approved
data policy. It makes 54 external requests and writes case-level metrics without raw model text.
Until this run is recorded, OpenAI comparison metrics remain pending. Baseline and prior Ollama
results must not be presented as proof of a completed three-way live comparison.

## Troubleshooting

- **API is unhealthy:** confirm the three artifact filenames and processed transaction parquet exist,
  then inspect only the last 100 API log lines.
- **Ollama is slow or exits:** inspect memory and disk; use one approved small quantized model and
  remove unused models.
- **HTTPS does not start:** verify the DNS record resolves to the Elastic IP and ports `80/443` are
  open; do not expose `8000` as a workaround.
- **Evaluation says no provider is configured:** check the variable names in `.env` without printing
  their values, then run the dry-run command.
- **Disk pressure:** inspect `docker system df` and `df -h /`; remove only confirmed unused images or
  models, never project evidence.
