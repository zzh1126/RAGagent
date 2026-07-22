import pytest

from scripts.run_evaluation import ensure_split_runnable


def test_final_evaluation_is_not_runnable() -> None:
    with pytest.raises(SystemExit, match="frozen final"):
        ensure_split_runnable("final")


def test_extension_evaluation_is_locked() -> None:
    with pytest.raises(SystemExit, match="locked extension"):
        ensure_split_runnable("extension")


def test_development_split_remains_runnable() -> None:
    assert ensure_split_runnable("dev") is None
