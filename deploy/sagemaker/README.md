# D3 SageMaker HPO package

This package runs a bounded, reproducible Random Forest hyperparameter tuning comparison for D3. The protected test snapshot is excluded before upload and is never available to the tuning job.

## Layout

- `train.py` - one SageMaker trial using the same two expanding temporal folds as local tuning.
- `prepare_input.py` - creates and verifies a development-only parquet before upload.
- `launch_hpo.py` - validates configuration, prints a dry-run plan, and launches only with `--launch`.
- `collect_results.py` - exports trial parameters, PR-AUC, elapsed time, and billable seconds.
- `benchmark_local.py` - replays the completed SageMaker trial configurations locally.
- `summarize_comparison.py` - creates sanitized JSON/Markdown metric and runtime evidence from the managed and local results.
- `config.example.json` - safe public template.
- `config.local.json` - ignored account-specific configuration.
- `requirements.txt` - packages installed in the managed training container.
- `iam/` - account-neutral least-privilege policy templates for the execution role and launcher identity.

## Safety contract

- Region is fixed to `ca-central-1`.
- The input must be under `s3://<bucket>/d3/input/` and output under `d3/output/`.
- Maximum jobs, parallel jobs, runtime, and Spot wait are configuration-bounded.
- Dry-run is the default. A paid job requires the explicit `--launch` flag.
- The uploaded parquet contains only `train` and `validation` rows.
- The training entry point also rejects any file containing a `test` row as defense in depth.
- Trial outputs contain metrics and parameters, not customer-level predictions.

## Preparation

### Required AWS resources

Create all resources in `ca-central-1`:

1. A private S3 bucket with Block Public Access enabled and default encryption enabled.
2. Prefixes `d3/input/`, `d3/source/`, and `d3/output/` in that bucket.
3. `BorealMarcheSageMakerExecutionRole`, trusted by `sagemaker.amazonaws.com`, with `iam/trust-policy.json` and `iam/execution-policy.json` after replacing `YOUR_PRIVATE_BUCKET` and `YOUR_AWS_ACCOUNT_ID`.
4. A human/automation launcher identity with `iam/launcher-policy.json`, again replacing the placeholders. Do not create access keys for the AWS root user. Prefer temporary/federated credentials; if a temporary IAM access key is used for a short experiment, delete it after evidence collection.

The execution role is assumed by SageMaker training containers. The launcher identity creates, describes, and stops the bounded tuning job and may pass only the named execution role to SageMaker. These are separate permission boundaries.

### Configuration fields

Copy `config.example.json` to ignored `config.local.json` and set only account-specific values there.

| Field | Required value or rule |
|---|---|
| `region` | `ca-central-1` |
| `bucket` | Private bucket name only; do not include `s3://` |
| `role_arn` | ARN of `BorealMarcheSageMakerExecutionRole` |
| `input_key` | `d3/input/customer_snapshots_development.parquet` |
| `output_prefix` | `d3/output` |
| `code_prefix` | `d3/source` |
| `instance_type` | `ml.m5.large` for the recorded comparison |
| `framework_version` | `1.2-1` |
| `python_version` | `py3` |
| `max_jobs` | 8 or fewer; use 1 for a canary |
| `max_parallel_jobs` | 2 or fewer; use 1 for a canary |
| `max_run_seconds` | 900 or fewer per trial |
| `max_wait_seconds` | 1200 or fewer and greater than `max_run_seconds` for Spot |
| `managed_spot` | `true` for the recorded comparison |

The dependency pins in `requirements.txt` intentionally match the SageMaker SKLearn `1.2-1` container. Do not broaden them without a new managed-container canary; incompatible Pandas/NumPy upgrades can fail every trial before training begins.

### Local launcher authentication

Use a named AWS CLI profile rather than relying on an unknown default profile:

```powershell
aws sts get-caller-identity --profile <PROFILE>
$env:AWS_PROFILE = "<PROFILE>"
```

The returned ARN must identify the intended launcher identity. Never paste credentials, `.env` content, access-key CSV files, or profile files into logs or issues.

Create a launcher environment without changing the project runtime:

```powershell
py -3.12 -m venv .sagemaker-venv
.\.sagemaker-venv\Scripts\python.exe -m pip install "sagemaker>=2.245,<3" "boto3>=1.35,<2"
```

Copy the safe template to the ignored local configuration and insert the real role ARN and bucket:

```powershell
Copy-Item deploy\sagemaker\config.example.json deploy\sagemaker\config.local.json
```

Create the development-only upload and its evidence manifest:

```powershell
.\.venv\Scripts\python.exe deploy\sagemaker\prepare_input.py `
  --source data\processed\customer_snapshots.parquet `
  --output data\processed\customer_snapshots_development.parquet `
  --manifest reports\d3\sagemaker\input_manifest.json
```

Upload `customer_snapshots_development.parquet` to the `d3/input/` prefix. Do not upload the full snapshot parquet; it contains the protected test partition.

Validate without an AWS call:

```powershell
.\.sagemaker-venv\Scripts\python.exe deploy\sagemaker\launch_hpo.py --config deploy\sagemaker\config.local.json
```

The launcher will print `external_calls_made: false`. Do not use `--launch` until the cost plan and permissions have been reviewed.

### Preflight and one-trial canary

Verify access to the exact development-only object:

```powershell
aws s3api head-object `
  --bucket <PRIVATE_BUCKET> `
  --key d3/input/customer_snapshots_development.parquet `
  --region ca-central-1 `
  --profile <PROFILE>
```

Before the eight-trial job, copy the local configuration to an ignored canary configuration and set `max_jobs` and `max_parallel_jobs` to 1, use distinct `canary-output` and `canary-source` prefixes, and use a `boreal-d3-rf-canary` base name. Launch the canary once and continue only if it completes with a numeric `validation:pr_auc` objective. A completed container alone is insufficient if the objective metric is missing.

## Training quota check

The required Service Quotas entry is exactly:

```text
ml.m5.large for spot training job usage
```

In the AWS Console, open **Service Quotas → AWS services → Amazon SageMaker AI**, remain in `ca-central-1`, and search for that full name. Do not confuse it with cluster, endpoint, processing, warm-pool, `ml.m5.xlarge`, or non-Spot training quotas.

The applied quota must be at least `max_parallel_jobs`. If it is smaller:

1. Select the exact Spot training quota row.
2. Choose **Request increase at account level**.
3. Enter the requested total quota, not a delta. If AWS requires at least its displayed default of 4, request 4; do not add 4 to the current value.
4. Open **Quota request history** and wait for approval and the applied value to update.
5. If AWS creates a Support Center case, follow that linked case. If no case is created and the request remains blocked or denied, open AWS Support Center from the account menu and include the information listed below.

A quota allocation creates no compute charge. Training charges begin only after a job starts.

### Information for AWS Support

Provide:

- Service: Amazon SageMaker AI
- Region: `ca-central-1`
- Quota name: `ml.m5.large for spot training job usage`
- Desired total quota and required parallelism
- Exact `ResourceLimitExceeded` message and timestamp
- Account ID through the authenticated support form, not in the public repository
- Business justification: bounded educational HPO experiment with the documented job/runtime caps

Never provide an access key, secret key, session token, `.pem` file, customer data, or unredacted local configuration.

## Error identification and response

| Output signature | Meaning | Response |
|---|---|---|
| `IncompleteSignature` or `Invalid key=value pair` | AWS profile contains a malformed or swapped credential value | Re-enter the two CSV fields separately with `aws configure --profile <PROFILE>`; never display them |
| `Unable to locate credentials` | No usable profile/session | Configure approved federated or temporary launcher credentials, then verify with STS |
| `AccessDenied` mentioning `iam:PassRole` | Launcher cannot pass the execution role | Compare the launcher policy role ARN and `iam:PassedToService` condition; do not grant broad administrator access |
| `AccessDenied` for S3 | Wrong bucket/prefix or missing scoped S3 action | Verify `d3/*` policy resources and run the exact `head-object` preflight |
| `ResourceLimitExceeded` and `...spot training job usage is 0 Instances` | Applied Spot quota is below requested parallel instances | Request the exact Spot training quota as described above; do not repeatedly relaunch |
| `ExecuteUserScriptError: ExitCode 1` | Wrapper error from the managed container | Stop the parent HPO if trials are repeatedly failing, then inspect the first Python traceback in CloudWatch |
| `sagemaker-sklearn-container ... requires pandas==1.1.3` followed by NumPy import failure | Requirements replaced container-compatible compiled packages | Restore the committed exact pins, run local tests, then run one managed canary before full HPO |
| Completed training job but null objective metric | Metric regex did not match output | Confirm the log contains `validation:pr_auc=<number>` and keep the configured metric name/regex aligned |
| Spot capacity wait or retryable capacity error | Capacity is temporarily unavailable, not a code error | Allow the bounded `max_wait_seconds`; retry only after the current job reaches a terminal state |

When several trials fail with the same error, stop the parent tuning job once. A message saying it is already stopping or terminal confirms that no additional stop is needed. Never relaunch until the cause is fixed locally and a one-trial managed canary succeeds.

Useful status command:

```powershell
aws sagemaker describe-hyper-parameter-tuning-job `
  --hyper-parameter-tuning-job-name <JOB_NAME> `
  --region ca-central-1 `
  --profile <PROFILE> `
  --query "{Status:HyperParameterTuningJobStatus,Reason:FailureReason,Counters:TrainingJobStatusCounters,BestJob:BestTrainingJob.TrainingJobName,BestPR_AUC:BestTrainingJob.FinalHyperParameterTuningJobObjectiveMetric.Value}"
```

## Evidence collection

After the tuning job completes:

```powershell
.\.sagemaker-venv\Scripts\python.exe deploy\sagemaker\collect_results.py --job-name <JOB_NAME> --output reports\d3\sagemaker
.\.venv\Scripts\python.exe deploy\sagemaker\benchmark_local.py --trials reports\d3\sagemaker\hpo_trials.csv --data data\processed\customer_snapshots_development.parquet --output reports\d3\sagemaker\local_benchmark.csv
```

Record the AWS Billing/Cost Explorer value separately after it becomes available. Do not infer actual cost from storage size or instance list price.

Create the sanitized comparison artifacts:

```powershell
.\.venv\Scripts\python.exe deploy\sagemaker\summarize_comparison.py `
  --job-summary reports\d3\sagemaker\hpo_job_summary.json `
  --trials reports\d3\sagemaker\hpo_trials.csv `
  --local-benchmark reports\d3\sagemaker\local_benchmark.csv `
  --output-json reports\d3\sagemaker\comparison_summary.json `
  --output-markdown reports\d3\sagemaker\COMPARISON.md `
  --billing-checked-on 2026-09-14 `
  --successful-job-estimate-usd 0.0031
```

The generated comparison intentionally omits training-job ARNs, account IDs, bucket names, and source object paths. Treat the raw collected JSON/CSV as internal evidence unless it has been separately sanitized.

## Teardown

After results, billing evidence, and the final report are secured:

1. Delete the temporary launcher access key or end the federated session.
2. Remove temporary S3 training source, input, and output objects after their aggregate evidence and hashes are retained.
3. Delete the dedicated launcher identity, execution role, and experiment bucket if they serve no continuing deployment purpose.
4. Verify that no SageMaker training, tuning, endpoint, processing, notebook, or Studio compute remains active.

Keep sanitized aggregate CSV/JSON results, configuration templates, job names, region, timestamps, hashes, and the incident/canary summary. Do not keep credentials or customer-level data as evidence.
