#!/usr/bin/env python3
"""Regenerate docs/_data/db_stats.yml from an AgIR SQLite database.

The GitHub Pages site (Jekyll) reads that file at build time to render the
home-page numbers and the Statistics page, so refreshing the site after a new
database release is:

    python scripts/update_db_stats.py --db /path/to/AgIR_DB_v2_0_202609.db
    git add docs/_data/db_stats.yml && git commit

Definitions used throughout (match docs/dataset/statistics.md):
    detection        row with a non-NULL cutout_id (one bounding box in one image)
    cutout           detection with cutout_exists = 1 (files confirmed on JUNO)
    primary cutout   cutout with is_primary = 1
    size class       estimated_area_bin (bbox area in cm^2; NULL -> "unbinned")

(totals.primary_detections counts is_primary = 1 rows whether or not the cutout
files exist, so the page can report how many primary detections still lack a cutout.)

Standard library only. The database is opened read-only and scanned once
(about a minute for the 12 GB v2 file).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "docs" / "_data" / "db_stats.yml"

# Natural (ascending) order; estimated_area_bin is TEXT so it must not be sorted lexically.
SIZE_CLASSES = ["0-1", "1-10", "10-100", "100-500", "500-1000", "1000-5000", "5000-10000", "10000+"]
UNBINNED = "unbinned"

# category_group values that are catalog classes rather than plant species.
NON_SPECIES_GROUPS = {"unknown", "colorchecker", "background"}


def q(value: object) -> str:
    """YAML-safe scalar. JSON string/number/null syntax is valid YAML."""
    return json.dumps(value, ensure_ascii=False)


def new_counts() -> Dict[str, int]:
    return {"detections": 0, "cutouts": 0, "primary_cutouts": 0}


def add(counts: Dict[str, int], n: int, cutout_exists, is_primary) -> None:
    counts["detections"] += n
    if cutout_exists == 1:
        counts["cutouts"] += n
        if is_primary == 1:
            counts["primary_cutouts"] += n


def parse_version(db_file: str) -> Dict[str, str]:
    """AgIR_DB_v2_0_202609.db -> version '2.0', release '2026-09'."""
    m = re.search(r"v(\d+)_(\d+)_(\d{4})(\d{2})", db_file)
    if not m:
        return {"version": "", "release": ""}
    return {"version": f"{m.group(1)}.{m.group(2)}", "release": f"{m.group(3)}-{m.group(4)}"}


def collect(db_path: Path, table: str) -> dict:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    # One pass over the table; everything else is derived from these groups.
    print("Scanning table (one full pass, ~1 min for the v2 database)...", file=sys.stderr)
    t0 = time.time()
    groups = con.execute(
        f"""
        SELECT state, (cutout_id IS NULL), category_group, category_class_id,
               category_usda_symbol, category_common_name,
               cutout_exists, is_primary, estimated_area_bin, COUNT(*)
        FROM {table}
        GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
        """
    ).fetchall()
    print(f"  {len(groups)} groups in {time.time() - t0:.0f}s", file=sys.stderr)

    # Covering-index query (batch_id, image_id, cutout_id) -> cheap.
    per_batch_images = con.execute(
        f"SELECT batch_id, COUNT(DISTINCT image_id) FROM {table} GROUP BY batch_id"
    ).fetchall()
    n_columns = len(con.execute(f"PRAGMA table_info({table})").fetchall())
    con.close()

    total_rows = 0
    placeholder_rows = 0
    primary_detections = 0  # is_primary = 1, whether or not the cutout files exist
    totals = new_counts()
    by_state: Dict[str, Dict[str, int]] = defaultdict(new_counts)
    by_size: Dict[str, Dict[str, int]] = defaultdict(new_counts)
    by_cat: Dict[tuple, Dict[str, int]] = defaultdict(new_counts)
    cat_size_primary: Dict[tuple, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for state, placeholder, group, class_id, symbol, name, exists, primary, size, n in groups:
        total_rows += n
        if placeholder:  # zero-detection image: one row, no cutout_id
            placeholder_rows += n
            continue
        size = size if size is not None else UNBINNED
        cat = (class_id, symbol, name, group)
        add(totals, n, exists, primary)
        add(by_state[state], n, exists, primary)
        add(by_size[size], n, exists, primary)
        add(by_cat[cat], n, exists, primary)
        if primary == 1:
            primary_detections += n
        if exists == 1 and primary == 1:
            cat_size_primary[cat][size] += n

    batches_by_state: Dict[str, int] = defaultdict(int)
    images_by_state: Dict[str, int] = defaultdict(int)
    for batch_id, n_images in per_batch_images:
        prefix = batch_id[:2]
        batches_by_state[prefix] += 1
        images_by_state[prefix] += n_images

    unknown_bins = set(by_size) - set(SIZE_CLASSES) - {UNBINNED}
    if unknown_bins:
        raise SystemExit(f"Unexpected estimated_area_bin values (update SIZE_CLASSES): {sorted(unknown_bins)}")

    species = []
    for (class_id, symbol, name, group), c in by_cat.items():
        species.append(
            {
                "name": name,
                "symbol": symbol,
                "group": group,
                "is_species": group not in NON_SPECIES_GROUPS,
                **c,
                "primary_by_size": [cat_size_primary[(class_id, symbol, name, group)][s] for s in SIZE_CLASSES],
            }
        )
    species.sort(key=lambda s: (-s["primary_cutouts"], -s["cutouts"], -s["detections"], s["name"]))

    return {
        "n_columns": n_columns,
        "totals": {
            "rows": total_rows,
            "batches": len(per_batch_images),
            "images": sum(n for _, n in per_batch_images),
            "images_without_detections": placeholder_rows,
            "species": sum(1 for s in species if s["is_species"]),
            "species_with_cutouts": sum(1 for s in species if s["is_species"] and s["cutouts"] > 0),
            "categories": len(species),
            **totals,
            "primary_detections": primary_detections,
        },
        "by_state": [
            {
                "state": st,
                "batches": batches_by_state[st],
                "images": images_by_state[st],
                **by_state[st],
            }
            for st in sorted(by_state)
        ],
        "by_size": [{"size_class": s, **by_size.get(s, new_counts())} for s in SIZE_CLASSES + [UNBINNED]],
        "species": species,
    }


def flow(d: dict) -> str:
    """Render a dict as a one-line YAML flow mapping."""
    parts = []
    for k, v in d.items():
        rendered = "[" + ", ".join(q(x) for x in v) + "]" if isinstance(v, list) else q(v)
        parts.append(f"{k}: {rendered}")
    return "{" + ", ".join(parts) + "}"


def render(stats: dict, db_path: Path) -> str:
    v = parse_version(db_path.name)
    t = stats["totals"]
    lines: List[str] = [
        "# AUTO-GENERATED by scripts/update_db_stats.py -- do not edit by hand.",
        "# Read by Jekyll as site.data.db_stats (home page + docs/dataset/statistics.md).",
        "#",
        "# detections      = rows with a cutout_id (one bounding box in one image)",
        "# cutouts         = detections with cutout_exists = 1 (files confirmed on JUNO)",
        "# primary_cutouts = cutouts with is_primary = 1",
        "# size classes    = estimated_area_bin (bbox area in cm^2); 'unbinned' = NULL",
        "",
        "database:",
        f"  file: {q(db_path.name)}",
        f"  version: {q(v['version'])}",
        f"  release: {q(v['release'])}",
        f"  table: {q('semif')}",
        f"  columns: {stats['n_columns']}",
        f"  size_gb: {round(db_path.stat().st_size / 1e9, 1)}",
        f"  generated: {q(dt.date.today().isoformat())}",
        "",
        "totals:",
    ]
    for key, value in t.items():
        lines.append(f"  {key}: {value}")
    lines += ["", "size_classes: [" + ", ".join(q(s) for s in SIZE_CLASSES) + "]", ""]
    lines.append("by_state:")
    lines += [f"  - {flow(r)}" for r in stats["by_state"]]
    lines += ["", "by_size:"]
    lines += [f"  - {flow(r)}" for r in stats["by_size"]]
    lines += [
        "",
        "# primary_by_size lists primary cutouts in the same order as size_classes",
        "species:",
    ]
    lines += [f"  - {flow(r)}" for r in stats["species"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, type=Path, help="path to the AgIR SQLite database")
    ap.add_argument("--table", default="semif", help="table to summarize (default: semif)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output file (default: {DEFAULT_OUT})")
    args = ap.parse_args()

    if not args.db.is_file():
        raise SystemExit(f"Database not found: {args.db}")

    stats = collect(args.db, args.table)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(stats, args.db), encoding="utf-8")
    print(f"Wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
