# src/agir_cvtoolkit/pipelines/stages/scinet_transfer.py
"""
Globus transfer stage for AgIR-CVToolkit.

Reads the query results (query.json / query.csv) produced by the *query* stage,
extracts source file paths relative to ``globus.src_root``, and submits a Globus
batch transfer from Juno LTS to a named destination endpoint (Ceres or Atlas).

Usage (after ``agir-cv query ...`` has been run in the same run directory):

    agir-cv scinet-transfer                  # dry-run → Ceres (default)
    agir-cv scinet-transfer --dst atlas      # dry-run → Atlas
    agir-cv scinet-transfer --dst ceres --submit   # actually transfer

Authentication
--------------
This stage shells out to the ``globus`` CLI binary, so whatever session
``globus login`` has already established is used automatically.
Make sure ``globus`` is on your PATH:

    pipx install globus-cli   # or: pip install globus-cli
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_globus_cli() -> str:
    """Return the path to the globus binary or raise a clear error."""
    binary = shutil.which("globus")
    if binary is None:
        raise RuntimeError(
            "The 'globus' CLI is not on your PATH.\n\n"
            "Install it with:  pipx install globus-cli\n"
            "Then log in with: globus login"
        )
    return binary


def _run_globus(args: List[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a globus CLI command and return the CompletedProcess."""
    binary = _require_globus_cli()
    cmd = [binary] + args
    log.debug(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _resolve_destination(globus_cfg: dict, dst_name: str) -> Tuple[str, str]:
    """
    Look up *dst_name* in ``globus.destinations`` and return
    ``(endpoint_uuid, dst_root)``.

    Raises a clear ValueError listing valid names if the key isn't found.
    """
    destinations: dict = globus_cfg.get("destinations", {})
    if not destinations:
        raise ValueError(
            "No destinations defined in globus config. "
            "Add entries under globus.destinations in conf/globus/default.yaml."
        )
    if dst_name not in destinations:
        valid = ", ".join(sorted(destinations))
        raise ValueError(
            f"Unknown destination '{dst_name}'. "
            f"Valid options: {valid}\n"
            "Add new destinations under globus.destinations in conf/globus/default.yaml."
        )
    entry = destinations[dst_name]
    return entry["endpoint"], entry["dst_root"]


def _load_records(run_root: Path) -> List[Dict]:
    """Load query records from query.json or query.csv inside *run_root*."""
    query_json = run_root / "query" / "query.json"
    query_csv  = run_root / "query" / "query.csv"

    if query_json.exists():
        log.info(f"Loading records from: {query_json}")
        with open(query_json) as fh:
            data = json.load(fh)
    elif query_csv.exists():
        log.info(f"Loading records from: {query_csv}")
        df = pd.read_csv(query_csv)
        df = df.where(pd.notnull(df), None)
        data = df.to_dict(orient="records")
    else:
        raise FileNotFoundError(
            f"No query results found under {run_root / 'query'}. "
            "Run 'agir-cv query ...' first."
        )

    if not data:
        log.warning("Query results are empty – nothing to transfer.")
    return data


def _extract_transfer_paths(
    records: List[Dict],
    path_columns: List[str],
    src_root: str,
) -> List[Tuple[str, str]]:
    """
    For every record build (src_path, rel_path) pairs.

    *src_path* – absolute path on the source (Juno) endpoint
    *rel_path* – path relative to src_root (mirrored under dst_root)

    Skips None, float NaN, and sentinel strings. Deduplicates.
    """
    _SENTINEL = {"none", "null", "", "nan"}
    seen: set[str] = set()
    pairs: List[Tuple[str, str]] = []

    for record in records:
        for col in path_columns:
            raw = record.get(col)
            if raw is None:
                continue
            # pandas reads missing CSV cells as float('nan');
            # NaN is the only value not equal to itself
            try:
                if raw != raw:
                    continue
            except TypeError:
                pass
            raw_str = str(raw).strip()
            if raw_str.lower() in _SENTINEL:
                continue

            rel = raw_str.lstrip("/")
            src = str(Path(src_root) / rel)

            if src in seen:
                continue
            seen.add(src)
            pairs.append((src, rel))

    return pairs


def _build_batch_file(
    pairs: List[Tuple[str, str]],
    dst_root: str,
    batch_path: Path,
) -> None:
    """
    Write a Globus CLI batch file to *batch_path*.

    Format understood by ``globus transfer --batch``:
        <src_path> <dst_path>
    One transfer item per line.
    """
    lines = [f"{src} {Path(dst_root) / rel}\n" for src, rel in pairs]
    batch_path.write_text("".join(lines))
    log.info(f"Batch file written: {batch_path}  ({len(lines)} items)")


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

class SciNetTransferStage:
    """
    Transfer files identified by a prior *query* stage via the Globus CLI.

    Parameters
    ----------
    cfg : dict
        Fully resolved Hydra configuration (already passed through
        ``finalize_cfg``).
    dst_name : str
        Key into ``globus.destinations`` — e.g. ``"ceres"`` or ``"atlas"``.
        Defaults to ``globus.default_dst`` from config.
    """

    def __init__(self, cfg: dict, dst_name: Optional[str] = None) -> None:
        self.cfg = cfg
        self.run_root   = Path(cfg["paths"]["run_root"])
        self.globus_cfg = cfg.get("globus", {})

        self.juno_endpoint: str = self.globus_cfg["juno_endpoint"]
        self.src_root: str      = self.globus_cfg["src_root"].rstrip("/") + "/"

        # Resolve destination
        self.dst_name: str = dst_name or self.globus_cfg.get("default_dst", "ceres")
        self.dst_endpoint, dst_root_raw = _resolve_destination(
            self.globus_cfg, self.dst_name
        )
        self.dst_root: str = dst_root_raw.rstrip("/") + "/"

        transfer_opts = self.globus_cfg.get("transfer", {})
        self.sync_level: str    = transfer_opts.get("sync_level", "checksum")
        self.label_prefix: str  = transfer_opts.get("label_prefix", "agir-cv scinet-transfer")
        self.wait: bool         = bool(transfer_opts.get("wait", False))
        self.poll_interval: int = int(transfer_opts.get("poll_interval_s", 10))
        self.timeout: int       = int(transfer_opts.get("timeout_s", 300))

        self.path_columns: List[str] = self.globus_cfg.get(
            "path_columns",
            [
                "image_path", "mask_path", "cropout_path", "cutout_path",
                "cutout_mask_path", "developed_image_path", "raw_image_path",
                "final_cutout_path", "final_mask_path",
            ],
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> Optional[str]:
        """Execute the transfer and return the Globus task ID."""
        log.info("=" * 60)
        log.info("SciNetTransferStage starting")
        log.info(f"  run_root     : {self.run_root}")
        log.info(f"  src endpoint : {self.juno_endpoint}  (Juno)")
        log.info(f"  dst endpoint : {self.dst_endpoint}  ({self.dst_name})")
        log.info(f"  src_root     : {self.src_root}")
        log.info(f"  dst_root     : {self.dst_root}")
        log.info("=" * 60)

        _require_globus_cli()
        self._check_logged_in()

        records = _load_records(self.run_root)
        log.info(f"Loaded {len(records)} records.")

        if not records:
            log.warning("No records – skipping transfer.")
            return None

        pairs = _extract_transfer_paths(records, self.path_columns, self.src_root)
        log.info(f"Unique source paths: {len(pairs)}")

        if not pairs:
            log.warning(
                "No valid file paths found in query results. "
                "Check that path_columns match your DB schema."
            )
            return None

        batch_path = self.run_root / "globus_batch.txt"
        _build_batch_file(pairs, self.dst_root, batch_path)

        manifest_path = self.run_root / "scinet_transfer_manifest.json"
        with open(manifest_path, "w") as fh:
            json.dump(
                {
                    "juno_endpoint": self.juno_endpoint,
                    "dst_name":      self.dst_name,
                    "dst_endpoint":  self.dst_endpoint,
                    "src_root":      self.src_root,
                    "dst_root":      self.dst_root,
                    "sync_level":    self.sync_level,
                    "num_items":     len(pairs),
                    "batch_file":    str(batch_path),
                },
                fh,
                indent=2,
            )
        log.info(f"Manifest written: {manifest_path}")

        task_id = self._submit_transfer(batch_path)
        log.info(f"Globus task submitted: {task_id}")

        if self.wait:
            self._wait_for_task(task_id)

        return task_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_logged_in(self) -> None:
        """Raise a clear error if the user is not logged into Globus."""
        result = _run_globus(["session", "show", "--format", "json"], check=False)
        if result.returncode != 0:
            raise RuntimeError(
                "Not logged into Globus (or 'globus session show' failed).\n\n"
                f"  stderr: {result.stderr.strip()}\n\n"
                "Run:  globus login"
            )
        log.debug(f"Globus session OK: {result.stdout.strip()[:120]}")

    def _submit_transfer(self, batch_path: Path) -> str:
        """Call ``globus transfer --batch`` and return the task ID."""
        label = (
            f"{self.label_prefix} "
            f"dst={self.dst_name} "
            f"run={self.cfg.get('runtime', {}).get('run_id', 'unknown')}"
        )
        args = [
            "transfer",
            self.juno_endpoint,
            self.dst_endpoint,
            "--batch", str(batch_path),
            "--label", label,
            "--sync-level", self.sync_level,
            "--format", "json",
        ]
        result = _run_globus(args)
        try:
            task_id: str = json.loads(result.stdout)["task_id"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(
                f"Could not parse task_id from globus transfer output.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            ) from exc
        return task_id

    def _wait_for_task(self, task_id: str) -> None:
        """Poll ``globus task show`` until terminal state or timeout."""
        deadline = time.monotonic() + self.timeout
        log.info(
            f"Waiting for task {task_id} "
            f"(timeout={self.timeout}s, poll={self.poll_interval}s) …"
        )
        while time.monotonic() < deadline:
            result = _run_globus(["task", "show", task_id, "--format", "json"], check=False)
            if result.returncode != 0:
                log.warning(f"globus task show failed: {result.stderr.strip()}")
                time.sleep(self.poll_interval)
                continue
            try:
                status: str = json.loads(result.stdout).get("status", "UNKNOWN")
            except json.JSONDecodeError:
                time.sleep(self.poll_interval)
                continue
            log.info(f"  task status: {status}")
            if status == "SUCCEEDED":
                log.info(f"Globus task {task_id} SUCCEEDED.")
                return
            if status == "FAILED":
                log.error(f"Globus task {task_id} FAILED.")
                return
            time.sleep(self.poll_interval)
        log.warning(
            f"Timed out after {self.timeout}s.\n"
            f"  Check: https://app.globus.org/activity/{task_id}"
        )