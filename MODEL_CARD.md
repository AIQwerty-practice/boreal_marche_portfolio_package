# Model Card

Status: D3 evaluation complete; deployment monitoring and later governance evidence remain in progress.

## Current retention model

- Intended use: prioritize customers for a retention campaign using pre-cutoff transaction history.
- Selected pipeline: tuned Random Forest with balanced class weights and sigmoid probability calibration.
- Feature source: four customer snapshots using a 365-day observation window and a separate 90-day return label.
- Selection data: expanding temporal training folds plus the 2011-06-01 validation snapshot.
- Validation PR-AUC: 0.7407; ROC-AUC: 0.7961; Brier score: 0.1676; recall at top decile: 0.2544.
- Screening baselines: business recency-rule PR-AUC 0.4790; dummy-prior PR-AUC 0.3675.
- Operating scenario: contact customers whose predicted return probability is at or below 0.400.
- Scenario assumptions: $30 gross margin per incremental purchase, $5 incentive cost per purchase, $1 contact cost, and 20% recovery of otherwise non-returning customers.
- Validation scenario output: estimated incremental profit 5,375.61 across 2,776 customers. This is not a causal treatment-effect estimate.
- Validation uncertainty: PR-AUC bootstrap 95% interval 0.7193-0.7610 and Brier interval 0.1617-0.1738 from 1,000 seeded resamples.
- Operational audit: country grouping, monetary-value thirds, and activity thirds. These are operational diagnostics, not demographic fairness evidence.
- Artifact: `artifacts/retention_model.joblib`; provenance and hashes are in `artifacts/retention_model_meta.json`.
- Artifact SHA-256: `5b3537f510d2e9221d76896fc9f22a4b835858c9df74d840b8c191682b98fe6e`.

## Managed training reproducibility check

Eight Bayesian SageMaker Spot trials and a matched local replay used identical Random Forest configurations on two development-only temporal folds. Both platforms selected the same best configuration. Best mean PR-AUC was 0.735864 on SageMaker and 0.735397 locally; mean absolute PR-AUC difference across all eight trials was 0.000221. The protected test partition was not uploaded or used. Managed wall time was 11.37 minutes versus 29.62 seconds locally, so local execution is the practical choice for this workload size. Actual AWS cost and a monetary crossover remain pending billing evidence.

## One-time protected test

The protected 10 September 2011 snapshot was opened once after the estimator, calibration, balancing strategy, feature contract, and threshold were frozen.

- Customers: 4,306; observed return rate: 50.72%.
- PR-AUC: 0.7994 (bootstrap 95% interval 0.7836-0.8139).
- ROC-AUC: 0.7702 (bootstrap 95% interval 0.7571-0.7834).
- Brier score: 0.2120 (bootstrap 95% interval 0.2052-0.2188).
- Recall at top decile: 0.1900.
- Mean predicted return: 37.00%; calibration gap: -13.72 percentage points.
- Frozen 0.400 rule selected 2,715 customers; scenario-estimated profit: 5,248.36.

No customer-level test predictions were persisted. No post-test model, calibration, balancing, or threshold selection is permitted.

## Serialization and security

The artifact contains preprocessing and the calibrated estimator together to reduce training-serving skew. joblib is convenient for scikit-learn and NumPy-heavy objects, but, like pickle, it is unsafe for untrusted input and can execute arbitrary code during loading. Production loading must require a controlled artifact source, SHA-256 verification, and compatible pinned dependencies.

## Limitations and out-of-scope uses

- Historical public retail data may not represent current Boreal Marche customers.
- Campaign response and recovery assumptions are hypothetical; the model does not estimate causal treatment effect.
- Test calibration deteriorated under temporal prevalence shift even though ranking remained useful.
- Demographic fairness cannot be assessed because the dataset lacks protected demographic attributes.
- Do not use the model for credit, employment, insurance, health, eligibility, or other high-impact decisions.
- Do not expose individual scores without authentication, authorization, notice, and an approved customer-to-feature data boundary.
- Do not load the serialized artifact from an untrusted location.

## Monitoring and retraining direction

Monitor input drift, score distribution, missingness, latency, campaign allocation, and delayed 90-day outcome quality. A retraining job should open a reviewed change rather than self-deploy. Recalibration requires a new governed validation/test cycle; the existing protected test cannot become tuning data.
