---
layout: default
title: Setup & Query Guide
parent: SciNet Usage
grand_parent: Access & Query
nav_order: 1
---

# SciNet Setup & Query Guide
{: .no_toc }

Get the AgIR-CVToolkit running on SciNet and start querying the database.
{: .fs-6 .fw-300 }

---

## Table of Contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Overview

The AgIR dataset lives on **Juno LTS**. The workflow is:

1. Clone the repo and install the toolkit on Ceres
2. Copy the database from Juno to your project space
3. Point the config at your local copy of the database
4. Run `agir-cv query` to select records
5. Run `agir-cv scinet-transfer` to pull the corresponding image files from Juno

---

## 1. Clone the Repo

```bash
git clone https://github.com/precision-sustainable-ag/AgIR-CVToolkit.git
cd AgIR-CVToolkit
```

---

## 2. Copy the Database from Juno

The database needs to be in your project space on Ceres before you can query it. Copy it from Juno LTS at:

```
/LTS/project/dash_agir/semifield-database/AgIR_DB_v1_0_202510.db
```

**Option A — Globus web UI** (easiest)

1. Open [app.globus.org](https://app.globus.org) and log in with your SciNet credentials
2. **Left pane**: Select `SCINet-Juno`, navigate to `/LTS/project/dash_agir/semifield-database/`
3. **Right pane**: Select `SCINet-Ceres`, navigate to `/project/<your_project>/semifield-db/`
4. Select `AgIR_DB_v1_0_202510.db` and click **Start**

**Option B — Globus CLI**

```bash
globus transfer \
  <JUNO_ENDPOINT>:/LTS/project/dash_agir/semifield-database/AgIR_DB_v1_0_202510.db \
  <CERES_ENDPOINT>:/project/<your_project>/semifield-db/AgIR_DB_v1_0_202510.db
```

{: .note }
> Copy to your **project directory**, not your home directory — home quotas are small.

---

## 3. Configure the Database Path

Edit `src/agir_cvtoolkit/conf/db/default.yaml` to point at your local copy:

```yaml
semif:
  db_path: /project/<your_project>/semifield-db/AgIR_DB_v1_0_202510.db
  table: semif
```

Alternatively, override the path inline without editing the file:

```bash
agir-cv query --db semif \
  -o db.semif.db_path=/project/<your_project>/semifield-db/AgIR_DB_v1_0_202510.db \
  --preview 5
```

---

## 4. Install Dependencies and Activate the Environment

Follow the installation instructions in the repo, then activate your environment before running any commands.

---

## 5. Run a Query

### Verify everything is working

```bash
agir-cv query --db semif \
  --sample "stratified:by=category_common_name|estimated_area_bin,per_group=5"
```

Results are written to:

```
outputs/runs/<project>/<subname>/query/
  ├── query.json        ← used by scinet-transfer
  ├── query.csv
  └── query_spec.json   ← full spec for reproducibility
```

The exact run path is printed to the terminal after the query completes.

### Filtering

Multiple `--filters` flags combine with AND logic. Multiple values within one flag use OR logic.

```bash
# Single filter
agir-cv query --db semif --filters "state=NC"

# Multiple values (OR)
agir-cv query --db semif --filters "state=NC,TX,GA"

# Multiple filters (AND)
agir-cv query --db semif \
  --filters "state=NC" \
  --filters "category_common_name=barley"

# Numeric range
agir-cv query --db semif --filters "estimated_bbox_area_cm2>=50"

# Preview without writing output
agir-cv query --db semif --filters "state=NC" --preview 10

# Limit results
agir-cv query --db semif --filters "state=NC" --limit 100
```

### Sampling

```bash
# Random sample
agir-cv query --db semif --sample "random:n=200"

# Seeded (reproducible) — same seed always returns the same records
agir-cv query --db semif --sample "seeded:n=200,seed=42"

# Stratified: N records per species
agir-cv query --db semif \
  --sample "stratified:by=category_common_name,per_group=10"

# Stratified: N records per species × area bin combination
agir-cv query --db semif \
  --sample "stratified:by=category_common_name|estimated_area_bin,per_group=5"
```

### Output Format

```bash
agir-cv query --db semif --filters "state=NC" --out json    # default
agir-cv query --db semif --filters "state=NC" --out csv
agir-cv query --db semif --filters "state=NC" --out parquet
```

---

## 6. Transfer Query Results from Juno

Once you have a query, use `agir-cv scinet-transfer` to pull the corresponding image files from Juno to Ceres (or Atlas). See the [SciNet Transfer Guide](transfer-guide.html) for full details.

```bash
# Install and log in to Globus CLI if you haven't already
pipx install globus-cli
globus login
globus session update --all

# Dry-run first — previews the file list without submitting
agir-cv scinet-transfer

# Submit the actual transfer
agir-cv scinet-transfer --submit
```

---

## Support

- **SciNet Documentation**: [scinet.usda.gov/guides](https://scinet.usda.gov/guides/)
- **SciNet Support**: scinet-support@usda.gov
- **AgIR Toolkit Issues**: [GitHub Issues](https://github.com/precision-sustainable-ag/AgIR-CVToolkit/issues)