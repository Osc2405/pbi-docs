"""Tests for format auto-detection in cli.py."""

import pytest
from pathlib import Path

from pbi_extractor.cli import detect_input_format, _get_model_name

FIXTURES = Path(__file__).parent / "fixtures"
SM_DIR = FIXTURES / "minimal_pbip" / "my-model.SemanticModel"
PROJECT_DIR = FIXTURES / "minimal_pbip"
PBIP_FILE = FIXTURES / "minimal_pbip" / "my-model.pbip"


# ---------------------------------------------------------------------------
# detect_input_format
# ---------------------------------------------------------------------------

def test_detect_pbit_by_extension(tmp_path):
    f = tmp_path / "model.pbit"
    f.write_text("", encoding="utf-8")
    assert detect_input_format(str(f)) == "pbit"


def test_detect_pbip_by_extension():
    assert detect_input_format(str(PBIP_FILE)) == "pbip"


def test_detect_pbip_sm_folder_directly():
    assert detect_input_format(str(SM_DIR)) == "pbip"


def test_detect_pbip_by_project_folder():
    assert detect_input_format(str(PROJECT_DIR)) == "pbip"


def test_detect_error_unknown_extension(tmp_path):
    f = tmp_path / "model.xlsx"
    f.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Cannot determine format"):
        detect_input_format(str(f))


def test_detect_error_empty_folder(tmp_path):
    with pytest.raises(ValueError, match="Cannot determine format"):
        detect_input_format(str(tmp_path))


def test_detect_error_nonexistent_path(tmp_path):
    with pytest.raises(ValueError, match="Cannot determine format"):
        detect_input_format(str(tmp_path / "ghost.pbit"))


# ---------------------------------------------------------------------------
# _get_model_name
# ---------------------------------------------------------------------------

def test_model_name_pbit(tmp_path):
    f = tmp_path / "my-report.pbit"
    f.write_text("", encoding="utf-8")
    assert _get_model_name(f, "pbit") == "my-report.pbit"


def test_model_name_pbip_sm_folder():
    assert _get_model_name(SM_DIR, "pbip") == "my-model"


def test_model_name_pbip_file():
    assert _get_model_name(PBIP_FILE, "pbip") == "my-model"


def test_model_name_pbip_project_folder():
    assert _get_model_name(PROJECT_DIR, "pbip") == "my-model"
