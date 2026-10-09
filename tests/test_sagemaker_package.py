import importlib.util
import json
from pathlib import Path


def load_launcher():
    path = Path(__file__).parents[1] / "deploy" / "sagemaker" / "launch_hpo.py"
    spec = importlib.util.spec_from_file_location("sagemaker_launcher", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def valid_config():
    return {
        "region": "ca-central-1", "bucket": "example", "role_arn": "arn:aws:iam::1:role/x",
        "input_key": "d3/input/customer_snapshots.parquet", "output_prefix": "d3/output",
        "code_prefix": "d3/source", "instance_type": "ml.m5.large",
        "framework_version": "1.2-1", "python_version": "py3", "max_jobs": 8,
        "max_parallel_jobs": 2, "max_run_seconds": 900, "max_wait_seconds": 1200,
        "random_seed": 42, "base_job_name": "boreal-d3-rf-hpo", "managed_spot": True,
    }


def test_dry_run_plan_makes_no_external_call(tmp_path):
    module = load_launcher()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(valid_config()), encoding="utf-8")
    config = module.load_and_validate(path)
    result = module.plan(config)
    assert result["max_jobs"] == 8
    assert result["input_uri"].endswith("/d3/input/customer_snapshots.parquet")
    assert result["protected_test_uploaded_or_used"] is False


def test_safety_caps_are_enforced(tmp_path):
    module = load_launcher()
    config = valid_config()
    config["max_jobs"] = 13
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    try:
        module.load_and_validate(path)
    except ValueError as error:
        assert "safety cap" in str(error)
    else:
        raise AssertionError("Expected max_jobs safety cap to reject the configuration")


def test_training_dependencies_match_managed_container():
    requirements = (
        Path(__file__).parents[1] / "deploy" / "sagemaker" / "requirements.txt"
    ).read_text(encoding="utf-8")
    assert "pandas==1.1.3" in requirements
    assert "python-dateutil==2.8.1" in requirements
    assert "pyarrow==14.0.1" in requirements
    assert "scikit-learn==1.2.1" in requirements
    assert ">=" not in "\n".join(
        line for line in requirements.splitlines() if line and not line.startswith("#")
    )
