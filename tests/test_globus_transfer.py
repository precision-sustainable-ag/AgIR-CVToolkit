# tests/test_scinet_transfer_stage.py
"""
Unit tests for SciNetTransferStage.

Globus CLI calls are monkey-patched so no real credentials are needed.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from agir_cvtoolkit.pipelines.stages.scinet_transfer import (
    SciNetTransferStage,
    _build_batch_file,
    _extract_transfer_paths,
    _load_records,
    _resolve_destination,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RECORDS = [
    {
        "cutout_id": "NC_001",
        "image_path": "SemiF/2022/NC/NC_001.jpg",
        "mask_path":  "SemiF/2022/NC/NC_001_mask.png",
        "cropout_path": None,
    },
    {
        "cutout_id": "NC_002",
        "image_path": "SemiF/2022/NC/NC_002.jpg",
        "mask_path":  None,
        "cropout_path": "SemiF/2022/NC/cropouts/NC_002_crop.jpg",
    },
    # Duplicate image_path – should be deduplicated
    {
        "cutout_id": "NC_003",
        "image_path": "SemiF/2022/NC/NC_001.jpg",
        "mask_path":  "SemiF/2022/NC/NC_003_mask.png",
        "cropout_path": "",
    },
]

PATH_COLUMNS = ["image_path", "mask_path", "cropout_path"]
SRC_ROOT = "/LTS/project/dash_agir/"

DESTINATIONS = {
    "ceres": {
        "endpoint": "f45a24f8-09ba-11ec-b342-1feaf93e3729",
        "dst_root":  "/90daydata/dash_agir/tmp/",
    },
    "atlas": {
        "endpoint": "c8ce33a1-0ec3-4aaa-b93a-c8ce0b5f8ad7",
        "dst_root":  "/90daydata/dash_agir/tmp/",
    },
}


@pytest.fixture
def query_dir(tmp_path: Path) -> Path:
    q = tmp_path / "query"
    q.mkdir(parents=True)
    return q


@pytest.fixture
def cfg(tmp_path: Path) -> dict:
    return {
        "paths":   {"run_root": str(tmp_path)},
        "runtime": {"run_id": "test_run"},
        "globus": {
            "juno_endpoint": "904c2108-90cf-11e8-9672-0a6d4e044368",
            "src_root":      SRC_ROOT,
            "default_dst":   "ceres",
            "destinations":  DESTINATIONS,
            "transfer": {
                "sync_level":      "checksum",
                "label_prefix":    "agir-cv scinet-transfer",
                "wait":            False,
                "poll_interval_s": 10,
                "timeout_s":       300,
            },
            "path_columns": PATH_COLUMNS,
        },
    }


def _mock_run_globus(cmd_args, task_id="fake-task-id-1234", **kwargs):
    """Return a fake CompletedProcess for any globus CLI call."""
    if "session" in cmd_args:
        return subprocess.CompletedProcess(cmd_args, 0, stdout="[]", stderr="")
    if "transfer" in cmd_args:
        return subprocess.CompletedProcess(
            cmd_args, 0,
            stdout=json.dumps({"task_id": task_id, "message": "accepted"}),
            stderr="",
        )
    return subprocess.CompletedProcess(cmd_args, 0, stdout="{}", stderr="")


# ---------------------------------------------------------------------------
# _resolve_destination
# ---------------------------------------------------------------------------

def test_resolve_destination_ceres() -> None:
    ep, root = _resolve_destination({"destinations": DESTINATIONS}, "ceres")
    assert ep   == DESTINATIONS["ceres"]["endpoint"]
    assert root == DESTINATIONS["ceres"]["dst_root"]


def test_resolve_destination_atlas() -> None:
    ep, root = _resolve_destination({"destinations": DESTINATIONS}, "atlas")
    assert ep == DESTINATIONS["atlas"]["endpoint"]


def test_resolve_destination_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown destination 'juno'"):
        _resolve_destination({"destinations": DESTINATIONS}, "juno")


def test_resolve_destination_no_config_raises() -> None:
    with pytest.raises(ValueError, match="No destinations defined"):
        _resolve_destination({}, "ceres")


# ---------------------------------------------------------------------------
# _load_records
# ---------------------------------------------------------------------------

def test_load_records_json(query_dir: Path, tmp_path: Path) -> None:
    (query_dir / "query.json").write_text(json.dumps(RECORDS))
    assert len(_load_records(tmp_path)) == 3


def test_load_records_csv(query_dir: Path, tmp_path: Path) -> None:
    import pandas as pd
    pd.DataFrame(RECORDS).to_csv(query_dir / "query.csv", index=False)
    assert len(_load_records(tmp_path)) == 3


def test_load_records_missing(tmp_path: Path) -> None:
    (tmp_path / "query").mkdir()
    with pytest.raises(FileNotFoundError, match="No query results found"):
        _load_records(tmp_path)


# ---------------------------------------------------------------------------
# _extract_transfer_paths
# ---------------------------------------------------------------------------

def test_extract_deduplicates() -> None:
    pairs = _extract_transfer_paths(RECORDS, PATH_COLUMNS, SRC_ROOT)
    src_paths = [p for p, _ in pairs]
    assert src_paths.count(SRC_ROOT + "SemiF/2022/NC/NC_001.jpg") == 1


def test_extract_count() -> None:
    # NC_001.jpg(1) + NC_001_mask(1) + NC_002.jpg(1) + NC_002_crop(1) + NC_003_mask(1) = 5
    assert len(_extract_transfer_paths(RECORDS, PATH_COLUMNS, SRC_ROOT)) == 5


def test_extract_src_prefix() -> None:
    for src, _ in _extract_transfer_paths(RECORDS, PATH_COLUMNS, SRC_ROOT):
        assert src.startswith(SRC_ROOT)


def test_extract_empty_records() -> None:
    assert _extract_transfer_paths([], PATH_COLUMNS, SRC_ROOT) == []


def test_extract_skips_nan_values() -> None:
    nan_records = [
        {"image_path": float("nan"), "mask_path": None,           "cropout_path": "nan"},
        {"image_path": "SemiF/real.jpg", "mask_path": float("nan"), "cropout_path": None},
    ]
    pairs = _extract_transfer_paths(nan_records, PATH_COLUMNS, SRC_ROOT)
    assert len(pairs) == 1
    assert pairs[0][0].endswith("SemiF/real.jpg")


# ---------------------------------------------------------------------------
# _build_batch_file
# ---------------------------------------------------------------------------

def test_build_batch_file(tmp_path: Path) -> None:
    dst_root = DESTINATIONS["ceres"]["dst_root"]
    pairs    = _extract_transfer_paths(RECORDS, PATH_COLUMNS, SRC_ROOT)
    batch    = tmp_path / "batch.txt"
    _build_batch_file(pairs, dst_root, batch)

    lines = batch.read_text().splitlines()
    assert len(lines) == len(pairs)
    for line in lines:
        src, dst = line.split(" ", 1)
        assert src.startswith(SRC_ROOT)
        assert dst.startswith(dst_root)


# ---------------------------------------------------------------------------
# SciNetTransferStage.run  (globus CLI mocked)
# ---------------------------------------------------------------------------

def test_stage_defaults_to_ceres(cfg: dict, query_dir: Path, tmp_path: Path) -> None:
    (query_dir / "query.json").write_text(json.dumps(RECORDS))
    with patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._run_globus",
               side_effect=_mock_run_globus), \
         patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._require_globus_cli",
               return_value="/usr/bin/globus"):
        stage = SciNetTransferStage(cfg)   # no dst_name → uses default_dst
        assert stage.dst_name == "ceres"
        assert stage.dst_endpoint == DESTINATIONS["ceres"]["endpoint"]


def test_stage_atlas_destination(cfg: dict, query_dir: Path, tmp_path: Path) -> None:
    (query_dir / "query.json").write_text(json.dumps(RECORDS))
    with patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._run_globus",
               side_effect=_mock_run_globus), \
         patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._require_globus_cli",
               return_value="/usr/bin/globus"):
        stage = SciNetTransferStage(cfg, dst_name="atlas")
        assert stage.dst_endpoint == DESTINATIONS["atlas"]["endpoint"]
        task_id = stage.run()
    assert task_id == "fake-task-id-1234"


def test_stage_writes_manifest(cfg: dict, query_dir: Path, tmp_path: Path) -> None:
    (query_dir / "query.json").write_text(json.dumps(RECORDS))
    with patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._run_globus",
               side_effect=_mock_run_globus), \
         patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._require_globus_cli",
               return_value="/usr/bin/globus"):
        SciNetTransferStage(cfg).run()

    manifest = json.loads((tmp_path / "scinet_transfer_manifest.json").read_text())
    assert manifest["dst_name"]     == "ceres"
    assert manifest["dst_endpoint"] == DESTINATIONS["ceres"]["endpoint"]
    assert manifest["num_items"]    == 5


def test_stage_writes_batch_file(cfg: dict, query_dir: Path, tmp_path: Path) -> None:
    (query_dir / "query.json").write_text(json.dumps(RECORDS))
    with patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._run_globus",
               side_effect=_mock_run_globus), \
         patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._require_globus_cli",
               return_value="/usr/bin/globus"):
        SciNetTransferStage(cfg).run()

    assert len((tmp_path / "globus_batch.txt").read_text().splitlines()) == 5


def test_stage_empty_records_returns_none(cfg: dict, query_dir: Path) -> None:
    (query_dir / "query.json").write_text("[]")
    with patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._require_globus_cli",
               return_value="/usr/bin/globus"), \
         patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._run_globus",
               side_effect=_mock_run_globus):
        assert SciNetTransferStage(cfg).run() is None


def test_stage_raises_if_not_logged_in(cfg: dict, query_dir: Path) -> None:
    (query_dir / "query.json").write_text(json.dumps(RECORDS))

    def _fail_session(args, **kwargs):
        if "session" in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="Not logged in")
        return _mock_run_globus(args)

    with patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._require_globus_cli",
               return_value="/usr/bin/globus"), \
         patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._run_globus",
               side_effect=_fail_session):
        with pytest.raises(RuntimeError, match="Not logged into Globus"):
            SciNetTransferStage(cfg).run()


def test_stage_raises_on_unknown_dst(cfg: dict) -> None:
    with pytest.raises(ValueError, match="Unknown destination 'jupiter'"):
        SciNetTransferStage(cfg, dst_name="jupiter")