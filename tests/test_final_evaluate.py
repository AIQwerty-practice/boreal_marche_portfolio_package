from pathlib import Path

import pytest

from boreal_marche.modeling.final_evaluate import evaluate_protected_test


def test_protected_test_requires_explicit_confirmation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="confirm-protected-test"):
        evaluate_protected_test(tmp_path, confirmed=False)
