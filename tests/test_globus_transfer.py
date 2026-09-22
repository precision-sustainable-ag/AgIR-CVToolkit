# tests/test_scinet_transfer_stage.py
"""
Unit tests for SciNetTransferStage.

Globus CLI calls are monkey-patched so no real credentials are needed.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from agir_cvtoolkit.pipelines.stages.scinet_transfer import (
    SciNetTransferStage,
    _build_batch_file,
    _collect_run_folder_pairs,
    _explain_no_paths,
    _extract_transfer_paths,
    _globus_folder_url,
    _landing_folder,
    _load_records,
    _resolve_destination,
    _scoped_dst_root,
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


# ---------------------------------------------------------------------------
# _load_records: the newest results file wins
# ---------------------------------------------------------------------------

def _write_both(query_dir: Path, json_mtime: int, csv_mtime: int) -> None:
    """query.json holds 3 records, query.csv holds 1, with the given modification times."""
    import pandas as pd
    (query_dir / "query.json").write_text(json.dumps(RECORDS))
    pd.DataFrame(RECORDS[:1]).to_csv(query_dir / "query.csv", index=False)
    os.utime(query_dir / "query.json", (json_mtime, json_mtime))
    os.utime(query_dir / "query.csv", (csv_mtime, csv_mtime))


def test_load_records_newer_csv_beats_stale_json(query_dir: Path, tmp_path: Path) -> None:
    _write_both(query_dir, json_mtime=1_000_000, csv_mtime=2_000_000)
    assert len(_load_records(tmp_path)) == 1          # the csv, not the old json


def test_load_records_newer_json_beats_stale_csv(query_dir: Path, tmp_path: Path) -> None:
    _write_both(query_dir, json_mtime=2_000_000, csv_mtime=1_000_000)
    assert len(_load_records(tmp_path)) == 3          # the json


def test_load_records_tie_keeps_json_first(query_dir: Path, tmp_path: Path) -> None:
    _write_both(query_dir, json_mtime=1_500_000, csv_mtime=1_500_000)
    assert len(_load_records(tmp_path)) == 3


# ---------------------------------------------------------------------------
# _explain_no_paths
# ---------------------------------------------------------------------------

CUTOUT_COLUMNS = ["cropout_path", "cutout_path", "cutout_mask_path", "cutout_json_path"]


def test_explain_no_rows() -> None:
    assert "no rows" in _explain_no_paths([], CUTOUT_COLUMNS)


def test_explain_projection_dropped_the_columns() -> None:
    msg = _explain_no_paths([{"cutout_id": "A_0"}, {"cutout_id": "A_1"}], CUTOUT_COLUMNS)
    assert "--projection" in msg
    assert "cutout_path" in msg


def test_explain_zero_detection_rows() -> None:
    rows = [{"cutout_id": None, "cutout_path": None, "cropout_path": float("nan")} for _ in range(3)]
    msg = _explain_no_paths(rows, CUTOUT_COLUMNS)
    assert "zero-detection" in msg
    assert 'cutout_juno_url is not null' in msg


def test_explain_empty_paths_but_real_cutout_ids() -> None:
    rows = [{"cutout_id": "A_0", "cutout_path": None}, {"cutout_id": "A_1", "cutout_path": ""}]
    msg = _explain_no_paths(rows, CUTOUT_COLUMNS)
    assert "zero-detection" not in msg
    assert "empty cutout paths" in msg


# ---------------------------------------------------------------------------
# _landing_folder / _globus_folder_url
# ---------------------------------------------------------------------------

DST_ROOT = "/90daydata/dash_agir/tmp/"


def _pairs(*rels: str):
    return [(SRC_ROOT + r, r) for r in rels]


def test_landing_folder_single_batch() -> None:
    pairs = _pairs("semifield-cutouts/NC_2023-07-11/a.png", "semifield-cutouts/NC_2023-07-11/a.json")
    assert _landing_folder(pairs, DST_ROOT) == "/90daydata/dash_agir/tmp/semifield-cutouts/NC_2023-07-11/"


def test_landing_folder_several_batches_uses_shared_parent() -> None:
    pairs = _pairs("semifield-cutouts/NC_2023-07-11/a.png", "semifield-cutouts/MD_2022-06-24/b.png")
    assert _landing_folder(pairs, DST_ROOT) == "/90daydata/dash_agir/tmp/semifield-cutouts/"


def test_landing_folder_files_at_the_root() -> None:
    assert _landing_folder(_pairs("a.png"), DST_ROOT) == "/90daydata/dash_agir/tmp/"


def test_landing_folder_no_files_falls_back_to_dst_root() -> None:
    assert _landing_folder([], DST_ROOT) == DST_ROOT


def test_globus_folder_url_encodes_the_path() -> None:
    url = _globus_folder_url("EP-1", "/90daydata/dash_agir/tmp/semifield-cutouts/")
    assert url == ("https://app.globus.org/file-manager?origin_id=EP-1"
                   "&origin_path=%2F90daydata%2Fdash_agir%2Ftmp%2Fsemifield-cutouts%2F")


def test_globus_folder_url_without_endpoint_is_none() -> None:
    assert _globus_folder_url(None, DST_ROOT) is None
    assert _globus_folder_url("", DST_ROOT) is None


# ---------------------------------------------------------------------------
# Stage: landing folder follows the destination; zero files explains itself
# ---------------------------------------------------------------------------

LANDING_RECORDS = [
    {"cutout_id": "NC_1_0", "image_path": "semifield-cutouts/NC_2023-07-11/NC_1_0.png"},
    {"cutout_id": "NC_1_1", "image_path": "semifield-cutouts/NC_2023-07-11/NC_1_1.png"},
]


@pytest.mark.parametrize("dst", ["ceres", "atlas"])
def test_stage_landing_url_points_at_the_chosen_destination(
    cfg: dict, query_dir: Path, dst: str
) -> None:
    (query_dir / "query.json").write_text(json.dumps(LANDING_RECORDS))
    with patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._run_globus",
               side_effect=_mock_run_globus), \
         patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._require_globus_cli",
               return_value="/usr/bin/globus"):
        stage = SciNetTransferStage(cfg, dst_name=dst)
        stage.run()

    # cfg's runtime.run_id is "test_run" -> namespaced under dst_root (see _scoped_dst_root)
    assert stage.landing_folder == "/90daydata/dash_agir/tmp/test_run/semifield-cutouts/NC_2023-07-11/"
    assert f"origin_id={DESTINATIONS[dst]['endpoint']}" in stage.landing_url
    other = "atlas" if dst == "ceres" else "ceres"
    assert DESTINATIONS[other]["endpoint"] not in stage.landing_url


def test_stage_zero_paths_logs_the_reason(cfg: dict, query_dir: Path, caplog) -> None:
    placeholders = [{"cutout_id": None, "image_path": None} for _ in range(3)]
    (query_dir / "query.json").write_text(json.dumps(placeholders))
    with patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._run_globus",
               side_effect=_mock_run_globus), \
         patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._require_globus_cli",
               return_value="/usr/bin/globus"):
        with caplog.at_level("WARNING"):
            assert SciNetTransferStage(cfg).run() is None
    assert "zero-detection" in caplog.text


# ---------------------------------------------------------------------------
# _scoped_dst_root
# ---------------------------------------------------------------------------

def test_scoped_dst_root_appends_run_id() -> None:
    assert _scoped_dst_root("/90daydata/dash_agir/tmp/", "test/001") == "/90daydata/dash_agir/tmp/test/001/"


def test_scoped_dst_root_normalizes_slashes() -> None:
    # no trailing slash on dst_root; leading/trailing slashes on run_id
    assert _scoped_dst_root("/90daydata/dash_agir/tmp", "/test/001/") == "/90daydata/dash_agir/tmp/test/001/"


def test_scoped_dst_root_single_segment_run_id() -> None:
    assert _scoped_dst_root("/90daydata/dash_agir/tmp/", "h=abcd1234") == "/90daydata/dash_agir/tmp/h=abcd1234/"


def test_scoped_dst_root_no_run_id_is_unchanged() -> None:
    assert _scoped_dst_root("/90daydata/dash_agir/tmp/", None) == "/90daydata/dash_agir/tmp/"
    assert _scoped_dst_root("/90daydata/dash_agir/tmp/", "") == "/90daydata/dash_agir/tmp/"


# ---------------------------------------------------------------------------
# _collect_run_folder_pairs
# ---------------------------------------------------------------------------

def test_collect_run_folder_pairs_finds_nested_files(tmp_path: Path) -> None:
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "run.log").write_text("log")
    (tmp_path / "query").mkdir()
    (tmp_path / "query" / "query.csv").write_text("csv")
    (tmp_path / "cfg.yaml").write_text("cfg")

    pairs = _collect_run_folder_pairs(tmp_path, "/90daydata/dash_agir/tmp/test/001/")
    rels = sorted(rel for _, rel in pairs)
    assert rels == ["cfg.yaml", "logs/run.log", "query/query.csv"]
    # relative paths, not absolute, and forward slashes even if run on a different OS
    assert all(not rel.startswith("/") for rel in rels)


def test_collect_run_folder_pairs_missing_folder_is_empty(tmp_path: Path) -> None:
    assert _collect_run_folder_pairs(tmp_path / "does-not-exist", "/dst/") == []


def test_collect_run_folder_pairs_empty_folder_is_empty(tmp_path: Path) -> None:
    assert _collect_run_folder_pairs(tmp_path, "/dst/") == []


def test_collect_run_folder_pairs_skips_directories(tmp_path: Path) -> None:
    (tmp_path / "empty_subdir").mkdir()
    (tmp_path / "cfg.yaml").write_text("cfg")
    pairs = _collect_run_folder_pairs(tmp_path, "/dst/")
    assert [rel for _, rel in pairs] == ["cfg.yaml"]


# ---------------------------------------------------------------------------
# SciNetTransferStage: copying the run folder alongside the data transfer
# ---------------------------------------------------------------------------

def _cfg_with_local_endpoint(cfg: dict) -> dict:
    out = {**cfg, "globus": {**cfg["globus"], "local_endpoint": "LOCAL-CERES-EP"}}
    return out


def test_stage_copies_run_folder_when_local_endpoint_set(
    cfg: dict, query_dir: Path, tmp_path: Path
) -> None:
    (query_dir / "query.json").write_text(json.dumps(LANDING_RECORDS))
    (tmp_path / "cfg.yaml").write_text("project: {}\n")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "run.log").write_text("hello")

    with patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._run_globus",
               side_effect=_mock_run_globus) as mock_globus, \
         patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._require_globus_cli",
               return_value="/usr/bin/globus"):
        stage = SciNetTransferStage(_cfg_with_local_endpoint(cfg))
        task_id = stage.run()

    assert task_id == "fake-task-id-1234"                 # unchanged: still the DATA transfer's id
    assert stage.run_folder_task_id == "fake-task-id-1234"
    # query.json (already on disk when run() started), cfg.yaml, logs/run.log,
    # plus globus_batch.txt and the manifest written during run()
    rels = sorted(rel for _, rel in stage.run_folder_pairs)
    assert rels == [
        "cfg.yaml", "globus_batch.txt", "logs/run.log",
        "query/query.json", "scinet_transfer_manifest.json",
    ]

    transfer_calls = [c for c in mock_globus.call_args_list if "transfer" in c.args[0]]
    assert len(transfer_calls) == 2                        # data transfer + run-folder copy
    data_src, run_folder_src = (c.args[0][1] for c in transfer_calls)
    assert data_src == cfg["globus"]["juno_endpoint"]
    assert run_folder_src == "LOCAL-CERES-EP"

    run_folder_batch = (tmp_path / "run_folder_batch.txt").read_text().splitlines()
    assert len(run_folder_batch) == len(stage.run_folder_pairs)
    for line in run_folder_batch:
        src, dst = line.split(" ", 1)
        assert src.startswith(str(tmp_path))
        assert dst.startswith(stage.dst_root)               # the scoped, project-namespaced root
    # run_folder_batch.txt does not try to include itself
    assert not any(rel == "run_folder_batch.txt" for _, rel in stage.run_folder_pairs)


def test_stage_skips_run_folder_copy_without_local_endpoint(
    cfg: dict, query_dir: Path, tmp_path: Path, caplog
) -> None:
    (query_dir / "query.json").write_text(json.dumps(LANDING_RECORDS))
    (tmp_path / "cfg.yaml").write_text("project: {}\n")

    with patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._run_globus",
               side_effect=_mock_run_globus) as mock_globus, \
         patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._require_globus_cli",
               return_value="/usr/bin/globus"):
        with caplog.at_level("INFO"):
            stage = SciNetTransferStage(cfg)               # no local_endpoint
            stage.run()

    assert stage.run_folder_task_id is None
    assert stage.run_folder_pairs                           # still reported, just not copied
    assert "local_endpoint" in caplog.text
    transfer_calls = [c for c in mock_globus.call_args_list if "transfer" in c.args[0]]
    assert len(transfer_calls) == 1                          # only the data transfer


def test_stage_no_run_folder_files_means_no_copy_attempt(
    cfg: dict, query_dir: Path, tmp_path: Path
) -> None:
    # tmp_path (run_root) has nothing in it yet besides query/query.json when run() starts;
    # globus_batch.txt / the manifest still get created during run(), so this exercises the
    # "files exist once the data transfer has written its own bookkeeping" path, same as above,
    # just without any pre-existing logs/cfg.yaml.
    (query_dir / "query.json").write_text(json.dumps(LANDING_RECORDS))
    with patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._run_globus",
               side_effect=_mock_run_globus), \
         patch("agir_cvtoolkit.pipelines.stages.scinet_transfer._require_globus_cli",
               return_value="/usr/bin/globus"):
        stage = SciNetTransferStage(_cfg_with_local_endpoint(cfg))
        stage.run()
    assert stage.run_folder_task_id is not None
    assert {rel for _, rel in stage.run_folder_pairs} == {
        "query/query.json", "globus_batch.txt", "scinet_transfer_manifest.json",
    }

