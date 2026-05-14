import os

import pandas as pd
import pytest

from tools import io_utils


def test_read_csv_safely_returns_dataframe(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    df = io_utils.read_csv_safely(str(p))
    assert df.shape == (2, 2)


def test_read_csv_safely_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        io_utils.read_csv_safely(str(tmp_path / "no.csv"))


def test_read_csv_safely_empty_rejected(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("a,b\n", encoding="utf-8")
    with pytest.raises(ValueError):
        io_utils.read_csv_safely(str(p))


def test_read_csv_safely_scan_pii_blocks_email(tmp_path):
    p = tmp_path / "leaky.csv"
    p.write_text("id,email\n1,user@example.com\n", encoding="utf-8")
    with pytest.raises(PermissionError):
        io_utils.read_csv_safely(str(p), scan_pii=True)


def test_read_csv_safely_scan_pii_blocks_rrn(tmp_path):
    p = tmp_path / "rrn.csv"
    p.write_text("id,note\n1,주민번호 901231-1234567\n", encoding="utf-8")
    with pytest.raises(PermissionError):
        io_utils.read_csv_safely(str(p), scan_pii=True)


def test_read_csv_safely_scan_pii_disabled_returns_df(tmp_path):
    p = tmp_path / "leaky.csv"
    p.write_text("id,email\n1,user@example.com\n", encoding="utf-8")
    df = io_utils.read_csv_safely(str(p), scan_pii=False)
    assert df.shape[0] == 1


def test_read_csv_safely_scan_pii_clean_passes(tmp_path):
    p = tmp_path / "clean.csv"
    p.write_text("id,score\n1,820\n2,710\n", encoding="utf-8")
    df = io_utils.read_csv_safely(str(p), scan_pii=True)
    assert df.shape[0] == 2
