# src/agir_cvtoolkit/cli.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer
from hydra import compose, initialize_config_module
from omegaconf import DictConfig, OmegaConf

from .core.logging_utils import setup_logging
from .pipelines.utils.hydra_utils import finalize_cfg

app = typer.Typer(help="AgIR CV Toolkit CLI", pretty_exceptions_show_locals=True)


def _compose_cfg(config_name: str = "config", overrides: Optional[List[str]] = None) -> DictConfig:
    """
    Centralized Hydra composition so every command uses the same behavior.
    - Looks for configs in the Python package module: `agir_cvtoolkit.conf`
    - Injects a runtime working_dir into the config
    """
    with initialize_config_module(
        config_module="agir_cvtoolkit.conf",
        job_name="agir_cvtoolkit",
        version_base="1.3",
    ):
        cfg = compose(config_name=config_name, overrides=overrides or [])
        cfg["working_dir"] = str(Path.cwd())
    return cfg

@app.command()
def query(
    config: str = typer.Option("config", help="Hydra config name (without .yaml)"),
    override: List[str] = typer.Option(
        None, "--override", "-o", help="Hydra override (repeatable)"
    ),
    db: Optional[str] = typer.Option(
        "semif", "--db", "-d", help="semif|field database (default: semif)"
    ),
    # passthrough args to the query runner:
    filters: List[str] = typer.Option(
        None, "--filters", "-f", help="Repeatable filter (mini-DSL or JSON)"
    ),
    projection: Optional[str] = typer.Option(
        None, help="Comma-separated columns; omit for ALL"
    ),
    sort: Optional[str] = typer.Option(
        None, help='Comma list like "datetime:desc,cutout_id:asc"'
    ),
    limit: Optional[int] = typer.Option(None),
    offset: Optional[int] = typer.Option(None),
    out: str = typer.Option("csv", help="json|csv|parquet"),
    out_path: Optional[Path] = typer.Option(
        None,
        "--out-path",
        help="Optional file path for query results (defaults to run output directory)",
    ),
    preview: int = typer.Option(0, help="If >0, show first N via preview()"),
    sample: Optional[str] = typer.Option(
        None,
        help='Sampling spec, e.g. "random:n=200" or "seeded:n=200,seed=42" or "stratified:by=category_common_name,per_group=10"',
    ),
):
    """
    Query the AgIR DB and write JSON/CSV/Parquet (or stream JSON to stdout).
    All actual work lives in commands/query.py to keep this entrypoint clean.
    """
    # Compose cfg first so we can inject CLI args as overrides
    cfg = _compose_cfg(config_name=config, overrides=override)
    # Populate the "query" key in cfg with all the parsed values
    cfg["query"] = {
        "filters": filters or [],
        "db": db,
        "projection": projection,
        "sort": sort,
        "limit": limit,
        "offset": offset or None,
        "out": out or "json",
        "out_path": str(out_path) if out_path else None,
        "preview": preview or 0,
        "sample": sample
    }
    # Finalize cfg (adds runtime, paths, run_id, hash, etc)
    cfg = OmegaConf.to_container(
        finalize_cfg(cfg, stage="query", dataset=db or "unknown", cli_overrides=override),
        resolve=True
    )

    setup_logging(cfg)  # consistent logging
    # Run the query
    from .pipelines.stages.query import run_query
    run_query(
        cfg=cfg,
        db=db,
        filters=filters,
        projection=projection,
        sort=sort,
        limit=limit,
        offset=offset,
        out=out,
        out_path=out_path,
        preview=preview,
        sample=sample,
    )
    typer.echo(f"Query run complete: {cfg['runtime']['run_id']}\n• run_root: {cfg['paths']['run_root']}")

@app.command("infer-seg")
def infer_seg(
    config: str = typer.Option("config", help="Hydra config name (without .yaml)"),
    override: List[str] = typer.Option(None, "--override", "-o", help="Hydra overrides"),
):
    """Run segmentation inference pipeline."""
    cfg = _compose_cfg(config, override)
    cfg = finalize_cfg(
        cfg,
        stage="infer_seg",
        dataset=cfg.get("seg_inference", {}).get("source", {}).get("db", "semif"), 
        cli_overrides=override
    )

    setup_logging(cfg)
    from agir_cvtoolkit.pipelines.stages.seg_infer import SegmentationInferenceStage
    SegmentationInferenceStage(cfg).run()
    
    typer.echo(f"Segmentation inference complete\nrun_id: {cfg['runtime']['run_id']}\nrun_root: {cfg['paths']['run_root']}")

@app.command("infer-det")
def infer_det(
    config: str = typer.Option("config", help="Hydra config name (without .yaml)"),
    override: List[str] = typer.Option(None, "--override", "-o", help="Hydra overrides"),
):
    """Run detection inference pipeline with multiscale processing."""
    cfg = _compose_cfg(config, override)
    cfg = finalize_cfg(
        cfg,
        stage="infer_det",
        dataset=cfg.get("det_inference", {}).get("source", {}).get("db", "semif"), 
        cli_overrides=override
    )

    setup_logging(cfg)
    from agir_cvtoolkit.pipelines.stages.det_infer import DetectionInferenceStage
    DetectionInferenceStage(cfg).run()
    
    typer.echo(
        f"Detection inference complete\n"
        f"run_id: {cfg['runtime']['run_id']}\n"
        f"run_root: {cfg['paths']['run_root']}"
    )


@app.command("upload-cvat")
def upload_cvat(
    config: str = typer.Option("config", help="Hydra config name (without .yaml)"),
    override: List[str] = typer.Option(None, "--override", "-o", help="Hydra overrides"),
):
    """Upload annotations to CVAT (detections or segmentations)."""
    cfg = _compose_cfg(config, override)
    cfg = finalize_cfg(
        cfg,
        stage="upload_cvat",
        dataset=cfg.get("cvat_upload", {}).get("source", {}).get("db", "semif"),
        cli_overrides=override
    )

    setup_logging(cfg)
    from agir_cvtoolkit.pipelines.stages.cvat_upload import CVATUploadStage
    CVATUploadStage(cfg).run()
    
    typer.echo(
        f"CVAT upload complete\n"
        f"run_id: {cfg['runtime']['run_id']}\n"
        f"run_root: {cfg['paths']['run_root']}"
    )

@app.command("download-cvat")
def download_cvat(
    config: str = typer.Option("config", help="Hydra config name (without .yaml)"),
    override: List[str] = typer.Option(None, "--override", "-o", help="Hydra overrides"),
):
    """Download annotations from CVAT (with task filtering)."""
    cfg = _compose_cfg(config, override)
    cfg = finalize_cfg(
        cfg,
        stage="download_cvat",
        dataset="cvat",
        cli_overrides=override
    )

    setup_logging(cfg)
    from agir_cvtoolkit.pipelines.stages.cvat_download import CVATDownloadStage
    CVATDownloadStage(cfg).run()
    
    typer.echo(
        f"CVAT download complete\n"
        f"run_id: {cfg['runtime']['run_id']}\n"
        f"run_root: {cfg['paths']['run_root']}"
    )

@app.command("preprocess")
def preprocess(
    config: str = typer.Option("config", help="Hydra config name (without .yaml)"),
    override: List[str] = typer.Option(None, "--override", "-o", help="Hydra overrides"),
):
    """Preprocess training data (pad/crop/resize, split, compute stats)."""
    cfg = _compose_cfg(config, override)
    cfg = finalize_cfg(
        cfg,
        stage="preprocess",
        dataset="train",
        cli_overrides=override
    )
    
    setup_logging(cfg)
    from agir_cvtoolkit.pipelines.stages.preprocess import PreprocessStage
    PreprocessStage(cfg).run()
    
    typer.echo(
        f"Preprocessing complete\n"
        f"run_id: {cfg['runtime']['run_id']}\n"
        f"run_root: {cfg['paths']['run_root']}"
    )

@app.command("train")
def train(
    config: str = typer.Option("config", help="Hydra config name (without .yaml)"),
    override: List[str] = typer.Option(None, "--override", "-o", help="Hydra overrides"),
):
    """Train a segmentation model using PyTorch Lightning."""
    cfg = _compose_cfg(config, override)
    cfg = finalize_cfg(
        cfg,
        stage="train",
        dataset=cfg.get("train", {}).get("dataset", "field"),
        cli_overrides=override
    )
    
    setup_logging(cfg)
    from agir_cvtoolkit.pipelines.stages.train import TrainingStage
    TrainingStage(cfg).run()
    
    typer.echo(
        f"Training complete\n"
        f"run_id: {cfg['runtime']['run_id']}\n"
        f"run_root: {cfg['paths']['run_root']}"
    )

@app.command("scinet-transfer")
def scinet_transfer(
    config: str = typer.Option("config", help="Hydra config name (without .yaml)"),
    override: List[str] = typer.Option(
        None, "--override", "-o", help="Hydra override (repeatable)"
    ),
    dst: Optional[str] = typer.Option(
        None,
        "--dst",
        help=(
            "Destination name as defined in globus.destinations config "
            "(e.g. 'ceres' or 'atlas'). Defaults to globus.default_dst."
        ),
    ),
    src_root: Optional[str] = typer.Option(
        None,
        "--src-root",
        help="Override source root path on Juno (globus.src_root in config).",
    ),
    wait: bool = typer.Option(
        False,
        "--wait/--no-wait",
        help="Block until the Globus task completes (or times out). Only meaningful with --submit.",
    ),
    submit: bool = typer.Option(
        False,
        "--submit",
        help="Actually submit the transfer to Globus. Without this flag the command is a dry-run.",
    ),
):
    """
    Transfer files identified by a prior 'query' run from Juno LTS to a
    named destination endpoint (ceres, atlas, …) via Globus.

    \b
    Runs as a DRY-RUN by default — prints the file list without submitting.
    Pass --submit to perform the actual Globus transfer.

    \b
    Typical workflow:
        agir-cv query --db semif --filters "state=NC" --limit 500
        agir-cv scinet-transfer                   # dry-run → ceres (default)
        agir-cv scinet-transfer --dst atlas       # dry-run → atlas
        agir-cv scinet-transfer --dst ceres --submit   # submit to ceres
        agir-cv scinet-transfer --dst atlas --submit   # submit to atlas

    Destinations are configured in conf/globus/default.yaml under
    globus.destinations. Add new endpoints there without touching Python.
    """
    # ---- Build Hydra overrides ----
    extra_overrides: List[str] = list(override or [])
    if src_root:
        extra_overrides.append(f"globus.src_root={src_root}")
    if wait:
        extra_overrides.append("globus.transfer.wait=true")

    cfg = _compose_cfg(config, extra_overrides)
    cfg = finalize_cfg(
        cfg,
        stage="scinet_transfer",
        dataset="unknown",
        cli_overrides=extra_overrides,
    )

    setup_logging(cfg)
    cfg_dict = OmegaConf.to_container(cfg, resolve=True)

    # Resolve destination name (CLI flag > config default)
    globus_cfg = cfg_dict.get("globus", {})
    dst_name = dst or globus_cfg.get("default_dst", "ceres")

    from agir_cvtoolkit.pipelines.stages.scinet_transfer import (
        SciNetTransferStage,
        _extract_transfer_paths,
        _load_records,
        _resolve_destination,
    )

    # Validate the destination name early so dry-run also catches typos
    dst_endpoint, dst_root_val = _resolve_destination(globus_cfg, dst_name)

    # ---- Dry-run mode (default) ----
    if not submit:
        from pathlib import Path as _Path

        run_root    = _Path(cfg_dict["paths"]["run_root"])
        path_columns = globus_cfg.get("path_columns", [])
        src_root_val = globus_cfg.get("src_root", "")

        try:
            records = _load_records(run_root)
        except FileNotFoundError as exc:
            typer.echo(f"[dry-run] ERROR: {exc}", err=True)
            raise typer.Exit(1)

        pairs = _extract_transfer_paths(records, path_columns, src_root_val)
        typer.echo(
            f"[dry-run] Would transfer {len(pairs)} unique files.\n"
            f"  src endpoint : {globus_cfg.get('juno_endpoint')}  (juno)\n"
            f"  dst endpoint : {dst_endpoint}  ({dst_name})\n"
            f"  src_root     : {src_root_val}\n"
            f"  dst_root     : {dst_root_val}\n"
        )
        if pairs:
            typer.echo("First 10 source paths:")
            for src, _ in pairs[:10]:
                typer.echo(f"  {src}")
            if len(pairs) > 10:
                typer.echo(f"  ... and {len(pairs) - 10} more")
        typer.echo(f"\nRe-run with --submit to transfer to {dst_name}.")
        return

    # ---- Live transfer (--submit) ----
    stage = SciNetTransferStage(cfg_dict, dst_name=dst_name)
    task_id = stage.run()

    if task_id:
        typer.echo(
            f"Globus transfer submitted to {dst_name}.\n"
            f"  task_id  : {task_id}\n"
            f"  run_root : {cfg_dict['paths']['run_root']}\n"
            f"  Monitor  : https://app.globus.org/activity/{task_id}"
        )
    else:
        typer.echo("No files were transferred (empty query results or no valid paths).")

if __name__ == "__main__":
    app()