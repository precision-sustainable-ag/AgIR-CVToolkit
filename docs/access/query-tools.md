---
layout: default
title: Query Guide
parent: Access & Query
nav_order: 3
---

# Query Guide
{: .no_toc }

Filter, sample and export records from the AgIR database with `agir-cv query`.
{: .fs-6 .fw-300 }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Overview

The **SemiF** database (`AgIR_DB_v2_0_202609.db`) has one row per plant detection. See the [schema](../dataset/semif.html) for every column and [Statistics](../dataset/statistics.html) for the species and their USDA symbols.

Examples write `agir-cv ...`. Prefix them with `uv run` if you have not activated the environment (see [Installation](installation.html)). The **Field** database will be added in a future release.

---

## Before You Run a Query

{: .warning }
> **Always set `--limit` (or a sample).** A query with no limit exports **every matching row**, and the full database has {% include num.html n=site.data.db_stats.totals.rows %} rows and {{ site.data.db_stats.database.columns }} columns.
>
> - `--preview N` prints N records **and then still runs the full query**. Use `--preview 5 --limit 5`.
> - `--limit 0` does **not** count rows; it means "no limit". To count, see [Counting](#counting).

**Speed.** The database is about {{ site.data.db_stats.database.size_gb }} GB.
- Filters on `batch_id`, `image_id`, `cutout_id` and `category_usda_symbol` are fast.
- `state`, `season` or `category_common_name` on their own may scan the whole table (10 to 60 seconds).
- To keep only detections that have downloadable files, filter on **`cutout_juno_url is not null`**, not `cutout_exists=1`. They select the same rows, but with `cutout_exists=1` the database walks all {% include compact_num.html n=site.data.db_stats.totals.cutouts %} cutouts even when you also filter by batch or species. That took close to a minute in testing, against about a second.

---

## Quick Start

```bash
# Look at 5 records
agir-cv query --db semif --preview 5 --limit 5

# 100 primary cutouts of barley (USDA symbol HOVU)
agir-cv query --db semif \
  --filters "category_usda_symbol=HOVU" \
  --filters "cutout_juno_url is not null" --filters "is_primary=1" \
  --limit 100

# A balanced set: 20 primary cutouts per species
agir-cv query --db semif \
  --filters "category_usda_symbol=HOVU,PISA6,SECE" \
  --filters "cutout_juno_url is not null" --filters "is_primary=1" \
  --sample "stratified:by=category_common_name,per_group=20"
```

---

## Filtering

Repeat `--filters` for each condition (they combine with **AND**). A comma-separated list of values inside one flag means **OR**.

```bash
# AND: separate flags
agir-cv query --db semif --filters "batch_id=MD_2022-06-24" --filters "category_usda_symbol=PADI" --limit 100

# OR: several values in one flag
agir-cv query --db semif --filters "category_usda_symbol=HOVU,PISA6,SECE" --limit 100

# NULL checks
agir-cv query --db semif --filters "category_usda_symbol=HOVU" --filters "cutout_juno_url is not null" --limit 100
```

### Species

Use `category_usda_symbol` (for example `HOVU` for barley). It is indexed, so it is much faster than `category_common_name`. Find symbols on the [Statistics](../dataset/statistics.html#by-species) page.

### Cutouts and primary cutouts

`cutout_juno_url is not null` keeps detections whose cutout files exist. Add `is_primary=1` to keep one preferred view of each plant that appears in several overlapping images.

```bash
agir-cv query --db semif \
  --filters "category_usda_symbol=HOVU" \
  --filters "cutout_juno_url is not null" --filters "is_primary=1" \
  --limit 100
```

### Size class

`estimated_area_bin` holds the size class in cm²: `0-1`, `1-10`, `10-100`, `100-500`, `500-1000`, `1000-5000`, `5000-10000`, `10000+`. It is text, so filter with equality, not `>=`.

```bash
agir-cv query --db semif \
  --filters "category_usda_symbol=GOHI" \
  --filters "cutout_juno_url is not null" \
  --filters "estimated_area_bin=1000-5000,5000-10000,10000+" \
  --limit 50
```

### Numeric ranges

Give each bound its own `--filters` flag. Putting two bounds in one flag (`a>=1,a<5`) is silently misread.

```bash
agir-cv query --db semif \
  --filters "estimated_bbox_area_cm2>=50" \
  --filters "estimated_bbox_area_cm2<=200" \
  --limit 100
```

Area in cm² is only reliable where `crs = 'LOCAL'` (see the [schema notes](../dataset/semif.html)).

### Dates

{: .warning }
> Do **not** filter on `datetime`. It mixes two text formats (`2022:06:25 01:11:08` and `2025-10-03T15:28:39`), so date comparisons return wrong rows. Use `batch_id`, which contains the capture date, or `season`.

```bash
# One capture day at one site
agir-cv query --db semif --filters "batch_id=MD_2022-06-24" --limit 100

# A date range within one state (batch_id sorts by date within a state)
agir-cv query --db semif --filters "batch_id>=MD_2022-06-01" --filters "batch_id<MD_2022-09-01" --limit 100

# A season
agir-cv query --db semif --filters "season=summer_weeds_2023" --limit 100
```

The states are `MD`, `NC` and `TX`.

---

## Sampling

Sampling applies after filtering.

```bash
# Random
agir-cv query --db semif --filters "category_usda_symbol=HOVU" --sample "random:n=200"

# Seeded: the same seed returns the same rows every time
agir-cv query --db semif \
  --filters "category_usda_symbol=HOVU" --filters "cutout_juno_url is not null" \
  --sample "seeded:n=200,seed=42"

# Stratified: per_group rows from each group ("|" separates several columns)
agir-cv query --db semif \
  --filters "category_usda_symbol=HOVU,PISA6,SECE" \
  --filters "cutout_juno_url is not null" --filters "is_primary=1" \
  --sample "stratified:by=category_common_name|estimated_area_bin,per_group=20"
```

{: .warning }
> Stratified sampling shuffles every matching row first, so always pre-filter (species, batch or season). Group by `estimated_area_bin`, not `area_bin`, which is not a column.

---

## Sorting and Paging

Results are ordered by `cutout_id` unless you sort. Sorting by a column without an index sorts every match, so filter first.

```bash
agir-cv query --db semif --filters "category_usda_symbol=HOVU" --sort "batch_id:desc" --limit 50
agir-cv query --db semif --filters "category_usda_symbol=HOVU" --sort "batch_id:desc" --limit 50 --offset 50
```

---

## Output

```bash
# Format: csv (the default), json or parquet
agir-cv query --db semif --filters "batch_id=MD_2022-06-24" --limit 500 --out parquet

# Only the columns you need
agir-cv query --db semif --filters "batch_id=MD_2022-06-24" --limit 500 \
  --projection "cutout_id,category_common_name,estimated_area_bin,cutout_juno_url"

# Write to a file of your choice
agir-cv query --db semif --filters "batch_id=MD_2022-06-24" --limit 500 --out-path my_query.csv
```

Each run also writes the query it ran, so you can reproduce it:

```
outputs/runs/{project_name}/{subname}/query/
├── query.csv             # or query.json / query.parquet
└── query_spec.json       # database file, filters, sampling, user, host, timestamp
```

```python
import pandas as pd
df = pd.read_csv("outputs/runs/test/001/query/query.csv")
```

### Counting

The command line cannot count without exporting, so count with Python or SQL:

```python
n = db.filter(category_usda_symbol="HOVU", is_primary=1).where("cutout_juno_url IS NOT NULL").count()
```
```sql
SELECT COUNT(*) FROM semif
WHERE category_usda_symbol = 'HOVU' AND cutout_juno_url IS NOT NULL AND is_primary = 1;
```

### Getting the files

Each row has direct download links in `cutout_juno_url` and its sibling columns. Export a list of them:

```bash
agir-cv query --db semif \
  --filters "category_usda_symbol=HOVU" --filters "cutout_juno_url is not null" \
  --projection "cutout_id,cutout_juno_url" --limit 1000
```

To copy the files between SciNet systems with Globus instead, see [SciNet Setup](scinet-usage.html#2-transfer-the-files). Run that query **without** `--projection`, because the transfer needs the path columns that a projection drops.

---

## Python API

The same queries are available from Python. Each record has `cutout_id`, `image_id`, `image_path`, `mask_path`, `json_path` and `aux_paths`, plus `extras`, a dictionary of every column.

```python
from agir_cvtoolkit.core.db import AgirDB

with AgirDB.connect(
    db_type="semif",
    db_path="/path/to/AgIR_DB_v2_0_202609.db",
    table="semif",
) as db:
    # Filters: keyword arguments (AND; a list means OR), and where() for expressions
    query = db.filter(category_usda_symbol="HOVU", is_primary=1).where("cutout_juno_url IS NOT NULL")
    print(query.count())

    for record in query.limit(5).all():
        print(record.cutout_id, record.extras["cutout_juno_url"])

    # Sampling
    seeded = db.filter(category_usda_symbol="HOVU").sample_seeded(200, seed=42).all()
    balanced = (
        db.filter(category_usda_symbol=["HOVU", "PISA6"], is_primary=1)
        .where("cutout_juno_url IS NOT NULL")
        .sample_stratified(by=["category_common_name", "estimated_area_bin"], per_group=5)
        .all()
    )

    # Sorting and paging
    page2 = db.filter(category_usda_symbol="HOVU").sort("batch_id", "desc").limit(50).offset(50).all()
```

Each builder call changes the query it is called on, so start a fresh `db.filter(...)` for each query.

---

## Quick Reference

### Filters

| Type | Syntax | Example |
|:-----|:-------|:--------|
| Equals | `field=value` | `state=NC` |
| Any of (OR) | `field=a,b` | `category_usda_symbol=HOVU,SECE` |
| All of (AND) | repeat `--filters` | `--filters "state=NC" --filters "is_primary=1"` |
| Greater / less | `field>=value`, `field<=value` | `estimated_bbox_area_cm2>=50` |
| NULL check | `field is null`, `field is not null` | `cutout_juno_url is not null` |

### Sampling

| Strategy | Syntax |
|:---------|:-------|
| Random | `--sample "random:n=100"` |
| Seeded | `--sample "seeded:n=100,seed=42"` |
| Stratified | `--sample "stratified:by=category_common_name,per_group=10"` |
| Stratified, several columns | `--sample "stratified:by=category_common_name\|estimated_area_bin,per_group=5"` |

---

## Next Steps

- **[SciNet Setup](scinet-usage.html)**: copy the database and transfer files
- **[SemiF schema](../dataset/semif.html)**: every column and its meaning
- **[Statistics](../dataset/statistics.html)**: what is in the database now
