from __future__ import annotations

import json

import pytest

from paper_trading.conformance import VECTOR_DIR, validate_all, validate_vector
from paper_trading.contracts import ContractError


def test_required_deployment_vectors_run_without_darwin() -> None:
    assert validate_all() >= 1


def test_vector_is_bound_to_immutable_bundle(tmp_path) -> None:
    source = next(VECTOR_DIR.glob("*.json"))
    vector = json.loads(source.read_text(encoding="utf-8"))
    vector["bundle_hash"] = "0" * 64
    changed = tmp_path / source.name
    changed.write_text(json.dumps(vector), encoding="utf-8")
    with pytest.raises(ContractError, match="different deployment bundle"):
        validate_vector(changed)
