from __future__ import annotations

import json
import re
from pathlib import Path

from boreal_marche.recommendation.recommend import recommend

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_assets_and_container_copy_are_present() -> None:
    for relative in ("frontend/index.html", "frontend/styles.css", "frontend/app.js", "frontend/ux.js"):
        assert (ROOT / relative).is_file()
    dockerfile = (ROOT / "deploy/aws/Dockerfile").read_text(encoding="utf-8")
    assert "COPY frontend ./frontend" in dockerfile
    dockerignore = (ROOT / "deploy/aws/Dockerfile.dockerignore").read_text(encoding="utf-8")
    assert "\nfrontend\n" not in f"\n{dockerignore}\n"
    interface = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    journey = (ROOT / "frontend/ux.js").read_text(encoding="utf-8")
    assert 'id="continue-to-basket"' in interface
    assert "Head B is a separate model" in journey
    assert 'const code = "15056BL"' in journey


def test_staff_ui_uses_demo_sign_in_instead_of_api_token_input() -> None:
    interface = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend/ux.js").read_text(encoding="utf-8")
    assert 'id="staff-username"' in interface
    assert 'id="staff-password"' in interface
    assert 'id="staff-token"' not in interface
    assert 'api("/internal/staff/login"' in frontend
    assert 'api("/internal/staff/logout"' in frontend
    assert 'Authorization:`Bearer ${$("#staff-token")' not in frontend


def test_customer_assistant_has_explicit_free_form_question_mode() -> None:
    interface = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend/ux.js").read_text(encoding="utf-8")
    assert 'id="question-mode-faq"' in interface
    assert 'id="question-mode-custom"' in interface
    assert 'id="faq-picker"' in interface
    assert 'id="question"' in interface
    assert '$("#assistant-task").value = "auto"' in frontend
    assert '$("#faq-picker").hidden = custom' in frontend


def test_retention_probability_is_separate_from_what_if_campaign_rule() -> None:
    interface = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend/ux.js").read_text(encoding="utf-8")
    assert 'id="apply-campaign-rule"' in interface
    assert 'id="campaign-threshold"' in interface
    assert 'min="0" max="100"' in interface
    assert 'value="40"' in interface
    assert "result.return_probability_90d<=threshold" in frontend
    assert 'const enabled=$("#apply-campaign-rule").checked' in frontend
    assert 'if (lastPrediction) renderPrediction(lastPrediction)' in frontend
    assert "result.campaign_eligible?" not in frontend


def test_retention_slider_minima_exclude_zero_purchase_profiles() -> None:
    interface = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend/ux.js").read_text(encoding="utf-8")
    assert 'id="frequency-slider" min="1" max="40"' in interface
    assert 'id="spend-slider" min="25" max="5000"' in interface
    assert 'id="products-slider" min="1" max="100"' in interface
    assert 'const spend = Math.max(25,Number(profile.monetary_total)||25)' in frontend


def test_guided_basket_fires_a_real_rule_and_frontend_persists_state() -> None:
    payload = json.loads((ROOT / "artifacts/recommendation_rules.json").read_text(encoding="utf-8"))
    result = recommend(["15056BL"], payload["rules_index"], payload["popularity"], k=5)

    assert result["source"] == "association_rules"
    rule_items = [item for item in result["recommendations"] if item["firing_rule"]]
    assert rule_items
    assert all(item["confidence"] > 0 and item["lift"] >= 1.10 for item in rule_items)

    frontend = (ROOT / "frontend/ux.js").read_text(encoding="utf-8")
    assert 'localStorage.getItem("boreal-basket")' in frontend
    assert 'localStorage.setItem("boreal-basket"' in frontend
    assert 'source === "empty_basket_popularity"' in frontend
    assert '"noMatchFallback"' in frontend


def test_container_uses_approved_model_runtime() -> None:
    dockerfile = (ROOT / "deploy/aws/Dockerfile").read_text(encoding="utf-8")
    assert '"scikit-learn==1.9.0"' in dockerfile
    assert "MPLCONFIGDIR=/tmp/matplotlib" in dockerfile


def test_d4_workflow_uses_oidc_and_immutable_sha_tag() -> None:
    workflow = (ROOT / ".github/workflows/deploy-d4.yml").read_text(encoding="utf-8")
    assert "id-token: write" in workflow
    assert "aws-actions/configure-aws-credentials@v5" in workflow
    assert "${GITHUB_SHA}" in workflow
    assert "aws ssm send-command" in workflow
    assert "aws_access_key_id" not in workflow.casefold()
    assert "aws_secret_access_key" not in workflow.casefold()


def test_public_d4_files_do_not_contain_private_aws_identifiers() -> None:
    checked = [
        ROOT / "frontend/index.html",
        ROOT / "frontend/app.js",
        ROOT / "deploy/aws/compose.deploy.yaml",
        ROOT / "deploy/aws/deploy_ssm.sh",
        ROOT / "deploy/aws/rollback_ssm.sh",
        ROOT / ".github/workflows/deploy-d4.yml",
        ROOT / "reports/d4/README.md",
    ]
    forbidden = ("AKIA", "ASIA")
    for path in checked:
        text = path.read_text(encoding="utf-8")
        assert not any(value in text for value in forbidden), path
        assert re.search(r"\b\d{12}\b", text) is None, path
